# Shared contracts
Pydantic v2 in witness_contracts/models.py is authoritative. schemas/ contains eight JSON
Schemas, examples/ contains one valid example per model, and openapi.json describes the API.
IncidentReport.json includes supported, contradicted and not_visible verdicts.
Regenerate from repository root: `python scripts/export_contracts.py`.
See ../../docs/integration.md for units, references, safety semantics and adapter signatures.
