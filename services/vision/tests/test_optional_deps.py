import importlib.util
import logging
import sys

import pytest

from witness_vision import tracing
from witness_vision.analysis import analyze_video
from witness_vision.detectors import UltralyticsDetector
from witness_vision.errors import OptionalDependencyError
from witness_vision.mock import SyntheticFrameSource, demo_lane_change_scene
from witness_vision.types import Frame


class FakeTensor:
    def __init__(self, rows):
        self.rows = rows

    def tolist(self):
        return self.rows


class FakeModel:
    names = {0: "person", 2: "car", 9: "traffic light"}

    def __init__(self):
        self.calls = []

    def predict(self, image, **kwargs):
        self.calls.append(kwargs)
        boxes = type("Boxes", (), {"xyxy": FakeTensor([[1, 2, 30, 40], [5, 5, 9, 20]]),
                                   "conf": FakeTensor([0.8, 0.6]), "cls": FakeTensor([2, 9])})
        return [type("Result", (), {"boxes": boxes})]


def test_ultralytics_adapter_maps_results_without_weights():
    model = FakeModel()
    detector = UltralyticsDetector(weights="custom.pt", model=model)
    dets = detector.detect(Frame(index=7, timestamp_seconds=0.7, width=64, height=48, image=object()))
    assert [(d.frame_index, d.timestamp_seconds, d.label, d.confidence) for d in dets] == [
        (7, 0.7, "car", 0.8), (7, 0.7, "traffic light", 0.6)]
    assert model.calls[0]["classes"] == [2, 9]  # person excluded
    assert detector.name == "ultralytics:custom.pt"


def test_ultralytics_rejects_pixel_free_frames():
    with pytest.raises(ValueError):
        UltralyticsDetector(model=FakeModel()).detect(Frame(0, 0.0, 10, 10, image=None))


@pytest.mark.skipif(importlib.util.find_spec("ultralytics") is not None, reason="ultralytics installed")
def test_missing_ultralytics_is_a_clear_error():
    with pytest.raises(OptionalDependencyError, match="yolo"):
        UltralyticsDetector().detect(Frame(0, 0.0, 10, 10, image=object()))


def test_detector_may_not_alter_frame_identity():
    class Shifty:
        name = "shifty"

        def detect(self, frame):
            from witness_vision.types import Box, Detection
            return [Detection(frame.index + 1, frame.timestamp_seconds, "car", 0.9, Box(0, 0, 5, 5))]
    scene = demo_lane_change_scene()
    with pytest.raises(ValueError, match="frame index"):
        analyze_video(SyntheticFrameSource(scene, "mock://x"), Shifty())


def test_tracing_disabled_without_project():
    calls = []

    @tracing.traced("t")
    def f(x):
        calls.append(x)
        return x * 2
    assert f(3) == 6 and calls == [3]
    assert tracing.init_weave() is None


def test_tracing_degrades_when_weave_unavailable(monkeypatch, caplog):
    monkeypatch.setenv("WITNESS_WEAVE_PROJECT", "team/witness")
    monkeypatch.setitem(sys.modules, "weave", None)  # import raises ImportError

    @tracing.traced("t")
    def f():
        return "ok"
    with caplog.at_level(logging.WARNING):
        assert f() == "ok"
    assert "Weave tracing disabled" in caplog.text


def test_tracing_uses_weave_op_when_available(monkeypatch):
    ops = []

    class FakeWeave:
        @staticmethod
        def init(project):
            ops.append(("init", project))

        @staticmethod
        def op(name):
            def deco(fn):
                def run(*a, **k):
                    ops.append(("op", name))
                    return fn(*a, **k)
                return run
            return deco
    monkeypatch.setenv("WITNESS_WEAVE_PROJECT", "team/witness")
    monkeypatch.setitem(sys.modules, "weave", FakeWeave)

    @tracing.traced("witness.test")
    def f():
        return 1
    assert f() == 1 and f() == 1
    assert ops == [("init", "team/witness"), ("op", "witness.test"), ("op", "witness.test")]
