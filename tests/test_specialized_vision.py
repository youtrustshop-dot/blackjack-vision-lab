"""Contracts and geometry, not synthetic claims of model accuracy."""
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from bjlab.specialized_vision import decoded_label, ordered_rectification, spatial_suppression, SpecializedCardDetector


def test_ordered_projective_rectification_preserves_visible_mark():
    patch=np.full((72,48,3),230,np.uint8); patch[8:22,9:24]=[210,20,40]
    source=np.float32([[0,0],[47,0],[47,71],[0,71]])
    destination=np.float32([[44,13],[89,39],[60,112],[11,84]])
    matrix=cv2.getPerspectiveTransform(source,destination)
    screen=cv2.warpPerspective(patch,matrix,(128,128),borderValue=(25,30,40))
    recovered=ordered_rectification(screen,destination)
    assert np.max(np.abs(recovered[10:20,11:22].astype(int)-patch[10:20,11:22]))<10


@pytest.mark.parametrize("points",[
    [[0,0],[20,0],[20,0],[0,0]],
    [[0,0],[0,20],[20,20],[20,0]],
    [[0,0],[20,0],[float('nan'),20],[0,20]],
])
def test_unusable_plane_is_not_presented_as_normalized_card(points):
    with pytest.raises(ValueError): ordered_rectification(np.zeros((32,32,3),np.uint8),points)


def test_rectification_cannot_recover_offscreen_pixels():
    image=np.zeros((64,64,3),np.uint8)
    crop=ordered_rectification(image,[[-30,-40],[18,-40],[18,32],[-30,32]])
    assert np.all(crop[:20]==127)


def test_equal_faces_are_never_deduplicated_by_label():
    proposals=[{"class":0,"score":.9,"bbox":(10,20,20,40),"rank":"7","suit":"C"},
               {"class":0,"score":.85,"bbox":(50,20,20,40),"rank":"7","suit":"C"},
               {"class":0,"score":.8,"bbox":(11,20,20,40),"rank":"7","suit":"C"}]
    result=spatial_suppression(proposals)
    assert len(result)==2 and [p["bbox"][0] for p in result]==[10,50]


def test_low_margin_or_unknown_head_abstains_independently():
    labels=["H","D","C","S",None]
    assert decoded_label(np.asarray([.46,.45,.04,.03,.02]),labels,.4,.1)[0] is None
    assert decoded_label(np.asarray([.02,.02,.02,.02,.92]),labels,.8,.1)[0] is None
    assert decoded_label(np.asarray([.91,.02,.02,.03,.02]),labels,.8,.1)[0]=="H"


def manifest_for(tmp_path):
    exports={}
    for name in ("pose.onnx","reader.onnx"):
        target=tmp_path/name; target.write_bytes(name.encode())
        exports[name]={"sha256":hashlib.sha256(target.read_bytes()).hexdigest()}
    spec={"schema":1,"model_family":"YOLO26n-pose","reader_version":"contract-mock",
          "imgsz":128,"pose_model":"pose.onnx","classifier_model":"reader.onnx","exports":exports,
          "thresholds":{"proposal":.3,"rank":.85,"suit":.8,"margin":.15},"score_type":"uncalibrated"}
    path=tmp_path/"reader.json"; path.write_text(json.dumps(spec),encoding="utf-8")
    return path


def test_corrupted_or_escaping_model_receipt_fails_before_execution(tmp_path):
    path=manifest_for(tmp_path)
    (tmp_path/"pose.onnx").write_bytes(b"changed")
    with pytest.raises(ValueError,match="hash mismatch"): SpecializedCardDetector(path)
    spec=json.loads(path.read_text()); spec["pose_model"]="../outside.onnx"
    path.write_text(json.dumps(spec))
    with pytest.raises(ValueError,match="escapes"): SpecializedCardDetector(path)


