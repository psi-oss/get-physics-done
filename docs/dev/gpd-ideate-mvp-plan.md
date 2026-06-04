# gpd:ideate MVP Plan

Branch: `feature/gpd-ideate-mvp`

This document is the review plan for implementing `gpd:ideate` in `PSI-GPD`. It is intentionally limited to a demo-ready MVP: a minimum viable product that shows the real workflow end to end without importing the full older Manki prototype wholesale.

No implementation should begin until this plan is approved.

## Goal

Build a source-grounded ideation workflow that takes a set of papers or existing GPD knowledge documents, digests them into a durable blackboard, runs a hypothesis generator against a general critic, and produces a ranked report of research questions plus the next best experiment, calculation, derivation, simulation, or literature check for each surviving idea.

The user-facing command will be:

```text
gpd:ideate [topic, papers, arxiv ids, folder, or existing knowledge docs]
```

The workflow must also work before a GPD project exists. In that mode it writes durable files under the current workspace's `GPD/blackboards/`.

## User Requirements

- Command name: `gpd:ideate`.
- Durable output root: `GPD/blackboards`.
- It must work in a current project or before any project exists.
- It must accept papers, arXiv IDs/URLs, PDFs, TeX files, folders, existing `GPD/knowledge/*.md` docs, and topic/question text.
- Topic-only input must not silently invent source-grounded ideas. It should ask whether the user wants to supply sources or search for candidate papers.
- Source grounding is mandatory for final ranked ideas.
- Do not show explicit final labels like `grounded`, `mixed`, or `speculative`.
- Final report must include ranked research questions.
- Every non-vetoed idea must include a next best experiment/calculation/check.
- Ranking criteria: novelty, physics importance, and feasibility.
- The system should point out possible issues with ideas.
- Use a multi-agent loop: `gpd-ideator` generates hypotheses and one general critic reviews them.
- Ask the user for depth preference: fast, balanced, or deep.
- Vetoed ideas still appear in a separate `Vetoed Ideas` section.
- The generator-critic exchange must be accessible afterwards.
- The user should be able to interrupt or steer between rounds.
- The internal generator agent should be named `gpd-ideator`.
- Port or rebuild the useful part of `paper-digester` for this flow.

## What We Should Reuse From Manki

The older implementation in `PSI-GPD-Manki` has useful deterministic structure, but its full orchestration is too large and stale for the current branch.

Reuse/adapt:

- Source manifest logic from `src/gpd/core/ideate_sources.py`.
- Session allocation and collision-safe artifact paths from `src/gpd/core/ideate_blackboard.py`.
- Three durable artifact pattern: blackboard, transcript, report.
- Template ideas from:
  - `src/gpd/specs/templates/ideate-blackboard.md`
  - `src/gpd/specs/templates/ideate-transcript.md`
  - `src/gpd/specs/templates/ideation-report.md`
- Topic-only behavior: create a blocked source row and ask for sources/search before source-grounded ideation.

Do not directly port for the MVP:

- `ideate_loop.py`.
- Manki's full discussion-agent fanout.
- Adversarial/canary/cluster/meta-audit machinery.
- Stale knowledge schema assumptions such as old `Draft`/`Stable` casing and sequential `K-NNN` IDs.
- Automatic commits.
- Fake or weak `--derive-equations` behavior.

## MVP Architecture

### Surface

Add a project-aware command:

```text
src/gpd/commands/ideate.md
src/gpd/specs/workflows/ideate.md
```

Use `context_mode: project-aware`, not `project-required`, because ideation should work both inside and outside a GPD project.

The command wrapper should remain thin:

1. Validate command context.
2. Load the workflow prompt.
3. Let the workflow initialize source/artifact state and orchestrate agents.

The command policy should declare managed durable output under:

```text
GPD/blackboards
```

### Durable Files

Each ideation session creates exactly three sibling files:

```text
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>.md
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-transcript.md
GPD/blackboards/ideate-YYYY-MM-DD-<topic-slug>-report.md
```

If those names already exist, append a numeric suffix such as `-2`.

The blackboard is the live shared workspace. The transcript preserves the generator-critic exchange. The report is the demo-facing output.

### Internal Agents

Add exactly three new internal agents for the MVP:

```text
src/gpd/agents/gpd-paper-digester.md
src/gpd/agents/gpd-ideator.md
src/gpd/agents/gpd-ideation-critic.md
```

Do not add `gpd-ideation-distiller` in the first pass. The parent workflow can distill into the final report. This keeps the implementation smaller while still satisfying the generator/critic requirement.

Agent roles:

