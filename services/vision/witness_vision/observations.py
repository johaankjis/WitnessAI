"""Map a VideoAnalysis onto shared-contract DetectorObservation records.

Rules enforced here (see AGENTS.md evidence boundary):
- One observation per claim, so every claim gets an explicit answer from the detector.
- Only geometric measurements are reported as `visible`. Braking, signalling intent,
  light changes and anything else a box cannot show are `not_visible` with an `_unknown`
  label. Absence of a detection is never phrased as evidence against a claim.
- confidence is always None: detector scores are not calibrated claim probabilities.
- Contracts have no fields for frame indices or track IDs, so both are written into the
  observation id/description (see CONTRACT_REQUESTS.md).
"""
from __future__ import annotations

from witness_contracts import AtomicClaim, DetectorObservation, EvidenceWindow, Incident, Provenance

from .config import VisionConfig
from .measurements import lateral_shifts, scale_changes
from .types import VideoAnalysis


def clip_window(start: float, end: float, limit: float, min_width: float) -> tuple[float, float]:
    """Clamp to [0, limit] while keeping end > start (contract requirement). Bounds are
    rounded to the microsecond only to drop float noise from window arithmetic."""
    start, end = round(start, 6), round(end, 6)
    start = max(0.0, min(start, limit))
    end = min(limit, max(end, start))
    if end <= start:
        end = min(limit, start + min_width)
    if end <= start:
        start = max(0.0, end - min_width)
    return start, end


