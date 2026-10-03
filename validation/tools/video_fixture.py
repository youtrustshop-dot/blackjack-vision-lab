"""Make an original, single-round local clip for pixel/replay acceptance tests."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import cv2
import numpy as np
from bjlab.datasets import render_table

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    writer=cv2.VideoWriter(str(args.output),cv2.VideoWriter_fourcc(*"MJPG"),30,(960,600))
    if not writer.isOpened():raise RuntimeError("Local MJPG writer unavailable")
    cards=[{"rank":"6","suit":"D","x":60,"y":60},
           {"rank":None,"suit":None,"face_down":True,"x":150,"y":60},
           {"rank":"A","suit":"S","x":60,"y":310},
           {"rank":"8","suit":"C","x":150,"y":310}]
    try:
        for index in range(9):
            image=render_table(cards,theme="green")
            writer.write(cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR))
    finally:writer.release()
    print(args.output)

if __name__=="__main__":main()
