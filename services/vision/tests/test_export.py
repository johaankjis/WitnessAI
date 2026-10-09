"""Per-detection export, full annotated video and CLI flags on tiny synthetic videos.
Skipped without OpenCV. No model weights used: the CLI's detector factory is monkeypatched."""
import csv
import json
from pathlib import Path

import pytest
from test_video_path import FPS, N, PixelDetector, write_video

cv2 = pytest.importorskip("cv2")

from witness_vision import __main__ as cli  # noqa: E402
from witness_vision.analysis import analyze_video  # noqa: E402
from witness_vision.annotate import write_annotated_video  # noqa: E402
from witness_vision.config import VisionConfig  # noqa: E402
from witness_vision.export import (  # noqa: E402
    COLUMNS,
    SCHEMA,
    detection_rows,
    detections_document,
    sha256_file,
    write_detections,
    write_detections_csv,
)
from witness_vision.sources import OpenCVFrameSource  # noqa: E402


@pytest.fixture
def video(tmp_path):
    return write_video(tmp_path / "clip.avi")


@pytest.fixture
def analysis(video):
    return analyze_video(OpenCVFrameSource(video), PixelDetector(), VisionConfig(sample_fps=5.0))


def test_rows_cover_every_kept_detection_with_exact_frame_identity(analysis):
    rows = detection_rows(analysis)
    assert len(rows) == sum(len(t.detections) for t in analysis.tracks) > 0
    assert rows == sorted(rows, key=lambda r: (r["frame_index"], r["track_id"]))
    sampled = set(analysis.sampled_frames)
    for row in rows:
        assert set(row) == set(COLUMNS)
        assert row["frame_index"] in sampled
        assert row["timestamp_seconds"] == pytest.approx(row["frame_index"] / FPS)
        assert row["x2"] > row["x1"] and row["y2"] > row["y1"]
        assert 0 <= row["confidence"] <= 1
    assert {r["label"] for r in rows} == {"car", "traffic light"}
    # the low-confidence decoy never forms a track, so it is absent
    assert not any(r["x2"] <= 4 for r in rows)


def test_document_carries_provenance_and_review_requirement(analysis, video, tmp_path):
    weights = tmp_path / "fake.pt"
    weights.write_bytes(b"not real weights")
    doc = detections_document(analysis, "test-pixel-detector", is_mock=False, config=VisionConfig(sample_fps=5.0),
                              weights_path=weights, video_path=video, device="cpu")
    assert doc["schema"] == SCHEMA and doc["human_review_required"] is True
    prov = doc["provenance"]
    assert prov["adapter"] == "witness-vision" and prov["is_mock"] is False
    assert prov["detector"] == "test-pixel-detector" and prov["weights"] == "fake.pt"
    assert prov["weights_sha256"] == sha256_file(weights) and prov["video_sha256"] == sha256_file(video)
    assert prov["sample_fps"] == 5.0 and prov["source_fps"] == FPS and prov["device"] == "cpu"
    assert prov["config"]["min_track_hits"] == 3
    assert doc["video"]["frame_count"] == N and doc["detections"] == detection_rows(analysis)
    assert any("not a probability" in note for note in doc["notes"])
    assert not any(note.startswith("SYNTHETIC") for note in doc["notes"])
    out = write_detections(doc, tmp_path / "out" / "dets.json")
    assert json.loads(out.read_text())["detections"] == doc["detections"]
    csv_path = write_detections_csv(doc["detections"], tmp_path / "out" / "dets.csv")
    with csv_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == len(doc["detections"]) and list(rows[0]) == list(COLUMNS)


def test_mock_document_is_labelled_synthetic(analysis):
    doc = detections_document(analysis, "scripted", is_mock=True)
    assert doc["provenance"]["adapter"] == "witness-vision-mock" and doc["provenance"]["is_mock"] is True
    assert doc["notes"][0].startswith("SYNTHETIC")
    assert doc["provenance"]["weights_sha256"] is None and doc["provenance"]["video_sha256"] is None


def test_full_annotated_video_has_every_sampled_frame_at_sample_rate(analysis, video, tmp_path):
    out = write_annotated_video(video, analysis, tmp_path / "annotated.mp4")
    cap = cv2.VideoCapture(str(out))
    assert cap.isOpened()
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == len(analysis.sampled_frames) == N // 2
    assert cap.get(cv2.CAP_PROP_FPS) == pytest.approx(analysis.sample_fps)
    cap.release()
    assert analysis.warnings == []  # writing a video is not an analysis warning and must not reach descriptions


def test_relative_video_path_gets_absolute_uri(video, monkeypatch):
    monkeypatch.chdir(video.parent)
    source = OpenCVFrameSource(Path(video.name))
    assert source.meta.uri == video.resolve().as_uri()


def test_cli_analyze_writes_all_artifacts(video, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli, "_detector", lambda args: PixelDetector())
    out = tmp_path / "o"
    code = cli.main(["analyze", str(video), "--sample-fps", "5", "--out", str(out / "analysis.json"),
                     "--detections-out", str(out / "dets.json"), "--detections-csv", str(out / "dets.csv"),
                     "--video-out", str(out / "full.mp4"), "--clip-out", str(out / "event.mp4")])
    assert code == 0 and capsys.readouterr().out == ""
    analysis = json.loads((out / "analysis.json").read_text())
    dets = json.loads((out / "dets.json").read_text())
    assert analysis["sampled_frame_count"] == N // 2 and analysis["event"] is not None
    assert dets["provenance"]["detector"] == "test-pixel-detector" and dets["provenance"]["is_mock"] is False
    assert dets["provenance"]["video_sha256"] == sha256_file(video)
    assert len(dets["detections"]) == sum(t["detections"] for t in analysis["tracks"])
    for name in ("dets.csv", "full.mp4", "event.mp4"):
        assert (out / name).stat().st_size > 0


def test_cli_observe_runs_real_adapter_on_local_file(video, tmp_path, monkeypatch, capsys):
    from conftest import make_claims, make_incident
    monkeypatch.setattr(cli, "_detector", lambda args: PixelDetector())
    incident = make_incident(id="real-1", video_uri=video.name, is_mock=False, duration_seconds=N / FPS)
    (tmp_path / "incident.json").write_text(incident.model_dump_json())
    (tmp_path / "claims.json").write_text(json.dumps([c.model_dump() for c in make_claims()]))
    code = cli.main(["observe", "--incident", str(tmp_path / "incident.json"),
                     "--claims", str(tmp_path / "claims.json"),
                     "--media-root", str(video.parent), "--sample-fps", "10", "--out", str(tmp_path / "obs.json"),
                     "--analysis-out", str(tmp_path / "analysis.json"), "--clip-dir", str(tmp_path / "clips")])
    assert code == 0
    observations = json.loads((tmp_path / "obs.json").read_text())
    assert [o["claim_id"] for o in observations] == [c.id for c in make_claims()]
    assert all(o["provenance"]["is_mock"] is False and o["evidence"]["video_uri"] == video.name for o in observations)
    assert (tmp_path / "clips" / "real-1-event.mp4").stat().st_size > 0
    assert "annotated event clip" in capsys.readouterr().err
    assert json.loads((tmp_path / "analysis.json").read_text())["event"] is not None
