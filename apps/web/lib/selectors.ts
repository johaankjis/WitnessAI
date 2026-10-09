import type {
  AtomicClaim,
  ClaimCategory,
  ClaimVerdict,
  DetectorObservation,
  EvidenceWindow,
  IncidentReport,
  Verdict,
} from "./contracts";

/** Join report claims to their parent driver statement (via statement_id). */
export function claimsForStatement(report: IncidentReport, statementId: string): AtomicClaim[] {
  return report.claims.filter((claim) => claim.statement_id === statementId);
}

/** Join a verdict to its claim (verdicts join by claim_id; exactly one per claim). */
export function verdictForClaim(report: IncidentReport, claimId: string): ClaimVerdict | null {
  return report.verdicts.find((verdict) => verdict.claim_id === claimId) ?? null;
}

/** Detector (YOLO) observations linked to a claim — kept separate from model evidence. */
export function observationsForClaim(
  report: IncidentReport,
  claimId: string,
): DetectorObservation[] {
  return report.observations.filter((observation) => observation.claim_id === claimId);
}

/** First evidence window drives video seeking and the timeline marker. */
export function primaryWindow(verdict: ClaimVerdict | null): EvidenceWindow | null {
  if (!verdict || verdict.evidence.length === 0) return null;
  return verdict.evidence[0];
}

export interface VerdictMeta {
  label: string;
  /** Text glyph so verdicts never rely on color alone. */
  glyph: string;
  description: string;
}

const VERDICT_META: Record<Verdict, VerdictMeta> = {
  supported: { label: "Supported", glyph: "✓", description: "Evidence in the footage supports this claim." },
  contradicted: { label: "Contradicted", glyph: "✕", description: "Evidence in the footage contradicts this claim." },
  not_visible: { label: "Not visible", glyph: "○", description: "The relevant moment is not visible; absence is not contradiction." },
};

export function verdictMeta(verdict: Verdict): VerdictMeta {
  return VERDICT_META[verdict];
}

const CATEGORY_LABELS: Record<ClaimCategory, string> = {
  lane_change: "Lane change",
  braking: "Braking",
  traffic_signal: "Traffic signal",
  other: "Other",
};

export function categoryLabel(category: ClaimCategory): string {
  return CATEGORY_LABELS[category];
}

export interface VerdictCounts {
  supported: number;
  contradicted: number;
  not_visible: number;
}

export function verdictCounts(report: IncidentReport): VerdictCounts {
  const counts: VerdictCounts = { supported: 0, contradicted: 0, not_visible: 0 };
  for (const verdict of report.verdicts) counts[verdict.verdict] += 1;
  return counts;
}

/**
 * Only real media URLs are playable. mock:// URIs (and any other
 * non-media scheme) render a labeled placeholder instead of a <video>.
 */
export function isPlayableVideoUri(videoUri: string): boolean {
  return /^(https?:|blob:|data:video\/)/i.test(videoUri.trim());
}

/** Seconds since video start, rendered as m:ss.t (e.g. 0:08.0). */
export function formatTimestamp(totalSeconds: number): string {
  const clamped = Math.max(0, totalSeconds);
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped - minutes * 60;
  const whole = Math.floor(seconds);
  const tenths = Math.floor((seconds - whole) * 10);
  return `${minutes}:${String(whole).padStart(2, "0")}.${tenths}`;
}

export function formatRange(startSeconds: number, endSeconds: number): string {
  return `${formatTimestamp(startSeconds)} – ${formatTimestamp(endSeconds)}`;
}

export function clampTime(value: number, durationSeconds: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(Math.max(0, value), Math.max(0, durationSeconds));
}

/**
 * Renders adapter-reported confidence honestly: null stays "not reported"
 * and real values are labeled uncalibrated so they never read as certainty.
 */
export function formatConfidence(confidence: number | null | undefined): string {
  if (confidence === null || confidence === undefined) return "Not reported";
  return `${Math.round(confidence * 100)}% (adapter-reported, uncalibrated)`;
}
