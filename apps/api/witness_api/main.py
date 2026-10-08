import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from witness_contracts import Incident, IncidentReport, AnalysisStatus
from .interfaces import Storage
from .config import configured_pipeline
from .jobs import Jobs, QueueFull, AnalysisRunner
from .storage import JsonStorage

ROOT = Path(__file__).resolve().parents[3]
logger = logging.getLogger(__name__)

def create_app(storage: Storage | None = None, pipeline: AnalysisRunner | None = None) -> FastAPI:
    mode = os.getenv("WITNESS_ANALYSIS_MODE", "mock")
    if mode not in ("mock", "real"):
        raise ValueError("WITNESS_ANALYSIS_MODE must be mock or real")
    @asynccontextmanager
    async def lifespan(app):
        yield
        if jobs is not None:
            jobs.close()
    app = FastAPI(lifespan=lifespan, title="Witness TASK-001", version="0.1.0", description=("Synthetic mock analysis only; human review required." if mode == "mock" else
        "Provider-backed draft analysis; human review required. No fault determination."))
    app.add_middleware(CORSMiddleware,
        allow_origins=os.getenv("WITNESS_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","),
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"], allow_credentials=False)
    store = storage if storage is not None else JsonStorage(Path(os.getenv("WITNESS_INCIDENT_PATH", str(ROOT / "data/demo/incident.json"))), Path(os.getenv("WITNESS_DATA_DIR", str(ROOT / "data/local"))))
    runner = pipeline if pipeline is not None else configured_pipeline(mode)
    jobs = Jobs(runner, store) if mode == "real" else None
    app.state.jobs = jobs

    def incident_or_404(incident_id: str) -> Incident:
        incident = store.get_incident(incident_id)
        if incident is None:
            raise HTTPException(404, "Incident not found")
        return incident

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "analysis_mode": mode}

    @app.get("/incidents/{incident_id}", response_model=Incident)
    def get_incident(incident_id: str):
        return incident_or_404(incident_id)

    @app.post("/incidents/{incident_id}/analyze", response_model=AnalysisStatus)
    def analyze(incident_id: str):
        incident = incident_or_404(incident_id)
        if jobs is not None:
            try:
                return jobs.submit(incident)
            except QueueFull:
                raise HTTPException(503, "Analysis queue is full; retry later") from None
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
