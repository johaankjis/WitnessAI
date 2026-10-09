# TASK-004A completion report — real YOLO inference on Nexar clip 00000

Branch `feature/task-004-real-video`, 2026-10-09. Computer-vision lead (Claude Code).
Scope: validate real, non-mock YOLO inference on one real dashcam clip and expose that clip
through the existing API and dashboard. No provider (W&B, Cosmos) calls were made; no verdicts
were produced; nothing here is a fault determination. Human review is required throughout.

## Result in one paragraph

A pretrained YOLO11n model (Ultralytics 8.4.174, PyTorch 2.14.1, CPU) ran on every frame of
`data/local/nexar/train/positive/00000.mp4` (1280x720, 28.9 fps, 1158 frames, 40.069 s). It
produced 3,296 vehicle/traffic-light detections grouped into 75 IoU tracks, exported as
timestamped JSON/CSV with provenance, and a full-rate annotated MP4 (boxes, track IDs, scores,
frame index and timestamp on every frame). A separate real incident `nexar-00000` is served by
the API, including the original MP4 with byte ranges, and the dashboard plays and seeks it in
Chrome. Against the dataset label (`time_of_event` 20.76 s) the detector-only event localizer
was wrong by **+11.0 s** on this clip. That is a measured negative result on n = 1, reported
as-is.

## Branch state found before starting (important)

Merge commit `4b352d7` ("merge: integrate TASK-003 into main") has the **same tree as its first
parent** `3c24b94`: the TASK-003 work (media route, status route, VisionObserver wiring, root
test paths, dashboard media URL and seek fix) was dropped by the merge. HEAD had no media
endpoint at all. The TASK-003 diff (`3c24b94..71b4797`, the `integration/task-003` branch)
applied cleanly, so it is re-applied on this branch as its own commit before the TASK-004A
changes. After the restore the root suite passes (174 passed, 1 expected skip) and the web
suite passes (27 tests, typecheck clean). Codex/Muse should confirm the restore is what they
intended; nothing in it was modified.

## Environment

