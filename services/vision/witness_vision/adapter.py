"""YoloObserver adapters for apps/api (Protocol: observe(incident, claims) -> observations).

- MockVisionObserver: synthetic incidents only (is_mock=True, mock:// URI).
- VisionObserver: real local footage only (is_mock=False). Never accepts mock incidents,
  never fabricates evidence; failures raise VisionError subclasses.
"""
from __future__ import annotations

from pathlib import Path

from witness_contracts import AtomicClaim, DetectorObservation, Incident, Provenance

from . import __version__
from .analysis import analyze_video
from .config import VisionConfig
from .detectors import Detector, UltralyticsDetector
from .errors import MockInputError
from .mock import ScriptedDetector, SyntheticFrameSource, SyntheticScene, demo_lane_change_scene
from .observations import ObservationBuilder
from .sources import OpenCVFrameSource, resolve_video_path
from .tracing import traced
from .types import VideoAnalysis


class MockVisionObserver:
    def __init__(self, scene: SyntheticScene | None = None, config: VisionConfig | None = None):
        self.scene = scene
        self.config = config or VisionConfig()
        self.last_analysis: VideoAnalysis | None = None

    def provenance(self, scene: SyntheticScene) -> Provenance:
        return Provenance(adapter="witness-vision-mock", version=__version__,
                          source=f"scripted synthetic scene '{scene.name}'; no video analyzed", is_mock=True)

    @traced("witness_vision.mock_observe")
    def observe(self, incident: Incident, claims: list[AtomicClaim]) -> list[DetectorObservation]:
        if not incident.is_mock or not incident.video_uri.startswith("mock://"):
            raise MockInputError("MockVisionObserver only accepts is_mock incidents with mock:// video")
        scene = self.scene or demo_lane_change_scene(incident.duration_seconds)
        analysis = analyze_video(SyntheticFrameSource(scene, incident.video_uri), ScriptedDetector(scene), self.config)
        self.last_analysis = analysis
        return ObservationBuilder(incident, analysis, self.provenance(scene), self.config,
                                  description_prefix="SYNTHETIC, no footage analyzed. ").build(claims)


class VisionObserver:
    """Real footage. Resolves Incident.video_uri to a local file (absolute path, file:// URI,
    or path relative to media_root), samples frames with OpenCV, detects with YOLO and
    tracks with the IoU tracker. If clip_dir is set, writes an annotated event clip and
    records its path in last_clip (contracts have no field for it yet)."""

    def __init__(self, detector: Detector | None = None, config: VisionConfig | None = None,
                 media_root: Path | None = None, clip_dir: Path | None = None):
        self.config = config or VisionConfig.from_env()
        self.detector = detector or UltralyticsDetector(min_confidence=min(0.1, self.config.min_confidence))
        self.media_root = media_root
        self.clip_dir = clip_dir
        self.last_analysis: VideoAnalysis | None = None
        self.last_clip: Path | None = None

    def provenance(self, analysis: VideoAnalysis) -> Provenance:
        return Provenance(adapter="witness-vision", version=__version__, is_mock=False,
                          source=f"{self.detector.name} + IoU tracker; {analysis.sample_fps:g} fps sample "
                                 f"of {analysis.meta.uri}")

    @traced("witness_vision.observe")
    def observe(self, incident: Incident, claims: list[AtomicClaim]) -> list[DetectorObservation]:
        if incident.is_mock:
            raise MockInputError("VisionObserver analyzes real footage only; use MockVisionObserver for mock incidents")
        path = resolve_video_path(incident.video_uri, self.media_root)
        source = OpenCVFrameSource(path, uri=incident.video_uri,
                                   max_consecutive_missing=self.config.max_consecutive_missing)
        analysis = analyze_video(source, self.detector, self.config)
        if analysis.meta.duration_seconds > incident.duration_seconds + 0.5:
            analysis.warnings.append(f"video is {analysis.meta.duration_seconds:.2f}s but incident declares "
                                     f"{incident.duration_seconds:.2f}s; windows clipped to the incident")
        self.last_analysis = analysis
        self.last_clip = None
        if self.clip_dir is not None and analysis.event is not None:
            from .annotate import write_annotated_clip
            event = analysis.event
            self.last_clip = write_annotated_clip(path, analysis, event.window_start, event.window_end,
                                                  self.clip_dir / f"{incident.id}-event.mp4")
        prefix = f"Analysis warnings: {'; '.join(analysis.warnings)}. " if analysis.warnings else ""
        return ObservationBuilder(incident, analysis, self.provenance(analysis), self.config, prefix).build(claims)
