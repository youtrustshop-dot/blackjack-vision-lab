"""Owned, family-disjoint training scenes; annotations never enter inference.

This extends the stress laboratory's original artwork, not provider assets.
The existing independent tournament and its sealed final holdout are untouched.
The new verification partition is locked until a selected checkpoint/configuration
has been written. Calibration is for model selection; verification is not.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path
import random
import time

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from bjlab.events import RANKS, SUITS
from validation.tools.stress_lab import digest, save_json

SIZE = (640, 480)
TILE = (112, 156)
PATCH = (48, 72)
CLASSES = ["index", "face_surface", "back"]
# None of the historical validation/final-holdout font families is training input.
PARTITIONS = {
    "train": {"seed": 4101201, "count": 8000,
              "fonts": ["arialbd.ttf", "verdanab.ttf", "timesbd.ttf", "consolab.ttf", "tahomabd.ttf"],
              "family": "owned-mixed-training-v1"},
    "calibration": {"seed": 4101317, "count": 1000,
                    "fonts": ["trebucbd.ttf", "cambriab.ttf"], "family": "owned-trebuchet-cambria-v1"},
    "verification": {"seed": 4101459, "count": 1000,
                     "fonts": ["comicbd.ttf", "palab.ttf"], "family": "owned-comic-palatino-v1"},
}


def project(points, matrix):
    return cv2.perspectiveTransform(np.asarray(points, np.float32)[None], matrix)[0]


def rectify(pixels, quad, size=PATCH):
    """Ordered TL/TR/BR/BL plane estimate. Never generative super-resolution."""
    points = np.asarray(quad, np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Four finite ordered points required")
    area = cv2.contourArea(points, oriented=True)
    if area <= 8 or not cv2.isContourConvex(points):
        raise ValueError("Degenerate or reflected quadrilateral")
    w, h = size
    target = np.float32([[0, 0], [w-1, 0], [w-1, h-1], [0, h-1]])
    return cv2.warpPerspective(pixels, cv2.getPerspectiveTransform(points, target),
                               size, flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                               borderValue=(127, 127, 127))


def bounds(mask):
    ys, xs = np.where(mask)
    return [int(xs.min()), int(ys.min()), int(xs.max()-xs.min()+1), int(ys.max()-ys.min()+1)] if len(xs) else None


def suit_shape(draw, center, radius, suit, fill):
    x, y = center; r = radius
    if suit == "D":
        draw.polygon([(x,y-r),(x+r*.70,y),(x,y+r),(x-r*.70,y)], fill=fill)
    elif suit == "H":
        draw.ellipse((x-r,y-r*.7,x,y+r*.3), fill=fill)
        draw.ellipse((x,y-r*.7,x+r,y+r*.3), fill=fill)
        draw.polygon([(x-r*.95,y),(x+r*.95,y),(x,y+r)], fill=fill)
    elif suit == "C":
        for cx,cy in ((x,y-r*.5),(x-r*.55,y+r*.05),(x+r*.55,y+r*.05)):
            draw.ellipse((cx-r*.5,cy-r*.5,cx+r*.5,cy+r*.5), fill=fill)
        draw.polygon([(x-r*.3,y+r),(x+r*.3,y+r),(x,y)], fill=fill)
    else:
        draw.polygon([(x,y-r),(x-r*.85,y+r*.05),(x+r*.85,y+r*.05)], fill=fill)
        draw.ellipse((x-r*.85,y-r*.2,x,y+r*.6), fill=fill)
        draw.ellipse((x,y-r*.2,x+r*.85,y+r*.6), fill=fill)
        draw.polygon([(x-r*.35,y+r),(x+r*.35,y+r),(x,y)], fill=fill)


def artwork(rank, suit, back, font_path, rng):
    """Original vector/glyph artwork; local fonts are used, never redistributed."""
    image = Image.new("RGBA", TILE)
    draw = ImageDraw.Draw(image)
    paper = tuple(rng.randint(210, 255) for _ in range(3))+(255,)
    draw.rounded_rectangle((0,0,111,155), radius=rng.choice([2,5,8]), fill=paper,
                           outline=(100,100,100,255), width=1)
    rank_mask = Image.new("L", TILE); suit_mask = Image.new("L", TILE)
    if back:
        color = rng.choice(["#23425b", "#685483", "#2765a5", "#b52943", "#246954"])
        draw.rounded_rectangle((5,5,106,150), 5, fill=color)
        spacing = rng.randint(5, 12)
        for y in range(10,150,spacing): draw.line((7,y,104,y), fill="#c3b3d8", width=1)
        # Texture is deliberately not a rank/suit label.
        return np.asarray(image), np.asarray(rank_mask), np.asarray(suit_mask)
    ink = rng.choice(["#a92032", "#c42a38", "#77223a"]) if suit in "HD" else rng.choice(["#172028", "#333333", "#101020"])
    rank_size = rng.randint(27, 33)
    font = ImageFont.truetype(str(font_path), rank_size)
    draw.text((8,8), rank, font=font, fill=ink, anchor="lt")
    ImageDraw.Draw(rank_mask).text((8,8), rank, font=font, fill=255, anchor="lt")
    # Both font-rendered and vector pips prevent training on one glyph template.
    if rng.random() < .45:
        symbol = dict(zip("SHDC", "♠♥♦♣"))[suit]
        pipfont = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", rng.randint(24,29))
        draw.text((9,42), symbol, font=pipfont, fill=ink, anchor="lt")
        ImageDraw.Draw(suit_mask).text((9,42), symbol, font=pipfont, fill=255, anchor="lt")
    else:
        suit_shape(draw, (22,55), 12, suit, ink)
        suit_shape(ImageDraw.Draw(suit_mask), (22,55), 12, suit, 255)
    suit_shape(draw, (67,99), rng.randint(18,30), suit, ink)
    draw.text((101,145), rank, font=ImageFont.truetype(str(font_path), 18), fill=ink, anchor="rb")
    return np.asarray(image), np.asarray(rank_mask), np.asarray(suit_mask)


def scene(partition, index, font_root=Path("C:/Windows/Fonts")):
    spec = PARTITIONS[partition]
    parent_seed = spec["seed"]*100000 + index//8
    rng = random.Random(parent_seed*8 + index%8)
    width, height = SIZE
    background = rng.choice([(15,84,61),(8,70,81),(27,41,67),(67,32,48),(115,107,84)])
    pixels = np.full((height,width,3), background, np.uint8)
    # Hard negatives: printed labels, chip-like circles and card-like popups.
    for _ in range(rng.randint(1,5)):
        x,y = rng.randrange(width), rng.randrange(height)
        cv2.circle(pixels, (x,y), rng.randint(10,30), (165,151,87), 2)
        cv2.putText(pixels, rng.choice(["20","100","K","HIT","3 TO 2","J","7"]),
                    (x,y), cv2.FONT_HERSHEY_SIMPLEX, rng.uniform(.3,.7), (170,180,135), 1, cv2.LINE_AA)
    n = 0 if index % 17 == 0 else rng.randint(1,7)
    overlapped = index % 3 == 0
    layers = []
    for j in range(n):
        font_path = font_root/rng.choice(spec["fonts"])
        rank = rng.choice(RANKS); suit = rng.choice(SUITS); back = rng.random() < .17
        tile, rank_ink, suit_ink = artwork(rank,suit,back,font_path,rng)
        size = rng.uniform(.55, 1.12)
        angle = rng.uniform(-50,50) if index % 4 else rng.uniform(-8,8)
        if index % 29 == 0: angle += 180
        c,s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        rotation = np.float32([[c,-s],[s,c]])
        original = np.float32([[0,0],[111,0],[111,155],[0,155]])
        quad = (original-[55.5,77.5])@rotation.T*size
        quad += np.float32([rng.uniform(-5,5),rng.uniform(-5,5)])
        for k in range(4): quad[k] += np.float32([rng.uniform(-5,5),rng.uniform(-5,5)])
        if overlapped:
            quad += [130+j*36, 170 if j%4 < 2 else 340]
        else:
            quad += [rng.uniform(35,605), rng.uniform(50,430)]
        transform = cv2.getPerspectiveTransform(original,quad.astype(np.float32))
        warped = cv2.warpPerspective(tile,transform,SIZE,flags=cv2.INTER_LINEAR)
        alpha = warped[:,:,3].astype(np.float32)/255
        covered = alpha > .5
        for previous in layers:
            for key in ("body","rank_mask","suit_mask"): previous[key][covered] = 0
        pixels = (warped[:,:,:3]*alpha[:,:,None]+pixels*(1-alpha[:,:,None])).astype(np.uint8)
        rmask = cv2.warpPerspective(rank_ink,transform,SIZE,flags=cv2.INTER_NEAREST)
        smask = cv2.warpPerspective(suit_ink,transform,SIZE,flags=cv2.INTER_NEAREST)
        # Exact projected ink before screen clipping/occlusion, rather than an
        # affine size**2 approximation under perspective.
        qmin=np.floor(quad.min(axis=0)).astype(int); qmax=np.ceil(quad.max(axis=0)).astype(int)
        local_size=tuple((qmax-qmin+3).tolist())
        shift=np.float32([[1,0,-qmin[0]+1],[0,1,-qmin[1]+1],[0,0,1]])@transform
        total_r=float(cv2.warpPerspective(rank_ink,shift,local_size,flags=cv2.INTER_NEAREST).sum())
        total_s=float(cv2.warpPerspective(suit_ink,shift,local_size,flags=cv2.INTER_NEAREST).sum())
        layers.append({"rank":rank,"suit":suit,"face_down":back,"body":covered.astype(np.uint8),
                       "rank_mask":rmask,"suit_mask":smask,"rank_total":total_r,"suit_total":total_s,
                       "body_quad":quad, "index_quad":project([[4,4],[51,4],[51,75],[4,75]],transform),
                       "font":font_path.name})
    popup = index%11 == 0 and n
    if popup:
        x,y = rng.randint(50,450),rng.randint(80,350); w,h = rng.randint(70,160),rng.randint(45,100)
        cv2.rectangle(pixels,(x,y),(x+w,y+h),(224,222,214),-1)
        cv2.putText(pixels,"CLOSE",(x+8,y+23),cv2.FONT_HERSHEY_SIMPLEX,.5,(50,60,70),1)
        for layer in layers:
            for key in ("body","rank_mask","suit_mask"): layer[key][y:y+h+1,x:x+w+1] = 0
    # Photometric variation preserves the truth coordinates and masks.
    if index % 5 == 0:
        mean = float(pixels.mean()); contrast = rng.uniform(.35,.7)
        pixels = np.clip((pixels.astype(np.float32)-mean)*contrast+mean,0,255).astype(np.uint8)
    if index % 7 == 0: pixels = cv2.GaussianBlur(pixels,(3,3),rng.uniform(.3,1.1))
    if index % 9 == 0:
        noise = np.random.default_rng(parent_seed+index).normal(0,2.5,pixels.shape)
        pixels = np.clip(pixels.astype(np.float32)+noise,0,255).astype(np.uint8)
    _, jpg = cv2.imencode(".jpg",cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR),[cv2.IMWRITE_JPEG_QUALITY,rng.randint(70,96)])
    pixels = cv2.cvtColor(cv2.imdecode(jpg,cv2.IMREAD_COLOR),cv2.COLOR_BGR2RGB)
    objects=[]; annotations=[]; crops=[]
    for number,layer in enumerate(layers):
        box = bounds(layer["body"])
        rfrac = min(1.,float(layer["rank_mask"].sum())/max(1.,layer["rank_total"]))
        sfrac = min(1.,float(layer["suit_mask"].sum())/max(1.,layer["suit_total"]))
        # Fraction is renderer visibility, not calibrated human legibility.
        observed_rank = layer["rank"] if rfrac >= .90 and not layer["face_down"] else None
        observed_suit = layer["suit"] if sfrac >= .90 and not layer["face_down"] else None
        objects.append({"object":number,"bbox":box,"body_quad":layer["body_quad"].tolist(),
                        "index_quad":layer["index_quad"].tolist(),"rank":observed_rank,"suit":observed_suit,
                        "physical_rank":layer["rank"] if not layer["face_down"] else None,
                        "presence":"absent" if box is None else "covered" if layer["face_down"] else "readable" if observed_rank else "unreadable",
                        "rank_visible_fraction":rfrac,"suit_visible_fraction":sfrac,"font":layer["font"]})
        if box is None: continue
        annotations.append((2 if layer["face_down"] else 1,box,layer["body_quad"],layer["body"]))
        if not layer["face_down"] and (rfrac > .30 or sfrac > .30):
            index_mask = np.zeros((height,width),np.uint8)
            cv2.fillConvexPoly(index_mask,np.round(layer["index_quad"]).astype(np.int32),1)
            index_mask *= layer["body"]
            index_box = bounds(index_mask)
            if index_box:
                annotations.append((0,index_box,layer["index_quad"],layer["body"]))
                try: patch = rectify(pixels,layer["index_quad"])
                except ValueError: continue
                crops.append((patch, RANKS.index(observed_rank) if observed_rank else 13,
                              SUITS.index(observed_suit) if observed_suit else 4,"card_index"))
                # Deliberate independent erasures teach abstention rather than guess.
                if number == 0:
                    cut = patch.copy()
                    if index%2: cut[:36] = rng.randint(80,240); ri,si = 13,(SUITS.index(observed_suit) if observed_suit else 4)
                    else: cut[36:] = rng.randint(80,240); ri,si = (RANKS.index(observed_rank) if observed_rank else 13),4
                    crops.append((cut,ri,si,"erased_index"))
    # Printed decoration/body centers are classifier negatives; never card IDs.
    occupied=np.zeros((height,width),bool)
    for layer in layers: occupied |= layer["body"].astype(bool)
    for _ in range(30):
        x,y = rng.randint(0,width-48),rng.randint(0,height-72)
        if occupied[y:y+72,x:x+48].mean() < .01:
            crops.append((pixels[y:y+72,x:x+48].copy(),13,4,"background_negative"))
            break
    labels=[]
    for cls,(x,y,w,h),quad,mask in annotations:
        points=[]
        for px,py in quad:
            ix,iy = int(round(px)),int(round(py))
            inside = 0<=ix<width and 0<=iy<height
            visibility = 2 if inside and mask[iy,ix] else 1 if inside else 0
            points.extend([min(1,max(0,float(px)/width)),min(1,max(0,float(py)/height)),visibility])
        labels.append([cls,(x+w/2)/width,(y+h/2)/height,w/width,h/height,*points])
    return pixels, labels, crops, {"index":index,"parent_seed":parent_seed,"objects":objects,
                                  "overlap":bool(overlapped),"popup":bool(popup)}


def generate(output, counts=None):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    specs = {k:dict(v,count=(counts or {}).get(k,v["count"])) for k,v in PARTITIONS.items()}
    fonts={str(Path("C:/Windows/Fonts")/name):digest(Path("C:/Windows/Fonts")/name)
           for spec in specs.values() for name in spec["fonts"]}
    plan={"schema":1,"created_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),
          "generator_sha256":digest(__file__),"partitions":specs,"size":SIZE,"patch_size":PATCH,
          "classes":CLASSES,"keypoints":["top_left","top_right","bottom_right","bottom_left"],
          "rank_classes":[*RANKS,None],"suit_classes":[*SUITS,None],"font_sha256":fonts,
          "source":"Owned renderer/vector artwork; locally installed fonts are not redistributed.",
          "split_policy":"Parent seed and rank-font artwork families disjoint; shared vector-pip/renderer mechanics remain a transfer limitation.",
          "visibility_policy":"Independent rank/suit ink >=90%; absent, unreadable, covered and readable retained. All visible bodies annotated, including tiny/clipped bodies.",
          "historical_final_holdout":"Untouched; neither labels nor frames are read.","api_requests":0}
    save_json(output/"pre_generation_freeze.json",plan)
    for part,spec in specs.items():
        (output/"images"/part).mkdir(parents=True); (output/"labels"/part).mkdir(parents=True)
        (output/"crops"/part).mkdir(parents=True)
        rows=[]; patches=[]; totals=Counter()
        started=time.perf_counter()
        for i in range(spec["count"]):
            pixels,labels,crops,truth=scene(part,i)
            name=f"{part}-{i:05d}"
            image_path=output/"images"/part/f"{name}.png"
            cv2.imwrite(str(image_path),cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR))
            label_path=output/"labels"/part/f"{name}.txt"
            label_path.write_text("\n".join(" ".join(str(round(v,7)) for v in row) for row in labels)+"\n",encoding="utf-8")
            for j,(pixels,rank,suit,kind) in enumerate(crops):
                relative=f"crops/{part}/{name}-{j}.png"; p=output/relative
                cv2.imwrite(str(p),cv2.cvtColor(pixels,cv2.COLOR_RGB2BGR))
                patches.append({"path":relative,"sha256":digest(p),"parent":name,"rank":rank,"suit":suit,"kind":kind})
                totals[f"rank_{rank}"]+=1; totals[f"suit_{suit}"]+=1
            truth.update({"image":f"images/{part}/{name}.png","image_sha256":digest(image_path),
                          "label_sha256":digest(label_path)})
            rows.append(truth)
            if (i+1)%500==0: print(json.dumps({"partition":part,"generated":i+1,"total":spec["count"]}),flush=True)
        save_json(output/f"{part}.truth.json",rows); save_json(output/f"{part}.crops.json",patches)
        receipt={"images":len(rows),"crops":len(patches),"class_counts":dict(totals),
                 "truth_sha256":digest(output/f"{part}.truth.json"),"crops_sha256":digest(output/f"{part}.crops.json"),
                 "elapsed_seconds":time.perf_counter()-started}
        save_json(output/f"{part}.receipt.json",receipt)
        plan["partitions"][part].update(receipt)
    yaml="path: "+str(output).replace("\\","/")+"\ntrain: images/train\nval: images/calibration\nkpt_shape: [4, 3]\nflip_idx: [0, 1, 2, 3]\nnames:\n  0: index\n  1: face_surface\n  2: back\n"
    (output/"data.yaml").write_text(yaml,encoding="utf-8")
    save_json(output/"manifest.json",plan)
    print(json.dumps({"generated":sum(s["count"] for s in specs.values()),"manifest_sha256":digest(output/"manifest.json")}),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--smoke",action="store_true")
    args=parser.parse_args(); generate(args.output,{"train":64,"calibration":16,"verification":16} if args.smoke else None)
