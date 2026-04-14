---
name: gpd:dimensional-analysis
description: Systematic dimensional analysis audit on all equations in a derivation or phase
argument-hint: "[phase number or file path]"
context_mode: project-aware
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
  - file_write
  - ask_user
---


<objective>
Audit dimensions across every equation in the target derivation, computation, or phase. Track algebraic steps, dimensionless function arguments, measures, delta functions, and restored units through the workflow.
</objective>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): analyze all equations in phase 3
- If a file path: analyze equations in that specific file
- If empty: prompt for target

Load unit system:

```bash
cat GPD/research-map/FORMALISM.md 2>/dev/null | grep -A 10 "Unit System"
cat GPD/research-map/FORMALISM.md 2>/dev/null | grep -A 20 "Notation and Conventions"
```

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/dimensional-analysis.md
</execution_context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context dimensional-analysis "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```
</process>

<success_criteria>

- [ ] Unit system established (natural, SI, etc.)
- [ ] Dimensional assignments built for all quantities
- [ ] Every equation in target identified and numbered
- [ ] Term-by-term analysis performed on each equation
- [ ] Function arguments verified dimensionless
- [ ] Integration measures checked
- [ ] Delta function dimensions verified
- [ ] Natural units restored for key results
- [ ] Report generated with all anomalies classified
- [ ] Anomalies linked to specific locations in the derivation
      </success_criteria>
