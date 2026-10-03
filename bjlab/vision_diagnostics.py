"""User-requested local pixel evidence bundles. No automatic external uploads."""
from dataclasses import asdict
from datetime import datetime,timezone
from io import BytesIO
import hashlib
import json
from pathlib import Path
import platform
import zipfile

from PIL import Image


def diagnostic_bundle(observer,received,original_bytes,capture_geometry=None):
    """Call under the observer lock after its exact requested frame is processed."""
    out=BytesIO()
    images={'received.png':received}
    if observer.corners:
        from .calibration import normalize_table
        calibration=normalize_table(received,observer.corners,(960,observer.output_height),corners_normalized=True)
        images['normalized.png']=Image.fromarray(calibration.image_rgb)
        transform=calibration.to_dict()
    else:
        transform={'kind':'native pixels, no perspective resampling','source_size':list(received.size)}
    detector=observer.detector
    for name,pixels in getattr(detector,'debug_images',{}).items():
        if pixels.size:images['crops/'+name+'.png']=Image.fromarray(pixels)
    report=observer.last_report or {}
    record={'schema':1,'created_utc':datetime.now(timezone.utc).isoformat(),
        'privacy':'private local capture; do not publish without explicit approval',
        'received_sha256':hashlib.sha256(original_bytes).hexdigest(),'received_size':list(received.size),
        'source_id':observer.source_id,'sequence':observer.sequence,'evidence_timestamp':report.get('timestamp'),
        'capture_geometry':capture_geometry,'transformation':transform,
        'configuration':{'rules':asdict(observer.rules),'corners':observer.corners,'zones':observer.zones,
            'layout':getattr(observer,'layout',None),'manual_turn':observer.manual_turn},
        'detector':getattr(detector,'last_diagnostics',{}),'observation':report,
        'event_log':observer.tracker.log.to_dict(),
        'runtime':{'python':platform.python_version(),'platform':platform.platform(),'source_fingerprint':source_revision(Path(__file__).resolve().parents[1])}}
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as archive:
        # original upload bytes allow exact replay, even if source encoding is JPEG.
        archive.writestr('received-upload.bin',original_bytes)
        for name,image in images.items():
            pixels=BytesIO();image.save(pixels,format='PNG');archive.writestr(name,pixels.getvalue())
        archive.writestr('diagnostic.json',json.dumps(record,indent=2,allow_nan=False))
    return out.getvalue()


def source_revision(root):
    """A content fingerprint works for frozen apps without requiring git."""
    root=Path(root)
    sources={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
        ('bjlab/external_vision.py','bjlab/corner_vision.py','bjlab/live.py','bjlab/vision.py') if (root/name).is_file()}
    return hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()


def candidate_revision(root):
    root=Path(root)
    provenance=root/'assets/build-provenance.json'
    if provenance.is_file():
        data=json.loads(provenance.read_text(encoding='utf-8-sig'))
        return {'commit':data.get('git_commit'),'working_tree_dirty':data.get('working_tree_dirty')}
    try:
        import subprocess
        commit=subprocess.run(['git','rev-parse','HEAD'],cwd=root,capture_output=True,text=True,timeout=2,check=True).stdout.strip()
        dirty=bool(subprocess.run(['git','status','--porcelain'],cwd=root,capture_output=True,text=True,timeout=2,check=True).stdout)
        return {'commit':commit,'working_tree_dirty':dirty}
    except (OSError,subprocess.SubprocessError):
        return {'commit':None,'working_tree_dirty':None}