| Item | Value |
| --- | --- |
| Python | 3.14.7 in `.venv` (existing) |
| Installed for this task | `pip install -e 'services/vision[yolo,dev]' -e evals` → ultralytics 8.4.174, torch 2.14.1, torchvision 0.29.1, ruff 0.16.10 (OpenCV 5.0.0.93 and numpy 2.5.3 were present) |
| Weights | `yolo11n.pt` (5,613,764 bytes, sha256 `0ebbc80d…44ee1`), downloaded once by Ultralytics from the official release to gitignored `data/local/models/` |
| Device | CPU (default). MPS is available and ~2x faster (`--device mps`) but CPU was used for reproducibility |
| ffprobe/ffmpeg | Homebrew, present |
| Video | sha256 `9b7364178cb8b6194db0ee0f96df0ad44615fc265efe435297394dcf6a9be5f9`, matches the Hugging Face download record |
| Label | `train/positive/metadata.csv` (gated dataset; fetched with the operator's existing Hugging Face login): `time_of_event` 20.76 s, `time_of_alert` 19.136 s, Normal/Clear/Urban |

Metadata confirmed with ffprobe and OpenCV before any change: h264 1280x720, `289/10` fps,
`nb_frames` 1158, duration 40.069204 s.

## Baseline (before changes)

| Suite | Result |
| --- | --- |
| `python -m pytest` (root, API only on HEAD) | 115 passed |
| `services/vision`: `python -m pytest` | 31 passed |
| `evals`: `python -m pytest` | 16 passed |

## What changed (source only; outputs, weights and footage are not committed)

Vision (`services/vision`, Claude Code area):
- `sources.py`: fixed a real bug hit on first use: a relative video path raised
  `ValueError: relative paths can't be expressed as file URIs`.
- `export.py` (new): per-detection export (`witness-vision/detections@1`) with provenance
  (adapter, detector, weights name + sha256, video URI + sha256, fps, device, thresholds), track
  summaries, event estimate, and one row per detection; JSON and CSV writers.
- `annotate.py`: `write_annotated_video()` for all sampled frames (track ID, class, score,
  frame/timestamp header, human-review footer); tries H.264 `avc1`, falls back to `mp4v`;
  `write_annotated_clip()` now delegates to it. Writing a video no longer appends to the
  analysis warnings (that text was leaking into evidence descriptions).
- `__main__.py`: `analyze` gained `--out`, `--detections-out`, `--detections-csv`,
  `--video-out`, `--device`; new `observe` subcommand runs the real `VisionObserver` on an
  Incident JSON plus claims JSON and writes `DetectorObservation[]`.
- Tests: `test_export.py` (7, synthetic), `test_real_video.py` (5: incident record always;
  footage/API-media/YOLO checks opt-in via local files). `.gitignore` ignores `*.pt`.

Evals (`evals`, Claude Code area):
- `labels.py` accepts the Hugging Face `metadata.csv` layout (`file_name` → ID).
- `tests/test_labels_metadata.py` (3). README records the single measured result.

Data/docs: `data/real/nexar-00000.json` (real incident, `is_mock=false`),
`data/real/nexar-00000.claims.json` (hand-written claims standing in for the extractor),
`data/real/README.md` (provenance, license, download), this report, README updates.
The two driver statements are **sample text written by the team**, labelled as such in the
incident title; they are inputs to be checked, not evidence.

Nothing under `apps/api`, `apps/web`, `packages/contracts` or root configuration was changed
beyond the TASK-003 restore. Cosmos and W&B adapters were not touched.

## Runs and measured results

All commands from the repository root with `WITNESS_YOLO_WEIGHTS=$PWD/data/local/models/yolo11n.pt`
and `O=data/local/task-004a` (gitignored). Wall-clock on an Apple-silicon laptop, CPU.

| Run | Command | Time | Output |
| --- | --- | --- | --- |
| Dense (every frame) | `analyze … --sample-fps 28.9 --detections-out --detections-csv --video-out` | 47.7 s | 1158 frames sampled, 3,296 detections (car 1472, traffic light 945, truck 467, bus 374, motorcycle 38), 75 tracks, 10,741 boxes below 0.35 dropped; `nexar-00000.annotated.mp4` 1158 frames at 28.9 fps, H.264 |
| Measurement (default 5 fps) | `analyze … --detections-out --clip-out` | 9.9 s | 193 frames (every 6th, 4.817 fps effective), 490 detections, 38 tracks; event clip 14 frames |
| Adapter | `observe --incident data/real/nexar-00000.json …` | 9.9 s | 6 contract-valid `DetectorObservation`s, `is_mock=false`, adapter `witness-vision`, event clip written |
| Evaluation | `python -m witness_evals --labels …/metadata.csv --videos … --ids 00000` | 9.2 s | 1 evaluated, error +11.00 s, 0 of 1 within 1 s |

Detection sanity checks: the first smoke frame (frame 500) returned persons, traffic lights
and a truck; the annotated frame at 19.52 s boxes the U-Haul van as `#20 bus 0.86`; at 31.76 s
a car on the left is boxed. Tracks are monotone in frame index, confined to sampled frames,
IDs start at 1 and are never reused (verified by the opt-in tests).

### Event localization versus the label

| | Seconds |
| --- | --- |
| Label `time_of_event` | 20.76 |
| Detector estimate at 5 fps (fastest log-area growth, track 49, frame 918) | 31.76 |
| Detector estimate at 28.9 fps (track 72, frame 855) | 29.58 |
| Signed error at 5 fps | +11.00 |

Why it missed, from the exported detections (not speculation): the van involved at the labeled
time is the only vehicle near the camera between 17 and 23 s. It appears as two short tracks
because YOLO's class flips (`bus` 17.6–20.3 s, 9 detections; `truck` 18.9–20.1 s, 7
detections) and the tracker associates within a class only. Its box reaches ~30% of the frame
with `x1 ≈ 1`, i.e. clipped at the left edge, so apparent growth is suppressed, and after
20.3 s it is not detected at ≥ 0.35 confidence at all (it fills the left half of the image at
very close range; see the 20.76 s frame). The maximum growth signal is instead a car passing
on the left around 31.8 s. Consequences:
- The detector observation windows for the real incident centre on 29.8–32.8 s, not the
  labeled event. The descriptions say exactly which track and frames they refer to and that
  the measurement is image-space only, so they are honest, but a reviewer must not read the
  "event window" as the incident window.
