"""Per-detection export of a VideoAnalysis: every detection the detector produced on every
sampled frame, with the track ID the IoU tracker assigned, as JSON (with provenance) or CSV.

Rows are detector outputs, not claim evidence. `confidence` is the detector's class score
for that box and says nothing about any driver claim; `track_id` is an image-space
association, not a vehicle identity; box growth or motion is image geometry, not speed,
braking or a lane change. Only sampled frames appear and nothing is interpolated.
Detections that belonged to tracks shorter than `min_track_hits` were discarded as noise
by the analysis and are therefore absent here."""
from __future__ import annotations

import csv
import hashlib
import json
import os
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .config import VisionConfig
from .types import VideoAnalysis

SCHEMA = "witness-vision/detections@1"
COLUMNS = ("frame_index", "timestamp_seconds", "track_id", "label", "confidence", "x1", "y1", "x2", "y2")
NOTES = (
    "Rows are raw detector outputs on sampled frames; they are not verdicts on any claim.",
    "confidence is the detector's class score for a box, not a probability that a claim is true.",
    "track_id is an image-space association made by a greedy IoU tracker; it is not a vehicle identity.",
    "Box size or position changes are image geometry only: they do not establish speed, braking or a lane change.",
    "Frames the detector did not see are absent; nothing is interpolated.",
    "Human review is required; no fault determination is made.",
)


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def detection_rows(analysis: VideoAnalysis) -> list[dict[str, Any]]:
    """One row per (frame, track) detection, ordered by frame index then track ID."""
    rows = []
    for track in analysis.tracks:
        for det in track.detections:
            rows.append({
                "frame_index": det.frame_index,
                "timestamp_seconds": round(det.timestamp_seconds, 6),
                "track_id": track.track_id,
                "label": det.label,
                "confidence": round(det.confidence, 4),
                "x1": round(det.box.x1, 2), "y1": round(det.box.y1, 2),
                "x2": round(det.box.x2, 2), "y2": round(det.box.y2, 2),
            })
    rows.sort(key=lambda r: (r["frame_index"], r["track_id"]))
    return rows


def detections_document(analysis: VideoAnalysis, detector_name: str, *, is_mock: bool,
                        config: VisionConfig | None = None, weights_path: Path | str | None = None,
                        video_path: Path | str | None = None, device: str | None = None) -> dict[str, Any]:
    """Full export: provenance, video metadata, track summaries, event estimate and rows.
    `is_mock` must be stated explicitly by the caller; mock output is labelled as such."""
    summary = analysis.to_dict()
    weights = None if weights_path is None else Path(weights_path)
    provenance: dict[str, Any] = {
        "adapter": "witness-vision-mock" if is_mock else "witness-vision",
        "version": __version__,
        "is_mock": is_mock,
        "detector": detector_name,
        "weights": None if weights is None else weights.name,
        "weights_sha256": sha256_file(weights) if weights is not None and weights.is_file() else None,
        "video_uri": analysis.meta.uri,
        "video_sha256": sha256_file(video_path) if video_path is not None and Path(video_path).is_file() else None,
        "source_fps": analysis.meta.fps,
        "sample_fps": analysis.sample_fps,
        "device": device or os.getenv("WITNESS_YOLO_DEVICE") or "default",
        "config": asdict(config or VisionConfig()),
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    notes = list(NOTES)
    if is_mock:
        notes.insert(0, "SYNTHETIC, no footage analyzed.")
    return {
        "schema": SCHEMA,
        "provenance": provenance,
        "human_review_required": True,
        "notes": notes,
        "video": {key: summary[key] for key in ("video_uri", "fps", "frame_count", "duration_seconds", "resolution",
                                                 "sample_fps", "sampled_frame_count", "missing_frames",
                                                 "low_confidence_dropped")},
        "tracks": summary["tracks"],
        "event": summary["event"],
        "signals": summary["signals"],
        "warnings": summary["warnings"],
        "detections": detection_rows(analysis),
    }


def write_detections(document: dict[str, Any], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n")
    return path


def write_detections_csv(rows: list[dict[str, Any]], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path
