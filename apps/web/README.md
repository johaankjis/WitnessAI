# Witness web — incident review dashboard (TASK-002B)

Next.js + TypeScript + Tailwind dashboard for adjusters reviewing conflicting driver
statements against dashcam evidence. Consumes the published TASK-001 contracts only;
no API, contract, or backend files are modified from here.

## Run

```sh
cd apps/web
npm install
npm run dev
```

Open [http://localhost:3000/incidents/demo-001](http://localhost:3000/incidents/demo-001)
in a browser. The home page accepts any incident ID; `/sweep` is the archive-sweep
placeholder shell.

## Connect the backend

Start the API first (from the repo root, see root README):

```sh
python -m uvicorn witness_api.main:app --port 8000
```

The dashboard calls, in order:

1. `GET /incidents/{id}` — incident, statements, duration
2. `GET /incidents/{id}/results` — claims, verdicts, observations (409 = not analyzed yet)
3. `POST /incidents/{id}/analyze` — synchronous analysis, then re-fetch results

Default API base is `http://localhost:8000`. Override with:

```sh
NEXT_PUBLIC_WITNESS_API_BASE=http://127.0.0.1:8000 npm run dev
```

CORS on the backend already allows `localhost:3000` and `127.0.0.1:3000`.

## Fixture mode

When the API is unreachable and the incident is `demo-001`, the dashboard falls back
to bundled fixtures copied verbatim from `packages/contracts/examples/*.json`, with a
visible "Fixture mode" chip plus the Demo/Mock banner. Force it with
`?fixture=1` or `NEXT_PUBLIC_WITNESS_FIXTURE=1`. Fixture data is never presented as
fresh analysis or real inference.

## Verify

```sh
npm run typecheck   # TypeScript
npm test            # vitest: joins, API client, video seeking, claim selection
npm run build       # production build (webpack; see note below)
```

The build script uses `next build --webpack` because Turbopack CSS compilation
requires a local subprocess port unavailable in the managed environment.

## Evidence honesty rules (enforced in UI)

- `mock://` URIs render a labeled placeholder, never a `<video>` element.
- Null confidence renders "Not reported"; reported values are labeled uncalibrated.
- Detector (YOLO) observations render separately from model evidence; mock
  observations carry a "not independent corroboration" note.
- The report panel always shows human-review-required status and states that no
  legal fault determination is provided.
