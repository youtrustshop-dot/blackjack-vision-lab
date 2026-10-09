"""Validation/scoring/decoder unit contracts; none are provider evidence."""
import copy
import json
from pathlib import Path
import pytest
from validation.tools import provider_session_replay as replay


def truth():
    return {'intervals':[{'start_s':0,'end_s':4,'boundary':'observable',
        'boundary_evidence':'Unit annotation only','history_complete':True,
        'observed_rank_inventory':{'2':1,'3':1,'6':1},'expected_action':'stand',
        'turn':'player','action_reference':'Unit scoring fixture, not strategy evidence',
        'player':['2','3'],'dealer':['6'],'round_label':'unit-1'}],
        'exposures':[{'instance_id':str(i),'time_s':0,'rank':r,'zone':z,'suit':None}
            for i,(r,z) in enumerate([('2','player:0'),('3','player:0'),('6','dealer')])],
        'manual_interventions':[]}


def manifest(tmp_path):
    video=tmp_path/'unit.avi';video.write_bytes(b'Unit manifest file, not a provider video')
    labels=tmp_path/'truth.json';labels.write_text(json.dumps(truth()))
    row={'session_id':'unit-1','capture_run_id':'unit-run-1','partition':'development',
         'video':video.name,'video_sha256':replay.digest(video),'annotations':labels.name,
         'annotations_sha256':replay.digest(labels),'source_size':[100,80],
         'authorization':{'local_analysis':True,'external_upload':False},
         'input_kind':'original-provider-video','provenance':'Unit validation metadata only',
         'rules_provenance':'Unit declared assumptions','annotation_review':'Unit review fixture',
         'config':{'layout':{'table':[0,0,1,1],'dealer':[.1,.1,.8,.3],'player:0':[.1,.6,.8,.3]},
                   'rules':{'decks':4}}}
    doc={'schema':1,'layout_family':'freegames-classic','policy':replay.POLICY,
         'candidate_fingerprint':replay.candidate_fingerprint(),'sessions':[row]}
    path=tmp_path/'manifest.json';path.write_text(json.dumps(doc))
    return path,doc


def save(path,doc):path.write_text(json.dumps(doc))


def test_missing_provider_data_is_not_a_benchmark_result(tmp_path):
    path,doc=manifest(tmp_path);doc['sessions']=[];save(path,doc)
    with pytest.raises(ValueError,match='No original provider recordings'):replay.validate_manifest(path)


def test_manifest_keeps_truth_separate_and_blocks_hidden_oracles(tmp_path):
    path,doc=manifest(tmp_path)
    _,prepared=replay.validate_manifest(path)
    assert isinstance(prepared[0][0],replay.ReplayInput)
    assert not hasattr(prepared[0][0],'intervals')
    doc['sessions'][0]['config']['phase']='player';save(path,doc)
    with pytest.raises(ValueError,match='turn/phase/round IDs'):replay.validate_manifest(path)


@pytest.mark.parametrize('mutation,message',[
    ('duplicate_run','recording run'),('duplicate_hash','Duplicate video'),
    ('changed_bytes','hash mismatch'),('changed_code','code changed'),
    ('holdout','holdouts'),('no_permission','authorization')])
def test_replay_cannot_silently_change_or_reuse_evidence(tmp_path,mutation,message):
    path,doc=manifest(tmp_path)
    row=doc['sessions'][0]
    if mutation.startswith('duplicate'):
        other=copy.deepcopy(row);other['session_id']='unit-2';other['partition']='verification'
        if mutation=='duplicate_hash':other['capture_run_id']='unit-run-2'
        doc['sessions'].append(other)
    elif mutation=='changed_bytes':(tmp_path/row['video']).write_bytes(b'Changed')
    elif mutation=='changed_code':doc['candidate_fingerprint']='wrong'
    elif mutation=='holdout':row['partition']='final-holdout'
    else:row['authorization']['local_analysis']=False
    save(path,doc)
    with pytest.raises(ValueError,match=message):replay.validate_manifest(path)


def test_truth_cannot_drop_hard_intervals_or_compensate_inventory(tmp_path):
    data=truth();data['intervals'][0]['start_s']=1
    with pytest.raises(ValueError,match='complete timeline'):replay.validate_annotations(data)
    data=truth();data['intervals'][0]['observed_rank_inventory']={'5':1,'3':1,'6':1}
    with pytest.raises(ValueError,match='checkpoint disagrees'):replay.validate_annotations(data)
    data=truth();data['intervals'][0]['boundary']='ambiguous'
    with pytest.raises(ValueError,match='annotated as complete'):replay.validate_annotations(data)


def reports(*,wrong_inventory=False,extra_event=False):
    inventory={'2':1,'3':1,'6':1} if not wrong_inventory else {'5':1,'3':1,'6':1}
    for i in range(20):
        pts=i*.2;events=[]
        if i==4:
            events=[{'kind':'CARD_CONFIRMED','payload':{'card_id':str(n),'rank':r,'zone':z}}
                for n,(r,z) in enumerate([('2','player:0'),('3','player:0'),('6','dealer')])]
            if extra_event:events.append({'kind':'CARD_CONFIRMED','payload':{'card_id':'duplicate','rank':'2','zone':'player:0'}})
        yield pts,{'count_reliable':False,'events':events,'player':['2','3'],'dealer':['6'],
             'advice':{'basic_action':'stand'} if i>=4 else None,
             'state':{'known_rank_counts':inventory if i>=4 else {}}},10


