# Phase 3 Report: Persona Builder

## Executor Scope

This report covers the final Phase 3 persona-builder command, agent, staged
workflow, help surfaces, and acceptance smoke tests.

Implemented Phase 3 files:

- `src/gpd/commands/build-persona.md`
- `src/gpd/agents/gpd-persona-builder.md`
- `src/gpd/specs/workflows/build-persona.md`
- `src/gpd/specs/workflows/build-persona-stage-manifest.json`
- `src/gpd/specs/workflows/build-persona/persona-intake.md`
- `src/gpd/specs/workflows/build-persona/persona-synthesis.md`
- `src/gpd/specs/workflows/build-persona/approval-and-apply.md`
- `src/gpd/commands/help.md`
- `src/gpd/registry.py`
- `tests/core/test_research_persona_builder_acceptance.py`
- `tests/core/test_research_persona_builder_help.py`
- `tests/core/test_research_persona_builder_privacy.py`
- `tests/core/test_research_persona_builder_registry.py`

## Implemented Command Contract

Phase 3 introduces a runtime command:

```text
gpd:build-persona
```

Expected command file:

```text
src/gpd/commands/build-persona.md
```

The command is an orchestrator for constructing a machine-local research persona. It must not silently write persona data. Its job is to:

- validate the current workspace context when relevant;
- gather explicit user-approved persona inputs;
- delegate synthesis to `gpd-persona-builder`;
- review the builder return envelope;
- validate the candidate persona patch;
- ask for approval before mutation;
- apply approved changes only through the Phase 2 CLI control plane.

The command must route writes through:

```text
gpd research-persona validate
gpd research-persona diff
gpd research-persona apply-patch
```

The command must not write `profile.json`, history ledgers, tombstones, `state.json`, project `GPD/`, command markdown, agent markdown, runtime catalogs, or public-surface files directly.

## Implemented Agent Contract

Phase 3 introduces a one-shot specialist agent:

```text
gpd-persona-builder
```

Expected agent file:

```text
src/gpd/agents/gpd-persona-builder.md
```

The agent synthesizes candidate persona updates only. It returns a structured patch proposal and evidence summary; it does not mutate local persona storage.

The agent should extract and organize:

- user interests;
- research areas;
- work and expertise;
- emphasis across math, code, experiment, fundamental, theoretical, and applied work;
- papers and projects supplied by the user;
- collaborators and institutions supplied by the user;
- relevant references;
- workstyle preferences;
- typical tools and runtimes;
- explanation preferences;
- review, verification, and writing preferences.

The agent must classify every proposed fact with source, privacy, confidence, and evidence metadata from Phase 1. It must prefer `inferred` over `confirmed` unless the user explicitly confirmed the fact.

## Implemented Workflow Contract

Phase 3 introduces a staged workflow:

```text
src/gpd/specs/workflows/build-persona.md
```

Expected supporting stages:

```text
src/gpd/specs/workflows/build-persona-stage-manifest.json
src/gpd/specs/workflows/build-persona/persona-intake.md
src/gpd/specs/workflows/build-persona/persona-synthesis.md
src/gpd/specs/workflows/build-persona/approval-and-apply.md
```

The workflow is intentionally patch-only:

1. Intake creates a bounded evidence packet from explicit user material and optional current-project context.
2. Synthesis delegates to `gpd-persona-builder` and requires a patch proposal, not direct edits.
3. Approval presents a readable diff and privacy summary.
4. Apply runs only after approval through `gpd research-persona apply-patch`.
5. Closeout validates the resulting persona through `gpd research-persona validate`.

The workflow must stop if validation fails, if the builder returns malformed patch JSON, if the requested source contains private material the user has not approved for persona use, or if the user declines the patch.

## Patch-Only Approval Contract

Phase 3 mutations are explicit and user-approved.

Allowed write path:

