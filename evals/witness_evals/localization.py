"""Event-localization evaluation against labeled time_of_event values.

Predictors return a time in seconds, or None to abstain. Any exception is recorded as an
`error` example; it is never converted into a prediction."""
from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Protocol

from .labels import LabeledClip
from .metrics import ExampleResult, summarize

logger = logging.getLogger(__name__)
VIDEO_EXTENSIONS = (".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm")


class Predictor(Protocol):
    name: str
    needs_video: bool

    def predict(self, clip_id: str, video: Path | None) -> float | None: ...


class PredictionFilePredictor:
    """Scores precomputed predictions, e.g. Cosmos Reason output or cached detector runs.
    File format: {"<clip id>": <seconds or null>, ...}. Absent IDs count as missing."""

    needs_video = False

    def __init__(self, path: Path, name: str | None = None):
        self.predictions: dict[str, Any] = json.loads(path.read_text())
        self.name = name or f"file:{path.name}"

    def predict(self, clip_id: str, video: Path | None) -> float | None:
        if clip_id not in self.predictions:
            raise KeyError(f"no prediction for {clip_id}")
        value = self.predictions[clip_id]
        return None if value is None else float(value)


class VisionPredictor:
    """Runs the witness_vision detector pipeline and returns its event timestamp."""

    needs_video = True

    def __init__(self, detector: Any = None, config: Any = None):
        from witness_vision.config import VisionConfig
        from witness_vision.detectors import UltralyticsDetector
        self.config = config or VisionConfig.from_env()
        self.detector = detector or UltralyticsDetector(min_confidence=min(0.1, self.config.min_confidence))
        self.name = f"witness_vision:{self.detector.name}@{self.config.sample_fps:g}fps"

    def predict(self, clip_id: str, video: Path | None) -> float | None:
        from witness_vision.analysis import analyze_video
        from witness_vision.sources import OpenCVFrameSource
        assert video is not None
        analysis = analyze_video(OpenCVFrameSource(video), self.detector, self.config)
        return None if analysis.event is None else analysis.event.timestamp_seconds


def find_video(video_dir: Path, clip_id: str) -> Path | None:
    for ext in VIDEO_EXTENSIONS:
        candidate = video_dir / f"{clip_id}{ext}"
        if candidate.is_file():
            return candidate
    return None


def evaluate_localization(labels: Iterable[LabeledClip], predictor: Predictor,
                          video_dir: Path | None = None, limit: int | None = None) -> list[ExampleResult]:
    """Evaluate labeled positives in order; `limit` caps how many labeled clips are attempted."""
    results: list[ExampleResult] = []
    attempted = 0
    for clip in labels:
        if limit is not None and attempted >= limit:
            break
        if clip.time_of_event is None:
            results.append(ExampleResult(clip.id, "no_label", detail="no time_of_event"))
            continue
        attempted += 1
        video = None
        if predictor.needs_video:
            video = find_video(video_dir, clip.id) if video_dir else None
            if video is None:
                results.append(ExampleResult(clip.id, "missing_video", clip.time_of_event))
                continue
        try:
            predicted = predictor.predict(clip.id, video)
        except Exception as exc:  # recorded per example; one bad clip must not end the run
            logger.warning("prediction failed for %s: %s", clip.id, exc)
            results.append(ExampleResult(clip.id, "error", clip.time_of_event, detail=f"{type(exc).__name__}: {exc}"))
            continue
        if predicted is None:
            results.append(ExampleResult(clip.id, "abstained", clip.time_of_event, detail="no event localized"))
        else:
            results.append(ExampleResult(clip.id, "evaluated", clip.time_of_event, predicted))
    return results


def report(results: list[ExampleResult], predictor_name: str, tolerance: float = 1.0) -> dict[str, Any]:
    return {"task": "event_localization", "predictor": predictor_name, "summary": summarize(results, tolerance),
            "examples": [r.to_dict() for r in results]}
