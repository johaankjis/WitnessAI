# Requested shared-contract changes (for Codex)

TASK-002A works within contract v1.0 unchanged. These requests would remove workarounds;
none have been applied. All are additive and optional, so existing fixtures stay valid.

## 1. Structured frame/track references on DetectorObservation (high)
Frame indices, track IDs and measured values currently live only in `id` and `description`
text, so the UI cannot seek to a frame or draw a track without parsing prose.

```python
class FrameSpan(Contract):
    source_fps: float = Field(gt=0)
    first_frame: int = Field(ge=0)
    last_frame: int = Field(ge=0)          # >= first_frame

class DetectorObservation(Contract):
    ...
    frames: FrameSpan | None = None
    track_ids: list[int] = Field(default_factory=list)
    measurements: dict[str, float] = Field(default_factory=dict)  # e.g. {"shift_fraction": -0.13}
```

## 2. Distinguish "not visible" from "not assessable" (high)
`visibility="not_visible"` covers both "the light was out of frame" and "braking cannot be
measured from boxes even though the car is in view". Request a third value:

```python
visibility: Literal["visible", "not_visible", "not_assessable"]
```
`ClaimVerdict.visible_basis` should treat `not_assessable` like `not_visible`.

## 3. Annotated evidence clip reference (medium)
`Pipeline` requires `evidence.video_uri == incident.video_uri`, which is right for the source,
but leaves nowhere to put the annotated overlay clip. Request on `EvidenceWindow`:

```python
annotated_clip_uri: str | None = None   # derived visual evidence; source remains video_uri
```

## 4. Incident-level event localization (medium)
`DetectorObservation.claim_id` is required, so the detector's event estimate is repeated in every
claim's observation. Request either an optional `claim_id`, or a separate model returned by a
new observer method:

```python
class EventEstimate(Contract):
    incident_id: str
    timestamp_seconds: float = Field(ge=0)
    window: EvidenceWindow
    method: str                 # e.g. "box_log_area_growth"
    provenance: Provenance
```

## 5. Media acquisition convention (medium)
`Incident.video_uri` has no defined scheme for real footage. Vision accepts absolute paths,
`file://` URIs and paths relative to a media root, and rejects `s3://`/`http(s)://`. Please
document the convention (suggest: `WITNESS_MEDIA_ROOT` + relative paths, with a separate
download step for VAST/S3 URIs).

## 6. Claim categories (low)
`AtomicClaim.category` has no `signaling`, `speed` or `collision` values, so "I signaled" claims
arrive as `other` and are answered `unsupported_claim_unknown`. Fine for now; flagging in case
the extractor starts emitting them.

## Root configuration (not contracts)
- Install `services/vision` and `evals` in the root dev environment, or add their test
  directories to root `[tool.pytest.ini_options].testpaths`.
- `evals/.gitignore` ignores `evals/results/`; no root `.gitignore` change needed.
