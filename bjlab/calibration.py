"""Geometric calibration and explicit pixel-derived table labels.

Geometry calibration rectifies a user-selected local table plane. Text templates
support the controlled renderer, while optional Tesseract is real OCR when installed.
Neither path reads simulator state to manufacture observations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any, Iterable, Mapping

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .datasets import card_font, THEMES, bbox_iou
from .vision import CardDetection, _rgb


@dataclass(frozen=True)
class NormalizedROI:
    x: float
    y: float
    width: float
    height: float

    def __post_init__(self) -> None:
        values = (self.x, self.y, self.width, self.height)
        if (any(not math.isfinite(v) for v in values) or self.x < 0 or self.y < 0 or
                self.width <= 0 or self.height <= 0 or self.x + self.width > 1 + 1e-9 or
                self.y + self.height > 1 + 1e-9):
            raise ValueError("Normalized ROI must be a finite positive rectangle inside [0,1]")

    def to_pixels(self, width: int, height: int) -> tuple[int, int, int, int]:
        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive")
        # Decimal ROI values can produce 60.00000000000001 after addition.
        # Pixel rounding ignores only sub-billionth-pixel arithmetic artifacts.
        left, top = math.floor(self.x * width + 1e-9), math.floor(self.y * height + 1e-9)
        right = min(width, max(left + 1, math.ceil((self.x + self.width) * width - 1e-9)))
        bottom = min(height, max(top + 1, math.ceil((self.y + self.height) * height - 1e-9)))
        return left, top, right - left, bottom - top

    def crop(self, image: Image.Image | np.ndarray | str | Path) -> np.ndarray:
        pixels = _rgb(image)
        x, y, w, h = self.to_pixels(pixels.shape[1], pixels.shape[0])
        return pixels[y:y + h, x:x + w].copy()

    def to_dict(self) -> dict[str, float]:
        return asdict(self)

    @classmethod
    def from_pixels(cls, box: Iterable[float], width: int, height: int) -> "NormalizedROI":
        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive")
        x, y, w, h = tuple(box)
        return cls(x / width, y / height, w / width, h / height)


def controlled_table_zones() -> dict[str, NormalizedROI]:
    """Default regions in the renderer's canonical plane; callers can override."""
    return {"dealer": NormalizedROI(.03, .12, .94, .32),
            "player": NormalizedROI(.03, .48, .94, .35),
            "rules": NormalizedROI(.25, .045, .70, .06),
            "controls": NormalizedROI(.03, .85, .94, .12)}


def validate_corners(corners: Iterable[Iterable[float]], image_width: int, image_height: int,
                     *, normalized: bool = False) -> np.ndarray:
    points = np.asarray(list(corners), dtype=np.float64)
    if points.shape != (4, 2) or not np.all(np.isfinite(points)):
        raise ValueError("Calibration requires four finite 2D points TL,TR,BR,BL")
    if image_width < 2 or image_height < 2:
        raise ValueError("Calibration image is too small")
    if normalized:
        if np.any(points < 0) or np.any(points > 1):
            raise ValueError("Normalized corners must lie in [0,1]")
        points *= np.array([image_width - 1, image_height - 1])
    if (np.any(points[:, 0] < 0) or np.any(points[:, 0] > image_width - 1) or
            np.any(points[:, 1] < 0) or np.any(points[:, 1] > image_height - 1)):
        raise ValueError("Calibration corners lie outside the source image")
    edges = np.roll(points, -1, axis=0) - points
    crosses = [float(edges[i, 0] * edges[(i + 1) % 4, 1] -
                     edges[i, 1] * edges[(i + 1) % 4, 0]) for i in range(4)]
    if any(cross <= 1e-6 for cross in crosses):
        raise ValueError("Corners must be strictly convex and ordered TL,TR,BR,BL clockwise")
    if any(float(np.linalg.norm(edge)) < 4 for edge in edges):
        raise ValueError("Calibration edges are too short")
    area = .5 * abs(float(np.dot(points[:, 0], np.roll(points[:, 1], -1)) -
                            np.dot(points[:, 1], np.roll(points[:, 0], -1))))
    if area < 16:
        raise ValueError("Calibration plane has insufficient area")
    return points


