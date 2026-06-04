---
name: gpd:ideate
description: Source-grounded research ideation from papers, arXiv IDs, PDFs, TeX files, folders, knowledge docs, or an explicit topic
argument-hint: "[topic | papers | arXiv IDs | PDFs | TeX files | folder | GPD/knowledge docs] [--depth fast|balanced|deep]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: ideation_intake
    resolution_mode: ideation_sources_or_topic
    explicit_input_kinds:
      - topic, papers, arXiv IDs, PDF/TeX files, folder, or GPD/knowledge docs
    allow_external_subjects: true
    allow_interactive_without_subject: true
    allowed_suffixes:
      - .pdf
      - .tex
      - .md
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/knowledge/*.md
      - GPD/literature/*.md
      - GPD/blackboards/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/blackboards
    stage_artifact_policy: gpd_owned_outputs_only
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - task
  - web_search
  - web_fetch
  - ask_user
help:
  group: Knowledge authoring
  order: 425
  compact_description: Run source-grounded idea generation and write blackboard, transcript, and report files
  display_signature: gpd:ideate [topic|sources]
  detail_signature: gpd:ideate [topic|papers|arXiv IDs|PDFs|TeX files|folder|GPD/knowledge docs] [--depth fast|balanced|deep]
  examples:
    - gpd:ideate "quantum memory in disordered spin chains" 2401.12345 ./papers/review.pdf
    - gpd:ideate ./papers ./GPD/knowledge/K-renormalization-group-fixed-points.md --depth balanced
  notes:
    - Creates durable ideation files under `GPD/blackboards/` in the current workspace.
    - Topic-only runs must pass the workflow source gate before ranked source-grounded ideas are reported.
  root_detail_order: 225
---

<objective>
Route an ideation request into the workflow-owned source-grounded ideation flow.

This wrapper owns command-context validation and the public durable-output boundary only. The same-named workflow owns source intake, depth selection, blackboard/transcript/report initialization, multi-agent orchestration, source gating, user steering checkpoints, and final ranked reporting.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/ideate.md
</execution_context>

<context>
Request: $ARGUMENTS

Durable ideation artifacts stay under the current workspace's `GPD/blackboards/` tree. In project-backed mode that is the resolved current project root. In standalone mode it is `./GPD/blackboards/` in the invoking workspace.

Validated command-context owns optional current-workspace project context. Use the `CONTEXT` payload plus the workflow-owned init step for any available `GPD/STATE.md`, `GPD/ROADMAP.md`, `GPD/knowledge/*.md`, or prior blackboard background.
</context>

<process>
## 0. Validate Context

Run `gpd --raw validate command-context ideate "$ARGUMENTS"` before delegation; if it fails, stop and surface the validator output.

## 1. Delegate To Workflow

Execute the included ideate workflow end-to-end.
Do not duplicate source classification, artifact allocation, agent routing, source gates, or report ranking in this wrapper.
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Ideate workflow executed as the authority for mechanics
- [ ] Durable artifacts kept under the current workspace's `GPD/blackboards/`
- [ ] Topic-only requests left to the workflow source gate
</success_criteria>
