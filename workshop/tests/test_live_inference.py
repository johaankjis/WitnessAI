"""Offline live-GPU contract tests: no real GPU, VSS or credentials used."""
import asyncio
from copy import deepcopy
import json
import time
from unittest.mock import MagicMock

import httpx
import pytest
import requests
from fastapi.testclient import TestClient

import live_inference as live
import main
from incident import INCIDENT
from test_api import _anchor_meta

VIDEO = b'\x00\x00\x00\x18ftypmp42' + b'test-video'
COSMOS = {'choices': [{'message': {'content': 'Fresh scene description.'}}]}
YOLO = {'perception_ok': True, 'object_classes': ['car', 'person'], 'object_counts': {'car': 2, 'person': 1}}


@pytest.fixture
def settings(monkeypatch, tmp_path):
    monkeypatch.setenv('COSMOS_GPU_URL', 'https://cosmos.invalid')
    monkeypatch.setenv('YOLO_GPU_URL', 'https://yolo.invalid')
    monkeypatch.setenv('GPU_BEARER_TOKEN', 'test-private-token')
    monkeypatch.setenv('WITNESS_LIVE_INFERENCE_ENABLED', 'true')
    monkeypatch.setattr(live, 'PREFLIGHT_FILE', tmp_path / 'receipt.json')
    value = live.GPUSettings.from_env()
    live.PREFLIGHT_FILE.write_text(json.dumps({'verified_at': time.time(), 'fingerprint': value.fingerprint(INCIDENT['source'])}))
    return value


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(live.httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))


@pytest.fixture
def client(monkeypatch, settings):
    monkeypatch.setattr(main, 'MODE', 'vast')
    monkeypatch.setattr(main, 'INCIDENT', deepcopy(INCIDENT))
    monkeypatch.setattr(main, 'live_limit', live.RequestLimit())
    upstream = MagicMock(status_code=200, headers={'Content-Type': 'video/mp4', 'Content-Length': str(len(VIDEO))})
    upstream.iter_content.return_value = [VIDEO]
    vss = MagicMock()
    vss.segment_metadata.return_value = _anchor_meta()
    vss.open_stream.return_value = upstream
    monkeypatch.setattr(main, 'vss', vss)
    return TestClient(main.app)


def test_success_uses_authorized_video_and_preserves_evidence(client, monkeypatch):
    before = deepcopy(main.INCIDENT)
    main.vss.segment_detections.return_value = {
        'source': 'yolo11_coco', 'segment_source': INCIDENT['source'], 'detection_count': 100, 'frames': []}
    main.vss.search.return_value = {'results': [_anchor_meta()]}
    review_before = client.get('/app/api/review')
    assert review_before.status_code == 200
    seen = []
    def handler(request):
        seen.append(request)
        assert request.headers['authorization'] == 'Bearer test-private-token'
        body = json.loads(request.content)
        if request.url.path == '/v1/chat/completions':
            assert body['model'] == live.COSMOS_MODEL
            content = body['messages'][0]['content']
            assert content[0]['type'] == 'text'
            assert content[1]['video_url']['url'] == 'data:video/mp4;base64,' + live.base64.b64encode(VIDEO).decode()
            return httpx.Response(200, json=COSMOS)
        assert request.url.path == '/v1/infer'
        assert body == {'video_base64': live.base64.b64encode(VIDEO).decode(),
                        'filename': INCIDENT['segment_filename'], 'include_frames': False}
        return httpx.Response(200, json=YOLO)
    transport(monkeypatch, handler)
    response = client.post('/app/api/live-analysis', json={'incident_id': INCIDENT['id']})
    assert response.status_code == 200
    result = response.json()
    assert result['status'] == 'ok' and result['live_inference'] is True
    assert result['cosmos']['description'] == 'Fresh scene description.'
    assert result['yolo']['object_counts'] == YOLO['object_counts']
    assert result['verdicts_changed'] is False and 'verdict' not in result
    assert result['human_review_required'] is True
    assert result['evidence_window_sec'] == INCIDENT['evidence_window_sec']
    assert main.INCIDENT == before
    assert client.get('/app/api/review').json() == review_before.json()
    assert response.headers['cache-control'] == 'no-store'
    assert 'test-private-token' not in response.text
    assert len(seen) == 2
    main.vss.open_stream.assert_called_once_with(INCIDENT['source'])
    main.vss.open_stream.return_value.close.assert_called_once()
    assert client.post('/api/live-analysis', json={'incident_id': INCIDENT['id']}).status_code == 429


