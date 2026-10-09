"""Deterministic synthetic teaching data. No network, footage or inference."""
from copy import deepcopy
from typing import Any

from vss_client import VSSAPIError

LABEL = "SYNTHETIC DEVELOPMENT FIXTURE — no footage analyzed; not independent corroboration."
SOURCE = "fixture://intersection/segment-006"
VIDEO = "fixture://intersection/parent"


class FixtureClient:
    mode = "fixture"

    def configured(self) -> bool:
        return True

    def segment_metadata(self, source: str) -> dict[str, Any]:
        if source != SOURCE:
            raise VSSAPIError("Unknown fixture source", 404)
        return {
            "source": SOURCE, "original_video": VIDEO, "filename": "fixture-segment",
            "synthetic": True, "segment_start_sec": 25.0, "segment_end_sec": 30.0,
            "duration": 5.0, "segment_number": 6,
            "reasoning_content": LABEL + " A black car is stopped at the intersection, "
            "waiting for the pedestrians. Pedestrians are crossing the street in a marked "
            "crosswalk. Another car is moving through the intersection.",
            "object_classes": ["car", "person"], "object_counts": {"car": 2, "person": 3},
        }

    def search(self, query: str, **kwargs: Any) -> dict[str, Any]:
        return {"synthetic": True, "results": [self.segment_metadata(SOURCE)], "total": 1,
                "llm_synthesis": {"response": LABEL + " Search fixture; query is not analyzed."}}

    def segment_detections(self, source: str) -> dict[str, Any]:
        self.segment_metadata(source)
        return deepcopy({"synthetic": True, "source": SOURCE, "detection_count": 5,
                         "object_classes": ["car", "person"],
                         "object_counts": {"car": 2, "person": 3}, "fps": 30,
                         "frame_count": 150, "frames": [{"detections": [{"label": "car"}]}]})

    def agent_ask_scoped(self, question: str, original_video: str, top_k: int = 8) -> dict[str, Any]:
        if original_video != VIDEO:
            raise VSSAPIError("Unknown fixture video scope", 404)
        return {"synthetic": True, "original_video": VIDEO,
                "answer": LABEL + " Scoped Q&A fixture; no question was analyzed. Human review required."}

    def open_stream(self, source: str, range_header: str | None = None) -> Any:
        raise VSSAPIError("Synthetic fixtures have no video footage", 404)
