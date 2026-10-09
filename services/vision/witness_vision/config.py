from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VisionConfig:
    """Tunable thresholds. Defaults are untuned starting points, not validated values;
    use evals/ to measure them on labeled clips before relying on them."""

    sample_fps: float = 5.0
    min_confidence: float = 0.35          # detections below this are dropped and counted
    min_track_hits: int = 3               # shorter tracks are treated as noise
    iou_match: float = 0.3                # tracker association threshold
    max_track_gap_seconds: float = 1.0    # a track ends after this long unmatched
    min_area_fraction: float = 0.002      # ignore tiny/distant boxes for growth scoring
    min_event_growth: float = 0.25        # d(ln area)/dt below this -> no event localized
    window_before_seconds: float = 2.0
    window_after_seconds: float = 1.0
    lateral_shift_fraction: float = 0.08  # min |dx|/frame width to report lateral motion
    max_consecutive_missing: int = 30     # decode failures tolerated before giving up
    max_missing_fraction: float = 0.2     # warn when more of the stream is missing

    @classmethod
    def from_env(cls) -> VisionConfig:
        fps = os.getenv("WITNESS_VISION_SAMPLE_FPS")
        conf = os.getenv("WITNESS_VISION_MIN_CONFIDENCE")
        return cls(sample_fps=float(fps) if fps else cls.sample_fps,
                   min_confidence=float(conf) if conf else cls.min_confidence)