def _transform_points(points: Iterable[Iterable[float]], homography: np.ndarray) -> np.ndarray:
    arr = np.asarray(list(points), dtype=np.float64)
    if arr.ndim != 2 or arr.shape[1] != 2 or not np.all(np.isfinite(arr)):
        raise ValueError("Points must be a finite Nx2 matrix")
    homogeneous = np.column_stack((arr, np.ones(len(arr)))) @ homography.T
    if np.any(np.abs(homogeneous[:, 2]) < 1e-12):
        raise ValueError("Projection maps a point to infinity")
    return homogeneous[:, :2] / homogeneous[:, 2, None]


@dataclass(frozen=True)
class CalibratedFrame:
    image_rgb: np.ndarray
    homography: np.ndarray
    inverse_homography: np.ndarray
    source_corners: np.ndarray
    source_size: tuple[int, int]
    output_size: tuple[int, int]

    @property
    def image(self) -> np.ndarray:
        return self.image_rgb

    def map_points_to_source(self, points: Iterable[Iterable[float]]) -> np.ndarray:
        return _transform_points(points, self.inverse_homography)

    def map_points_to_canonical(self, points: Iterable[Iterable[float]]) -> np.ndarray:
        return _transform_points(points, self.homography)

    def map_bbox_to_source(self, bbox: Iterable[float]) -> tuple[int, int, int, int]:
        x, y, w, h = tuple(bbox)
        if w <= 0 or h <= 0:
            raise ValueError("Bounding box must have positive area")
        points = self.map_points_to_source(((x, y), (x + w, y), (x + w, y + h), (x, y + h)))
        left, top = np.floor(points.min(axis=0)).astype(int)
        right, bottom = np.ceil(points.max(axis=0)).astype(int)
        left, top = max(0, left), max(0, top)
        right, bottom = min(self.source_size[0], right), min(self.source_size[1], bottom)
        if right <= left or bottom <= top:
            raise ValueError("Mapped bounding box falls outside source image")
        return int(left), int(top), int(right - left), int(bottom - top)

    def map_detection_to_source(self, detection: CardDetection) -> CardDetection:
        return CardDetection(detection.rank, detection.suit, self.map_bbox_to_source(detection.bbox),
                             detection.score, detection.face_down, detection.zone, detection.logical_hint,
                             detection.calibrated_probability, detection.score_type)

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": 1, "source_size": list(self.source_size),
                "output_size": list(self.output_size), "source_corners": self.source_corners.tolist(),
                "homography": self.homography.tolist(),
                "inverse_homography": self.inverse_homography.tolist(),
                "coordinate_contract": "source TL,TR,BR,BL -> canonical image corners"}


def normalize_table(image: Image.Image | np.ndarray | str | Path,
                    corners: Iterable[Iterable[float]], outputsize: tuple[int, int] = (960, 600),
                    *, corners_normalized: bool = False) -> CalibratedFrame:
    """Rectify an explicit four-corner table plane with an invertible homography."""
    cv2.setNumThreads(1)
    rgb = _rgb(image)
    width, height = outputsize
    if (type(width) is not int or type(height) is not int or
            not 16 <= width <= 4096 or not 16 <= height <= 2160):
        raise ValueError("Canonical output must be integer dimensions from 16 to 4096x2160")
    points = validate_corners(corners, rgb.shape[1], rgb.shape[0], normalized=corners_normalized)
    target = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], dtype=np.float32)
    homography = cv2.getPerspectiveTransform(points.astype(np.float32), target).astype(np.float64)
    if not np.all(np.isfinite(homography)) or np.linalg.cond(homography) > 1e12:
        raise ValueError("Calibration transform is numerically unstable")
    inverse = np.linalg.inv(homography)
    normalized_image = cv2.warpPerspective(rgb, homography, (width, height),
                                          flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)
    return CalibratedFrame(normalized_image, homography, inverse, points,
                           (rgb.shape[1], rgb.shape[0]), (width, height))


@dataclass(frozen=True)
class TextLabelDetection:
    text: str
    bbox: tuple[int, int, int, int]
    score: float
    score_type: str = "text_template_similarity"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


RULE_LABELS = ("H17", "S17", "PEEK", "NPEEK", "AHC", "ENHC", "DAS", "NDAS", "RSA", "NRSA", "ES", "LS", "NS",
               "BJ3:2", "BJ6:5", "D1", "D2", "D4", "D6", "D8")
BUTTON_LABELS = ("HIT", "STAND", "DOUBLE", "SPLIT", "SURRENDER", "DEAL", "NEW SHOE",
                 "INSURANCE", "DECLINE INSURANCE", "CONTINUE")


