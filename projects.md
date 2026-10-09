# Witness

**Checks every sentence of a driver's statement against the dashcam footage.**

Project plan for the VAST Builders Challenge (video agents track). New York runs Friday, October 9; London runs Saturday, October 17. Build time is 9:30 to 4:30 with lunch at 12:30, so roughly six and a half hours of real work.

## The idea in one paragraph

An auto claims adjuster gets two drivers' statements that contradict each other plus a dashcam clip. Reconciling the stories against the footage takes time they rarely have, so the video gets skimmed. Witness splits each statement into small checkable claims, finds the matching moment in the video, judges each claim with Cosmos Reason 2, cross checks it with YOLO measurements, and returns a verdict per claim (supported, contradicted, or not visible) with a timestamped clip as evidence. It ends with a draft liability note that cites the traffic rule it relied on.

## Why this wins with these judges

Every judge is a solutions architect at a sponsor (NVIDIA, VAST, CoreWeave, W&B), so real use of the stack and technical depth carry extra weight.

Most teams will build the default path that VAST's own video workshop teaches: S3 triggers, LLM summaries, embeddings, vector search, then "chat with your footage." NVIDIA's VSS warehouse blueprint already uses Cosmos Reason 2 for warehouse safety incidents, so that space is also taken. Witness stands out because it makes a decision a real person makes by hand today, shows its evidence, and comes with a measured accuracy number.

Other angles that land:

Driving is Cosmos Reason's home domain, which plays well with the NVIDIA AV simulation judge. The archive sweep (below) is exactly the "video sitting unwatched in storage" story the event is built around. The claims background from Waystar gives the pitch a genuine origin story.

## The user and the pain

**Primary user:** an auto claims adjuster at an insurer, or a safety manager at a commercial fleet.

**Today:** two conflicting written statements, one clip, not enough time. The footage gets skimmed and fault leans on the written stories.

**The hidden money:** closed claims with video nobody reviewed may include cases where the other driver was at fault. The insurer could have recovered costs from the other carrier (subrogation) but never knew.

## How it works

1. **Ingest.** Footage and statements land in a VAST bucket. A DataEngine element trigger fires a Python function that starts the pipeline.
2. **Claim extraction.** A W&B Inference LLM splits each statement into atomic claims as JSON, for example "I had a green light", "they never signaled", "I braked right away."
3. **Localize.** Find the event window in the clip. Cosmos Reason 2 returns the event time as JSON. For long trip footage, use the stack's semantic search to find the window first.
4. **Verify.** For each claim, Cosmos Reason 2 judges it on a short window around the relevant moment.
5. **Cross check (the second witness).** YOLO tracks vehicles and traffic lights. A color read on the traffic light crop, lane change detection, and how fast the gap to the other car closed give measured evidence, so the VLM is never the only proof.
6. **Report.** The LLM writes a verdict per claim with clip links, plus a liability note grounded by RAG over a small set of traffic rules.
7. **Store.** Claims, verdicts, timestamps, and embeddings go into VAST DataBase so the whole archive becomes queryable.

## Stack and what each piece does

| Piece | Job in Witness |
|---|---|
| VAST DataStore | Holds footage and statements |
| VAST DataEngine | Event triggers run the pipeline when new footage lands |
| VAST DataBase | Verdicts, timestamps, embeddings; archive queries |
| VAST AgentEngine | If exposed at the event, register the verify claim tool as an MCP tool |
| NVIDIA Cosmos Reason 2 (8B) | Event localization and claim judgments. Feed video at 4 fps |
| YOLO | Vehicle and traffic light tracking, measured cross checks |
| W&B Inference | Claim extraction, report writing, RAG answers |
| W&B Weave | Traces of every agent step plus the accuracy evaluation |
| CoreWeave GPUs | Model serving |
| Cursor | Building fast |

## Data

**Nexar Dashcam Collision Prediction dataset:** 1,500 clips of roughly 40 seconds each, half with a collision or near collision, labeled with the exact event time (`time_of_event`) and alert time. Kaggle competition terms are non commercial, which a hackathon demo should fit, but read them before using.

**Demo statements:** written by the team. For each of three demo clips, write two conflicting driver statements, with at least one claim the footage clearly contradicts.

## Evaluation (the number almost nobody else will have)

Run Cosmos Reason 2 event localization on 20 to 50 labeled Nexar clips and score the predicted event time against `time_of_event` in a Weave evaluation. Report something like "event localized within one second on X of Y clips." Put it on a Weave leaderboard and show it during the demo.

## Archive sweep (the stretch that fixes the weakest score)

Treat the 50 clips as a folder of "closed claims." Run Witness over all of them as a batch and rank the ones where the footage suggests the insurer should have recovered money. This turns unwatched stored video into a dollar figure, which is the event's whole theme.

## Demo script (about 3 minutes)

