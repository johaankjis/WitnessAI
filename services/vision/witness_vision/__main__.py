"""CLI.

  python -m witness_vision analyze VIDEO [--weights PATH] [--sample-fps N] [--clip-out OUT.mp4]
  python -m witness_vision export-examples [--incident data/demo/incident.json]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import analyze_video
from .config import VisionConfig
from .errors import VisionError

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _analyze(args: argparse.Namespace) -> int:
    from .detectors import UltralyticsDetector
    from .sources import OpenCVFrameSource, resolve_video_path
    config = VisionConfig(sample_fps=args.sample_fps, min_confidence=args.min_confidence)
    path = resolve_video_path(args.video)
    analysis = analyze_video(OpenCVFrameSource(path), UltralyticsDetector(args.weights, min_confidence=0.1), config)
    if args.clip_out and analysis.event:
        from .annotate import write_annotated_clip
        event = analysis.event
        write_annotated_clip(path, analysis, event.window_start, event.window_end, Path(args.clip_out))
    print(json.dumps(analysis.to_dict(), indent=2))
    return 0


def _export_examples(args: argparse.Namespace) -> int:
    from witness_contracts import AtomicClaim, Incident

    from .adapter import MockVisionObserver
    incident = Incident.model_validate_json(Path(args.incident).read_text())
    claims = [AtomicClaim(id=f"c{i}", statement_id=sid, text=text, subject=subj, category=cat)
              for i, (sid, text, subj, cat) in enumerate(EXAMPLE_CLAIMS, start=1)]
    observer = MockVisionObserver()
    observations = observer.observe(incident, claims)
    EXAMPLES.mkdir(exist_ok=True)
    (EXAMPLES / "demo-001.claims.json").write_text(
        json.dumps([c.model_dump(mode="json") for c in claims], indent=2) + "\n")
    (EXAMPLES / "demo-001.observations.json").write_text(
        json.dumps([o.model_dump(mode="json") for o in observations], indent=2) + "\n")
    (EXAMPLES / "demo-001.analysis.json").write_text(json.dumps(observer.last_analysis.to_dict(), indent=2) + "\n")
    print(f"wrote {len(observations)} observations to {EXAMPLES}")
    return 0


# Same claims as apps/api/witness_api/mock.py ROWS, duplicated so examples need no API import.
EXAMPLE_CLAIMS = [
    ("statement-a", "Driver B moved into my lane.", "driver-b", "lane_change"),
    ("statement-a", "I braked.", "driver-a", "braking"),
    ("statement-a", "My traffic light was green.", "driver-a", "traffic_signal"),
    ("statement-b", "I stayed in my lane.", "driver-b", "lane_change"),
    ("statement-b", "Driver A did not brake.", "driver-a", "braking"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="witness_vision")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="run YOLO + tracking on a local video and print the analysis")
    a.add_argument("video")
    a.add_argument("--weights", default=None, help="YOLO weights path (default WITNESS_YOLO_WEIGHTS or yolo11n.pt)")
    a.add_argument("--sample-fps", type=float, default=VisionConfig.sample_fps)
    a.add_argument("--min-confidence", type=float, default=VisionConfig.min_confidence)
    a.add_argument("--clip-out", default=None, help="write an annotated event clip here")
    a.set_defaults(func=_analyze)
    e = sub.add_parser("export-examples", help="regenerate examples/ from the deterministic mock")
    e.add_argument("--incident", default=str(ROOT / "data/demo/incident.json"))
    e.set_defaults(func=_export_examples)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except VisionError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
