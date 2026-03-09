---
name: gpd-compare-experiment
description: Systematically compare theoretical predictions with experimental or observational data
argument-hint: "[prediction or dataset to compare]"
requires:
  files: [".planning/ROADMAP.md"]
allowed-tools:
  - read_file
  - write_file
  - apply_patch
  - shell
  - grep
  - glob
  - web_search
  - web_fetch
  - ask_user
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Systematically compare theoretical predictions with experimental or observational data. Handles unit conversion, uncertainty propagation, statistical testing, and discrepancy analysis.

**Why a dedicated command:** Theory-experiment comparison is not just plotting two curves on the same axes. It requires rigorous treatment of units, uncertainties, systematic effects, and statistical significance. A "good agreement" by eye may be a 3-sigma discrepancy when uncertainties are properly accounted for. Conversely, a visually poor fit may be statistically acceptable when systematic uncertainties are included.

**The principle:** Agreement between theory and experiment must be quantified. "Looks about right" is not physics. The comparison must state: (1) what was predicted, (2) what was measured, (3) what the uncertainties are on both sides, (4) whether the agreement is statistically significant, and (5) if not, what the discrepancy tells us.
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
cat .planning/research-map/ARCHITECTURE.md 2>/dev/null | grep -A 20 "Predictions"
ls .planning/phases/*/results/ 2>/dev/null
find . -name "*.json" -o -name "*.csv" -o -name "*.dat" | grep -i "result\|predict" | head -10
```

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/compare-experiment.md
</execution_context>

<process>

**Pre-flight check:**
```bash
if [ ! -d ".planning" ]; then
  echo "Error: No GPD project found. Run $gpd-new-project first."
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
