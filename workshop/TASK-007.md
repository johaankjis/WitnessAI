# TASK-007 — live Cosmos + YOLO workshop inference

The workshop-only `POST /api/live-analysis` accepts `{ "incident_id": "<selected incident id>" }`.
It retrieves the same authorized VSS segment used by the player, validates its source and
25–30 second parent-video window, downloads fresh MP4 bytes, and calls both GPU services.
No caller-supplied URLs, uploads, source overrides, or cached video are accepted.

Cosmos uses `nvidia/cosmos3-nano-reasoner` at `/v1/chat/completions`, with text and a
base64 MP4 `video_url`. YOLO11s uses `/v1/infer` with `video_base64`, `filename`,
and `include_frames: false`. Both requests carry the runtime bearer token server-side.
The new UI panel reports fresh descriptions, classes/counts, configured model identities,
per-service status/errors, timestamps, video SHA-256, source/window and live provenance.
The identities describe the configured deployments, not an independent weights attestation.
No inference output updates existing claim verdicts, indexed evidence or review functionality.
Human review is required; observations may be wrong, unseen signals remain `not_visible`,
and this feature makes no legal fault decisions or independent-corroboration claims.

## Deployment: required VM/pod preflight

Do not run GPU/VSS requests or deploy from the Mac. Offline packaging/preflight is safe.
From the workshop VM, configure the existing app Deployment with runtime environment
variables or Secret references (never literal credentials in committed manifests):

- `COSMOS_GPU_URL`: service base URL, without `/v1/chat/completions`.
- `YOLO_GPU_URL`: service base URL, without `/v1/infer`.
- `GPU_BEARER_TOKEN`: private VM-supplied token, through Kubernetes Secret.
- `WITNESS_LIVE_INFERENCE_ENABLED=true`: still gated until pod preflight passes.
- Keep existing `WITNESS_WORKSHOP_MODE=vast` and VSS Secret references.

After releasing the new source to the existing application pod, execute **from the VM**:

```sh
kubectl -n team-6 exec <application-pod> -- python live_preflight.py
```

Run in the deployed workshop working directory. This makes authenticated, full inference
requests against both GPU endpoints using the authorized VSS video **inside the app pod's
network namespace**. VM-only curl success is insufficient. The command refuses macOS and
non-Kubernetes execution and prints only sanitized statuses. Both models must return valid
successes before a local `/tmp/witness-live-preflight.json` receipt is atomically written.
A failed recheck removes any older receipt. The API requires that receipt, matching endpoint/token/source configuration and no older
than one hour. Re-run after a pod restart, credentials/endpoints change, or expiry, and in
each pod. If connectivity fails, leave the feature disabled; existing reviews still work.
The existing release deployment planner preserves runtime GPU environment entries;
operators must provision these entries/Secrets on the VM. Do not put tokens in shell history.

## Limits and errors

- One application process/replica for this MVP: one in-flight live request, 30-second
  cooldown, maximum 20 attempts/hour. Limits are in-memory, shared across visitors,
  reset at restart; not a distributed quota or new user authentication system.
- JSON request limit 1 KiB with a five-second body deadline; no arbitrary source selection. Cross-site browser requests rejected.
- Video limit 20 MiB, enforced from both declared length and streamed bytes; complete MP4 only.
- VSS uses its existing bounded configured socket timeout; stream checks a 30-second
  elapsed deadline between chunks (a stalled read can last up to the VSS socket timeout).
- GPU calls run concurrently, each with a 60-second total async deadline, 5-second
  connection timeout, 55-second socket timeout, 256 KiB response ceiling and no redirects,
  retries or inherited HTTP proxies. Cosmos generation is capped at 512 tokens.
- Results are not persisted and use `Cache-Control: no-store`. Failures expose static
  errors/status codes, never upstream bodies, exception text, credentials or signed URLs.
- One successful service returns HTTP 200 with `status=partial`; both failing returns
  HTTP 200 with `status=error`. Each failed service has `live_inference=false` and no
  fabricated observations. Top-level `live_inference` is true only if a service succeeds.
  Consumers must inspect per-service status. Disabled/missing preflight: 503; fixture: 409;
  unauthorized selection: 403; bad metadata/download: 502; rate/concurrency limit: 429.

## Offline verification and limitations

Mock transport tests cover successful payloads/auth, partial failures, timeouts including
total deadline, 401/403 errors, unreachable/invalid services, response/video/request size
limits, source/mode authorization, unchanged incident data, preflight gates and request
limits. Existing workshop/repository tests and offline release preflight are run locally.
No live GPU integration, Kubernetes connectivity, deployment or new footage was verified
from the Mac. The supplied workshop HTTP-200 observations are user-reported prerequisites;
actual pod connectivity and current response compatibility remain required release checks.
This MVP adds only a separate observation panel, not live claim verification or tracking.

Verified locally for this release:

- `.venv/bin/python -m pytest workshop/tests -q`: **185 passed** (network mocked).
- `.venv/bin/python -m pytest -q`: **209 passed, 3 skipped**.
- `.venv/bin/python scripts/export_contracts.py`: completed; shared exports unchanged.
- `.venv/bin/python workshop/release.py preflight`: **PASS**, offline, 13 runtime files.
- `node --check workshop/app.js` and `git diff --check`: **PASS**.
- Release archive includes the adapters, pod preflight, UI, docs and offline tests;
  deterministic packaging emits a separate SHA-256 checksum and per-file manifest.
