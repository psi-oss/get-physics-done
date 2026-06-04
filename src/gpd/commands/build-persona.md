---
name: gpd:build-persona
description: Build a private research persona patch from explicit interview or consented source ingestion
argument-hint: "[focus | --interview-only | --from-current-project | --paper PATH | --bibtex PATH | --repo-scan PATH | --manual-patch PATH | --statement TEXT]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: research_persona_scope
    resolution_mode: explicit_input_or_interactive_scope
    explicit_input_kinds:
      - focus area
      - current-project scan request
      - interview-only request
      - paper path ingestion request
      - BibTeX path ingestion request
      - repository scan request
      - manual JSON patch review request
      - user statement capture request
    allow_interactive_without_subject: true
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/knowledge/*.md
      - GPD/literature/*.md
      - paper/*.tex
      - manuscript/*.tex
      - references/*.bib
      - literature/*.bib
      - pyproject.toml
      - package.json
      - Cargo.toml
  output_policy:
    output_mode: advisory
    managed_root_kind: none
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - ask_user
  - task
help:
  group: Tangents, memory, and exports
  order: 545
  compact_description: Draft a private research-persona patch for explicit review
  display_signature: gpd:build-persona [focus|--from-current-project|--interview-only]
  detail_signature: gpd:build-persona [focus|--from-current-project|--interview-only]
  examples:
    - gpd:build-persona --interview-only
    - gpd:build-persona --from-current-project "math/code balance and citation style"
    - gpd:build-persona --paper paper/main.tex
    - gpd:build-persona --bibtex references/library.bib
    - gpd:build-persona --manual-patch /tmp/persona-patch.json
  notes:
    - Emits a candidate ResearchPersonaPatch only; apply it separately with `gpd research-persona apply-patch`.
    - Interviewing, paper imports, BibTeX imports, repository scans, and manual patch review require exact source consent.
    - Source-derived candidates use `gpd research-persona ingest-source SOURCE_JSON|- --output PATCH_JSON`.
    - Never writes persona storage directly.
  root_detail_order: 245
---

<objective>
Draft a candidate `ResearchPersonaPatch` JSON object that captures
user-approved research-persona facts, preferences, expertise axes, workstyle
signals, and scientific taste notes.

This wrapper owns the public command surface and the no-direct-mutation rule
only. The same-named workflow owns consent checks, interview design, explicit
source ingestion, privacy classification, schema validation, and final patch
presentation.

No silent memory: this command must not silently create, infer, or update
persona memory. Explicit user approval is required before any mutation step,
including `gpd research-persona apply-patch`.

When existing persona context is needed, request only a prompt-safe capsule or
projection such as `gpd research-persona export-capsule`; never place the raw
private profile in prompt context.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/build-persona/persona-intake.md
</execution_context>

<context>
Requested persona-building scope or source mode: $ARGUMENTS

This command is project-aware because the user may explicitly permit current
project evidence, named paper paths, BibTeX libraries, repository scans, manual
JSON patches, or direct user statements, but it must also work without a GPD
project through interview only. Do not auto-reenter a recent project for persona
building.
</context>

<process>
Follow the included first-stage build-persona authority exactly. Later source
ingestion, synthesis, approval, and application-preview stages are manifest-owned.

Preserve these command-surface invariants while delegating mechanics to the
workflow:

- Interviewing is opt-in and scoped by the user's answer.
- Source ingestion is opt-in, category-scoped, path-scoped where applicable,
  and read-only until a candidate patch is produced.
- Supported source modes are interview, current project, paper path, BibTeX
  path, repository scan, manual JSON patch, and user statement.
- For every non-interview source, ask the user to approve the exact source
  category and path before reading it.
- Convert explicit sources into candidate patches through
  `gpd research-persona ingest-source SOURCE_JSON|- --output PATCH_JSON`;
  do not hand-write durable persona state or use nonexistent ingestion mode
  flags.
- The only output is a candidate `ResearchPersonaPatch` JSON object plus review
  guidance.
- Persona storage is never mutated by this runtime command. The user must apply
  the patch separately with `gpd research-persona apply-patch`.
- Do not call `apply-patch` until explicit user approval is given after the
  candidate patch and diff have been reviewed.
- Keep all downstream persona context prompt-safe by using role capsules or
  projections; never inject the raw private profile into prompts.
- After a user-approved application, future Researcher Doppelganger,
  Expertise-Aware Explanation, and Scientific Taste previews must use
  `gpd research-persona export-capsule` or the Phase 5 advisory helpers:
  `doppelganger`, `explain-plan`, and `taste-check`.
</process>

<success_criteria>

- [ ] Build-persona workflow executed as the authority for mechanics
- [ ] Explicit consent collected before interview questions or source reads
- [ ] Source category and exact path approved before paper, BibTeX, project, repository, or manual patch ingestion
- [ ] Candidate patch created through `gpd research-persona ingest-source` when a source mode is used
- [ ] Candidate `ResearchPersonaPatch` JSON emitted for review
- [ ] User shown the validate, diff, explicit approval, and apply-patch route
- [ ] No direct persona storage mutation performed
</success_criteria>
