from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab import model_api
import base64,io
from PIL import Image


def test_missing_optional_model_does_not_disable_the_lab(monkeypatch):
    def offline(*args):
        raise OSError('Offline fixture')
    monkeypatch.setattr(model_api, 'call', offline)
    with TestClient(app) as client:
        assert client.get('/api/models/clef/status').json()['status'] == 'offline'
        assert client.post('/api/models/clef/classify', json={'image_base64': 'AA=='}).status_code == 503
        assert client.get('/api/health').json()['status'] == 'ok'


def test_classifier_bridge_has_a_fixed_loopback_destination(monkeypatch):
    calls = []
    def ready(*args):
        calls.append(args)
        return {'status': 'ready', 'scope': 'Experimental classifier'}
    monkeypatch.setattr(model_api, 'call', ready)
    with TestClient(app) as client:
        assert client.get('/api/models/clef/status').json()['status'] == 'ready'
        assert client.post('/api/models/clef/classify', json={'image_base64': 'AA=='}).status_code == 200
        assert calls == [('/health',), ('/classify', {'image_base64': 'AA=='}, 60)]
        assert model_api.ENDPOINT == 'http://127.0.0.1:9051'


def test_visual_bridge_rejects_invalid_pixels_before_contacting_model(monkeypatch):
    def forbidden(*args):raise AssertionError('Invalid pixels reached the model')
    monkeypatch.setattr(model_api,'call',forbidden)
    with TestClient(app) as client:
        for payload in ('AA==','not base64'):
            assert client.post('/api/models/clef/verify',json={'image_base64':payload}).status_code==422


def test_visual_bridge_calibration_sends_only_normalized_pixels(monkeypatch):
    output=io.BytesIO();Image.new('RGB',(400,200),'red').save(output,format='PNG')
    calls=[]
    def ready(path,body,timeout):
        calls.append((path,body,timeout));return {'task':'table','answers':{}}
    monkeypatch.setattr(model_api,'call',ready)
    with TestClient(app) as client:
        response=client.post('/api/models/clef/verify',json={'image_base64':base64.b64encode(output.getvalue()).decode(),
           'corners':[[0,0],[1,0],[1,1],[0,1]],'output_height':600,'task':'table'})
        assert response.status_code==200
    path,body,timeout=calls[0]
    assert path=='/verify' and timeout==60 and set(body)=={'task','image_base64'}
    with Image.open(io.BytesIO(base64.b64decode(body['image_base64']))) as image:
        assert image.size==(960,600) and image.getpixel((500,300))==(255,0,0)
