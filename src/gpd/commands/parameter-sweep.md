---
name: gpd:parameter-sweep
description: Systematic parameter sweep with parallel execution and result aggregation
argument-hint: "[phase | computation anchor] [--param name --range start:end:steps] [--adaptive] [--log]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    explicit_input_kinds:
      - computation anchor or file path
      - --param name
      - --range start:end:steps
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/phases/*/README.md
      - GPD/analysis/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/sweeps
    stage_artifact_policy: gpd_owned_outputs_only
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - find_files
  - search_files
  - task
  - ask_user
---

<objective>
Route a parameter-sweep request into the workflow-owned implementation.

This wrapper owns command-context validation and output-root boundaries only. The same-named workflow owns sweep design, wave execution, convergence monitoring, adaptive refinement, result aggregation, and reporting.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/parameter-sweep.md
</execution_context>

<context>
Request: $ARGUMENTS

Accepted targets:

- authoritative current-workspace phase context
- one explicit current-workspace computation anchor, such as a script, notebook, results file, or concrete computation description

Output boundaries:

- Authoritative phase-backed runs may write sibling phase docs and may persist project state.
- All durable sweep artifacts stay under the invoking workspace's `GPD/sweeps/` tree.
- Standalone/current-workspace runs keep both docs and durable artifacts under `GPD/sweeps/{sweep-slug}/`.
- Do not invent `GPD/phases/XX-sweep` for standalone/current-workspace runs.
- Do not write durable sweep datasets to `artifacts/`.
</context>

<process>
## 1. Validate Context

```bash
CONTEXT=$(gpd --raw validate command-context parameter-sweep "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

## 2. Delegate To Workflow

Execute the included parameter-sweep workflow end-to-end.
Preserve its workspace-locked bootstrap, explicit current-workspace target resolution, and the split between authoritative phase-backed docs and current-workspace-only sweep roots.
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Parameter-sweep workflow executed as the authority for mechanics
- [ ] Phase-backed outputs and standalone/current-workspace `GPD/sweeps/` outputs kept distinct
- [ ] No standalone/current-workspace phase directory or `artifacts/` sweep dataset root invented
</success_criteria>
