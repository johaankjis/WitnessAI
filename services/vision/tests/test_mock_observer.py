import json
from pathlib import Path

import pytest
from conftest import make_incident
from witness_contracts import AtomicClaim, DetectorObservation

from witness_vision.adapter import MockVisionObserver, VisionObserver
from witness_vision.errors import MockInputError
from witness_vision.mock import ScriptedObject, SyntheticScene

EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def dump(observations):
    return [o.model_dump(mode="json") for o in observations]


def test_deterministic(incident, claims):
    first, second = MockVisionObserver(), MockVisionObserver()
    assert dump(first.observe(incident, claims)) == dump(second.observe(incident, claims))
    assert first.last_analysis.to_dict() == second.last_analysis.to_dict()


def test_one_observation_per_claim_all_mock(incident, claims):
    observations = MockVisionObserver().observe(incident, claims)
    assert [o.claim_id for o in observations] == [c.id for c in claims]
    assert len({o.id for o in observations}) == len(observations)
    for o in observations:
        DetectorObservation.model_validate(o.model_dump())
        assert o.provenance.is_mock and o.evidence.provenance.is_mock
        assert o.confidence is None
        assert o.evidence.video_uri == incident.video_uri
        assert 0 <= o.evidence.start_seconds < o.evidence.end_seconds <= incident.duration_seconds
        assert o.evidence.description.startswith("SYNTHETIC")


def test_evidence_boundaries(incident, claims):
    by_claim = {o.claim_id: o for o in MockVisionObserver().observe(incident, claims)}
    # lateral image motion is measured and visible, but explicitly not a lane-change verdict
    lane = by_claim["c1"]
    assert lane.label == "vehicle_lateral_image_shift" and lane.evidence.visibility == "visible"
    assert "not by itself a lane-change determination" in lane.evidence.description
    # braking is never inferred from boxes
    for cid in ("c2", "c5"):
        assert by_claim[cid].label == "braking_unknown"
        assert by_claim[cid].evidence.visibility == "not_visible"
    # no light in frame -> not_visible, never contradiction
    assert by_claim["c3"].label == "traffic_light_not_visible"
    assert by_claim["c3"].evidence.visibility == "not_visible"
    assert "neither supports nor contradicts" in by_claim["c3"].evidence.description
    assert by_claim["c6"].label == "unsupported_claim_unknown"
    assert by_claim["c6"].evidence.visibility == "not_visible"


def test_ids_frames_and_timestamps_consistent(incident, claims):
    observer = MockVisionObserver()
    observations = observer.observe(incident, claims)
    analysis = observer.last_analysis
    fps = analysis.meta.fps
    assert all(abs(t - f / fps) < 1e-9 for f, t in zip(analysis.sampled_frames, analysis.sampled_timestamps))
    for track in analysis.tracks:
        assert all(abs(d.timestamp_seconds - d.frame_index / fps) < 1e-9 for d in track.detections)
    event = analysis.event
    assert event is not None and 10.0 <= event.timestamp_seconds <= 12.0
    assert event.frame_index == round(event.timestamp_seconds * fps)
    lane = observations[0]
    assert lane.id == f"vision-c1-vehicle_lateral_image_shift-track{event.track_id}"
    assert f"track {event.track_id}" in lane.evidence.description


def test_missing_frames_and_low_confidence_handled(incident, claims):
    observer = MockVisionObserver()
    observer.observe(incident, claims)
    analysis = observer.last_analysis
    assert analysis.missing_frames == [58, 59]
    assert 58 not in analysis.sampled_frames  # never fabricated
    assert analysis.low_confidence_dropped == 5  # phantom 0.18-confidence car on 5 samples
    assert {t.label for t in analysis.tracks} == {"car", "truck"}


def test_no_event_keeps_everything_unknown(claims):
    static = SyntheticScene("static", 10.0, 10.0, 640, 360,
                            (ScriptedObject("car", ((0.0, (300, 200, 360, 240)), (10.0, (300, 200, 360, 240)))),))
    incident = make_incident(duration_seconds=10.0)
    observer = MockVisionObserver(scene=static)
    observations = observer.observe(incident, claims)
    assert observer.last_analysis.event is None
    assert all(o.evidence.visibility == "not_visible" for o in observations)
    assert all("No event localized" in o.evidence.description for o in observations)


def test_empty_scene_has_no_tracks(claims):
    empty = SyntheticScene("empty", 5.0, 10.0, 640, 360, ())
    observations = MockVisionObserver(scene=empty).observe(make_incident(duration_seconds=5.0), claims)
    assert observations[0].label == "lane_change_unknown"
    assert "No vehicle tracked" in observations[0].evidence.description


def test_mock_and_real_never_mix(incident, claims):
    real = make_incident(is_mock=False, video_uri="/tmp/clip.mp4")
    with pytest.raises(MockInputError):
        MockVisionObserver().observe(real, claims)
    with pytest.raises(MockInputError):
        VisionObserver(detector=object()).observe(incident, claims)


def test_plugs_into_task001_pipeline(incident):
    pytest.importorskip("witness_api")
    from witness_api.mock import MockAdapters
    from witness_api.pipeline import Pipeline
    from witness_contracts import IncidentReport
    mock = MockAdapters()
    report = Pipeline(mock, mock, mock, MockVisionObserver(), mock, mock).analyze(incident)
    IncidentReport.model_validate(report.model_dump())
    assert len(report.observations) == len(report.claims) == 5
    assert report.is_mock and report.human_review_required


def test_examples_match_mock_output(incident):
    claims = [AtomicClaim.model_validate(c) for c in json.loads((EXAMPLES / "demo-001.claims.json").read_text())]
    expected = json.loads((EXAMPLES / "demo-001.observations.json").read_text())
    assert dump(MockVisionObserver().observe(incident, claims)) == expected
