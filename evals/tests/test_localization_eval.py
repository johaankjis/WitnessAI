import json
import sys
from pathlib import Path

import pytest

from witness_evals import (
    ExampleResult,
    PredictionFilePredictor,
    evaluate_localization,
    headline,
    load_labels,
    report,
    summarize,
)
from witness_evals.__main__ import main
from witness_evals.weave_eval import log_to_weave

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def fixture_results():
    labels = load_labels(FIXTURES / "labels.csv")
    return evaluate_localization(labels, PredictionFilePredictor(FIXTURES / "predictions.json"))


def test_labels_keep_padded_ids_and_blank_times():
    labels = load_labels(FIXTURES / "labels.csv")
    assert [c.id for c in labels][:3] == ["00001", "00002", "00003"]
    assert labels[2].time_of_event is None and labels[2].target == 0
    assert labels[0].time_of_event == 19.5 and labels[0].time_of_alert == 18.2


@pytest.mark.parametrize("body", ["id,foo\n1,2\n", "id,time_of_event\n1,2\n1,3\n", "id,time_of_event\n1,-4\n",
                                  "id,time_of_event\n1,nan\n"])
def test_bad_labels_rejected(tmp_path, body):
    path = tmp_path / "bad.csv"
    path.write_text(body)
    with pytest.raises(ValueError):
        load_labels(path)


def test_statuses_and_metrics_use_only_evaluated_examples():
    results = fixture_results()
    assert {r.id: r.status for r in results} == {"00001": "evaluated", "00002": "evaluated", "00003": "no_label",
                                                 "00004": "abstained", "00005": "evaluated", "00006": "error"}
    s = summarize(results)
    assert (s["n_examples"], s["n_evaluated"], s["n_abstained"], s["n_no_label"], s["n_error"]) == (6, 3, 1, 1, 1)
    assert s["mean_signed_error_seconds"] == pytest.approx((-0.4 + 2.3 + 0.0) / 3)
    assert s["mean_abs_error_seconds"] == pytest.approx((0.4 + 2.3 + 0.0) / 3)
    assert s["median_abs_error_seconds"] == pytest.approx(0.4)
    assert s["max_abs_error_seconds"] == pytest.approx(2.3)
    assert s["n_within_tolerance"] == 2
    assert s["within_tolerance_accuracy"] == pytest.approx(2 / 3)
    assert s["within_tolerance_rate_including_abstentions"] == pytest.approx(2 / 4)
    assert "within 1s on 2 of 3 evaluated clips" in headline(s)


def test_boundary_is_inclusive_and_tolerance_configurable():
    results = [ExampleResult("a", "evaluated", 10.0, 11.0), ExampleResult("b", "evaluated", 10.0, 8.5)]
    assert summarize(results)["n_within_tolerance"] == 1
    assert summarize(results, tolerance=2.0)["n_within_tolerance"] == 2


def test_nothing_evaluated_gives_none_not_zero():
    s = summarize([ExampleResult("a", "abstained", 3.0), ExampleResult("b", "no_label")])
    assert s["n_evaluated"] == 0
    for key in ("mean_abs_error_seconds", "median_abs_error_seconds", "within_tolerance_accuracy"):
        assert s[key] is None
    assert headline(s).startswith("No examples evaluated")


def test_limit_counts_attempted_labeled_clips():
    labels = load_labels(FIXTURES / "labels.csv")
    results = evaluate_localization(labels, PredictionFilePredictor(FIXTURES / "predictions.json"), limit=2)
    assert [r.id for r in results] == ["00001", "00002"]


def test_missing_video_is_skipped_not_scored(tmp_path):
    class NeedsVideo:
        name, needs_video = "v", True

        def predict(self, clip_id, video):
            raise AssertionError("must not be called")
    results = evaluate_localization(load_labels(FIXTURES / "labels.csv"), NeedsVideo(), tmp_path)
    assert {r.status for r in results} == {"missing_video", "no_label"}
    assert summarize(results)["median_abs_error_seconds"] is None


def test_cli_writes_report(tmp_path, capsys):
    out = tmp_path / "report.json"
    assert main(["--labels", str(FIXTURES / "labels.csv"), "--predictions", str(FIXTURES / "predictions.json"),
                 "--out", str(out)]) == 0
    data = json.loads(out.read_text())
    assert data["predictor"] == "file:predictions.json" and data["summary"]["n_evaluated"] == 3
    assert len(data["examples"]) == 6
    assert "2 of 3 evaluated" in capsys.readouterr().out


def test_weave_skipped_without_project(monkeypatch):
    monkeypatch.delenv("WITNESS_WEAVE_PROJECT", raising=False)
    results = fixture_results()
    assert log_to_weave(results, "p", summarize(results)) is None


def test_weave_failure_is_graceful(monkeypatch):
    monkeypatch.setitem(sys.modules, "weave", None)
    results = fixture_results()
    assert log_to_weave(results, "p", summarize(results), project="team/witness") is None


def test_weave_receives_only_evaluated_examples(monkeypatch):
    captured = {}

    class FakeEvaluation:
        def __init__(self, name, dataset, scorers):
            captured.update(dataset=dataset, scorer=scorers[0])

        async def evaluate(self, model):
            rows = [captured["scorer"](r["time_of_event"], model(r["id"])) for r in captured["dataset"]]
            return {"n": len(rows), "within": sum(r["within_tolerance"] for r in rows)}

    class FakeWeave:
        Evaluation = FakeEvaluation

        @staticmethod
        def init(project):
            captured["project"] = project

        @staticmethod
        def op(name):
            return lambda fn: fn

        @staticmethod
        def attributes(attrs):
            captured["attrs"] = attrs
            import contextlib
            return contextlib.nullcontext()
    monkeypatch.setitem(sys.modules, "weave", FakeWeave)
    results = fixture_results()
    out = log_to_weave(results, "p", summarize(results), project="team/witness")
    assert out == {"n": 3, "within": 2}
    assert [r["id"] for r in captured["dataset"]] == ["00001", "00002", "00005"]
    assert captured["attrs"]["n_abstained"] == 1


def test_report_shape():
    data = report(fixture_results(), "p")
    first = data["examples"][0]
    assert first["signed_error_seconds"] == pytest.approx(-0.4) and first["abs_error_seconds"] == pytest.approx(0.4)
