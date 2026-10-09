# TASK-003 completion report

Integrated on `integration/task-003`, based on merge `3c24b94`; not merged into main.

## Result

One complete deterministic incident review uses the merged API, Claude vision observer,
and Muse dashboard. Mock judgments are unchanged. Detector observations retain separate
provenance and never become automatic Cosmos corroboration. Real wiring is provider-ready,
with a shared immutable media snapshot, but no live inference claim is made.

Added read-only job status polling and incident-scoped MP4 serving with byte-range support.
Existing endpoints and v1 evidence models remain compatible. Browser claim selection seeks
original-video seconds and reapplies seeks after metadata loads. Root installation includes
vision/evaluation packages; canonical examples feed the frontend fixture fallback.

## Validation (2026-10-08)

| Package/check | Result |
| --- | --- |
| API: `python -m pytest apps/api/tests` | 128 passed |
| Vision: `python -m pytest services/vision/tests` | 31 passed |
| Evaluation: `python -m pytest evals/tests` | 16 passed |
| Root: `python -m pytest` | 175 passed, no skips |
| Frontend: `npm test --prefix apps/web` | 27 passed |
| Frontend typecheck | Passed |
| Frontend production webpack build | Passed |
| Contract export and export consistency tests | Passed |
| Running Uvicorn HTTP smoke: health, incident, analyze, status, results | All HTTP 200 |

Python 3.14 on macOS arm64; tested dependency constraints are in requirements-dev.lock.
One upstream Starlette/HTTPX deprecation warning remains. Tests use temporary storage and
no network/provider calls. The separately invoked HTTP smoke used localhost and persisted
only the deterministic demo report. `scripts/smoke_api.py` repeats it against a running API.

Media transport tests verify original bytes, 206 ranges, 416 invalid ranges, and traversal/
symlink/remote-path rejection. Video component tests verify timestamp seeks, including
metadata readiness. Vision/evaluation tests decode generated synthetic MP4s with injected
detections. **Actual dashcam MP4 browser playback was not verified:** no incident footage
was supplied. Generated test videos do not establish real model functionality or accuracy.

## Remaining blockers and limits

No operational real inference validation: missing approved dashcam footage, ffprobe,
provider endpoints/credentials and local YOLO weights/runtime. No calibrated accuracy is
claimed. Runtime endpoints and credentials were not activated. Jobs remain single-process,
in-memory, with sticky terminal status, finite capacity and no hard whole-job deadline.
Media files must remain immutable under operator control. Authentication, durable retries,
uploads and archive sweep remain out of scope.

Setup/start commands are in the root README and docs/integration.md, including real-mode
configuration prerequisites. Recommended next task: provision one approved real clip and
validate decoding, browser playback/seeking, and endpoint-backed inference under human
review; record observed failures and measured results before claiming model performance.

## Files changed
- `.env.example`
- `README.md`
- `apps/api/tests/test_integration.py`
- `apps/api/witness_api/config.py`
- `apps/api/witness_api/jobs.py`
- `apps/api/witness_api/main.py`
- `apps/api/witness_api/media.py`
- `apps/api/witness_api/providers.py`
- `apps/web/README.md`
- `apps/web/app/incidents/[id]/IncidentDashboard.test.tsx`
- `apps/web/app/incidents/[id]/IncidentDashboard.tsx`
- `apps/web/components/VideoPlayer.test.tsx`
- `apps/web/components/VideoPlayer.tsx`
- `apps/web/lib/api.test.ts`
- `apps/web/lib/api.ts`
- `apps/web/lib/fixtures.ts`
- `apps/web/lib/selectors.test.ts`
- `docs/TASK-003.md`
- `docs/architecture.md`
- `docs/integration.md`
- `packages/contracts/examples/DetectorObservation.json`
- `packages/contracts/examples/IncidentReport.json`
- `packages/contracts/openapi.json`
- `pyproject.toml`
- `requirements-dev.lock`
- `scripts/export_contracts.py`
- `scripts/smoke_api.py`
