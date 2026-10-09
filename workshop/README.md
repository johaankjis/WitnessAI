# Witness workshop — TASK-005C

A separate, lightweight FastAPI application with plain HTML/CSS/JS, scoped to the
Team 6 workshop. All application source stays in this directory. It does not import
or overwrite `apps/api`, `apps/web`, shared contracts, or the vision service.
The Mac Witness product has Pydantic contracts, protocol-based pipelines, persisted
reports and a Next.js dashboard; this app uses synchronous retrieval and six fixed
illustrative claims, with no persistence, upload, inference, or fault determination.

## Mac development

Python 3.11+ is required. From the repository root:

```sh
sh workshop/start-mac.sh
```

Open http://127.0.0.1:8080 (also works at `/app/`). First startup installs the pinned
workshop requirements from the public Python package index into `workshop/.venv`.
It always selects fixture mode, binds localhost, and does not use inherited VSS
credentials. Subsequent offline startup after dependencies are installed:

```sh
cd workshop
WITNESS_WORKSHOP_MODE=fixture .venv/bin/python main.py
```

No `.env` file is loaded automatically. `.env.example` describes configuration.
Default `WITNESS_WORKSHOP_MODE=fixture` constructs only `FixtureClient`:
search, captions, object counts and scoped Q&A are deterministic synthetic teaching
data. Every review and claim is labeled synthetic, including provenance and rationale.
The video placeholder deliberately has no footage. Fixture identifiers use `fixture://`.
No synthetic result is independent corroboration or measured model performance.

Codex integrates configuration, API and release tooling; Claude Code can develop
retrieval/fixture tests here; Muse can edit this directory's HTML/CSS/JS. Agree on
workshop API shape together. These roles do not change ownership of the Mac product.
Do not add providers, footage, weights or dependencies to the source ConfigMap.

## VAST mode (VM only)

Explicitly set `WITNESS_WORKSHOP_MODE=vast`, `VSS_URL`, `VSS_USERNAME`, and
`VSS_PASSWORD`. `VSS_TIMEOUT_SECONDS` defaults to 60, with a finite range of (0, 300].
`HOST` defaults to localhost; deployed pods require `HOST=0.0.0.0`, `PORT=8080`.
Invalid/missing configuration fails startup. There is no fallback to fixtures.
Credentials stay server-side; redirects are refused; network errors are sanitized.
Do not configure or call private VSS from a Mac. See [deployment](DEPLOYMENT.md).

## API and evidence behavior

- `GET /health`: mode, synthetic flag and configuration status (not a VSS readiness probe).
- `GET /api/incident`: illustrative statements and mode-specific incident.
- `GET /api/review?include_agent=true`: six reviews; agent notes optional/advisory.
- `GET /api/claims/{id}`: one review; unknown IDs return 404.
- `GET /api/media/stream`: VAST byte-range proxy; fixtures return 404, never real footage.
- `/`, `/styles.css`, `/app.js`: UI. Both preserved and stripped `/app` ingress paths work.

Metadata/search failures return 502. Detection/Q&A failures are explicit advisory
errors and never fabricated success. Missing detections are not negative evidence.
VAST 401 refreshes once; a repeated failure stops. Bad JSON/types return sanitized
errors. Requests time out; stream resources close on completion/failure/disconnect.
Mid-stream network errors terminate the response; they cannot change an already-sent
HTTP status. Tokens and upstream response bodies are not included in public errors.

Verdicts use only the exact fixed anchor source and its validated 25–30 second parent
window. An unrelated search hit is discarded; filename equality is insufficient.
Offsets are relative to the five-second clip; parent time is start + offset. Offsets
are illustrative review markers, not detected event times. Unexpected/nonfinite
windows are rejected. A not_visible window identifies the reviewed interval, not
proof of a claim. Every verdict has provenance, uncertainty, window and human review.
Interpretive signal/right-of-way claims abstain; mixed cues and missing captions
abstain. Similarity and agent text never decide verdicts. Cue matching remains a
limited workshop heuristic and cannot establish driver identity or legal fault.

## Validation and release

```sh
workshop/.venv/bin/python -m pytest workshop/tests -q
python3 workshop/release.py preflight
python3 workshop/release.py package --output /tmp/witness-workshop.tar
```

Tests block real requests globally and mock every VSS interaction. Release packaging
uses an explicit file allowlist, rejects symlinks, writes a checksum manifest, and
limits uncompressed source size. It excludes `.env`, credentials, generated files,
footage, weights, virtual environments and node_modules. It cannot prove that a
human has not pasted secrets into source: review staged changes before release.
The VM plan uses an immutable, content-named ConfigMap for reliable rollback.
See [TASK-005C results](TASK-005C.md) and [deployment and rollback](DEPLOYMENT.md).