- `gpd-paper-digester`: turns a source paper or existing text surface into source-grounded digest notes using the current `GPD/knowledge` schema conventions.
- `gpd-ideator`: proposes candidate research questions and next experiments from the source digests and blackboard.
- `gpd-ideation-critic`: reviews candidates for source support, novelty, physics importance, feasibility, assumption risk, and experiment quality; it can veto ideas.

Agent frontmatter must match the current closed schema. All three should use:

```yaml
commit_authority: orchestrator
surface: internal
shared_state_authority: return_only
```

Recommended role families:

```yaml
gpd-paper-digester: analysis
gpd-ideator: analysis
gpd-ideation-critic: review
```

Recommended artifact authority:

```yaml
gpd-paper-digester: scoped_write
gpd-ideator: scoped_write
gpd-ideation-critic: scoped_write
```

Each writable internal agent body must include the repo-required internal specialist boundary text exactly once.

## Source Intake And Grounding

### Source Manifest

`gpd:ideate` should create one source ledger in the blackboard init block:

```yaml
source_manifest:
  sources:
    - source_id: SRC-001
      kind: arxiv | pdf | tex | knowledge_doc | directory_item | topic | blocked
      input: ""
      normalized_ref: ""
      status: pending | completed | reused | blocked
      digest_path: ""
      warnings: []
```

The source manifest is the only evidence ledger. Final ranked ideas must cite at least one `SRC-NNN` whose status is `completed` or `reused`.

Topic rows are useful context but are never evidence.

### Accepted Inputs

The intake helper should accept:

- arXiv IDs and URLs, including old-style IDs such as `hep-th/9901001`.
- Explicit `.pdf` files.
- Explicit `.tex` files.
- Existing `GPD/knowledge/K-*.md` docs.
- Directories containing `.tex` and `.pdf`.
- Free-form topics/questions.

Use the current repo's shared arXiv normalizer instead of Manki's local regex:

```text
gpd.core.arxiv_source_download.normalize_arxiv_id
```

Directory scan rules for MVP:

- Keep it shallow.
- Accept only paper-like `.tex` and `.pdf` files.
- Prefer `.tex` over same-stem `.pdf`.
- Enforce `--max-papers` if supported.
- Record duplicate or skipped files as warnings instead of failing silently.

### Topic-Only Flow

If the invocation is only a topic and no usable project/knowledge sources are selected, the workflow should ask:

```text
Do you want to supply paper/arXiv/PDF/folder sources, or should GPD search for candidate papers?
```

If the user chooses search:

1. Run a bounded literature search.
2. Show 3 to 5 candidate papers with short reasons.
3. Ask which papers to ingest.
4. Only then run source-grounded ideation.

If no sources are available, the command may create a blackboard and transcript with a blocked state, but it must not produce final ranked source-grounded ideas.

### Paper Digester

`gpd-paper-digester` should be a current-main rewrite, not a direct Manki copy.

It should:

- Produce digest notes compatible with the current `GPD/knowledge` schema direction.
- Use `knowledge_schema_version`, deterministic `knowledge_id`, lowercase `status: draft`, typed `sources`, and structured `coverage_summary`.
- Never promote a knowledge document to stable.
- For `.tex`, read directly.
- For `.pdf`, derive a text surface with the current artifact-text validator/extractor and preserve the original PDF as the source artifact.
- For arXiv, normalize the ID and prefer TeX/source when available; otherwise record extraction limitations.
- Return `gpd_return` with status, source ID, digest path, grounding warnings, and files written.

For the hackathon demo, the digester can write concise source notes under the session blackboard scope or draft knowledge docs under `GPD/knowledge/`. The stronger long-term path is to route through `gpd:digest-knowledge` so knowledge lifecycle ownership remains centralized.

## Blackboard, Transcript, And Report

### Blackboard Sections

The blackboard should be structured enough for a demo and for later continuation:

```text
# Ideation Blackboard

## Session
## User Preferences
## Source Manifest
## Source Digests
## Cross-Paper Model
## Tensions And Confusions
## Candidate Ideas
## Critic Notes
## Vetoed Ideas
## Ranked Questions
## Next Experiments Or Calculations
## Open Steering Questions
```

### Transcript Sections

The transcript should preserve the generator-critic exchange in readable turns:

```text
# Ideation Transcript

## Turn 1

### User Or Workflow Prompt
### gpd-ideator Candidate Set
### gpd-ideation-critic Review
### gpd-ideator Revision
### Parent Synthesis
### Durable Effects
```

### Report Sections

The final report should be easy to show in a demo:

```text
# Ideation Report

## Executive Summary
## Source Corpus
## Ranked Research Questions
## Next Best Experiments Or Calculations
## Possible Issues
## Vetoed Ideas
## Recommended Next Actions
```

Each ranked idea should use this visible shape:

