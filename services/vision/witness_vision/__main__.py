"""CLI.

  python -m witness_vision analyze VIDEO [--weights PATH] [--device DEV] [--sample-fps N] [--min-confidence C]
                                   [--out analysis.json] [--detections-out dets.json] [--detections-csv dets.csv]
                                   [--video-out annotated.mp4] [--clip-out event.mp4]
  python -m witness_vision observe --incident INCIDENT.json --claims CLAIMS.json [--media-root DIR]
                                   [--out observations.json] [--analysis-out analysis.json] [--clip-dir DIR]
                                   [--weights PATH] [--device DEV] [--sample-fps N] [--min-confidence C]
  python -m witness_vision export-examples [--incident data/demo/incident.json]

`analyze` and `observe` run a real pretrained YOLO model on local footage (needs the `yolo`
extra and weights). `export-examples` regenerates the deterministic mock examples only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .analysis import analyze_video
from .config import VisionConfig
from .detectors import Detector
from .errors import VisionError

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def _detector(args: argparse.Namespace) -> Detector:
    """Real YOLO detector for the CLI. Tests may monkeypatch this to inject a fake."""
    from .detectors import UltralyticsDetector
    return UltralyticsDetector(args.weights, device=args.device, min_confidence=0.1)


def _write_json(payload: object, path: str | None) -> None:
    text = json.dumps(payload, indent=2)
    if path:
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text + "\n")
    else:
        print(text)


def _analyze(args: argparse.Namespace) -> int:
    from .export import detections_document, write_detections, write_detections_csv
    from .sources import OpenCVFrameSource, resolve_video_path
    config = VisionConfig(sample_fps=args.sample_fps, min_confidence=args.min_confidence)
    path = resolve_video_path(args.video)
    detector = _detector(args)
    analysis = analyze_video(OpenCVFrameSource(path), detector, config)
    if args.video_out:
        from .annotate import write_annotated_video
        write_annotated_video(path, analysis, Path(args.video_out))
    if args.clip_out and analysis.event:
        from .annotate import write_annotated_clip
        event = analysis.event
        write_annotated_clip(path, analysis, event.window_start, event.window_end, Path(args.clip_out))
    if args.detections_out or args.detections_csv:
        document = detections_document(analysis, detector.name, is_mock=False, config=config,
                                       weights_path=getattr(detector, "weights", None), video_path=path,
                                       device=args.device)
        if args.detections_out:
            write_detections(document, Path(args.detections_out))
        if args.detections_csv:
            write_detections_csv(document["detections"], Path(args.detections_csv))
    _write_json(analysis.to_dict(), args.out)
    return 0


def _observe(args: argparse.Namespace) -> int:
    from witness_contracts import AtomicClaim, Incident

    from .adapter import VisionObserver
    incident = Incident.model_validate_json(Path(args.incident).read_text())
    claims = [AtomicClaim.model_validate(c) for c in json.loads(Path(args.claims).read_text())]
    config = VisionConfig(sample_fps=args.sample_fps, min_confidence=args.min_confidence)
    observer = VisionObserver(detector=_detector(args), config=config,
                              media_root=Path(args.media_root) if args.media_root else None,
                              clip_dir=Path(args.clip_dir) if args.clip_dir else None)
    observations = observer.observe(incident, claims)
    _write_json([o.model_dump(mode="json") for o in observations], args.out)
    if args.analysis_out and observer.last_analysis is not None:
        _write_json(observer.last_analysis.to_dict(), args.analysis_out)
    if observer.last_clip is not None:
        print(f"annotated event clip: {observer.last_clip}", file=sys.stderr)
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


def _add_detector_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--weights", default=None,
                        help="YOLO weights path (default WITNESS_YOLO_WEIGHTS or yolo11n.pt)")
    parser.add_argument("--device", default=None,
                        help="torch device, e.g. cpu, mps, cuda:0 (default WITNESS_YOLO_DEVICE)")
    parser.add_argument("--sample-fps", type=float, default=VisionConfig.sample_fps)
    parser.add_argument("--min-confidence", type=float, default=VisionConfig.min_confidence)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="witness_vision")
    sub = parser.add_subparsers(dest="command", required=True)
    a = sub.add_parser("analyze", help="run YOLO + tracking on a local video and print the analysis")
    a.add_argument("video")
    _add_detector_args(a)
    a.add_argument("--out", default=None, help="write the analysis summary JSON here instead of stdout")
    a.add_argument("--detections-out", default=None,
                   help="write every detection (frame, time, track, box, score) as JSON")
    a.add_argument("--detections-csv", default=None, help="write the same detection rows as CSV")
    a.add_argument("--video-out", default=None, help="write an annotated video of all sampled frames")
    a.add_argument("--clip-out", default=None, help="write an annotated event-window clip here")
    a.set_defaults(func=_analyze)
    o = sub.add_parser("observe",
                       help="run the real VisionObserver on an incident JSON and write DetectorObservation[]")
    o.add_argument("--incident", required=True, help="Incident JSON with is_mock=false and a local video_uri")
    o.add_argument("--claims", required=True, help="JSON list of AtomicClaim objects")
    o.add_argument("--media-root", default=None, help="directory that relative video_uri values resolve against")
    _add_detector_args(o)
    o.add_argument("--out", default=None, help="write observations JSON here instead of stdout")
    o.add_argument("--analysis-out", default=None, help="also write the internal analysis summary JSON")
    o.add_argument("--clip-dir", default=None, help="write <incident id>-event.mp4 here when an event is localized")
    o.set_defaults(func=_observe)
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
