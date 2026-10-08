"""python -m witness_evals --labels train.csv (--predictions preds.json | --videos DIR) [options]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .labels import load_labels
from .localization import PredictionFilePredictor, VisionPredictor, evaluate_localization, report
from .metrics import headline
from .weave_eval import log_to_weave


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="witness_evals", description="Event localization vs labeled time_of_event")
    parser.add_argument("--labels", required=True, type=Path, help="CSV with id,time_of_event (Nexar train.csv)")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--predictions", type=Path, help='JSON {"<id>": seconds|null} to score')
    source.add_argument("--videos", type=Path, help="directory of <id>.mp4 clips; runs the YOLO vision pipeline")
    parser.add_argument("--weights", default=None, help="YOLO weights for --videos")
    parser.add_argument("--ids", nargs="*", help="restrict to these clip IDs")
    parser.add_argument("--limit", type=int, default=None, help="max labeled clips to attempt")
    parser.add_argument("--tolerance", type=float, default=1.0)
    parser.add_argument("--out", type=Path, help="write the full JSON report here")
    parser.add_argument("--weave", action="store_true",
                        help="also log a Weave evaluation (needs WITNESS_WEAVE_PROJECT)")
    args = parser.parse_args(argv)

    labels = load_labels(args.labels)
    if args.ids:
        wanted = set(args.ids)
        labels = [c for c in labels if c.id in wanted]
    if args.predictions:
        predictor = PredictionFilePredictor(args.predictions)
    else:
        from witness_vision.detectors import UltralyticsDetector
        predictor = VisionPredictor(detector=UltralyticsDetector(args.weights, min_confidence=0.1))
    results = evaluate_localization(labels, predictor, args.videos, args.limit)
    output = report(results, predictor.name, args.tolerance)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output["summary"], indent=2))
    print(headline(output["summary"]))
    if args.weave and log_to_weave(results, predictor.name, output["summary"], args.tolerance) is None:
        print("Weave evaluation not logged (see warnings).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
