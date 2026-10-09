"""Auth failure, API errors, and mock separation for VSS client."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vss_client import (
    VSSAPIError,
    VSSAuthError,
    VSSClient,
    prefer_incident_hit,
    public_evidence_row,
    summarize_detections,
)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text or ("" if payload is None else str(payload))
        self.headers = {}

    def close(self):
        self.closed = True

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def test_login_auth_failure_401():
    session = MagicMock()
    session.post.return_value = FakeResponse(401, text="unauthorized")
    client = VSSClient(
        base_url="http://vss.example",
        username="u",
        password="p",
        session=session,
    )
    with pytest.raises(VSSAuthError):
        client.login(force=True)


def test_login_success_caches_token():
    session = MagicMock()
    session.post.return_value = FakeResponse(200, {"access_token": "tok123", "token_type": "bearer"})
    client = VSSClient("http://vss.example", "u", "p", session=session)
    assert client.login(force=True) == "tok123"
    assert client.login() == "tok123"
    assert session.post.call_count == 1


def test_search_api_error():
    session = MagicMock()
    session.post.side_effect = [
        FakeResponse(200, {"access_token": "t"}),
        FakeResponse(500, text="boom"),
    ]
    # first post is login; request uses session.request for search
    session.request.return_value = FakeResponse(500, text="boom")
    client = VSSClient("http://vss.example", "u", "p", session=session)
    with pytest.raises(VSSAPIError) as ei:
        client.search("q")
    assert ei.value.status_code == 500


def test_prefer_incident_hit_and_public_row():
    source = "s3://bucket/segments/target.mp4"
    rows = [
        {"source": "s3://other", "filename": "other.mp4", "reasoning_content": "x"},
        {"source": source, "filename": "target.mp4", "reasoning_content": "y", "segment_start_sec": 25},
    ]
    hit = prefer_incident_hit(rows, source)
    assert hit["filename"] == "target.mp4"
    pub = public_evidence_row(hit, source_fallback=source)
    assert pub["found"] is True
    assert pub["reasoning_content"] == "y"
    assert "provenance" in pub


def test_missing_evidence_public_row():
    pub = public_evidence_row(None, source_fallback="s3://x")
    assert pub["found"] is False
    assert pub["reasoning_content"] is None


def test_summarize_detections_missing():
    s = summarize_detections(None)
    assert s["available"] is False


def test_summarize_detections_present():
    s = summarize_detections(
        {
            "detection_count": 10,
            "object_classes": ["car"],
            "object_counts": {"car": 2},
            "fps": 30,
            "frame_count": 150,
            "max_detection_conf": 0.9,
            "frames": [{"detections": [{"label": "car"}, {"label": "person"}]}],
        }
    )
    assert s["available"] is True
    assert "car" in s["sample_frame0_labels"]


def test_unconfigured_client():
    client = VSSClient(base_url="", username="", password="")
    assert client.configured() is False
    with pytest.raises(VSSAuthError):
        client.login()


def test_request_exception_on_login():
    session = MagicMock()
    session.post.side_effect = requests.RequestException("network down")
    client = VSSClient("http://vss.example", "u", "p", session=session)
    with pytest.raises(VSSAuthError):
        client.login(force=True)
