"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { DEMO_INCIDENT_ID } from "../lib/api";

export default function Home() {
  const router = useRouter();
  const [incidentId, setIncidentId] = useState(DEMO_INCIDENT_ID);

  return (
    <div className="mx-auto max-w-3xl py-8">
      <p className="text-xs font-bold tracking-widest text-cyan-300 uppercase">
        Claims workstation
      </p>
      <h1 className="mt-2 text-3xl font-extrabold tracking-tight text-slate-50 sm:text-4xl">
        Check every sentence against the footage.
      </h1>
      <p className="mt-3 max-w-2xl text-[15px] leading-relaxed text-slate-400">
        Witness splits each driver&apos;s statement into atomic claims, judges each one against
        the dashcam clip, and cross-checks it with detector measurements. Open an incident to
        review the evidence window behind every verdict.
      </p>

      <form
        className="mt-6 flex flex-col gap-3 sm:flex-row"
        onSubmit={(event) => {
          event.preventDefault();
          const id = incidentId.trim();
          if (id) router.push(`/incidents/${encodeURIComponent(id)}`);
        }}
      >
        <label htmlFor="incident-id" className="sr-only">
          Incident ID
        </label>
        <input
          id="incident-id"
          data-testid="incident-id-input"
          value={incidentId}
          onChange={(event) => setIncidentId(event.target.value)}
          placeholder="incident id, e.g. demo-001"
          spellCheck={false}
          className="flex-1 rounded-md border border-slate-700 bg-slate-900 px-4 py-2.5 font-mono text-sm text-slate-100 placeholder:text-slate-500 focus:border-cyan-400 focus:outline-none"
        />
        <button
          type="submit"
          className="rounded-md bg-cyan-400 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
        >
          Open incident
        </button>
      </form>

      <div className="mt-8 grid gap-3 sm:grid-cols-2">
        <Link
          href={`/incidents/${DEMO_INCIDENT_ID}`}
          className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 transition-colors hover:border-slate-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
        >
          <p className="text-sm font-bold text-slate-100">Demo incident · demo-001</p>
          <p className="mt-1 text-sm leading-relaxed text-slate-400">
            A synthetic lane-change dispute. Works offline in fixture mode when the API is down.
          </p>
        </Link>
        <Link
          href="/sweep"
          className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 transition-colors hover:border-slate-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
        >
          <p className="text-sm font-bold text-slate-100">Archive sweep</p>
          <p className="mt-1 text-sm leading-relaxed text-slate-400">
            Batch review of closed claims is planned. This release focuses on one incident end
            to end.
          </p>
        </Link>
      </div>

      <p className="mt-6 rounded-lg border border-slate-800 bg-slate-900/40 p-3 text-xs leading-relaxed text-slate-500">
        Demo data is synthetic and labeled as mock wherever it appears. Confidence is only shown
        when an adapter reports it, and it is never a fault score.
      </p>
    </div>
  );
}
