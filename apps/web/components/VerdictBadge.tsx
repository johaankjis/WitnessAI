import type { Verdict } from "../lib/contracts";
import { verdictMeta } from "../lib/selectors";

const STYLES: Record<Verdict, string> = {
  supported: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  contradicted: "border-red-500/40 bg-red-500/10 text-red-300",
  not_visible: "border-slate-500/40 bg-slate-500/10 text-slate-300",
};

export default function VerdictBadge({ verdict, size = "md" }: { verdict: Verdict; size?: "sm" | "md" }) {
  const meta = verdictMeta(verdict);
  const sizing = size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs";
  return (
    <span
      role="status"
      aria-label={`Verdict: ${meta.label}`}
      title={meta.description}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-md border font-semibold tracking-wide uppercase ${sizing} ${STYLES[verdict]}`}
    >
      <span aria-hidden="true" className="font-bold">
        {meta.glyph}
      </span>
      {meta.label}
    </span>
  );
}
