"""Object detectors. Ultralytics is imported lazily; nothing downloads weights at import time."""
from __future__ import annotations

import os
from typing import Any, Protocol

from .errors import OptionalDependencyError
from .types import TRAFFIC_LIGHT, VEHICLE_CLASSES, Box, Detection, Frame

RELEVANT_CLASSES = VEHICLE_CLASSES | {TRAFFIC_LIGHT}
DEFAULT_WEIGHTS = "yolo11n.pt"


class Detector(Protocol):
    name: str

    def detect(self, frame: Frame) -> list[Detection]: ...


class UltralyticsDetector:
    """COCO-pretrained YOLO restricted to vehicles and traffic lights.

    Weights: `weights` argument, else WITNESS_YOLO_WEIGHTS, else yolo11n.pt. Ultralytics
    downloads named official weights on first *use* (network required); pass a local path
    to stay offline. `model` may be injected for tests."""

    def __init__(self, weights: str | None = None, device: str | None = None,
                 min_confidence: float = 0.25, model: Any = None):
        self.weights = weights or os.getenv("WITNESS_YOLO_WEIGHTS", DEFAULT_WEIGHTS)
        self.device = device or os.getenv("WITNESS_YOLO_DEVICE") or None
        self.min_confidence = min_confidence
        self._model = model
        self.name = f"ultralytics:{os.path.basename(self.weights)}"

    def _load(self) -> Any:
        if self._model is None:
            try:
                from ultralytics import YOLO
            except ImportError as exc:
                raise OptionalDependencyError("ultralytics", "yolo") from exc
            self._model = YOLO(self.weights)
        return self._model

    def detect(self, frame: Frame) -> list[Detection]:
        if frame.image is None:
            raise ValueError("UltralyticsDetector needs decoded pixels; synthetic frames have none")
        model = self._load()
        names: dict[int, str] = model.names
        class_ids = [i for i, n in names.items() if n in RELEVANT_CLASSES]
        kwargs: dict[str, Any] = {"conf": self.min_confidence, "classes": class_ids, "verbose": False}
        if self.device:
            kwargs["device"] = self.device
        result = model.predict(frame.image, **kwargs)[0]
        detections = []
        for xyxy, conf, cls in zip(result.boxes.xyxy.tolist(), result.boxes.conf.tolist(),
                                   result.boxes.cls.tolist(), strict=True):
            label = names[int(cls)]
            if label in RELEVANT_CLASSES:
                detections.append(Detection(frame.index, frame.timestamp_seconds, label,
                                            float(conf), Box(*map(float, xyxy))))
        return detections
