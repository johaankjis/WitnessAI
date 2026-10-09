"""Witness workshop MVP — FastAPI + static UI for team-6.

Deploy with deployment/deploy-app-no-registry (Ingress /app).
Credentials stay server-side via VSS_* env vars. Never embed tokens in HTML.
"""

from __future__ import annotations

import logging
import requests
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from config import mode, vast_settings
from fixtures import FixtureClient, LABEL, SOURCE, VIDEO
from copy import deepcopy
import math

from incident import INCIDENT, all_claims, get_claim, get_incident_bundle
from verdicts import map_claim_verdict, seek_time_for_claim
from vss_client import (
    VSSAPIError,
    VSSAuthError,
    VSSClient,
    prefer_incident_hit,
    public_evidence_row,
    summarize_detections,
    validate_detection_provenance,
)
from wandb_adapter import WandBInferenceAdapter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("witness")

APP_DIR = Path(__file__).resolve().parent
PORT = int(os.environ.get("PORT", "8080"))

app = FastAPI(title="Witness Workshop MVP", version="0.2.0")
MODE = mode()
if MODE == "vast":
    url, username, password, timeout = vast_settings()
    vss = VSSClient(url, username, password, timeout=timeout)
else:
    vss = FixtureClient()
INCIDENT = deepcopy(INCIDENT)
if MODE == "fixture":
    INCIDENT.update(source=SOURCE, original_video=VIDEO, segment_filename="fixture-segment",
                    original_video_basename="fixture-parent", footage_permitted=False,
                    footage_notes=LABEL, title="Synthetic intersection development fixture",
                    disclaimer=LABEL + " Human review required. No fault determination.")


def evidence_mode() -> dict[str, Any]:
    return {"mode": MODE, "synthetic": MODE == "fixture",
            "label": LABEL if MODE == "fixture" else "VAST evidence — human review required"}


def validate_evidence(row: dict[str, Any], *, metadata: bool = False) -> None:
    if not isinstance(row, dict):
        raise HTTPException(502, "Invalid evidence record")
    if bool(row.get("synthetic", False)) != (MODE == "fixture"):
        raise HTTPException(502, "Evidence mode mismatch; refusing mixed provenance")
    if row.get("source") != INCIDENT["source"]:
        raise HTTPException(502, "Evidence source mismatch")
    if metadata:
        if row.get("reasoning_content") is not None and not isinstance(row["reasoning_content"], str):
            raise HTTPException(502, "Invalid evidence description")
        start, end = row.get("segment_start_sec"), row.get("segment_end_sec")
        if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                for v in (start, end)) or start < 0 or end <= start
                or {"start": start, "end": end} != INCIDENT["evidence_window_sec"]):
            raise HTTPException(502, "Invalid or unexpected evidence timestamps")
wandb = WandBInferenceAdapter()

@app.middleware("http")
async def ingress_prefix(request: Request, call_next):
    path = request.scope["path"]
    if path == "/app" or path.startswith("/app/"):
        request.scope["path"] = path[4:] or "/"
    return await call_next(request)


def _anchor_segment() -> dict[str, Any]:
    """Load metadata + detections for the fixed incident segment."""
    source = INCIDENT["source"]
    try:
        meta = vss.segment_metadata(source)
    except VSSAuthError as exc:
        raise HTTPException(status_code=502, detail=f"VSS auth failed: {exc}") from exc
    except VSSAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "metadata_failed", "status": exc.status_code, "message": str(exc)},
        ) from exc
    validate_evidence(meta, metadata=True)
    detection_error = None
    try:
        det = vss.segment_detections(source)
    except (VSSAPIError, VSSAuthError):
        detection_error = "Detections unavailable; not treated as negative evidence"
        det = None
    if det is not None:
        if MODE == "fixture":
            validate_evidence(det)
        else:
            try:
                validate_detection_provenance(
                    det, meta, source=source,
                    legacy_source=INCIDENT["legacy_detection_source"],
                    expected_sidecar=INCIDENT["detection_sidecar_uri"],
                )
            except ValueError as exc:
                raise HTTPException(502, str(exc)) from exc
    return {
        "metadata": public_evidence_row(meta, source_fallback=source),
        "detections": {**summarize_detections(det), "error": detection_error},
        "raw_meta": meta,
        "raw_det": det,
    }


