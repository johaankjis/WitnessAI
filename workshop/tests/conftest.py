"""All workshop tests are offline, including tests of the real transport adapter."""
import os
import sys
from pathlib import Path
import pytest
import requests

os.environ["WITNESS_WORKSHOP_MODE"] = "fixture"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Network forbidden in workshop tests")
    monkeypatch.setattr(requests.sessions.Session, "request", denied)
