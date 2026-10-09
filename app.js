const PRESETS = [
  "truck changing lanes on the highway",
  "two vehicles close together",
  "pedestrian near the curb",
  "vehicle braking hard",
  "person close to a moving vehicle",
];

const MESSAGE_FOR_INVALID_QUERY =
  "This archive does not contain crash footage. Use one of the valid prompts from the challenge corpus such as 'truck changing lanes on the highway' or 'pedestrian near the curb'.";

/** Valid team-6 / corpus clips aligned to the Architecture Reference and documented packs. */
const CLIPS = [
  {
    id: "i24-lane",
    file: "20261001_055638_scene1_p1c1_chunk_0009.mp4",
    camera_id: "i24_cam-1",
    capture_type: "traffic",
    location: "nashville",
    objects: ["bus", "car", "truck"],
    score: 0.78,
    window: "0:00–0:05",
    scene: "highway",
    reasoning:
      "Multi-lane I-24 corridor. Vehicles at steady speeds. In the departing lanes a white truck is visible among cars; adjacent vehicles occupy neighboring lanes with close lateral spacing typical of a lane-change / merge interaction.",
    queries: ["truck changing lanes on the highway", "vehicle braking hard", "person close to a moving vehicle"],
    collision: false,
    parties: {
      primary: { name: "Truck (departing lanes)", pct: 62, role: "Initiating lane change / occupying two-lane envelope" },
      other: { name: "Adjacent passenger vehicle", pct: 38, role: "Maintaining lane; limited gap" },
    },
    verdict:
      "No impact is indexed. For a claims desk this is a near-miss merge: the truck is the party changing the traffic envelope. Recommend requesting the adjacent camera in the same I-24 scene (p1c2) before assigning fault.",
  },
  {
    id: "i24-brake",
    file: "20261001_060054_scene1_p1c2_chunk_0009.mp4",
    camera_id: "i24_cam-1",
    capture_type: "traffic",
    location: "nashville",
    objects: ["bus", "car", "truck"],
    score: 0.71,
    window: "0:05–0:10",
    scene: "highway",
    reasoning:
      "Dry multi-lane highway, clear weather, traffic both directions separated by a median. Dense vehicle mix (bus, car, truck) consistent with following-distance / hard-brake review.",
    queries: ["vehicle braking hard", "truck changing lanes on the highway"],
    collision: false,
    parties: {
      primary: { name: "Lead vehicle in dense pack", pct: 55, role: "Speed change that compresses following gap" },
      other: { name: "Following vehicles", pct: 45, role: "Following distance not independently verified" },
    },
    verdict:
      "Highway pack with mixed vehicle classes. Treat as a following-too-closely candidate, not a confirmed collision. Re-ingest this chunk with a prompt that asks who braked, who changed lanes, and time-to-collision.",
  },
  {
    id: "nbhd-close",
    file: "20261001_074123_neighborhood_20260902_chunk_001….mp4",
    camera_id: "neighborhood_cam-1",
    capture_type: "streets",
    location: "neighborhood",
    objects: ["car"],
    score: 0.66,
    window: "0:00–0:05",
    scene: "night",
    reasoning:
      "A car is seen driving on the road in the background. Parked cars line the curb. Two-vehicle proximity on a residential street — the Architecture Reference example for this camera.",
    queries: ["two vehicles close together", "person close to a moving vehicle"],
    collision: false,
    parties: {
      primary: { name: "Moving sedan", pct: 70, role: "Only moving actor; duty to clear parked/curbside objects" },
      other: { name: "Parked / driveway vehicles", pct: 30, role: "Static; possible obstruction if over curb" },
    },
    verdict:
      "Neighborhood cam shows ordinary pass-by, not a crash. Useful as the 'before' context in a claim if a later chunk shows contact. Cosmos already answered that no collision is in these clips.",
  },
  {
    id: "pie-ped",
    file: "pie_set03_forward_drive_segment.mp4",
    camera_id: "pie_cam-3",
    capture_type: "streets",
    location: "toronto",
    objects: ["car", "person"],
    score: 0.74,
    window: "intersection / curb",
    scene: "highway",
    reasoning:
      "Forward-facing Toronto PIE drive (corpus pack B). Indexed story: pedestrian near the curb, intersection with turning traffic, vehicle ahead. This is the live-driving pack the Architecture Reference tells teams to query for road-safety events.",
    queries: ["pedestrian near the curb", "person close to a moving vehicle"],
    collision: false,
    parties: {
      primary: { name: "Approaching driver (ego / vehicle ahead)", pct: 58, role: "Must yield to pedestrian in/near crosswalk zone" },
      other: { name: "Pedestrian at curb", pct: 42, role: "Position relative to curb not a confirmed entry into travel lane" },
    },
    verdict:
      "Highest-value demo for an insurer app: not a wreck, but a duty-of-care event. Search with capture_type=streets and camera_id=pie_cam-3, then ask the agent who had right of way.",
  },
  {
    id: "wh-fork",
    file: "sdg_warehouse_aisle_clip.mp4",
    camera_id: "sdg_warehouse_cam-2",
    capture_type: "warehouse",
    location: "warehouse3",
    objects: ["forklift", "person"],
    score: 0.81,
    window: "aisle",
    scene: "highway",
    reasoning:
      "SDG warehouse RGB. Indexed near-miss class: forklift approaching a person in an aisle / person in a walkway. Same 'party at fault from video' workflow, industrial instead of roadway.",
    queries: ["person close to a moving vehicle"],
    collision: false,
    parties: {
      primary: { name: "Forklift operator", pct: 75, role: "Moving industrial vehicle in pedestrian aisle" },
      other: { name: "Pedestrian in aisle", pct: 25, role: "May be in a restricted zone — confirm from detections" },
    },
    verdict:
      "Warehouse near-miss is in the same index as highway traffic. Cross-pack query “person close to a moving vehicle” is the organizers’ intended demo line.",
  },
];

