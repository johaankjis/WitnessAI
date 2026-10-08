# TASK-002C — AI reasoning engine

Implemented within `apps/api`; public models, exported schemas and default mock OpenAPI are unchanged. No changes to vision, evaluation or web ownership areas. TASK-002C stops at provider-ready boundaries with offline transport tests, not demonstrated live inference.

## Foundation / integration prerequisite

This worktree's HEAD contains only `projects.md`. TASK-001 exists as uncommitted files in the sibling `../WitnessAI` checkout. The API source and original 32 tests were copied unchanged before extending the API. Contracts, fixtures, root package configuration and shared documentation were inspected and used read-only. Integrate these API changes on top of TASK-001; this worktree alone is not a standalone installation. Do not replace other agents' work when integrating.

## Implementation

- `provider_io.py`: synchronous OpenAI-compatible chat-completions HTTP boundary behind background jobs. Bounded retries for 429, 5xx and transport/timeouts; no retry on authentication, malformed output or other 4xx. Redirects disabled. Exceptions omit provider bodies, credentials and statements. Strict JSON or a single JSON fence is accepted; duplicate keys, nonfinite numbers, extra fields, coercions, refusal, truncation and oversize responses fail closed. JSON schema is supplied in prompts; server-side structured-output support is not assumed.
- `providers.py`: W&B extraction preserves source quotes and driver/statement references, requests one independently checkable assertion per claim and assigns stable IDs. Cosmos localization and verification consume actual video input. Per-run adapters bind immutable video bytes to prevent concurrent incident mix-ups. A missing evidentiary basis always produces `not_visible`; no fallback to synthetic success. Pydantic checks structure, not semantic atomicity or truth; those require model evaluation and human review.
- W&B report generation produces a constrained report outline and review priority list. The renderer copies existing claims and evidence rather than allowing a second model to invent verdicts or fault assignments. Observation = evidence description, inference = verdict explanation, uncertainty = verdict uncertainty. Reports always require human review and prohibit a legal fault determination. Model-supplied observations and inferences remain unverified judgments, not detector measurements.
- Provenance includes provider, configured model identifier, stage, SHA-256 of the exact video bytes and timestamp basis. Existing evidence records preserve original URI, start/end, description and optional uncalibrated confidence. W&B report provenance is in summary text because v1 lacks a report provenance field.
- `media.py`: local MP4 only, bounded at 25 MB and 120 seconds. Snapshot bytes are probed with `ffprobe` and the same bytes sent as a base64 video data URL. Uses video stream duration, not a supplied fixture duration or audio length. Missing/unreadable duration fails. Incident metadata must agree within 0.05 seconds; windows must remain strictly within both durations, with no clamping. All timestamps are original-video seconds. Verification sends the full video and restricts attention through explicit review windows; this does not physically crop the video or guarantee model attention.
- `pipeline.py`: checks localization before verification, references, unique claims, evidence bounds and mock provenance; rejects report-stage rewriting of claims, verdicts or observations.
- Real mode uses no detector until a real observer is integrated; observations are empty and reports explicitly disclose that corroboration is unavailable. It never relabels mock observations as real.

## Verified provider assumptions (2026-10-08)

Installed TASK-001 environment: Python 3.14, Pydantic 2.14.0, FastAPI 0.143.0, HTTPX 0.28.1, pytest 9.1.1. No OpenAI, W&B or NVIDIA SDK installed. The system Python lacks the foundation dependencies. Direct HTTPX was selected rather than introducing uninspected SDK calls. `ffprobe` is absent locally.

Primary documentation inspected:

