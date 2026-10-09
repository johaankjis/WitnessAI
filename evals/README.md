# Evaluations — Claude Code ownership

Offline event-localization evaluation against labeled `time_of_event` values (Nexar collision
dataset layout). **No benchmark exists yet.** One clip has been evaluated (below); that is a
single measurement, not an accuracy number. Fixture results in `fixtures/` are contract tests.

## What is measured
For each labeled clip the predictor returns a time in seconds or abstains. Each clip ends in
exactly one status:

| Status | Meaning | Scored? |
| --- | --- | --- |
| `evaluated` | label and prediction present | yes |
| `abstained` | predictor ran, localized nothing | no (counted) |
| `no_label` | no `time_of_event` (e.g. Nexar negatives) | no (counted) |
| `missing_video` | clip file not found | no (counted) |
| `error` | predictor raised; message recorded | no (counted) |

Metrics over **evaluated examples only**: mean signed error (prediction − label; positive = late),
mean and median absolute error, max absolute error, and within-tolerance accuracy (`|error| ≤ 1 s`
by default, inclusive). `within_tolerance_rate_including_abstentions` is also reported so
abstaining cannot inflate the headline. With zero evaluated examples all metrics are `null`.

## Run
```sh
python -m pip install -e evals            # stdlib only
# score precomputed predictions (e.g. Cosmos Reason output): {"<id>": seconds | null}
python -m witness_evals --labels path/to/train.csv --predictions preds.json --out evals/results/cosmos.json
# run the YOLO vision pipeline on <id>.mp4 files (needs services/vision[yolo])
python -m witness_evals --labels path/to/train.csv --videos path/to/videos --limit 50 --out evals/results/yolo.json
```
Options: `--ids`, `--limit` (labeled clips attempted), `--tolerance`, `--weights`, `--weave`.
The CLI prints a summary and a headline such as
"Event localized within 1s on X of Y evaluated clips; median |error| …".

Nexar IDs are kept as text so zero padding (`00822`) matches file names. Labels may use the
Kaggle layout (`id,time_of_event,...`) or the Hugging Face `train/positive/metadata.csv` layout
(`file_name,time_of_event,time_of_alert,...`; the ID is the file name without `.mp4`). Read the
dataset license (Nexar Open Data License on Hugging Face; attribution required) before use.

## Measured so far (TASK-004A, 2026-10-09)
Clip `00000.mp4` only, `witness_vision:ultralytics:yolo11n.pt@5fps`, label `time_of_event`
20.76 s, predicted 31.76 s, signed error **+11.00 s**, 0 of 1 within 1 s. The detector-based
localizer picked a different vehicle's approach at ~31.8 s; the van involved at 20.76 s was
detected as `bus`/`truck` (two short tracks), fills ~30% of the frame and is undetected after
20.3 s. Reproduce with the command in `docs/TASK-004A.md`; results are written to the gitignored
`evals/results/` or `data/local/`. Do not quote this as accuracy: n = 1 and nothing was tuned.

## Weave
`--weave` with `WITNESS_WEAVE_PROJECT=<entity>/<project>` and W&B credentials logs a
`weave.Evaluation` named `witness-event-localization`. Predictions are replayed from the local
run, so Weave shows exactly the locally reported numbers; only `evaluated` examples are sent,
and skip/abstain counts are attached as attributes. Missing package, credentials or network
produce a warning and the local report still completes.

## Tests
```sh
cd evals && python -m pytest && ruff check .
```
19 tests. The end-to-end test generates small videos and runs the real vision pipeline with a
pixel detector (skipped without OpenCV). Weave is tested with a stub; the real Weave API has
not been exercised (scorer uses the current `output` argument name).
