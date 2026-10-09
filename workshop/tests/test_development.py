from copy import deepcopy
from unittest.mock import MagicMock

import pytest
import requests
from fastapi.testclient import TestClient

import main
from config import mode, vast_settings
from fixtures import FixtureClient, SOURCE, VIDEO
from vss_client import VSSClient, VSSAPIError, VSSAuthError, prefer_incident_hit
from test_vss_client import FakeResponse


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "MODE", "fixture")
    monkeypatch.setattr(main, "vss", FixtureClient())
    return TestClient(main.app)


def test_deterministic_and_provenance(client):
    first = client.get('/api/review?include_agent=true')
    assert first.status_code == 200
    assert first.json() == client.get('/api/review?include_agent=true').json()
    data = first.json()
    assert data['synthetic'] and data['ui']['video_url'] is None
    for row in data['claim_reviews']:
        assert row['synthetic']
        assert row['evidence']['segment']['source'] == SOURCE
        assert row['evidence']['segment']['provenance']['reasoning_source'] == 'SYNTHETIC FIXTURE'
        assert 'SYNTHETIC' in row['evidence']['detections_summary']['provenance']
        assert 'SYNTHETIC' in row['evidence']['agent_answer_advisory']
        assert not row['verdict']['provenance']['cosmos_reasoning_used']
        assert not row['verdict']['provenance']['independent_corroboration']
        assert row['verdict']['human_review_required']
        assert row['verdict']['uncertainty']
        assert 0 <= row['seek_sec'] < 5
        assert row['seek_absolute_sec'] == 25 + row['seek_sec']
    assert client.get('/api/media/stream').status_code == 404
    assert client.get('/api/claims/unknown').status_code == 404


@pytest.mark.parametrize('field,value', [('synthetic', False), ('source', 's3://other'),
    ('segment_start_sec', None), ('segment_start_sec', -1), ('segment_end_sec', 25),
    ('segment_end_sec', float('nan')), ('segment_end_sec', float('inf')),
    ('segment_start_sec', True), ('segment_end_sec', 31)])
def test_bad_anchor_rejected(client, monkeypatch, field, value):
    row = FixtureClient().segment_metadata(SOURCE)
    row[field] = value
    monkeypatch.setattr(main.vss, 'segment_metadata', lambda source: row)
    assert client.get('/api/review').status_code == 502


def test_wrong_search_does_not_supply_evidence(client, monkeypatch):
    monkeypatch.setattr(main.vss, 'search', lambda *a, **k: {
        'synthetic': True, 'results': [{'source': 'fixture://other', 'reasoning_content': 'no cars'}]})
    data = client.get('/api/review').json()
    assert all(r['evidence']['segment']['source'] == SOURCE for r in data['claim_reviews'])
    assert all(not r['evidence']['search']['hit']['found'] for r in data['claim_reviews'])
    assert prefer_incident_hit([{'filename': ''}], SOURCE) is None


@pytest.mark.parametrize('method', ['search', 'segment_detections', 'agent_ask_scoped'])
def test_mixed_provenance_rejected(client, monkeypatch, method):
    monkeypatch.setattr(main.vss, method, lambda *a, **k: {'synthetic': False})
    assert client.get('/api/review?include_agent=true').status_code == 502


def test_optional_failures_visible(client, monkeypatch):
    def fail(*args, **kwargs):
        raise VSSAuthError('authentication unavailable')
    monkeypatch.setattr(main.vss, 'segment_detections', fail)
    monkeypatch.setattr(main.vss, 'agent_ask_scoped', fail)
    data = client.get('/api/review?include_agent=true').json()
    assert data['anchor']['detections']['available'] is False
    assert data['anchor']['detections']['error']
    assert data['claim_reviews'][0]['evidence']['agent_error']


def test_fixture_scope():
    with pytest.raises(VSSAPIError):
        FixtureClient().agent_ask_scoped('q', 's3://other')
    with pytest.raises(VSSAPIError):
        FixtureClient().segment_detections('s3://other')


def transport(payload=None, status=200):
    session = MagicMock()
    session.post.return_value = FakeResponse(200, {'access_token': 'secret-token'})
    session.request.return_value = FakeResponse(status, payload)
    return VSSClient('https://vss.example', 'u', 'p', session=session), session


