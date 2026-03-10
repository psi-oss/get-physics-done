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

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Systematically identify all relevant limiting cases for a physics result and verify that each limit is correctly recovered. This is the single most powerful verification tool in theoretical physics.

**Why a dedicated command:** Checking limiting cases ad hoc misses limits. A systematic audit ensures every physically meaningful limit is checked. When a result fails a known limit, the error is localized: something in the derivation breaks in that regime, which dramatically narrows the search space for debugging.

**The principle:** Every new result must reduce to known results in appropriate limits. If it doesn't, the new result is wrong (or the known result is wrong, which is rare but possible). There are no exceptions to this principle.
</objective>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): check limits for all results in phase 3
- If a file path: check limits for results in that file
- If empty: prompt for target

Load known framework:

```bash
cat .gpd/research-map/FORMALISM.md 2>/dev/null | grep -A 20 "Known Limiting Cases"
cat .gpd/research-map/VALIDATION.md 2>/dev/null | grep -A 30 "Limiting Cases"
```

</context>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/limiting-cases.md
</execution_context>

<process>

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context limiting-cases "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Follow the limiting-cases workflow: @{GPD_INSTALL_DIR}/workflows/limiting-cases.md

**For comprehensive verification** (dimensional analysis + limiting cases + symmetries + convergence), use `/gpd:verify-work`.
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
