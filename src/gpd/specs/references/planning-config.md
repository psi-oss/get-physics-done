<planning_config>

Configuration options for `.gpd/` directory behavior in physics research projects.

<config_schema>

```json
"planning": {
  "commit_docs": true,
  "search_gitignored": false
},
"autonomy": "guided",
"research_mode": "balanced",
"parallelization": true,
"model_profile": "review",
"git": {
  "branching_strategy": "none",
  "phase_branch_template": "gpd/phase-{phase}-{slug}",
  "milestone_branch_template": "gpd/{milestone}-{slug}"
},
"workflow": {
  "verify_between_waves": "auto",
  "verifier": true,
  "plan_checker": true
},
"physics": {
  "default_precision": "double",
  "unit_system": "natural",
  "computational_backend": "numpy",
  "symbolic_backend": "sympy",
  "convergence_tolerance": 1e-8,
  "dimensional_analysis": true
}
```

| Option                          | Default                      | Description                                                                                    |
| ------------------------------- | ---------------------------- | ---------------------------------------------------------------------------------------------- |
| `commit_docs`                   | `true`                       | Whether to commit planning artifacts to git                                                    |
| `search_gitignored`             | `false`                      | Add `--no-ignore` to broad rg searches                                                         |
| `autonomy`                      | `"guided"`                   | Human-in-the-loop level: `"supervised"`, `"guided"`, `"autonomous"`, `"yolo"`                  |
| `research_mode`                 | `"balanced"`                 | Research strategy: `"explore"` (breadth), `"balanced"`, `"exploit"` (depth), `"adaptive"`       |
| `parallelization`               | `true`                       | Execute plans within a wave in parallel (`true`) or sequentially (`false`)                     |
| `model_profile`                 | `"review"`                   | Research profile: `"deep-theory"`, `"numerical"`, `"exploratory"`, `"review"`, `"paper-writing"` |
| `git.branching_strategy`        | `"none"`                     | Git branching approach: `"none"`, `"phase"`, or `"milestone"`                                  |
| `git.phase_branch_template`     | `"gpd/phase-{phase}-{slug}"` | Branch template for phase strategy                                                             |
| `git.milestone_branch_template` | `"gpd/{milestone}-{slug}"`   | Branch template for milestone strategy                                                         |
| `physics.default_precision`     | `"double"`                   | Floating-point precision: `"single"`, `"double"`, `"quad"`, `"arbitrary"`                      |
| `physics.unit_system`           | `"natural"`                  | Unit convention: `"natural"` (hbar=c=1), `"SI"`, `"CGS"`, `"Gaussian"`, `"Planck"`, `"atomic"` |
| `physics.computational_backend` | `"numpy"`                    | Numerical backend: `"numpy"`, `"jax"`, `"torch"`, `"scipy"`                                    |
| `physics.symbolic_backend`      | `"sympy"`                    | Symbolic algebra: `"sympy"`, `"sage"`, `"mathematica"`                                         |
| `physics.convergence_tolerance` | `1e-8`                       | Default convergence threshold for iterative methods                                            |
| `workflow.verify_between_waves` | `"auto"`                     | Inter-wave verification: `"auto"` (profile-dependent), `true` (always), `false` (never)        |
| `workflow.verifier`             | `true`                       | Enable end-of-phase verification                                                               |
| `workflow.plan_checker`         | `true`                       | Spawn plan checker agent during plan-phase to validate plans before execution                   |
| `physics.dimensional_analysis`  | `true`                       | Auto-check dimensional consistency in expressions                                              |

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

**Inter-wave verification (`workflow.verify_between_waves`):**

| Value    | Behavior                                                                                |
| -------- | --------------------------------------------------------------------------------------- |
| `"auto"` | Profile-dependent: enabled for `deep-theory`, disabled for `exploratory` and `numerical` |
| `true`   | Always run inter-wave verification gates                                                |
| `false`  | Never run inter-wave verification (fastest execution)                                   |

When enabled, after each wave completes and before the next wave starts, the orchestrator runs lightweight checks on the wave's SUMMARY.md outputs:

1. **Dimensional analysis** — verify dimensional consistency of key results reported in SUMMARY.md
2. **Convention consistency** — check that results use the same conventions locked in state.json

If either check fails, execution pauses with options to continue, rollback the wave, or stop.