const SYNTHESIS = {
  "car accident": {
    answer: MESSAGE_FOR_INVALID_QUERY,
    gaps: "The evidence does not contain actual crash footage. Use a valid near-miss / duty-of-care query instead.",
  },
};

function $(id) {
  return document.getElementById(id);
}

function renderChips() {
  const wrap = $("chips");
  wrap.innerHTML = "";
  PRESETS.forEach((p) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = "chip" + (p === $("q").value ? " active" : "");
    b.textContent = p;
    b.onclick = () => {
      $("q").value = p;
      search();
    };
    wrap.appendChild(b);
  });
}

function apiPayload(query, camera, capture, location) {
  return {
    query,
    top_k: 15,
    timeFilter: { value: 7, unit: "days" },
    filters: {
      camera_id: camera || undefined,
      capture_type: capture || undefined,
      location: location || undefined,
    },
  };
}

function matchesFilters(clip, camera, capture, location) {
  if (camera && clip.camera_id !== camera) return false;
  if (capture && clip.capture_type !== capture) return false;
  if (location && clip.location !== location) return false;
  return true;
}

function search() {
  const query = $("q").value.trim();
  const camera = $("camera").value;
  const capture = $("capture").value;
  const location = $("location").value;
  renderChips();
  $("api").textContent =
    "POST https://team-6-vss.thecosmoslabs.com/api/v1/tools/search\n" +
    JSON.stringify(apiPayload(query, camera, capture, location), null, 2);

  const hits = CLIPS.filter(
    (c) => c.queries.some((q) => q === query || query.toLowerCase().includes(q.toLowerCase())) && matchesFilters(c, camera, capture, location)
  ).sort((a, b) => b.score - a.score);

  $("count").textContent = `Found ${hits.length} clip${hits.length === 1 ? "" : "s"}`;
  $("meta").textContent = SYNTHESIS[query] ? "Invalid query — no crash footage in index" : "Corpus-aligned demo hits";

  const list = $("list");
  list.innerHTML = "";
  if (SYNTHESIS[query]) {
    const note = document.createElement("div");
    note.className = "empty";
    note.innerHTML = `<strong>Index answer</strong><p>${SYNTHESIS[query].answer}</p><p>${SYNTHESIS[query].gaps}</p>`;
    list.appendChild(note);
  }
  if (!hits.length) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = "No indexed segments for this query + filter combo. Try a recommended chip or clear filters.";
    list.appendChild(empty);
    return;
  }
  hits.forEach((clip) => {
    const el = document.createElement("article");
    el.className = "card";
    el.innerHTML = `
      <span class="score">${Math.round(clip.score * 100)}% match</span>
      <div class="title">${clip.file}</div>
      <div class="cap">${clip.reasoning}</div>
      <div class="tags">
        <span class="tag">${clip.camera_id}</span>
        <span class="tag">${clip.capture_type}</span>
        <span class="tag">${clip.location}</span>
        ${clip.objects.map((o) => `<span class="tag">${o}</span>`).join("")}
        <span class="tag">${clip.window}</span>
      </div>`;
    el.onclick = () => openCase(clip, el);
    list.appendChild(el);
  });
}

