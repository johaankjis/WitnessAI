"use client";

import type { Verdict } from "../lib/contracts";
import { formatRange, formatTimestamp, verdictMeta } from "../lib/selectors";

export interface TimelineMarker {
  claimId: string;
  claimText: string;
  verdict: Verdict;
  startSeconds: number;
  endSeconds: number;
}

interface TimelineProps {
  durationSeconds: number;
  currentTimeSeconds: number;
  markers: TimelineMarker[];
  selectedClaimId: string | null;
  onSelectClaim: (claimId: string) => void;
}

const MARKER_STYLES: Record<Verdict, string> = {
  supported: "border-emerald-400 bg-emerald-500 text-slate-950",
  contradicted: "border-red-400 bg-red-500 text-slate-950",
  not_visible: "border-slate-400 bg-slate-500 text-slate-950",
};

const SEGMENT_STYLES: Record<Verdict, string> = {
  supported: "bg-emerald-500/25 border-emerald-500/50",
  contradicted: "bg-red-500/25 border-red-500/50",
  not_visible: "bg-slate-500/20 border-slate-500/50",
};

function percent(time: number, duration: number): number {
  if (duration <= 0) return 0;
  return Math.min(100, Math.max(0, (time / duration) * 100));
}

export default function Timeline({
  durationSeconds,
  currentTimeSeconds,
  markers,
  selectedClaimId,
  onSelectClaim,
}: TimelineProps) {
  return (
    <div
      data-testid="incident-timeline"
      className="rounded-xl border border-slate-800 bg-slate-900/60 px-4 pt-3 pb-4"
    >
      <div className="flex items-center justify-between">
        <p className="text-xs font-bold tracking-widest text-slate-400 uppercase">
          Incident timeline
        </p>
        <p className="font-mono text-xs text-slate-500 tabular-nums">
          {formatTimestamp(currentTimeSeconds)} / {formatTimestamp(durationSeconds)}
        </p>
      </div>

      <div className="relative mt-8 h-16" role="group" aria-label="Evidence markers">
        <div className="absolute top-1/2 right-0 left-0 h-2 -translate-y-1/2 rounded-full bg-slate-800" />
        {markers.map((marker, index) => {
          const lane = index % 3;
          const left = percent(marker.startSeconds, durationSeconds);
          const width = Math.max(
            2,
            percent(marker.endSeconds, durationSeconds) - left,
          );
          const meta = verdictMeta(marker.verdict);
          const selected = marker.claimId === selectedClaimId;
          return (
            <div key={`${marker.claimId}-${marker.startSeconds}`}>
              <div
                aria-hidden="true"
                title={`${marker.claimId}: ${formatRange(marker.startSeconds, marker.endSeconds)}`}
                className={`absolute top-1/2 h-2 -translate-y-1/2 rounded-full border ${SEGMENT_STYLES[marker.verdict]}`}
                style={{ left: `${left}%`, width: `${width}%` }}
              />
              <button
                type="button"
                data-testid={`timeline-marker-${marker.claimId}`}
                aria-pressed={selected}
                aria-label={`Claim ${marker.claimId}, ${meta.label}, evidence ${formatRange(marker.startSeconds, marker.endSeconds)}: ${marker.claimText}`}
                title={`${marker.claimId} · ${meta.label} · ${formatRange(marker.startSeconds, marker.endSeconds)}`}
                onClick={() => onSelectClaim(marker.claimId)}
                style={{ left: `calc(${left}% - 11px)`, top: `${lane * 22 - 34}px` }}
                className={`absolute flex h-[22px] min-w-[22px] items-center justify-center rounded-full border-2 px-1 text-[11px] font-extrabold transition-transform focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400 ${MARKER_STYLES[marker.verdict]} ${selected ? "ring-2 ring-cyan-300 ring-offset-2 ring-offset-slate-900" : ""}`}
              >
                <span aria-hidden="true">{meta.glyph}</span>
              </button>
            </div>
          );
        })}
        <div
          aria-hidden="true"
          data-testid="timeline-playhead"
          className="absolute top-0 bottom-0 w-0.5 bg-cyan-300"
          style={{ left: `${percent(currentTimeSeconds, durationSeconds)}%` }}
        />
      </div>

      <div className="mt-1 flex justify-between font-mono text-[11px] text-slate-500 tabular-nums">
        <span>{formatTimestamp(0)}</span>
        <span>{formatTimestamp(durationSeconds)}</span>
      </div>

      {markers.length === 0 && (
        <p className="mt-2 text-center text-xs text-slate-500">
          Evidence markers appear here after analysis.
        </p>
      )}
    </div>
  );
}
