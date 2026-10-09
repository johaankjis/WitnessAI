# TASK-006B — Synchronize live VAST fixes

Completed locally on `feature/task-005-vast-workshop`. No private VAST service,
cluster, or live deployment was contacted, restarted, modified, or redeployed.
The operator reported `team-6/witness-app` revision 4 working with HTTP 200,
mode `vast`, synthetic false, six reviews and six timeline markers. These are
operator-supplied observations, not live checks performed by this task.

## Changes

- Metadata source remains an exact Team 6 match; the existing finite 25–30 second
  timestamp checks are unchanged.
- YOLO `source` must be `yolo11_coco`. Footage comes from `segment_source`, which
  must equal the fixed Team 6 segment or its exact legacy Team A mapping:
  `s3://team-a-vss-chunks-segments/segments/20261001_062538_set02_video_chunk_0017_segment_006_of_006.mp4`.
- Metadata must identify the operator-confirmed sidecar:
  `s3://team-6-vss-chunks-segments/detections/20261001_062538_set02_video_chunk_0017_segment_006_of_006.json.gz`.
  If detections also provide `detection_sidecar_uri`, it must match exactly.
- Metadata and detection counts must be equal nonnegative integers (booleans,
  missing values, strings and floats rejected). The observed pair of 2,380 is
  covered by regression tests; counts are compared, not hard-coded as evidence.
- Unrelated sources, altered filenames/paths, unexpected buckets, sidecar/count
  mismatches and mixed synthetic evidence fail with HTTP 502. No input identifiers
  are rewritten. Reviews expose original detector, segment and metadata sidecar
  identifiers for audit. The sidecar variable is defined locally before use,
  with API regressions covering the previously observed `anchor_sidecar` NameError.
- Release plans explicitly pin `VSS_URL` to
  `http://video-backend-service.team-6.svc.cluster.local:8000`, overriding stale
  URL values or Secret references. Username/password remain Secret references.
  VM preflight rejects other URLs. Deployment mode remains explicitly `vast`;
  invalid credentials/configuration cannot silently select fixtures.
- Updated deployment guide, environment example and `deployment-env.json` template
  are included in the allowlisted release. Fixture development remains available.
  No changes to `apps/api`, `apps/web` or shared contracts were needed.

## Validation

- `workshop/.venv/bin/python -m pytest workshop/tests -q`: **141 passed**.
  Tests block network access and use mocked VSS responses. Coverage includes
  accepted direct/legacy sources, optional echoed sidecar, audit preservation,
  strict rejection cases, six-review output, fixture mode and stale deployment URLs.
- `.venv/bin/python -m pytest -q -rs`: **209 passed, 3 skipped**. One skip covers
  the absent-dependency scenario when ultralytics is installed; two require local
  Nexar footage and YOLO weights.
- `.venv/bin/python scripts/export_contracts.py`: succeeded; no generated changes.
- `.venv/bin/python workshop/release.py preflight`: passed, no network;
  11 runtime files, 71,424 serialized bytes.
- Release packaging, archive SHA-256, extracted per-file manifest verification and
  byte-for-byte reproducibility verified locally. Package:
  `/tmp/witness-workshop-task-006b.tar`, with adjacent `.sha256` checksum file.
- `git diff --check`: passed.

## Remaining limitations

This is offline synchronization, not fresh verification of the live service or
cluster. Compatibility is intentionally restricted to one observed footage mapping
and sidecar. Equal counts and matching identifiers are provenance consistency
checks, not cryptographic proof of video content. Missing detections remain
unavailable evidence, never contradiction. Dependency deprecation warnings remain
under Python 3.14 (Starlette/AnyIO and asyncio).

The workshop uses conservative caption/cue matching, not calibrated verification.
Human review and no-fault disclaimers remain in place. W&B inference is inactive.
