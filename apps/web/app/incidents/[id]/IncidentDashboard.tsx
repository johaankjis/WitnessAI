"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import EvidencePanel from "../../../components/EvidencePanel";
import MockBanner from "../../../components/MockBanner";
import ReportPanel from "../../../components/ReportPanel";
import { EmptyState, ErrorPanel, LoadingSkeleton, ProcessingState } from "../../../components/StateViews";
import StatementColumn from "../../../components/StatementColumn";
import Timeline, { type TimelineMarker } from "../../../components/Timeline";
import VideoPlayer from "../../../components/VideoPlayer";
import type { Incident, IncidentReport } from "../../../lib/contracts";
import {
  ApiError,
  analyzeIncident,
  getIncident,
  getResults,
  isNotAnalyzed,
  isNotFound,
} from "../../../lib/api";
import {
  FIXTURE_INCIDENT,
  FIXTURE_INCIDENT_ID,
  FIXTURE_REPORT,
  fixtureForcedByEnv,
} from "../../../lib/fixtures";
import {
  formatTimestamp,
  observationsForClaim,
  primaryWindow,
  verdictForClaim,
} from "../../../lib/selectors";

type LoadPhase = "loading" | "ready" | "error";
type AnalysisPhase = "unknown" | "not-analyzed" | "analyzing" | "completed" | "failed";

interface Playhead {
  time: number;
  token: number;
}

const DRIVER_LETTERS = "ABCDEFGH";

function driverLabel(index: number): string {
  return `Driver ${DRIVER_LETTERS[index] ?? index + 1}`;
}

function fixtureRequestedInUrl(): boolean {
  if (typeof window === "undefined") return false;
  return new URLSearchParams(window.location.search).get("fixture") === "1";
}

