import logging
import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from .media import LocalMedia
from .provider_io import ProviderError
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
    app = FastAPI(lifespan=lifespan, title="Witness", version="0.3.0", description=("Synthetic mock analysis only; human review required." if mode == "mock" else
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

    def saved_report(incident: Incident) -> IncidentReport | None:
        report = store.get_report(incident.id)
        if report is not None:
            windows = [e for v in report.verdicts for e in v.evidence]
            windows += [o.evidence for o in report.observations]
            if (report.incident_id != incident.id or report.is_mock != incident.is_mock
                    or any(w.video_uri != incident.video_uri or w.end_seconds > incident.duration_seconds
                           for w in windows)):
                raise HTTPException(409, "Saved report belongs to different source media; analyze this incident")
        return report

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

    @app.get("/incidents/{incident_id}/status", response_model=AnalysisStatus)
    def status(incident_id: str):
        incident = incident_or_404(incident_id)
        current = jobs.get(incident_id) if jobs is not None else None
        if current is not None:
            return current
        if saved_report(incident) is not None:
            return AnalysisStatus(incident_id=incident_id, state="completed", is_mock=incident.is_mock,
                                  detail="Saved report available; human review required.")
        raise HTTPException(409, "Analysis has not run; POST /analyze first")

    @app.get("/incidents/{incident_id}/media", response_class=FileResponse,
             responses={200: {"content": {"video/mp4": {"schema": {"type": "string", "format": "binary"}}}},
                        206: {"description": "Partial MP4 byte range"},
                        404: {"description": "Footage unavailable"},
                        416: {"description": "Invalid byte range"}})
    def media(incident_id: str):
        incident = incident_or_404(incident_id)
        root = os.getenv("WITNESS_MEDIA_ROOT")
        if incident.is_mock or not root:
            raise HTTPException(404, "No local footage available")
        try:
            path = LocalMedia(Path(root)).resolve(incident)
        except (ProviderError, OSError, ValueError):
            raise HTTPException(404, "No local footage available") from None
        return FileResponse(path, media_type="video/mp4", headers={"X-Content-Type-Options": "nosniff"})

    @app.get("/incidents/{incident_id}/results", response_model=IncidentReport)
    def results(incident_id: str):
        incident = incident_or_404(incident_id)
        report = saved_report(incident)
        if report is None:
            raise HTTPException(409, "Analysis has not run; POST /analyze first")
        return report

    return app

app = create_app()
