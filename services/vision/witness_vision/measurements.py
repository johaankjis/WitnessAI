"""Measurements derived from tracks. Each function reports image-space geometry only.

Deliberately absent: braking, turn-signal use and traffic-light *changes*. A bounding box
cannot show brake lights or indicators, and apparent size/position mixes the other car's
motion with the dashcam's own motion. Those questions stay explicitly unknown here."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .config import VisionConfig
from .types import Detection, EventEstimate, SignalReading, SignalState, Track, VideoMeta


@dataclass(frozen=True)
class LateralShift:
    track_id: int
    label: str
    start: Detection
    end: Detection
    shift_fraction: float  # (end center x - start center x) / frame width; + is rightward


@dataclass(frozen=True)
class ScaleChange:
    track_id: int
    label: str
    start: Detection
    end: Detection
    area_ratio: float      # end box area / start box area


def _growth_series(track: Track, frame_area: float, min_area_fraction: float) -> list[tuple[Detection, float]]:
    series = []
    for a, b in zip(track.detections, track.detections[1:]):
        dt = b.timestamp_seconds - a.timestamp_seconds
        if dt <= 0 or a.box.area <= 0 or b.box.area / frame_area < min_area_fraction:
            continue
        series.append((b, (math.log(b.box.area) - math.log(a.box.area)) / dt))
    # 3-point median suppresses single-frame box jitter
    smoothed = []
    for i, (det, _) in enumerate(series):
        neighbours = sorted(g for _, g in series[max(0, i - 1): i + 2])
        smoothed.append((det, neighbours[len(neighbours) // 2]))
    return smoothed


def localize_event(tracks: list[Track], meta: VideoMeta, config: VisionConfig) -> EventEstimate | None:
    """Time at which a tracked vehicle's box area grew fastest (log-area rate). Fast growth
    means the gap to that object is closing quickly in the image; it does not say who
    moved, braked or was at fault. Returns None if nothing exceeds min_event_growth."""
    frame_area = float(meta.width * meta.height)
    if frame_area <= 0:
        return None
    best: tuple[float, float, int, Detection] | None = None
    for track in tracks:
        for det, growth in _growth_series(track, frame_area, config.min_area_fraction):
            key = (growth, -det.timestamp_seconds, -track.track_id)
            if best is None or key > best[:3]:
                best = (*key, det)
    if best is None or best[0] < config.min_event_growth:
        return None
    growth, _, neg_id, det = best
    t = det.timestamp_seconds
    start = max(0.0, t - config.window_before_seconds)
    end = min(meta.duration_seconds, t + config.window_after_seconds)
    return EventEstimate(t, det.frame_index, -neg_id, growth, start, end)


def lateral_shifts(tracks: list[Track], start: float, end: float, frame_width: int) -> list[LateralShift]:
    """Horizontal image displacement of each track within [start, end], largest first."""
    shifts = []
    for track in tracks:
        dets = track.within(start, end)
        if len(dets) >= 2 and frame_width > 0:
            shifts.append(LateralShift(track.track_id, track.label, dets[0], dets[-1],
                                       (dets[-1].box.center_x - dets[0].box.center_x) / frame_width))
    return sorted(shifts, key=lambda s: (-abs(s.shift_fraction), s.track_id))


def scale_changes(tracks: list[Track], start: float, end: float) -> list[ScaleChange]:
    """Box area ratio of each track within [start, end], largest growth first."""
    changes = []
    for track in tracks:
        dets = track.within(start, end)
        if len(dets) >= 2 and dets[0].box.area > 0:
            changes.append(ScaleChange(track.track_id, track.label, dets[0], dets[-1],
                                       dets[-1].box.area / dets[0].box.area))
    return sorted(changes, key=lambda c: (-c.area_ratio, c.track_id))


def estimate_signal_color(image: Any, det: Detection) -> SignalState:
    """Conservative HSV read of a traffic-light crop: returns a colour only when one hue band
    clearly dominates the bright, saturated pixels. Anything ambiguous is 'unknown'."""
    if image is None:
        return "unknown"
    try:
        import cv2
        import numpy as np
    except ImportError:
        return "unknown"
    h, w = image.shape[:2]
    x1, y1 = max(0, int(det.box.x1)), max(0, int(det.box.y1))
    x2, y2 = min(w, int(math.ceil(det.box.x2))), min(h, int(math.ceil(det.box.y2)))
    if x2 - x1 < 3 or y2 - y1 < 6:
        return "unknown"
    hsv = cv2.cvtColor(image[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
    hue, sat, val = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    lit = (sat > 100) & (val > 150)
    if lit.mean() < 0.03:
        return "unknown"
    counts = {
        "red": int(np.count_nonzero(lit & ((hue < 10) | (hue > 160)))),
        "yellow": int(np.count_nonzero(lit & (hue >= 15) & (hue <= 35))),
        "green": int(np.count_nonzero(lit & (hue >= 40) & (hue <= 95))),
    }
    ranked = sorted(counts.items(), key=lambda kv: -kv[1])
    if ranked[0][1] == 0 or ranked[0][1] < 2 * ranked[1][1]:
        return "unknown"
    return ranked[0][0]  # type: ignore[return-value]


def summarize_signal(track: Track, states: dict[Detection, SignalState]) -> SignalReading:
    """One state per light track, only if a clear majority (>=60%) of its detections agree
    and no other colour was read. Mixed readings become 'unknown': a change of light state
    is never inferred from per-frame colour reads."""
    readings = [states.get(d, "unknown") for d in track.detections]
    known = Counter(r for r in readings if r != "unknown")
    state: SignalState = "unknown"
    if len(known) == 1:
        (colour, count), = known.items()
        if count / len(readings) >= 0.6:
            state = colour
    return SignalReading(track.track_id, track.start_seconds, track.end_seconds, state, len(readings))
