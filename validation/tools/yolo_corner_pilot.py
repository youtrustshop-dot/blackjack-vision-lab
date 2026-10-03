"""Contained optional Ultralytics experiment; own synthetic glyph annotations.

Runs only in a separate research environment. No upstream weights, external
screenshots, telemetry or cloud training. This is not a production dependency.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
RANKS=('A','2','3','4','5','6','7','8','9','10','J','Q','K')


def offline_configuration(root):
    root=Path(root).resolve();config_base=root/'ultralytics-config';config=config_base/'Ultralytics';config.mkdir(parents=True,exist_ok=True)
    os.environ['YOLO_CONFIG_DIR']=str(config_base)
    os.environ['YOLO_OFFLINE']='true'
    os.environ['MPLCONFIGDIR']=str(root/'matplotlib-cache')
    os.environ['OMP_NUM_THREADS']='4'
    document={'settings_version':'0.0.6','datasets_dir':str(root/'data'),'weights_dir':str(root/'weights'),
        'runs_dir':str(root/'runs'),'uuid':'local-research-no-telemetry','sync':False,'api_key':'','openai_api_key':'',
        **{key:False for key in ('clearml','comet','dvc','hub','mlflow','neptune','raytune','tensorboard','wandb','vscode_msg','openvino_msg')}}
    (config/'settings.json').write_text(json.dumps(document),encoding='utf-8')
    import shutil
    font=ROOT/'bjlab/assets/fonts/DejaVuSans-Bold.ttf'
    if not font.is_file():font=ROOT/'assets/fonts/DejaVuSans-Bold.ttf'
    if not font.is_file():font=Path('C:/Windows/Fonts/arial.ttf')
    if font.is_file():shutil.copyfile(font,config/'Arial.ttf')
    # Guard network use in this process, including accidental auto-downloads.
    import socket
    def forbidden(*args,**kwargs):raise RuntimeError('Network access is disabled for this local pilot.')
    socket.socket.connect=forbidden
    from ultralytics import settings
    assert not settings['sync'] and not settings['hub']


def generate(root,train=128,validation=32):
    from PIL import Image,ImageDraw,ImageFont
    root=Path(root).resolve(); manifest=[]
    if (root/'manifest.json').exists():raise ValueError('Do not overwrite a generated dataset.')
    fonts=[ROOT/'bjlab/assets/fonts/DejaVuSans-Bold.ttf',ROOT/'assets/fonts/DejaVuSans-Bold.ttf',
        Path('C:/Windows/Fonts/arial.ttf'),Path('C:/Windows/Fonts/times.ttf'),Path('C:/Windows/Fonts/cour.ttf')]
    fonts=[str(p) for p in fonts if p.is_file()]
    if not fonts:raise ValueError('A local font is required.')
    for split,count,seed in [('train',train,711307),('val',validation,292907)]:
        rng=random.Random(seed)
        for index in range(count):
            image=Image.new('RGB',(416,320),(rng.randrange(0,100),rng.randrange(20,130),rng.randrange(20,130)))
            draw=ImageDraw.Draw(image);labels=[]
            for row in range(2):
                for col in range(3):
                    x=25+col*125+rng.randrange(-8,9);y=18+row*150+rng.randrange(-5,6)
                    rank=rng.choice(RANKS); size=rng.randrange(15,31)
                    font=ImageFont.truetype(rng.choice(fonts),size)
                    fill=(rng.randrange(215,256),rng.randrange(215,256),rng.randrange(200,256))
                    draw.rounded_rectangle((x,y,x+80,y+120),radius=6,fill=fill)
                    gx,gy=x+5,y+5; color='black' if rng.random()<.5 else '#d82f38'
                    draw.text((gx,gy),rank,font=font,fill=color,anchor='lt')
                    bounds=draw.textbbox((gx,gy),rank,font=font,anchor='lt');a,b,c,d=bounds
                    labels.append(f'{RANKS.index(rank)} {(a+c)/2/416:.8f} {(b+d)/2/320:.8f} {(c-a)/416:.8f} {(d-b)/320:.8f}')
                    draw.text((x+5,y+size+10),rng.choice(('S','H','D','C')),font=ImageFont.truetype(font.path,13),fill=color)
                    # A second corner is decoration, not a second physical card.
                    draw.text((x+58,y+90),rank,font=ImageFont.truetype(font.path,12),fill=color,anchor='lt')
            folder=root/'images'/split;folder.mkdir(parents=True,exist_ok=True)
            output=folder/f'{index:04}.png';image.save(output)
            lab=root/'labels'/split;lab.mkdir(parents=True,exist_ok=True)
            (lab/(output.stem+'.txt')).write_text('\n'.join(labels)+'\n')
            manifest.append({'file':output.relative_to(root).as_posix(),'split':split,'group':f'synthetic:{split}:{index}',
                'sha256':hashlib.sha256(output.read_bytes()).hexdigest()})
    document={'schema':1,'scope':'own synthetic rank-corner drawings; no real provider training images',
        'classes':list(RANKS),'files':manifest,'seeds':{'train':711307,'validation':292907}}
    (root/'manifest.json').write_text(json.dumps(document,indent=2))
    import yaml
    (root/'data.yaml').write_text(yaml.safe_dump({'path':str(root),'train':'images/train','val':'images/val',
        'names':dict(enumerate(RANKS))},sort_keys=False))
    return root/'data.yaml'


def train(root,epochs=8):
    root=Path(root).resolve();offline_configuration(root)
    import torch
    torch.set_num_threads(4)
    from ultralytics import YOLO,__version__
    data=generate(root/'data'); began=time.perf_counter()
    model=YOLO('yolo26n.yaml')
    result=model.train(data=str(data),epochs=epochs,imgsz=416,batch=8,device='cpu',workers=0,
        amp=False,pretrained=False,plots=False,save=True,project=str(root/'runs'),name='rank-corners',
        exist_ok=False,seed=483107,deterministic=True,optimizer='AdamW',lr0=.002,
        mosaic=0,fliplr=0,flipud=0,degrees=0,translate=.05,scale=.10,verbose=False)
    checkpoint=Path(model.trainer.best)
    report={'schema':1,'ultralytics':__version__,'torch':torch.__version__,'device':'cpu','model':'yolo26n.yaml',
        'initialization':'random scratch, no pretrained COCO weights','classes':list(RANKS),
        'checkpoint_sha256':hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        'data_manifest_sha256':hashlib.sha256((root/'data/manifest.json').read_bytes()).hexdigest(),
        'epochs':epochs,'wall_seconds':time.perf_counter()-began,'validation_metrics':result.results_dict,
        'telemetry':False,'external_uploads':False,'license':'Ultralytics AGPL-3.0; no distribution promotion',
        'scope':'small synthetic training pilot, not proof of provider generalization'}
    (root/'training.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


_models={}
def detect(image,layout,checkpoint):
    if not _models:offline_configuration(Path(checkpoint).resolve().parents[3])
    from bjlab.calibration import NormalizedROI
    from bjlab.vision import CardDetection
    from ultralytics import YOLO
    import numpy as np
    checkpoint=str(Path(checkpoint).resolve())
    if checkpoint not in _models:_models[checkpoint]=YOLO(checkpoint)
    results=[]
    for zone in ('dealer','player:0'):
        roi=NormalizedROI(*layout[zone]);x,y,w,h=roi.to_pixels(*image.size)
        predictions=_models[checkpoint].predict(roi.crop(image),imgsz=416,conf=.50,device='cpu',verbose=False)[0]
        for bounds,confidence,label in zip(predictions.boxes.xyxy.tolist(),predictions.boxes.conf.tolist(),predictions.boxes.cls.tolist()):
            a,b,c,d=bounds;glyph_h=d-b
            results.append(CardDetection(predictions.names[int(label)],None,
                (x+max(0,a-3),y+max(0,b-5),min(w-a,glyph_h*5),min(h-b,glyph_h*7)),confidence,
                zone=zone,score_type='uncalibrated_ultralytics_score'))
    return results


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--epochs',type=int,default=8);args=parser.parse_args();train(args.root,args.epochs)
