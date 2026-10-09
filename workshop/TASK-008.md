# TASK-008 — full parent playback and evidence timeline

Workshop-only change on `feature/task-005-vast-workshop`. No deployment or VAST/GPU
requests were made from the Mac. `apps/api`, `apps/web`, claim verdict logic,
provenance validation and inference/preflight implementations are unchanged.

## Playback API

`GET /api/media/full` streams only the configured `INCIDENT["original_video"]`
through the existing authenticated VSS client. It requires permitted footage and
configured VSS credentials; synthetic mode has no footage. Caller query parameters
(including source/token overrides) are rejected. This preserves the existing public
workshop access model; it does not introduce visitor accounts or browser JWTs.

Single closed, open-ended and suffix byte ranges are forwarded. Successful upstream
200/206 responses preserve numeric Content-Length and Content-Range as applicable;
Accept-Ranges is bytes. VAST's verified binary/octet-stream is served as video/mp4
for this fixed MP4 source. Invalid ranges return 400, upstream unsatisfiable ranges
return 416, authorization/configuration/fixture failures return 403/503/404, and
upstream authentication or retrieval failures return sanitized 502 errors. No
upstream cookies, redirects, tokens, signed URLs or raw S3 playback links are sent
to the player. Responses use no-store and stream in 64 KiB chunks rather than
buffering the parent video. Existing evidence provenance identifiers are unchanged.

`GET /api/media/stream` remains the segment fallback. Review UI metadata now points
video_url at the full route and fallback_video_url at the segment route. The same
proxy validation and error sanitization apply to both routes. Live analysis still
retrieves only `INCIDENT["source"]` (25–30 seconds), subject to its existing 20 MiB
limit, GPU configuration and pod preflight requirements.

## UI

The main player loads the parent video. Six native keyboard-accessible buttons sit
beside it (stacked on narrow screens), use parent timestamps, and update the existing
claim inspector. The timeline highlights the selected claim; the player shows its
live parent position, a proportional 25–30 second analyzed band and explicit text
when viewing context outside the analyzed window. Duration comes from media metadata,
not an invented video length. Search synthesis and agent text remain advisory;
observational captions/detections and human-review disclaimers remain visible.

A media error switches once to the segment route, labels the fallback, and converts
the selected claim seek to clip-relative time. Further failure is explicitly shown;
there is no retry loop. Pending metadata seeks use the most recent claim selection.
Reload evidence retries parent playback. Native playback controls remain available.

## Offline validation

- Workshop suite: 210 passed, including mocked range/auth/error/allowlist tests and
  execution of the actual UI with a mocked DOM/player in Node.
- Repository suite: 209 passed, 3 skipped.
- Contract export completed; generated shared contracts unchanged.
- JavaScript syntax and git whitespace checks passed.
- Release preflight and archive manifest/checksum verification completed offline.

No real browser decoding of the VAST video or live upstream connection was tested.
The supplied successful 206 probe is the source of the parent-video availability
assumption. Final playback smoke testing must occur from the authorized VM/deployed
application; this release is packaged only, preserving the working deployment.
