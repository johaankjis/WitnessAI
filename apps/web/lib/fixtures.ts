import type { AnalysisStatus, Incident, IncidentReport } from "./contracts";
import incident from "./fixtures/Incident.json";
import report from "./fixtures/IncidentReport.json";
import status from "./fixtures/AnalysisStatus.json";

// Offline fallback only, always labeled DEMO/MOCK and never fresh inference.
export const FIXTURE_INCIDENT_ID = "demo-001";
export const FIXTURE_INCIDENT = incident as Incident;
export const FIXTURE_REPORT = report as IncidentReport;
export const FIXTURE_STATUS = status as AnalysisStatus;

export function fixtureForcedByEnv(): boolean {
  return process.env.NEXT_PUBLIC_WITNESS_FIXTURE === "1";
}
