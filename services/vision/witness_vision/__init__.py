"""Witness vision engine: frame sampling, vehicle detection/tracking and detector
observations for the shared contracts. Heavy dependencies (OpenCV, Ultralytics, Weave)
are optional and imported lazily; mock mode needs none of them."""
__version__ = "0.1.0"

from .analysis import analyze_video  # noqa: E402
from .config import VisionConfig  # noqa: E402
from .errors import (  # noqa: E402
    MockInputError,
    OptionalDependencyError,
    UnsupportedVideoError,
    VideoDecodeError,
    VisionError,
)

__all__ = ["MockInputError", "OptionalDependencyError", "UnsupportedVideoError", "VideoDecodeError",
           "VisionConfig", "VisionError", "__version__", "analyze_video"]