```yaml
question_id: RQ-001
research_question: ""
source_ids:
  - SRC-001
score:
  novelty: 1-5
  physics_importance: 1-5
  feasibility: 1-5
  overall: 1-5
why_it_matters: ""
next_best_experiment:
  type: calculation | derivation | simulation | real_world_experiment | literature_check
  objective: ""
  protocol: ""
  success_criterion: ""
  required_inputs: []
possible_issues:
  - ""
```

Do not expose `grounded/mixed/speculative` labels. Instead, enforce source grounding by requiring source IDs and source-specific support for every non-vetoed final idea.

Vetoed ideas should use:

```yaml
idea_id: VI-001
idea: ""
veto_reason: ""
vetoed_by: gpd-ideation-critic
source_ids: []
possible_revisit_condition: ""
```

## Workflow Logic

### Depth Modes

At the start, ask which depth the user wants unless the invocation specifies it:

- `fast`: one generator pass, one critic pass, one revision, one report.
- `balanced`: two generator/critic rounds with a user steering checkpoint.
- `deep`: three rounds, broader search or more source digestion, and user steering between rounds.

For the demo, implement all three labels, but allow `deep` to reuse the same mechanics with more rounds rather than building a separate engine.

### Round Flow

Each round should follow:

1. Parent workflow updates blackboard with current sources and preferences.
2. `gpd-ideator` proposes candidate research questions and next experiments.
3. `gpd-ideation-critic` reviews each candidate.
4. Critic marks each candidate as keep, revise, or veto.
5. Vetoed ideas are moved to `Vetoed Ideas`, not deleted.
6. Ideator revises kept/revise candidates.
7. Parent writes transcript turn and updates blackboard.
8. If depth requires it, ask the user whether to steer, continue, narrow, or stop.
9. Parent writes final ranked report.

### Critic Veto Reasons

The critic can veto for any of:

- Insufficient source support.
- Low novelty.
- Low physics importance.
- Low feasibility.
- Confused or hidden assumptions.
- The proposed experiment/calculation does not test the idea.
- The idea is outside the source corpus.
- The result would be non-actionable in the user's current timeframe.

## Files To Add

Prompt and templates:

```text
src/gpd/commands/ideate.md
src/gpd/specs/workflows/ideate.md
src/gpd/specs/templates/ideate-blackboard.md
src/gpd/specs/templates/ideate-transcript.md
src/gpd/specs/templates/ideation-report.md
src/gpd/agents/gpd-paper-digester.md
src/gpd/agents/gpd-ideator.md
src/gpd/agents/gpd-ideation-critic.md
```

Core helpers:

```text
src/gpd/core/ideate_sources.py
src/gpd/core/ideate_blackboard.py
```

Focused tests:

```text
tests/core/test_ideate_sources.py
tests/core/test_ideate_blackboard.py
tests/core/test_ideate_prompt_contract.py
```

## Files Likely To Update

Command/help/registry:

```text
src/gpd/registry.py
src/gpd/specs/workflows/help.md
src/gpd/specs/references/help/detailed-command-reference.md
tests/core/test_command_prompt_budget.py
tests/core/test_spawn_contract_inventory.py
tests/core/test_spawn_contracts.py
tests/core/test_prompt_wiring.py
```

Core wiring:

```text
src/gpd/core/constants.py
src/gpd/core/context.py
src/gpd/cli.py
tests/repo_graph_contract.json
tests/README.md
```

Agent/model wiring:

```text
src/gpd/core/config.py
src/gpd/specs/references/orchestration/model-profiles.md
src/gpd/specs/workflows/set-profile.md
tests/core/test_agent_prompt_budget.py
tests/core/test_agent_role_prompting.py
tests/core/test_agent_spawn_policy.py
tests/core/test_config.py
tests/test_metadata_consistency.py
```

Changelog:

```text
CHANGELOG.md
```

## Model Profile Plan

Adding three internal agents changes the known agent count from 24 to 27.

Suggested tiers:

| Agent | deep-theory | numerical | exploratory | review/default | paper-writing |
| --- | --- | --- | --- | --- | --- |
| `gpd-paper-digester` | tier-1 | tier-2 | tier-2 | tier-2 | tier-2 |
| `gpd-ideator` | tier-1 | tier-2 | tier-1 | tier-2 | tier-2 |
| `gpd-ideation-critic` | tier-1 | tier-2 | tier-2 | tier-1 | tier-2 |

Mirror these in both `src/gpd/core/config.py` and `src/gpd/specs/references/orchestration/model-profiles.md`.

## Generated Artifacts

After implementation, regenerate:

```bash
uv run python scripts/render_help_surface.py
uv run python scripts/sync_repo_graph_contract.py
```

Then run check mode:

```bash
uv run python scripts/render_help_surface.py --check
uv run python scripts/sync_repo_graph_contract.py --check
```

If public surfaces change, also run:

