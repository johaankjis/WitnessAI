"""Localization metrics computed only from examples that were actually evaluated.

An example is *evaluated* when it has a label time and the predictor returned a time.
Skipped examples (no label, missing video, predictor error) and abstentions (predictor ran
but localized nothing) are counted and reported, never scored as zero error. With no
evaluated examples every metric is None rather than a misleading 0."""
from __future__ import annotations

import statistics
from dataclasses import asdict, dataclass
from typing import Any, Literal

Status = Literal["evaluated", "abstained", "no_label", "missing_video", "error"]


@dataclass(frozen=True)
class ExampleResult:
    id: str
    status: Status
    label_seconds: float | None = None
    predicted_seconds: float | None = None
    detail: str = ""

    @property
    def signed_error(self) -> float | None:
        if self.status != "evaluated":
            return None
        return self.predicted_seconds - self.label_seconds  # type: ignore[operator]

    def to_dict(self) -> dict[str, Any]:
        out = asdict(self)
        err = self.signed_error
        out["signed_error_seconds"] = err
        out["abs_error_seconds"] = None if err is None else abs(err)
        return out


def score(label_seconds: float, predicted_seconds: float, tolerance: float = 1.0) -> dict[str, float | bool]:
    """Per-example scorer (also used as the Weave scorer)."""
    err = predicted_seconds - label_seconds
    return {"signed_error": err, "abs_error": abs(err), "within_tolerance": abs(err) <= tolerance}


def summarize(results: list[ExampleResult], tolerance: float = 1.0) -> dict[str, Any]:
    evaluated = [r for r in results if r.status == "evaluated"]
    counts = {s: sum(r.status == s for r in results)
              for s in ("evaluated", "abstained", "no_label", "missing_video", "error")}
    attempted = counts["evaluated"] + counts["abstained"]  # labeled clips the predictor actually ran on
    summary: dict[str, Any] = {"n_examples": len(results), **{f"n_{k}": v for k, v in counts.items()},
                               "tolerance_seconds": tolerance}
    if not evaluated:
        summary.update(mean_signed_error_seconds=None, mean_abs_error_seconds=None, median_abs_error_seconds=None,
                       max_abs_error_seconds=None, n_within_tolerance=None, within_tolerance_accuracy=None,
                       within_tolerance_rate_including_abstentions=None)
        return summary
    signed = [r.signed_error for r in evaluated]
    absolute = [abs(e) for e in signed]  # type: ignore[arg-type]
    within = sum(a <= tolerance for a in absolute)
    summary.update(
        mean_signed_error_seconds=statistics.fmean(signed),  # type: ignore[arg-type]
        mean_abs_error_seconds=statistics.fmean(absolute),
        median_abs_error_seconds=statistics.median(absolute),
        max_abs_error_seconds=max(absolute),
        n_within_tolerance=within,
        within_tolerance_accuracy=within / len(evaluated),
        within_tolerance_rate_including_abstentions=within / attempted,
    )
    return summary


def headline(summary: dict[str, Any]) -> str:
    if not summary["n_evaluated"]:
        return f"No examples evaluated ({summary['n_examples']} examples, all skipped or abstained)."
    skipped = summary["n_examples"] - summary["n_evaluated"] - summary["n_abstained"]
    return (f"Event localized within {summary['tolerance_seconds']:g}s on {summary['n_within_tolerance']} of "
            f"{summary['n_evaluated']} evaluated clips; median |error| {summary['median_abs_error_seconds']:.2f}s, "
            f"mean |error| {summary['mean_abs_error_seconds']:.2f}s "
            f"({summary['n_abstained']} abstained, {skipped} skipped).")
