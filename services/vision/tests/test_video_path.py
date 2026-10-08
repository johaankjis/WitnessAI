"""Exercises real decode, sampling, annotation and the real adapter on tiny synthetic videos.
Skipped when the `video` extra (OpenCV + numpy) is not installed. No model weights used."""
from pathlib import Path

import pytest
from conftest import make_claims, make_incident

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")

from witness_vision.adapter import VisionObserver  # noqa: E402
from witness_vision.analysis import analyze_video  # noqa: E402
from witness_vision.annotate import extract_clip, write_annotated_clip  # noqa: E402
from witness_vision.config import VisionConfig  # noqa: E402
from witness_vision.errors import UnsupportedVideoError, VideoDecodeError  # noqa: E402
from witness_vision.sources import OpenCVFrameSource, resolve_video_path  # noqa: E402
from witness_vision.types import Box, Detection, Frame  # noqa: E402

FPS, W, H, N = 10.0, 160, 120, 40


def car_box(i):
    """Blue 'car' drifts left from frame 15 and grows from frame 25."""
    s = 1.0 if i < 25 else 1.12 ** (i - 25)
    x = 100 - max(0, i - 15) * 3
    return x, 60, x + 20 * s, 60 + 12 * s


def write_video(path: Path, light: tuple[int, int, int] | None = (40, 230, 40)) -> Path:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    assert writer.isOpened()
    for i in range(N):
        img = np.full((H, W, 3), 90, dtype=np.uint8)
        x1, y1, x2, y2 = (int(v) for v in car_box(i))
        img[y1:min(H, y2), max(0, x1):min(W, x2)] = (230, 40, 40)
        if light:
            img[5:35, 10:22] = (20, 20, 20)
            img[24:33, 12:20] = light
        writer.write(img)
    writer.release()
    return path


class PixelDetector:
    """Stand-in for YOLO: finds the blue box ('car') and dark housing ('traffic light')."""
    name = "test-pixel-detector"

    def detect(self, frame: Frame) -> list[Detection]:
        out = []
        img = frame.image.astype(int)
        masks = {"car": (img[..., 0] > 160) & (img[..., 2] < 100),
                 "traffic light": (img.sum(axis=2) < 120)}
        for label, mask in masks.items():
            ys, xs = np.nonzero(mask)
            if len(xs) > 10:
                box = Box(float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1))
                out.append(Detection(frame.index, frame.timestamp_seconds, label, 0.9, box))
        out.append(Detection(frame.index, frame.timestamp_seconds, "car", 0.1, Box(0, 0, 4, 4)))  # low conf
        return out


@pytest.fixture
def video(tmp_path):
    return write_video(tmp_path / "clip.avi")


def test_sampling_preserves_source_indices_and_timestamps(video):
    source = OpenCVFrameSource(video)
    frames = list(source.frames(sample_fps=5.0))
    assert [f.index for f in frames] == list(range(0, N, 2))
    assert all(f.timestamp_seconds == f.index / FPS for f in frames)
    assert source.meta.frame_count == N and source.missing_frames == []
    assert frames[0].image.shape == (H, W, 3)


def test_real_observer_end_to_end(video, tmp_path):
    incident = make_incident(video_uri=video.as_uri(), is_mock=False, duration_seconds=N / FPS)
    observer = VisionObserver(detector=PixelDetector(), config=VisionConfig(sample_fps=10.0),
                              clip_dir=tmp_path / "clips")
    observations = observer.observe(incident, make_claims())
    analysis = observer.last_analysis
    assert analysis.low_confidence_dropped == len(analysis.sampled_frames)
    assert analysis.event is not None and analysis.event.timestamp_seconds >= 2.5
    by_claim = {o.claim_id: o for o in observations}
    assert all(not o.provenance.is_mock and o.evidence.video_uri == incident.video_uri for o in observations)
    assert by_claim["c1"].label == "vehicle_lateral_image_shift"
    assert "leftward" in by_claim["c1"].evidence.description
    assert by_claim["c2"].label == "braking_unknown"
    assert by_claim["c3"].label == "traffic_light_color_estimate_green"
    assert by_claim["c3"].evidence.visibility == "visible"
    assert "no change of state is inferred" in by_claim["c3"].evidence.description
    assert observer.last_clip is not None and observer.last_clip.stat().st_size > 0


def test_unlit_signal_is_not_visible(tmp_path):
    path = write_video(tmp_path / "dark.avi", light=(25, 25, 25))
    incident = make_incident(video_uri=str(path), is_mock=False, duration_seconds=N / FPS)
    observations = VisionObserver(detector=PixelDetector()).observe(incident, make_claims())
    signal = next(o for o in observations if o.claim_id == "c3")
    assert signal.label == "traffic_light_state_unknown" and signal.evidence.visibility == "not_visible"


def test_annotated_clip_contains_only_sampled_frames(video, tmp_path):
    analysis = analyze_video(OpenCVFrameSource(video), PixelDetector(), VisionConfig(sample_fps=5.0))
    out = write_annotated_clip(video, analysis, 1.0, 2.0, tmp_path / "annot.mp4")
    cap = cv2.VideoCapture(str(out))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 6   # frames 10,12,...,20
    assert cap.get(cv2.CAP_PROP_FPS) == pytest.approx(5.0)
    cap.release()
    clip = extract_clip(video, analysis, 1.0, 2.0, tmp_path / "raw.mp4")
    cap = cv2.VideoCapture(str(clip))
    assert int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) == 11  # frames 10..20 at source rate
    cap.release()


def test_unsupported_and_corrupt_inputs(tmp_path):
    for uri in ("mock://x/no-video", "s3://bucket/clip.mp4", "https://x/clip.mp4"):
        with pytest.raises(UnsupportedVideoError):
            resolve_video_path(uri)
    text = tmp_path / "notes.txt"
    text.write_text("hi")
    with pytest.raises(UnsupportedVideoError):
        resolve_video_path(str(text))
    with pytest.raises(UnsupportedVideoError):
        resolve_video_path(str(tmp_path / "missing.mp4"))
    corrupt = tmp_path / "corrupt.mp4"
    corrupt.write_bytes(b"\x00not a video" * 100)
    with pytest.raises((UnsupportedVideoError, VideoDecodeError)):
        list(OpenCVFrameSource(corrupt).frames(5.0))


def test_relative_path_uses_media_root(video):
    assert resolve_video_path(video.name, media_root=video.parent) == video
