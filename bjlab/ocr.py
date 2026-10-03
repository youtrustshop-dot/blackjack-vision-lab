"""Offline, bounded CPU text recognition using an attributed PaddleOCR model.

The resize/CTC contract follows RapidOCR / PaddleOCR (Apache-2.0). Input pixels,
not game memory or labels, are the only source of recognized text.
"""
from functools import lru_cache
import hashlib
import math
from pathlib import Path
import threading

import cv2
import numpy as np

MODEL_SHA256 = "48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b"
_lock = threading.RLock()
_session = None
_characters = None


def _runtime():
    global _session, _characters
    with _lock:
        if _session is None:
            import onnxruntime as ort
            path = Path(__file__).parent / "assets/ocr/ch_PP-OCRv4_rec_infer.onnx"
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256:
                raise RuntimeError("The bundled card OCR model is missing or damaged. Reinstall the current app.")
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.log_severity_level = 3
            _session = ort.InferenceSession(str(path), sess_options=options, providers=["CPUExecutionProvider"])
            _characters = [""] + _session.get_modelmeta().custom_metadata_map["character"].splitlines() + [" "]
        return _session, _characters


@lru_cache(maxsize=512)
def _read_cached(shape, content):
    rgb = np.frombuffer(content, dtype=np.uint8).reshape(shape)
    h, w = rgb.shape[:2]
    width = max(1, math.ceil(48 * w / h))
    if width > 1024:
        return "", 0.
    scaled = cv2.resize(rgb[:, :, ::-1], (width, 48)).astype(np.float32) / 127.5 - 1.
    batch = np.zeros((1, 3, 48, max(320, width)), dtype=np.float32)
    batch[0, :, :, :width] = scaled.transpose(2, 0, 1)
    session, characters = _runtime()
    with _lock:
        output = session.run(None, {session.get_inputs()[0].name: batch})[0][0]
    ids = output.argmax(1)
    keep = (ids != 0) & np.r_[True, ids[1:] != ids[:-1]]
    if not keep.any():
        return "", 0.
    return "".join(characters[i] for i in ids[keep]).strip(), float(output.max(1)[keep].mean())


def read_text(rgb):
    image = np.ascontiguousarray(rgb, dtype=np.uint8)
    if image.ndim != 3 or image.shape[2] != 3 or min(image.shape[:2]) < 3 or image.size > 1_000_000:
        return "", 0.
    return _read_cached(image.shape, image.tobytes())


def read_light_text(rgb):
    """Read a light-on-dark label, excluding the panel border."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    ink = (hsv[:, :, 1] < 115) & (hsv[:, :, 2] > 160)
    # Compression can turn isolated gold-border pixels white. They must not
    # stretch a one-digit label into a panel-wide OCR crop. Preserve the actual
    # grayscale strokes while bounding only text-sized connected components.
    _, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    valid=[i for i,(_,_,w,h,area) in enumerate(stats) if i and h>=3 and area>=4]
    ink=np.isin(labels,valid)
    yy, xx = np.where(ink)
    if len(xx) < 5:
        return "", 0.
    # A white background is robust for the recognizer's normal text contract.
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    bw = 255-gray[yy.min():yy.max()+1, xx.min():xx.max()+1]
    bw = cv2.normalize(bw, None, 0, 255, cv2.NORM_MINMAX)
    bw = cv2.copyMakeBorder(bw, 3, 3, 3, 3, cv2.BORDER_CONSTANT, value=255)
    return read_text(np.repeat(bw[:, :, None], 3, axis=2))
