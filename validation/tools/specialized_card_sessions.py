"""Predeclared new legal sessions for the trained-reader verification.

Reuse the existing engine/scenarios and owned stress renderer. These are paired
difficulty renderings of two new six-round sessions, not 12 independent sessions.
The renderer's truth is stored separately and remains evaluator-only.
"""
import argparse
from dataclasses import asdict
from pathlib import Path

import cv2
import numpy as np

from validation.tools.independent_tournament import scenario_timeline, render, game_rules, BASELINE
from validation.tools.stress_lab import PROFILES, LAYOUT, SIZE, FPS, digest, save_json

FAMILIES=[
    {"seed":4101883,"family":"new-comic-verification","font":"C:/Windows/Fonts/comicbd.ttf",
     "paper":"#f8f2ed","back":"#356c64","stripe":"#ccded9","accent":"#c3aa78"},
    {"seed":4101887,"family":"new-palatino-verification","font":"C:/Windows/Fonts/palab.ttf",
     "paper":"#edf5f7","back":"#62365e","stripe":"#d9c2d6","accent":"#c3aa78"},
]


def generate(output):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    target=output/"validation"; target.mkdir()
    plan={"schema":1,"generator_sha256":digest(__file__),"families":FAMILIES,"fps":FPS,
          "size":SIZE,"layout":LAYOUT,"rules":asdict(game_rules()),"baseline_commit":BASELINE,
          "scope":"Two new physical engine sessions, six paired difficulty renderings each. Not independent provider engines.",
          "verification_used":False,"api_requests":0,"historical_final_holdout":"sealed_untouched"}
    save_json(output/"pre_generation_freeze.json",plan)
    manifest={"schema":1,"partition":"validation","kind":"own-synthetic-continuous-video","layout":LAYOUT,
              "fps":FPS,"rules":asdict(game_rules()),"sessions":[],"families":FAMILIES,"api_requests":0,
              "generator_sha256":digest(__file__)}
    for family in FAMILIES:
        stages=scenario_timeline(family["seed"])
        for profile,parameters in PROFILES.items():
            name=f"{family['seed']}-{family['family']}-{profile}"
            video=target/f"{name}.webm"
            writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*"VP80"),FPS,SIZE)
            if not writer.isOpened(): raise RuntimeError("VP8 encoder unavailable")
            rows=[]; frame=0; seen={}
            try:
                for stage in stages:
                    cached=None
                    for tick in range(round(stage["duration"]*FPS)):
                        if cached is None or stage["phase"]=="dealing": cached=render(stage,parameters,family,tick)
                        image,truth=cached
                        writer.write(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR))
                        for card in truth:
                            if card["presence"]!="absent_from_pixels" and card["physical_rank"]: seen[card["card_id"]]=card["physical_rank"]
                        rows.append({"frame":frame,"timestamp_ms":frame*1000/FPS,"round":stage["round"],
                                     "phase":stage["phase"],"scenario":stage["scenario"],"cards":truth,"seen":dict(seen)})
                        frame+=1
            finally: writer.release()
            truth_path=target/f"{name}.truth.json"; save_json(truth_path,rows)
            manifest["sessions"].append({"name":name,"profile":profile,"group":family["family"],"seed":family["seed"],
                "frames":frame,"video":video.name,"video_sha256":digest(video),"truth":truth_path.name,
                "truth_sha256":digest(truth_path),"parameters":parameters,"font_sha256":digest(family["font"])})
            print({"generated_session":name,"frames":frame},flush=True)
    save_json(target/"manifest.json",manifest)
    save_json(output/"freeze.json",{"schema":1,"baseline_commit":BASELINE,"generator_sha256":digest(__file__),
        "manifests":{"validation":{"path":"validation/manifest.json","sha256":digest(target/"manifest.json")}},
        "independent_physical_sessions":2,"paired_difficulty_renderings":6,"api_requests":0,
        "verification_status":"locked_until_reader_selection","historical_final_holdout":"sealed_untouched"})


if __name__=="__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--output",type=Path,required=True)
    generate(parser.parse_args().output)
