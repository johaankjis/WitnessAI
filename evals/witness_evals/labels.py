"""Labeled event times. Accepts the Nexar collision CSV layout (id, time_of_event,
time_of_alert, target) or any CSV with at least `id` and `time_of_event`."""
from __future__ import annotations

import csv
import math
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LabeledClip:
    id: str                       # kept as text: Nexar IDs are zero-padded ("00822")
    time_of_event: float | None   # seconds from video start; None for negatives/unlabeled
    time_of_alert: float | None = None
    target: int | None = None


def _number(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"invalid time {value!r}")
    return number


def load_labels(path: Path) -> list[LabeledClip]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not {"id", "time_of_event"} <= set(reader.fieldnames):
            raise ValueError(f"{path} needs 'id' and 'time_of_event' columns")
        clips = []
        seen: set[str] = set()
        for row in reader:
            clip_id = row["id"].strip()
            if not clip_id or clip_id in seen:
                raise ValueError(f"missing or duplicate id {clip_id!r} in {path}")
            seen.add(clip_id)
            target = row.get("target")
            clips.append(LabeledClip(clip_id, _number(row["time_of_event"]), _number(row.get("time_of_alert")),
                                     int(float(target)) if target not in (None, "") else None))
    return clips
