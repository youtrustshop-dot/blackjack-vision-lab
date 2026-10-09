"""Offline GPU research: YOLO26n four-keypoint localizer + learned 13+4 reader.

Official DetectionModel weights initialize the compatible backbone, NOT a card
or pose head. The head is trained on owned annotations. Our checkpoints contain
only state dictionaries; external deserialization remains restricted and hashed.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
import time

import numpy as np

from validation.tools.stress_lab import digest, save_json


def dataset_audit(data):
    data=Path(data).resolve(); manifest=json.loads((data/"manifest.json").read_text(encoding="utf-8"))
    fonts=[]; seeds=[]
    for partition in ("train","calibration","verification"):
        spec=manifest["partitions"][partition]
        if digest(data/f"{partition}.truth.json") != spec["truth_sha256"]: raise ValueError("Truth manifest changed")
        if digest(data/f"{partition}.crops.json") != spec["crops_sha256"]: raise ValueError("Crop manifest changed")
        fonts.append(set(spec["fonts"])); seeds.append(spec["seed"])
        # Audit immutable files without reading verification labels into training.
        if partition == "verification": continue
        rows=json.loads((data/f"{partition}.truth.json").read_text(encoding="utf-8"))
        for row in rows:
            if digest(data/row["image"]) != row["image_sha256"]: raise ValueError("Image changed")
            label=data/"labels"/partition/(Path(row["image"]).stem+".txt")
            if digest(label) != row["label_sha256"]: raise ValueError("Annotation changed")
            for line in label.read_text(encoding="utf-8").splitlines():
                if not line.strip(): continue
                values=np.asarray([float(v) for v in line.split()])
                if len(values)!=17 or not np.isfinite(values).all() or int(values[0]) not in (0,1,2): raise ValueError("Invalid pose annotation")
                if not np.all((values[1:5]>=0)&(values[1:5]<=1)) or min(values[3:5])<=0: raise ValueError("Invalid normalized box")
                pts=values[5:].reshape(4,3)
                if not np.all((pts[:,:2]>=0)&(pts[:,:2]<=1)) or not np.isin(pts[:,2],[0,1,2]).all(): raise ValueError("Invalid keypoint/visibility")
    if len(set(seeds))!=3 or any(fonts[i]&fonts[j] for i in range(3) for j in range(i+1,3)):
        raise ValueError("Partition contamination")
    return manifest


def classifier_model():
    import torch.nn as nn
    class RankSuit(nn.Module):
        def __init__(self):
            super().__init__()
            self.features=nn.Sequential(nn.Conv2d(3,32,3,padding=1),nn.BatchNorm2d(32),nn.ReLU(),nn.MaxPool2d(2),
                nn.Conv2d(32,64,3,padding=1),nn.BatchNorm2d(64),nn.ReLU(),nn.MaxPool2d(2),
                nn.Conv2d(64,96,3,padding=1),nn.BatchNorm2d(96),nn.ReLU(),nn.MaxPool2d(2))
            self.shared=nn.Sequential(nn.Flatten(),nn.Linear(96*9*6,256),nn.ReLU(),nn.Dropout(.10))
            self.rank=nn.Linear(256,14); self.suit=nn.Linear(256,5)
        def forward(self,x):
            features=self.shared(self.features(x))
            return self.rank(features),self.suit(features)
    return RankSuit()


def load_crops(data,partition):
    import cv2
    rows=json.loads((data/f"{partition}.crops.json").read_text(encoding="utf-8"))
    arrays=[]
    for row in rows:
        path=data/row["path"]
        if digest(path)!=row["sha256"]: raise ValueError("Crop changed")
        image=cv2.cvtColor(cv2.imread(str(path)),cv2.COLOR_BGR2RGB)
        if image.shape!=(72,48,3): raise ValueError("Wrong patch dimensions")
        arrays.append(image.transpose(2,0,1))
    return np.stack(arrays),np.asarray([[r["rank"],r["suit"]] for r in rows],np.int64)


def train_classifier(data,output,epochs=24):
    import torch
    from torch.nn import functional as F
    torch.manual_seed(4101501); np.random.seed(4101501)
    train,targets=load_crops(data,"train"); val,labels=load_crops(data,"calibration")
    train=torch.from_numpy(train); targets=torch.from_numpy(targets)
    val=torch.from_numpy(val); labels=torch.from_numpy(labels)
    model=classifier_model().cuda(); optimizer=torch.optim.AdamW(model.parameters(),lr=.0015,weight_decay=.0001)
    weights=[]
    for head,n in ((0,14),(1,5)):
        freq=torch.bincount(targets[:,head],minlength=n).float()
        weight=(freq.mean()/freq.clamp(min=1)).sqrt().clamp(.4,3).cuda(); weights.append(weight)
    best=-1.; curve=[]; began=time.perf_counter()
    for epoch in range(epochs):
        model.train(); loss_sum=0.; order=torch.randperm(len(train)); start=time.perf_counter()
        for left in range(0,len(order),256):
            idx=order[left:left+256]
            x=train[idx].cuda().float()/255.; y=targets[idx].cuda()
            # Small sampling errors; large rotation/perspective are normalized by
            # the four-point localizer, not guessed from a full-card rectangle.
            theta=torch.eye(2,3,device=x.device).repeat(len(x),1,1)
            theta[:,0,2]=(torch.rand(len(x),device=x.device)-.5)*.05
            theta[:,1,2]=(torch.rand(len(x),device=x.device)-.5)*.05
            x=F.grid_sample(x,F.affine_grid(theta,x.shape,align_corners=False),padding_mode="border",align_corners=False)
            optimizer.zero_grad(set_to_none=True); rank,suit=model(x)
            loss=F.cross_entropy(rank,y[:,0],weight=weights[0])+F.cross_entropy(suit,y[:,1],weight=weights[1])
            loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(),5); optimizer.step()
            loss_sum+=float(loss.detach())*len(idx)
        model.eval(); predicted=[]; logits=[]
        with torch.inference_mode():
            for left in range(0,len(val),256):
                a,b=model(val[left:left+256].cuda().float()/255.)
                predicted.append(torch.stack([a.argmax(1),b.argmax(1)],1).cpu())
                logits.append((a.softmax(1).cpu(),b.softmax(1).cpu()))
        prediction=torch.cat(predicted); correct=prediction==labels
        joint=float(correct.all(1).float().mean())
        row={"epoch":epoch+1,"loss":loss_sum/len(train),"rank_raw_accuracy":float(correct[:,0].float().mean()),
             "suit_raw_accuracy":float(correct[:,1].float().mean()),"joint_raw_accuracy":joint,
             "seconds":time.perf_counter()-start,"partition":"calibration"}
        curve.append(row); print(json.dumps({"classifier":row}),flush=True)
        if joint>best:
            best=joint; torch.save({"schema":1,"state_dict":{k:v.detach().cpu() for k,v in model.state_dict().items()},
                                  "epoch":epoch+1,"architecture":"rank-suit-conv-v1"},output/"classifier-best.pt")
            torch.save({"rank":torch.cat([r for r,s in logits]),"suit":torch.cat([s for r,s in logits]),"labels":labels},output/"calibration-logits.pt")
    save_json(output/"classifier-learning.json",{"train_crops":len(train),"calibration_crops":len(val),"curve":curve,
          "best_calibration_joint":best,"checkpoint_sha256":digest(output/"classifier-best.pt"),
          "elapsed_seconds":time.perf_counter()-began,"verification_used":False,"score_type":"uncalibrated softmax scores"})
    return output/"classifier-best.pt"


def train_pose(data,output,official,epochs=40,budget=2400,imgsz=512,batch=12):
    import torch
    import yaml
    import ultralytics
    from ultralytics.models.yolo.pose.train import PoseTrainer
    from ultralytics.nn.tasks import PoseModel
    from validation.tools.yolo_learning_check import restricted_pretrained
    weights,origin=restricted_pretrained(official)
    cfg_path=Path(ultralytics.__file__).parent/"cfg/models/26/yolo26-pose.yaml"
    cfg=yaml.safe_load(cfg_path.read_text(encoding="utf-8")); cfg.update(nc=3,kpt_shape=[4,3],scale="n")
    architecture=output/"yolo26n-card-pose.yaml"; architecture.write_text(yaml.safe_dump(cfg),encoding="utf-8")
    model=PoseModel(cfg,ch=3,nc=3,data_kpt_shape=[4,3],verbose=False)
    compatible={k:v for k,v in weights.float().state_dict().items()
                if k in model.state_dict() and model.state_dict()[k].shape==v.shape}
    model.load_state_dict(compatible,strict=False)
    origin.update({"transferred_tensors":len(compatible),"target_tensors":len(model.state_dict()),
                   "initialization":"Official YOLO26n COCO detection-compatible tensors; new 3-class 4-keypoint head is not pretrained on cards."})
    class TensorOnlyTrainer(PoseTrainer):
        def save_model(self):
            payload={"schema":1,"state_dict":{k:v.detach().float().cpu() for k,v in self.ema.ema.state_dict().items()},
                     "epoch":self.epoch,"architecture":cfg,"fitness":self.fitness}
            torch.save(payload,self.last)
            if self.best_fitness==self.fitness: torch.save(payload,self.best)
        def final_eval(self):
            # No upstream strip_optimizer/load_checkpoint(unrestricted pickle).
            return
    overrides=dict(model=str(architecture),data=str(data/"data.yaml"),epochs=epochs,imgsz=imgsz,batch=batch,device=0,
        workers=0,amp=False,pretrained=False,plots=False,save=True,project=str(output/"runs"),name="pose",
        exist_ok=False,seed=4101502,deterministic=True,optimizer="AdamW",lr0=.0015,warmup_epochs=1,
        mosaic=0,fliplr=0,flipud=0,degrees=0,translate=0,scale=0,hsv_h=0,hsv_s=0,hsv_v=0,
        erasing=0,patience=12,verbose=False,val=True)
    trainer=TensorOnlyTrainer(overrides=overrides); trainer.model=model
    began=time.perf_counter(); deadline=began+budget
    def cap(trainer):
        if time.perf_counter()>=deadline: trainer.stop=True
        print(json.dumps({"pose_epoch":trainer.epoch+1,"elapsed_seconds":time.perf_counter()-began,
                          "budget_seconds":budget,"fitness":trainer.fitness}),flush=True)
    trainer.add_callback("on_fit_epoch_end",cap)
    trainer.train()
    path=trainer.best if trainer.best.exists() else trainer.last
    report={"schema":1,"ultralytics":ultralytics.__version__,"torch":torch.__version__,"cuda":torch.version.cuda,
            "gpu":torch.cuda.get_device_name(0),"gpu_capability":torch.cuda.get_device_capability(0),
            "origin":origin,"imgsz":imgsz,"batch":batch,"requested_epochs":epochs,"actual_epochs":trainer.epoch+1,
            "budget_seconds":budget,"elapsed_seconds":time.perf_counter()-began,"checkpoint_path":str(path),
            "checkpoint_sha256":digest(path),"architecture_sha256":digest(architecture),"metrics":trainer.metrics,
            "verification_used":False,"telemetry":False,"uploads":False,"checkpoint_format":"state_dict only, weights_only=True reload"}
    save_json(output/"pose-learning.json",report)
    return path


def export_models(output,pose_path,classifier_path,imgsz):
    import torch
    import onnx
    import onnxruntime as ort
    from ultralytics.nn.tasks import PoseModel
    pose_payload=torch.load(pose_path,map_location="cpu",weights_only=True)
    pose=PoseModel(pose_payload["architecture"],ch=3,nc=3,data_kpt_shape=[4,3],verbose=False)
    pose.load_state_dict(pose_payload["state_dict"]); pose=pose.float().eval().requires_grad_(False)
    for module in pose.modules():
        if hasattr(module,"export"): module.export=True; module.format="onnx"
    class PoseExport(torch.nn.Module):
        def __init__(self,model):
            super().__init__(); self.model=model
            # Keep the trained one-to-one branch, but export raw anchors rather
            # than TopK: low-score ties reorder differently between runtimes.
            # Selection/suppression is explicit and auditable in our adapter.
            self.model.model[-1].postprocess=lambda predictions: predictions
        def forward(self,x):
            y=self.model(x)
            return y[0] if isinstance(y,tuple) else y
    wrapper=PoseExport(pose)
    example=torch.rand(1,3,imgsz,imgsz)
    # Export tracing must not reuse anchor tensors created in inference_mode.
    with torch.no_grad(): expected=wrapper(example).numpy()
    path=output/"card-pose.onnx"
    torch.onnx.export(wrapper,example,str(path),input_names=["image"],output_names=["detections"],
                       opset_version=17,dynamo=False)
    classifier=classifier_model(); payload=torch.load(classifier_path,map_location="cpu",weights_only=True)
    classifier.load_state_dict(payload["state_dict"]); classifier.eval()
    patch=torch.rand(3,3,72,48)
    cpath=output/"rank-suit.onnx"
    torch.onnx.export(classifier,patch,str(cpath),input_names=["patch"],output_names=["rank","suit"],
                     dynamic_axes={"patch":{0:"batch"},"rank":{0:"batch"},"suit":{0:"batch"}},opset_version=17,dynamo=False)
    checks={}
    for target,inputs,truths in ((path,example,[expected]),(cpath,patch,[v.detach().numpy() for v in classifier(patch)])):
        onnx.checker.check_model(str(target))
        options=ort.SessionOptions(); options.intra_op_num_threads=4
        session=ort.InferenceSession(str(target),sess_options=options,providers=["CPUExecutionProvider"])
        actual=session.run(None,{session.get_inputs()[0].name:inputs.numpy()})
        deltas=[float(np.abs(a-b).max()) for a,b in zip(actual,truths)]
        tolerance=.1 if target==path else .005
        checks[target.name]={"sha256":digest(target),"maximum_absolute_difference":deltas,"absolute_tolerance":tolerance,
                             "output_shapes":[list(a.shape) for a in actual]}
        save_json(output/"export-parity.json",checks)
        if any(d>tolerance for d in deltas): raise ValueError("ONNX export parity failed")
    manifest={"schema":1,"reader_version":"specialized-card-v1","model_family":"YOLO26n-pose",
              "imgsz":imgsz,"classes":["index","face_surface","back"],"keypoint_shape":[4,3],
              "rank_classes":["A","2","3","4","5","6","7","8","9","10","J","Q","K",None],
              "suit_classes":["S","H","D","C",None],"exports":checks,"pose_model":"card-pose.onnx","classifier_model":"rank-suit.onnx",
              "thresholds":{"proposal":.30,"rank":.85,"suit":.80,"margin":.15},
              "coordinate_contract":"raw one-to-one rows: xyxy, three class scores, four (x,y,keypoint score) triples; scaled letterbox pixels",
              "score_type":"uncalibrated model/softmax scores, not probabilities of correctness",
              "geometry":"Estimated index plane; no claim that hidden whole-card corners were observed",
              "license":"Research-only Ultralytics-derived model; AGPL/Enterprise obligations survive export; not bundled or distributed",
              "verification_used":False,"api_requests":0}
    save_json(output/"reader.json",manifest)
    return manifest


def run(data,output,official,epochs=40,budget=2400):
    from validation.tools.yolo_corner_pilot import offline_configuration
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=False)
    offline_configuration(output)
    import torch
    torch.set_num_threads(4)
    if not torch.cuda.is_available(): raise RuntimeError("CUDA environment not usable; preserve failure, do not silently change experiment")
    manifest=dataset_audit(data); data=Path(data).resolve()
    plan={"schema":1,"data_manifest_sha256":digest(data/"manifest.json"),"training_source_sha256":digest(__file__),
          "requested_pose_epochs":epochs,"pose_budget_seconds":budget,"classifier_epochs":24,"imgsz":512,"batch":12,
          "partition_counts":{k:v["count"] for k,v in manifest["partitions"].items()},
          "thresholds_initial":{"proposal":.30,"rank":.85,"suit":.80,"margin":.15},
          "gate":"Research challenger only. No promotion unless same-input state accuracy/coverage improve without added false-current states; R2 evaluated separately.",
          "verification_access":"Locked until selected reader.json is created; no tuning after verification.","api_requests":0,"historical_final_holdout":"sealed_untouched"}
    save_json(output/"pre_training_freeze.json",plan)
    pose_path=train_pose(data,output,official,epochs,budget)
    classifier_path=train_classifier(data,output)
    exported=export_models(output,pose_path,classifier_path,512)
    print(json.dumps({"reader_sha256":digest(output/"reader.json"),"exports":exported["exports"]}),flush=True)


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("--data",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True); parser.add_argument("--official",type=Path,required=True)
    parser.add_argument("--epochs",type=int,default=40); parser.add_argument("--budget-seconds",type=int,default=2400)
    parser.add_argument("--export-only",action="store_true")
    args=parser.parse_args()
    if args.export_only:
        from validation.tools.yolo_corner_pilot import offline_configuration
        offline_configuration(args.output)
        pose=json.loads((args.output/"pose-learning.json").read_text(encoding="utf-8"))
        reader=json.loads((args.output/"classifier-learning.json").read_text(encoding="utf-8"))
        pose_path=Path(pose["checkpoint_path"]); classifier_path=args.output/"classifier-best.pt"
        if digest(pose_path)!=pose["checkpoint_sha256"] or digest(classifier_path)!=reader["checkpoint_sha256"]: raise ValueError("Own checkpoint changed")
        export_models(args.output,pose_path,classifier_path,pose["imgsz"])
    else:
        run(args.data,args.output,args.official,args.epochs,args.budget_seconds)