class TemplateTextDetector:
    """Finite-vocabulary recognition of actually rendered bright label pixels.

    This is a controlled text-template matcher, not arbitrary OCR. The public
    vocabulary is configuration, not a list of truth answers from the session.
    """
    def __init__(self, labels: Iterable[str], *, font_size: int = 16,
                 font_path: str | None = None, minimum_score: float = .92) -> None:
        cv2.setNumThreads(1)
        if not 6 <= font_size <= 96 or not 0 <= minimum_score <= 1:
            raise ValueError("Invalid text detector parameters")
        self.minimum_score = minimum_score
        self.templates: dict[str, list[np.ndarray]] = {}
        font = card_font(font_size, font_path)
        for label in labels:
            if not label:
                raise ValueError("Text vocabulary cannot contain an empty label")
            left, top, right, bottom = font.getbbox(label, anchor="lt")
            prototypes = []
            for background in ((0, 0, 0), *THEMES.values()):
                tile = Image.new("RGB", (right - left + 6, bottom - top + 6), background)
                ImageDraw.Draw(tile).text((3 - left, 3 - top), label, font=font,
                                          fill=(212, 220, 213), anchor="lt")
                prototypes.append(self._mask(np.asarray(tile)))
            self.templates[label] = prototypes

    @staticmethod
    def _mask(rgb: np.ndarray) -> np.ndarray:
        hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
        return ((hsv[:, :, 2] >= 135) & (hsv[:, :, 1] <= 95)).astype(np.float32)

    def detect(self, image: Image.Image | np.ndarray | str | Path,
               roi: NormalizedROI | None = None) -> list[TextLabelDetection]:
        rgb = _rgb(image)
        ox = oy = 0
        if roi is not None:
            ox, oy, w, h = roi.to_pixels(rgb.shape[1], rgb.shape[0])
            rgb = rgb[oy:oy + h, ox:ox + w]
        mask = self._mask(rgb)
        detections: list[TextLabelDetection] = []
        for label, prototypes in self.templates.items():
            template = prototypes[0]
            th, tw = template.shape
            if th > mask.shape[0] or tw > mask.shape[1]:
                continue
            # Antialiasing changes foreground threshold coverage with the felt
            # color. Explicit renderer-theme prototypes retain the same threshold
            # and vocabulary rather than lowering acceptance for short labels.
            response = np.maximum.reduce([cv2.matchTemplate(mask, prototype, cv2.TM_CCORR_NORMED)
                                          for prototype in prototypes])
            response = np.nan_to_num(response, nan=0, posinf=0, neginf=0)
            while True:
                _, score, _, pos = cv2.minMaxLoc(response)
                if score < self.minimum_score:
                    break
                x, y = pos
                detections.append(TextLabelDetection(label, (x + ox, y + oy, tw, th),
                                                     min(1, max(0, float(score)))))
                response[max(0, y - th // 2):min(response.shape[0], y + th // 2 + 1),
                         max(0, x - tw // 2):min(response.shape[1], x + tw // 2 + 1)] = 0
        # Similar glyphs (e.g. D6/D8) may exceed the absolute threshold at the
        # same physical token. Compare competing labels at that token instead
        # of interpreting them as two separate rendered rule statements.
        kept: list[TextLabelDetection] = []
        def contains(outer: tuple[int, int, int, int], inner: tuple[int, int, int, int]) -> bool:
            x, y, w, h = outer
            ix, iy, iw, ih = inner
            return x <= ix + 1 and y <= iy + 1 and x + w >= ix + iw - 1 and y + h >= iy + ih - 1
        for detection in sorted(detections, key=lambda d: d.score, reverse=True):
            # An exact word inside an exact longer button label is a substring,
            # not a separately visible control (INSURANCE / DECLINE INSURANCE).
            if any(detection.text != previous.text and detection.text in previous.text and
                   contains(previous.bbox, detection.bbox) for previous in kept):
                continue
            kept = [previous for previous in kept if not (
                previous.text != detection.text and previous.text in detection.text and
                contains(detection.bbox, previous.bbox))]
            competing = [previous for previous in kept if bbox_iou(previous.bbox, detection.bbox) > .5]
            if not competing or max(previous.score for previous in competing) - detection.score <= .01:
                # Near-equal alternatives remain observable ambiguity.
                kept.append(detection)
        return sorted(kept, key=lambda d: (d.bbox[1], d.bbox[0], d.text))


def extract_controlled_metadata(image: Image.Image | np.ndarray | str | Path) -> dict[str, Any]:
    """Read controlled rule/button glyphs with uncertainty for conflicting labels."""
    pixels = _rgb(image)
    zones = controlled_table_zones()
    rule_detections = TemplateTextDetector(RULE_LABELS).detect(pixels, zones["rules"])
    button_detections = TemplateTextDetector(BUTTON_LABELS).detect(pixels, zones["controls"])
    present = {d.text for d in rule_detections}
    issues = []
    def choose(*options: str) -> str | None:
        seen = [option for option in options if option in present]
        if len(seen) > 1:
            issues.append(f"Conflicting pixel labels {'/'.join(seen)}")
            return None
        return seen[0] if seen else None
    soft = choose("H17", "S17")
    hole = choose("AHC", "ENHC")
    if hole is None and "AHC" not in present and "ENHC" not in present and "PEEK" in present:
        hole = "PEEK"  # Legacy controlled fixtures represented American hole-card by PEEK.
    peek = choose("PEEK", "NPEEK")
    das = choose("DAS", "NDAS")
    rsa = choose("RSA", "NRSA")
    surrender = choose("ES", "LS", "NS")
    payout = choose("BJ3:2", "BJ6:5")
    decks_seen = [int(tag[1:]) for tag in present if tag in {"D1", "D2", "D4", "D6", "D8"}]
    if len(decks_seen) > 1:
        issues.append("Conflicting pixel labels for deck count")
    return {"schema_version": 1, "source": "pixel_text_templates",
            "rules": {"soft17": soft, "hole_card": hole, "peek": peek, "das": das, "rsa": rsa,
                      "surrender": surrender, "blackjack_payout": payout,
                      "decks": decks_seen[0] if len(decks_seen) == 1 else None},
            "rule_detections": [d.to_dict() for d in rule_detections],
            "button_detections": [d.to_dict() for d in button_detections],
            "issues": issues, "probability_of_correct_rules": None,
            "scope": "controlled uppercase label glyphs at canonical scale/font; absent fields are unknown"}


class TesseractAdapter:
    """Optional OCR via a real installed Tesseract executable and TSV output."""
    def __init__(self, executable: str | Path | None = None, *, language: str = "eng",
                 timeout_seconds: float = 10) -> None:
        resolved = str(executable) if executable else shutil.which("tesseract")
        if not resolved or not Path(resolved).is_file():
            raise RuntimeError("Tesseract is not installed; controlled template labels remain available")
        if not language or any(character not in "abcdefghijklmnopqrstuvwxyz_+" for character in language):
            raise ValueError("Invalid Tesseract language code")
        if timeout_seconds <= 0:
            raise ValueError("OCR timeout must be positive")
        self.executable, self.language, self.timeout_seconds = resolved, language, timeout_seconds

    def recognize(self, image: Image.Image | np.ndarray | str | Path,
                  roi: NormalizedROI | None = None, *, psm: int = 6) -> list[TextLabelDetection]:
        import csv
        from io import StringIO
        if type(psm) is not int or not 0 <= psm <= 13:
            raise ValueError("Invalid Tesseract page segmentation mode")
        rgb = _rgb(image)
        ox = oy = 0
        if roi is not None:
            ox, oy, w, h = roi.to_pixels(rgb.shape[1], rgb.shape[0])
            rgb = rgb[oy:oy + h, ox:ox + w]
        with tempfile.TemporaryDirectory(prefix="bjlab-ocr-") as directory:
            source = Path(directory) / "roi.png"
            Image.fromarray(rgb).save(source)
            result = subprocess.run([self.executable, str(source), "stdout", "-l", self.language,
                                     "--psm", str(psm), "tsv"], capture_output=True, text=True,
                                    timeout=self.timeout_seconds, check=False,
                                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        if result.returncode != 0:
            raise RuntimeError(f"Tesseract failed: {result.stderr.strip()[:200]}")
        detections = []
        for row in csv.DictReader(StringIO(result.stdout), delimiter="\t"):
            text = (row.get("text") or "").strip()
            if not text:
                continue
            confidence = float(row["conf"])
            if confidence < 0:
                continue
            box = (int(row["left"]) + ox, int(row["top"]) + oy,
                   int(row["width"]), int(row["height"]))
            detections.append(TextLabelDetection(text, box, min(1, confidence / 100),
                                                 "tesseract_score_not_calibrated_probability"))
        return detections
