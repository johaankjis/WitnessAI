"""End-to-end: generated videos -> witness_vision pipeline -> localization metrics.
Uses a pixel-threshold detector instead of YOLO, so no weights are needed."""
from pathlib import Path

import pytest

cv2 = pytest.importorskip("cv2")
np = pytest.importorskip("numpy")
pytest.importorskip("witness_vision")

from witness_vision.config import VisionConfig  # noqa: E402
from witness_vision.types import Box, Detection  # noqa: E402

from witness_evals import VisionPredictor, evaluate_localization, summarize  # noqa: E402
from witness_evals.labels import LabeledClip  # noqa: E402

FPS, W, H = 10.0, 160, 120


def write_clip(path: Path, growth_frame: int, frames: int = 50) -> None:
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), FPS, (W, H))
    for i in range(frames):
        s = 1.0 if i < growth_frame else min(5.0, 1.25 ** (i - growth_frame))
        img = np.full((H, W, 3), 90, dtype=np.uint8)
        x2, y2 = int(70 + 16 * s), int(60 + 10 * s)
        img[60:min(H, y2), 70:min(W, x2)] = (230, 40, 40)
        writer.write(img)
    writer.release()


class BlueBoxDetector:
    name = "blue-box"

    def detect(self, frame):
        ys, xs = np.nonzero((frame.image[..., 0] > 160) & (frame.image[..., 2] < 100))
        if len(xs) < 10:
            return []
        return [Detection(frame.index, frame.timestamp_seconds, "car", 0.9,
                          Box(float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1)))]


def test_vision_predictor_localizes_synthetic_growth(tmp_path):
    write_clip(tmp_path / "a.avi", growth_frame=20)
    write_clip(tmp_path / "b.avi", growth_frame=30)
    labels = [LabeledClip("a", 2.0), LabeledClip("b", 3.0), LabeledClip("missing", 1.0)]
    predictor = VisionPredictor(detector=BlueBoxDetector(), config=VisionConfig(sample_fps=10.0))
    results = evaluate_localization(labels, predictor, tmp_path)
    assert [r.status for r in results] == ["evaluated", "evaluated", "missing_video"]
    s = summarize(results)
    assert s["n_evaluated"] == 2 and s["n_within_tolerance"] == 2
    assert predictor.name == "witness_vision:blue-box@10fps"