1. **Impact (20 seconds).** The adjuster, two contradicting statements, a clip nobody has time to watch, and money left in closed claims.
2. **Innovation (15 seconds).** Sentence level fact checking, borrowed from NLP, grounded in physical video reasoning, with a detector as a second witness.
3. **Live demo (60 to 90 seconds).** Two statements side by side. One sentence turns red. Click it and a two second clip plays with the timestamp and detector overlay showing why. Then show the archive sweep ranking.
4. **Technical depth (20 seconds).** Architecture view, the Weave accuracy number, and the hardest part solved (trusting the VLM only when the detector agrees).
5. **Close.** Who uses it next (insurers, fleets), how it scales on VAST and CoreWeave, who built what. For the NVIDIA judges: the reconstructed incident timeline could export as a simulation scenario for AV testing.

Have a recorded backup of the demo working in case the network fails.

## Team split

| Person | Owns |
|---|---|
| Johaan | Agent loop: claim extraction, verification, report, RAG |
| Teammate 2 | YOLO tracking and cross checks |
| Teammate 3 | UI (statements view, clip player, sweep ranking) |
| Teammate 4 | Weave evaluation, archive sweep, pitch |

Everyone speaks or runs part of the demo so collaboration is visible.

## Before the event

Prep data and prompts, not code, unless the rules say otherwise.

1. Download about 50 positive Nexar clips.
2. Pick three demo clips with a clear, checkable moment.
3. Write two conflicting statements per demo clip.
4. Draft JSON schemas for claims and verdicts.
5. Draft the Cosmos prompts for event localization and claim judgment.

## Build day plan

**9:30 to 10:00.** Get stack access working, push clips into the VAST bucket, confirm a DataEngine trigger calls your function. If triggers are slow to set up, call the services directly and wire the trigger after lunch.

**10:00 to 11:00.** Prove the riskiest piece. Ask Cosmos Reason 2 at 4 fps for the event time as JSON on 20 clips and score against the labels in Weave. If most land within about a second, move on. If not, localize with YOLO (a tracked car's box growing fast) and use Cosmos only to judge that window.

**11:00 to 12:00.** Claim extraction with a W&B model, then verdicts on one demo clip.

**12:00 to 12:30.** Thin UI, one clip end to end, record a backup video of it working.

**12:30 to 1:15.** Lunch.

**1:15 to 3:00.** YOLO cross checks, RAG liability note, archive sweep over all clips.

**3:00 to 3:45.** UI polish, Weave leaderboard view, architecture slide.

**3:45 to 4:30.** Three full demo run throughs, cut anything that runs long.

## Judge scorecard

| Criterion | Score | Why |
|---|---|---|
| Innovation | 4 | Dashcam AI is common; checking a statement sentence by sentence is rarer. Archive sweep pushes it up |
| Impact | 5 | Named user, real money, clear path to use |
| Technical depth | 5 | Cascade pipeline, detector cross check, measured evaluation |
| Presentation | 5 | The red sentence moment plus the clip that proves it |

## Pitch lines

**Technical:** Witness splits a driver's statement into checkable claims and verifies each against dashcam footage with Cosmos Reason 2, cross checked by YOLO, and we measured it on labeled crash clips in Weave.

**Business:** Adjusters decide fault from conflicting stories because nobody has time to watch the video; Witness watches it, shows the proof, and finds money in closed claims nobody reviewed.

## Likely judge questions

**Who actually uses this?** Claims adjusters and subrogation teams at auto insurers; safety managers at commercial fleets.

**What was the hardest part?** Getting reliable timestamps and not trusting the VLM alone, solved by the detector cross check and the Weave evaluation.

**What would you build next?** The archive sweep at production scale on DataEngine, more evidence types (doorbell and traffic cams), and exporting incident timelines as simulation scenarios.

**What did each person do?** See team split.

## Risks and fallbacks

| Risk | Fallback |
|---|---|
| Cosmos timestamps are loose | Localize with YOLO, use Cosmos only to judge the window |
| DataEngine trigger setup is slow | Call services directly, wire the trigger after lunch |
| Traffic light state is unclear in a clip | Pick demo claims about lane changes or braking instead |
| Network fails during judging | Play the recorded backup |

## Sources

[VAST Builders Challenge](https://www.vastdata.com/vast-builders-challenge)
[Launch post by Ram Bansal](https://vastdata.com/blog/lets-build-introducing-the-vast-builders-challenge)
[VAST video agents workshop](https://luma.com/h8muplvs)
[VSS warehouse blueprint, Cosmos Reason 2](https://docs.nvidia.com/vss/3.1.0/warehouse-docs/CR2.html)
[Cosmos Reason 2 model card](https://build.nvidia.com/nvidia/cosmos-reason2-8b/modelcard)
[VAST DataEngine overview](https://www.vastdata.com/blog/vast-dataengine-the-compute-fabric-for-real-time-governed-data-operations)
[VAST AgentEngine announcement](https://idm.net.au/node/15171)
[W&B inference with Weave](https://docs.coreweave.com/products/wandb/weave/guides/integrations/inference)
[Nexar collision dataset paper](https://huggingface.co/papers/2503.03848)
[Nexar Kaggle competition](https://www.kaggle.com/competitions/nexar-collision-prediction)