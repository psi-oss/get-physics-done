# Knowledge Trust Phase 0: Scope Lock RFC

Status: experimental, non-binding scope lock
Date: 2026-04-07

This RFC defines the intended role of knowledge-trust artifacts before any public
command, schema, layout, or runtime contract is treated as shipped.

This document does not change the current runtime behavior. It exists to prevent
artifact overlap, schema churn, and misleading public claims while the feature is
still being built.

## Problem Statement

GPD already has several artifact families with strong but different roles:

- `GPD/CONVENTIONS.md` for prescriptive project conventions
- `GPD/literature/` for literature review and citation-source gathering
- `GPD/research-map/` for descriptive project or folder analysis
- `PLAN.md` artifacts for execution contracts
- result registry artifacts for canonical derived results
- verification artifacts for contract-backed evidence

Without an explicit scope lock, a knowledge-trust feature would likely duplicate one
or more of those roles, and it would be easy to market a template-only surface as if
it already carried real downstream trust.

## Goals

Phase 0 is only meant to lock scope.

It should:

1. define what a knowledge document is
2. define what it is not
3. identify the later runtime integration seam
4. define the rollout posture while the feature remains incomplete

## Core Definition

A knowledge document is a reviewed, project-scoped topic synthesis that captures
what the project intends to trust enough to reference downstream once the runtime
supports it.

In later phases, this artifact family is expected to be explicitly addressable by ID
and consumable through the shared reference-ingestion path. In Phase 0, that is only
a target architecture, not a shipped contract.

## Boundary Decisions

Knowledge documents may:

- synthesize findings from literature reviews, research maps, prior project work, and
  verified results
- capture topic-level understanding, caveats, and downstream implications
- become explicit reference inputs to later workflows once the runtime integration is
  implemented

Knowledge documents must not:

- replace `GPD/CONVENTIONS.md` as the authority for project conventions
- replace literature reviews as the broad field-survey and citation-source layer
- replace research maps as the descriptive analysis of an existing project or folder
- replace the result registry as the canonical store for derived results
- replace verification artifacts as the evidence ledger for whether work passed

## Future Artifact Posture

`GPD/knowledge/` is the proposed future artifact family name used by this RFC.

In Phase 0 it is only a proposal. This RFC does not establish:

- a canonical directory contract
- a canonical filename or ID contract
- a stable schema
- a stable public command surface

Those decisions belong to later phases.

## Runtime Integration Target

The future v1 integration point is the shared reference-ingestion and runtime-context
path that already feeds:

- `effective_reference_intake`
- `active_reference_context`
- `reference_artifacts_content`

This RFC records that knowledge-trust should eventually enter that shared seam rather
than being implemented as per-workflow bespoke logic.

The first mandatory downstream consumers, once implemented, should be:

1. the shared init paths
2. `research-phase`
3. `plan-phase`
4. `verify-work`
5. `execute-phase`

Other consumers such as `map-research`, `quick`, `compare-experiment`, or `explain`
are useful but not required for the initial trust-critical cut.

## Public-Surface Posture

Phase 0 does not add knowledge-trust to:

- quick start paths
- beginner onboarding
- shared runtime help
- command indexes
- canonical project-structure docs

If the concept is mentioned outside this RFC at all before later phases land, it must
be described as advanced, optional, experimental, and subject to change.

## Non-Goals

Phase 0 explicitly does not attempt to provide:

1. automatic truth inference
2. a stable command
3. a stable schema
4. a stable storage layout
5. automatic migration of experimental docs
6. implicit or eager runtime loading
7. universal adoption for every project
8. any claim that trusted knowledge is already consumed by planning, verification, or
   execution

## Rollout Posture

Until later phases land, knowledge trust must be treated only as experimental
scaffolding.

It must not be promoted beyond that status until all of the following are real and
tested:

1. naming and schema contracts
2. real authoring and update behavior
3. lifecycle and review evidence enforcement
4. shared runtime ingestion
5. downstream workflow visibility
6. aligned help and public docs

The detailed delivery order lives in
`docs/rfcs/2026-04-knowledge-trust-rollout-sequence.md`.

## Acceptance Criteria For Phase 0

This RFC is complete when:

1. the artifact role is clearly defined
2. the boundaries against existing artifact families are explicit
3. the future integration seam is identified without overclaiming current behavior
4. the feature is clearly labeled experimental
5. the rollout posture and non-goals are documented