export default function IncidentDashboard({ incidentId }: { incidentId: string }) {
  const [loadPhase, setLoadPhase] = useState<LoadPhase>("loading");
  const [analysisPhase, setAnalysisPhase] = useState<AnalysisPhase>("unknown");
  const [incident, setIncident] = useState<Incident | null>(null);
  const [report, setReport] = useState<IncidentReport | null>(null);
  const [loadError, setLoadError] = useState("");
  const [analysisError, setAnalysisError] = useState("");
  const [analysisDetail, setAnalysisDetail] = useState("");
  const [fixtureMode, setFixtureMode] = useState(false);
  const [fixtureReason, setFixtureReason] = useState("");
  const [selectedClaimId, setSelectedClaimId] = useState<string | null>(null);
  const [playhead, setPlayhead] = useState<Playhead>({ time: 0, token: 0 });
  const [reloadToken, setReloadToken] = useState(0);

  const enterFixtureMode = useCallback(
    (reason: string) => {
      setIncident(FIXTURE_INCIDENT);
      setReport(FIXTURE_REPORT);
      setLoadPhase("ready");
      setAnalysisPhase("completed");
      setFixtureMode(true);
      setFixtureReason(reason);
      setLoadError("");
      const firstClaim = FIXTURE_REPORT.claims[0];
      if (firstClaim) {
        setSelectedClaimId(firstClaim.id);
        const window = primaryWindow(verdictForClaim(FIXTURE_REPORT, firstClaim.id));
        if (window) setPlayhead((previous) => ({ time: window.start_seconds, token: previous.token + 1 }));
      }
    },
    [],
  );

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadPhase("loading");
      setAnalysisPhase("unknown");
      setLoadError("");
      setAnalysisError("");
      setReport(null);
      setSelectedClaimId(null);
      setPlayhead({ time: 0, token: 0 });
      setFixtureMode(false);
      setFixtureReason("");

      if (fixtureForcedByEnv() || fixtureRequestedInUrl()) {
        if (incidentId !== FIXTURE_INCIDENT_ID) {
          if (!cancelled) {
            setLoadPhase("error");
            setLoadError(
              `Fixture mode only covers ${FIXTURE_INCIDENT_ID}; "${incidentId}" needs the live API.`,
            );
          }
          return;
        }
        if (!cancelled) enterFixtureMode("requested (fixture=1)");
        return;
      }

      let loadedIncident: Incident;
      try {
        loadedIncident = await getIncident(incidentId);
      } catch (error) {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 0 && incidentId === FIXTURE_INCIDENT_ID) {
          enterFixtureMode(`API unreachable (${error.detail})`);
          return;
        }
        setLoadPhase("error");
        setLoadError(
          isNotFound(error)
            ? `Incident "${incidentId}" was not found. Check the ID or open ${FIXTURE_INCIDENT_ID}.`
            : error instanceof Error
              ? error.message
              : "Failed to load the incident.",
        );
        return;
      }
      if (cancelled) return;
      setIncident(loadedIncident);
      setLoadPhase("ready");

      try {
        const loadedReport = await getResults(incidentId);
        if (cancelled) return;
        setReport(loadedReport);
        setAnalysisPhase("completed");
        const firstClaim = loadedReport.claims[0];
        if (firstClaim) {
          setSelectedClaimId(firstClaim.id);
          const window = primaryWindow(verdictForClaim(loadedReport, firstClaim.id));
          if (window) setPlayhead((previous) => ({ time: window.start_seconds, token: previous.token + 1 }));
        }
      } catch (error) {
        if (cancelled) return;
        if (isNotAnalyzed(error)) {
          setAnalysisPhase("not-analyzed");
          return;
        }
        if (error instanceof ApiError && error.status === 0 && incidentId === FIXTURE_INCIDENT_ID) {
          enterFixtureMode(`results unreachable (${error.detail})`);
          return;
        }
        setAnalysisPhase("failed");
        setAnalysisError(error instanceof Error ? error.message : "Failed to load results.");
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [incidentId, reloadToken, enterFixtureMode]);

  const verdictByClaimId = useMemo(() => {
    const map = new Map<string, NonNullable<ReturnType<typeof verdictForClaim>>>();
    if (!report) return map;
    for (const verdict of report.verdicts) map.set(verdict.claim_id, verdict);
    return map;
  }, [report]);

  const claimById = useMemo(() => {
    const map = new Map<string, IncidentReport["claims"][number]>();
    if (!report) return map;
    for (const claim of report.claims) map.set(claim.id, claim);
    return map;
  }, [report]);

  const markers: TimelineMarker[] = useMemo(() => {
    if (!report) return [];
    const items: TimelineMarker[] = [];
    for (const verdict of report.verdicts) {
      const claim = claimById.get(verdict.claim_id);
      const window = primaryWindow(verdict);
      if (!claim || !window) continue;
      items.push({
        claimId: claim.id,
        claimText: claim.text,
        verdict: verdict.verdict,
        startSeconds: window.start_seconds,
        endSeconds: window.end_seconds,
      });
    }
    return items.sort((a, b) => a.startSeconds - b.startSeconds);
  }, [report, claimById]);

  const selectClaim = useCallback(
    (claimId: string) => {
      setSelectedClaimId(claimId);
      if (!report) return;
      const window = primaryWindow(verdictForClaim(report, claimId));
      if (window) {
        setPlayhead((previous) => ({ time: window.start_seconds, token: previous.token + 1 }));
      }
    },
    [report],
  );

  const runAnalysis = useCallback(async () => {
    setAnalysisPhase("analyzing");
    setAnalysisError("");
    setAnalysisDetail("Contacting the analysis backend…");
    try {
      const status = await analyzeIncident(incidentId);
      setAnalysisDetail(status.detail);
      const loadedReport = await getResults(incidentId);
      setReport(loadedReport);
      setAnalysisPhase("completed");
      const firstClaim = selectedClaimId ? claimById.get(selectedClaimId) : loadedReport.claims[0];
      const target = firstClaim ?? loadedReport.claims[0];
      if (target) {
        setSelectedClaimId(target.id);
        const window = primaryWindow(verdictForClaim(loadedReport, target.id));
        if (window) setPlayhead((previous) => ({ time: window.start_seconds, token: previous.token + 1 }));
      }
    } catch (error) {
      setAnalysisPhase(report ? "completed" : "failed");
      if (report) {
        setAnalysisError(
          `Re-analysis failed and the previous report was kept: ${error instanceof Error ? error.message : "unknown error"}`,
        );
      } else {
        setAnalysisError(error instanceof Error ? error.message : "Analysis failed.");
      }
    }
  }, [incidentId, report, selectedClaimId, claimById]);

  const retryLive = useCallback(() => {
    const url = new URL(window.location.href);
    url.searchParams.delete("fixture");
    window.location.href = url.toString();
  }, []);

  const selectedClaim = selectedClaimId ? (claimById.get(selectedClaimId) ?? null) : null;
  const selectedVerdict = selectedClaimId && report ? verdictForClaim(report, selectedClaimId) : null;
  const selectedObservations =
    selectedClaimId && report ? observationsForClaim(report, selectedClaimId) : [];

  if (loadPhase === "loading") {
    return <LoadingSkeleton label={`Loading incident ${incidentId}…`} />;
  }

  if (loadPhase === "error" || !incident) {
    return (
      <ErrorPanel
        title="Could not load this incident"
        detail={loadError || "The incident could not be loaded."}
        onRetry={() => setReloadToken((token) => token + 1)}
      />
    );
  }

  return (
    <div className="flex flex-col gap-4" data-testid="incident-dashboard">
      {incident.is_mock && (
        <MockBanner
          sourceLabel={fixtureMode ? "bundled fixture" : "backend mock adapter"}
        />
      )}
      {fixtureMode && (
        <div
          role="status"
          data-testid="fixture-chip"
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-cyan-500/40 bg-cyan-500/10 px-4 py-2.5 text-sm"
        >
          <p className="text-cyan-200">
            <span className="font-bold">Fixture mode.</span>{" "}
            <span className="text-cyan-200/80">
              Showing bundled {FIXTURE_INCIDENT_ID} data — {fixtureReason}. Not fresh analysis.
            </span>
          </p>
          <button
            type="button"
            onClick={retryLive}
            className="rounded-md border border-cyan-500/50 px-3 py-1 text-xs font-bold text-cyan-200 hover:bg-cyan-500/20 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
          >
            Retry live API
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs text-slate-500">{incident.id}</p>
          <h1 className="mt-1 text-2xl font-extrabold tracking-tight text-slate-50">
            {incident.title}
          </h1>
          <p className="mt-1 font-mono text-xs text-slate-500">
            duration {formatTimestamp(incident.duration_seconds)} · {incident.statements.length}{" "}
            statements · <span className="break-all">{incident.video_uri}</span>
          </p>
        </div>
        {!fixtureMode && (
          <div className="flex items-center gap-3">
            <span
              role="status"
              data-testid="analysis-state"
              className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-bold tracking-wide text-slate-300 uppercase"
            >
              {analysisPhase === "completed" && report
                ? "Completed"
                : analysisPhase === "analyzing"
                  ? "Processing"
                  : analysisPhase === "not-analyzed"
                    ? "Not analyzed"
                    : analysisPhase === "failed"
                      ? "Failed"
                      : "Loading"}
            </span>
            {(analysisPhase === "not-analyzed" ||
              analysisPhase === "failed" ||
              analysisPhase === "completed") && (
              <button
                type="button"
                data-testid="analyze-button"
                onClick={runAnalysis}
                className="rounded-md bg-cyan-400 px-4 py-2 text-sm font-bold text-slate-950 hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
              >
                {analysisPhase === "completed" ? "Re-run analysis" : "Run analysis"}
              </button>
            )}
          </div>
        )}
      </div>

      {analysisPhase === "not-analyzed" && (
        <EmptyState
          title="This incident has not been analyzed"
          detail="Statements are shown below. Run analysis to split them into atomic claims and judge each one against the footage."
          action={
            fixtureMode ? undefined : (
              <button
                type="button"
                data-testid="analyze-button-empty"
                onClick={runAnalysis}
                className="rounded-md bg-cyan-400 px-5 py-2.5 text-sm font-bold text-slate-950 hover:bg-cyan-300 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
              >
                Run analysis
              </button>
            )
          }
        />
      )}
      {analysisPhase === "analyzing" && (
        <ProcessingState detail={analysisDetail || "Running claim extraction and verification…"} />
      )}
      {analysisError && (
        <div
          role="alert"
          data-testid="analysis-error"
          className="rounded-lg border border-red-500/40 bg-red-500/10 px-4 py-3 text-sm text-red-200"
        >
          {analysisError}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-12">
        <div className="flex flex-col gap-4 xl:col-span-7">
          <VideoPlayer
            videoUri={incident.video_uri}
            durationSeconds={incident.duration_seconds}
            seekToSeconds={playhead.time}
            seekToken={playhead.token}
            onTimeChange={(time) => setPlayhead((previous) => ({ ...previous, time }))}
          />
          <Timeline
            durationSeconds={incident.duration_seconds}
            currentTimeSeconds={playhead.time}
            markers={markers}
            selectedClaimId={selectedClaimId}
            onSelectClaim={selectClaim}
          />
        </div>
        <div className="xl:col-span-5">
          <EvidencePanel
            claim={selectedClaim}
            verdict={selectedVerdict}
            observations={selectedObservations}
          />
        </div>
      </div>

      {incident.statements.length === 0 ? (
        <EmptyState
          title="No statements on this incident"
          detail="The backend returned an incident without driver statements, so there is nothing to review."
        />
      ) : (
        <div className="grid gap-4 md:grid-cols-2" data-testid="statements-grid">
          {incident.statements.map((statement, index) => (
            <StatementColumn
              key={statement.id}
              statement={statement}
              driverLabel={driverLabel(index)}
              claims={report ? report.claims.filter((c) => c.statement_id === statement.id) : []}
              verdictByClaimId={verdictByClaimId}
              selectedClaimId={selectedClaimId}
              analyzed={report !== null}
              onSelectClaim={selectClaim}
            />
          ))}
        </div>
      )}

      {report && <ReportPanel report={report} />}
    </div>
  );
}
