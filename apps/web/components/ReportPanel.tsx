import type { IncidentReport } from "../lib/contracts";
import { verdictCounts } from "../lib/selectors";
import VerdictBadge from "./VerdictBadge";

export default function ReportPanel({ report }: { report: IncidentReport }) {
  const counts = verdictCounts(report);
  return (
    <section
      aria-label="Incident report"
      data-testid="report-panel"
      className="rounded-xl border border-slate-800 bg-slate-900/60 p-5"
    >
      <h2 className="text-xs font-bold tracking-widest text-slate-400 uppercase">
        Incident report
      </h2>
      <p className="mt-2 text-[15px] leading-relaxed text-slate-200">{report.summary}</p>

      <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-2 py-3">
          <dt className="order-2 mt-1.5 flex justify-center">
            <VerdictBadge verdict="supported" size="sm" />
          </dt>
          <dd className="text-2xl font-extrabold text-slate-50 tabular-nums">{counts.supported}</dd>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-2 py-3">
          <dt className="order-2 mt-1.5 flex justify-center">
            <VerdictBadge verdict="contradicted" size="sm" />
          </dt>
          <dd className="text-2xl font-extrabold text-slate-50 tabular-nums">{counts.contradicted}</dd>
        </div>
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 px-2 py-3">
          <dt className="order-2 mt-1.5 flex justify-center">
            <VerdictBadge verdict="not_visible" size="sm" />
          </dt>
          <dd className="text-2xl font-extrabold text-slate-50 tabular-nums">{counts.not_visible}</dd>
        </div>
      </dl>

      <div className="mt-4 rounded-lg border border-cyan-500/30 bg-cyan-500/5 p-3">
        <p className="flex items-center gap-2 text-sm font-bold text-cyan-200">
          <span aria-hidden="true">◈</span> Human review: required
        </p>
        <p className="mt-1 text-sm leading-relaxed text-slate-300">
          These verdicts are investigative leads, not findings. An adjuster must review the cited
          evidence windows before any decision.
        </p>
      </div>

      <p className="mt-3 rounded-lg border border-slate-700 bg-slate-950/60 p-3 text-xs leading-relaxed text-slate-400">
        No legal fault determination is provided. Nothing in this report is a binding legal
        conclusion about liability.
      </p>

      <p className="mt-3 font-mono text-[11px] text-slate-500">
        schema {report.schema_version} · {report.claims.length} claims ·{" "}
        {report.observations.length} detector observations
      </p>
    </section>
  );
}
