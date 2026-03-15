<planning_config>

Configuration options for `.gpd/` directory behavior in physics research projects.

<config_schema>

```json
"planning": {
  "commit_docs": true
},
"autonomy": "balanced",
"execution": {
  "review_cadence": "adaptive",
  "max_unattended_minutes_per_plan": 45,
  "max_unattended_minutes_per_wave": 90,
  "checkpoint_after_n_tasks": 3,
  "checkpoint_after_first_load_bearing_result": true,
  "checkpoint_before_downstream_dependent_tasks": true
},
"research_mode": "balanced",
"parallelization": true,
"model_profile": "review",
"git": {
  "branching_strategy": "none",
  "phase_branch_template": "gpd/phase-{phase}-{slug}",
  "milestone_branch_template": "gpd/{milestone}-{slug}"
},
"workflow": {
  "research": true,
  "verifier": true,
  "plan_checker": true
}
```

| Option                          | Default                      | Description                                                                                    |
| ------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------- |
| `commit_docs`                   | `true`                       | Whether to commit planning artifacts to git                                                    |
| `autonomy`                      | `"balanced"`                 | Human-in-the-loop level: `"supervised"`, `"balanced"`, `"yolo"`                                    |
| `execution.review_cadence`      | `"adaptive"`                 | How aggressively long-running execution injects bounded review points                            |
| `execution.max_unattended_minutes_per_plan` | `45`             | Wall-clock budget before a bounded continuation segment must be created, even if the run feels smooth |
| `execution.max_unattended_minutes_per_wave` | `90`             | Wave-level unattended budget before forcing a bounded review                                     |
| `execution.checkpoint_after_n_tasks` | `3`                    | Task budget before forcing a bounded continuation segment                                        |
| `execution.checkpoint_after_first_load_bearing_result` | `true` | Require a first-result sanity gate before fanout, especially when decisive evidence is not yet in hand |
| `execution.checkpoint_before_downstream_dependent_tasks` | `true` | Require review before dependent downstream work unlocks when later tasks would assume unresolved decisive evidence |
| `research_mode`                 | `"balanced"`                 | Research strategy: `"explore"` (breadth), `"balanced"`, `"exploit"` (depth), `"adaptive"`       |
| `parallelization`               | `true`                       | Execute plans within a wave in parallel (`true`) or sequentially (`false`)                     |
| `model_profile`                 | `"review"`                   | Research profile: `"deep-theory"`, `"numerical"`, `"exploratory"`, `"review"`, `"paper-writing"` |
| `git.branching_strategy`        | `"none"`                     | Git branching approach: `"none"`, `"per-phase"`, or `"per-milestone"`                          |
| `git.phase_branch_template`     | `"gpd/phase-{phase}-{slug}"` | Branch template for the `per-phase` strategy                                                   |
| `git.milestone_branch_template` | `"gpd/{milestone}-{slug}"`   | Branch template for the `per-milestone` strategy                                               |
| `workflow.research`             | `true`                       | Spawn the phase-researcher during `plan-phase`                                                 |
| `workflow.verifier`             | `true`                       | Enable end-of-phase verification                                                               |
| `workflow.plan_checker`         | `true`                       | Spawn plan checker agent during plan-phase to validate plans before execution                   |

</config_schema>

<commit_docs_behavior>

**When `commit_docs: true` (default):**

- Planning files committed normally
- SUMMARY.md, STATE.md, ROADMAP.md tracked in git
- Full history of research decisions preserved

**When `commit_docs: false`:**

- Skip all `git add`/`git commit` for `.gpd/` files
- User must add `.gpd/` to `.gitignore`
- Useful for: private research notes, draft calculations, preliminary explorations

**Using gpd CLI (preferred):**

```bash
# Commit with automatic commit_docs + gitignore checks:
gpd commit "docs: update state" --files .gpd/STATE.md

# Load config via init progress (returns JSON):
INIT=$(gpd init progress --include state,config)
# commit_docs is available in the JSON output

# Or use init commands which include commit_docs:
INIT=$(gpd init execute-phase "1")
# commit_docs is included in all init command outputs
```

**Auto-detection:** If `.gpd/` is gitignored, `commit_docs` is automatically `false` regardless of config.json. This prevents git errors when users have `.gpd/` in `.gitignore`.

**Commit via CLI (handles checks automatically):**

```bash
gpd commit "docs: update state" --files .gpd/STATE.md
```

The CLI checks `commit_docs` config and gitignore status internally -- no manual conditionals needed.

</commit_docs_behavior>

<workflow_config_behavior>

**Execution review cadence (`execution.review_cadence`):**

| Value        | Behavior |
| ------------ | -------- |
| `"dense"`    | Frequent bounded review points and short unattended segments |
| `"adaptive"` | Default. Insert first-result and risky-fanout gates automatically when results become load-bearing or decisive evidence remains unresolved |
| `"sparse"`   | Fewest review stops, but required correctness gates still run when a result becomes load-bearing, decisive evidence is still missing, or a wall-clock/task budget trips |

`autonomy` and `execution.review_cadence` are separate axes:

- `autonomy` controls who must review or approve a gate
- `execution.review_cadence` controls when the system must create a bounded gate
- even in `yolo`, first-result and failed-sanity gates are not skipped
- wall-clock and task budgets still create bounded segments in every autonomy mode
- `supervised` means each required gate is shown for approval; `balanced` pauses on non-routine or unresolved cases; `yolo` may auto-continue only after the gate is explicitly cleared
- phase number, wave number, and `model_profile` do not create or retire these gates by themselves