function openCase(clip, cardEl) {
  document.querySelectorAll(".card").forEach((c) => c.classList.remove("sel"));
  cardEl.classList.add("sel");
  const parties = clip.parties || {
    primary: { name: "No at-fault party", pct: 0, role: "No collision indexed" },
    other: { name: "—", pct: 0, role: "Routine traffic / parked vehicles" },
  };
  const verdict = clip.verdict ||
    "Do not file as a collision. Cosmos Reason found no impact. Keep this clip only as negative evidence that the queried window is ordinary driving.";
  $("case").innerHTML = `
    <div class="scene ${clip.scene}">
      <div class="lane"></div>
      <div class="car a"></div>
      <div class="car b"></div>
      ${clip.scene === "highway" ? '<div class="car c"></div>' : ""}
    </div>
    <div class="tags" style="margin-bottom:10px">
      <span class="tag">${clip.camera_id}</span>
      <span class="tag">${clip.location}</span>
      <span class="tag">${clip.collision ? "Collision" : "No collision in index"}</span>
    </div>
    <p class="hint">${clip.reasoning}</p>
    <div class="fault">
      <div class="party primary">
        <div>${parties.primary.name}</div>
        <div class="pct">${parties.primary.pct}%</div>
        <div class="hint">${parties.primary.role}</div>
      </div>
      <div class="party other">
        <div>${parties.other.name}</div>
        <div class="pct">${parties.other.pct}%</div>
        <div class="hint">${parties.other.role}</div>
      </div>
    </div>
    <div class="verdict"><strong>Desk opinion.</strong> ${verdict}</div>
  `;

  const videoPanel = document.getElementById("video-panel");
  const playButton = document.getElementById("play-button");
  const mediaUrl = clip.mediaUrl || "";

  if (mediaUrl && /^https?:\/\//i.test(mediaUrl)) {
    playButton.classList.remove("hidden");
    playButton.onclick = () => {
      const video = document.createElement("video");
      video.src = mediaUrl;
      video.controls = true;
      video.autoplay = true;
      video.style.width = "100%";
      video.style.borderRadius = "8px";
      const placeholder = videoPanel.querySelector(".video-placeholder");
      placeholder.innerHTML = "";
      placeholder.appendChild(video);
    };
    videoPanel.classList.remove("hidden");
  } else {
    playButton.classList.add("hidden");
    videoPanel.classList.remove("hidden");
    const placeholder = videoPanel.querySelector(".video-placeholder");
    placeholder.innerHTML = `
      <div class="video-icon">▶</div>
      <div class="video-text">No playable media URL is available in this local demo.</div>
    `;
  }
}

$("go").onclick = search;
$("q").addEventListener("keydown", (e) => {
  if (e.key === "Enter") search();
});
["camera", "capture", "location"].forEach((id) => $(id).addEventListener("change", search));
renderChips();
search();
