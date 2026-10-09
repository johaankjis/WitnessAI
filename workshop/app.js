/* Witness workshop UI — no credentials or Bearer [REDACTED] in the client. */
(function () {
  // /app is the workshop ingress prefix; upstream may strip it.
  const base = location.pathname === "/app" || location.pathname.startsWith("/app/") ? "/app" : "";
  const apiUrl = (path) => base + path;
  const state = {
    review: null,
    selectedClaimId: null,
  };

  const $ = (id) => document.getElementById(id);

  const VERDICT_ICON = {
    supported: "\u2713",
    contradicted: "\u2715",
    not_visible: "\u25CB",
  };

  function verdictClass(v) {
    if (v === "supported") return "supported";
    if (v === "contradicted") return "contradicted";
    return "not_visible";
  }

  function verdictIcon(v) {
    return VERDICT_ICON[v] || VERDICT_ICON.not_visible;
  }

  function fmtSec(x) {
    const n = Number(x);
    return Number.isFinite(n) ? n.toFixed(1) + "s" : "?";
  }

  function clipTimeLabel(row) {
    return `clip ${fmtSec(row.seek_sec)} \u00B7 video ${fmtSec(row.seek_absolute_sec)}`;
  }

  async function fetchReview(includeAgent) {
    $("load-status").textContent = includeAgent
      ? "Loading evidence + scoped agent notes\u2026"
      : "Loading review\u2026";
    $("load-status").classList.remove("err");
    const url = "/api/review" + (includeAgent ? "?include_agent=true" : "");
    const res = await fetch(apiUrl(url));
    if (!res.ok) {
      const body = await res.text();
      throw new Error(`API ${res.status}: ${body.slice(0, 240)}`);
    }
    return res.json();
  }

  function renderChips(review) {
    const inc = review.incident || {};
    const w = inc.evidence_window_sec || {};
    const chips = [
      review.synthetic ? "SYNTHETIC FIXTURE" : "VAST EVIDENCE",
      `ns:${inc.team_namespace || "?"}`,
      `${inc.location || "?"}/${inc.camera_id || "?"}`,
      `window ${w.start}\u2013${w.end}s`,
      inc.segment_filename || "",
    ];
    $("chips").innerHTML = chips
      .filter(Boolean)
      .map((c) => `<span class="chip">${escapeHtml(c)}</span>`)
      .join("");
  }

  function renderSummary(review) {
    const counts = { supported: 0, contradicted: 0, not_visible: 0 };
    for (const row of review.claim_reviews || []) {
      const cls = verdictClass(row.verdict && row.verdict.verdict);
      counts[cls] += 1;
    }
    const total = (review.claim_reviews || []).length;
    $("verdict-summary").innerHTML = `
      <span class="vs-pill supported"><b>${counts.supported}</b><small>Supported</small></span>
      <span class="vs-pill contradicted"><b>${counts.contradicted}</b><small>Contradicted</small></span>
      <span class="vs-pill not_visible"><b>${counts.not_visible}</b><small>Not visible</small></span>
      <span class="vs-pill"><b>${total}</b><small>claims</small></span>`;
  }

  function escapeHtml(s) {
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function claimById(id) {
    return (state.review?.claim_reviews || []).find((r) => r.claim.id === id);
  }

  function orderedClaims() {
    return (state.review?.claim_reviews || []).map((r) => r.claim.id);
  }

  function badgeHtml(verdict, label) {
    const cls = verdictClass(verdict);
    return `<span class="badge ${cls}"><span class="ico" aria-hidden="true">${verdictIcon(verdict)}</span>${escapeHtml(label)}</span>`;
  }

  function renderStatements(review) {
    const byStmt = {};
    for (const row of review.claim_reviews || []) {
      const sid = row.claim.statement_id;
      if (!byStmt[sid]) byStmt[sid] = [];
      byStmt[sid].push(row);
    }
    const root = $("statements");
    root.innerHTML = (review.statements || [])
      .map((stmt) => {
        const rows = byStmt[stmt.id] || [];
        const claimsHtml = rows
          .map((row) => {
            const v = row.verdict;
            const selected = state.selectedClaimId === row.claim.id;
            return `
              <button type="button" class="claim${selected ? " selected" : ""}" data-claim="${escapeHtml(row.claim.id)}"
                aria-pressed="${selected}" aria-label="Inspect claim: ${escapeHtml(row.claim.text)}">
                <span class="claim-text">${escapeHtml(row.claim.text)}</span>
                <span class="claim-foot">
                  ${badgeHtml(v.verdict, v.verdict_label)}
                  <span class="claim-time">${escapeHtml(clipTimeLabel(row))}</span>
                </span>
              </button>`;
          })
          .join("");
        return `
          <div class="panel statement">
            <div class="label-row">
              <div class="label">${escapeHtml(stmt.label)}</div>
              <span class="illust">Illustrative \u00B7 team-authored</span>
            </div>
            <div class="body">${escapeHtml(stmt.text)}</div>
            ${claimsHtml}
          </div>`;
      })
      .join("");

    root.querySelectorAll(".claim").forEach((el) => {
      el.addEventListener("click", () => selectClaim(el.getAttribute("data-claim")));
    });
  }

  function renderTimeline(review) {
    const root = $("timeline");
    const rows = [...(review.timeline || [])].sort((a, b) => Number(a.seek_sec) - Number(b.seek_sec));
    root.innerHTML = rows
      .map((t) => {
        const active = state.selectedClaimId === t.claim_id;
        return `
          <button type="button" role="listitem" class="tl-btn${active ? " active" : ""}" data-claim="${escapeHtml(t.claim_id)}"
            ${active ? 'aria-current="true"' : ""} aria-label="Seek to ${escapeHtml(t.label)} at clip ${fmtSec(t.seek_sec)}">
            <div class="t">${fmtSec(t.seek_sec)} \u00B7 abs ${fmtSec(t.seek_absolute_sec)}</div>
            <div class="tl-label">${escapeHtml(t.label)}</div>
            ${badgeHtml(t.verdict, t.verdict_label)}
          </button>`;
      })
      .join("");
    root.querySelectorAll(".tl-btn").forEach((btn) => {
      btn.addEventListener("click", () => selectClaim(btn.getAttribute("data-claim")));
    });
  }

  function cueChips(label, hits) {
    const chips = (hits && hits.length)
      ? hits.map((h) => `<span class="cue-chip hit">${escapeHtml(h)}</span>`).join("")
      : `<span class="cue-chip miss">none</span>`;
    return `<div class="cue-row">${escapeHtml(label)}: ${chips}</div>`;
  }

  function renderInspector(row) {
    const empty = $("inspector-empty");
    const body = $("inspector-body");
    if (!row) {
      empty.hidden = false;
      body.hidden = true;
      return;
    }
    empty.hidden = true;
    body.hidden = false;
    const v = row.verdict;
    const seg = row.evidence?.segment || {};
    const det = row.evidence?.detections_summary || {};
    const searchHit = row.evidence?.search?.hit || {};
    const synthetic = Boolean(state.review.synthetic);
    const counts = det.object_counts && typeof det.object_counts === "object"
      ? Object.entries(det.object_counts).map(([k, n]) => `${k} \u00D7${n}`).join(", ")
      : String(det.object_counts ?? "\u2014");
    const classes = Array.isArray(det.object_classes) ? det.object_classes.join(", ") : String(det.object_classes ?? "\u2014");

    body.innerHTML = `
      <div class="kv">
        <span>Claim</span><span>${escapeHtml(row.claim.text)}</span>
        <span>Verdict</span><span>${badgeHtml(v.verdict, v.verdict_label)}</span>
        <span>Seek</span><span class="seek-line">${escapeHtml(clipTimeLabel(row))}</span>
        <span>Mode</span><span><span class="mode-tag">${escapeHtml(row.claim.verdict_mode || "")}</span></span>
      </div>
      <div class="prov-tags">
        <span class="prov-tag cosmos">${synthetic ? "Synthetic caption" : "Cosmos reasoning"}</span>
        <span class="prov-tag yolo">${synthetic ? "Synthetic objects" : "YOLO measurements"}</span>
        <span class="prov-tag adv">Agent / synthesis advisory only</span>
      </div>
      <div class="block observed">
        <h3>Verdict rationale <span class="tag obs">Observed</span></h3>
        <pre>${escapeHtml(v.rationale || "")}</pre>
        ${cueChips("support cues", v.support_cue_hits)}
        ${cueChips("contradict cues", v.contradict_cue_hits)}
        ${cueChips("YOLO object hints", v.object_hint_hits)}
        <div class="flag-row">
          <span>human review: <b>${v.human_review_required ? "required" : "required"}</b></span>
          <span>binding liability: <b>${v.binding_liability_conclusion ? "yes" : "no"}</b></span>
        </div>
      </div>
      <div class="block observed">
        <h3>${synthetic ? "Synthetic caption fixture" : "Cosmos description (reasoning_content)"} <span class="tag obs">Observed</span></h3>
        <pre>${escapeHtml(seg.reasoning_content || "(missing)")}</pre>
        <div class="mono" style="margin-top:8px;color:#9facc2">
          segment ${seg.segment_start_sec}\u2013${seg.segment_end_sec}s
          \u00B7 file ${escapeHtml(seg.filename || "")}
          \u00B7 used_anchor=${row.evidence?.used_anchor_segment}
        </div>
      </div>
      <div class="block observed">
        <h3>${synthetic ? "Synthetic detection fixture" : "YOLO detections (measurements)"} <span class="tag obs">Observed</span></h3>
        <dl class="measure-grid">
          <dt>Available</dt><dd>${escapeHtml(String(det.available ?? "\u2014"))}</dd>
          <dt>Detections</dt><dd>${escapeHtml(String(det.detection_count ?? "\u2014"))}</dd>
          <dt>Classes</dt><dd>${escapeHtml(classes || "\u2014")}</dd>
          <dt>Counts</dt><dd>${escapeHtml(counts || "\u2014")}</dd>
          <dt>Max conf</dt><dd>${escapeHtml(String(det.max_detection_conf ?? "\u2014"))}</dd>
          <dt>Sample labels</dt><dd>${escapeHtml(JSON.stringify(det.sample_frame0_labels ?? null))}</dd>
          <dt>Provenance</dt><dd>${escapeHtml(String(det.provenance ?? det.source ?? "\u2014"))}</dd>
          ${det.error ? `<dt>Error</dt><dd>${escapeHtml(String(det.error))}</dd>` : ""}
        </dl>
        <details class="raw">
          <summary>Raw detection summary</summary>
          <pre>${escapeHtml(JSON.stringify(det, null, 2))}</pre>
        </details>
      </div>
      <div class="block advisory">
        <h3>Search hit (advisory similarity) <span class="tag adv">Advisory</span></h3>
        <dl class="measure-grid">
          <dt>Query</dt><dd>${escapeHtml(String(row.evidence?.search?.query ?? "\u2014"))}</dd>
          <dt>Found</dt><dd>${escapeHtml(String(searchHit.found ?? "\u2014"))}</dd>
          <dt>Similarity</dt><dd>${escapeHtml(String(searchHit.similarity_score ?? "\u2014"))}</dd>
          <dt>File</dt><dd>${escapeHtml(String(searchHit.filename ?? "\u2014"))}</dd>
        </dl>
        <div class="mono" style="margin-top:8px;color:#9facc2">Similarity alone never sets Supported / Contradicted.</div>
      </div>
      <div class="block advisory">
        <h3>Scoped agent note (advisory \u00B7 not proof) <span class="tag adv">Advisory</span></h3>
        <pre>${escapeHtml(row.evidence?.agent_answer_advisory || row.evidence?.agent_error || "Not requested. Use \u201CReload + scoped agent notes\u201D.")}</pre>
      </div>
    `;
  }

  function selectClaim(claimId) {
    state.selectedClaimId = claimId;
    const row = claimById(claimId);
    renderStatements(state.review);
    renderTimeline(state.review);
    renderInspector(row);
    const player = $("player");
    if (row && player && !state.review.synthetic) {
      const t = Number(row.seek_sec) || 0;
      const seek = () => {
        try {
          player.currentTime = t;
        } catch (_) { /* ignore */ }
      };
      if (player.readyState >= 1) seek();
      else player.addEventListener("loadedmetadata", seek, { once: true });
      player.play().catch(() => {});
    }
  }

  function setupVideo(review) {
    const player = $("player");
    let note = document.getElementById("synthetic-note");
    if (review.synthetic) {
      player.hidden = true;
      player.removeAttribute("src");
      $("media-note").textContent = "SYNTHETIC FIXTURE \u2014 no video footage. Timeline values are illustrative.";
      $("now-playing").textContent = "";
      if (!note) {
        note = document.createElement("div");
        note.id = "synthetic-note";
        note.className = "synthetic-note";
        note.textContent = "No footage in fixture mode \u2014 claims, captions, and detections are synthetic teaching data.";
        player.after(note);
      }
      return;
    }
    if (note) note.remove();
    player.hidden = false;
    $("media-note").textContent = "VAST footage; human review required.";
    const url = apiUrl(review.ui.video_url);
    if (player.getAttribute("src") !== url) {
      player.src = url;
    }
  }

  function trackPlayback() {
    const player = $("player");
    player.addEventListener("timeupdate", () => {
      if (!state.review || state.review.synthetic) return;
      const w = state.review.incident?.evidence_window_sec || {};
      $("now-playing").textContent =
        `at ${fmtSec(player.currentTime)} \u00B7 window ${w.start}\u2013${w.end}s (parent video)`;
    });
  }

  function setupKeyboard() {
    $("statements").addEventListener("keydown", (ev) => {
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp" && ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
      const ids = orderedClaims();
      const idx = ids.indexOf(state.selectedClaimId);
      if (idx < 0) return;
      ev.preventDefault();
      const next = (ev.key === "ArrowDown" || ev.key === "ArrowRight")
        ? ids[(idx + 1) % ids.length]
        : ids[(idx - 1 + ids.length) % ids.length];
      selectClaim(next);
      const btn = document.querySelector(`.claim[data-claim="${next}"]`);
      if (btn) btn.focus();
    });
    document.addEventListener("keydown", (ev) => {
      if (ev.metaKey || ev.ctrlKey || ev.altKey) return;
      const tag = (document.activeElement && document.activeElement.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const n = Number(ev.key);
      const ids = orderedClaims();
      if (Number.isInteger(n) && n >= 1 && n <= ids.length) {
        selectClaim(ids[n - 1]);
      }
    });
  }

  async function load(includeAgent) {
    try {
      const review = await fetchReview(includeAgent);
      state.review = review;
      if (review.disclaimer) $("disclaimer").innerHTML = `<strong>Notice.</strong> ${escapeHtml(review.disclaimer)}`;
      renderChips(review);
      renderSummary(review);
      setupVideo(review);
      renderStatements(review);
      renderTimeline(review);
      const first = state.selectedClaimId || review.claim_reviews?.[0]?.claim?.id;
      if (first) selectClaim(first);
      else renderInspector(null);
      $("load-status").textContent = `Loaded ${review.claim_reviews?.length || 0} claims \u00B7 ${review.label} \u00B7 human review required`;
    } catch (err) {
      $("load-status").textContent = String(err.message || err);
      $("load-status").classList.add("err");
    }
  }

  $("btn-refresh").addEventListener("click", () => load(false));
  $("btn-agent").addEventListener("click", () => load(true));
  trackPlayback();
  setupKeyboard();
  load(false);
})();
