# WitnessAI

Claims desk on top of the VAST Builders Challenge video index (team-6).

## What the index actually contains

There is **no labeled car-accident footage**. Organizers pre-ingested:

| Pack | `camera_id` | `capture_type` | `location` |
|------|-------------|----------------|------------|
| I-24 highway | `i24_cam-1` | `traffic` | `nashville` |
| Toronto PIE drives | `pie_cam-3` | `streets` | `toronto` |
| Neighborhood | `neighborhood_cam-1` | `streets` | `neighborhood` |
| Warehouse | `sdg_warehouse_cam-2` | `warehouse` | `warehouse3` |

A live search for `car accident` on https://team-6-vss.thecosmoslabs.com/search returned ordinary night driving at 15–32% match. Cosmos: *no collision visible*.

## How to demo this file

Open `index.html` (or serve the folder). Preset chips replay real index behavior:

- `car accident` → empty/low-quality hits + the real synthesis
- `truck changing lanes on the highway` → I-24
- `pedestrian near the curb` → PIE pack
- `person close to a moving vehicle` → cross-pack (the organizers’ intended query)

## Live API (on the workshop VM)

Login JWT is required (`USERNAME` / `PASSWORD` from `/config/team-6.config`).

```http
POST /api/v1/tools/search
POST /api/v1/agent/search-and-answer
POST /api/v1/agent/ask
GET  /api/v1/metadata/schema
```

Filter body fields that exist in VastDB: `camera_id`, `capture_type`, `location`, plus YOLO `object_classes`. Search text is embedded `reasoning_content` — if the ingest prompt never asked about collisions, you cannot retrieve them.

## Re-ingest prompt (do this on the VM, not YouTube)

Challenge rules: do **not** ingest internet crash videos. Re-run existing I-24 / PIE / neighborhood segments with a prompt such as:

> Describe each vehicle, lane, and any pedestrian. Note lane changes, hard braking, following distance, who yielded, and whether anyone is at fault for an unsafe interaction. If there is no incident, say so explicitly.

Then search the same queries again.