- [W&B / CoreWeave chat-completions reference](https://docs.coreweave.com/products/inference/serverless/api-reference/chat-completions): `https://api.inference.wandb.ai/v1`, bearer API key, model, chat messages and `choices[0].message.content`; optional project tracking. The documented curl example confirms `/chat/completions`, bearer authentication and optional `OpenAI-Project` header. Model availability and account access must be confirmed by the operator.
- [NVIDIA Cosmos Reason 2 repository](https://github.com/nvidia-cosmos/cosmos-reason2): documented vLLM serving, Cosmos Reason2 model family and reasoning parser. This adapter targets an operator-deployed **vLLM-compatible** Reason 2 server, not an invented NVIDIA hosted NIM endpoint. Configure the exact served model name. NVIDIA now recommends Cosmos 3; this task deliberately retains requested Reason 2.
- [vLLM multimodal documentation](https://docs.vllm.ai/en/stable/features/multimodal_inputs/) and [official HTTP client example](https://github.com/vllm-project/vllm/blob/main/examples/generate/multimodal/openai_chat_completion_client_for_multimodal.py): video content uses `video_url`; MP4 base64 data URLs are demonstrated. Request transport tests assert this wire shape.

Unverified externally: endpoint deployment/authentication, chosen model access, JSON compliance, localization/verification accuracy, throughput, maximum context, full-video payload support on the chosen server, and effective sampling FPS. No live requests, provider credentials, GPU inference or benchmark were used. Configure 4 fps on the serving deployment and validate its sampling behavior separately; the client does not claim an unverified per-request FPS extension. Configure the vLLM reasoning parser so final JSON appears in message content; embedded reasoning traces are rejected. No hosted-NIM compatibility claim is made.

## Setup

On a checkout containing TASK-001, install its dependencies plus `python -m pip install -r apps/api/requirements-providers.txt`. Install FFmpeg/ffprobe through your platform package manager. No provider SDK is required. Supply environment variables through the shell or a secret manager; no dotenv loading or secrets are included.

| Variable | Default / requirement |
| --- | --- |
| `WITNESS_ANALYSIS_MODE` | `mock` (credential-free); `real` enables both providers |
| `WANDB_API_KEY` | Required for real mode; obtain from your provider account |
| `WANDB_INFERENCE_MODEL` | Required exact accessible model name; no guessed default |
| `WANDB_INFERENCE_BASE_URL` | `https://api.inference.wandb.ai/v1` |
| `WANDB_INFERENCE_PROJECT` | Optional `team/project` usage attribution |
| `COSMOS_BASE_URL` | Required vLLM-compatible base ending in `/v1` |
| `COSMOS_MODEL` | `nvidia/Cosmos-Reason2-8B`; match deployed served name |
| `COSMOS_API_KEY` | Optional for local unauthenticated serving; required if deployment enforces auth |
| `WITNESS_PROVIDER_TIMEOUT` | 30 seconds per HTTP operation, >0 and <=120 |
| `WITNESS_PROVIDER_RETRIES` | 2 retries after initial attempt; allowed 0–3 |
| `WITNESS_MEDIA_ROOT` | Required approved local directory of MP4 footage |
| `WITNESS_FFPROBE` | `ffprobe` executable name or path |
| `WITNESS_INCIDENT_PATH` | Existing `data/demo/incident.json`; real mode needs a real incident JSON |
| `WITNESS_DATA_DIR` | Existing `data/local` report storage |
| `WITNESS_CORS_ORIGINS` | Existing localhost origins, unchanged |

Remote provider URLs require HTTPS; HTTP is accepted only for loopback serving. Real incident JSON must set `is_mock=false`, provide a local `.mp4` path beneath the media root (absolute, relative or local `file:///` URI), accurate duration and driver statements. Remote URLs, S3/VAST acquisition and uploads are not implemented. Start the existing ASGI app with **one worker**, e.g. `uvicorn witness_api.main:app`. `/health` indicates selected mode, not provider availability. Invalid real-mode configuration fails startup instead of silently switching to mock.

## API behavior and bounded jobs

Mock POST remains synchronous, deterministic and returns the original completed status. All original route schemas/OpenAPI exports continue to match.

Real POST returns HTTP 200 with the existing `AnalysisStatus` shape and `pending`, then `running`, `completed` or `failed`. Repeat the same POST to poll. Duplicate submissions do not enqueue more work. The single worker allows at most four outstanding jobs; another incident gets HTTP 503 when full. State history is capped at 128 incidents. Completion is recorded only after atomic report persistence. Failure preserves an old report and returns a safe diagnostic. `/results` keeps its existing behavior: 409 with no saved report, otherwise the saved report (possibly older); wait for completed status before treating it as the current run.

Terminal status is sticky for the process lifetime unless evicted from the bounded history; restarting the process allows reanalysis. This deliberately avoids rerunning inference every time a client polls. A new attempt/retry API needs coordination. Pending/running states are in memory, not durable or shared across processes. Shutdown cancels queued work; a running worker finishes its bounded provider operations and may still commit. There is no hard whole-job deadline or thread cancellation; HTTP timeouts are inactivity limits, with finite attempt/claim counts, not a wall-clock SLA. Use a durable external worker before production/multi-worker deployment.

## Contract requests — proposals only

1. Dedicated status GET plus attempt/job ID and an explicit retry operation, timestamps and safe error code. Needed for durable jobs, reruns and avoiding stale `/results` ambiguity. Existing status states suffice for the limited worker here.
2. Claim provenance plus `source_quote`/character offsets. The extractor validates quotes internally, but v1 cannot retain them or extraction model identity as structured fields.
3. Structured report provenance and separate observation/inference/uncertainty sections with claim references. Current fields preserve the distinctions, with report organization provenance in summary text.
4. Media metadata including authoritative video duration, immutable asset digest, sampling FPS and crop offsets. Current adapter records digest and time basis in provenance text and uses original-video seconds.
5. A verifier context accepting incident/media metadata explicitly. Current synchronous Protocol stays intact; a per-job Cosmos instance safely binds that context internally.

No proposals were applied to `packages/contracts`. Vision integration requires coordination with Claude Code; frontend real-mode status polling requires coordination with Muse. UI video serving for local files, detector integration and VAST acquisition remain blockers outside TASK-002C.

## Validation

Run normally after integrating TASK-001: `python -m pytest apps/api/tests`.

In this isolated worktree, use the sibling foundation environment/contracts and opt-in read-only fixture root:

```sh
PYTHONDONTWRITEBYTECODE=1 \
PYTHONPATH=apps/api:../WitnessAI/packages/contracts \
WITNESS_TEST_FOUNDATION_ROOT=../WitnessAI \
../WitnessAI/.venv/bin/python -m pytest apps/api/tests -q -p no:cacheprovider
```

The optional fixture-root hook only affects tests. No original test was changed. Tests use HTTPX MockTransport and mocked ffprobe output; these verify boundaries, not actual decoding or inference. No network, secrets or GPUs required.

Final result: **115 passed** (32 unchanged foundation tests + 83 new cases). One installed Starlette/HTTPX deprecation warning; no test failures.

Files added for TASK-002C: `witness_api/provider_io.py`, `providers.py`, `media.py`, `config.py`, `jobs.py`; `tests/test_reasoning.py`, `tests/conftest.py`, `requirements-providers.txt`, and this document. Foundation files modified: `witness_api/main.py`, `witness_api/pipeline.py`. The copied foundation interfaces, mock, storage, package initializer and original test file are unchanged.
