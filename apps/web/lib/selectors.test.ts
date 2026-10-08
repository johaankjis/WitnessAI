import { describe, expect, it } from "vitest";
import { FIXTURE_REPORT } from "./fixtures";
import {
  categoryLabel,
  clampTime,
  claimsForStatement,
  formatConfidence,
  formatRange,
  formatTimestamp,
  isPlayableVideoUri,
  observationsForClaim,
  primaryWindow,
  verdictCounts,
  verdictForClaim,
  verdictMeta,
} from "./selectors";

describe("contract joins", () => {
  it("joins claims to statements via statement_id", () => {
    expect(claimsForStatement(FIXTURE_REPORT, "statement-a").map((c) => c.id)).toEqual([
      "c1",
      "c2",
      "c3",
    ]);
    expect(claimsForStatement(FIXTURE_REPORT, "statement-b").map((c) => c.id)).toEqual([
      "c4",
      "c5",
    ]);
  });

  it("joins verdicts to claims via claim_id", () => {
    expect(verdictForClaim(FIXTURE_REPORT, "c4")?.verdict).toBe("contradicted");
    expect(verdictForClaim(FIXTURE_REPORT, "c3")?.verdict).toBe("not_visible");
    expect(verdictForClaim(FIXTURE_REPORT, "missing")).toBeNull();
  });

  it("keeps detector observations separate from model evidence", () => {
    expect(observationsForClaim(FIXTURE_REPORT, "c1").map((o) => o.id)).toEqual([
      "mock-observation-1",
    ]);
    expect(observationsForClaim(FIXTURE_REPORT, "c2")).toEqual([]);
  });

  it("exposes the primary evidence window for seeking", () => {
    const window = primaryWindow(verdictForClaim(FIXTURE_REPORT, "c1"));
    expect(window?.start_seconds).toBe(8.0);
    expect(window?.end_seconds).toBe(12.0);
    expect(primaryWindow(null)).toBeNull();
  });

  it("counts verdicts by value", () => {
    expect(verdictCounts(FIXTURE_REPORT)).toEqual({
      supported: 2,
      contradicted: 2,
      not_visible: 1,
    });
  });
});

describe("verdict presentation", () => {
  it("labels every verdict with text and glyph (never color alone)", () => {
    expect(verdictMeta("supported")).toMatchObject({ label: "Supported", glyph: "✓" });
    expect(verdictMeta("contradicted")).toMatchObject({ label: "Contradicted", glyph: "✕" });
    expect(verdictMeta("not_visible")).toMatchObject({ label: "Not visible", glyph: "○" });
  });

  it("labels claim categories", () => {
    expect(categoryLabel("traffic_signal")).toBe("Traffic signal");
    expect(categoryLabel("lane_change")).toBe("Lane change");
  });
});

describe("timestamps", () => {
  it("formats evidence timestamps as m:ss.t", () => {
    expect(formatTimestamp(8)).toBe("0:08.0");
    expect(formatTimestamp(75.25)).toBe("1:15.2");
  });

  it("formats evidence ranges", () => {
    expect(formatRange(8, 12)).toBe("0:08.0 – 0:12.0");
  });

  it("clamps seek targets to the incident duration", () => {
    expect(clampTime(-3, 20)).toBe(0);
    expect(clampTime(99, 20)).toBe(20);
    expect(clampTime(8, 20)).toBe(8);
  });
});

describe("media honesty", () => {
  it("refuses to play mock:// URIs as footage", () => {
    expect(isPlayableVideoUri("mock://demo-001/no-video")).toBe(false);
    expect(isPlayableVideoUri("  mock://x")).toBe(false);
  });

  it("accepts real media URLs", () => {
    expect(isPlayableVideoUri("https://cdn.example/clip.mp4")).toBe(true);
    expect(isPlayableVideoUri("http://localhost:8000/media/a.mp4")).toBe(true);
  });

  it("never invents confidence", () => {
    expect(formatConfidence(null)).toBe("Not reported");
    expect(formatConfidence(undefined)).toBe("Not reported");
    expect(formatConfidence(0.5)).toContain("uncalibrated");
  });
});
