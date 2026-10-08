# Vision engine (TASK-002A) — Claude Code ownership

Frame sampling, vehicle/traffic-light detection, IoU tracking and detector measurements,
mapped onto the shared `DetectorObservation` contract through the TASK-001
`YoloObserver.observe(incident, claims)` Protocol (`apps/api/witness_api/interfaces.py`).

```
video ─▶ OpenCVFrameSource ─▶ Detector (YOLO) ─▶ IoUTracker ─▶ measurements ─▶ ObservationBuilder ─▶ DetectorObservation[]
mock  ─▶ SyntheticFrameSource ─▶ ScriptedDetector ┘   (same tracker, measurements and mapping)
```

| Module | Role |
| --- | --- |
| `sources.py` | URI → local path, OpenCV decode, frame sampling, missing-frame accounting |
| `detectors.py` | `UltralyticsDetector` (COCO vehicles + traffic lights), lazy import |
| `tracking.py` | Deterministic greedy IoU tracker, stable never-reused track IDs |
| `measurements.py` | Event localization (box log-area growth), lateral shift, scale change, conservative HSV signal colour |
| `observations.py` | Contract mapping and evidence-boundary rules |
| `adapter.py` | `VisionObserver` (real footage) and `MockVisionObserver` (synthetic) |
| `annotate.py` | Event clip extraction and annotated evidence clips |
| `mock.py` | Scripted synthetic scenes; `demo_lane_change_scene` matches demo-001 |
| `tracing.py` | Optional W&B Weave tracing |

## Evidence rules
- **One observation per claim.** Every claim gets an explicit detector answer.
- **Only geometry is ever `visible`.** Reported measurements: lateral image shift of a tracked
  vehicle (`vehicle_lateral_image_shift`) and a traffic-light colour estimate
  (`traffic_light_color_estimate_<colour>`). Descriptions state what the measurement does *not*
  establish (camera motion, lane markings, which driver a light governs).
- **Never inferred from boxes:** braking (`braking_unknown`), turn signals and other claim
  types (`unsupported_claim_unknown`), and traffic-light *changes* (mixed colour reads → unknown).
