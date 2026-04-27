---
name: gpd:sensitivity-analysis
description: Systematic sensitivity analysis -- which parameters matter most and how uncertainties propagate
argument-hint: "[--target quantity] [--params p1,p2,...] [--method analytical|numerical]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    explicit_input_kinds:
      - --target quantity
      - --params p1,p2,...
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/analysis/PARAMETERS.md
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
  - find_files
  - search_files
  - task
  - ask_user
---


<objective>
Determine which input parameters most strongly affect an output quantity or uncertainty budget.

Keep any standalone/current-workspace durable artifacts under `GPD/analysis/` rooted at the invoking workspace. Only authoritative phase-backed project runs may persist phase-local reports or update project state; standalone/current-workspace runs stop after writing the analysis artifact and presenting the findings.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/sensitivity-analysis.md
</execution_context>

<context>
Target: $ARGUMENTS

Interpretation:

- Use `--target` to name the observable or stored result to analyze
- Use `--params` to name the parameters included in the analysis
- If `--method` is omitted, let the workflow choose analytical, numerical, or combined
- In standalone/current-workspace mode, centralized preflight requires explicit `--target` and `--params`
- `GPD/STATE.md`, `GPD/ROADMAP.md`, and `GPD/analysis/PARAMETERS.md` are optional current-workspace background context when they exist
- Validated command-context owns optional current-workspace supporting context; the workflow re-loads needed background through its workspace-locked init step instead of this wrapper attaching raw project-file includes
</context>

<process>
Run centralized context preflight before executing the workflow:

```bash
CONTEXT=$(gpd --raw validate command-context sensitivity-analysis "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Execute the included sensitivity-analysis workflow end-to-end.

If authoritative phase-backed project context exists, the workflow may write `${phase_dir}/SENSITIVITY-REPORT.md` and update uncertainty state through the CLI.
If no authoritative phase-backed context exists, the durable output must stay under `GPD/analysis/sensitivity-{slug}.md` in the invoking workspace, with no `STATE.md` or `state.json` mutation and no standalone commit step.
</process>

<success_criteria>

- [ ] Target quantity and parameter list resolved from the explicit request or canonical current-workspace result lookup
- [ ] Sensitivity method chosen and justified
- [ ] Parameters ranked by contribution to the output uncertainty
- [ ] Critical thresholds, stiff directions, and null directions documented
- [ ] Recommendations written for which inputs deserve more effort
- [ ] Standalone/current-workspace runs write only under `GPD/analysis/` and do not mutate project state

</success_criteria>
