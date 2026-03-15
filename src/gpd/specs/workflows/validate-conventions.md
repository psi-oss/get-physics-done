<purpose>
Check convention consistency across all completed phases. Detects sign errors, notation drift, metric signature mismatches, and convention lock violations. Critical for catching errors that propagate silently across phases — a wrong sign convention in Phase 2 invalidates everything built on it.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init" priority="first">
**Load project conventions and state:**

```bash
INIT=$(gpd init progress --include state,roadmap,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract: `state_exists`, `roadmap_exists`, `phases`, `current_phase`.

**Read mode settings:**

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `autonomy=supervised`: Present each convention conflict for user resolution before applying fixes.
- `autonomy=balanced` (default): Auto-fix trivial conflicts and clear lock-consistency issues. Pause for ambiguous conflicts requiring physics judgment.
- `autonomy=yolo`: Auto-fix all conflicts using most recent convention as authoritative.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context validate-conventions "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**If `state_exists` is false:**

```
No project state found. Run /gpd:new-project first.
```

Exit.

**Load convention lock from state.json:**

```bash
CONVENTIONS=$(gpd convention list)
```

Parse JSON for all locked convention fields and their values. The convention lock is the project-level source of truth.

**Load CONVENTIONS.md if it exists:**

```bash
cat .gpd/CONVENTIONS.md 2>/dev/null
```

CONVENTIONS.md is the human-readable convention reference. Convention lock (in state.json) is the machine-readable enforced version.
</step>

<step name="check_convention_lock_drift">
**Compare convention lock against CONVENTIONS.md:**

For each field in the convention lock:

1. Find the corresponding entry in CONVENTIONS.md
2. Compare values

| Field | Convention Lock | CONVENTIONS.md | Status |
|-------|----------------|----------------|--------|
| metric_signature | (-,+,+,+) | (-,+,+,+) | OK |
| fourier_convention | physics | mathematical | DRIFT |

**DRIFT** means the documents disagree. This is a CRITICAL issue — one must be wrong.

For each drift:

```
CRITICAL: Convention drift detected

Field: {field}
Convention lock (state.json): {lock_value}
CONVENTIONS.md: {conventions_value}

