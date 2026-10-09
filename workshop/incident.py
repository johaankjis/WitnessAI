"""Fixed workshop incident + illustrative team-authored statements.

These statements are fictional teaching fixtures for the Builders Challenge.
They are NOT real driver claims, accident reports, or liability assertions.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

# Stable VAST identifiers for team-6 Toronto pie_cam-3 segment (discovery-confirmed).
INCIDENT: dict[str, Any] = {
    "id": "witness-workshop-toronto-pie-0017-seg6",
    "title": "Toronto intersection review (workshop MVP)",
    "disclaimer": (
        "ILLUSTRATIVE ONLY — statements below were authored by the Witness team for "
        "workshop demonstration. They are not real driver statements, insurance claims, "
        "or findings of fault. Footage shows an ordinary intersection scene; it is not "
        "labeled or proven as a collision. Human review is required. No binding liability "
        "conclusion is produced."
    ),
    "footage_permitted": True,
    "footage_notes": (
        "Uses pre-indexed workshop corpus already available to team-6 (PIE Toronto live "
        "driving). No external Nexar upload. No re-ingestion."
    ),
    "team_namespace": "team-6",
    "location": "toronto",
    "camera_id": "pie_cam-3",
    "capture_type": "streets",
    "segment_filename": "20261001_062538_set02_video_chunk_0017_segment_006_of_006.mp4",
    "original_video_basename": "20261001_062538_set02_video_chunk_0017.mp4",
    "source": (
        "s3://team-6-vss-chunks-segments/segments/"
        "20261001_062538_set02_video_chunk_0017_segment_006_of_006.mp4"
    ),
    "original_video": (
        "s3://team-6-vss-chunks/team-6/20261001_062538_set02_video_chunk_0017.mp4"
    ),
    "evidence_window_sec": {"start": 25.0, "end": 30.0},
    "segment_number": 6,
    "total_segments": 6,
    "media_proxy_path": "/api/media/stream",
}

# Atomic claims with conservative observation metadata.
# verdict_mode:
#   observable — may be Supported/Contradicted only via explicit Cosmos cues + optional YOLO
#   interpretive — always Not visible / Not established (needs human review)
STATEMENTS: list[dict[str, Any]] = [
    {
        "id": "driver_a",
        "label": "Driver A",
        "illustrative": True,
        "text": (
            "I stopped at the crosswalk and waited for pedestrians to clear before "
            "proceeding through the intersection. Traffic lights were controlling the "
            "crossing and I had already yielded."
        ),
        "claims": [
            {
                "id": "a1",
                "text": "A vehicle was stopped at the intersection / crosswalk.",
                "verdict_mode": "observable",
                "search_query": (
                    "black car stopped at intersection waiting for pedestrians crosswalk"
                ),
                "support_cues": [
                    "stopped",
                    "waiting",
                    "wait for",
                    "yielding",
                    "stopped at the intersection",
                ],
                "contradict_cues": [
                    "no vehicles",
                    "no cars",
                    "empty intersection",
                    "no car is stopped",
                ],
                "object_hints": ["car"],
                "seek_offset_sec": 0.5,
            },
            {
                "id": "a2",
                "text": "Pedestrians were crossing the street in the marked crosswalk.",
                "verdict_mode": "observable",
                "search_query": "pedestrians crossing marked crosswalk intersection",
                "support_cues": [
                    "pedestrians are crossing",
                    "pedestrian",
                    "crossing the street",
                    "crosswalk",
                ],
                "contradict_cues": [
                    "no pedestrians",
                    "no people",
                    "empty sidewalk",
                    "deserted",
                ],
                "object_hints": ["person"],
                "seek_offset_sec": 1.0,
            },
            {
                "id": "a3",
                "text": "Driver A had the right of way / a protecting green signal.",
                "verdict_mode": "interpretive",
                "search_query": "traffic light signal green red intersection",
                "support_cues": [],
                "contradict_cues": [],
                "object_hints": ["traffic light"],
                "seek_offset_sec": 2.0,
                "abstain_reason": (
                    "Right-of-way and signal phase for a specific driver require "
                    "interpretation beyond reliable segment observations."
                ),
            },
        ],
    },
    {
        "id": "driver_b",
        "label": "Driver B",
        "illustrative": True,
        "text": (
            "Pedestrians suddenly entered the roadway while I was already moving through "
            "the intersection, and there were no stopped vehicles waiting at the crosswalk."
        ),
        "claims": [
            {
                "id": "b1",
                "text": "Pedestrians suddenly entered the roadway without warning.",
                "verdict_mode": "interpretive",
                "search_query": "pedestrians entering roadway suddenly unexpected",
                "support_cues": [],
                "contradict_cues": [],
                "object_hints": ["person"],
                "seek_offset_sec": 1.5,
                "abstain_reason": (
                    "Suddenness and warning are temporal/intent judgments not reliably "
                    "established from a short Cosmos caption."
                ),
            },
            {
                "id": "b2",
                "text": "There were no stopped vehicles waiting at the crosswalk.",
                "verdict_mode": "observable",
                "search_query": "no stopped vehicles at crosswalk empty waiting cars",
                "support_cues": [
                    "no vehicles",
                    "no cars",
                    "no car is stopped",
                    "empty intersection",
                ],
                "contradict_cues": [
                    "car is stopped",
                    "black car is stopped",
                    "stopped at the intersection",
                    "waiting for the pedestrians",
                    "vehicle is stopped",
                ],
                "object_hints": ["car"],
                "seek_offset_sec": 0.8,
            },
            {
                "id": "b3",
                "text": "Other vehicles were moving through the intersection.",
                "verdict_mode": "observable",
                "search_query": "car moving through intersection traffic flowing",
                "support_cues": [
                    "moving through",
                    "moving",
                    "drives through",
                    "traveling",
                    "in the background, moving",
                ],
                "contradict_cues": [
                    "all vehicles stopped",
                    "no moving vehicles",
                    "completely stopped traffic",
                ],
                "object_hints": ["car"],
                "seek_offset_sec": 2.5,
            },
        ],
    },
]


def get_incident_bundle() -> dict[str, Any]:
    return {
        "incident": deepcopy(INCIDENT),
        "statements": deepcopy(STATEMENTS),
    }


def all_claims() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for stmt in STATEMENTS:
        for claim in stmt["claims"]:
            row = deepcopy(claim)
            row["statement_id"] = stmt["id"]
            row["statement_label"] = stmt["label"]
            out.append(row)
    return out


def get_claim(claim_id: str) -> dict[str, Any] | None:
    for claim in all_claims():
        if claim["id"] == claim_id:
            return claim
    return None
