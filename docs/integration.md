# Integration contract v1.0
Canonical models: packages/contracts/witness_contracts/models.py. Each model has a standalone
JSON Schema (with local $defs) under schemas/ and a validated example under examples/.
IncidentReport.json includes all three verdict values. openapi.json defines the HTTP API.
Regenerate with `python scripts/export_contracts.py` after installing the root package.

| Route | Success | Other behavior |
| --- | --- | --- |
| GET /health | 200, status and analysis_mode | No provider checks |
| GET /incidents/{id} | 200 Incident | 404 unknown |
| POST /incidents/{id}/analyze | 200 AnalysisStatus | 404 unknown, 500 pipeline/storage failure |
| GET /incidents/{id}/results | 200 IncidentReport | 404 unknown, 409 not analyzed |

Errors use FastAPI's `{"detail": "..."}` shape. No request body is needed for POST.
Demo ID is demo-001. CORS defaults to http://localhost:3000 and http://127.0.0.1:3000;
override WITNESS_CORS_ORIGINS with comma-separated exact origins.

## Muse
Use report claims' statement_id to join to driver statements; verdicts join by claim_id.
Timestamps are seconds relative to the video start; end must exceed start and stay within
the incident duration. Display supported, contradicted and not_visible separately.
Display explanation, uncertainty, provenance, human-review requirement and mock banner.
Do not render mock:// as playable footage. Confidence can be null; it is not a fault score.
POST completes synchronously; then fetch results. Handle 409 before first analysis.

## Claude Code
Implement YoloObserver.observe(incident, claims) in services/vision against the Protocol
in apps/api/witness_api/interfaces.py. Return typed DetectorObservation records, each with
claim_id, label, timestamped EvidenceWindow, provenance and optional confidence.
Do not infer traffic-light state from an invisible signal or equate absent detections with
contradiction. Real adapters must derive evidence from actual media and set is_mock=false;
never relabel fixture data. The current composition root supports the mock demo only.
Coordinate any new measurements or serving contracts with Codex. Keep evals offline and
separate measured accuracy from scripted fixture results. No evaluation score exists yet.

## Adapter replacement
ClaimExtractor.extract, VideoLocalizer.localize, ClaimVerifier.verify, YoloObserver.observe,
EvidenceFusion.fuse, ReportGenerator.generate and Storage are synchronous Python Protocols.
Construct a Pipeline with replacements and inject it plus Storage into create_app. Real
adapters need separate media acquisition and failure policy work before activation.