The convention lock is authoritative. If CONVENTIONS.md is correct,
update the lock: gpd convention set {field} "{value}"
```
</step>

<step name="scan_phase_conventions">
**Scan all completed phases for convention declarations:**

```bash
ROADMAP=$(gpd roadmap analyze)
```

For each phase with `disk_status: "complete"` or `disk_status: "partial"`:

```bash
# Extract conventions from SUMMARY.md frontmatter
for SUMMARY in .gpd/phases/${PHASE_DIR}/*-SUMMARY.md; do
  gpd summary-extract "$SUMMARY" --field conventions --field affects
done
```

Build a convention map:

```
phase_conventions = {
  "Phase 1": { metric_signature: "(-,+,+,+)", fourier: "physics", ... },
  "Phase 2": { metric_signature: "(-,+,+,+)", hbar: "1", ... },
  "Phase 3": { metric_signature: "(+,-,-,-)", ... },  // MISMATCH
}
```
</step>

<step name="cross_reference">
**Cross-reference: do all phase conventions match the project convention lock?**

For each phase and each convention field declared:

1. Look up the field in the convention lock
2. Compare values

Build a findings list with severity levels:

**CRITICAL (sign-affecting, metric, units):**
- Metric signature mismatch (`(-,+,+,+)` vs `(+,-,-,-)`)
- Sign convention mismatch (e.g., `e^{-ikx}` vs `e^{+ikx}` Fourier)
- Unit system mismatch (natural vs SI vs Gaussian)
- Factors of `2*pi` in Fourier convention
- Time-ordering sign convention
- Coupling constant sign

**WARNING (notation inconsistency, non-propagating):**
- Variable naming drift (same quantity, different symbol)
- Index placement conventions (up vs down)
- Normalization convention differences
- Coordinate labeling differences

**INFO (cosmetic, no physics impact):**
- Formatting differences in convention declaration
- Redundant convention re-declarations matching the lock
</step>

<step name="check_unlocked_conventions">
**Identify conventions used across phases but NOT locked:**

Some conventions may appear in phase summaries but never got added to the convention lock. These are vulnerable to drift.

For each convention field found in any phase summary that is NOT in the convention lock:

```
WARNING: Unlocked convention used across phases

Field: {field}
Used in: Phase {X}, Phase {Y}
Values: {X_value}, {Y_value}

This convention is not locked. If phases agree, lock it:
  gpd convention set {field} "{value}"

If phases disagree, this is a potential error source.
```
</step>

<step name="spawn_consistency_checker">
**For thorough validation, spawn gpd-consistency-checker in rapid mode:**

```bash
CONSISTENCY_MODEL=$(gpd resolve-model gpd-consistency-checker)
```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-consistency-checker",
  model="{consistency_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-consistency-checker.md for your role and instructions.

    <mode>rapid</mode>
    <scope>all-phases</scope>

    Validate convention consistency across the entire project.
    Read conventions from state.json via: gpd convention list
    Read all SUMMARY.md files from all completed phases.
    file_read: .gpd/STATE.md, .gpd/state.json, .gpd/CONVENTIONS.md

    Focus on:
    1. Sign conventions propagating correctly across phase boundaries
    2. Metric signature consistency in all tensor expressions
    3. Fourier transform convention (factors of 2*pi) consistency
    4. Unit system consistency (natural units, hbar=1, c=1 implications)
    5. Normalization conventions for wavefunctions, propagators, amplitudes

    Return consistency_status with detailed issue list.
  ",
  description="Validate conventions across all phases"
)
```

**If the consistency checker agent fails to spawn or returns an error:** Proceed without automated consistency checking. Note in the validation report that cross-phase consistency verification was skipped. The convention lock fields and CONVENTIONS.md can still be inspected manually. The user should run `/gpd:validate-conventions` again or inspect conventions manually.

Parse return for `consistency_status`: CONSISTENT, WARNING, or INCONSISTENT.
</step>

<step name="report">
**Present convention consistency report:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > CONVENTION VALIDATION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Phases scanned:** {count}
**Convention lock fields:** {count}
**Status:** {CONSISTENT / ISSUES FOUND}

### Convention Lock vs CONVENTIONS.md

| Field | Lock | Doc | Status |
|-------|------|-----|--------|
| metric_signature | (-,+,+,+) | (-,+,+,+) | OK |
| fourier_convention | physics | physics | OK |

### Phase-by-Phase Consistency

| Phase | Field | Expected | Actual | Severity |
|-------|-------|----------|--------|----------|
| 3 | metric_signature | (-,+,+,+) | (+,-,-,-) | CRITICAL |
| 5 | fourier | physics | mathematical | CRITICAL |

### Unlocked Conventions

| Field | Phases | Values | Risk |
|-------|--------|--------|------|
| hbar_convention | 2, 4, 6 | all "1" | Low (consistent) |
| coupling_def | 3, 5 | "g^2/4pi", "g" | HIGH (inconsistent) |

### Summary

- CRITICAL: {count} (sign-affecting mismatches — must fix)
- WARNING: {count} (notation inconsistencies — should fix)
- INFO: {count} (cosmetic — can ignore)
```

**If CRITICAL issues found:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CRITICAL convention violations detected. Results in affected phases
may be incorrect.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Spawn gpd-notation-coordinator to resolve conflicts:**

```bash
NOTATION_MODEL=$(gpd resolve-model gpd-notation-coordinator)
```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-notation-coordinator",
  model="{notation_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-notation-coordinator.md for your role and instructions.

<task>
Resolve convention conflicts detected by validation.
</task>

<conflicts>
{structured_issues_from_consistency_checker}
</conflicts>

<project_context>
file_read: .gpd/CONVENTIONS.md, .gpd/STATE.md, .gpd/state.json
file_read affected phase SUMMARY.md files.
</project_context>

<instructions>
1. For each CRITICAL conflict, determine which convention is correct
2. Generate conversion tables for affected quantities
3. Update CONVENTIONS.md with resolved conventions
4. Lock resolved conventions via gpd convention set
5. Return CONVENTION UPDATE with list of affected phases that need re-execution
</instructions>
",
  description="Resolve convention conflicts"
)
```

**If the notation coordinator agent fails to spawn or returns an error:** Report the failure. The CRITICAL convention conflicts still need resolution. Offer: 1) Retry notation coordinator, 2) Resolve conflicts manually by editing CONVENTIONS.md and running `gpd convention set` for each field, 3) Abort and leave conflicts unresolved (not recommended — downstream phases will inherit inconsistencies).

**Handle notation-coordinator return:**

- **`CONVENTION UPDATE`:** Display resolved conventions and affected phases. Commit updated CONVENTIONS.md.
- **`CONVENTION CONFLICT`:** Conflicts require user decision. Present options and wait.

**After resolution, recommend follow-up actions:**

```
Recommended actions:
1. /gpd:regression-check {affected_phases} -- re-verify affected phases
2. /gpd:debug -- investigate specific discrepancies
3. Re-execute affected plans with corrected conventions
```

**If WARNING issues only:**

```
No critical issues. {count} warnings found — review and fix at your discretion.

Lock consistent conventions:
  gpd convention set {field} "{value}"
```

**If CONSISTENT:**

```
All conventions consistent across {count} phases. No issues found.
```
</step>

</process>

<failure_handling>

- **No convention lock:** Report that no conventions are locked. Suggest running `/gpd:execute-phase` which locks conventions before parallel execution.
- **No SUMMARY.md files:** Cannot validate — no phase data to check. Report and exit.
- **Consistency checker agent fails:** Fall back to the static analysis from steps 2-4 (convention lock drift + phase scan + cross-reference). Report that deep consistency check was skipped.
- **CONVENTIONS.md missing:** Skip the drift check (step 2). Rely on convention lock in state.json as sole authority.

</failure_handling>

<success_criteria>

- [ ] Convention lock loaded from state.json
- [ ] CONVENTIONS.md compared against lock (if exists)
- [ ] All completed phase SUMMARY.md files scanned for convention fields
- [ ] Cross-reference performed: each phase convention vs project lock
- [ ] Unlocked but used conventions identified
- [ ] gpd-consistency-checker spawned for deep validation
- [ ] Issues classified by severity (CRITICAL / WARNING / INFO)
- [ ] gpd-notation-coordinator spawned for CRITICAL issues (convention conflict resolution)
- [ ] Report presented with actionable next steps
- [ ] Critical issues flagged for immediate attention
</success_criteria>
