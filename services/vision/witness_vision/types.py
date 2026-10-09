"""Internal vision records. Richer than the shared contracts: they keep frame indices,
track IDs and boxes so nothing is lost before mapping to DetectorObservation.

Units: timestamps are float seconds from the start of the source video, frame indices are
0-based indices into the *source* stream (not into the sampled subset), boxes are pixel
(x1, y1, x2, y2) in source resolution.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

VEHICLE_CLASSES = frozenset({"car", "truck", "bus", "motorcycle", "bicycle"})
TRAFFIC_LIGHT = "traffic light"
SignalState = Literal["red", "yellow", "green", "unknown"]


@dataclass(frozen=True)
class VideoMeta:
    uri: str
    fps: float
    frame_count: int
    width: int
    height: int

    @property
    def duration_seconds(self) -> float:
        return self.frame_count / self.fps


@dataclass(frozen=True)
class Frame:
    index: int
    timestamp_seconds: float
    width: int
    height: int
    image: Any = None  # BGR ndarray for real video; None for synthetic frames


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2

    def iou(self, other: Box) -> float:
        ix = max(0.0, min(self.x2, other.x2) - max(self.x1, other.x1))
        iy = max(0.0, min(self.y2, other.y2) - max(self.y1, other.y1))
        inter = ix * iy
        union = self.area + other.area - inter
        return inter / union if union > 0 else 0.0


@dataclass(frozen=True)
class Detection:
    frame_index: int
    timestamp_seconds: float
    label: str
    confidence: float
    box: Box


@dataclass
class Track:
    track_id: int
    label: str
    detections: list[Detection] = field(default_factory=list)

    @property
    def start_seconds(self) -> float:
        return self.detections[0].timestamp_seconds

    @property
    def end_seconds(self) -> float:
        return self.detections[-1].timestamp_seconds

    @property
    def mean_confidence(self) -> float:
        return sum(d.confidence for d in self.detections) / len(self.detections)

    def within(self, start: float, end: float) -> list[Detection]:
        return [d for d in self.detections if start <= d.timestamp_seconds <= end]


@dataclass(frozen=True)
class EventEstimate:
    """Detector-based event localization: the sample where a tracked object's apparent size
    grew fastest. This is a measurement of image motion, not a claim about what happened."""

    timestamp_seconds: float
    frame_index: int
    track_id: int
    growth_per_second: float
    window_start: float
    window_end: float


@dataclass(frozen=True)
class SignalReading:
    track_id: int
    first_seconds: float
    last_seconds: float
    state: SignalState
    detections: int


@dataclass
class VideoAnalysis:
    meta: VideoMeta
    sample_fps: float
    sampled_frames: list[int]
    sampled_timestamps: list[float]
    missing_frames: list[int]
    low_confidence_dropped: int
    tracks: list[Track]
    event: EventEstimate | None
    signals: list[SignalReading]
    warnings: list[str] = field(default_factory=list)

    def vehicle_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.label in VEHICLE_CLASSES]

    def signal_tracks(self) -> list[Track]:
        return [t for t in self.tracks if t.label == TRAFFIC_LIGHT]

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly summary for debugging, examples and evals."""
        return {
            "video_uri": self.meta.uri,
            "fps": self.meta.fps,
            "frame_count": self.meta.frame_count,
            "duration_seconds": round(self.meta.duration_seconds, 6),
            "resolution": [self.meta.width, self.meta.height],
            "sample_fps": self.sample_fps,
            "sampled_frame_count": len(self.sampled_frames),
            "missing_frames": self.missing_frames,
            "low_confidence_dropped": self.low_confidence_dropped,
            "tracks": [
                {
                    "track_id": t.track_id,
                    "label": t.label,
                    "first_frame": t.detections[0].frame_index,
                    "last_frame": t.detections[-1].frame_index,
                    "start_seconds": t.start_seconds,
                    "end_seconds": t.end_seconds,
                    "detections": len(t.detections),
                    "mean_confidence": round(t.mean_confidence, 4),
                }
                for t in self.tracks
            ],
            "event": None if self.event is None else {
                "timestamp_seconds": self.event.timestamp_seconds,
                "frame_index": self.event.frame_index,
                "track_id": self.event.track_id,
                "growth_per_second": round(self.event.growth_per_second, 4),
                "window": [self.event.window_start, self.event.window_end],
            },
            "signals": [
                {"track_id": s.track_id, "state": s.state, "first_seconds": s.first_seconds,
                 "last_seconds": s.last_seconds, "detections": s.detections}
                for s in self.signals
            ],
            "warnings": self.warnings,
        }
