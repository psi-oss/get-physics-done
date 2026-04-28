---
name: gpd:derive-equation
description: Perform a rigorous physics derivation with systematic verification at each step
argument-hint: "[equation or topic to derive]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    explicit_input_kinds:
      - equation or topic to derive
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/analysis/*.md
      - GPD/phases/*/DERIVATION-*.md
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
  - task
  - ask_user
---


<objective>
Perform a rigorous physics derivation with systematic verification at each step.

Provide the equation or topic to derive as an argument (e.g., `gpd:derive-equation "effective mass from self-energy"`). If project context already exists and the request is omitted or ambiguous, ask one focused clarification question. Outside a project, an explicit derivation target is required and empty standalone launches stay blocked.

Keep standalone/current-workspace durable derivation artifacts under `GPD/analysis/` rooted at the invoking workspace. Only runs with authoritative phase context may additionally write sibling phase artifacts and persist project registry state.

- States assumptions explicitly, establishes notation and conventions
- Performs step-by-step derivation with dimensional analysis at each stage
- Verifies intermediate results against known limits and symmetry properties
- Justifies and bounds all approximations with error estimates
- For theorem-bearing derivations, spawns `gpd-check-proof` as a separate proof critic and fails closed without its audit
- Produces a complete, self-contained derivation document with boxed final result
  </objective>

<context>
Target: $ARGUMENTS

Validated command-context owns optional current-workspace state detection. Use the `CONTEXT` payload plus the workflow-owned init/result lookup for any available `GPD/STATE.md` background; this wrapper must not attach raw project-file includes.
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/derive-equation.md
</execution_context>

<process>
## 0. Validate Context

```bash
CONTEXT=$(gpd --raw validate command-context derive-equation "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

## 1. Execute the Derivation Workflow

Execute the included derive-equation workflow end-to-end.
Preserve its gates: canonical result lookup via `gpd result search` and direct stored-result inspection via `gpd result show "{result_id}"`, assumptions, notation, derivation steps, dimensional checks, limiting cases, artifact write, and registry persistence only when authoritative phase context exists.
Registry writes use `gpd result persist-derived`, reuse or carry forward a stable `result_id`, preserve the actual canonical `result_id`, seed continuation, and stay disabled for standalone artifacts.
</process>
