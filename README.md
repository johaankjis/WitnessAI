# Witness — TASK-003

An integrated incident review dashboard: driver statements, claim judgments, timestamp
selection, separate detector observations, and a human-review report. The default demo
is deterministic and explicitly **DEMO/MOCK**. No footage is analyzed in mock mode;
no legal fault determination or measured model accuracy is provided.

## Install and start

From this repository root, Python 3.11+ and Node.js 20.9+:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
npm ci --prefix apps/web
WITNESS_ANALYSIS_MODE=mock python -m uvicorn witness_api.main:app --host 127.0.0.1 --port 8000 --workers 1
```

In another terminal, from the repository root:

```sh
npm run dev --prefix apps/web
```

Open http://localhost:3000/incidents/demo-001 and select **Run analysis**. Select any
claim to seek its evidence timestamp. The demo intentionally shows a placeholder player
because `mock://` is not footage. If the API is unavailable, the dashboard labels its
canonical bundled examples as fixture mode. `?fixture=1` explicitly requests that mode.
API docs: http://127.0.0.1:8000/docs.

Root installation includes API, shared contracts, vision and evaluation Python packages.
The dev extra includes OpenCV/NumPy for offline video tests, but no model weights or GPU
runtime. Frontend dependencies use `package-lock.json`; tested Python pins are in
`requirements-dev.lock` (install with `-c requirements-dev.lock` for the tested versions).

## Validate

```sh
source .venv/bin/activate
python -m pytest
python scripts/export_contracts.py
npm run typecheck --prefix apps/web
npm test --prefix apps/web
npm run build --prefix apps/web
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/incidents/demo-001
curl -X POST http://127.0.0.1:8000/incidents/demo-001/analyze
curl http://127.0.0.1:8000/incidents/demo-001/status
curl http://127.0.0.1:8000/incidents/demo-001/results
```

Reports persist atomically in `data/local`. Exported schemas, examples and OpenAPI live in
`packages/contracts`; frontend fixtures import those examples directly.

## Real adapters (operator configured, not live-validated)

`WITNESS_ANALYSIS_MODE` is the single mock/real selector. Real mode requires W&B and
Cosmos endpoint configuration, real incident metadata, approved local MP4 footage,
FFmpeg/ffprobe, and existing local YOLO weights. No credentials or footage ship here.
See [integration setup](docs/integration.md) for exact environment variables and commands,
and [provider assumptions](apps/api/TASK-002C.md) for unverified serving requirements.
Do not label transport tests or synthetic video tests as validated real inference.

Use one API worker. This is a local development application without authentication,
uploads, distributed jobs, archive sweep, or final fault decisions. Keep the media root
operator-controlled and its source files immutable while reviewing an incident.
