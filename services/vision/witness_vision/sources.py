"""Frame sources. OpenCV is imported lazily so mock mode needs no video dependencies."""
from __future__ import annotations

import math
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol
from urllib.parse import unquote, urlparse

from .errors import OptionalDependencyError, UnsupportedVideoError, VideoDecodeError
from .types import Frame, VideoMeta

SUPPORTED_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"})


class FrameSource(Protocol):
    @property
    def meta(self) -> VideoMeta: ...

    @property
    def missing_frames(self) -> list[int]: ...

    @property
    def warnings(self) -> list[str]: ...

    def frames(self, sample_fps: float) -> Iterator[Frame]: ...


def sample_step(fps: float, sample_fps: float) -> int:
    """Every Nth source frame is sampled; the effective rate is fps / step."""
    if sample_fps <= 0:
        raise ValueError("sample_fps must be positive")
    return max(1, round(fps / sample_fps))


def resolve_video_path(video_uri: str, media_root: Path | None = None) -> Path:
    """Map an Incident.video_uri to a local file. Remote schemes need a separate media
    acquisition step (not part of TASK-002A) and are rejected rather than guessed at."""
    parsed = urlparse(video_uri)
    if parsed.scheme == "mock":
        raise UnsupportedVideoError("mock:// URIs have no footage; use MockVisionObserver")
    if parsed.scheme == "file":
        path = Path(unquote(parsed.path))
    elif parsed.scheme == "" or (len(parsed.scheme) == 1 and video_uri[1:3] in (":\\", ":/")):
        path = Path(video_uri)
        if not path.is_absolute() and media_root is not None:
            path = media_root / path
    else:
        raise UnsupportedVideoError(f"unsupported video URI scheme {parsed.scheme!r}; download to a local path first")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise UnsupportedVideoError(f"unsupported video container {path.suffix or '(none)'!r}")
    if not path.is_file():
        raise UnsupportedVideoError(f"video file not found: {path}")
    return path


def _cv2():
    try:
        import cv2
    except ImportError as exc:
        raise OptionalDependencyError("opencv-python-headless", "video") from exc
    return cv2


class OpenCVFrameSource:
    """Sequential decode with grab()/retrieve(): every frame is grabbed so source frame
    indices stay exact, but only sampled frames are decoded to pixels.

    Timestamps are frame_index / fps (constant-frame-rate assumption; container PTS from
    OpenCV is unreliable across backends). Failed grabs/retrieves are recorded as missing
    frames and never interpolated."""

    def __init__(self, path: Path, uri: str | None = None, max_consecutive_missing: int = 30):
        cv2 = _cv2()
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            raise UnsupportedVideoError(f"unsupported video container {path.suffix or '(none)'!r}")
        self._cap = cv2.VideoCapture(str(path))
        if not self._cap.isOpened():
            raise UnsupportedVideoError(f"OpenCV could not open {path.name}; codec or container unsupported")
        fps = float(self._cap.get(cv2.CAP_PROP_FPS) or 0)
        if not math.isfinite(fps) or fps <= 0 or fps > 1000:
            self._cap.release()
            raise UnsupportedVideoError(f"invalid or unknown frame rate ({fps}) in {path.name}")
        self._meta = VideoMeta(
            uri=uri or path.as_uri(), fps=fps,
            frame_count=max(0, int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)),
            width=int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0),
            height=int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0))
        self._missing: list[int] = []
        self._warnings: list[str] = []
        self._max_consecutive_missing = max_consecutive_missing

    @property
    def meta(self) -> VideoMeta:
        return self._meta

    @property
    def missing_frames(self) -> list[int]:
        return list(self._missing)

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def frames(self, sample_fps: float) -> Iterator[Frame]:
        step = sample_step(self._meta.fps, sample_fps)
        reported = self._meta.frame_count
        limit = reported if reported > 0 else 10**9
        consecutive = 0
        last_good = -1
        decoded = 0
        width, height = self._meta.width, self._meta.height
        try:
            for index in range(limit):
                if not self._cap.grab():
                    if reported <= 0:
                        break  # unknown length: first failure is end of stream
                    self._missing.append(index)
                    consecutive += 1
                    if consecutive > self._max_consecutive_missing:
                        break
                    continue
                consecutive = 0
                last_good = index
                if index % step:
                    continue
                ok, image = self._cap.retrieve()
                if not ok or image is None:
                    self._missing.append(index)
                    continue
                if not width or not height:
                    height, width = image.shape[:2]
                decoded += 1
                yield Frame(index=index, timestamp_seconds=index / self._meta.fps,
                            width=width, height=height, image=image)
        finally:
            self._cap.release()
        if decoded == 0:
            raise VideoDecodeError("no frames could be decoded")
        if reported <= 0 or last_good + 1 < reported:
            if reported > 0:
                self._warnings.append(f"stream ended at frame {last_good} of {reported} reported frames")
                # trailing failures past the true end of stream are truncation, not gaps
                self._missing = [i for i in self._missing if i <= last_good]
            self._meta = VideoMeta(self._meta.uri, self._meta.fps, last_good + 1, width, height)
        elif (width, height) != (self._meta.width, self._meta.height):
            self._meta = VideoMeta(self._meta.uri, self._meta.fps, self._meta.frame_count, width, height)
