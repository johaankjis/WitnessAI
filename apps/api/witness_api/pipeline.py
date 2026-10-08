from dataclasses import dataclass
from witness_contracts import Incident, IncidentReport
from .interfaces import ClaimExtractor, VideoLocalizer, ClaimVerifier, YoloObserver, EvidenceFusion, ReportGenerator

@dataclass
class Pipeline:
    extractor: ClaimExtractor
    localizer: VideoLocalizer
    verifier: ClaimVerifier
    observer: YoloObserver
    fusion: EvidenceFusion
    reporter: ReportGenerator

    def analyze(self, incident: Incident) -> IncidentReport:
        claims = self.extractor.extract(incident)
        if any(c.statement_id not in {s.id for s in incident.statements} for c in claims):
            raise ValueError("unknown statement reference")
        if not claims or len({c.id for c in claims}) != len(claims):
            raise ValueError("claims must be nonempty and unique")
        def check_windows(windows):
            from witness_contracts import EvidenceWindow
            for candidate in windows:
                window = EvidenceWindow.model_validate(candidate.model_dump())
                if (window.video_uri != incident.video_uri or window.end_seconds > incident.duration_seconds
                        or window.provenance.is_mock != incident.is_mock):
                    raise ValueError("evidence outside incident video or invalid provenance")
        observations = self.observer.observe(incident, claims)
        if any(o.claim_id not in {c.id for c in claims} for o in observations):
            raise ValueError("unknown observation claim")
        check_windows([o.evidence for o in observations])
        verdicts = []
        for claim in claims:
            windows = self.localizer.localize(incident, claim)
            if not windows:
                raise ValueError("localization requires a reviewed window")
            check_windows(windows)
            verdict = self.verifier.verify(claim, windows)
            if verdict.claim_id != claim.id:
                raise ValueError("verdict claim mismatch")
            check_windows(verdict.evidence)
            verdicts.append(self.fusion.fuse(verdict, [o for o in observations if o.claim_id == claim.id]))
        report = self.reporter.generate(incident, claims, verdicts, observations)
        report = IncidentReport.model_validate(report.model_dump())
        if report.claims != claims or report.verdicts != verdicts or report.observations != observations:
            raise ValueError("report generator changed validated evidence")
        if report.incident_id != incident.id or report.is_mock != incident.is_mock:
            raise ValueError("report incident mismatch")
        for window in [e for v in report.verdicts for e in v.evidence] + [o.evidence for o in report.observations]:
            if window.video_uri != incident.video_uri or window.end_seconds > incident.duration_seconds:
                raise ValueError("evidence outside incident video")
        return report
