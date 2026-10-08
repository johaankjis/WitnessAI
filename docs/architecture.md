# TASK-001 architecture
The project plan was read in full. Its provider-backed pipeline is represented here by
replaceable interfaces; no integrations are activated. The requested safety boundary
supersedes the plan's draft liability note: reports provide no legal fault determination.

FastAPI → Pipeline → extractor → localizer → verifier → fusion → report generator.
The observer supplies claim-linked detector observations to fusion. Storage loads the
incident fixture and atomically writes validated reports using temporary files plus rename.
The composition root wires all seven interfaces to local adapters. create_app accepts
storage and pipeline overrides, enabling isolated tests and later adapter replacement.

Pydantic models forbid unknown fields, bound confidence and timestamps, reject missing
visible evidence for supported/contradicted verdicts, and check report claim references
and mock provenance consistency. Pipeline validates statement references and evidence bounds.
These structural checks cannot establish that real evidence is authentic: real adapters
must inspect actual media, preserve source provenance and apply the evidence policy.

The mock fixture describes B changing lanes and A braking. Two drivers contradict each
other about those actions. A green-signal claim is not_visible because the synthetic
scenario places the signal outside frame. Timestamps 8–12 seconds are fixture data only;
mock:// is deliberately not a playable URL. Null confidence avoids invented certainty.

POST is synchronous: completed means the report has been saved. No background task or
status database exists. Pending/running/failed are reserved contract states. Failed POSTs
return 500; previous reports remain available. Repeated runs replace the report with the
same content. Local file storage is for single-machine development, with last-write-wins
semantics; it is not a distributed job system. No authentication or production hosting is included.

Future providers belong behind Protocol interfaces; none should be imported or contacted
by default. Claude Code owns vision and evaluation; Muse owns frontend behavior. Shared
contract changes require coordination with Codex. No TASK-002 features are implemented.
