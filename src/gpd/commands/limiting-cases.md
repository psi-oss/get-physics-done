---
name: gpd:limiting-cases
description: Systematically identify and verify all relevant limiting cases for a result or phase
argument-hint: "[phase number or file path]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    explicit_input_kinds:
      - phase number or file path
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/research-map/*.md
      - GPD/analysis/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/analysis
    stage_artifact_policy: gpd_owned_outputs_only
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - ask_user
---


<objective>
Route a limiting-cases request into the workflow-owned implementation.

This wrapper owns command-context validation and the public output-root boundary only. The same-named workflow owns target resolution, convention loading, limit enumeration, verification, diagnosis, and reporting.
</objective>

<context>
Target: $ARGUMENTS

Phase-backed runs write `${phase_dir}/LIMITING-CASES.md`. Standalone current-workspace runs write `GPD/analysis/limits-{slug}.md` rooted at the invoking workspace.
For standalone analysis, bare numeric tokens are not valid standalone targets.

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/limiting-cases.md
</execution_context>

<process>

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context limiting-cases "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Parse the returned JSON before continuing.

The workflow owns canonical target resolution plus `slug` and `OUTPUT_PATH` selection. Do not promise phase-local artifacts, project state mutation, or commits when authoritative phase context is absent.

Follow the included limiting-cases workflow.
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Limiting-cases workflow executed as the authority for mechanics
- [ ] Output-root boundaries preserved
</success_criteria>
