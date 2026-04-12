---
name: gpd:limiting-cases
description: Systematically identify and verify all relevant limiting cases for a result or phase
argument-hint: "[phase number or file path]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - ask_user
---


<objective>
Systematically identify relevant limiting cases for a physics result or phase and verify that each expected limit is recovered through the workflow.
</objective>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): check limits for all results in phase 3
- If a file path: check limits for results in that file
- If empty: prompt for target

Load known framework:

```bash
cat GPD/research-map/FORMALISM.md 2>/dev/null | grep -A 20 "Known Limiting Cases"
cat GPD/research-map/VALIDATION.md 2>/dev/null | grep -A 30 "Limiting Cases"
```

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/limiting-cases.md
</execution_context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context limiting-cases "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```
</process>

<success_criteria>

- [ ] All results in target identified
- [ ] Applicable limits enumerated systematically by domain
- [ ] Known limiting expressions identified with sources
- [ ] Each limit verified analytically or numerically
- [ ] Discrepancies characterized (factor, sign, form, divergence)
- [ ] Failures localized to specific derivation steps
- [ ] Report generated with full results table
- [ ] Failed limits diagnosed with likely causes
- [ ] Next steps suggested for any failures
</success_criteria>
