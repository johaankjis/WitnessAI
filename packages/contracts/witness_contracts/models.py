from enum import Enum
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

class Verdict(str, Enum):
    supported = "supported"
    contradicted = "contradicted"
    not_visible = "not_visible"

class Provenance(Contract):
    adapter: str = Field(min_length=1)
    version: str = Field(min_length=1)
    source: str = Field(min_length=1)
    is_mock: bool

class DriverStatement(Contract):
    id: str = Field(min_length=1)
    driver_id: str = Field(min_length=1)
    text: str = Field(min_length=1)

class Incident(Contract):
    id: str = Field(pattern=r"^[a-zA-Z0-9_-]+$")
    title: str
    video_uri: str
    duration_seconds: float = Field(gt=0)
    statements: list[DriverStatement] = Field(min_length=2)
    is_mock: bool

    @model_validator(mode="after")
    def unique_statements(self):
        if len({s.id for s in self.statements}) != len(self.statements):
            raise ValueError("statement IDs must be unique")
        return self

class AtomicClaim(Contract):
    id: str
    statement_id: str
    text: str = Field(min_length=1)
    subject: str
    category: Literal["lane_change", "braking", "traffic_signal", "other"]

class EvidenceWindow(Contract):
    video_uri: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    visibility: Literal["visible", "not_visible"]
    description: str = Field(min_length=1)
    provenance: Provenance

    @model_validator(mode="after")
    def ordered(self):
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds")
        return self

class DetectorObservation(Contract):
    id: str
    claim_id: str
    label: str
    evidence: EvidenceWindow
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: Provenance

class ClaimVerdict(Contract):
    claim_id: str
    verdict: Verdict
    evidence: list[EvidenceWindow] = Field(min_length=1)
    explanation: str = Field(min_length=1)
    provenance: Provenance
    confidence: float | None = Field(default=None, ge=0, le=1)
    uncertainty: str = Field(min_length=1)

    @model_validator(mode="after")
    def visible_basis(self):
        if self.verdict != Verdict.not_visible and not any(e.visibility == "visible" for e in self.evidence):
            raise ValueError("supported/contradicted requires visible evidence")
        return self

class IncidentReport(Contract):
    schema_version: Literal["1.0"] = "1.0"
    incident_id: str
    is_mock: bool
    claims: list[AtomicClaim] = Field(min_length=1)
    verdicts: list[ClaimVerdict] = Field(min_length=1)
    observations: list[DetectorObservation]
    summary: str
    human_review_required: Literal[True] = True
    legal_fault_determination: Literal["not_provided"] = "not_provided"

    @model_validator(mode="after")
    def references(self):
        ids = [c.id for c in self.claims]
        verdict_ids = [v.claim_id for v in self.verdicts]
        if len(set(ids)) != len(ids) or sorted(ids) != sorted(verdict_ids):
            raise ValueError("exactly one verdict per unique claim required")
        if any(o.claim_id not in ids for o in self.observations):
            raise ValueError("unknown observation claim")
        sources = [v.provenance for v in self.verdicts]
        sources += [e.provenance for v in self.verdicts for e in v.evidence]
        sources += [p for o in self.observations for p in (o.provenance, o.evidence.provenance)]
        if any(p.is_mock != self.is_mock for p in sources):
            raise ValueError("report and evidence mock labels must agree")
        return self

class AnalysisStatus(Contract):
    incident_id: str
    state: Literal["pending", "running", "completed", "failed"]
    is_mock: bool
    detail: str