def _claim_search(claim: dict[str, Any]) -> dict[str, Any]:
    filters = {
        "location": INCIDENT["location"],
        "camera_id": INCIDENT["camera_id"],
    }
    try:
        data = vss.search(
            claim.get("search_query") or claim["text"],
            top_k=5,
            min_similarity=0.2,
            metadata_filters=filters,
            llm_top_n=1,
        )
    except VSSAuthError as exc:
        raise HTTPException(status_code=502, detail=f"VSS auth failed: {exc}") from exc
    except VSSAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "search_failed", "status": exc.status_code, "message": str(exc)},
        ) from exc
    if bool(data.get("synthetic", False)) != (MODE == "fixture"):
        raise HTTPException(502, "Search evidence mode mismatch")
    hit = prefer_incident_hit(data.get("results") or [], INCIDENT["source"])
    if hit:
        validate_evidence(hit, metadata=True)
    return {
        "query": claim.get("search_query") or claim["text"],
        "hit": public_evidence_row(hit, source_fallback=INCIDENT["source"]),
        "total": data.get("total"),
        "llm_synthesis_advisory": (data.get("llm_synthesis") or {}).get("response"),
    }


def _build_claim_review(
    claim: dict[str, Any],
    *,
    anchor: dict[str, Any],
    include_agent: bool = False,
) -> dict[str, Any]:
    search = _claim_search(claim)
    hit = search["hit"]
    # Verdicts and player always refer to the validated fixed anchor.
    use_anchor = True
    evidence_row = anchor["metadata"]
    reasoning = evidence_row.get("reasoning_content")
    missing = not bool(reasoning)

    agent_answer = None
    agent_error = None
    if include_agent:
        try:
            asked = vss.agent_ask_scoped(
                f"Regarding this video only: is there observational evidence for: {claim['text']}? "
                "Do not assign fault. Cite only what is visible.",
                INCIDENT["original_video"],
                top_k=6,
            )
            if bool(asked.get("synthetic", False)) != (MODE == "fixture"):
                raise HTTPException(502, "Agent evidence mode mismatch")
            agent_answer = asked.get("answer")
        except (VSSAPIError, VSSAuthError) as exc:
            agent_error = str(exc)

    verdict = map_claim_verdict(
        claim,
        reasoning_content=reasoning,
        object_classes=evidence_row.get("object_classes")
        or (anchor["detections"].get("object_classes")),
        object_counts=evidence_row.get("object_counts")
        or (anchor["detections"].get("object_counts")),
        similarity_score=hit.get("similarity_score") if hit.get("found") else None,
        agent_answer=agent_answer,
        evidence_missing=missing,
    )
    verdict["provenance"].update(evidence_mode())
    verdict["provenance"]["independent_corroboration"] = False
    verdict["uncertainty"] = "Cue matching is not calibrated verification; human review required."
    verdict["evidence_window_sec"] = INCIDENT["evidence_window_sec"]
    if MODE == "fixture":
        verdict["provenance"].update(cosmos_reasoning_used=False, yolo_objects_used=False)
        verdict["rationale"] = LABEL + " " + verdict["rationale"].replace("Cosmos", "Synthetic caption").replace("YOLO", "Synthetic").replace("corroborate presence only", "are simulated context only")
    seek_rel = seek_time_for_claim(claim, INCIDENT["evidence_window_sec"])
    return {
        **evidence_mode(),
        "claim": {
            "id": claim["id"],
            "text": claim["text"],
            "statement_id": claim.get("statement_id"),
            "statement_label": claim.get("statement_label"),
            "verdict_mode": claim.get("verdict_mode"),
        },
        "verdict": verdict,
        "seek_sec": seek_rel,
        "seek_absolute_sec": INCIDENT["evidence_window_sec"]["start"] + seek_rel,
        "evidence": {
            "segment": evidence_row,
            "used_anchor_segment": use_anchor,
            "search": {
                "query": search["query"],
                "hit": hit,
                "total": search["total"],
            },
            "detections_summary": anchor["detections"],
            "llm_synthesis_advisory": search.get("llm_synthesis_advisory"),
            "agent_answer_advisory": agent_answer,
            "agent_error": agent_error,
            "media": {
                "proxy_url": "/api/media/stream" if MODE == "vast" else None,
                "source_basename": INCIDENT["segment_filename"],
                "original_video_basename": INCIDENT["original_video_basename"],
                "note": "Browser plays via server proxy; JWT never sent to client.",
            },
        },
    }