- The projects.md fallback ("localize with YOLO") does not hold on this clip as implemented.
  Candidate fixes to measure, not assume: class-agnostic association for vehicle tracks,
  growth of box area that also counts edge-clipped boxes, a lower confidence floor for very
  large boxes, or using `time_of_alert`-style precursors. None were applied.

### Evidence-boundary check on the real observations

| Claim | Label | Visibility | Window (s) |
| --- | --- | --- | --- |
| c1 lane change (van) | `vehicle_lateral_image_shift` | visible | 29.90–31.76 |
| c2 braking | `braking_unknown` | not_visible | 29.76–32.76 |
| c3 light turned green | `traffic_light_not_visible` | not_visible | 29.76–32.76 |
| c4 stayed in lane | `vehicle_lateral_image_shift` | visible | 29.90–31.76 |
| c5 my light was green | `traffic_light_not_visible` | not_visible | 29.76–32.76 |
| c6 sped up (other) | `unsupported_claim_unknown` | not_visible | 29.76–32.76 |

`confidence` is `null` on all six; braking is never inferred from boxes; absent lights are
`not_visible`; the lateral-shift observations state they are image-space motion of a specific
track and "not by itself a lane-change determination". Traffic-light colour reads on this night
clip are mixed (`red`/`yellow` on the same intersection lights at 0–18 s) and were not
validated; they should be treated as unverified until checked against frames.

## API and dashboard verification

API started as `WITNESS_ANALYSIS_MODE=mock`, `WITNESS_INCIDENT_PATH=data/real/nexar-00000.json`,
`WITNESS_MEDIA_ROOT=data/local/nexar` on port 8001 (8000 was in use by an older process).

| Request | Response |
| --- | --- |
| `GET /health` | 200, `analysis_mode: mock` |
| `GET /incidents/nexar-00000` | 200, `is_mock: false`, `video_uri: train/positive/00000.mp4` |
| `GET /incidents/nexar-00000/media` | 200 `video/mp4`, 12,237,783 bytes, sha256 identical to the source file |
| `Range: bytes=0-1023` | 206, `content-range: bytes 0-1023/12237783`, `accept-ranges: bytes` |
| `Range: bytes=99999999-` | 416 |
| `GET …/results`, `GET …/status` | 409 (no report; nothing fabricated) |
| `POST …/analyze` (mock mode) | 500 "Analysis failed; no new report committed" — mock adapters refuse a real incident, as intended |
| `GET /incidents/demo-001` | 404 (storage serves one incident file at a time; see limits) |

Dashboard: `apps/web` built with `NEXT_PUBLIC_WITNESS_API_BASE=http://127.0.0.1:8001` and
served on port 3001; opened `http://localhost:3001/incidents/nexar-00000` in Chrome. The page
loads the real incident, shows "Not analyzed", and renders a `<video>` whose `src` is the API
media route. Verified in the live page: `duration` 40.069204, `videoWidth/Height` 1280x720,
`readyState` 4; playback advanced 20.76 → 22.67 s in 2 s; programmatic seeks to 20.76 s and
35.5 s each fired `seeked` with exact `currentTime`, and the readout showed `0:20.7 / 0:40.0`
then `0:35.5 / 0:40.0`. The API log shows nine 206 range responses for the browser's media
requests. Screenshot (not committed): `data/local/task-004a/dashboard-nexar-00000-seek-20.76s.jpg`.
Chrome defers media loading in a background tab, so `preload="metadata"` only fetched once the
tab was active/played; that is browser behaviour, not an app defect.

Claim-driven seeking (click a claim → seek to its window) could not be exercised on the real
incident because no report exists for it without providers; it remains covered by the TASK-003
component tests on demo data.

## Tests after changes

| Suite | Result |
| --- | --- |
| `python -m pytest` (root: API + vision + evals) | 187 passed, 3 skipped (ultralytics-present skip + 2 YOLO opt-ins) |
| `services/vision`: `python -m pytest` | 40 passed, 3 skipped; `ruff check .` clean |
| `services/vision/tests/test_real_video.py` with weights + clip | 5 passed (real inference, ~9 s) |
| `evals`: `python -m pytest` | 19 passed; `ruff check .` clean |
| `apps/web`: `npm test`, `npm run typecheck`, `npm run build` | 27 passed, clean, built |

