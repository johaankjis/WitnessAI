"""Frame sampling -> detection -> tracking -> measurements, independent of contracts."""
from __future__ import annotations

from .config import VisionConfig
from .detectors import Detector
from .measurements import estimate_signal_color, localize_event, summarize_signal
from .sources import FrameSource, sample_step
from .tracing import traced
from .tracking import IoUTracker
from .types import TRAFFIC_LIGHT, VEHICLE_CLASSES, Detection, SignalState, VideoAnalysis


@traced("witness_vision.analyze_video")
def analyze_video(source: FrameSource, detector: Detector, config: VisionConfig | None = None) -> VideoAnalysis:
    config = config or VisionConfig()
    tracker = IoUTracker(config.iou_match, config.max_track_gap_seconds)
    sampled_frames: list[int] = []
    sampled_timestamps: list[float] = []
    low_conf = 0
    signal_states: dict[Detection, SignalState] = {}
    last_ts = -1.0
    warnings: list[str] = []
    for frame in source.frames(config.sample_fps):
        if frame.timestamp_seconds <= last_ts:
            warnings.append(f"non-increasing timestamp at frame {frame.index}; frame skipped")
            continue
        last_ts = frame.timestamp_seconds
        sampled_frames.append(frame.index)
        sampled_timestamps.append(frame.timestamp_seconds)
        kept = []
        for det in detector.detect(frame):
            if det.frame_index != frame.index or det.timestamp_seconds != frame.timestamp_seconds:
                raise ValueError("detector changed frame index or timestamp")
            if det.confidence < config.min_confidence:
                low_conf += 1
                continue
            kept.append(det)
            if det.label == TRAFFIC_LIGHT:
                signal_states[det] = estimate_signal_color(frame.image, det)
        tracker.update(kept)
    meta = source.meta
    tracks = tracker.tracks(config.min_track_hits)
    vehicles = [t for t in tracks if t.label in VEHICLE_CLASSES]
    missing = source.missing_frames
    warnings = source.warnings + warnings
    if meta.frame_count and len(missing) / meta.frame_count > config.max_missing_fraction:
        warnings.append(f"{len(missing)} of {meta.frame_count} frames missing; measurements may be unreliable")
    effective = meta.fps / sample_step(meta.fps, config.sample_fps)
    return VideoAnalysis(
        meta=meta, sample_fps=effective, sampled_frames=sampled_frames,
        sampled_timestamps=sampled_timestamps, missing_frames=missing, low_confidence_dropped=low_conf,
        tracks=tracks, event=localize_event(vehicles, meta, config),
        signals=[summarize_signal(t, signal_states) for t in tracks if t.label == TRAFFIC_LIGHT],
        warnings=warnings)
