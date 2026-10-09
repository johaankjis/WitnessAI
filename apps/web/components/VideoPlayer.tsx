"use client";

import { useEffect, useRef, useState } from "react";
import { clampTime, formatTimestamp, isPlayableVideoUri } from "../lib/selectors";

interface VideoPlayerProps {
  videoUri: string;
  durationSeconds: number;
  /** Requested seek target. Applied whenever `seekToken` changes. */
  seekToSeconds: number | null;
  /** Increment to apply `seekToSeconds` (lets the same timestamp seek twice). */
  seekToken: number;
  onSeeked?: (seconds: number) => void;
  onTimeChange?: (seconds: number) => void;
}

/**
 * Synchronized evidence player. Real media URLs render a <video> element;
 * mock:// (or any non-media) URI renders a labeled placeholder that still
 * tracks the requested evidence timestamp — without pretending footage exists.
 */
export default function VideoPlayer({
  videoUri,
  durationSeconds,
  seekToSeconds,
  seekToken,
  onSeeked,
  onTimeChange,
}: VideoPlayerProps) {
  const playable = isPlayableVideoUri(videoUri);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    if (seekToSeconds === null) return;
    const target = clampTime(seekToSeconds, durationSeconds);
    setCurrentTime(target);
    const element = videoRef.current;
    if (element && playable) {
      try {
        element.currentTime = target;
      } catch {
        /* jsdom / unready media: readout still reflects the seek target */
      }
    }
    onSeeked?.(target);
    onTimeChange?.(target);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seekToken]);

  const progress = durationSeconds > 0 ? (currentTime / durationSeconds) * 100 : 0;

  return (
    <div
      data-testid="video-player"
      data-playable={playable ? "true" : "false"}
      data-current-time={currentTime.toFixed(1)}
      className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950"
    >
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-2">
        <p className="text-xs font-bold tracking-widest text-slate-400 uppercase">Dashcam evidence</p>
        <p
          data-testid="video-time-readout"
          aria-live="polite"
          className="font-mono text-sm font-semibold text-cyan-300 tabular-nums"
        >
          {formatTimestamp(currentTime)} <span className="text-slate-500">/ {formatTimestamp(durationSeconds)}</span>
        </p>
      </div>

      {playable ? (
        <video
          ref={videoRef}
          data-testid="video-element"
          controls
          preload="metadata"
          src={videoUri}
          className="aspect-video w-full bg-black"
          onLoadedMetadata={(event) => {
            if (seekToSeconds !== null) {
              event.currentTarget.currentTime = clampTime(seekToSeconds, durationSeconds);
            }
          }}
          onTimeUpdate={(event) => {
            const time = event.currentTarget.currentTime;
            setCurrentTime(time);
            onTimeChange?.(time);
          }}
        />
      ) : (
        <div className="flex aspect-video w-full flex-col items-center justify-center gap-3 bg-slate-950 px-6 text-center">
          <p className="rounded border border-amber-400/40 bg-amber-400/10 px-2 py-1 text-[11px] font-bold tracking-widest text-amber-300 uppercase">
            No playable footage
          </p>
          <p className="max-w-md text-sm text-slate-400">
            This incident references <span className="font-mono text-slate-300">{videoUri}</span>,
            which is not viewable media. Timestamps below identify the reviewed evidence window.
          </p>
          <p className="font-mono text-3xl font-bold text-slate-100 tabular-nums">
            {formatTimestamp(currentTime)}
          </p>
          <p className="text-xs text-slate-500">
            Select a claim to move this marker to its evidence window.
          </p>
        </div>
      )}

      <div
        className="h-1.5 w-full bg-slate-800"
        role="progressbar"
        aria-label="Playback position"
        aria-valuemin={0}
        aria-valuemax={Math.round(durationSeconds)}
        aria-valuenow={Math.round(currentTime)}
      >
        <div className="h-full bg-cyan-400 transition-[width]" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}