def test_mock_model_contract_keeps_two_equal_faces_and_unknown_suit(tmp_path,monkeypatch):
    import onnxruntime as ort
    class Session:
        def __init__(self,path,**kwargs): self.pose=Path(path).name=="pose.onnx"
        def get_inputs(self): return [type("Input",(),{"name":"input"})()]
        def run(self,outputs,inputs):
            if not self.pose:
                ranks=np.full((2,14),-8,np.float32); ranks[:,6]=8
                suits=np.full((2,5),-8,np.float32); suits[0,3]=8; suits[1,4]=8
                return [ranks,suits]
            rows=[]
            for x in (10,70):
                # Full surfaces and upper index patches are reconciled into two
                # physical objects, not four objects or one deduplicated 7C.
                rows.append([x,10,x+40,100,0,.8,0,*np.asarray([[x,10,1],[x+40,10,1],[x+40,100,1],[x,100,1]]).ravel()])
                rows.append([x+2,12,x+22,48,.7,0,0,*np.asarray([[x+2,12,1],[x+22,12,1],[x+22,48,1],[x+2,48,1]]).ravel()])
            return [np.asarray([rows],np.float32)]
    monkeypatch.setattr(ort,"InferenceSession",Session)
    detector=SpecializedCardDetector(manifest_for(tmp_path))
    found=detector.detect(np.zeros((128,128,3),np.uint8))
    assert len(found)==2 and [d.rank for d in found]==["7","7"]
    assert found[0].suit=="C" and found[1].suit is None
    assert all(d.score==pytest.approx(.7) for d in found)
    assert detector.tracking_minimum_score==.3


def test_training_family_and_parent_seeds_are_disjoint():
    from validation.tools.specialized_card_data import PARTITIONS
    partitions=list(PARTITIONS.values())
    assert len({s["seed"] for s in partitions})==3
    assert not any(set(a["fonts"])&set(b["fonts"]) for i,a in enumerate(partitions) for b in partitions[i+1:])
    assert not set(PARTITIONS["train"]["fonts"])&{"seguisb.ttf","georgiab.ttf"}


def test_native_table_crop_returns_source_coordinates_and_excludes_other_windows(tmp_path,monkeypatch):
    import onnxruntime as ort
    tensors=[]
    class Session:
        def __init__(self,path,**kwargs): self.pose=Path(path).name=='pose.onnx'
        def get_inputs(self): return [type('Input',(),{'name':'input'})()]
        def run(self,outputs,inputs):
            if self.pose:
                tensors.append(inputs['input'])
                return [np.asarray([[[10,10,50,100,0,.8,0,10,10,1,50,10,1,50,100,1,10,100,1],
                                     [12,12,32,48,.7,0,0,12,12,1,32,12,1,32,48,1,12,48,1]]],np.float32)]
            rank=np.full((1,14),-8,np.float32); rank[0,6]=8
            suit=np.full((1,5),-8,np.float32); suit[0,3]=8
            return [rank,suit]
    monkeypatch.setattr(ort,'InferenceSession',Session)
    image=np.full((128,256,3),22,np.uint8); image[:,128:]=91
    detector=SpecializedCardDetector(manifest_for(tmp_path),{'table':(.5,0,.5,1),'player:0':(.5,0,.5,1)})
    found=detector.detect(image)
    assert len(found)==1 and found[0].bbox==(138,10,40,90)
    assert np.allclose(tensors[0],91/255.)
    assert detector.last_diagnostics['native_region']==[128,0,128,128]


def test_one_physical_card_straddling_regions_does_not_become_two_objects(tmp_path,monkeypatch):
    import onnxruntime as ort
    class Session:
        def __init__(self,path,**kwargs): self.pose=Path(path).name=='pose.onnx'
        def get_inputs(self): return [type('Input',(),{'name':'input'})()]
        def run(self,outputs,inputs):
            if self.pose:
                return [np.asarray([[[10,10,50,126,0,.8,0,10,10,1,50,10,1,50,126,1,10,126,1],
                                     [12,12,32,48,.7,0,0,12,12,1,32,12,1,32,48,1,12,48,1]]],np.float32)]
            rank=np.full((1,14),-8,np.float32); rank[0,6]=8
            suit=np.full((1,5),-8,np.float32); suit[0,3]=8
            return [rank,suit]
    monkeypatch.setattr(ort,'InferenceSession',Session)
    detector=SpecializedCardDetector(manifest_for(tmp_path),{'dealer':(0,0,1,.5),'player:0':(0,.5,1,.5)})
    found=detector.detect(np.zeros((128,128,3),np.uint8))
    assert len(found)==1 and found[0].zone=='dealer' and found[0].bbox==(10,10,40,116)
    assert detector.last_diagnostics['unmatched_surface_count']==0