When cadence logic injects a gate, the orchestrator still runs lightweight convention and sanity checks before unlocking downstream work.

**Profile interaction:**

- `model_profile` affects how much detail, rigor, and verification depth each executor applies
- `review_cadence` affects where bounded continuation segments appear
- keep them independent so, for example, `paper-writing` can still run with `dense` cadence when stakes are high

**Cost:** Each cadence-driven gate adds overhead, but the cost is negligible compared to letting a wrong first assumption propagate through downstream waves.

</workflow_config_behavior>

<conventions_behavior>

**Project conventions are not part of `config.json`.**

Notation, unit systems, metric signatures, Fourier conventions, and similar physics choices live in:

- `.gpd/CONVENTIONS.md` — human-readable convention reference
- `.gpd/state.json` (`convention_lock`) — machine-readable convention state

Manage those values with:

- `gpd convention set <key> <value>`
- `/gpd:validate-conventions`
- the notation-coordinator / convention-establishment workflow during project setup

Keep `config.json` focused on workflow orchestration: autonomy, research mode, review cadence, runtime/model overrides, branching, and agent toggles. Do **not** introduce a `physics` block there.

</conventions_behavior>

<setup_uncommitted_mode>

To use uncommitted mode:

1. **Set config:**

   ```json
   "planning": {
     "commit_docs": false
   }
   ```

2. **Add to .gitignore:**

   ```
   .gpd/
   ```

3. **Existing tracked files:** If `.gpd/` was previously tracked:
   ```bash
   git rm -r --cached .gpd/
   git commit -m "chore: stop tracking planning docs"
   ```

</setup_uncommitted_mode>

<branching_strategy_behavior>

**Branching Strategies:**

| Strategy    | When branch created                   | Branch scope     | Merge point             |
| ----------- | ------------------------------------- | ---------------- | ----------------------- |
| `none`      | Never                                 | N/A              | N/A                     |
| `phase`     | At `execute-phase` start              | Single phase     | User merges after phase |
| `milestone` | At first `execute-phase` of milestone | Entire milestone | At `complete-milestone` |

**When `git.branching_strategy: "none"` (default):**

- All work commits to current branch
- Standard GPD behavior

**When `git.branching_strategy: "per-phase"`:**

- `execute-phase` creates/switches to a branch before execution
- Branch name from `phase_branch_template` (e.g., `gpd/phase-03-hamiltonian-construction`)
- All plan commits go to that branch
- User merges branches manually after phase completion
- `complete-milestone` offers to merge all phase branches

**When `git.branching_strategy: "per-milestone"`:**

- First `execute-phase` of milestone creates the milestone branch
- Branch name from `milestone_branch_template` (e.g., `gpd/v1.0-ground-state-calculation`)
- All phases in milestone commit to same branch
- `complete-milestone` offers to merge milestone branch to main

**Template variables:**

| Variable      | Available in              | Description                           |
| ------------- | ------------------------- | ------------------------------------- |
| `{phase}`     | phase_branch_template     | Zero-padded phase number (e.g., "03") |
| `{slug}`      | Both                      | Lowercase, hyphenated name            |
| `{milestone}` | milestone_branch_template | Milestone version (e.g., "v1.0")      |

**Checking the config:**

Use `init execute-phase` which returns all config as JSON:

```bash
INIT=$(gpd init execute-phase "1")
# JSON output includes: branching_strategy, phase_branch_template, milestone_branch_template
```

Or use `init progress` for the config values:

```bash
INIT=$(gpd init progress --include state,config)
# Parse branching_strategy, phase_branch_template, milestone_branch_template from JSON
```

**Branch creation:**

```bash
# For per-phase strategy
if [ "$BRANCHING_STRATEGY" = "per-phase" ]; then
  PHASE_SLUG=$(echo "$PHASE_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
  BRANCH_NAME=$(echo "$PHASE_BRANCH_TEMPLATE" | sed "s/{phase}/$PADDED_PHASE/g" | sed "s/{slug}/$PHASE_SLUG/g")
  git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
fi

# For per-milestone strategy
if [ "$BRANCHING_STRATEGY" = "per-milestone" ]; then
  MILESTONE_SLUG=$(echo "$MILESTONE_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
  BRANCH_NAME=$(echo "$MILESTONE_BRANCH_TEMPLATE" | sed "s/{milestone}/$MILESTONE_VERSION/g" | sed "s/{slug}/$MILESTONE_SLUG/g")
  git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
fi
```

**Merge options at complete-milestone:**

| Option                     | Git command          | Result                           |
| -------------------------- | -------------------- | -------------------------------- |
| Squash merge (recommended) | `git merge --squash` | Single clean commit per branch   |
| Merge with history         | `git merge --no-ff`  | Preserves all individual commits |
| Delete without merging     | `git branch -D`      | Discard branch work              |
| Keep branches              | (none)               | Manual handling later            |

Squash merge is recommended -- keeps main branch history clean while preserving the full development history in the branch (until deleted).

**Use cases:**

| Strategy    | Best for                                                                          |
| ----------- | --------------------------------------------------------------------------------- |
| `none`      | Solo research, exploratory work, single-problem investigations                    |
| `phase`     | Multi-approach comparison, granular rollback, collaboration on shared calculation |
| `milestone` | Publication-oriented work, versioned results, reproducibility checkpoints         |

</branching_strategy_behavior>

</planning_config>
