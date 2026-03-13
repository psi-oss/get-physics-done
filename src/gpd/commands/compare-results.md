---
name: gpd:compare-results
description: Compare internal results, baselines, or methods and emit decisive verdicts
argument-hint: "[phase, artifact, or comparison target]"
context_mode: project-aware
allowed-tools:
  - file_read
  - file_write
  - file_edit
  - shell
  - search_files
  - find_files
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Compare internal results in a machine-readable way: analytics vs numerics, method A vs method B, benchmark vs produced quantity, expected vs observed behavior, or baseline vs modified run.

This command exists because "the two plots look similar" is not a decisive comparison. When a result is load-bearing, GPD should produce an explicit comparison artifact with thresholds, verdicts, and follow-up actions keyed to contract IDs when available.
</objective>

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

Execute the compare-results workflow from @{GPD_INSTALL_DIR}/workflows/compare-results.md end-to-end.
Preserve all validation gates (target mapping, metric selection, verdict emission, and follow-up routing).
</process>
