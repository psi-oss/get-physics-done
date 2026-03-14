---
template_version: 1
---

# Derivation State Template

Template for `.gpd/DERIVATION-STATE.md` — cumulative record of equations, conventions, and intermediate results across all sessions.

**Purpose:** Survive context resets. Each session appends its key equations, conventions, and results here via the pause-work workflow. This file is append-only (except pruning) and is read by resume-work to restore derivation context.

**Relationship to other files:**

- `continue-here.md` is ephemeral (deleted on resume) — its `<persistent_state>` section is extracted and appended here
- `STATE.md` tracks position and accumulated context — DERIVATION-STATE.md tracks equations and derivation progress
- `CONVENTIONS.md` is the authoritative convention catalog — DERIVATION-STATE.md records which conventions were active per session

---

## File Template

```markdown
---
last_updated: YYYY-MM-DDTHH:MM:SSZ
session_count: 0
total_equations: 0
---

# Derivation State

Cumulative record of equations, conventions, and intermediate results across all sessions.
This file is append-only. Pruning rules apply (see bottom).

---

## Session: {date} — Phase {phase_number}: {phase_name}

**Plan:** {plan_id}
**Tasks completed:** {task_range}

### Key Equations

1. `{latex_equation}` (units: {units}, valid: {validity_range}, derived from: {source_or_method})
2. `{latex_equation}` (units: {units}, valid: {validity_range}, derived from: {source_or_method})

### Conventions Active

- Metric: {metric_signature}
- Fourier: {fourier_convention}
- Units: {unit_system}
- Gauge: {gauge_choice} (if applicable)
- Other: {any_session_specific_conventions}

### Intermediate Results

- {result_id}: {description} — {value_or_expression} (units: {units}, valid: {validity_range})
- {result_id}: {description} — {value_or_expression} (units: {units}, valid: {validity_range})

### Parameter Values

| Parameter | Value | Units | Source |
|-----------|-------|-------|--------|
| {name} | {value} | {units} | {how_determined} |
| {name} | {value} | {units} | {how_determined} |

### Approximations Used

- {approximation_name}: valid when {condition} — checked by {method_or_comparison}

---

[Repeat ## Session blocks for each session...]

---

## Pruning Rules

1. **Maximum 5 sessions retained.** When appending a 6th session, remove the oldest session block.
2. **Remove completed-phase entries.** When a phase is fully verified and archived (milestone complete), its session entries can be pruned. Key equations should already be in the phase SUMMARY.md.
3. **Never prune the most recent session** even if its phase is complete — it may contain context needed for the next phase.
4. **Preserve cross-phase equations.** If an equation from an old session is referenced by `depends_on` in a current intermediate result, do not prune that session.
5. **Git preserves history.** Pruned content is recoverable via `git log -p -- .gpd/DERIVATION-STATE.md`.
```

<guidelines>

**When this file is created:**

- By the pause-work workflow on first session pause
- Initialized with frontmatter and empty structure

**When this file is appended to:**

- By pause-work workflow: extracts `<persistent_state>` from `.continue-here.md` and appends as a new Session block
- Each append increments `session_count` and `total_equations` in frontmatter

**When this file is read:**

- By resume-work workflow: loads full derivation context before resuming
- By execute-plan: optionally references for cross-session equation dependencies

**When this file is pruned:**

- By resume-work workflow: applies pruning rules before loading into context
- On milestone completion: removes entries for fully archived phases

**Content quality:**

- Every equation must have explicit units (even "dimensionless") and validity range
- Convention snapshots must match the convention_lock in state.json at the time of the session
- Result IDs should match those in state.json intermediate_results
- Parameter values should include how they were determined (analytical, numerical, from literature)

**Why this matters:**

Physics derivations are stateful — you cannot "rerun" them like code. An equation derived in session 1 is needed in session 5, but the context window between sessions is empty. This file is the bridge.

</guidelines>
