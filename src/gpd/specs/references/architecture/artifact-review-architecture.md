# Artifact Review Architecture

Current architecture-oriented reference for how review, verification, and paper artifacts fit into GPD today.

This file is intentionally evergreen. Dated forward-looking design notes belong outside the shipped runtime reference bundle.

## What Exists Today

- typed paper and compiler surfaces exposed through the GPD paper tooling
- verification registry and verification MCP surfaces for machine-facing check metadata
- review and referee workflows under `{GPD_INSTALL_DIR}/workflows/`
- durable local observability under `GPD/observability/` and `GPD/traces/`
- result and state management through the GPD CLI and state surfaces

## What This Architecture Already Does Well

- keeps review and verification grounded in explicit workflow surfaces
- exposes machine-readable verification metadata instead of only prose
- preserves local traces and workflow state for later inspection
- separates planning, execution, verification, and consistency concerns

## Where The Live System Is Still Thin

### Typed evidence is still incomplete

The system has strong markdown discipline, but many trust-critical review facts are still not first-class typed records. Examples include:

- claim-level verification evidence
- artifact-to-claim provenance
- structured revision-resolution state
- uncertainty propagation across phases and manuscript artifacts

### Publication-grade hard gates are still partial

GPD has strong checks, but some review-sensitive failures can still degrade into warnings or partial-flow behavior depending on runtime conditions. Publication-grade review still needs stronger fail-closed behavior around missing evidence and unresolved blockers.

### Provenance is good, but not yet claim-aware enough

Local traces and observability are valuable, but they are not yet a full claim-evidence graph. The architecture still needs deeper links between results, review artifacts, claims, and verification evidence.

## Current Design Principle

When review or verification behavior is described in multiple places:

- executable registries and typed models win over prose
- shipped reference files should describe implemented surfaces first
- dated proposals and audits should stay outside the shipped runtime reference bundle

## Use This File With

- `references/verification/audits/verification-gap-analysis.md`
- `references/verification/core/verification-core.md`
- `references/publication/paper-quality-scoring.md`
- the paper/review workflows under `{GPD_INSTALL_DIR}/workflows/`

## Bottom Line

GPD already has a credible review-and-verification scaffold. The next architectural gains come from making evidence, provenance, and review integrity more explicitly typed and less dependent on narrative-only markdown interpretation.
