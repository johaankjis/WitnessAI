import Link from "next/link";

export const metadata = {
  title: "Archive sweep — Witness",
  description: "Planned batch review of closed claims with unwatched video.",
};

export default function SweepPage() {
  return (
    <div className="mx-auto max-w-3xl py-8">
      <p className="text-xs font-bold tracking-widest text-cyan-300 uppercase">Archive sweep</p>
      <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-50">
        Closed-claim review, planned.
      </h1>
      <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-slate-400">
        The archive sweep will run Witness over folders of closed claims and rank the ones where
        footage suggests the insurer should have recovered costs. This release prioritizes one
        incident reviewed end to end, so no sweep rankings exist yet — and none are faked here.
      </p>

      <div
        data-testid="sweep-placeholder"
        className="mt-6 rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-10 text-center"
      >
        <p className="text-sm font-semibold text-slate-300">No sweep data yet</p>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
          When the batch pipeline lands, this page will list ranked incidents with their verdict
          counts and evidence links. Until then, the demo incident below is the full experience.
        </p>
        <Link
          href="/incidents/demo-001"
          className="mt-5 inline-block rounded-md bg-cyan-400 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
        >
          Review the demo incident
        </Link>
      </div>
    </div>
  );
}
