import type { AnalysisStatus, HealthStatus, Incident, IncidentReport } from "./contracts";

export const DEFAULT_API_BASE = "http://localhost:8000";
export const DEMO_INCIDENT_ID = "demo-001";

/** Resolves the API base URL. Env override wins; localhost:8000 is the documented default. */
export function apiBase(): string {
  const env = process.env.NEXT_PUBLIC_WITNESS_API_BASE?.trim();
  if (env) return env.replace(/\/+$/, "");
  return DEFAULT_API_BASE;
}

/**
 * Typed fetch failure. `status` mirrors the HTTP status code, or 0 when the
 * API host is unreachable (network error), which callers use to enter fixture mode.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function isNotFound(error: unknown): boolean {
  return error instanceof ApiError && error.status === 404;
}

/** 409 from GET results means analysis has not run yet (POST /analyze first). */
export function isNotAnalyzed(error: unknown): boolean {
  return error instanceof ApiError && error.status === 409;
}

export function isUnreachable(error: unknown): boolean {
  return error instanceof ApiError && error.status === 0;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase()}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, `API unreachable at ${apiBase()}. Is the backend running?`);
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }
  return (await response.json()) as T;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    if (typeof body === "object" && body !== null && "detail" in body) {
      const detail = (body as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.length > 0) return detail;
    }
  } catch {
    /* fall through to generic message */
  }
  return `Request failed with status ${response.status}`;
}

export function getHealth(): Promise<HealthStatus> {
  return request<HealthStatus>("/health");
}

export function getIncident(incidentId: string): Promise<Incident> {
  return request<Incident>(`/incidents/${encodeURIComponent(incidentId)}`);
}

/**
 * Runs analysis synchronously on the backend (POST returns when the report
 * has been saved). Callers should then fetch results.
 */
export function analyzeIncident(incidentId: string): Promise<AnalysisStatus> {
  return request<AnalysisStatus>(`/incidents/${encodeURIComponent(incidentId)}/analyze`, {
    method: "POST",
  });
}

export function getResults(incidentId: string): Promise<IncidentReport> {
  return request<IncidentReport>(`/incidents/${encodeURIComponent(incidentId)}/results`);
}
