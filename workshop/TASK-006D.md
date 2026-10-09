# TASK-006D — Final Witness Evidence Audit

Audited on `feature/task-005-vast-workshop` (HEAD `b5dc98d`) for VAST Builders
Challenge submission. Read-only review of `main.py`, `incident.py`, `verdicts.py`,
`vss_client.py`, `fixtures.py`, `config.py`, `app.js`, `index.html` and the
workshop tests. No VAST cluster was contacted or modified. **No code changes were
needed; no submission-blocking issues found.**

## Audit

| # | Check | Result | Notes |
|---|-------|--------|-------|
| 1 | Verdicts grounded in retrieved evidence | **PASS** | `map_claim_verdict` sets Supported/Contradicted only from explicit cue phrases found in the validated anchor segment's `reasoning_content`. Similarity, LLM synthesis and agent answers never decide. Interpretive claims, missing/empty captions, and conflicting cues all produce `not_visible`. A missing detection sidecar is reported as unavailable, not as negative evidence. |
| 1a | Cue matching robustness | **WARN** | Matching is a case-insensitive substring check with no negation handling. For example, `moving` would also match "not moving". The rationale and `uncertainty` field both say the matching is uncalibrated and needs human review. |
| 2 | Cosmos vs YOLO vs advisory separation | **PASS** | Verdict provenance carries `cosmos_reasoning_used`, `yolo_objects_used`, `similarity_not_sufficient`, `llm_not_sufficient`, `agent_answer_used_as_proof=false` and `independent_corroboration=false`. The UI tags Cosmos and YOLO as *Observed* and search/agent as *Advisory*. In fixture mode every label is replaced with "Synthetic". |
| 2a | YOLO hint source | **WARN** | Object hints use the segment row's `object_classes` first and fall back to the validated sidecar only if those are missing. The two sources are labelled differently, and hints are context only and never decide a verdict. |
| 3 | Source IDs, legacy bucket, timestamps, sidecar | **PASS** | Metadata must match the exact Team 6 source and window `{25.0, 30.0}`, and evidence-mode mismatches are rejected. Detections must have `source=yolo11_coco` and a `segment_source` equal to the Team 6 source or the one exact Team A legacy path. Nothing is rewritten. The metadata sidecar must equal the configured URI, and an echoed sidecar must agree. Detection counts must be equal non-negative integers. |
| 3a | Strict search-hit validation | **WARN** | A search hit with the incident source but missing or different segment timestamps makes the whole review return 502. That is fail-closed, as intended, but it would stop the demo if live search rows leave out `segment_start_sec`/`segment_end_sec`. Check with one live `/api/review` before presenting. |
| 4 | Video seek | **PASS** | The proxy streams the 5 s segment (`INCIDENT["source"]`). `seek_sec` is clip-relative and clamped to [0, 4.95]. `seek_absolute_sec = 25 + seek_sec` is display-only. The player seeks to `seek_sec`. Smoke-checked values: 0.5/25.5, 1.0/26.0, 2.0/27.0, 1.5/26.5, 0.8/25.8, 2.5/27.5. |
| 5 | Human-review / illustrative disclaimers | **PASS** | They appear in the banner (replaced by the server `disclaimer` after load), on the "Illustrative · team-authored" statement tags and in the footer. Every verdict has `human_review_required=true` and `binding_liability_conclusion=false`, and `ui.collision_claimed=false`. |
| 6 | Credentials off the frontend | **PASS** | The JWT is used only server-side, with the stream token added as a query parameter by the proxy. `app.js` and `index.html` contain no tokens, passwords or `VSS_*` values. Error details are sanitized messages without upstream bodies, and `config.py` rejects credentials embedded in `VSS_URL`. |
| 7 | UI ↔ API field compatibility | **PASS** | Every field `app.js` reads is present in the `/api/review` response. The `/app` ingress prefix is served correctly. |

## Tests

- `workshop/.venv/bin/python -m pytest workshop/tests -q`: **141 passed**
- `.venv/bin/python -m pytest -q` (repo root): **209 passed, 3 skipped** (the skips were already there)
- `node --check workshop/app.js`: OK
- `python workshop/release.py preflight`: PASS (11 files, 87,720 bytes, no network)
- Fixture-mode TestClient smoke: 6 claims (3 supported, 1 contradicted, 2 not visible, all fixture data). `video_url` is null and the HTML contains no secrets.

## Remaining limitations

- Verdicts come from keyword cues over one precomputed Cosmos caption. They are not calibrated, are not frame-level verification and do not handle negation.
- Each claim is checked against one fixed 5 s segment. Search is used only for advisory similarity.
- Live VAST behaviour (search row shape, stream Range handling, agent availability) was not re-checked in this audit. Run one live smoke before presenting.
- Real-browser rendering of the polished UI is still unverified here (see TASK-006C).
- Statements are illustrative team-authored fixtures. No fault or liability determination is produced.
