"use client";

import type { AtomicClaim, ClaimVerdict, DriverStatement } from "../lib/contracts";
import ClaimRow from "./ClaimRow";

interface StatementColumnProps {
  statement: DriverStatement;
  driverLabel: string;
  claims: AtomicClaim[];
  verdictByClaimId: Map<string, ClaimVerdict>;
  selectedClaimId: string | null;
  analyzed: boolean;
  onSelectClaim: (claimId: string) => void;
}

export default function StatementColumn({
  statement,
  driverLabel,
  claims,
  verdictByClaimId,
  selectedClaimId,
  analyzed,
  onSelectClaim,
}: StatementColumnProps) {
  return (
    <section
      aria-label={`${driverLabel} statement`}
      data-testid={`statement-${statement.id}`}
      className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/60"
    >
      <header className="border-b border-slate-800 px-5 pt-4 pb-3">
        <p className="text-xs font-bold tracking-widest text-slate-400 uppercase">{driverLabel}</p>
        <p className="mt-1 font-mono text-xs text-slate-500">{statement.id}</p>
      </header>
      <blockquote className="border-b border-slate-800 px-5 py-4 text-[15px] leading-relaxed text-slate-200">
        &ldquo;{statement.text}&rdquo;
      </blockquote>
      <div className="flex flex-col gap-2 px-4 py-4">
        <p className="px-1 text-xs font-semibold tracking-widest text-slate-500 uppercase">
          Atomic claims{claims.length > 0 ? ` (${claims.length})` : ""}
        </p>
        {!analyzed && (
          <p className="rounded-lg border border-dashed border-slate-700 px-3 py-4 text-center text-sm text-slate-500">
            Run analysis to split this statement into checkable claims.
          </p>
        )}
        {analyzed && claims.length === 0 && (
          <p className="rounded-lg border border-dashed border-slate-700 px-3 py-4 text-center text-sm text-slate-500">
            No atomic claims were extracted from this statement.
          </p>
        )}
        {claims.map((claim) => (
          <ClaimRow
            key={claim.id}
            claim={claim}
            verdict={verdictByClaimId.get(claim.id) ?? null}
            selected={selectedClaimId === claim.id}
            onSelect={onSelectClaim}
          />
        ))}
      </div>
    </section>
  );
}
