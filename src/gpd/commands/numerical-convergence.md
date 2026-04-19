---
name: gpd:numerical-convergence
description: Systematic convergence testing for numerical physics computations
argument-hint: "[phase number or file path]"
context_mode: project-aware
command-policy:
  schema_version: 1
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/research-map/VALIDATION.md
      - GPD/analysis/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/analysis
    stage_artifact_policy: gpd_owned_outputs_only
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - ask_user
---


<objective>
Perform systematic convergence tests on numerical computations in the active physics project or on an explicit current-workspace target.

Keep standalone/current-workspace durable outputs under `GPD/analysis/` rooted at the invoking workspace. Only authoritative phase-backed runs may write phase-local reports. Standalone/current-workspace runs stop after writing the analysis artifact, do not mutate `STATE.md` or `state.json`, and do not assume a standalone commit step.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/numerical-convergence.md
</execution_context>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): test convergence for all numerical results in that current-workspace phase
- If a file path: test convergence for computations in that file
- If empty in current-workspace project mode: ask one focused question to identify the phase or file target
- If empty outside a project: command-context validation rejects the request; require an explicit phase number or file path
- Phase-local reports are honest only when authoritative phase context exists in the current workspace. Otherwise write the durable artifact under `GPD/analysis/numerical-{slug}.md`

</context>

<process>
## 0. Validate Context

```bash
CONTEXT=$(gpd --raw validate command-context numerical-convergence "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Execute the numerical-convergence workflow from @{GPD_INSTALL_DIR}/workflows/numerical-convergence.md end-to-end.
Keep its workspace-locked bootstrap, explicit target/output resolution, and the phase-backed vs standalone/current-workspace persistence split intact.

If authoritative phase-backed project context exists, the workflow may write `${phase_dir}/NUMERICAL-VALIDATION.md`.
If no authoritative phase-backed context exists, the durable output must stay under `GPD/analysis/numerical-{slug}.md` in the invoking workspace, with no `STATE.md` or `state.json` mutation and no standalone commit step.
</process>

<success_criteria>

- [ ] Numerical target resolved from the explicit request or authoritative current-workspace phase context
- [ ] Convergence study design and grading recorded for each computation tested
- [ ] Output path is phase-local only when authoritative phase context exists
- [ ] Standalone/current-workspace runs write only under `GPD/analysis/` and do not mutate project state
- [ ] Final report contains enough detail to reproduce the convergence study

</success_criteria>
