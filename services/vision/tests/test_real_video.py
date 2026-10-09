"""The real-video incident (TASK-004A). The incident record is always checked. Tests that
decode the footage or run YOLO are opt-in: they need the Nexar clip under
WITNESS_MEDIA_ROOT (default data/local/nexar) and, for inference, WITNESS_YOLO_WEIGHTS
pointing at a local weights file plus the `yolo` extra. Nothing is downloaded."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest
from witness_contracts import AtomicClaim, DetectorObservation, Incident

ROOT = Path(__file__).resolve().parents[3]
INCIDENT_PATH = ROOT / "data/real/nexar-00000.json"
CLAIMS_PATH = ROOT / "data/real/nexar-00000.claims.json"
MEDIA_ROOT = Path(os.getenv("WITNESS_MEDIA_ROOT", str(ROOT / "data/local/nexar")))
WEIGHTS = os.getenv("WITNESS_YOLO_WEIGHTS", "")
LABEL_SECONDS = 20.76  # train/positive/metadata.csv time_of_event for 00000.mp4 (not committed)


def incident() -> Incident:
    return Incident.model_validate_json(INCIDENT_PATH.read_text())


def claims() -> list[AtomicClaim]:
    return [AtomicClaim.model_validate(c) for c in json.loads(CLAIMS_PATH.read_text())]


def video_path() -> Path:
    return MEDIA_ROOT / incident().video_uri


needs_footage = pytest.mark.skipif(not video_path().is_file(), reason=f"Nexar clip not found under {MEDIA_ROOT}")
needs_yolo = pytest.mark.skipif(
    not (video_path().is_file() and Path(WEIGHTS).is_file() and importlib.util.find_spec("ultralytics")),
    reason="needs the Nexar clip, WITNESS_YOLO_WEIGHTS=<local file> and the yolo extra")


def test_incident_record_is_real_and_consistent_with_probed_media():
    record = incident()
    assert record.id == "nexar-00000" and record.is_mock is False
    assert record.video_uri == "train/positive/00000.mp4" and record.duration_seconds == 40.069204
    assert "sample statements" in record.title
    rows = claims()
    assert {c.statement_id for c in rows} <= {s.id for s in record.statements}
    assert len({c.id for c in rows}) == len(rows) == 6


@needs_footage
def test_footage_metadata_matches_incident():
    cv2 = pytest.importorskip("cv2")
    cap = cv2.VideoCapture(str(video_path()))
    assert cap.isOpened()
    fps, frames = cap.get(cv2.CAP_PROP_FPS), cap.get(cv2.CAP_PROP_FRAME_COUNT)
    size = (int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)))
    cap.release()
    assert fps == pytest.approx(28.9, abs=0.01) and frames == 1158 and size == (1280, 720)
    assert abs(frames / fps - incident().duration_seconds) < 0.05


@needs_footage
def test_api_serves_original_footage_for_real_incident(tmp_path, monkeypatch):
    """The TASK-003 media route streams the exact file, with byte ranges, and no report yet."""
    from fastapi.testclient import TestClient
    from witness_api.main import create_app
    from witness_api.storage import JsonStorage
    monkeypatch.setenv("WITNESS_ANALYSIS_MODE", "mock")
    monkeypatch.setenv("WITNESS_MEDIA_ROOT", str(MEDIA_ROOT))
    size = video_path().stat().st_size
    with TestClient(create_app(JsonStorage(INCIDENT_PATH, tmp_path / "reports"))) as client:
        got = client.get("/incidents/nexar-00000")
        assert got.status_code == 200 and got.json()["is_mock"] is False
        media = client.get("/incidents/nexar-00000/media")
        assert media.status_code == 200 and media.headers["content-type"] == "video/mp4"
        assert len(media.content) == size and media.content == video_path().read_bytes()
        partial = client.get("/incidents/nexar-00000/media", headers={"Range": "bytes=1000-1999"})
        assert partial.status_code == 206 and len(partial.content) == 1000
        assert partial.headers["content-range"] == f"bytes 1000-1999/{size}"
        assert client.get("/incidents/nexar-00000/results").status_code == 409
        assert client.get("/incidents/nexar-00000/status").status_code == 409


@pytest.fixture(scope="module")
def real_run():
    from witness_vision.adapter import VisionObserver
    from witness_vision.config import VisionConfig
    from witness_vision.detectors import UltralyticsDetector
    observer = VisionObserver(detector=UltralyticsDetector(WEIGHTS, min_confidence=0.1),
                              config=VisionConfig(sample_fps=5.0), media_root=MEDIA_ROOT)
    return observer, observer.observe(incident(), claims())


@needs_yolo
def test_yolo_detects_and_tracks_vehicles_on_real_footage(real_run):
    observer, _ = real_run
    analysis = observer.last_analysis
    assert analysis.meta.frame_count == 1158 and analysis.sample_fps == pytest.approx(28.9 / 6)
    assert len(analysis.sampled_frames) == 193 and analysis.missing_frames == []
    vehicles = analysis.vehicle_tracks()
    assert vehicles and max(len(t.detections) for t in vehicles) >= 10
    assert all(t.track_id >= 1 for t in analysis.tracks)
    for track in analysis.tracks:
        frames = [d.frame_index for d in track.detections]
        assert frames == sorted(frames) and all(f in set(analysis.sampled_frames) for f in frames)
        assert all(0 < d.confidence <= 1 for d in track.detections)
    if analysis.event is not None:
        assert 0 <= analysis.event.timestamp_seconds <= analysis.meta.duration_seconds


@needs_yolo
def test_observations_keep_evidence_boundary_on_real_footage(real_run):
    observer, observations = real_run
    record = incident()
    assert [o.claim_id for o in observations] == [c.id for c in claims()]
    for obs in observations:
        assert DetectorObservation.model_validate(obs.model_dump()) == obs
        assert obs.provenance.adapter == "witness-vision" and obs.provenance.is_mock is False
        assert obs.evidence.video_uri == record.video_uri and obs.evidence.end_seconds <= record.duration_seconds
        assert obs.confidence is None and "SYNTHETIC" not in obs.evidence.description
        if obs.evidence.visibility == "visible":
            assert obs.label.startswith(("vehicle_lateral_image_shift", "traffic_light_color_estimate_"))
        else:
            assert obs.label.endswith(("_unknown", "_not_visible"))
    by_claim = {o.claim_id: o for o in observations}
    assert by_claim["c2"].label == "braking_unknown" and by_claim["c2"].evidence.visibility == "not_visible"
    assert by_claim["c6"].label == "unsupported_claim_unknown"
