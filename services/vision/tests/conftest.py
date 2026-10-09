from __future__ import annotations

import pytest
from witness_contracts import AtomicClaim, Incident

from witness_vision import tracing


def make_incident(**overrides) -> Incident:
    data = {
        "id": "demo-001", "title": "Synthetic lane-change dispute", "video_uri": "mock://demo-001/no-video",
        "duration_seconds": 20.0, "is_mock": True,
        "statements": [
            {"id": "statement-a", "driver_id": "driver-a",
             "text": "Driver B moved into my lane. I braked. My traffic light was green."},
            {"id": "statement-b", "driver_id": "driver-b", "text": "I stayed in my lane. Driver A did not brake."},
        ],
    }
    data.update(overrides)
    return Incident.model_validate(data)


def make_claims() -> list[AtomicClaim]:
    rows = [
        ("c1", "statement-a", "Driver B moved into my lane.", "driver-b", "lane_change"),
        ("c2", "statement-a", "I braked.", "driver-a", "braking"),
        ("c3", "statement-a", "My traffic light was green.", "driver-a", "traffic_signal"),
        ("c4", "statement-b", "I stayed in my lane.", "driver-b", "lane_change"),
        ("c5", "statement-b", "Driver A did not brake.", "driver-a", "braking"),
        ("c6", "statement-b", "I signaled before turning.", "driver-b", "other"),
    ]
    return [AtomicClaim(id=i, statement_id=s, text=t, subject=u, category=c) for i, s, t, u, c in rows]


@pytest.fixture
def incident() -> Incident:
    return make_incident()


@pytest.fixture
def claims() -> list[AtomicClaim]:
    return make_claims()


@pytest.fixture(autouse=True)
def no_weave(monkeypatch):
    monkeypatch.delenv("WITNESS_WEAVE_PROJECT", raising=False)
    tracing.reset_for_tests()
    yield
    tracing.reset_for_tests()