@pytest.mark.parametrize('failure', ['timeout', 'deadline', 'auth', 'forbidden', 'server', 'redirect', 'invalid', 'oversize', 'perception', 'connection'])
def test_partial_failure(client, monkeypatch, failure):
    async def handler(request):
        if request.url.path.endswith('completions'):
            return httpx.Response(200, json=COSMOS)
        if failure == 'connection':
            raise httpx.ConnectError('private endpoint')
        if failure == 'timeout':
            raise httpx.ReadTimeout('must never expose private URL or token')
        if failure == 'deadline':
            await asyncio.sleep(.05)
        if failure in {'auth', 'forbidden', 'server', 'redirect'}:
            return httpx.Response({'auth': 401, 'forbidden': 403, 'server': 500, 'redirect': 302}[failure],
                                  text='private upstream body')
        if failure == 'oversize':
            return httpx.Response(200, content=b'x' * (live.MAX_RESPONSE_BYTES + 1))
        if failure == 'perception':
            return httpx.Response(200, json=YOLO | {'perception_ok': False})
        return httpx.Response(200, json={'invalid': True})
    if failure == 'deadline':
        monkeypatch.setattr(live, 'GPU_TIMEOUT_SECONDS', .01)
    transport(monkeypatch, handler)
    response = client.post('/api/live-analysis', json={'incident_id': INCIDENT['id']})
    result = response.json()
    assert response.status_code == 200
    assert result['status'] == 'partial' and result['live_inference'] is True
    assert result['cosmos']['status'] == 'ok'
    assert result['yolo']['status'] == 'error' and result['yolo']['live_inference'] is False
    assert 'object_counts' not in result['yolo']
    assert 'error' in result['yolo']
    assert 'private' not in response.text


def test_both_fail(client, monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(401))
    result = client.post('/api/live-analysis', json={'incident_id': INCIDENT['id']}).json()
    assert result['status'] == 'error' and result['live_inference'] is False
    assert result['attempted_live_inference'] is True


@pytest.mark.parametrize('failure,status', [('fixture', 409), ('source', 403), ('permission', 403),
    ('disabled', 503), ('receipt', 503), ('expired', 503), ('changed_token', 503), ('metadata', 502),
    ('vss_auth', 502), ('vss_timeout', 502), ('cross_site', 403), ('extra', 422), ('large', 413)])
def test_fail_closed_before_inference(client, monkeypatch, failure, status):
    body = {'incident_id': INCIDENT['id']}
    headers = {}
    if failure == 'fixture': monkeypatch.setattr(main, 'MODE', 'fixture')
    if failure == 'source': body['incident_id'] = 'other-incident'
    if failure == 'permission': main.INCIDENT['footage_permitted'] = False
    if failure == 'disabled': monkeypatch.delenv('WITNESS_LIVE_INFERENCE_ENABLED')
    if failure == 'receipt': live.PREFLIGHT_FILE.unlink()
    if failure == 'expired':
        receipt = json.loads(live.PREFLIGHT_FILE.read_text())
        receipt['verified_at'] -= 3601
        live.PREFLIGHT_FILE.write_text(json.dumps(receipt))
    if failure == 'changed_token': monkeypatch.setenv('GPU_BEARER_TOKEN', 'different-token')
    if failure == 'metadata': main.vss.segment_metadata.return_value['source'] = 'other-source'
    if failure == 'vss_auth': main.vss.segment_metadata.side_effect = main.VSSAuthError('secret')
    if failure == 'vss_timeout': main.vss.open_stream.return_value.iter_content.side_effect = requests.Timeout('secret')
    if failure == 'cross_site': headers['Sec-Fetch-Site'] = 'cross-site'
    if failure == 'extra': body['source'] = 'https://untrusted.invalid'
    if failure == 'large': body['incident_id'] = 'x' * 1025
    response = client.post('/api/live-analysis', json=body, headers=headers)
    assert response.status_code == status, response.text
    assert 'secret' not in response.text


