from fastapi.testclient import TestClient
from bjlab.api import app
from bjlab import model_api


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
