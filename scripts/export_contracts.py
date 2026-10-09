"""Run from repository root after installing the editable Python package."""
import json
from pathlib import Path
from witness_contracts import (Incident, DriverStatement, AtomicClaim, EvidenceWindow,
    DetectorObservation, ClaimVerdict, IncidentReport, AnalysisStatus)
from witness_api.main import create_app, ROOT
from witness_api.config import configured_pipeline
from witness_api.pipeline import Pipeline

def export():
    base = ROOT / "packages/contracts"
    for model in (Incident, DriverStatement, AtomicClaim, EvidenceWindow, DetectorObservation,
                  ClaimVerdict, IncidentReport, AnalysisStatus):
        (base / "schemas" / f"{model.__name__}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
    incident = Incident.model_validate_json((ROOT / "data/demo/incident.json").read_text())
    report = configured_pipeline("mock").analyze(incident)
    examples = {"Incident": incident, "DriverStatement": incident.statements[0], "AtomicClaim": report.claims[0],
        "EvidenceWindow": report.verdicts[0].evidence[0], "DetectorObservation": report.observations[0],
        "ClaimVerdict": report.verdicts[0], "IncidentReport": report,
        "AnalysisStatus": AnalysisStatus(incident_id=incident.id, state="completed", is_mock=True, detail="Mock analysis complete.")}
    for name, value in examples.items():
        (base / "examples" / f"{name}.json").write_text(value.model_dump_json(indent=2) + "\n")
    (base / "openapi.json").write_text(json.dumps(create_app().openapi(), indent=2) + "\n")

if __name__ == "__main__":
    export()
