# WitnessAI

WitnessAI is a Python-based video evidence and claims-analysis platform for reconciling witness statements against dashcam footage. The project is designed to turn raw video evidence into structured, reviewable findings: identify the relevant moment in a clip, extract checkable claims from written statements, verify those claims against video evidence, and produce a report that supports human review.

This repository contains the foundational implementation for the project, including the API composition root, contract schemas, vision adapters, evaluation tooling, and supporting documentation.

## What the project does

The core workflow is:

- ingest one or more witness statements and a video clip
- split each statement into discrete claims
- find the relevant event window in the footage
- review each claim against available evidence
- cross-check the result using detection-based observations
- produce a structured report describing the evidence, uncertainty, and provenance

The project is explicitly built for evidence review, not final legal determination. Every finding is framed as a reviewable artifact with timestamps, explanations, and provenance. Missing evidence is handled as `not_visible` rather than as proof of a negative.

In practice, this helps teams answer questions like:

- Did the driver actually say what they claim?
- Was the event window visible in the footage?
- What evidence supports or contradicts a statement?
- What is the degree of confidence or uncertainty in the review?

## Why this project matters

Claims workflows are often bottlenecked by the time required to review video evidence manually. WitnessAI aims to reduce that gap by making the decision process more structured and traceable:

- video evidence is reviewed in time-bounded windows
- claims are checked one at a time
- evidence is tied to specific timestamps and sources
- results are returned in a machine-readable schema for downstream use

## Repository structure

- `apps/api/` — FastAPI application and composition root
- `packages/contracts/` — Pydantic v2 contract models and API schemas
- `services/vision/` — vision and detection adapters
- `evals/` — evaluation harnesses for offline scoring and metrics
- `apps/web/` — web front-end consumption layer (when present)
- `docs/` — project and task documentation
- `scripts/` — export and project automation scripts
- `data/` — local fixtures and sample data
- `workshop/` — lightweight workshop or demo-focused app

## Architecture overview

The project follows a layered design:

- API layer: creates the application and exposes endpoints
- Contract layer: Pydantic v2 models are the single source of truth for contracts
- Service layer: protocols define the orchestration boundaries, adapters implement them
- Storage layer: JSON-backed local persistence replaces reports atomically
- Evaluation layer: offline checks validate findings against labeled data

This keeps the system modular and testable while avoiding provider, GPU, or real-inference logic in the main API layer.

## Installation

### Requirements

- Python 3.11+
- pip
- virtual environment recommended

### Clone and set up the environment

```bash
git clone https://github.com/johaankjis/WitnessAI.git
cd WitnessAI
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
```

### Install the project and dev dependencies

```bash
python -m pip install -e .[dev]
python -m pip install -e services/vision[dev]
python -m pip install -e evals[dev]
```

If you want the optional vision extras that include video processing and Yolo support, use:

```bash
python -m pip install -e services/vision[yolo]
```

## Running the API

From the repository root:

```bash
uvicorn witness_api.main:app --host 0.0.0.0 --port 8000 --reload
```

The FastAPI app exposes the project contract and routes defined in the API package. The exact endpoints depend on the active task and implementation state, but the app is intended to serve structured evidence review results over HTTP.

## Running tests

Run the backend test suite from the repository root:

```bash
python -m pytest
```

For local evaluation or vision-related checks, use the package-level test commands as needed:

```bash
cd evals && python -m pytest
cd services/vision && python -m pytest
```

## Contract generation

The project explicitly treats generated contracts as part of the software output. When contract changes are made, regenerate them with:

```bash
python scripts/export_contracts.py
```

This should be kept in sync with the corresponding API schema and example output.

## Development principles

This codebase follows a few key rules:

- typed Python across interfaces and adapters
- Pydantic v2 schemas as the source of truth
- explicit dependency boundaries between orchestration and implementations
- no hidden success states for failed analyses
- no fabricated evidence or synthetic observations presented as real findings
- human review remains required for any final or interpretive decision

## Documentation and project context

Useful starting points:

- `projects.md` — project goals, constraints, and architecture context
- `AGENTS.md` — contributor ownership and boundaries
- `docs/` — implementation and task-specific docs
- `evals/README.md` — evaluation methodology and offline metrics
- `workshop/README.md` — demo and workshop-specific application behavior

## Project status and boundaries

This repository contains a research and prototype foundation for a video evidence review workflow. It is intentionally scoped to evidence-grounded reasoning and human-in-the-loop decision support. It does not claim to determine legal fault automatically, and it does not rely on hidden provider behavior or unreviewed model output as proof.

## License

Check the repository configuration for the active license and any additional usage terms before distribution or production deployment.
