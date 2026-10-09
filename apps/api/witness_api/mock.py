"""Scripted synthetic fixtures only. No footage is read and no inference occurs."""
from witness_contracts import (Incident, AtomicClaim, EvidenceWindow, DetectorObservation,
                               ClaimVerdict, IncidentReport, Provenance)

PROVENANCE = Provenance(adapter="deterministic-mock", version="1.0", source="synthetic fixture; no video analyzed", is_mock=True)
ROWS = [
    ("c1", "statement-a", "Driver B moved into my lane.", "driver-b", "lane_change", "supported"),
    ("c2", "statement-a", "I braked.", "driver-a", "braking", "supported"),
    ("c3", "statement-a", "My traffic light was green.", "driver-a", "traffic_signal", "not_visible"),
    ("c4", "statement-b", "I stayed in my lane.", "driver-b", "lane_change", "contradicted"),
    ("c5", "statement-b", "Driver A did not brake.", "driver-a", "braking", "contradicted"),
]

class MockAdapters:
    def extract(self, incident: Incident) -> list[AtomicClaim]:
        if incident.id != "demo-001" or not incident.is_mock:
            raise ValueError("mock adapter only accepts the synthetic demo")
        return [AtomicClaim(id=i, statement_id=s, text=t, subject=u, category=c) for i,s,t,u,c,v in ROWS]

    def localize(self, incident: Incident, claim: AtomicClaim) -> list[EvidenceWindow]:
        unseen = claim.category == "traffic_signal"
        return [EvidenceWindow(video_uri=incident.video_uri, start_seconds=8, end_seconds=12,
            visibility="not_visible" if unseen else "visible",
            description="Synthetic review window; signal outside frame." if unseen else
                "Scripted demo event: B changes lanes and A brakes. No real footage exists.",
            provenance=PROVENANCE)]

    def verify(self, claim: AtomicClaim, windows: list[EvidenceWindow]) -> ClaimVerdict:
        verdict = next(row[5] for row in ROWS if row[0] == claim.id)
        return ClaimVerdict(claim_id=claim.id, verdict=verdict, evidence=windows,
            explanation="Signal is unseen; absence cannot contradict the claim." if verdict == "not_visible" else
                f"Synthetic fixture assigns {verdict}: B changes lanes and A brakes.",
            provenance=PROVENANCE, confidence=None,
            uncertainty="Synthetic demonstration only; no inference or measured confidence.")

    def observe(self, incident: Incident, claims: list[AtomicClaim]) -> list[DetectorObservation]:
        return [DetectorObservation(id="mock-observation-1", claim_id="c1", label="scripted_lane_change",
            evidence=self.localize(incident, claims[0])[0], provenance=PROVENANCE)]

    def fuse(self, verdict: ClaimVerdict, observations: list[DetectorObservation]) -> ClaimVerdict:
        # Mock observations do not constitute independent corroboration.
        return verdict

    def generate(self, incident: Incident, claims: list[AtomicClaim], verdicts: list[ClaimVerdict],
                 observations: list[DetectorObservation]) -> IncidentReport:
        return IncidentReport(incident_id=incident.id, is_mock=True, claims=claims, verdicts=verdicts,
            observations=observations, summary="Synthetic demo only. Human review required. No legal fault determination.")
