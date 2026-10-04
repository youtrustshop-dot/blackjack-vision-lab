from validation.tools.overlap_session import anchors


def object_(x,rank,identity):
    return {'bbox':[x,100,112,156],'zone':'dealer','rank':rank,'card_id':identity}


def test_anchor_assignment_is_one_to_one_and_not_rank_based():
    a=object_(100,'4','up'); a['bbox'][2]=39
    b=object_(139,'4','hole')
    # Wrong rank must not change association or hide the rank error.
    detections=[object_(102,'K','track1'),object_(141,'4','track2')]
    pairs,missing,extra=anchors([a,b],detections)
    assert not missing and not extra
    assert [(c['card_id'],d['card_id']) for c,d in pairs]==[('up','track1'),('hole','track2')]


def test_missing_back_cannot_be_matched_to_wide_upcard_box():
    a=object_(100,'4','up'); a['bbox'][2]=39
    b=object_(139,None,'hole')
    pairs,missing,extra=anchors([a,b],[object_(102,'4','track1')])
    assert len(pairs)==1 and missing==[b] and not extra


def test_empty_and_extra_scenes_remain_in_denominator():
    d=object_(100,'4','track1')
    assert anchors([],[d])==([],[],[d])
    assert anchors([d],[])==([],[d],[])