```text
candidate patch -> gpd research-persona validate -> gpd research-persona diff -> user approval -> gpd research-persona apply-patch
```

Forbidden write paths:

- direct filesystem writes to `${GPD_DATA_DIR:-~/.gpd}/research-persona/profile.json`;
- direct history or tombstone ledger writes from command or agent prose;
- inferred updates from ordinary chat context;
- applying facts from repository scans without an approval step;
- storing `never_prompt` facts in prompts, capsules, workflow state, command returns, or project files.

The command should display a human-readable summary before approval:

- facts added, updated, or removed;
- privacy labels involved;
- low-confidence or inferred facts;
- source documents and evidence ids;
- fields that will be excluded from prompt capsules.

## Privacy Guarantees

Phase 3 inherits the Phase 1 privacy labels:

- `session_only`
- `private_local`
- `project_private`
- `safe_to_share`
- `never_prompt`

The builder may propose `never_prompt` facts, but they must only appear in local storage and local approval diffs. They must never appear in prompt capsules, runtime workflow context, generated command frontmatter, public surface manifests, or project `GPD/` state.

The command and workflow must use the Phase 2 CLI and Phase 1 projection helpers rather than hand-written privacy filters. Prompt-facing summaries must come from prompt-safe capsules, not raw local persona dumps.

## Ambitious Feature Hooks

Phase 3 establishes the persona data needed for three later features:

- Researcher Doppelganger: role capsule `doppelganger`, focused on simulating the user's likely questions, objections, standards, and follow-up decisions.
- Expertise-Aware Explanations: role capsule `explainer`, focused on adapting explanations to the user's math, code, experimental, and theoretical background.
- Scientific Taste Model: role capsule `taste`, focused on ranking research directions by the user's stated taste, tolerance for risk, preferred evidence standards, and preferred balance of novelty versus tractability.

Phase 3 should not implement autonomous behavior for these features yet. It should only ensure the profile can store and export the necessary facts without leaking private material.

## Tests

Phase 3 acceptance smoke tests live in:

```text
tests/core/test_research_persona_builder_acceptance.py
tests/core/test_research_persona_builder_help.py
tests/core/test_research_persona_builder_privacy.py
tests/core/test_research_persona_builder_registry.py
```

The tests are intentionally lightweight. They verify:

- this report exists and documents the command, agent, workflow, patch-only approval contract, privacy guarantees, ambitious feature hooks, and source-ingestion handoff;
- the expected Phase 3 command, agent, and workflow files exist after source-writing executors land;
- runtime surfaces mention the CLI apply/validate flow instead of direct local persona writes;
- privacy labels and prompt-safety language are present in the Phase 3 source surfaces.

## Next Phase Source Ingestion Hooks

Phase 4 should add explicit source ingestion without weakening approval semantics.

Recommended hooks:

- `gpd:build-persona --from-interview`
- `gpd:build-persona --from-project`
- `gpd:build-persona --from-paper <path>`
- `gpd:build-persona --from-bibtex <path>`
- `gpd:build-persona --from-cv <path>`
- `gpd:build-persona --from-collaborator-list <path>`

All source ingestion should produce evidence packets and candidate patches. It must not auto-apply.

Phase 4 should also introduce source-kind-specific evidence normalizers for:

- `interview`
- `project_scan`
- `paper_import`
- `bibtex_import`
- `repo_scan`
- `manual_patch`

Each ingested item should carry provenance, path or citation metadata, privacy default, confidence default, and a user-visible reason for inclusion.

## Acceptance Criteria

Phase 3 is complete when:

- `gpd:build-persona` is registered as a runtime command;
- `gpd-persona-builder` exists and returns patch proposals only;
- the build-persona workflow exists and delegates mutation exclusively to the Phase 2 CLI;
- no source surface directly writes persona storage;
- prompt-facing surfaces mention `never_prompt` exclusion;
- focused acceptance tests pass;
- full repo tests pass before commit.
