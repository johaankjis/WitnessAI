# Witness — TASK-001
A runnable monorepo foundation for checking driver statements against dashcam evidence.
This release runs **synthetic mock analysis only**. No video exists for the demo, no model
is called, and no credentials are required. Human review remains the decision boundary.
The project direction is in [projects.md](projects.md); TASK-001 does not implement the full plan.

## Backend setup
From the repository root, with Python 3.11+:
```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
python -m uvicorn witness_api.main:app --reload --port 8000
```
Open http://localhost:8000/docs for interactive API documentation.
Optional environment variables are listed in `.env.example`; export them in your shell
(the API does not automatically load .env). CORS allows localhost and 127.0.0.1 on port 3000.

```sh
curl http://localhost:8000/health
curl http://localhost:8000/incidents/demo-001
curl -X POST http://localhost:8000/incidents/demo-001/analyze
curl http://localhost:8000/incidents/demo-001/results
```
Analysis runs synchronously and POST returns completed status. GET results returns 409
before analysis; unknown incidents return 404. Repeated analysis gives the same report.
Reports persist in ignored `data/local/`. A failed rerun leaves the previous report intact.

## Test and export contracts
```sh
python -m pytest
python scripts/export_contracts.py
```
Schemas, OpenAPI, and examples are checked into `packages/contracts/`.

## Frontend scaffold
With Node.js 20.9+ and npm:
```sh
cd apps/web
npm install
npm run dev
```
Only a static scaffold is provided. Muse owns product UI and API integration.

## Layout and handoff
- `apps/api`: routes, pipeline, mock adapters, JSON storage and tests (Codex).
- `packages/contracts`: Pydantic models and exported JSON contracts (Codex).
- `apps/web`: Next.js / TypeScript / Tailwind scaffold (Muse).
- `services/vision`, `evals`: ownership placeholders (Claude Code).
- `data/demo`: deterministic synthetic incident; `data/rules`: reserved, empty of legal rules.
- `docs`: [architecture](docs/architecture.md) and [integration](docs/integration.md).

TASK-001 excludes real inference, legal analysis, authentication, uploads, job queues,
archive search and deployment. See AGENTS.md for contribution boundaries.
