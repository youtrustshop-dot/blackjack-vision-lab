"""Do not destroy earlier evidence when comparing two readers on one video."""
import json

import pytest

from validation.tools.stress_lab import run


def test_ambiguous_output_name_and_consumed_result_are_rejected_before_evaluation(tmp_path):
    absent = tmp_path/'manifest.json'
    with pytest.raises(ValueError, match='results.json'): run(absent, tmp_path/'v2')
    result = tmp_path/'results.json'; result.write_text('frozen earlier result')
    with pytest.raises(FileExistsError, match='consumed'): run(absent, result)
    assert result.read_text() == 'frozen earlier result'


def test_existing_trace_is_preserved_even_with_a_different_new_result_filename(tmp_path):
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps({'kind':'own-synthetic-continuous-video',
        'partition':'development','sessions':[{'profile':'clean'}]}))
    trace = tmp_path/'clean.trace.json'; trace.write_text('frozen earlier trace')
    with pytest.raises(FileExistsError, match='previous traces'):
        run(manifest, tmp_path/'new-results.json', profiles=['clean'])
    assert trace.read_text() == 'frozen earlier trace' and not (tmp_path/'new-results.json').exists()
