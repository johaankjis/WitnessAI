"""Deterministic synthetic scenes. No pixels, no model, no randomness: a scripted list of
object trajectories is turned into detections, then runs through the *same* tracker,
measurements and contract mapping as real video. Output is always labelled is_mock."""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field

from .sources import sample_step
from .types import Box, Detection, Frame, VideoMeta

Keyframe = tuple[float, tuple[float, float, float, float]]


@dataclass(frozen=True)
class ScriptedObject:
    label: str
    keyframes: tuple[Keyframe, ...]  # (seconds, (x1, y1, x2, y2)), linearly interpolated
    confidence: float = 0.8

    def box_at(self, t: float) -> Box | None:
        kf = self.keyframes
        if t < kf[0][0] or t > kf[-1][0]:
            return None
        for (t0, b0), (t1, b1) in zip(kf, kf[1:]):
            if t0 <= t <= t1:
                a = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
                return Box(*(round(p + a * (q - p), 3) for p, q in zip(b0, b1)))
        return Box(*kf[-1][1])


@dataclass(frozen=True)
class SyntheticScene:
    name: str
    duration_seconds: float
    fps: float
    width: int
    height: int
    objects: tuple[ScriptedObject, ...]
    missing_frames: frozenset[int] = field(default_factory=frozenset)


class SyntheticFrameSource:
    def __init__(self, scene: SyntheticScene, uri: str):
        frame_count = int(round(scene.duration_seconds * scene.fps))
        self._meta = VideoMeta(uri, scene.fps, frame_count, scene.width, scene.height)
        self.scene = scene
        self._missing: list[int] = []

    @property
    def meta(self) -> VideoMeta:
        return self._meta

    @property
    def missing_frames(self) -> list[int]:
        return list(self._missing)

    @property
    def warnings(self) -> list[str]:
        return []

    def frames(self, sample_fps: float) -> Iterator[Frame]:
        self._missing = sorted(i for i in self.scene.missing_frames if i < self._meta.frame_count)
        step = sample_step(self._meta.fps, sample_fps)
        for index in range(0, self._meta.frame_count, step):
            if index in self.scene.missing_frames:
                continue
            yield Frame(index, index / self._meta.fps, self._meta.width, self._meta.height, image=None)


class ScriptedDetector:
    name = "scripted-synthetic"

    def __init__(self, scene: SyntheticScene):
        self.scene = scene

    def detect(self, frame: Frame) -> list[Detection]:
        out = []
        for obj in self.scene.objects:
            box = obj.box_at(frame.timestamp_seconds)
            if box is not None:
                out.append(Detection(frame.index, frame.timestamp_seconds, obj.label, obj.confidence, box))
        return out


def demo_lane_change_scene(duration_seconds: float = 20.0) -> SyntheticScene:
    """Matches the TASK-001 demo-001 story: another car cuts across into the dashcam lane
    between 8 and 11 s, then closes in fast around 11-12 s. No traffic light is in frame.
    A low-confidence phantom and two undecodable frames exercise the safety paths."""
    car_b = ScriptedObject("car", (
        (0.0, (430, 190, 500, 235)),
        (8.0, (410, 185, 495, 240)),
        (11.0, (290, 180, 390, 245)),
        (12.0, (230, 150, 420, 290)),
        (20.0, (225, 145, 425, 295)),
    ), confidence=0.86)
    distant_truck = ScriptedObject("truck", ((0.0, (90, 180, 140, 210)), (20.0, (90, 180, 140, 210))), confidence=0.71)
    phantom = ScriptedObject("car", ((5.0, (560, 40, 600, 70)), (6.0, (560, 40, 600, 70))), confidence=0.18)
    return SyntheticScene("demo-lane-change-v1", duration_seconds, 10.0, 640, 360,
                          (car_b, distant_truck, phantom), missing_frames=frozenset({58, 59}))
