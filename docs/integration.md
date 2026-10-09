# TASK-003 integration contract

Canonical source: `packages/contracts/witness_contracts/models.py`. Evidence contracts
remain v1.0. Regenerate schemas, examples and OpenAPI together with
`python scripts/export_contracts.py`. No vision contract proposals are needed for this
integration; frame/track metadata and overlays remain future additive work.

| Route | Success | Other behavior |
| --- | --- | --- |
| GET /health | 200 status, analysis_mode | Does not check providers |
| GET /incidents/{id} | 200 Incident | 404 unknown |
| POST /incidents/{id}/analyze | 200 AnalysisStatus | 404 unknown; 500 synchronous failure; 503 full queue |
| GET /incidents/{id}/status | 200 AnalysisStatus | 404 unknown; 409 no analysis/saved source mismatch |
| GET /incidents/{id}/results | 200 IncidentReport | 404 unknown; 409 absent/source mismatch |
| GET /incidents/{id}/media | 200 video/mp4; 206 byte range | 404 unavailable/disallowed/mock; 416 invalid range |

All existing routes and payloads are retained. Errors use `{"detail":"..."}`. Mock POST
completes synchronously. Real POST queues once; clients poll GET status until completed
or failed. Repeated POST still polls the same job for backward compatibility. Status is
pending/running/completed/failed; before submission GET returns 409, not a fictional job.
Completion means report persistence succeeded. Failed jobs preserve older reports; results
can therefore be older while a job runs or fails. Only fetch current results after completed.
Saved reports with incompatible source URI/mock labeling/duration are rejected.

Real terminal status is sticky until process restart/history eviction. There is no retry
endpoint or job ID yet. One worker, four outstanding jobs, 128 retained statuses; not durable
or shared between processes. Provider timeouts bound individual operations, not total job
wall time. The dashboard polls once per second for up to ten minutes, then displays a
status-check message; it does not cancel server work. Reloading a real incident resumes
status checking. Browser requests time out after 15 seconds.

## Mock setup

From repository root:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
npm ci --prefix apps/web
WITNESS_ANALYSIS_MODE=mock python -m uvicorn witness_api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

Second terminal: `npm run dev --prefix apps/web`. Open
http://localhost:3000/incidents/demo-001. The demo has no playable footage.

## Real setup (requires operator-provided assets and endpoints)

Install FFmpeg using your platform package manager (macOS: `brew install ffmpeg`), then:

```sh
source .venv/bin/activate
python -m pip install -e '.[real]'
export WITNESS_ANALYSIS_MODE=real
export WITNESS_MEDIA_ROOT=/absolute/path/to/approved-footage
export WITNESS_INCIDENT_PATH=/absolute/path/to/real-incident.json
export WITNESS_DATA_DIR=data/local-real
export WITNESS_YOLO_WEIGHTS=/absolute/path/to/existing-yolo-weights.pt
export WANDB_INFERENCE_MODEL='your-accessible-model'
export WANDB_INFERENCE_BASE_URL=https://api.inference.wandb.ai/v1
export COSMOS_BASE_URL='https://your-vllm-host/v1'
export COSMOS_MODEL='your-served-cosmos-model'
# Supply WANDB_API_KEY and (if required by deployment) COSMOS_API_KEY securely in the shell.
python -m uvicorn witness_api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

These are configuration examples, not working provider credentials or deployed endpoints.
Configuration fails closed when required values/weights are absent. Real mode wires both
providers and real vision together; it cannot use synthetic observations as fallback.
Optional variables: WITNESS_FFPROBE (default ffprobe), WITNESS_PROVIDER_TIMEOUT (30),
WITNESS_PROVIDER_RETRIES (2), WITNESS_VISION_SAMPLE_FPS (5),
WITNESS_VISION_MIN_CONFIDENCE (0.35), WITNESS_YOLO_DEVICE and WANDB_INFERENCE_PROJECT.
Cosmos server video sampling/reasoning parser requirements remain operator responsibilities;
see `apps/api/TASK-002C.md`. Vision thresholds are not calibrated accuracy claims.

Real incident JSON follows `packages/contracts/examples/Incident.json`, with `is_mock=false`,
real statements, accurate video duration and `video_uri` set to a relative path beneath
WITNESS_MEDIA_ROOT (or an absolute path/local file:/// URI within it). MP4 only, at most
25 MB and 120 seconds for inference; declared duration must agree with ffprobe within
0.05 seconds. Remote URLs, uploads and VAST acquisition are not implemented.

The player uses `${API_BASE}/incidents/${id}/media`; evidence continues to identify the
original source URI. Keep the approved root and source files immutable and operator-owned.
No arbitrary path is accepted from a route/query argument. Mock incidents return 404 for
media. Select a claim to seek to the primary window's start in original-video seconds;
a pending seek is reapplied when metadata loads. No annotated overlay is claimed.

## Frontend and evidence policy

`NEXT_PUBLIC_WITNESS_API_BASE` defaults to http://localhost:8000. CORS defaults to
http://localhost:3000 and http://127.0.0.1:3000; override WITNESS_CORS_ORIGINS with exact
comma-separated origins. Environment files are not automatically loaded by the backend.

Join claims by statement_id; verdicts/observations by claim_id. Detector measurements and
Cosmos judgments render separately. Missing evidence remains not_visible. Confidence may
be null and is never a fault score or calibrated accuracy. Mock observations are explicitly
not independent corroboration. Every report requires human review and supplies no legal
fault determination. No archive-sweep functionality is enabled.
