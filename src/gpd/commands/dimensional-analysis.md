---
name: gpd:dimensional-analysis
description: Systematic dimensional analysis audit on all equations in a derivation or phase
argument-hint: "[phase number or file path]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    explicit_input_kinds:
      - phase number or file path
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/research-map/FORMALISM.md
      - GPD/research-map/VALIDATION.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/analysis
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
  - file_write
  - ask_user
---


<objective>
Perform a systematic dimensional analysis audit on every equation in a derivation, computation, or phase. Track dimensions through all algebraic steps, verify consistency, and flag any dimensional anomalies.

Dimensional analysis is the cheapest and most powerful diagnostic in physics. It catches ~30% of errors at near-zero cost. This command applies it systematically rather than ad hoc.

**Why a dedicated command:** Dimensional analysis is often done informally -- "looks right" -- but rigorous tracking through multi-step derivations catches errors that informal checks miss. A factor of hbar dropped on line 12 of a derivation propagates silently until the final answer is off by orders of magnitude.

Keep any standalone/current-workspace GPD-authored audit artifact under `GPD/analysis/` rooted at the invoking workspace. Phase-backed context may change how the target is interpreted, but it should not silently relocate a standalone/current-workspace audit into some other recovered project.
</objective>

<context>
Target: $ARGUMENTS

Interpretation:

- If a number (e.g., "3"): analyze all equations in phase 3 when current-workspace project context can resolve that phase
- If a file path: analyze equations in that specific file
- If empty and project context exists: prompt for the target
- If empty outside a project: command-context validation rejects the request; rerun with an explicit target

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

**Pre-flight check:**
```bash
CONTEXT=$(gpd --raw validate command-context dimensional-analysis "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Follow the dimensional-analysis workflow: @{GPD_INSTALL_DIR}/workflows/dimensional-analysis.md
Preserve workspace-locked initialization, keep standalone/current-workspace durable outputs under `GPD/analysis/`, treat missing conventions as explicit user input instead of a fake project failure, and do not promise a standalone commit.

**For comprehensive verification** (dimensional analysis + limiting cases + symmetries + convergence), use `gpd:verify-work`.
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
