"""Conservative claim → verdict mapping.

Rules (MVP):
- Similarity score alone never yields Supported or Contradicted.
- An LLM / agent answer alone never yields Supported or Contradicted.
- Interpretive claims always abstain (Not visible / Not established).
- Observable support requires explicit cue overlap in Cosmos reasoning_content
  (case-insensitive substring). YOLO object_hints are corroborative only.
- Contradiction requires explicit oppose cues in reasoning_content.
- Missing / empty evidence → Not visible.
- Human review is always required.
"""

from __future__ import annotations

from typing import Any
import math

VERDICT_SUPPORTED = "supported"
VERDICT_CONTRADICTED = "contradicted"
VERDICT_NOT_VISIBLE = "not_visible"

LABELS = {
    VERDICT_SUPPORTED: "Supported",
    VERDICT_CONTRADICTED: "Contradicted",
    VERDICT_NOT_VISIBLE: "Not visible / Not established",
}


def _norm(text: str | None) -> str:
    return (text or "").strip().lower()


def _cue_hit(text: str, cues: list[str]) -> list[str]:
    hits: list[str] = []
    for cue in cues or []:
        c = _norm(cue)
        if c and c in text:
            hits.append(cue)
    return hits


def _object_present(object_classes: Any, hints: list[str]) -> list[str]:
    if not hints:
        return []
    if isinstance(object_classes, str):
        classes = {c.strip().lower() for c in object_classes.split(",") if c.strip()}
    elif isinstance(object_classes, (list, tuple, set)):
        classes = {str(c).strip().lower() for c in object_classes}
    elif isinstance(object_classes, dict):
        classes = {str(k).strip().lower() for k in object_classes.keys()}
    else:
        classes = set()
    return [h for h in hints if h.lower() in classes]


def map_claim_verdict(
    claim: dict[str, Any],
    *,
    reasoning_content: str | None,
    object_classes: Any = None,
    object_counts: Any = None,
    similarity_score: float | None = None,
    agent_answer: str | None = None,
    evidence_missing: bool = False,
) -> dict[str, Any]:
    """Return a provenance-preserving verdict record."""
    mode = claim.get("verdict_mode") or "interpretive"
    reasoning = _norm(reasoning_content)
    support_hits = _cue_hit(reasoning, claim.get("support_cues") or [])
    contradict_hits = _cue_hit(reasoning, claim.get("contradict_cues") or [])
    obj_hits = _object_present(object_classes or object_counts, claim.get("object_hints") or [])

    base = {
        "claim_id": claim.get("id"),
        "verdict_mode": mode,
        "human_review_required": True,
        "binding_liability_conclusion": False,
        "similarity_score": similarity_score,
        "agent_answer_advisory_only": True,
        "agent_answer_used_as_proof": False,
        "support_cue_hits": support_hits,
        "contradict_cue_hits": contradict_hits,
        "object_hint_hits": obj_hits,
        "provenance": {
            "cosmos_reasoning_used": bool(reasoning),
            "yolo_objects_used": bool(obj_hits),
            "similarity_not_sufficient": True,
            "llm_not_sufficient": True,
        },
    }

    if evidence_missing or not reasoning:
        return {
            **base,
            "verdict": VERDICT_NOT_VISIBLE,
            "verdict_label": LABELS[VERDICT_NOT_VISIBLE],
            "rationale": (
                "No usable Cosmos segment description was available for this claim. "
                "Abstaining pending human review."
            ),
        }

    if mode == "interpretive":
        return {
            **base,
            "verdict": VERDICT_NOT_VISIBLE,
            "verdict_label": LABELS[VERDICT_NOT_VISIBLE],
            "rationale": claim.get("abstain_reason")
            or (
                "Claim requires interpretation beyond reliable observations in the "
                "indexed segment. Marked Not visible / Not established for human review."
            ),
            "advisory_agent_note": (agent_answer or None),
        }

    # Observable path — cues required; similarity/agent never decide alone.
    if contradict_hits and not support_hits:
        rationale = (
            "Cosmos reasoning contains explicit cues opposing the claim "
            f"({', '.join(contradict_hits)}). Similarity={similarity_score!r} was "
            "not used as proof. Human review still required."
        )
        if obj_hits:
            rationale += f" YOLO classes present as context only: {', '.join(obj_hits)}."
        return {
            **base,
            "verdict": VERDICT_CONTRADICTED,
            "verdict_label": LABELS[VERDICT_CONTRADICTED],
            "rationale": rationale,
            "advisory_agent_note": (agent_answer or None),
        }

    if support_hits:
        # If both support and contradict cues fire, abstain rather than force a side.
        if contradict_hits:
            return {
                **base,
                "verdict": VERDICT_NOT_VISIBLE,
                "verdict_label": LABELS[VERDICT_NOT_VISIBLE],
                "rationale": (
                    "Both supporting and opposing cues appear in Cosmos reasoning "
                    f"(support={support_hits}, contradict={contradict_hits}). "
                    "Abstaining for human review."
                ),
                "advisory_agent_note": (agent_answer or None),
            }
        rationale = (
            "Cosmos reasoning contains explicit observational cues matching the claim "
            f"({', '.join(support_hits)}). Semantic similarity alone was not treated as "
            f"proof (score={similarity_score!r})."
        )
        if obj_hits:
            rationale += (
                f" YOLO object hints corroborate presence only: {', '.join(obj_hits)}."
            )
        else:
            rationale += " YOLO object hints were absent or unused for the decision."
        return {
            **base,
            "verdict": VERDICT_SUPPORTED,
            "verdict_label": LABELS[VERDICT_SUPPORTED],
            "rationale": rationale,
            "advisory_agent_note": (agent_answer or None),
        }

    # Related caption / objects without explicit cue → abstain
    return {
        **base,
        "verdict": VERDICT_NOT_VISIBLE,
        "verdict_label": LABELS[VERDICT_NOT_VISIBLE],
        "rationale": (
            "Retrieved segment text did not contain explicit support or contradiction "
            "cues for this claim. A semantically similar caption or YOLO co-occurrence "
            "is not sufficient. Not visible / Not established — human review required."
        ),
        "advisory_agent_note": (agent_answer or None),
    }


def seek_time_for_claim(claim: dict[str, Any], evidence_window: dict[str, float]) -> float:
    """Return segment-relative seconds; caller adds window start for parent time."""
    start = float(evidence_window.get("start", 0.0))
    end = float(evidence_window.get("end", start + 5.0))
    offset = float(claim.get("seek_offset_sec") or 0.0)
    if not all(math.isfinite(v) for v in (start, end, offset)) or start < 0 or end <= start:
        raise ValueError("Invalid evidence window or seek offset")
    # Segment file is the 5s clip; player loads the segment, so seek is relative 0..(end-start)
    duration = end - start
    rel = min(max(offset, 0.0), max(0.0, duration - 0.05))
    return round(rel, 3)
