import type { ReactNode } from "react";

function Panel({ children, testId }: { children: ReactNode; testId: string }) {
  return (
    <div
      data-testid={testId}
      className="rounded-xl border border-slate-800 bg-slate-900/60 px-6 py-10 text-center"
    >
      {children}
    </div>
  );
}

export function LoadingSkeleton({ label }: { label: string }) {
  return (
    <Panel testId="state-loading">
      <div
        aria-busy="true"
        aria-live="polite"
        className="mx-auto max-w-md animate-pulse space-y-4"
      >
        <div className="mx-auto h-3 w-40 rounded bg-slate-700" />
        <div className="h-40 rounded-lg bg-slate-800" />
        <div className="mx-auto h-3 w-64 rounded bg-slate-700" />
      </div>
      <p className="mt-5 text-sm text-slate-400">{label}</p>
    </Panel>
  );
}

export function ProcessingState({ detail }: { detail: string }) {
  return (
    <Panel testId="state-processing">
      <p className="text-sm font-semibold tracking-widest text-cyan-300 uppercase">Analyzing</p>
      <p className="mx-auto mt-3 max-w-md text-sm text-slate-300" aria-live="polite">
        {detail}
      </p>
      <div className="mx-auto mt-5 h-1.5 w-56 overflow-hidden rounded-full bg-slate-800">
        <div className="h-full w-1/2 animate-[processing-slide_1.2s_ease-in-out_infinite] rounded-full bg-cyan-400" />
      </div>
    </Panel>
  );
}

export function ErrorPanel({
  title,
  detail,
  onRetry,
  retryLabel = "Retry",
}: {
  title: string;
  detail: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  return (
    <Panel testId="state-error">
      <p className="text-sm font-semibold tracking-widest text-red-300 uppercase">Error</p>
      <h2 className="mt-3 text-lg font-bold text-slate-100">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">{detail}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-5 rounded-md border border-slate-600 bg-slate-800 px-4 py-2 text-sm font-semibold text-slate-100 transition-colors hover:bg-slate-700 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-cyan-400"
        >
          {retryLabel}
        </button>
      )}
    </Panel>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail: string;
  action?: ReactNode;
}) {
  return (
    <Panel testId="state-empty">
      <p className="text-sm font-semibold tracking-widest text-slate-400 uppercase">No results yet</p>
      <h2 className="mt-3 text-lg font-bold text-slate-100">{title}</h2>
      <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">{detail}</p>
      {action && <div className="mt-5">{action}</div>}
    </Panel>
  );
}
