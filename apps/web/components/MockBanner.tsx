export default function MockBanner({ sourceLabel }: { sourceLabel: string }) {
  return (
    <div
      role="alert"
      data-testid="mock-banner"
      className="flex items-center gap-3 rounded-lg border border-amber-400/50 bg-amber-400/10 px-4 py-2.5 text-sm"
    >
      <span
        aria-hidden="true"
        className="rounded bg-amber-400 px-2 py-0.5 text-[11px] font-extrabold tracking-widest text-slate-950 uppercase"
      >
        Demo / Mock
      </span>
      <p className="text-amber-200">
        Synthetic demonstration data ({sourceLabel}). No real footage was analyzed. Human review is
        required.
      </p>
    </div>
  );
}