def test_full_timeline_scoring_retains_per_rank_errors_and_extra_events(tmp_path,monkeypatch):
    monkeypatch.setattr(replay,'observe_video',lambda _:reports(wrong_inventory=True,extra_event=True))
    config=replay.ReplayInput('unit',tmp_path/'unused',(100,80),{},{})
    result=replay.measure_session(config,truth(),tmp_path/'trace.jsonl')
    assert result['timely_correct_decisions']==1 and result['first_correct_advice_delay_ms']['p50']==810
    assert result['inventory_max_l1']==2  # Same Hi-Lo RC, different inventory.
    assert result['exposures']['missed_or_late']==0 and result['exposures']['unmatched_emitted']==1
    assert result['capture_to_display_ms'] is None
    assert result['manual_interventions']==0


def test_short_unsampled_decision_stays_in_the_denominator(tmp_path,monkeypatch):
    data=truth();short=copy.deepcopy(data['intervals'][0]);short['end_s']=.1
    rest=copy.deepcopy(short);rest.update(start_s=.1,end_s=4,expected_action=None,turn='settled')
    data['intervals']=[short,rest]
    monkeypatch.setattr(replay,'observe_video',lambda _:reports())
    config=replay.ReplayInput('unit',tmp_path/'unused',(100,80),{},{})
    result=replay.measure_session(config,data,tmp_path/'trace.jsonl')
    assert result['decision_opportunities']==1 and result['timely_correct_decisions']==0
    assert result['false_advice_frames']==16  # Stale advice is not a useful result.


@pytest.mark.parametrize('busy_ms',[0,450])
def test_decoder_uses_actual_frames_native_crop_and_no_manual_turn(tmp_path,monkeypatch,busy_ms):
    import cv2
    import numpy as np
    video=tmp_path/'decoder-unit.avi'
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),5,(100,80))
    assert writer.isOpened()
    for i in range(6):writer.write(np.full((80,100,3),30+i*20,np.uint8))
    writer.release()
    calls=[]
    class SpyObserver:
        def __init__(self,_,**kwargs):
            assert kwargs['manual_turn'] is False and kwargs['fresh_shoe'] is False
            assert kwargs['layout']['table']==[0,0,1,1]
        def process(self,image,sequence,timestamp):
            assert image.size==(80,64)
            calls.append((sequence,timestamp,int(np.asarray(image).mean())))
            return {'unit':'decoder plumbing only'}
        def stop(self):pass
    monkeypatch.setattr('bjlab.live.LiveObserver',SpyObserver)
    from types import SimpleNamespace
    from itertools import count
    clock=count(step=busy_ms/1000)
    monkeypatch.setattr(replay,'time',SimpleNamespace(perf_counter=lambda:next(clock)))
    config=replay.ReplayInput('unit',video,(100,80),
        {'table':[.1,.1,.8,.8],'dealer':[.2,.2,.5,.2],'player:0':[.2,.5,.5,.3]}, {'decks':4},sample_interval_ms=200)
    rows=list(replay.observe_video(config))
    expected=6 if not busy_ms else 2
    assert len(rows)==expected and len({c[2] for c in calls})==expected
    assert [c[0] for c in calls]==list(range(expected))
    assert [c[1] for c in calls]==pytest.approx([1+i*(.2 if not busy_ms else .6) for i in range(expected)])


def test_development_or_no_decisions_never_promotes():
    assert not replay.acceptance([])
    assert not replay.acceptance([{'partition':'development'}])


def test_replay_refuses_pixels_beyond_the_actual_live_transport_cap(tmp_path):
    config=replay.ReplayInput('unit',tmp_path/'unused',(6000,1000),
        {'table':[0,0,1,1],'dealer':[.1,.1,.8,.3],'player:0':[.1,.6,.8,.3]}, {'decks':4})
    with pytest.raises(ValueError,match='five-megapixel transport cap'):list(replay.observe_video(config))


def test_correct_capture_becomes_stale_when_processing_finishes_after_a_turn(tmp_path,monkeypatch):
    data=truth();short=copy.deepcopy(data['intervals'][0]);short['end_s']=.1
    rest=copy.deepcopy(short);rest.update(start_s=.1,end_s=4,expected_action=None,turn='settled')
    data['intervals']=[short,rest]
    def delayed(_):
        pts,report,_=next(iter(reports()))
        report['advice']={'basic_action':'stand'}
        yield .05,report,150  # Valid at capture, obsolete at local completion.
        report=copy.deepcopy(report);report['advice']=None
        yield 3.8,report,10
    monkeypatch.setattr(replay,'observe_video',delayed)
    config=replay.ReplayInput('unit',tmp_path/'unused',(100,80),{},{})
    result=replay.measure_session(config,data,tmp_path/'trace.jsonl')
    assert result['timely_correct_decisions']==0 and result['false_advice_frames']==1
