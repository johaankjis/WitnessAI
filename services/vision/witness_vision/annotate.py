"""Event clip extraction and annotated visual evidence (requires the `video` extra).

Annotated clips contain only *sampled* frames, written at the sample rate, with the boxes
detected on exactly that frame. Boxes are never interpolated onto frames the detector did
not see. Every frame is stamped with its source frame index and timestamp."""
from __future__ import annotations

from pathlib import Path

from .errors import VideoDecodeError
from .sources import _cv2
from .types import Detection, VideoAnalysis

_COLOURS = {"traffic light": (0, 200, 255)}
_DEFAULT_COLOUR = (60, 220, 60)


def _open_writer(cv2, out_path: Path, fps: float, size: tuple[int, int]):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
    if not writer.isOpened():
        raise VideoDecodeError(f"could not open video writer for {out_path}")
    return writer


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
    writer = _open_writer(cv2, out_path, fps, (analysis.meta.width, analysis.meta.height))
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


def write_annotated_clip(video_path: Path, analysis: VideoAnalysis, start: float, end: float, out_path: Path) -> Path:
    cv2 = _cv2()
    by_frame: dict[int, list[tuple[int, Detection]]] = {}
    for track in analysis.tracks:
        for det in track.detections:
            by_frame.setdefault(det.frame_index, []).append((track.track_id, det))
    sampled = [f for f, t in zip(analysis.sampled_frames, analysis.sampled_timestamps) if start <= t <= end]
    if not sampled:
        raise VideoDecodeError("no sampled frames in clip range")
    wanted = set(sampled)
    event_frame = analysis.event.frame_index if analysis.event else None
    writer = _open_writer(cv2, out_path, analysis.sample_fps, (analysis.meta.width, analysis.meta.height))
    written = 0
    try:
        for index, image in _frames_in_range(cv2, video_path, sampled[0], sampled[-1]):
            if index not in wanted:
                continue
            for track_id, det in by_frame.get(index, []):
                colour = _COLOURS.get(det.label, _DEFAULT_COLOUR)
                b = det.box
                cv2.rectangle(image, (int(b.x1), int(b.y1)), (int(b.x2), int(b.y2)), colour, 2)
                cv2.putText(image, f"#{track_id} {det.label} {det.confidence:.2f}", (int(b.x1), max(12, int(b.y1) - 4)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)
            header = f"t={index / analysis.meta.fps:.2f}s frame={index}" + ("  EVENT" if index == event_frame else "")
            cv2.putText(image, header, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
            cv2.putText(image, "detector overlay - human review required", (8, analysis.meta.height - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1, cv2.LINE_AA)
            writer.write(image)
            written += 1
    finally:
        writer.release()
    if not written:
        raise VideoDecodeError("no frames decoded in clip range")
    return out_path
