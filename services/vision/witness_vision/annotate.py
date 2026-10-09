"""Event clip extraction and annotated visual evidence (requires the `video` extra).

Annotated videos contain only *sampled* frames, written at the sample rate, with the boxes
detected on exactly that frame. Boxes are never interpolated onto frames the detector did
not see. Every frame is stamped with its source frame index and timestamp, and a footer
states that the overlay is a detector output requiring human review."""
from __future__ import annotations

import logging
from pathlib import Path

from .errors import VideoDecodeError
from .sources import _cv2
from .types import Detection, VideoAnalysis

logger = logging.getLogger(__name__)
_COLOURS = {"traffic light": (0, 200, 255)}
_DEFAULT_COLOUR = (60, 220, 60)
_EVENT_COLOUR = (0, 80, 255)
# avc1 (H.264) plays in browsers when the OpenCV build has an encoder; mp4v is the portable fallback.
CODECS = ("avc1", "mp4v")


def _open_writer(cv2, out_path: Path, fps: float, size: tuple[int, int]):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    for codec in CODECS:
        writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*codec), fps, size)
        if writer.isOpened():
            return writer, codec
        writer.release()
    raise VideoDecodeError(f"could not open video writer for {out_path}")


def _frames_in_range(cv2, video_path: Path, first: int, last: int):
    """Yield (index, image) for source frames first..last, reading sequentially so indices
    match the analysis exactly (frame seeking is inexact for many codecs)."""
    cap = cv2.VideoCapture(str(video_path))
    try:
        for index in range(last + 1):
            if not cap.grab():
                return
            if index >= first:
                ok, image = cap.retrieve()
                if ok and image is not None:
                    yield index, image
    finally:
        cap.release()


def extract_clip(video_path: Path, analysis: VideoAnalysis, start: float, end: float, out_path: Path) -> Path:
    """Copy source frames in [start, end] seconds unmodified, at the source frame rate."""
    cv2 = _cv2()
    fps = analysis.meta.fps
    first, last = int(round(start * fps)), min(int(round(end * fps)), analysis.meta.frame_count - 1)
    writer, _ = _open_writer(cv2, out_path, fps, (analysis.meta.width, analysis.meta.height))
    written = 0
    try:
        for _, image in _frames_in_range(cv2, video_path, first, last):
            writer.write(image)
            written += 1
    finally:
        writer.release()
    if not written:
        raise VideoDecodeError("no frames decoded in clip range")
    return out_path


def draw_overlay(cv2, image, index: int, analysis: VideoAnalysis, detections: list[tuple[int, Detection]],
                 caption: str) -> None:
    """Draw boxes, track IDs, scores and the frame/time stamp onto one sampled frame in place."""
    height = analysis.meta.height
    scale = max(0.45, min(1.0, height / 720 * 0.6))
    thickness = 1 if height < 480 else 2
    for track_id, det in detections:
        colour = _COLOURS.get(det.label, _DEFAULT_COLOUR)
        b = det.box
        cv2.rectangle(image, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), colour, thickness)
        cv2.putText(image, f"#{track_id} {det.label} {det.confidence:.2f}", (int(b.x1), max(12, int(b.y1) - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, scale * 0.75, colour, 1, cv2.LINE_AA)
    event = analysis.event
    is_event = event is not None and index == event.frame_index
    header = f"t={index / analysis.meta.fps:.2f}s frame={index}" + ("  EVENT (fastest box growth)" if is_event else "")
    cv2.putText(image, header, (8, int(22 * scale) + 4), cv2.FONT_HERSHEY_SIMPLEX, scale * 0.9,
                _EVENT_COLOUR if is_event else (255, 255, 255), 2, cv2.LINE_AA)
    footer = caption or "detector overlay - not a verdict - human review required"
    cv2.putText(image, footer, (8, height - 10), cv2.FONT_HERSHEY_SIMPLEX, scale * 0.75, (255, 255, 255), 1,
                cv2.LINE_AA)


def write_annotated_video(video_path: Path, analysis: VideoAnalysis, out_path: Path,
                          start: float | None = None, end: float | None = None, caption: str = "") -> Path:
    """Write the sampled frames in [start, end] (default: the whole analysed range) at the
    sample rate, each with the detections made on that exact frame. Returns out_path."""
    cv2 = _cv2()
    by_frame: dict[int, list[tuple[int, Detection]]] = {}
    for track in analysis.tracks:
        for det in track.detections:
            by_frame.setdefault(det.frame_index, []).append((track.track_id, det))
    lo = 0.0 if start is None else start
    hi = float("inf") if end is None else end
    sampled = [f for f, t in zip(analysis.sampled_frames, analysis.sampled_timestamps) if lo <= t <= hi]
    if not sampled:
        raise VideoDecodeError("no sampled frames in clip range")
    wanted = set(sampled)
    writer, codec = _open_writer(cv2, out_path, analysis.sample_fps, (analysis.meta.width, analysis.meta.height))
    written = 0
    try:
        for index, image in _frames_in_range(cv2, video_path, sampled[0], sampled[-1]):
            if index not in wanted:
                continue
            draw_overlay(cv2, image, index, analysis, by_frame.get(index, []), caption)
            writer.write(image)
            written += 1
    finally:
        writer.release()
    if not written:
        raise VideoDecodeError("no frames decoded in clip range")
    logger.info("annotated video %s: %d sampled frames at %g fps, codec %s",
                out_path, written, analysis.sample_fps, codec)
    return out_path


def write_annotated_clip(video_path: Path, analysis: VideoAnalysis, start: float, end: float, out_path: Path) -> Path:
    """Annotated clip of the sampled frames in [start, end] (typically the event window)."""
    return write_annotated_video(video_path, analysis, out_path, start, end)
