# TASK-006C — Witness Workshop UI Polish

Completed locally on `feature/task-005-vast-workshop`. Frontend-only polish of the
deployed workshop application for the VAST Builders Challenge demo. No backend
evidence-verification logic, VSS validation, authentication, API contracts, or
`apps/api` / `apps/web` code was changed. No live VAST cluster was contacted.
No deployment was performed.

The `design-reference/` screenshots are dashcam footage stills (including a YOLO
detection-overlay frame), not UI mockups, so they were used as domain guidance:
the polished UI keeps the video frame as the focal point and surfaces detector
measurements next to the footage they describe.

## Changes (`index.html`, `styles.css`, `app.js` only)

- Dashboard hierarchy: brand header with evidence chips plus a verdict-count
  summary (Supported / Contradicted / Not visible / total), status bar with
  primary "Reload evidence" and secondary "Reload + scoped agent notes" actions,
  then video stage, claim inspector, statement claim cards, and footer notes.
- Video is the focal point: larger 16:9 stage, evidence-window caption, and a
  live playback-position readout. Fixture mode still hides the player and shows
  an explicit no-footage notice instead of fabricating video.
- Claim cards are real `<button>` elements with verdict badge (icon + words, not
  color alone) and per-claim timestamps (`clip Xs · video Ys`). Timeline markers
  are sorted by seek time with the same dual timestamps and keyboard focus.
- Inspector separates Observed evidence (verdict rationale with cue chips,
  Cosmos `reasoning_content`, YOLO measurements as a labeled grid with a raw
  `<details>` fallback) from Advisory synthesis (search similarity, scoped agent
  note), each tagged and styled distinctly; a static legend explains the split.
- Disclaimers stay prominent: top banner, fixture/VAST mode chip, per-statement
  "Illustrative · team-authored" tags, and a footer restating human-review
  requirement, no binding liability, advisory-only synthesis, and disabled W&B
  inference.
- Accessibility and responsive: skip link, landmarks, `aria-live` status,
  `aria-pressed`/`aria-current` selection, visible focus rings,
  `prefers-reduced-motion`, icon+text verdicts; layouts stack at 1080px and 720px
  for projector/laptop presentation. Keyboard: Tab/Enter, arrow keys between
  claims, number keys 1–6 to jump.
- No new network calls, endpoints, or response fields are used; every rendered
  value comes from the existing `/api/review` contract.

## Validation

- `node --check workshop/app.js`: passed.
- `workshop/.venv/bin/python -m pytest workshop/tests -q`: **141 passed**.
- `.venv/bin/python -m pytest -q`: **209 passed, 3 skipped** (pre-existing skips).
- UI smoke via TestClient (`/tmp/task006c_smoke.py`, not committed): all
  required element IDs present; disclaimers, legend, skip link, and verdict CSS
  states found; no bearer/password text in HTML; fixture review returns 6
  claims + 6 timeline markers with `human_review_required`, no video URL,
  inactive W&B, and synthetic agent notes on `?include_agent=true`.
- `workshop/release.py preflight`: passed, no network; 11 runtime files,
  87,720 serialized bytes (within ConfigMap budget).
- `git diff --check`: passed.
- Browser rendering is unverified: the sandbox forbids local socket binding, so
  no live browser session was run; review the UI with `sh workshop/start-mac.sh`
  and open http://127.0.0.1:8080 before presenting.
