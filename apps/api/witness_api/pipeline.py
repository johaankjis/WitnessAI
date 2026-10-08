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
        observations = self.observer.observe(incident, claims)
        verdicts = []
        for claim in claims:
            windows = self.localizer.localize(incident, claim)
            verdict = self.verifier.verify(claim, windows)
            verdicts.append(self.fusion.fuse(verdict, [o for o in observations if o.claim_id == claim.id]))
        report = self.reporter.generate(incident, claims, verdicts, observations)
        if report.incident_id != incident.id or report.is_mock != incident.is_mock:
            raise ValueError("report incident mismatch")
        for window in [e for v in report.verdicts for e in v.evidence] + [o.evidence for o in report.observations]:
            if window.video_uri != incident.video_uri or window.end_seconds > incident.duration_seconds:
                raise ValueError("evidence outside incident video")
        return report