def build_full_review(*, include_agent: bool = False) -> dict[str, Any]:
    if not vss.configured():
        raise HTTPException(
            status_code=503,
            detail="VSS credentials not configured (VSS_URL / VSS_USERNAME / VSS_PASSWORD)",
        )
    anchor = _anchor_segment()
    claim_rows = []
    for claim in all_claims():
        claim_rows.append(_build_claim_review(claim, anchor=anchor, include_agent=include_agent))

    # Timeline markers from claims
    timeline = [
        {
            "claim_id": row["claim"]["id"],
            "label": row["claim"]["text"][:72],
            "seek_sec": row["seek_sec"],
            "seek_absolute_sec": row["seek_absolute_sec"],
            "verdict": row["verdict"]["verdict"],
            "verdict_label": row["verdict"]["verdict_label"],
        }
        for row in claim_rows
    ]

    return {
        **evidence_mode(),
        "incident": INCIDENT,
        "disclaimer": INCIDENT["disclaimer"],
        "wandb": wandb.status(),
        "anchor": {
            "metadata": anchor["metadata"],
            "detections": anchor["detections"],
        },
        "statements": get_incident_bundle()["statements"],
        "claim_reviews": claim_rows,
        "timeline": timeline,
        "ui": {
            "video_url": "/api/media/stream" if MODE == "vast" else None,
            "human_review_required": True,
            "binding_liability_conclusion": False,
            "collision_claimed": False,
            "collision_note": (
                ("Synthetic development fixture; no footage analyzed. " if MODE == "fixture" else "Footage is an ordinary intersection scene from the workshop corpus. ") +
                "Do not treat it as a proven collision."
            ),
        },
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        **evidence_mode(),
        "status": "ok",
        "app": "witness-workshop",
        "team": INCIDENT["team_namespace"],
        "vss_configured": vss.configured(),
        "wandb": wandb.status(),
    }


@app.get("/api/incident")
def api_incident() -> dict[str, Any]:
    bundle = get_incident_bundle()
    bundle["incident"] = INCIDENT
    bundle.update(evidence_mode())
    bundle["wandb"] = wandb.status()
    return bundle


@app.get("/api/review")
def api_review(include_agent: bool = False) -> dict[str, Any]:
    return build_full_review(include_agent=include_agent)


@app.get("/api/claims/{claim_id}")
def api_claim(claim_id: str, include_agent: bool = False) -> dict[str, Any]:
    claim = get_claim(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="unknown claim")
    if not vss.configured():
        raise HTTPException(status_code=503, detail="VSS credentials not configured")
    anchor = _anchor_segment()
    return _build_claim_review(claim, anchor=anchor, include_agent=include_agent)


@app.get("/api/media/stream")
def api_media_stream(request: Request) -> Response:
    """Proxy VSS range-capable stream; keep JWT server-side."""
    if not vss.configured():
        raise HTTPException(status_code=503, detail="VSS credentials not configured")
    if MODE == "fixture":
        raise HTTPException(404, "Synthetic fixtures have no video footage")
    range_header = request.headers.get("range")
    try:
        upstream = vss.open_stream(INCIDENT["source"], range_header=range_header)
    except VSSAuthError as exc:
        raise HTTPException(status_code=502, detail=f"VSS auth failed: {exc}") from exc
    except VSSAPIError as exc:
        raise HTTPException(status_code=502, detail=f"stream failed: {exc}") from exc

    headers = {}
    for key in (
        "Content-Type",
        "Content-Length",
        "Content-Range",
        "Accept-Ranges",
        "Cache-Control",
    ):
        if key in upstream.headers:
            headers[key] = upstream.headers[key]
    if "Content-Type" not in headers:
        headers["Content-Type"] = "video/mp4"
    headers["Accept-Ranges"] = headers.get("Accept-Ranges", "bytes")

    def iter_bytes():
        try:
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                if chunk:
                    yield chunk
        except requests.RequestException:
            raise RuntimeError("Upstream video stream interrupted") from None
        finally:
            upstream.close()

    return StreamingResponse(
        iter_bytes(),
        status_code=upstream.status_code,
        headers=headers,
        media_type=headers.get("Content-Type", "video/mp4"),
    )


@app.get("/")
def index(request: Request) -> HTMLResponse:
    path = APP_DIR / "index.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="index.html missing")
    return HTMLResponse(path.read_text())


@app.get("/styles.css")
def styles() -> FileResponse:
    return FileResponse(APP_DIR / "styles.css", media_type="text/css")


@app.get("/app.js")
def app_js() -> FileResponse:
    return FileResponse(APP_DIR / "app.js", media_type="application/javascript")


def create_app() -> FastAPI:
    return app


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=os.getenv("HOST", "127.0.0.1"), port=PORT, log_level="info")
