"""Offline integration checks; media bytes below are transport fixtures, not footage."""
from pathlib import Path
from threading import Event
import time

import pytest
from fastapi.testclient import TestClient
from witness_contracts import IncidentReport, DetectorObservation
from witness_api.config import configured_pipeline
from witness_api.main import ROOT, create_app
from witness_api.storage import JsonStorage


def storage(tmp_path):
    return JsonStorage(ROOT / 'data/demo/incident.json', tmp_path / 'reports')


def test_full_mock_review(tmp_path):
    with TestClient(create_app(storage(tmp_path))) as client:
        assert client.get('/health').json()['analysis_mode'] == 'mock'
        assert client.get('/incidents/demo-001').status_code == 200
        assert client.get('/incidents/demo-001/status').status_code == 409
        assert client.get('/incidents/demo-001/results').status_code == 409
        assert client.post('/incidents/demo-001/analyze').json()['state'] == 'completed'
        assert client.get('/incidents/demo-001/status').json()['state'] == 'completed'
        first = client.get('/incidents/demo-001/results').json()
        report = IncidentReport.model_validate(first)
        assert report.human_review_required and report.is_mock
        assert len(report.claims) == 5
        assert report.observations
        for item in report.observations:
            assert DetectorObservation.model_validate_json(item.model_dump_json()) == item
            assert item.provenance.adapter == 'witness-vision-mock'
            assert item.provenance.is_mock
        assert {v.verdict.value for v in report.verdicts} == {'supported', 'contradicted', 'not_visible'}
        client.post('/incidents/demo-001/analyze')
        assert client.get('/incidents/demo-001/results').json() == first
        assert client.get('/incidents/demo-001/media').status_code == 404
        assert client.get('/incidents/unknown/status').status_code == 404


@pytest.mark.parametrize('failure', [False, True])
def test_async_status_deduplicates_and_never_commits_failure(tmp_path, monkeypatch, failure):
    monkeypatch.setenv('WITNESS_ANALYSIS_MODE', 'real')
    entered, release = Event(), Event()
    calls = []
    class Runner:
        def analyze(self, incident):
            calls.append(incident.id)
            entered.set()
            assert release.wait(5)
            if failure:
                raise ValueError('private diagnostic')
            return configured_pipeline('mock').analyze(incident)
    with TestClient(create_app(storage(tmp_path), Runner())) as client:
        try:
            assert client.post('/incidents/demo-001/analyze').json()['state'] == 'pending'
            assert entered.wait(2)
            assert client.get('/incidents/demo-001/status').json()['state'] == 'running'
            client.post('/incidents/demo-001/analyze')
            assert calls == ['demo-001']
        finally:
            release.set()
        for _ in range(200):
            status = client.get('/incidents/demo-001/status').json()
            if status['state'] in ('completed', 'failed'):
                break
            time.sleep(.005)
        assert status['state'] == ('failed' if failure else 'completed')
        assert 'private' not in status['detail']
        assert client.get('/incidents/demo-001/results').status_code == (409 if failure else 200)


def media_client(tmp_path, monkeypatch, uri):
    store = storage(tmp_path)
    incident = store.get_incident('demo-001').model_copy(update={'is_mock': False, 'video_uri': uri})
    fixture = tmp_path / 'incident.json'
    fixture.write_text(incident.model_dump_json())
    monkeypatch.setenv('WITNESS_MEDIA_ROOT', str(tmp_path / 'media'))
    return TestClient(create_app(JsonStorage(fixture, tmp_path / 'reports')))


def test_media_original_bytes_and_range(tmp_path, monkeypatch):
    root = tmp_path / 'media'
    root.mkdir()
    payload = b'transport fixture only; not decodable footage'
    (root / 'clip.mp4').write_bytes(payload)
    with media_client(tmp_path, monkeypatch, 'clip.mp4') as client:
        response = client.get('/incidents/demo-001/media')
        assert response.content == payload
        assert response.headers['content-type'] == 'video/mp4'
        response = client.get('/incidents/demo-001/media', headers={'Range': 'bytes=3-9'})
        assert response.status_code == 206 and response.content == payload[3:10]
        assert client.get('/incidents/demo-001/media', headers={'Range': 'bytes=999-'}).status_code == 416


@pytest.mark.parametrize('uri', ['../outside.mp4', '%2e%2e/outside.mp4', 'link.mp4',
                                  'https://example.org/a.mp4', 'file://host/a.mp4', 'missing.mp4', 'a.txt'])
def test_media_rejects_unapproved_paths(tmp_path, monkeypatch, uri):
    (tmp_path / 'media').mkdir()
    (tmp_path / 'outside.mp4').write_bytes(b'private')
    (tmp_path / 'media/link.mp4').symlink_to(tmp_path / 'outside.mp4')
    with media_client(tmp_path, monkeypatch, uri) as client:
        assert client.get('/incidents/demo-001/media').status_code == 404


def test_real_detector_receives_same_snapshot_as_cosmos(tmp_path, monkeypatch):
    import base64
    from witness_api.media import VideoAsset
    from witness_api.providers import SnapshotObserver
    from witness_api.mock import MockAdapters
    from witness_vision.adapter import VisionObserver
    incident = storage(tmp_path).get_incident('demo-001')
    claims = MockAdapters().extract(incident)
    observations = configured_pipeline('mock').analyze(incident).observations
    real = incident.model_copy(update={'is_mock': False, 'video_uri': 'original.mp4'})
    seen = []
    def observe(self, bound, claims):
        seen.append(Path(bound.video_uri))
        assert Path(bound.video_uri).read_bytes() == b'exact source snapshot'
        assert not bound.is_mock
        for item in observations:
            item.provenance.is_mock = False
            item.evidence.provenance.is_mock = False
            item.provenance.source = f'detector test; {bound.video_uri}'
            item.evidence.video_uri = bound.video_uri
        return observations
    monkeypatch.setattr(VisionObserver, 'observe', observe)
    asset = VideoAsset('original.mp4', 20, 'data:video/mp4;base64,' +
                       base64.b64encode(b'exact source snapshot').decode(), 'test-digest')
    result = SnapshotObserver(VisionObserver(), asset).observe(real, claims)
    assert not seen[0].exists()
    assert all(o.evidence.video_uri == 'original.mp4' for o in result)
    assert all('sha256=test-digest' in o.provenance.source for o in result)


def test_saved_mock_report_cannot_be_loaded_for_real_incident(tmp_path, monkeypatch):
    store = storage(tmp_path)
    store.save_report(configured_pipeline('mock').analyze(store.get_incident('demo-001')))
    with media_client(tmp_path, monkeypatch, 'clip.mp4') as client:
        assert client.get('/incidents/demo-001/results').status_code == 409
        assert client.get('/incidents/demo-001/status').status_code == 409