Tests use temp storage and no network. The opt-in real-footage tests skip unless the clip and
local weights are present.

## Exact local run commands

```sh
cd /Users/jkathila/Desktop/work/WitnessAI && source .venv/bin/activate
python -m pip install -e '.[dev]' -e 'services/vision[yolo,dev]' -e evals   # once
# footage + labels (gated dataset; accept the license on Hugging Face, `hf auth login`)
python - <<'EOF'
from huggingface_hub import hf_hub_download
for f in ["train/positive/00000.mp4", "train/positive/metadata.csv", "LICENSE"]:
    hf_hub_download("nexar-ai/nexar_collision_prediction", f, repo_type="dataset", local_dir="data/local/nexar")
EOF
mkdir -p data/local/models && python -c "from ultralytics import YOLO; YOLO('data/local/models/yolo11n.pt')"  # downloads once
export WITNESS_YOLO_WEIGHTS=$PWD/data/local/models/yolo11n.pt O=data/local/task-004a V=data/local/nexar/train/positive/00000.mp4
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,nb_frames,duration -of compact $V

python -m witness_vision analyze $V --sample-fps 28.9 --out $O/dense.analysis.json \
  --detections-out $O/dense.detections.json --detections-csv $O/dense.detections.csv \
  --video-out $O/nexar-00000.annotated.mp4
python -m witness_vision analyze $V --out $O/5fps.analysis.json \
  --detections-out $O/5fps.detections.json --clip-out $O/5fps.event-clip.mp4
python -m witness_vision observe --incident data/real/nexar-00000.json \
  --claims data/real/nexar-00000.claims.json --media-root data/local/nexar \
  --out $O/nexar-00000.observations.json --analysis-out $O/nexar-00000.observe-analysis.json --clip-dir $O/clips
python -m witness_evals --labels data/local/nexar/train/positive/metadata.csv \
  --videos data/local/nexar/train/positive --ids 00000 --weights $WITNESS_YOLO_WEIGHTS --out $O/eval-00000.json

python -m pytest                                               # root
python -m pytest services/vision/tests/test_real_video.py      # opt-in real-footage checks

# API + dashboard with the real incident
WITNESS_ANALYSIS_MODE=mock WITNESS_INCIDENT_PATH=$PWD/data/real/nexar-00000.json \
  WITNESS_MEDIA_ROOT=$PWD/data/local/nexar WITNESS_DATA_DIR=$PWD/data/local/reports-real \
  python -m uvicorn witness_api.main:app --host 127.0.0.1 --port 8000 --workers 1
curl -s -o /dev/null -w '%{http_code} %{size_download}\n' -H 'Range: bytes=0-1023' http://127.0.0.1:8000/incidents/nexar-00000/media
npm run dev --prefix apps/web      # open http://localhost:3000/incidents/nexar-00000
```

## Limits and recommended next steps (not done here)

- Storage serves a single incident file (`WITNESS_INCIDENT_PATH`), so demo-001 and
  nexar-00000 cannot be served at once. A directory-backed `JsonStorage` is a Codex change.
- A real report for nexar-00000 needs the W&B extractor and Cosmos verifier (credentials,
  endpoints). Real mode also requires `WITNESS_YOLO_WEIGHTS`; this run shows the detector side
  works end to end through `VisionObserver`, including the snapshot path tested in TASK-003.
- The detector localizer failed on this clip (+11.0 s). Evaluate on the 20–50 labeled clips
  before relying on it as the Cosmos fallback, and try class-agnostic association for
  vehicles. Keep abstentions counted; do not tune on this single clip.
- Traffic-light colour estimates need a frame-level check on night footage.
- Contract requests in `services/vision/CONTRACT_REQUESTS.md` still apply: frame/track fields
  and an annotated-clip URI would let the dashboard show the overlay and seek to detector
  frames without parsing descriptions.
- Dataset use is under the Nexar Open Data License (attribution, no resale, no
  re-identification); the clip, label CSV and derived outputs stay out of git.
