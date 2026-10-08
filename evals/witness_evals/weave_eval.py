"""Optional W&B Weave evaluation logging.

Runs only when WITNESS_WEAVE_PROJECT (or an explicit project) is set and the `weave`
package imports and initializes. Predictions are computed once by evaluate_localization
and replayed into Weave, so the leaderboard shows exactly the locally reported numbers.
Only `evaluated` examples are sent; skipped/abstained counts are attached as attributes."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from .metrics import ExampleResult, score

logger = logging.getLogger(__name__)


def log_to_weave(results: list[ExampleResult], predictor_name: str, summary: dict[str, Any],
                 tolerance: float = 1.0, project: str | None = None) -> dict[str, Any] | None:
    project = project or os.getenv("WITNESS_WEAVE_PROJECT")
    if not project:
        logger.info("WITNESS_WEAVE_PROJECT not set; skipping Weave evaluation")
        return None
    evaluated = [r for r in results if r.status == "evaluated"]
    if not evaluated:
        logger.warning("no evaluated examples; nothing to log to Weave")
        return None
    try:
        import weave
        weave.init(project)
        predictions = {r.id: r.predicted_seconds for r in evaluated}

        @weave.op(name="replayed_prediction")
        def model(id: str) -> float:  # noqa: A002 - matches dataset column
            return predictions[id]

        @weave.op(name="localization_error")
        def localization_error(time_of_event: float, output: float) -> dict[str, Any]:
            return score(time_of_event, output, tolerance)

        evaluation = weave.Evaluation(
            name="witness-event-localization",
            dataset=[{"id": r.id, "time_of_event": r.label_seconds} for r in evaluated],
            scorers=[localization_error])
        with weave.attributes({"predictor": predictor_name, "tolerance_seconds": tolerance,
                               "n_abstained": summary["n_abstained"], "n_error": summary["n_error"],
                               "n_missing_video": summary["n_missing_video"]}):
            return asyncio.run(evaluation.evaluate(model))
    except Exception as exc:  # missing package, credentials, network or API drift
        logger.warning("Weave evaluation skipped: %s", exc)
        return None
