# Witness contributor boundaries
Read projects.md completely before architectural decisions. Current scope is TASK-001 only.

## Architecture
Python 3.11+ FastAPI composition root: apps/api/witness_api/main.py.
Pydantic v2 contracts in packages/contracts are the single contract source.
Pipeline orchestration depends on Protocol interfaces; adapters provide implementations.
Local JSON storage atomically replaces reports. Demo is synchronous and deterministic.
No providers, credentials, GPUs, real inference, upload flow, or fault decisions in TASK-001.

## Ownership
- Codex: apps/api, packages/contracts, root configuration, architecture/integration docs.
- Claude Code: services/vision and evals. Implement adapters against published contracts;
  propose shared contract changes to Codex before changing them.
- Muse: apps/web. Consume documented API and schemas; propose contract changes to Codex.
Scaffold-only changes to others' areas are permitted for TASK-001. Do not implement their features.
Inspect existing work and git status first; preserve unrelated edits. No automatic TASK-002.

## Standards and tests
Use typed Python, Pydantic v2, explicit dependencies and small adapters. Do not put provider
calls in routes. Reject invalid data and references; never hide a failure as successful analysis.
Run `python -m pytest` after backend changes. Regenerate contracts using
`python scripts/export_contracts.py`; commit schemas, examples and OpenAPI together.
Use TypeScript and Tailwind for web. Keep credentials in environment, never in fixtures.
Tests must use temp storage and no network. Document API behavior changes.

## Evidence boundary
Real adapters must never invent video evidence or present mocks as real analysis.
Missing evidence is not contradiction. Unseen signals must be not_visible.
Every verdict needs timestamped windows, explanation, provenance and uncertainty;
confidence is optional and must not imply calibration. A not_visible window identifies
what was reviewed, not proof of a claim. Mock observations are not independent corroboration.
Human review is always required. Never generate final legal fault determinations.
