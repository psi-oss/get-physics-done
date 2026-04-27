---
name: gpd:compare-results
description: Compare internal results, baselines, or methods and emit decisive verdicts
argument-hint: "[comparison target or source-a vs source-b]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: comparison
    resolution_mode: explicit_or_interactive_internal_comparison
    explicit_input_kinds:
      - comparison target, phase, artifact path, or source-a vs source-b
    allow_external_subjects: true
    allow_interactive_without_subject: true
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/comparisons
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
Compare internal results in a machine-readable way: analytics vs numerics, method A vs method B, benchmark vs produced quantity, expected vs observed behavior, or baseline vs modified run.

This command exists because "the two plots look similar" is not a decisive comparison. When a result is load-bearing, GPD should produce an explicit comparison artifact with thresholds, verdicts, and follow-up actions keyed to contract IDs when available.
</objective>

<context>
Comparison subject: $ARGUMENTS

Interpretation:

- If a phase number or artifact path: compare that result against the relevant baseline, alternate method, or benchmark available in the current workspace context
- If a named comparison target or explicit `source-a vs source-b` request: resolve both sides directly
- If empty: ask one focused clarification question to identify Source A, Source B, and the decisive metric before proceeding

External comparison inputs may live anywhere, but keep the generated GPD-authored comparison package under the current workspace `GPD/comparisons/` subtree.
</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compare-results.md
</execution_context>

<process>
```bash
CONTEXT=$(gpd --raw validate command-context compare-results "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Execute the included compare-results workflow end-to-end.
Preserve all validation gates (target mapping, metric selection, verdict emission, and follow-up routing), and keep the final comparison package under the current workspace `GPD/comparisons/` subtree.
</process>