**Profile defaults for `"auto"` mode:**

| Profile        | verify_between_waves |
| -------------- | -------------------- |
| `deep-theory`  | enabled              |
| `numerical`    | disabled             |
| `exploratory`  | disabled             |
| `review`       | enabled              |
| `paper-writing`| disabled             |

**Cost:** Each inter-wave gate adds ~2-5k tokens (one lightweight consistency-checker call per wave transition). For a 4-wave phase with deep-theory profile, this is ~10-15k tokens overhead — negligible compared to the cost of a sign error propagating through 3 subsequent waves.

</workflow_config_behavior>

<physics_config_behavior>

**Unit system behavior:**

| System     | Constants set to 1 | Typical use                    |
| ---------- | ------------------ | ------------------------------ |
| `natural`  | hbar, c, k_B       | High-energy physics, QFT       |
| `SI`       | (none)             | Engineering, experimental      |
| `CGS`      | (none)             | Astrophysics, older literature |
| `Gaussian` | (none)             | Classical electrodynamics      |
| `Planck`   | hbar, c, G, k_B    | Quantum gravity                |
| `atomic`   | hbar, m_e, e, k_e  | Atomic/molecular physics       |

The unit system affects:

- How expressions are written and checked
- Which constants appear explicitly vs are set to 1
- Dimensional analysis expectations
- Output formatting of numerical results

**Computational backend behavior:**

| Backend | Strengths                                    | When to use                             |
| ------- | -------------------------------------------- | --------------------------------------- |
| `numpy` | General-purpose, mature                      | Default for most calculations           |
| `jax`   | Auto-diff, GPU, JIT                          | Gradient-based optimization, ML-physics |
| `torch` | Auto-diff, GPU, ML ecosystem                 | Neural network potentials, ML workflows |
| `scipy` | ODE solvers, optimization, special functions | Differential equations, fitting         |

**Symbolic backend behavior:**

| Backend       | Strengths                            | When to use                                      |
| ------------- | ------------------------------------ | ------------------------------------------------ |
| `sympy`       | Pure Python, good integration        | Default, most symbolic work                      |
| `sage`        | Comprehensive math, number theory    | Advanced algebra, topology                       |
| `mathematica` | Widest coverage, best simplification | Complex symbolic manipulation (requires license) |

**Convergence tolerance:**

The `convergence_tolerance` value is used as the default for:

- Iterative eigenvalue solvers (e.g., Lanczos, Davidson)
- Self-consistent field loops
- Numerical integration adaptive schemes
- Root-finding algorithms
- Optimization convergence criteria

Individual phases can override this for specific calculations that need tighter or looser tolerance.

</physics_config_behavior>

<search_behavior>

**When `search_gitignored: false` (default):**

- Standard rg behavior (respects .gitignore)
- Direct path searches work: `rg "pattern" .gpd/` finds files
- Broad searches skip gitignored: `rg "pattern"` skips `.gpd/`

**When `search_gitignored: true`:**

- Add `--no-ignore` to broad rg searches that should include `.gpd/`
- Only needed when searching entire repo and expecting `.gpd/` matches

**Note:** Most GPD operations use direct file reads or explicit paths, which work regardless of gitignore status.

</search_behavior>

<setup_uncommitted_mode>

To use uncommitted mode:

1. **Set config:**

   ```json
   "planning": {
     "commit_docs": false,
     "search_gitignored": true
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

**When `git.branching_strategy: "phase"`:**

- `execute-phase` creates/switches to a branch before execution
- Branch name from `phase_branch_template` (e.g., `gpd/phase-03-hamiltonian-construction`)
- All plan commits go to that branch
- User merges branches manually after phase completion
- `complete-milestone` offers to merge all phase branches

**When `git.branching_strategy: "milestone"`:**

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
# For phase strategy
if [ "$BRANCHING_STRATEGY" = "phase" ]; then
  PHASE_SLUG=$(echo "$PHASE_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
  BRANCH_NAME=$(echo "$PHASE_BRANCH_TEMPLATE" | sed "s/{phase}/$PADDED_PHASE/g" | sed "s/{slug}/$PHASE_SLUG/g")
  git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
fi

# For milestone strategy
if [ "$BRANCHING_STRATEGY" = "milestone" ]; then
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