@pytest.mark.parametrize('failure', ['size_header', 'size_stream', 'empty', 'partial', 'mime', 'length', 'mp4', 'timeout'])
def test_video_bounds(settings, failure, monkeypatch):
    upstream = MagicMock(status_code=200, headers={'Content-Type': 'video/mp4'})
    upstream.iter_content.return_value = [VIDEO]
    if failure == 'size_header': upstream.headers['Content-Length'] = str(live.MAX_VIDEO_BYTES + 1)
    if failure == 'size_stream': monkeypatch.setattr(live, 'MAX_VIDEO_BYTES', 10)
    if failure == 'empty': upstream.iter_content.return_value = []
    if failure == 'partial': upstream.status_code = 206
    if failure == 'mime': upstream.headers['Content-Type'] = 'text/html'
    if failure == 'length': upstream.headers['Content-Length'] = '1000'
    if failure == 'mp4': upstream.iter_content.return_value = [b'not an mp4 body']
    if failure == 'timeout': upstream.iter_content.side_effect = requests.Timeout('private')
    vss = MagicMock()
    vss.open_stream.return_value = upstream
    with pytest.raises(live.LiveError): live.read_video(vss, INCIDENT['source'])
    upstream.close.assert_called_once()


def test_concurrency_and_hour_limit():
    limit = live.RequestLimit()
    with limit.reserve():
        with pytest.raises(live.LiveError, match='busy'):
            with limit.reserve(): pass
    limit.starts.clear()
    limit.starts.extend([time.monotonic() - 100] * 20)
    with pytest.raises(live.LiveError, match='limit'):
        with limit.reserve(): pass


def test_preflight_refuses_mac(monkeypatch):
    import live_preflight
    monkeypatch.setattr(live_preflight.sys, 'platform', 'darwin')
    assert live_preflight.main() == 1


@pytest.mark.parametrize('success', [True, False])
def test_preflight_issues_gate_only_after_both_services_pass(client, monkeypatch, success):
    import live_preflight
    monkeypatch.setattr(live_preflight.sys, 'platform', 'linux')
    monkeypatch.setenv('KUBERNETES_SERVICE_HOST', 'test-pod')
    monkeypatch.setattr(live_preflight, 'PREFLIGHT_FILE', live.PREFLIGHT_FILE)
    # Existing successful receipt must be invalidated on a failed recheck.
    transport(monkeypatch, lambda request: httpx.Response(200, json=(COSMOS if request.url.path.endswith('completions') else YOLO))
              if success else httpx.Response(401))
    assert live_preflight.main() == (0 if success else 1)
    assert live.PREFLIGHT_FILE.exists() is success


@pytest.mark.parametrize('env,value', [('COSMOS_GPU_URL', 'https://user:password@host'),
    ('YOLO_GPU_URL', 'https://host?token=private'), ('COSMOS_GPU_URL', 'https://[broken'),
    ('YOLO_GPU_URL', 'https://host:bad-port'), ('GPU_BEARER_TOKEN', ''), ('GPU_BEARER_TOKEN', 'bad\nheader')])
def test_invalid_settings_rejected(settings, monkeypatch, env, value):
    monkeypatch.setenv(env, value)
    with pytest.raises(live.LiveError): live.GPUSettings.from_env()


def test_cosmos_failure_preserves_yolo(client, monkeypatch):
    transport(monkeypatch, lambda request: httpx.Response(200, json={'choices': []})
              if request.url.path.endswith('completions') else httpx.Response(200, json=YOLO))
    result = client.post('/api/live-analysis', json={'incident_id': INCIDENT['id']}).json()
    assert result['status'] == 'partial'
    assert result['cosmos']['status'] == 'error'
    assert 'description' not in result['cosmos']
    assert result['yolo']['object_counts'] == YOLO['object_counts']
    assert result['provenance']['live_inference'] is True