class ObservationBuilder:
    def __init__(self, incident: Incident, analysis: VideoAnalysis, provenance: Provenance,
                 config: VisionConfig | None = None, description_prefix: str = ""):
        self.incident = incident
        self.analysis = analysis
        self.provenance = provenance
        self.config = config or VisionConfig()
        self.prefix = description_prefix
        self.limit = min(incident.duration_seconds, analysis.meta.duration_seconds)
        self.min_width = 1.0 / analysis.sample_fps if analysis.sample_fps > 0 else 0.1

    def build(self, claims: list[AtomicClaim]) -> list[DetectorObservation]:
        handlers = {"lane_change": self._lane_change, "braking": self._braking,
                    "traffic_signal": self._traffic_signal}
        return [handlers.get(c.category, self._unsupported)(c) for c in claims]

    # -- helpers -----------------------------------------------------------------------------
    def _review_window(self) -> tuple[float, float, str]:
        event = self.analysis.event
        if event is None:
            start, end = clip_window(0.0, self.limit, self.limit, self.min_width)
            return start, end, ("No event localized (no tracked vehicle exceeded growth threshold); "
                                f"reviewed {start:.2f}-{end:.2f}s.")
        start, end = clip_window(event.window_start, event.window_end, self.limit, self.min_width)
        return start, end, (f"Detector event window {start:.2f}-{end:.2f}s around fastest box growth "
                            f"(track {event.track_id}, frame {event.frame_index}, t={event.timestamp_seconds:.2f}s).")

    def _frames(self, start: float, end: float) -> str:
        a = self.analysis
        frames = [f for f, t in zip(a.sampled_frames, a.sampled_timestamps) if start <= t <= end]
        missing = [f for f in a.missing_frames if start <= f / a.meta.fps <= end]
        text = "no sampled frames"
        if frames:
            text = f"sampled frames {frames[0]}-{frames[-1]} ({len(frames)} @ {a.sample_fps:g} fps)"
        return text + (f"; {len(missing)} frames missing/undecodable" if missing else "")

    def _obs(self, claim: AtomicClaim, label: str, start: float, end: float, visible: bool,
             description: str, suffix: str = "") -> DetectorObservation:
        start, end = clip_window(start, end, self.limit, self.min_width)
        window = EvidenceWindow(
            video_uri=self.incident.video_uri, start_seconds=start, end_seconds=end,
            visibility="visible" if visible else "not_visible",
            description=f"{self.prefix}{description} [{self._frames(start, end)}]",
            provenance=self.provenance)
        return DetectorObservation(id=f"vision-{claim.id}-{label}{suffix}", claim_id=claim.id, label=label,
                                   evidence=window, confidence=None, provenance=self.provenance)

    # -- per category ----------------------------------------------------------------------
    def _lane_change(self, claim: AtomicClaim) -> DetectorObservation:
        start, end, context = self._review_window()
        shifts = lateral_shifts(self.analysis.vehicle_tracks(), start, end, self.analysis.meta.width)
        if not shifts:
            return self._obs(claim, "lane_change_unknown", start, end, False,
                             f"{context} No vehicle tracked in this window; lane position not measured.")
        top = shifts[0]
        if abs(top.shift_fraction) < self.config.lateral_shift_fraction:
            return self._obs(claim, "lane_change_unknown", start, end, False,
                             f"{context} Largest lateral image shift was track {top.track_id} "
                             f"({top.shift_fraction:+.1%} of frame width), below the "
                             f"{self.config.lateral_shift_fraction:.0%} reporting threshold; inconclusive, "
                             "not evidence of no lane change.")
        a, b = top.start, top.end
        direction = "rightward" if top.shift_fraction > 0 else "leftward"
        return self._obs(claim, "vehicle_lateral_image_shift", a.timestamp_seconds, b.timestamp_seconds, True,
                         f"{context} Track {top.track_id} ({top.label}) box centre moved {direction} "
                         f"{abs(top.shift_fraction):.1%} of frame width from frame {a.frame_index} "
                         f"(t={a.timestamp_seconds:.2f}s) to frame {b.frame_index} (t={b.timestamp_seconds:.2f}s). "
                         "Image-space motion only: lane markings and dashcam motion are not measured, "
                         "so this is not by itself a lane-change determination.",
                         suffix=f"-track{top.track_id}")

    def _braking(self, claim: AtomicClaim) -> DetectorObservation:
        start, end, context = self._review_window()
        changes = scale_changes(self.analysis.vehicle_tracks(), start, end)
        detail = ""
        if changes:
            top = changes[0]
            detail = (f" Largest box growth: track {top.track_id} ({top.label}) area x{top.area_ratio:.2f} "
                      f"frames {top.start.frame_index}-{top.end.frame_index}; this shows the image gap "
                      "changing, not which vehicle slowed.")
        return self._obs(claim, "braking_unknown", start, end, False,
                         f"{context} Braking cannot be determined from bounding boxes (brake lights and "
                         f"vehicle speed are not measured).{detail}")

    def _traffic_signal(self, claim: AtomicClaim) -> DetectorObservation:
        start, end, context = self._review_window()
        readings = [s for s in self.analysis.signals if s.last_seconds >= start and s.first_seconds <= end]
        if not readings:
            return self._obs(claim, "traffic_light_not_visible", start, end, False,
                             f"{context} No traffic light was detected in this window; its state is unknown, "
                             "which neither supports nor contradicts the claim.")
        states = {s.state for s in readings}
        ids = ", ".join(str(s.track_id) for s in readings)
        if len(states) != 1 or "unknown" in states:
            return self._obs(claim, "traffic_light_state_unknown", start, end, False,
                             f"{context} Traffic light track(s) {ids} detected but colour could not be read "
                             "consistently; state unknown. Light changes are never inferred.")
        state = states.pop()
        first = min(s.first_seconds for s in readings)
        last = max(s.last_seconds for s in readings)
        return self._obs(claim, f"traffic_light_color_estimate_{state}", max(start, first), min(end, last), True,
                         f"{context} Traffic light track(s) {ids} visible {first:.2f}-{last:.2f}s; HSV colour "
                         f"estimate '{state}' in a clear majority of crops. Which lane or driver this light "
                         "governs is not determined, and no change of state is inferred.")

    def _unsupported(self, claim: AtomicClaim) -> DetectorObservation:
        start, end, context = self._review_window()
        return self._obs(claim, "unsupported_claim_unknown", start, end, False,
                         f"{context} The detector has no measurement for '{claim.category}' claims; unknown.")