```bash
uv run python scripts/render_public_surface.py --check
```

## Test Plan

Minimum focused test run:

```bash
uv run pytest tests/core/test_ideate_sources.py tests/core/test_ideate_blackboard.py tests/core/test_ideate_prompt_contract.py -q
uv run pytest tests/test_registry.py tests/core/test_prompt_wiring.py tests/core/test_command_prompt_budget.py -q
uv run pytest tests/core/test_agent_prompt_budget.py tests/core/test_agent_role_prompting.py tests/core/test_agent_spawn_policy.py tests/core/test_config.py -q
uv run pytest tests/core/test_help_inventory_contract.py tests/core/test_help_public_surface_sync.py tests/core/test_help_renderer.py -q
```

Command-context smoke checks:

```bash
uv run gpd --raw help --command ideate
uv run gpd --raw command field-access ideate --style json
tmpdir="$(mktemp -d)"
uv run gpd --raw --cwd "$tmpdir" validate command-context ideate "test topic"
```

Broader verification if time allows:

```bash
uv run pytest tests/test_metadata_consistency.py tests/core/test_repo_interdependency_graph.py tests/core/test_generated_surface_target_registry.py -q
uv run pytest tests/adapters/test_runtime_projected_prompt_parity.py tests/adapters/test_runtime_projected_command_requirement_coverage.py tests/adapters/test_frontmatter_projection.py -q
```

Manual demo smoke:

```text
gpd:ideate "some explicit topic" path/to/paper.tex path/to/paper.pdf
```

Expected demo output:

- Three files under `GPD/blackboards/`.
- Source manifest contains `SRC-NNN` rows.
- Transcript contains `gpd-ideator` and `gpd-ideation-critic` turns.
- Report contains ranked research questions.
- Every surviving idea has novelty, physics importance, feasibility, overall score, source IDs, possible issues, and a next best experiment/calculation/check.
- Vetoed ideas are present in a separate section.

## Implementation Worker Split After Approval

When this plan is approved, spawn six implementation subagents with disjoint scopes:

1. Core source intake worker
   - Owns `src/gpd/core/ideate_sources.py` and `tests/core/test_ideate_sources.py`.
   - Ports/adapts Manki source manifest behavior using current arXiv normalization.

2. Core artifact/session worker
   - Owns `src/gpd/core/ideate_blackboard.py`, constants/layout additions, and `tests/core/test_ideate_blackboard.py`.
   - Implements collision-safe paths and initial blackboard/transcript/report rendering.

3. Command/workflow worker
   - Owns `src/gpd/commands/ideate.md`, `src/gpd/specs/workflows/ideate.md`, and spawn-contract tests.
   - Implements the user-facing workflow, depth modes, source-gate rules, and generator/critic loop prompt.

4. Agent prompt worker
   - Owns the three new agent markdown files and agent prompt contract tests.
   - Creates `gpd-paper-digester`, `gpd-ideator`, and `gpd-ideation-critic`.

5. Registry/config/generated-surface worker
   - Owns registry category updates, model profile rows, help regeneration, repo graph regeneration, prompt budgets, and metadata consistency updates.

6. Integration and demo worker
   - Owns final focused test execution, smoke-command validation, bug fixes in coordination with the parent, and a short demo transcript/report check.

The parent should integrate worker changes, resolve conflicts, run the final focused test set, and keep the branch ready for a PR.

## Risks And Mitigations

- Direct Manki import risk: stale schemas and missing agents. Mitigation: port deterministic helpers only and rewrite prompts to current repo conventions.
- Source grounding risk: topic-only runs could hallucinate final ideas. Mitigation: enforce source IDs for every non-vetoed final idea and block final ranking without completed/reused sources.
- PDF extraction risk: equations may be poorly recovered. Mitigation: preserve extraction warnings and prefer TeX/arXiv source when available.
- Scope risk: adding agents triggers config and prompt-budget failures. Mitigation: include model/profile/test updates in the MVP scope.
- Demo timing risk: full paper ingestion may be slow. Mitigation: support existing `GPD/knowledge/*.md` reuse and explicit TeX/PDF files, and keep depth mode default to `fast`.
- User steering risk: a command run may need interaction. Mitigation: checkpoint after rounds and persist state so the transcript/report are still useful if interrupted.

## Approval Checklist

Approve this plan if the first implementation should:

- Add three internal agents: `gpd-paper-digester`, `gpd-ideator`, `gpd-ideation-critic`.
- Use `GPD/blackboards` as the durable root.
- Build source-grounded ideation only after source intake/digestion.
- Keep vetoed ideas in a separate final section.
- Avoid exposing `grounded/mixed/speculative` labels in the report.
- Defer Manki's full discussion loop, adversarial machinery, and automatic commits.
