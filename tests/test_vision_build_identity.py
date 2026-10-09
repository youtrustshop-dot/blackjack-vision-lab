import hashlib
import json

from bjlab.vision_diagnostics import source_revision


def test_frozen_compiled_modules_have_the_same_identity_as_source(tmp_path):
    names=('bjlab/external_vision.py','bjlab/corner_vision.py','bjlab/live.py','bjlab/vision.py')
    hashes={}
    for name in names:
        path=tmp_path/name;path.parent.mkdir(exist_ok=True)
        path.write_bytes(name.encode())
        hashes[name]=hashlib.sha256(path.read_bytes()).hexdigest()
    original=source_revision(tmp_path)
    for name in names:(tmp_path/name).unlink()
    assert source_revision(tmp_path)=='unavailable'
    (tmp_path/'assets').mkdir()
    manifest=tmp_path/'assets/build-provenance.json'
    manifest.write_text(json.dumps({'source_sha256':hashes}),encoding='utf-8')
    assert source_revision(tmp_path)==original
    hashes[names[0]]='f'*64
    manifest.write_text(json.dumps({'source_sha256':hashes}),encoding='utf-8')
    assert source_revision(tmp_path)!=original
