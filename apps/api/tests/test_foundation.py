import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from witness_api.main import ROOT, create_app
from witness_api.storage import JsonStorage
from witness_contracts import (Incident, DriverStatement, AtomicClaim, EvidenceWindow,
    DetectorObservation, ClaimVerdict, IncidentReport, AnalysisStatus)

@pytest.fixture
def client(tmp_path):
    return TestClient(create_app(JsonStorage(ROOT / "data/demo/incident.json", tmp_path)))

def test_api_lifecycle_and_determinism(client):
    assert client.get("/health").json() == {"status": "ok", "analysis_mode": "mock"}
    incident = client.get("/incidents/demo-001")
    assert incident.status_code == 200
    assert len(incident.json()["statements"]) == 2
    assert client.get("/incidents/demo-001/results").status_code == 409
    response = client.post("/incidents/demo-001/analyze")
    assert response.status_code == 200
    assert response.json()["state"] == "completed"
    first = client.get("/incidents/demo-001/results")
    assert first.status_code == 200
    report = IncidentReport.model_validate(first.json())
    assert {v.verdict.value for v in report.verdicts} == {"supported", "contradicted", "not_visible"}
    assert report.human_review_required and report.is_mock
    signal = next(c for c in report.claims if c.category == "traffic_signal")
    assert next(v for v in report.verdicts if v.claim_id == signal.id).verdict == "not_visible"
    assert all(v.evidence[0].start_seconds == 8 for v in report.verdicts)
    assert client.post("/incidents/demo-001/analyze").status_code == 200
    assert client.get("/incidents/demo-001/results").json() == first.json()

@pytest.mark.parametrize("method,path", [("get", ""), ("post", "/analyze"), ("get", "/results")])
def test_unknown(client, method, path):
    assert getattr(client, method)("/incidents/missing" + path).status_code == 404

def test_cors(client):
    headers = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST"}
    response = client.options("/incidents/demo-001/analyze", headers=headers)
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "https://untrusted.example"
    assert "access-control-allow-origin" not in client.options("/incidents/demo-001/analyze", headers=headers).headers

def example(name):
    return json.loads((ROOT / f"packages/contracts/examples/{name}.json").read_text())

@pytest.mark.parametrize("model", [Incident, DriverStatement, AtomicClaim, EvidenceWindow,
    DetectorObservation, ClaimVerdict, IncidentReport, AnalysisStatus])
def test_examples_and_schema_exports(model):
    model.model_validate(example(model.__name__))
    schema = json.loads((ROOT / f"packages/contracts/schemas/{model.__name__}.schema.json").read_text())
    assert schema == model.model_json_schema()

@pytest.mark.parametrize("start,end", [(-1, 2), (3, 2), (2, 2), (0, float("inf"))])
def test_bad_windows(start, end):
    data = example("EvidenceWindow")
    data.update(start_seconds=start, end_seconds=end)
    with pytest.raises(ValidationError):
        EvidenceWindow.model_validate(data)

@pytest.mark.parametrize("change", [{"confidence": 1.1}, {"verdict": "unknown"}, {"evidence": []}, {"uncertainty": ""}])
def test_bad_verdicts(change):
    data = example("ClaimVerdict")
    data.update(change)
    with pytest.raises(ValidationError):
        ClaimVerdict.model_validate(data)

def test_absence_is_not_contradiction():
    data = example("ClaimVerdict")
    data["evidence"][0]["visibility"] = "not_visible"
    for verdict in ("supported", "contradicted"):
        data["verdict"] = verdict
        with pytest.raises(ValidationError):
            ClaimVerdict.model_validate(data)
    data["verdict"] = "not_visible"
    ClaimVerdict.model_validate(data)

@pytest.mark.parametrize("mutation", ["reference", "duplicate", "mock", "review", "fault"])
def test_report_boundaries(mutation):
    data = example("IncidentReport")
    if mutation == "reference": data["verdicts"][0]["claim_id"] = "missing"
    if mutation == "duplicate": data["claims"].append(data["claims"][0])
    if mutation == "mock": data["verdicts"][0]["provenance"]["is_mock"] = False
    if mutation == "review": data["human_review_required"] = False
    if mutation == "fault": data["legal_fault_determination"] = "driver-b"
    with pytest.raises(ValidationError):
        IncidentReport.model_validate(data)

def test_persistence_and_failure(tmp_path):
    store = JsonStorage(ROOT / "data/demo/incident.json", tmp_path)
    client = TestClient(create_app(store))
    assert client.post("/incidents/demo-001/analyze").status_code == 200
    old = TestClient(create_app(store)).get("/incidents/demo-001/results").json()
    class BrokenPipeline:
        def analyze(self, incident):
            raise RuntimeError("private provider details")
    failed = TestClient(create_app(store, BrokenPipeline()))
    response = failed.post("/incidents/demo-001/analyze")
    assert response.status_code == 500
    assert "private" not in response.text
    assert failed.get("/incidents/demo-001/results").json() == old
    with pytest.raises(ValueError):
        store.get_report("../escape")

def test_openapi_export():
    assert json.loads((ROOT / "packages/contracts/openapi.json").read_text()) == create_app().openapi()

@pytest.mark.parametrize("invalid", ["statement", "duration", "video"])
def test_pipeline_rejects_invalid_adapter_evidence(invalid):
    from witness_api.mock import MockAdapters
    from witness_api.pipeline import Pipeline
    class InvalidAdapter(MockAdapters):
        def extract(self, incident):
            claims = super().extract(incident)
            if invalid == "statement":
                claims[0] = claims[0].model_copy(update={"statement_id": "missing"})
            return claims
        def localize(self, incident, claim):
            windows = super().localize(incident, claim)
            if invalid == "duration":
                windows[0] = windows[0].model_copy(update={"end_seconds": 100})
            if invalid == "video":
                windows[0] = windows[0].model_copy(update={"video_uri": "other-video"})
            return windows
    mock = InvalidAdapter()
    incident = Incident.model_validate(example("Incident"))
    with pytest.raises(ValueError):
        Pipeline(mock, mock, mock, mock, mock, mock).analyze(incident)
