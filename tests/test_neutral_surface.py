import json

import pytest
from PIL import Image, ImageDraw

from bjlab.corner_vision import CornerCardDetector
from bjlab.datasets import card_font
from bjlab.state_reader import LocalVisionReader, prepare_frame, analysis_gate
from validation.tools.surface_profile_comparison import evaluate


LAYOUT = {'table': (0, 0, 1, 1), 'dealer': (.05, .04, .9, .42), 'player:0': (.05, .52, .9, .44)}


def test_small_top_seam_cannot_replace_the_taller_rank():
    image = Image.new('RGB', (520, 500), '#075344')
    draw = ImageDraw.Draw(image)
    # A second rounded card edge within a merged row, next to a genuine rank.
    draw.rounded_rectangle((100, 280, 250, 460), radius=8, fill='white')
    draw.polygon(((168, 282), (173, 282), (168, 288)), fill='black')
    draw.text((171, 292), '2', fill='black', font=card_font(24), anchor='lt')
    detector = CornerCardDetector(LAYOUT, surface_profile='neutral')
    found = detector.detect(image)
    assert [d.rank for d in found] == ['2']
    assert detector.last_diagnostics['ignored_surface_border_artifacts']
    assert detector.context['phase'] == 'unknown'


def test_neutral_surface_keeps_an_unreadable_card_present():
    image = Image.new('RGB', (520, 500), '#075344')
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((100, 280, 225, 460), radius=8, fill='white')
    detector = CornerCardDetector(LAYOUT, surface_profile='neutral')
    found = detector.detect(image)
    assert len(found) == 1 and found[0].visibility == 'unreadable'
    assert found[0].rank is None
    assert detector.last_diagnostics['rejected_card_candidates'] > 0


def test_unknown_profile_cannot_fall_back_silently():
    for constructor, args in ((CornerCardDetector, (LAYOUT,)), (LocalVisionReader, ())):
        with pytest.raises(ValueError, match='surface profile'):
            constructor(*args, surface_profile='typo')
    assert LocalVisionReader().name != LocalVisionReader(surface_profile='neutral').name


def test_neutral_reader_still_blocks_a_real_crop_with_two_visible_cards():
    image = Image.new('RGB', (720, 500), '#243747')
    draw = ImageDraw.Draw(image)
    for x, y, rank in ((110, 45, '6'), (110, 285, '7'), (155, 285, '2'), (200, 285, 'A')):
        draw.rounded_rectangle((x, y, x+80, y+110), radius=6, fill='white')
        draw.text((x+6, y+6), rank, font=card_font(22), fill='black', anchor='lt')
    layout = {'table':(0,0,1,1), 'dealer':(.12,.06,.70,.29), 'player:0':(.12,.54,.20,.29)}
    result = LocalVisionReader(surface_profile='neutral').read(prepare_frame(image, layout))
    assert not analysis_gate(result.observation)['usable']
    assert any('region edge' in reason for reason in result.observation.blockers)


def test_still_probe_rejects_video_claims_final_test_and_changed_pixels(tmp_path):
    manifest = tmp_path/'manifest.json'
    base = {'evidence_kind':'sparse-browser-screenshots-not-continuous-video', 'cases': []}
    for document, message in ((base | {'evidence_kind':'original-video'}, 'sparse'),
                              (base | {'cases':[{'split':'final-test'}]}, 'Development'),
                              (base | {'cases':[{'id':'x','split':'development','source_file':str(manifest),
                                               'sha256':'wrong'}]}, 'pixels changed')):
        manifest.write_text(json.dumps(document))
        with pytest.raises(ValueError, match=message):
            evaluate(manifest, tmp_path/'output.json')
    assert not (tmp_path/'output.json').exists()
