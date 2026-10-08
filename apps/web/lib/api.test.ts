import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ApiError,
  analyzeIncident,
  getIncident,
  getResults,
  isNotAnalyzed,
  isNotFound,
  isUnreachable,
} from "./api";
import { FIXTURE_INCIDENT, FIXTURE_REPORT, FIXTURE_STATUS } from "./fixtures";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("typed API client", () => {
  it("fetches an incident from the documented route", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(FIXTURE_INCIDENT));
    vi.stubGlobal("fetch", fetchMock);
    const incident = await getIncident("demo-001");
    expect(incident.id).toBe("demo-001");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/incidents/demo-001",
      expect.objectContaining({ headers: expect.anything() }),
    );
  });

  it("posts analysis without a body, then reads results", async () => {
    const fetchMock = vi
      .fn(async () => jsonResponse(FIXTURE_STATUS))
      .mockImplementationOnce(async () => jsonResponse(FIXTURE_STATUS));
    vi.stubGlobal("fetch", fetchMock);
    const status = await analyzeIncident("demo-001");
    expect(status.state).toBe("completed");
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/incidents/demo-001/analyze",
      expect.objectContaining({ method: "POST" }),
    );

    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse(FIXTURE_REPORT)));
    const report = await getResults("demo-001");
    expect(report.incident_id).toBe("demo-001");
    expect(report.human_review_required).toBe(true);
    expect(report.legal_fault_determination).toBe("not_provided");
  });

  it("surfaces FastAPI detail messages with status codes", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => jsonResponse({ detail: "Incident not found" }, 404)));
    const error = await getIncident("nope").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(404);
    expect((error as ApiError).detail).toBe("Incident not found");
    expect(isNotFound(error)).toBe(true);

    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse({ detail: "Analysis has not run; POST /analyze first" }, 409)),
    );
    const pending = await getResults("demo-001").catch((e: unknown) => e);
    expect(isNotAnalyzed(pending)).toBe(true);
  });

  it("maps network failures to status 0 for fixture fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        throw new TypeError("fetch failed");
      }),
    );
    const error = await getIncident("demo-001").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(0);
    expect(isUnreachable(error)).toBe(true);
  });
});
