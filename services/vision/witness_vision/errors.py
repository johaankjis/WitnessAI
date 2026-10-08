"""Typed failures. Vision never converts a failure into an empty "successful" analysis."""


class VisionError(Exception):
    """Base class for all vision pipeline failures."""


class OptionalDependencyError(VisionError):
    """An optional dependency (OpenCV, Ultralytics, Weave) is required but not installed."""

    def __init__(self, package: str, extra: str):
        super().__init__(f"{package} is not installed; install with `pip install -e 'services/vision[{extra}]'`")
        self.package = package
        self.extra = extra


class UnsupportedVideoError(VisionError):
    """The video URI scheme, container or stream parameters are not supported."""


class VideoDecodeError(VisionError):
    """The video could be opened but too few frames decoded to analyze."""


class MockInputError(VisionError):
    """Mock and real data were mixed (a real adapter got a mock incident or vice versa)."""
