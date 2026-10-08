# Synthetic eval fixtures
Hand-written to exercise metric edge cases; they are **not** Nexar labels or model output,
and numbers computed from them are not accuracy results.

- `labels.csv`: Nexar column layout. `00003` is a negative (no `time_of_event`).
- `predictions.json`: `00004` abstains (null), `00006` is absent (counts as an error),
  `00003` has a prediction but no label, so it is skipped.

Expected: 3 evaluated (errors -0.4, +2.3, 0.0 s), 2 within 1 s, median |error| 0.4 s.
