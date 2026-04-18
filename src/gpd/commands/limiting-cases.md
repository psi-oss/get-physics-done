---
name: gpd:limiting-cases
description: Systematically identify and verify all relevant limiting cases for a result or phase
argument-hint: "[phase number or file path]"
context_mode: project-aware
command-policy:
  schema_version: 1
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/research-map/*.md
      - GPD/analysis/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/analysis
    stage_artifact_policy: gpd_owned_outputs_only
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - ask_user
---


<objective>
Systematically identify all relevant limiting cases for a physics result and verify that each limit is correctly recovered. This is the single most powerful verification tool in theoretical physics.

Phase-backed runs write `${phase_dir}/LIMITING-CASES.md`. Standalone current-workspace runs write `GPD/analysis/limits-{slug}.md` rooted at the invoking workspace.

**Why a dedicated command:** Checking limiting cases ad hoc misses limits. A systematic audit ensures every physically meaningful limit is checked. When a result fails a known limit, the error is localized: something in the derivation breaks in that regime, which dramatically narrows the search space for debugging.

**The principle:** Every new result must reduce to known results in appropriate limits. If it doesn't, the new result is wrong (or the known result is wrong, which is rare but possible). There are no exceptions to this principle.
</objective>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3") and project context exists: check limits for all results in phase 3
- If a file path: check limits for results in that file
- If empty in project context: ask one focused question for a phase number or file path
- If empty outside a project: centralized preflight should already reject the launch
- If outside a project: bare numeric tokens are not valid standalone targets; require an explicit file path

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

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context limiting-cases "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Parse the returned JSON before continuing.

- If `project_exists=false`, require an explicit file path target from `$ARGUMENTS`; do not reinterpret a bare numeric token as a standalone phase.
- If `project_exists=true` and `$ARGUMENTS` is empty, ask one focused question to choose a phase number or file path.
- The workflow owns canonical target resolution plus `slug` and `OUTPUT_PATH` selection. Standalone durable outputs stay under `GPD/analysis/` rooted at the current workspace.
- Do not promise phase-local artifacts, project state mutation, or commits when authoritative phase context is absent.

Follow the limiting-cases workflow: @{GPD_INSTALL_DIR}/workflows/limiting-cases.md

**For comprehensive verification** (dimensional analysis + limiting cases + symmetries + convergence), use `gpd:verify-work`.
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
