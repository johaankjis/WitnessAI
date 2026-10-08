/**
 * TypeScript mirror of the published TASK-001 Pydantic contracts
 * (packages/contracts/witness_contracts/models.py, schema v1.0).
 *
 * Field names and value literals match the backend exactly. The frontend
 * must adapt to these shapes and never assume extra fields.
 */

export type Verdict = "supported" | "contradicted" | "not_visible";

export type ClaimCategory = "lane_change" | "braking" | "traffic_signal" | "other";

export type Visibility = "visible" | "not_visible";

export type AnalysisState = "pending" | "running" | "completed" | "failed";

export interface Provenance {
  adapter: string;
  version: string;
  source: string;
  is_mock: boolean;
}

export interface DriverStatement {
  id: string;
  driver_id: string;
  text: string;
}

export interface Incident {
  id: string;
  title: string;
  video_uri: string;
  duration_seconds: number;
  statements: DriverStatement[];
  is_mock: boolean;
}

export interface AtomicClaim {
  id: string;
  statement_id: string;
  text: string;
  subject: string;
  category: ClaimCategory;
}

export interface EvidenceWindow {
  video_uri: string;
  start_seconds: number;
  end_seconds: number;
  visibility: Visibility;
  description: string;
  provenance: Provenance;
}

export interface DetectorObservation {
  id: string;
  claim_id: string;
  label: string;
  evidence: EvidenceWindow;
  confidence: number | null;
  provenance: Provenance;
}

export interface ClaimVerdict {
  claim_id: string;
  verdict: Verdict;
  evidence: EvidenceWindow[];
  explanation: string;
  provenance: Provenance;
  confidence: number | null;
  uncertainty: string;
}

export interface IncidentReport {
  schema_version: "1.0";
  incident_id: string;
  is_mock: boolean;
  claims: AtomicClaim[];
  verdicts: ClaimVerdict[];
  observations: DetectorObservation[];
  summary: string;
  human_review_required: true;
  legal_fault_determination: "not_provided";
}

export interface AnalysisStatus {
  incident_id: string;
  state: AnalysisState;
  is_mock: boolean;
  detail: string;
}

export interface HealthStatus {
  status: string;
  analysis_mode: string;
}
