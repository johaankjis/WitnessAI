"""API-level tests: auth failure surfaces, timestamp handling, mock separation."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

import main
from incident import INCIDENT
from vss_client import VSSAuthError, VSSAPIError


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(main, "MODE", "vast")
    monkeypatch.setattr(main, "INCIDENT", INCIDENT)
    return TestClient(main.app)


def _anchor_meta():
    return {
        "source": INCIDENT["source"],
        "original_video": INCIDENT["original_video"],
        "filename": INCIDENT["segment_filename"],
        "reasoning_content": (
            "The scene is a busy city intersection with a marked crosswalk and traffic lights. "
            "Pedestrians are crossing the street from right to left in front of the camera. "
            "A black car is stopped at the intersection, waiting for the pedestrians to clear. "
            "Another black car is visible in the background, moving through the intersection."
        ),
        "segment_start_sec": 25.0,
        "segment_end_sec": 30.0,
        "segment_number": 6,
        "duration": 5.0,
        "location": "toronto",
        "camera_id": "pie_cam-3",
        "capture_type": "streets",
        "object_classes": "car,person,traffic light,truck,bus",
        "object_counts": {"car": 6, "person": 11, "traffic light": 6},
        "detection_count": 100,
        "detection_sidecar_uri": INCIDENT["detection_sidecar_uri"],
    }


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["team"] == "team-6"
    assert body["wandb"]["active"] is False


def test_incident_illustrative(client):
    r = client.get("/api/incident")
    assert r.status_code == 200
    data = r.json()
    assert "ILLUSTRATIVE" in data["incident"]["disclaimer"].upper() or "illustrative" in data["incident"]["disclaimer"].lower()
    assert len(data["statements"]) == 2
    for s in data["statements"]:
        assert s["illustrative"] is True


def test_review_auth_failure(client):
    with patch.object(main.vss, "configured", return_value=True), patch.object(
        main.vss, "segment_metadata", side_effect=VSSAuthError("login rejected (401)")
    ):
        r = client.get("/api/review")
        assert r.status_code == 502
        assert "auth" in r.text.lower() or "VSS" in r.text


def test_review_api_error(client):
    with patch.object(main.vss, "configured", return_value=True), patch.object(
        main.vss, "segment_metadata", side_effect=VSSAPIError("metadata failed", 500, "x")
    ):
        r = client.get("/api/review")
        assert r.status_code == 502


def test_review_happy_path_and_timestamps(client):
    meta = _anchor_meta()

    def fake_search(query, **kwargs):
        return {
            "results": [meta | {"similarity_score": 0.4}],
            "total": 1,
            "llm_synthesis": {"response": "advisory only"},
        }

    with patch.object(main.vss, "configured", return_value=True), patch.object(
        main.vss, "segment_metadata", return_value=meta
    ), patch.object(
        main.vss, "segment_detections", return_value={
            "source": "yolo11_coco",
            "segment_source": INCIDENT["source"],
            "detection_count": 100,
            "object_classes": ["car", "person"],
            "object_counts": {"car": 2, "person": 3},
            "fps": 30,
            "frame_count": 150,
            "max_detection_conf": 0.9,
            "frames": [{"detections": [{"label": "car"}]}],
        }
    ), patch.object(main.vss, "search", side_effect=fake_search):
        r = client.get("/api/review")
        assert r.status_code == 200
        data = r.json()
        assert data["ui"]["binding_liability_conclusion"] is False
        assert data["ui"]["collision_claimed"] is False
        assert data["wandb"]["active"] is False

        by_id = {row["claim"]["id"]: row for row in data["claim_reviews"]}
        # a1/a2 should be supported from cosmos cues; a3 interpretive abstain; b2 contradicted
        assert by_id["a1"]["verdict"]["verdict"] == "supported"
        assert by_id["a2"]["verdict"]["verdict"] == "supported"
        assert by_id["a3"]["verdict"]["verdict"] == "not_visible"
        assert by_id["b1"]["verdict"]["verdict"] == "not_visible"
        assert by_id["b2"]["verdict"]["verdict"] == "contradicted"
        assert by_id["b3"]["verdict"]["verdict"] == "supported"

        for row in data["claim_reviews"]:
            assert 0 <= row["seek_sec"] < 5
            assert row["seek_absolute_sec"] == pytest.approx(
                INCIDENT["evidence_window_sec"]["start"] + row["seek_sec"]
            )
            assert row["verdict"]["human_review_required"] is True
            assert row["verdict"]["agent_answer_used_as_proof"] is False


def test_index_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Witness" in r.text
    assert "bearer" not in r.text.lower()
    assert "password" not in r.text.lower()


def test_media_proxy_uses_server_token(client):
    upstream = MagicMock()
    upstream.status_code = 206
    upstream.headers = {
        "Content-Type": "video/mp4",
        "Content-Range": "bytes 0-10/100",
        "Accept-Ranges": "bytes",
        "Content-Length": "11",
    }
    upstream.iter_content = lambda chunk_size=0: [b"\x00" * 11]
    upstream.close = MagicMock()

    with patch.object(main.vss, "configured", return_value=True), patch.object(
        main.vss, "open_stream", return_value=upstream
    ) as opened:
        r = client.get("/api/media/stream", headers={"Range": "bytes=0-10"})
        assert r.status_code == 206
        opened.assert_called()
        # Ensure client request did not need to pass a token query param
        assert "token" not in str(r.request.url).lower()
        upstream.close.assert_called_once()


def detection_pair(legacy=True):
    meta = _anchor_meta() | {
        'detection_sidecar_uri': INCIDENT['detection_sidecar_uri'], 'detection_count': 2380}
    det = {'source': 'yolo11_coco',
           'segment_source': INCIDENT['legacy_detection_source'] if legacy else INCIDENT['source'],
           'detection_count': 2380, 'frames': []}
    return meta, det


@pytest.mark.parametrize('echo_sidecar', [False, True])
@pytest.mark.parametrize('legacy', [False, True])
def test_yolo_review_preserves_provenance_without_anchor_sidecar_nameerror(client, monkeypatch, legacy, echo_sidecar):
    from copy import deepcopy
    meta, det = detection_pair(legacy)
    if echo_sidecar:
        det["detection_sidecar_uri"] = meta["detection_sidecar_uri"]
    original_meta = deepcopy(meta)
    original = deepcopy(det)
    monkeypatch.setattr(main.vss, 'segment_metadata', lambda source: meta)
    monkeypatch.setattr(main.vss, 'segment_detections', lambda source: det)
    monkeypatch.setattr(main.vss, 'search', lambda *a, **k: {'results': [meta]})
    response = client.get('/api/review')
    assert response.status_code == 200
    body = response.json()
    assert body['mode'] == 'vast' and body['synthetic'] is False
    assert len(body['claim_reviews']) == len(body['timeline']) == 6
    assert body['anchor']['detections']['source'] == 'yolo11_coco'
    assert body['anchor']['detections']['segment_source'] == original['segment_source']
    assert body['anchor']['metadata']['detection_sidecar_uri'] == meta['detection_sidecar_uri']
    assert det == original
    assert meta == original_meta
    assert body['wandb']['active'] is False


@pytest.mark.parametrize('target,field,value', [
    ('det', 'source', 'other_detector'),
    ('det', 'source', None),
    ('det', 'segment_source', None),
    ('det', 'segment_source', 's3://unrelated/video.mp4'),
    ('det', 'segment_source', INCIDENT['source'].replace('team-6', 'team-7')),
    ('det', 'segment_source', INCIDENT['source'].replace('0017', '0018')),
    ('det', 'segment_source', INCIDENT['source'] + '?signed=no'),
    ('det', 'segment_source', INCIDENT['legacy_detection_source'].replace('0017', '0018')),
    ('det', 'segment_source', INCIDENT['legacy_detection_source'].replace('/segments/', '/other/')),
    ('meta', 'detection_sidecar_uri', INCIDENT['detection_sidecar_uri'].replace('team-6', 'team-a')),
    ('meta', 'detection_sidecar_uri', INCIDENT['detection_sidecar_uri'].replace('0017', '0018')),
    ('det', 'detection_count', 2379),
    ('det', 'detection_count', '2380'),
    ('det', 'detection_count', True),
    ('det', 'detection_count', None),
    ('det', 'detection_sidecar_uri', 's3://other/sidecar.json'),
    ('det', 'synthetic', True),
    ('meta', 'source', INCIDENT['source'].replace('team-6', 'team-a')),
    ('meta', 'segment_start_sec', 24),
    ('meta', 'segment_end_sec', 31),
    ('meta', 'detection_sidecar_uri', None),
    ('meta', 'detection_sidecar_uri', 's3://other/sidecar.json'),
    ('meta', 'detection_count', 2379),
    ('meta', 'detection_count', None),
    ('meta', 'detection_count', True),
    ('det', 'detection_count', -1),
    ('det', 'detection_count', 2380.0),
])
def test_detection_provenance_rejected(client, monkeypatch, target, field, value):
    meta, det = detection_pair()
    (meta if target == 'meta' else det)[field] = value
    monkeypatch.setattr(main.vss, 'segment_metadata', lambda source: meta)
    monkeypatch.setattr(main.vss, 'segment_detections', lambda source: det)
    assert client.get('/api/review').status_code == 502
