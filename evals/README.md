# Evaluations — Claude Code ownership

Offline event-localization evaluation against labeled `time_of_event` values (Nexar collision
dataset layout). **No benchmark has been run yet; no accuracy number exists.** Fixture results
in `fixtures/` are contract tests, not model accuracy.

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

Nexar IDs are kept as text so zero padding (`00822`) matches file names. Check the Kaggle
competition terms before downloading clips.

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
16 tests. The end-to-end test generates small videos and runs the real vision pipeline with a
pixel detector (skipped without OpenCV). Weave is tested with a stub; the real Weave API has
not been exercised (scorer uses the current `output` argument name).
