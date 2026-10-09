# TASK-005C integration report

Completed on 2026-10-09 on `feature/task-005-vast-workshop`. Scope is workshop
Mac development, offline validation, packaging and VM deployment preparation only.
The supplied TASK-005C instruction supersedes AGENTS.md's historical TASK-001 scope;
all other ownership and evidence boundaries remain in force.

## Inspection and architecture

Read `projects.md`, `AGENTS.md`, the original workshop README and every original
workshop source/test file before implementation. The entire workshop directory was
initially untracked; existing implementation was preserved and extended. The Mac
product has its own composition root, contracts, adapters, persistence and Next.js
frontend. The workshop remains a flat FastAPI + HTML/CSS/JS app; no Mac product files,
shared contracts, vision implementation, or web product source were changed.

## Delivered behavior

- Default fixture adapter for search, metadata, detections and scoped Q&A. It never
  constructs a real VSS session; inherited credentials do not enable real mode.
- Explicit `vast` mode with environment validation, timeouts, bounded token refresh,
  no redirects, sanitized transport errors and response cleanup.
- Synthetic identifiers/provenance, UI banner and placeholder; fixtures have no
  playable media and are never fallback evidence for a VAST failure.
- Exact anchor source selection, finite timestamp/window validation and explicit
  relative versus parent times. Unrelated hits no longer drive verdicts. Existing
  interpretive abstention, mixed-cue abstention and human review rules retained.
- Every verdict includes uncertainty and provenance; fixture observations are not
  marked as actual Cosmos/YOLO use or independent corroboration.
- Mac startup script and documented offline restart; removed remote font dependency.
  UI works at root and `/app`, with or without upstream prefix stripping.
- Allowlisted deterministic tar, file hashes, source size checks and symlink rejection.
  Credentials/env files, generated output, footage, weights and dependencies excluded.
- Offline VM preflight validates existing Team 6 Deployment/Service/Ingress shape,
  source mount and port mapping; emits immutable source ConfigMap and deployment
  plan without applying anything. Transfer, readiness checks and rollback documented.

## Validation results

Local platform: macOS, Python 3.14.7. A fresh `workshop/.venv` installed the original
pinned workshop dependencies from public PyPI (FastAPI 0.115.6, uvicorn 0.34.0,
requests 2.32.3, httpx 0.28.1, pytest 8.3.4; resolved Pydantic 2.14.0).

| Check | Result |
|---|---|
| `workshop/.venv/bin/python -m pytest workshop/tests -q` | 107 passed |
| `.venv/bin/python -m pytest` (existing Mac product suite) | 209 passed, 3 skipped |
| `.venv/bin/python scripts/export_contracts.py` | Successful; no generated changes |
| `node --check workshop/app.js` / `sh -n workshop/start-mac.sh` | Passed |
| `python3 workshop/release.py preflight` | Passed; 11 flat runtime files, under 70 KB serialized data, 750 KB cap |
| Release tests | Deterministic archives, exclusions, hashes, tamper/size/symlink rejection, incompatible VM shape rejection passed |
| Mac startup and Chrome at `http://127.0.0.1:8080/app` | Six labeled synthetic claims, no-footage placeholder and evidence inspector rendered |

The pinned FastAPI/Starlette stack produces 93 upstream deprecation warnings on
Python 3.14 (AnyIO portal alias and asyncio coroutine introspection); no failures.
Python 3.11 and the actual VM image have not been executed here. The root suite's
three optional-dependency skips are not workshop failures. The root pytest config
excludes workshop, so run the explicit workshop command as well.

Tests deny requests network access and exercise every client interaction (login,
search, metadata, detections, scoped Q&A, stream), JSON/HTTP/network/auth errors,
refresh/cache expiry, missing sidecars, Range forwarding, stream closure, fixture
scope, deterministic output, mixed provenance, nonfinite windows, and `/app` paths.

## Deployment status and remaining operator work

No private VAST service was contacted. No credentials, private HTTP endpoints,
signed URLs, footage or model weights are in the committed source or release.
No transfer, deployment, push or main merge was performed. Public PyPI access and
localhost binding required sandbox approval during validation.

The official `deployment/deploy-app-no-registry` implementation is absent locally.
The plan therefore targets an existing compatible app and retains its image/service/
ingress. The operator must verify the VM Python/dependency versions, Secret keys and
actual platform manifests, review/server-dry-run the generated plan, then authorize
application. Real VSS response compatibility and playback remain VM-only acceptance
checks; mock transport tests are not proof of live VAST integration.

See [DEPLOYMENT.md](DEPLOYMENT.md) for the exact transfer, preflight, application and
revision-based rollback steps. Retain old ConfigMaps and Secrets to make rollback
work. Heuristic verdicts remain draft teaching output, never legal fault decisions.