- **Unseen is unknown.** No light detected → `traffic_light_not_visible`; unreadable colour →
  `traffic_light_state_unknown`; small shift → `lane_change_unknown` ("inconclusive, not evidence
  of no lane change"). All are `not_visible`, so the contract forbids using them to contradict.
- **`confidence` is always `null`.** Detector scores are not claim probabilities.
- **Mock is labelled.** Mock provenance is `is_mock=true`, adapter `witness-vision-mock`, and every
  description starts with `SYNTHETIC, no footage analyzed.` The mock only accepts `is_mock`
  incidents with `mock://` URIs; the real observer refuses them.

## Units and identity
- Timestamps: float seconds from video start, computed as `source_frame_index / fps`
  (constant-frame-rate assumption). Window bounds are clamped to
  `[0, min(video duration, incident.duration_seconds)]` and rounded to the microsecond.
- Frame indices are 0-based indices into the *source* stream, never into the sampled subset.
  Sampling takes every `round(fps / sample_fps)`th frame; the effective rate is recorded.
- Track IDs start at 1, are assigned deterministically and never renumbered.
- Contracts have no fields for these, so they appear in the observation `id`
  (`vision-<claim>-<label>[-track<N>]`) and description (`[sampled frames 92-122 (16 @ 5 fps)]`).
  See [CONTRACT_REQUESTS.md](CONTRACT_REQUESTS.md).

## Failure handling
| Situation | Behaviour |
| --- | --- |
| `mock://`, `s3://`, `http(s)://` URI, unknown extension, missing file | `UnsupportedVideoError` |
| OpenCV cannot open, or fps is 0/NaN/absurd | `UnsupportedVideoError` |
| No frame decodes | `VideoDecodeError` |
| Individual frames fail to grab/decode | Recorded in `missing_frames`, never interpolated; warning if >20% missing |
| Stream shorter than reported | Frame count corrected, warning added |
| Non-increasing timestamps | Frame skipped, warning added |
| Detection below `min_confidence` (0.35) | Dropped and counted (`low_confidence_dropped`) |
| Track shorter than 3 hits | Ignored as noise |
| No growth above threshold | `event = null`; whole clip reviewed, all observations `not_visible` |
| OpenCV / Ultralytics not installed | `OptionalDependencyError` with install hint |
| Detector alters frame index/timestamp | `ValueError` |

Warnings are prefixed onto real-observation descriptions. Errors propagate; the TASK-001 API
turns them into HTTP 500 and keeps the previous report.

## Install and runtime requirements
Python ≥ 3.11 (tested on 3.14.6). From the repository root:

```sh
python -m pip install -e . -e 'services/vision[dev]'            # mock mode: pydantic only
python -m pip install -e 'services/vision[video]'                # + OpenCV/numpy: decode, clips, colour read
python -m pip install -e 'services/vision[yolo]'                 # + Ultralytics (pulls PyTorch)
python -m pip install -e 'services/vision[weave]'                # + W&B Weave tracing
```

| Mode | Needs | Network | GPU |
| --- | --- | --- | --- |
| Mock | pydantic | no | no |
| Real decode/annotation | opencv-python-headless ≥ 4.9 (tested 5.0.0.93), numpy | no | no |
| YOLO detection | ultralytics ≥ 8.3, torch | first use downloads `yolo11n.pt` (~5 MB) unless `WITNESS_YOLO_WEIGHTS` is a local file | optional (`WITNESS_YOLO_DEVICE=cuda:0`) |
| Weave tracing | weave, W&B login or `WANDB_API_KEY` | yes | no |

Environment variables (all optional): `WITNESS_YOLO_WEIGHTS`, `WITNESS_YOLO_DEVICE`,
`WITNESS_VISION_SAMPLE_FPS` (default 5), `WITNESS_VISION_MIN_CONFIDENCE` (default 0.35),
`WITNESS_WEAVE_PROJECT` (enables tracing; unset = no Weave import at all).

Rough cost: a 40 s, 30 fps Nexar clip at 5 fps is ~200 YOLO calls; with `yolo11n` on CPU expect
tens of seconds per clip (not benchmarked here).

## Integration with apps/api (for Codex)
Mock demo — swap only the observer in the composition root (`apps/api/witness_api/main.py`):

```python
from witness_vision.adapter import MockVisionObserver
runner = pipeline if pipeline is not None else Pipeline(mock, mock, mock, MockVisionObserver(), mock, mock)
```

The resulting `IncidentReport` validates (covered by `tests/test_mock_observer.py::test_plugs_into_task001_pipeline`).
`EvidenceFusion` currently ignores observations, which is correct for mock data.

Real footage — `VisionObserver(media_root=Path(...), clip_dir=Path(...))` for an incident with
`is_mock=false` and a local `video_uri` (absolute path, `file://` URI, or path relative to
`media_root`). Two constraints from TASK-001 apply:
1. `IncidentReport` requires every provenance `is_mock` to equal the report's, so the real
   observer can only be wired together with real extractor/localizer/verifier adapters.
2. `Pipeline` requires `evidence.video_uri == incident.video_uri`, so annotated clips cannot be
   referenced in the contract; their path is exposed as `observer.last_clip`.

Root configuration needed for merged CI (not changed here; owned by Codex): install
`services/vision` (and `evals`) in the root environment, or add their `tests/` to the root
pytest `testpaths`. The root `pythonpath` already covers `packages/contracts` and `apps/api`.

## CLI and examples
```sh
python -m witness_vision analyze clip.mp4 --clip-out out/event.mp4     # needs [yolo]
python -m witness_vision export-examples                              # regenerate examples/
```
`examples/` holds the deterministic mock output for demo-001: claims, observations
(`DetectorObservation[]`) and the full internal analysis. They are synthetic and a test asserts
they match the current mock exactly.

## Tests and lint
```sh
cd services/vision && python -m pytest && ruff check .
```
31 tests; video-path tests skip automatically without OpenCV. No test downloads weights or
touches the network (YOLO is exercised through an injected fake model and a pixel detector).
