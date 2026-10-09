# TASK-004B-SETUP — provider readiness

Checked 2026-10-09 on `feature/task-004-real-video`. **Blocked: no live Reason 2 endpoint access verified.**
The initial checkout was clean. This task changes only the credential alias, adds an isolated
text probe and offline tests, and documents setup. No inference, incident analysis, dataset
transfer, weights download, record update, commit, or merge was performed.

## Availability evidence

- The [old Reason 2 Build URL](https://build.nvidia.com/nvidia/cosmos-reason2-8b)
  redirects to [Cosmos3-Nano-Reasoner](https://build.nvidia.com/nvidia/cosmos3-nano-reasoner).
  That listing is a separate model, not proof of hosted Reason 2 access. Cosmos3 was not selected
  or tested. Using it requires an explicit compatibility decision, including provenance changes.
- [Official Reason 2 NIM documentation](https://docs.nvidia.com/nim/vision-language-models/1.7.0/examples/cosmos-reason2/api.html)
  documents self-hosting 2B/8B containers, a local request URL
  `http://127.0.0.1:8000/v1/chat/completions`, and deployment model discovery through
  `client.models.list()`. Its lowercase NIM naming includes `nvidia/cosmos-reason2-8b`.
  This is deployment documentation, not evidence that this user's server exists.
- No authenticated provider response was obtained. `NVIDIA_API_KEY`, `COSMOS_API_KEY`,
  `COSMOS_BASE_URL`, and `COSMOS_MODEL` were all absent/empty in the tool process environment
  (only presence booleans were inspected). A key exported in another terminal is not necessarily
  inherited by this process. No secret files were searched or loaded.

Hosted Reason 2 availability is **unverified**, not definitively absent. The public redirect
alone cannot establish that Cosmos3 is the only hosted model, nor establish account entitlement.
There is no verified hosted Reason 2 request URL to configure from this session.

## Request compatibility

The NIM guide matches the existing POST shape: `model`, system/user `messages`, `max_tokens`,
`stream:false`, and `video_url.url` containing an MP4 base64 data URL. It documents text-only
queries and a default 4 FPS with optional `media_io_kwargs` sampling controls. Witness does
not set sampling controls. Deployment behavior still needs verification.

Witness requests JSON using a schema in the prompt, not server-enforced `response_format`.
It validates final content with Pydantic and rejects reasoning-tagged, malformed, refused,
truncated, or oversized responses. Documented reasoning examples can emit tags, so wire-format
compatibility does not establish JSON compliance. The smoke probe exercises this strict parsing.
No video or temporal-reasoning capability has been tested.

## Configuration

No dotenv loader is used. Supply secrets through the launching process environment or secret
manager; do not paste keys into source, commands saved in shell history, or this document.

| Variable | Actual behavior |
| --- | --- |
| `COSMOS_BASE_URL` | Required in real mode; transport appends `/chat/completions`. Use the deployment's documented base, normally ending `/v1`, not the full request URL or a Build webpage. |
| `COSMOS_MODEL` | Real pipeline retains existing default `nvidia/Cosmos-Reason2-8B` (vLLM spelling). Override with exact deployed ID; the smoke command requires an explicit ID. |
| `NVIDIA_API_KEY` | New environment alias for Cosmos Bearer authentication. |
| `COSMOS_API_KEY` | Nonempty value takes precedence over `NVIDIA_API_KEY`. Both absent means unauthenticated local serving; the smoke command refuses a remote request without a key. |
| `WITNESS_PROVIDER_TIMEOUT` | Real pipeline default 30 seconds, valid >0 and <=120. |
| `WITNESS_PROVIDER_RETRIES` | Real pipeline default 2, valid 0–3. |
| `WITNESS_ANALYSIS_MODE` | Default mock; leave it unchanged for the standalone smoke test. |

Remote URLs require HTTPS; HTTP is allowed only for loopback. Redirects are not followed.
NGC container-download credentials in the NIM guide are separate from application endpoint auth.
Do not assume an NVIDIA key grants access to an arbitrary private deployment.

After obtaining a documented accessible **Reason 2 8B** deployment, export its exact base and
model ID as `COSMOS_BASE_URL` and `COSMOS_MODEL`. For a locally deployed NIM only, the documented
base is `http://127.0.0.1:8000/v1`; no local NIM was started here. The probe accepts the documented
lowercase NIM spelling and the existing mixed-case vLLM spelling. Custom served aliases require
review before extending the probe; it deliberately rejects arbitrary replacement model names.

With `NVIDIA_API_KEY` already securely loaded into that process environment, run from repo root:

```sh
.venv/bin/python -m witness_api.provider_smoke
```

The command uses the production HTTP transport and parser with a fixed text-only schema,
30-second timeout and zero retries. It imports no application entrypoint and constructs no
pipeline, media loader, YOLO detector, or storage. Exit 0 means the configured model accepted
the text request and returned valid JSON; it does not independently attest backend model
identity, prove auth enforcement on an open server, or validate video inference. Exit 1 reports
a sanitized blocker. Provider bodies, prompts, URLs and credentials are not printed.

Full real-mode analysis additionally needs `WANDB_API_KEY`, `WANDB_INFERENCE_MODEL`,
`WITNESS_YOLO_WEIGHTS`, `WITNESS_MEDIA_ROOT`, and a real incident configuration; see
[existing integration instructions](../apps/api/TASK-002C.md). Do not start incident analysis
as a connectivity test: it sends full video. The new alias supersedes the older credential
table; public API routes and contracts are unchanged.

## Outcomes and remaining blockers

| Check | Outcome |
| --- | --- |
| Live smoke command | Blocked before network: missing base URL and model. Key also absent. |
| Live authentication / model access / JSON response | Not run; unavailable configuration. |
| Offline authentication and model errors | HTTP 401, 403, 404 safely reported, no retry or fallback. |
| Offline transport / parsing | Valid JSON passes; malformed/extra-field/reasoning-tagged output fails; 301, 400, 429, 500, 503, connection errors and timeouts fail safely. |
| Full `python -m pytest` using `.venv/bin/python` | 209 passed, 3 skipped (optional vision tests); includes 22 new offline tests. |
| `python scripts/export_contracts.py` using `.venv/bin/python` | Completed; schemas, examples and OpenAPI have no diff. |

Remaining prerequisites: a key inherited by the executing process; a documented or API-discovered
Reason 2 8B deployment URL and exact model ID; a successful text smoke run; and separate dataset
permission confirmation before any Nexar transfer. Endpoint access alone does not authorize
licensed-media disclosure. Existing YOLO observations and mock behavior are preserved. Stop here;
no successful inference or provider readiness is claimed.
