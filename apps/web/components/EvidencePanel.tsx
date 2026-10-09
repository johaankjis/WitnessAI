import type {
  AtomicClaim,
  ClaimVerdict,
  DetectorObservation,
  EvidenceWindow,
  Provenance,
} from "../lib/contracts";
import {
  categoryLabel,
  formatConfidence,
  formatRange,
  formatTimestamp,
} from "../lib/selectors";
import VerdictBadge from "./VerdictBadge";

interface EvidencePanelProps {
  claim: AtomicClaim | null;
  verdict: ClaimVerdict | null;
  observations: DetectorObservation[];
}

function ProvenanceLine({ provenance }: { provenance: Provenance }) {
  return (
    <dl className="grid grid-cols-[86px_1fr] gap-x-3 gap-y-1 font-mono text-xs">
      <dt className="text-slate-500">adapter</dt>
      <dd className="text-slate-300">
        {provenance.adapter} <span className="text-slate-500">v{provenance.version}</span>
      </dd>
      <dt className="text-slate-500">source</dt>
      <dd className="text-slate-300">{provenance.source}</dd>
      <dt className="text-slate-500">mock</dt>
      <dd className={provenance.is_mock ? "text-amber-300" : "text-slate-300"}>
        {provenance.is_mock ? "yes — synthetic" : "no"}
      </dd>
    </dl>
  );
}

function WindowCard({ window }: { window: EvidenceWindow }) {
  const visible = window.visibility === "visible";
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <span
          className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-[11px] font-bold tracking-wide uppercase ${
            visible
              ? "border-cyan-500/40 bg-cyan-500/10 text-cyan-300"
              : "border-slate-500/40 bg-slate-500/10 text-slate-300"
          }`}
        >
          <span aria-hidden="true">{visible ? "◉" : "◌"}</span>
          {visible ? "Visible" : "Not visible"}
        </span>
        <span className="font-mono text-xs font-semibold text-slate-200 tabular-nums">
          {formatRange(window.start_seconds, window.end_seconds)}
        </span>
      </div>
      <p className="mt-2 text-sm leading-relaxed text-slate-300">{window.description}</p>
      <p className="mt-1 truncate font-mono text-[11px] text-slate-500" title={window.video_uri}>
        {window.video_uri}
      </p>
      <div className="mt-2 border-t border-slate-800 pt-2">
        <ProvenanceLine provenance={window.provenance} />
      </div>
    </div>
  );
}

export default function EvidencePanel({ claim, verdict, observations }: EvidencePanelProps) {
  if (!claim || !verdict) {
    return (
      <div
        data-testid="evidence-panel"
        className="flex h-full min-h-64 flex-col items-center justify-center rounded-xl border border-dashed border-slate-700 bg-slate-900/40 px-6 py-10 text-center"
      >
        <p className="text-sm font-semibold text-slate-300">No claim selected</p>
        <p className="mt-2 max-w-xs text-sm text-slate-500">
          Select an atomic claim from either statement — or a marker on the timeline — to inspect
          its evidence, provenance, and uncertainty.
        </p>
      </div>
    );
  }

  const primary = verdict.evidence[0];
  const anyMock =
    verdict.provenance.is_mock || verdict.evidence.some((w) => w.provenance.is_mock);

  return (
    <article
      data-testid="evidence-panel"
      aria-label={`Evidence for claim ${claim.id}`}
      className="flex flex-col gap-4 rounded-xl border border-slate-800 bg-slate-900/60 p-5"
    >
      <header>
        <div className="flex flex-wrap items-center gap-2">
          <VerdictBadge verdict={verdict.verdict} />
          <span className="font-mono text-xs text-slate-500">{claim.id}</span>
          <span className="text-xs text-slate-500">
            {categoryLabel(claim.category)} · subject {claim.subject}
          </span>
        </div>
        <h2 className="mt-2 text-lg leading-snug font-bold text-slate-50">{claim.text}</h2>
        {primary && (
          <p className="mt-1 font-mono text-xs text-cyan-300 tabular-nums">
            Evidence window starts at {formatTimestamp(primary.start_seconds)} — the player seeks
            here on selection.
          </p>
        )}
      </header>

      <section aria-label="Assessment">
        <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase">Assessment</h3>
        <p className="mt-1.5 text-sm leading-relaxed text-slate-200">{verdict.explanation}</p>
        <div className="mt-2 rounded-lg border border-slate-800 bg-slate-950/60 p-3">
          <p className="text-xs font-bold tracking-widest text-slate-500 uppercase">Uncertainty</p>
          <p className="mt-1 text-sm text-slate-300">{verdict.uncertainty}</p>
          <p className="mt-2 text-xs text-slate-500">
            Confidence:{" "}
            <span className="font-semibold text-slate-300">
              {formatConfidence(verdict.confidence)}
            </span>
          </p>
        </div>
        <div className="mt-2">
          <ProvenanceLine provenance={verdict.provenance} />
        </div>
      </section>

      <section aria-label="Model evidence">
        <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase">
          Model evidence ({verdict.evidence.length})
        </h3>
        <div className="mt-2 flex flex-col gap-2">
          {verdict.evidence.map((window, index) => (
            <WindowCard key={`${window.start_seconds}-${window.end_seconds}-${index}`} window={window} />
          ))}
        </div>
      </section>

      <section aria-label="Detector observations">
        <h3 className="text-xs font-bold tracking-widest text-slate-400 uppercase">
          Detector observations — YOLO cross-check ({observations.length})
        </h3>
        {observations.length === 0 ? (
          <p className="mt-2 rounded-lg border border-dashed border-slate-700 px-3 py-3 text-sm text-slate-500">
            No detector observations are linked to this claim. Missing detector evidence is not
            contradiction.
          </p>
        ) : (
          <div className="mt-2 flex flex-col gap-2">
            {observations.map((observation) => (
              <div
                key={observation.id}
                className="rounded-lg border border-slate-800 bg-slate-950/60 p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-xs font-semibold text-slate-200">
                    {observation.label}
                  </span>
                  <span className="font-mono text-[11px] text-slate-500">{observation.id}</span>
                </div>
                <p className="mt-2 font-mono text-xs text-slate-300 tabular-nums">
                  {formatRange(
                    observation.evidence.start_seconds,
                    observation.evidence.end_seconds,
                  )}
                </p>
                <p className="mt-1 text-sm text-slate-400">{observation.evidence.description}</p>
                <p className="mt-1 text-xs text-slate-500">
                  Confidence:{" "}
                  <span className="font-semibold text-slate-300">
                    {formatConfidence(observation.confidence)}
                  </span>
                </p>
                <div className="mt-2 border-t border-slate-800 pt-2">
                  <ProvenanceLine provenance={observation.provenance} />
                </div>
              </div>
            ))}
          </div>
        )}
        {anyMock && observations.length > 0 && (
          <p className="mt-2 text-xs leading-relaxed text-amber-200/90">
            These mock observations are scripted fixture data, not independent corroboration of the
            model evidence above.
          </p>
        )}
      </section>
    </article>
  );
}
