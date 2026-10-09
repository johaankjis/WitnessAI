"""Verdict abstention and conservative mapping tests."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from verdicts import (
    VERDICT_CONTRADICTED,
    VERDICT_NOT_VISIBLE,
    VERDICT_SUPPORTED,
    map_claim_verdict,
    seek_time_for_claim,
)


OBSERVABLE = {
    "id": "t1",
    "verdict_mode": "observable",
    "support_cues": ["stopped at the intersection", "waiting"],
    "contradict_cues": ["no cars", "no vehicles"],
    "object_hints": ["car"],
    "seek_offset_sec": 1.0,
}

INTERPRETIVE = {
    "id": "t2",
    "verdict_mode": "interpretive",
    "support_cues": ["green light"],
    "contradict_cues": [],
    "object_hints": ["traffic light"],
    "abstain_reason": "Needs human interpretation.",
}


def test_missing_evidence_abstains():
    out = map_claim_verdict(OBSERVABLE, reasoning_content=None, evidence_missing=True)
    assert out["verdict"] == VERDICT_NOT_VISIBLE
    assert out["human_review_required"] is True


def test_interpretive_always_abstains_even_with_cues():
    out = map_claim_verdict(
        INTERPRETIVE,
        reasoning_content="The traffic light shows a green light for vehicles.",
        object_classes=["traffic light"],
        similarity_score=0.99,
        agent_answer="Driver had right of way.",
    )
    assert out["verdict"] == VERDICT_NOT_VISIBLE
    assert out["agent_answer_used_as_proof"] is False


def test_similarity_alone_does_not_support():
    out = map_claim_verdict(
        OBSERVABLE,
        reasoning_content="A sunny day on a city street with buildings nearby.",
        similarity_score=0.95,
        agent_answer="This strongly supports the claim.",
    )
    assert out["verdict"] == VERDICT_NOT_VISIBLE


def test_support_requires_explicit_cues():
    out = map_claim_verdict(
        OBSERVABLE,
        reasoning_content="A black car is stopped at the intersection, waiting for pedestrians.",
        object_classes=["car", "person"],
        similarity_score=0.1,
    )
    assert out["verdict"] == VERDICT_SUPPORTED
    assert "stopped at the intersection" in out["support_cue_hits"]


def test_contradiction_requires_oppose_cues():
    claim = {
        **OBSERVABLE,
        "id": "b2",
        "support_cues": ["no vehicles", "no cars"],
        "contradict_cues": ["stopped at the intersection", "waiting for the pedestrians"],
    }
    out = map_claim_verdict(
        claim,
        reasoning_content="A black car is stopped at the intersection, waiting for the pedestrians.",
        object_classes=["car"],
    )
    assert out["verdict"] == VERDICT_CONTRADICTED


def test_mixed_cues_abstain():
    claim = {
        **OBSERVABLE,
        "support_cues": ["waiting"],
        "contradict_cues": ["no cars"],
    }
    out = map_claim_verdict(
        claim,
        reasoning_content="A car is waiting. There are no cars on the side street.",
    )
    assert out["verdict"] == VERDICT_NOT_VISIBLE


def test_seek_time_clamped_to_window():
    t = seek_time_for_claim({"seek_offset_sec": 100}, {"start": 25.0, "end": 30.0})
    assert 0 <= t < 5.0
    t2 = seek_time_for_claim({"seek_offset_sec": 1.5}, {"start": 25.0, "end": 30.0})
    assert t2 == 1.5


def test_llm_never_marks_proof_flag():
    out = map_claim_verdict(
        OBSERVABLE,
        reasoning_content="A black car is stopped at the intersection, waiting.",
        agent_answer="Definitely supported.",
    )
    assert out["agent_answer_used_as_proof"] is False
    assert out["binding_liability_conclusion"] is False


def test_invalid_timestamps_rejected():
    import pytest
    for window in [{'start': 5, 'end': 4}, {'start': -1, 'end': 5},
                   {'start': 0, 'end': float('nan')}]:
        with pytest.raises(ValueError):
            seek_time_for_claim({}, window)
    with pytest.raises(ValueError):
        seek_time_for_claim({'seek_offset_sec': float('inf')}, {'start': 0, 'end': 5})
