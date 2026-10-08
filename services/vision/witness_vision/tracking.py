"""Deterministic greedy IoU tracker. Kept dependency-free so mock and real runs share it and
track IDs are reproducible: same detections in, same IDs out."""
from __future__ import annotations

from .types import Detection, Track


class IoUTracker:
    def __init__(self, iou_match: float = 0.3, max_gap_seconds: float = 1.0):
        self.iou_match = iou_match
        self.max_gap_seconds = max_gap_seconds
        self._active: list[Track] = []
        self._finished: list[Track] = []
        self._next_id = 1

    def update(self, detections: list[Detection]) -> None:
        """Feed all detections for one sampled frame (same timestamp)."""
        if not detections:
            return
        now = detections[0].timestamp_seconds
        still_active = []
        for track in self._active:
            (still_active if now - track.end_seconds <= self.max_gap_seconds else self._finished).append(track)
        self._active = still_active
        order = sorted(detections, key=lambda d: (-d.confidence, d.label, d.box.x1, d.box.y1))
        claimed: set[int] = set()
        for det in order:
            best, best_iou = None, self.iou_match
            for track in self._active:
                if track.track_id in claimed or track.label != det.label:
                    continue
                iou = track.detections[-1].box.iou(det.box)
                if iou >= best_iou and (best is None or iou > best_iou):
                    best, best_iou = track, iou
            if best is None:
                best = Track(self._next_id, det.label)
                self._next_id += 1
                self._active.append(best)
            best.detections.append(det)
            claimed.add(best.track_id)

    def tracks(self, min_hits: int = 1) -> list[Track]:
        """All tracks with at least min_hits detections, ordered by ID. IDs are never reused
        or renumbered, so dropped short tracks leave gaps rather than shifting other IDs."""
        return sorted((t for t in self._finished + self._active if len(t.detections) >= min_hits),
                      key=lambda t: t.track_id)
