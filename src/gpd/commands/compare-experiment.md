---
name: gpd:compare-experiment
description: Systematically compare theoretical predictions with experimental or observational data
argument-hint: "[prediction, dataset, phase, or comparison target]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: comparison
    resolution_mode: explicit_or_interactive_theory_data_comparison
    explicit_input_kinds:
      - prediction, dataset path, phase identifier, or comparison target
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
  - web_search
  - web_fetch
  - ask_user
---


<objective>
Systematically compare theoretical predictions with experimental or observational data. Handles unit conversion, uncertainty propagation, statistical testing, and discrepancy analysis.

**Why a dedicated command:** Theory-experiment comparison is not just plotting two curves on the same axes. It requires rigorous treatment of units, uncertainties, systematic effects, and statistical significance. A "good agreement" by eye may be a 3-sigma discrepancy when uncertainties are properly accounted for. Conversely, a visually poor fit may be statistically acceptable when systematic uncertainties are included.

**The principle:** Agreement between theory and experiment must be quantified. "Looks about right" is not physics. The comparison must state: (1) what was predicted, (2) what was measured, (3) what the uncertainties are on both sides, (4) whether the agreement is statistically significant, and (5) if not, what the discrepancy tells us.

For contract-backed work, the comparison must also state which decisive output or contract target is being tested and emit an explicit verdict ledger keyed by `subject_id` / `reference_id`, not just a prose comparison.
</objective>

<context>
Comparison target: $ARGUMENTS

Interpretation:

- If a prediction name: compare that specific theoretical prediction with data
- If a dataset path: compare theoretical model against that dataset
- If a phase number: compare all predictions from that phase with available data
- If empty: ask one focused clarification question to identify the theory side, the data side, and the decisive comparison target

Load theoretical predictions:

```bash
cat GPD/research-map/ARCHITECTURE.md 2>/dev/null | grep -A 20 "Predictions"
find artifacts/ results/ data/ figures/ simulations/ paper/ -maxdepth 4 \
  \( -name "*.json" -o -name "*.csv" -o -name "*.dat" -o -name "*.h5" \) 2>/dev/null | \
  grep -i "result\|predict\|spectrum\|observable" | head -20
```

Treat `GPD/**` as internal provenance only for source discovery. Discover predictions and reusable comparison inputs from stable workspace directories such as `artifacts/`, `results/`, `data/`, `figures/`, `simulations/`, or `paper/`, but keep the generated GPD-authored comparison package under the current workspace `GPD/comparisons/` subtree.

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compare-experiment.md
</execution_context>

<process>

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context compare-experiment "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Follow the included compare-experiment workflow.
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Compare-experiment workflow executed as the authority for comparison mechanics
- [ ] Current-workspace input discovery and `GPD/comparisons/` output boundaries preserved
</success_criteria>
