# TASK-003 architecture

Composition root: `apps/api/witness_api/main.py`. `WITNESS_ANALYSIS_MODE` selects a single
coherent configuration. Pydantic v2 models in `packages/contracts` remain the only evidence
contract source; all v1 evidence models and endpoint payloads are unchanged.

Mock: FastAPI → synchronous Pipeline → deterministic claim extraction/localization/
verification → Claude MockVisionObserver → pass-through fusion → deterministic report →
atomic JSON storage. Vision runs scripted detections through its tracker and measurement
code. Its observations never modify scripted claim judgments or constitute independent
corroboration. Every source remains labeled synthetic.

Real: FastAPI → bounded single-thread job runner → LocalMedia snapshot/probe → W&B
extraction → VisionObserver → Cosmos localization/verification → pass-through fusion →
W&B constrained report → atomic storage. Vision and Cosmos consume the same captured MP4
bytes. The detector reads a temporary copy, which is removed afterward; its evidence URI
is restored to the original incident URI and provenance includes the snapshot SHA-256.
Cosmos provenance independently includes the same digest. Detector measurements remain
separate from model judgments; neither is an automatic fault determination.

Provider operations and optional model libraries are not activated by mock mode. Real
configuration requires existing local YOLO weights, preventing implicit weight downloads
through the integration path. Missing runtime/media/provider output fails analysis rather
than manufacturing successful evidence. Provider APIs remain unverified live.

The browser loads original footage from an incident-scoped API media route. URI resolution
rejects remote sources, traversal and symlink escapes outside the configured root. It
supports byte-range requests through FileResponse for browser seeking. Evidence retains
the original URI; only the player's URL changes. The operator must keep local files
immutable, as media serving reads the current original file, not persisted analysis bytes.

Jobs have four outstanding slots, one worker and 128 retained incident statuses. GET status
is read-only; repeated POST retains its earlier polling behavior. Terminal states are
sticky until restart/eviction. Jobs are in memory and do not have a hard whole-job deadline;
provider calls have finite retries/timeouts and media has size/duration limits. No durable
queue or multi-worker support is claimed. Failed jobs retain previous reports. The UI waits
for completion before fetching results, and distinguishes failures from saved reports.

Human review is always required. No archive sweep or legal fault determination is added.
