import type { AnalysisStatus, Incident, IncidentReport } from "./contracts";

/**
 * Bundled demo fixtures. Values are copied verbatim from the published
 * contract examples (packages/contracts/examples/*.json) so fixture mode
 * can never drift from the backend contract.
 *
 * Fixture mode is an offline fallback for demos when the API is unavailable.
 * It is always labeled as fixture/mock data in the UI and must never be
 * presented as fresh analysis or real video inference.
 */

export const FIXTURE_INCIDENT_ID = "demo-001";

export const FIXTURE_INCIDENT: Incident = {
  id: "demo-001",
  title: "Synthetic lane-change dispute",
  video_uri: "mock://demo-001/no-video",
  duration_seconds: 20.0,
  statements: [
    {
      id: "statement-a",
      driver_id: "driver-a",
      text: "Driver B moved into my lane. I braked. My traffic light was green.",
    },
    {
      id: "statement-b",
      driver_id: "driver-b",
      text: "I stayed in my lane. Driver A did not brake.",
    },
  ],
  is_mock: true,
};

export const FIXTURE_REPORT: IncidentReport = {
  schema_version: "1.0",
  incident_id: "demo-001",
  is_mock: true,
  claims: [
    {
      id: "c1",
      statement_id: "statement-a",
      text: "Driver B moved into my lane.",
      subject: "driver-b",
      category: "lane_change",
    },
    {
      id: "c2",
      statement_id: "statement-a",
      text: "I braked.",
      subject: "driver-a",
      category: "braking",
    },
    {
      id: "c3",
      statement_id: "statement-a",
      text: "My traffic light was green.",
      subject: "driver-a",
      category: "traffic_signal",
    },
    {
      id: "c4",
      statement_id: "statement-b",
      text: "I stayed in my lane.",
      subject: "driver-b",
      category: "lane_change",
    },
    {
      id: "c5",
      statement_id: "statement-b",
      text: "Driver A did not brake.",
      subject: "driver-a",
      category: "braking",
    },
  ],
  verdicts: [
    {
      claim_id: "c1",
      verdict: "supported",
      evidence: [
        {
          video_uri: "mock://demo-001/no-video",
          start_seconds: 8.0,
          end_seconds: 12.0,
          visibility: "visible",
          description: "Scripted demo event: B changes lanes and A brakes. No real footage exists.",
          provenance: {
            adapter: "deterministic-mock",
            version: "1.0",
            source: "synthetic fixture; no video analyzed",
            is_mock: true,
          },
        },
      ],
      explanation: "Synthetic fixture assigns supported: B changes lanes and A brakes.",
      provenance: {
        adapter: "deterministic-mock",
        version: "1.0",
        source: "synthetic fixture; no video analyzed",
        is_mock: true,
      },
      confidence: null,
      uncertainty: "Synthetic demonstration only; no inference or measured confidence.",
    },
    {
      claim_id: "c2",
      verdict: "supported",
      evidence: [
        {
          video_uri: "mock://demo-001/no-video",
          start_seconds: 8.0,
          end_seconds: 12.0,
          visibility: "visible",
          description: "Scripted demo event: B changes lanes and A brakes. No real footage exists.",
          provenance: {
            adapter: "deterministic-mock",
            version: "1.0",
            source: "synthetic fixture; no video analyzed",
            is_mock: true,
          },
        },
      ],
      explanation: "Synthetic fixture assigns supported: B changes lanes and A brakes.",
      provenance: {
        adapter: "deterministic-mock",
        version: "1.0",
        source: "synthetic fixture; no video analyzed",
        is_mock: true,
      },
      confidence: null,
      uncertainty: "Synthetic demonstration only; no inference or measured confidence.",
    },
    {
      claim_id: "c3",
      verdict: "not_visible",
      evidence: [
        {
          video_uri: "mock://demo-001/no-video",
          start_seconds: 8.0,
          end_seconds: 12.0,
          visibility: "not_visible",
          description: "Synthetic review window; signal outside frame.",
          provenance: {
            adapter: "deterministic-mock",
            version: "1.0",
            source: "synthetic fixture; no video analyzed",
            is_mock: true,
          },
        },
      ],
      explanation: "Signal is unseen; absence cannot contradict the claim.",
      provenance: {
        adapter: "deterministic-mock",
        version: "1.0",
        source: "synthetic fixture; no video analyzed",
        is_mock: true,
      },
      confidence: null,
      uncertainty: "Synthetic demonstration only; no inference or measured confidence.",
    },
    {
      claim_id: "c4",
      verdict: "contradicted",
      evidence: [
        {
          video_uri: "mock://demo-001/no-video",
          start_seconds: 8.0,
          end_seconds: 12.0,
          visibility: "visible",
          description: "Scripted demo event: B changes lanes and A brakes. No real footage exists.",
          provenance: {
            adapter: "deterministic-mock",
            version: "1.0",
            source: "synthetic fixture; no video analyzed",
            is_mock: true,
          },
        },
      ],
      explanation: "Synthetic fixture assigns contradicted: B changes lanes and A brakes.",
      provenance: {
        adapter: "deterministic-mock",
        version: "1.0",
        source: "synthetic fixture; no video analyzed",
        is_mock: true,
      },
      confidence: null,
      uncertainty: "Synthetic demonstration only; no inference or measured confidence.",
    },
    {
      claim_id: "c5",
      verdict: "contradicted",
      evidence: [
        {
          video_uri: "mock://demo-001/no-video",
          start_seconds: 8.0,
          end_seconds: 12.0,
          visibility: "visible",
          description: "Scripted demo event: B changes lanes and A brakes. No real footage exists.",
          provenance: {
            adapter: "deterministic-mock",
            version: "1.0",
            source: "synthetic fixture; no video analyzed",
            is_mock: true,
          },
        },
      ],
      explanation: "Synthetic fixture assigns contradicted: B changes lanes and A brakes.",
      provenance: {
        adapter: "deterministic-mock",
        version: "1.0",
        source: "synthetic fixture; no video analyzed",
        is_mock: true,
      },
      confidence: null,
      uncertainty: "Synthetic demonstration only; no inference or measured confidence.",
    },
  ],
  observations: [
    {
      id: "mock-observation-1",
      claim_id: "c1",
      label: "scripted_lane_change",
      evidence: {
        video_uri: "mock://demo-001/no-video",
        start_seconds: 8.0,
        end_seconds: 12.0,
        visibility: "visible",
        description: "Scripted demo event: B changes lanes and A brakes. No real footage exists.",
        provenance: {
          adapter: "deterministic-mock",
          version: "1.0",
          source: "synthetic fixture; no video analyzed",
          is_mock: true,
        },
      },
      confidence: null,
      provenance: {
        adapter: "deterministic-mock",
        version: "1.0",
        source: "synthetic fixture; no video analyzed",
        is_mock: true,
      },
    },
  ],
  summary: "Synthetic demo only. Human review required. No legal fault determination.",
  human_review_required: true,
  legal_fault_determination: "not_provided",
};

export const FIXTURE_STATUS: AnalysisStatus = {
  incident_id: "demo-001",
  state: "completed",
  is_mock: true,
  detail: "Mock analysis complete.",
};

/** True when fixture mode is forced via env (?fixture=1 is read at runtime in the dashboard). */
export function fixtureForcedByEnv(): boolean {
  return process.env.NEXT_PUBLIC_WITNESS_FIXTURE === "1";
}