@pytest.mark.parametrize('method,args,path,payload', [
    ('search', ('q',), '/search', {'results': []}),
    ('segment_metadata', ('s3://source',), '/videos/metadata', {'source': 's3://source'}),
    ('segment_detections', ('s3://source',), '/videos/detections', {'frames': []}),
    ('agent_ask_scoped', ('q', 's3://parent'), '/agent/ask', {'answer': 'advisory'}),
    ('open_stream', ('s3://source', 'bytes=0-5'), '/videos/stream', {}),
])
def test_all_interactions(method, args, path, payload):
    adapter, session = transport(payload)
    getattr(adapter, method)(*args)
    call = session.request.call_args
    assert call.args[1] == 'https://vss.example/api/v1' + path
    assert call.kwargs['allow_redirects'] is False
    assert call.kwargs['timeout'] == 60
    if method == 'open_stream':
        assert call.kwargs['headers'] == {'Range': 'bytes=0-5'}
        assert call.kwargs['params']['token'] == 'secret-token'
    else:
        assert call.kwargs['headers']['Authorization'] == 'Bearer secret-token'
    if method == 'agent_ask_scoped':
        assert call.kwargs['json']['original_video'] == 's3://parent'
    if method == 'search':
        assert call.kwargs['json']['query'] == 'q'


@pytest.mark.parametrize('method,args', [('search', ('q',)), ('segment_metadata', ('s',)),
    ('segment_detections', ('s',)), ('agent_ask_scoped', ('q', 'v')), ('open_stream', ('s',))])
@pytest.mark.parametrize('failure', [401, 403, 500, 302, 'network', 'bad_json'])
def test_errors_all_interactions(method, args, failure):
    adapter, session = transport({'results': []})
    if failure == 'bad_json' and method == 'open_stream':
        return  # Stream is bytes, not JSON.
    if failure == 'network':
        session.request.side_effect = requests.Timeout('https://private.invalid/?token=SECRET')
    else:
        session.request.return_value = FakeResponse(failure if isinstance(failure, int) else 200)
    with pytest.raises(VSSAPIError) as exc:
        getattr(adapter, method)(*args)
    assert 'SECRET' not in str(exc.value)
    assert 'private.invalid' not in str(exc.value)
    assert session.request.call_count == (2 if failure == 401 else 1)


def test_refresh_and_missing_detections():
    adapter, session = transport()
    old = FakeResponse(401)
    session.request.side_effect = [old, FakeResponse(200, {'results': []})]
    assert adapter.search('q') == {'results': []}
    assert session.post.call_count == 2 and old.closed
    session.request.side_effect = None
    session.request.return_value = FakeResponse(404)
    assert adapter.segment_detections('s') is None
    with pytest.raises(VSSAPIError):
        adapter.segment_metadata('s')


@pytest.mark.parametrize('payload', [None, [], {}, {'access_token': 123}])
def test_malformed_login(payload):
    adapter, session = transport()
    session.post.return_value = FakeResponse(200, payload)
    with pytest.raises(VSSAuthError):
        adapter.login()


def test_environment(monkeypatch):
    monkeypatch.delenv('WITNESS_WORKSHOP_MODE', raising=False)
    assert mode() == 'fixture'
    monkeypatch.setenv('WITNESS_WORKSHOP_MODE', 'typo')
    with pytest.raises(ValueError):
        mode()
    monkeypatch.setenv('VSS_URL', 'https://vss.example')
    monkeypatch.setenv('VSS_USERNAME', 'u')
    monkeypatch.setenv('VSS_PASSWORD', 'p')
    assert vast_settings()[:3] == ('https://vss.example', 'u', 'p')
    assert not VSSClient('', '', '').configured()
    for bad in ['nan', '0', '301']:
        monkeypatch.setenv('VSS_TIMEOUT_SECONDS', bad)
        with pytest.raises(ValueError):
            vast_settings()


@pytest.mark.parametrize('path', ['/app', '/app/', '/app/app.js', '/app/styles.css', '/app/health', '/app/api/review'])
def test_ingress_paths(client, path):
    assert client.get(path).status_code == 200


@pytest.mark.parametrize('method,args,payload', [
    ('search', ('q',), {'results': [None]}),
    ('search', ('q',), {'results': [], 'llm_synthesis': []}),
    ('segment_metadata', ('s',), {'reasoning_content': 3}),
    ('segment_detections', ('s',), {'frames': [None]}),
    ('segment_detections', ('s',), {'frames': [{'detections': [None]}]}),
    ('agent_ask_scoped', ('q', 'v'), {'answer': []}),
])
def test_malformed_shapes(method, args, payload):
    adapter, session = transport(payload)
    with pytest.raises(VSSAPIError):
        getattr(adapter, method)(*args)


def test_stream_refresh_failure_is_sanitized():
    adapter, session = transport()
    session.request.side_effect = [FakeResponse(401), requests.Timeout('token=SECRET')]
    with pytest.raises(VSSAPIError, match='VSS request failed'):
        adapter.open_stream('s')
    assert session.request.call_count == 2


def test_expired_token_refresh():
    adapter, session = transport({'results': []})
    adapter.login()
    adapter._token_obtained_at = 0
    adapter.search('q')
    assert session.post.call_count == 2


def test_nonfinite_payload_rejected():
    adapter, session = transport({'results': [], 'total': float('nan')})
    with pytest.raises(VSSAPIError):
        adapter.search('q')
