"use client";

import type { AtomicClaim, ClaimVerdict } from "../lib/contracts";
import { categoryLabel, formatRange, primaryWindow } from "../lib/selectors";
import VerdictBadge from "./VerdictBadge";

interface ClaimRowProps {
  claim: AtomicClaim;
  verdict: ClaimVerdict | null;
  selected: boolean;
  onSelect: (claimId: string) => void;
}

export default function ClaimRow({ claim, verdict, selected, onSelect }: ClaimRowProps) {
  const window = primaryWindow(verdict);
  return (
    <button
      type="button"
      data-testid={`claim-row-${claim.id}`}
      aria-pressed={selected}
      aria-label={`${claim.text} — ${verdict ? `verdict ${verdict.verdict.replace("_", " ")}` : "verdict pending"}`}
      onClick={() => onSelect(claim.id)}
      className={`w-full rounded-lg border p-3 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400 ${
        selected
          ? "border-cyan-400/70 bg-cyan-400/10"
          : "border-slate-800 bg-slate-950/60 hover:border-slate-600"
      }`}
    >
      <span className="flex items-start justify-between gap-3">
        <span className="text-sm leading-snug font-medium text-slate-100">{claim.text}</span>
        {verdict && <VerdictBadge verdict={verdict.verdict} size="sm" />}
      </span>
      <span className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-400">
        <span className="font-mono">{claim.id}</span>
        <span>{categoryLabel(claim.category)}</span>
        {window && (
          <span className="font-mono tabular-nums">
            {formatRange(window.start_seconds, window.end_seconds)}
          </span>
        )}
        {!verdict && <span className="text-slate-500">Awaiting verdict</span>}
      </span>
    </button>
  );
}
