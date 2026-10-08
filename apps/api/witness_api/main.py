import logging
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from witness_contracts import Incident, IncidentReport, AnalysisStatus
from .interfaces import Storage
from .mock import MockAdapters
from .pipeline import Pipeline
from .storage import JsonStorage

ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)

def create_app(storage: Storage | None = None, pipeline: Pipeline | None = None) -> FastAPI:
    app = FastAPI(title="Witness TASK-001", version="0.1.0", description="Synthetic mock analysis only; human review required.")
    app.add_middleware(CORSMiddleware,
        allow_origins=os.getenv("WITNESS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=False)
    store = storage if storage is not None else JsonStorage(ROOT / "data/demo/incident.json", Path(os.getenv("WITNESS_DATA_DIR", str(ROOT / "data/local"))))
    mock = MockAdapters()
    runner = pipeline if pipeline is not None else Pipeline(mock, mock, mock, mock, mock, mock)

    def incident_or_404(incident_id: str) -> Incident:
        incident = store.get_incident(incident_id)
        if incident is None:
            raise HTTPException(404, "Incident not found")
        return incident

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "analysis_mode": "mock"}

    @app.get("/incidents/{incident_id}", response_model=Incident)
    def get_incident(incident_id: str):
        return incident_or_404(incident_id)

    @app.post("/incidents/{incident_id}/analyze", response_model=AnalysisStatus)
    def analyze(incident_id: str):
        incident = incident_or_404(incident_id)
        try:
            store.save_report(runner.analyze(incident))
        except Exception:
            logger.exception("Analysis failed for %s", incident_id)
            raise HTTPException(500, "Analysis failed; no new report committed") from None
        return AnalysisStatus(incident_id=incident_id, state="completed", is_mock=incident.is_mock,
                              detail="Synchronous mock analysis complete; retrieve /results.")

    @app.get("/incidents/{incident_id}/results", response_model=IncidentReport)
    def results(incident_id: str):
        incident_or_404(incident_id)
        report = store.get_report(incident_id)
        if report is None:
            raise HTTPException(409, "Analysis has not run; POST /analyze first")
        return report

    return app

app = create_app()
