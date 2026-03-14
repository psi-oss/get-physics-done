---
name: gpd:compare-experiment
description: Systematically compare theoretical predictions with experimental or observational data
argument-hint: "[prediction or dataset to compare]"
context_mode: project-aware
requires:
  files: [".gpd/ROADMAP.md"]
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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

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
- If empty: prompt for comparison target

Load theoretical predictions:

```bash
cat .gpd/research-map/ARCHITECTURE.md 2>/dev/null | grep -A 20 "Predictions"
find artifacts/ results/ data/ figures/ simulations/ paper/ -maxdepth 4 \
  \( -name "*.json" -o -name "*.csv" -o -name "*.dat" -o -name "*.h5" \) 2>/dev/null | \
  grep -i "result\|predict\|spectrum\|observable" | head -20
```

Treat `.gpd/**` as internal provenance only. Discover predictions and reusable comparison inputs from stable workspace directories such as `artifacts/`, `results/`, `data/`, `figures/`, `simulations/`, or `paper/`.

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

Follow the compare-experiment workflow: @{GPD_INSTALL_DIR}/workflows/compare-experiment.md
</process>

<success_criteria>

- [ ] Theoretical predictions identified with uncertainties
- [ ] Experimental data loaded with uncertainties (stat + syst)
- [ ] Unit conversions documented and applied
- [ ] Convention matching verified
- [ ] Point-by-point comparison performed with pulls
- [ ] Global chi-squared computed with p-value
- [ ] Residual analysis performed for systematic patterns
- [ ] Discrepancies classified and quantified (in sigma)
- [ ] Root cause analysis for any significant discrepancy
- [ ] Comparison report generated
- [ ] Comparison figures generated (or scripts provided)
- [ ] Results routed appropriately (paper writing or debugging)
      </success_criteria>
