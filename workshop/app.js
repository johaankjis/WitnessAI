/* Witness workshop UI — no credentials or bearer tokens in the client. */
(function () {
  // /app is the workshop ingress prefix; upstream may strip it.
  const base = location.pathname === "/app" || location.pathname.startsWith("/app/") ? "/app" : "";
  const apiUrl = (path) => base + path;
  const state = {
    review: null,
    selectedClaimId: null,
  };

  const $ = (id) => document.getElementById(id);

  function verdictClass(v) {
    if (v === "supported") return "supported";
    if (v === "contradicted") return "contradicted";
    return "not_visible";
  }

  async function fetchReview(includeAgent) {
    $("load-status").textContent = includeAgent
      ? "Loading evidence + scoped agent notes…"
      : "Loading review…";
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
    const chips = [
      `ns:${inc.team_namespace || "?"}`,
      `${inc.location || "?"}/${inc.camera_id || "?"}`,
      `window ${inc.evidence_window_sec?.start}–${inc.evidence_window_sec?.end}s`,
      inc.segment_filename || "",
    ];
    $("chips").innerHTML = chips
      .filter(Boolean)
      .map((c) => `<span class="chip">${escapeHtml(c)}</span>`)
      .join("");
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
            const cls = verdictClass(v.verdict);
            const selected = state.selectedClaimId === row.claim.id ? "selected" : "";
            return `
              <div class="claim ${selected}" data-claim="${escapeHtml(row.claim.id)}">
                <div class="claim-text">${escapeHtml(row.claim.text)}</div>
                <span class="badge ${cls}">${escapeHtml(v.verdict_label)}</span>
              </div>`;
          })
          .join("");
        return `
          <div class="panel statement">
            <div class="label-row">
              <div class="label">${escapeHtml(stmt.label)}</div>
              <span class="illust">Illustrative · team-authored</span>
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
    root.innerHTML = (review.timeline || [])
      .map((t) => {
        const cls = verdictClass(t.verdict);
        const active = state.selectedClaimId === t.claim_id ? "active" : "";
        return `
          <button type="button" class="tl-btn ${active}" data-claim="${escapeHtml(t.claim_id)}">
            <div class="t">${Number(t.seek_sec).toFixed(1)}s · abs ${Number(t.seek_absolute_sec).toFixed(1)}s</div>
            <div>${escapeHtml(t.label)}</div>
            <div class="v badge ${cls}">${escapeHtml(t.verdict_label)}</div>
          </button>`;
      })
      .join("");
    root.querySelectorAll(".tl-btn").forEach((btn) => {
      btn.addEventListener("click", () => selectClaim(btn.getAttribute("data-claim")));
    });
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
    body.innerHTML = `
      <div class="kv">
        <span>Claim</span><span>${escapeHtml(row.claim.text)}</span>
        <span>Verdict</span><span class="badge ${verdictClass(v.verdict)}">${escapeHtml(v.verdict_label)}</span>
        <span>Seek</span><span class="mono">${row.seek_sec}s (clip) · ${row.seek_absolute_sec}s (parent)</span>
        <span>Mode</span><span class="mono">${escapeHtml(row.claim.verdict_mode || "")}</span>
      </div>
      <div>
        <span class="prov-tag cosmos">${state.review.synthetic ? "Synthetic caption" : "Cosmos reasoning"}</span>
        <span class="prov-tag yolo">${state.review.synthetic ? "Synthetic objects" : "YOLO measurements"}</span>
        <span class="prov-tag adv">Agent / synthesis advisory only</span>
      </div>
      <div class="block">
        <h3>Verdict rationale</h3>
        <pre>${escapeHtml(v.rationale || "")}</pre>
        <div class="mono" style="margin-top:8px;color:#93a0b5">
          cue support: ${escapeHtml(JSON.stringify(v.support_cue_hits || []))}
          · contradict: ${escapeHtml(JSON.stringify(v.contradict_cue_hits || []))}
          · yolo hints: ${escapeHtml(JSON.stringify(v.object_hint_hits || []))}
          · human_review_required: ${v.human_review_required}
          · binding_liability: ${v.binding_liability_conclusion}
        </div>
      </div>
      <div class="block">
        <h3>${state.review.synthetic ? "Synthetic caption fixture" : "Cosmos description (reasoning_content)"}</h3>
        <pre>${escapeHtml(seg.reasoning_content || "(missing)")}</pre>
        <div class="mono" style="margin-top:8px;color:#93a0b5">
          segment ${seg.segment_start_sec}–${seg.segment_end_sec}s
          · file ${escapeHtml(seg.filename || "")}
          · used_anchor=${row.evidence?.used_anchor_segment}
        </div>
      </div>
      <div class="block">
        <h3>${state.review.synthetic ? "Synthetic detection fixture" : "YOLO detections (measurements)"}</h3>
        <pre>${escapeHtml(JSON.stringify({
          available: det.available,
          detection_count: det.detection_count,
          object_classes: det.object_classes,
          object_counts: det.object_counts,
          max_detection_conf: det.max_detection_conf,
          sample_frame0_labels: det.sample_frame0_labels,
          provenance: det.provenance,
        }, null, 2))}</pre>
      </div>
      <div class="block">
        <h3>Search hit (advisory similarity)</h3>
        <pre>${escapeHtml(JSON.stringify({
          query: row.evidence?.search?.query,
          found: searchHit.found,
          similarity_score: searchHit.similarity_score,
          filename: searchHit.filename,
          note: "Similarity alone never sets Supported/Contradicted",
        }, null, 2))}</pre>
      </div>
      <div class="block">
        <h3>Scoped agent note (advisory · not proof)</h3>
        <pre>${escapeHtml(row.evidence?.agent_answer_advisory || row.evidence?.agent_error || "Not requested. Use “Reload + scoped agent notes”.")}</pre>
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
    player.hidden = review.synthetic;
    $("media-note").textContent = review.synthetic
      ? "SYNTHETIC FIXTURE — no video footage. Timeline values are illustrative." : "VAST footage; human review required.";
    if (review.synthetic) { player.removeAttribute("src"); return; }
    const url = apiUrl(review.ui.video_url);
    if (player.getAttribute("src") !== url) {
      player.src = url;
    }
  }

  async function load(includeAgent) {
    try {
      const review = await fetchReview(includeAgent);
      state.review = review;
      if (review.disclaimer) $("disclaimer").innerHTML = `<strong>Notice.</strong> ${escapeHtml(review.disclaimer)}`;
      renderChips(review);
      setupVideo(review);
      renderStatements(review);
      renderTimeline(review);
      const first = state.selectedClaimId || review.claim_reviews?.[0]?.claim?.id;
      if (first) selectClaim(first);
      else renderInspector(null);
      $("load-status").textContent = `Loaded ${review.claim_reviews?.length || 0} claims · ${review.label} · human review required`;
    } catch (err) {
      $("load-status").textContent = String(err.message || err);
      $("load-status").classList.add("err");
    }
  }

  $("btn-refresh").addEventListener("click", () => load(false));
  $("btn-agent").addEventListener("click", () => load(true));
  load(false);
})();
