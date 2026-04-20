<purpose>
Switch the research mode profile used by GPD agents. Controls agent behavior, emphasis, and model selection for different phases of physics research work.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="validate">
Validate argument:

```
if $ARGUMENTS.profile not in ["deep-theory", "numerical", "exploratory", "review", "paper-writing"]:
  Error: Invalid profile "$ARGUMENTS.profile"
  Valid profiles: deep-theory, numerical, exploratory, review, paper-writing
  EXIT
```

</step>

<step name="ensure_and_load_config">
Ensure config exists and load current state:

```bash
gpd config ensure-section
# Compatibility note for installer text checks:
# INIT=$(gpd --raw init progress --include state,config)
INIT=$(gpd --raw init progress --include state,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

This creates `GPD/config.json` with defaults if missing and loads current config.
</step>

<step name="update_config">
Read current config from init output or directly:

Update `model_profile` field:

```json
{
  "model_profile": "$ARGUMENTS.profile"
}
```

Write updated config back to `GPD/config.json`.
</step>

<step name="confirm">
Display confirmation with profile details for selected profile:

```
Profile set to: $ARGUMENTS.profile

Agents will now operate in this mode:

[Show profile details for selected profile]
```

**Profile definitions:**

**deep-theory**
Focus: Rigorous analytical derivations, formal proofs, exact results

| Agent                    | Tier   |
| ------------------------ | ------ |
| gpd-planner              | tier-1 |
| gpd-roadmapper           | tier-1 |
| gpd-executor             | tier-1 |
| gpd-phase-researcher     | tier-1 |
| gpd-project-researcher   | tier-1 |
| gpd-research-synthesizer | tier-1 |
| gpd-debugger             | tier-1 |
| gpd-verifier             | tier-1 |
| gpd-plan-checker         | tier-2 |
| gpd-consistency-checker  | tier-1 |
| gpd-paper-writer         | tier-1 |
| gpd-literature-reviewer  | tier-1 |
| gpd-bibliographer        | tier-2 |
| gpd-check-proof          | tier-1 |
| gpd-referee              | tier-1 |
| gpd-experiment-designer  | tier-2 |

Best for: Deriving new results, proving identities, establishing exact relations, formal perturbation theory, renormalization group calculations.

Behavioral highlights: Verification checkpoints after every derivation step. Planner inserts derivation checkpoint every 2 steps. Run the full relevant universal verifier registry plus any required contract-aware checks. All 16 plan dimensions checked. Paper-writer includes proofs in main text (not appendices). Full investigation debugging with formal proof of root cause. Pair with `execution.review_cadence=dense` when you want more bounded review stops, but `set-profile` does not change cadence automatically.

**numerical**
Focus: Computational implementation, optimization, convergence, performance

| Agent                    | Tier   |
| ------------------------ | ------ |
| gpd-planner              | tier-1 |
| gpd-executor             | tier-2 |
| gpd-phase-researcher     | tier-1 |
| gpd-debugger             | tier-1 |
| gpd-verifier             | tier-1 |
| gpd-plan-checker         | tier-2 |
| gpd-experiment-designer  | tier-1 |

Best for: Implementing solvers, running simulations, optimizing code, convergence studies, parallelization, data pipeline construction.

Behavioral highlights: Convergence testing task added to every numerical computation. Grid/basis/timestep refinement required before results accepted. Richardson extrapolation automatic. Plan-checker emphasizes numerical stability and error budgets. `execution.review_cadence` stays independent; `adaptive` is usually the right default unless you explicitly want denser review gates.

**exploratory**
Focus: Rapid prototyping, hypothesis testing, parameter space exploration

| Agent                    | Tier   |
| ------------------------ | ------ |
| gpd-planner              | tier-1 |
| gpd-executor             | tier-2 |
| gpd-phase-researcher     | tier-1 |
| gpd-debugger             | tier-2 |
| gpd-verifier             | tier-2 |
| gpd-plan-checker         | tier-2 |

Best for: Early-stage investigation, scanning parameter spaces, testing new ideas, order-of-magnitude estimates, dimensional analysis, building intuition.

Behavioral highlights: 3-4 tasks per plan, larger tasks (up to 90 min), only final results verified (skips intermediate checkpoints). Plan-checker reduced to 9 core dimensions. Quick-triage debugging (max 2 rounds). Verifier runs only dimensional analysis + limiting cases + spot-checks + plausibility. Use `execution.review_cadence=sparse` or `adaptive` if you want fewer bounded review stops, but required correctness gates still remain.

**review** (default)
Focus: Critical assessment, error checking, literature comparison

| Agent                    | Tier   |
| ------------------------ | ------ |
| gpd-planner              | tier-1 |
| gpd-executor             | tier-2 |
| gpd-phase-researcher     | tier-2 |
| gpd-debugger             | tier-1 |
| gpd-verifier             | tier-1 |
| gpd-plan-checker         | tier-1 |
| gpd-consistency-checker  | tier-1 |
| gpd-check-proof          | tier-1 |
| gpd-referee              | tier-1 |

Best for: Pre-submission review, debugging wrong results, resolving discrepancies, preparing referee responses, validating collaborator work.

Behavioral highlights: Exhaustive debugging documentation. All verifier checks run plus cross-validation against 2+ literature values. Plan-checker runs all 16 dimensions plus testability checks. Every step cross-references the literature source it implements. This profile often benefits from `execution.review_cadence=dense`, but cadence remains a separate setting.

**paper-writing**
Focus: Clear exposition, LaTeX production, figure generation, narrative flow

| Agent                    | Tier   |
| ------------------------ | ------ |
| gpd-planner              | tier-1 |
| gpd-executor             | tier-1 |
| gpd-phase-researcher     | tier-2 |
| gpd-verifier             | tier-2 |
| gpd-paper-writer         | tier-1 |
| gpd-research-synthesizer | tier-1 |
| gpd-bibliographer        | tier-1 |
| gpd-check-proof          | tier-1 |
| gpd-referee              | tier-1 |

Best for: Writing manuscripts, preparing talks, generating figures, formatting for journal submission, writing supplementary material.

Behavioral highlights: Plans organized by paper sections with tasks mapped to figures, tables, and equations. Narrative-focused execution with clean intermediate expressions. Publication-readiness verification (figures match data, notation consistent, all symbols defined). All 16 plan dimensions checked with emphasis on publication readiness. Full BibTeX formatting against target journal style. Rapid first drafts with multiple revision passes. `execution.review_cadence=adaptive` or `sparse` usually fits, but cadence is not profile-owned.

---

**Review cadence interaction:**

`set-profile` changes abstract tier assignments and behavior depth. It does NOT rewrite `execution.review_cadence`.

- `dense`: more bounded review stops during execution
- `adaptive` (default): inject first-result and risky-fanout gates while letting clean segments continue
- `sparse`: fewest bounded review stops beyond the required correctness gates

Change cadence with `gpd:settings` or by editing `GPD/config.json` (`execution.review_cadence`: `"dense"` / `"adaptive"` / `"sparse"`).

If you also want to pin concrete runtime model strings for `tier-1`, `tier-2`, or `tier-3`, use `gpd:set-tier-models` for the direct path or `gpd:settings` for the broader unattended/configuration flow. `set-profile` changes the abstract tier assignments, not the runtime-native model IDs.

For full agent tier assignments across all 25 agents, see `references/orchestration/model-profiles.md`.
For detailed behavioral effect descriptions per agent per profile, see the "Behavioral Effects" section in `references/orchestration/model-profiles.md`.

Next spawned agents will use the new profile.

```
</step>

</process>

<success_criteria>
- [ ] Argument validated against five physics research profiles
- [ ] Config file ensured
- [ ] Config updated with new model_profile
- [ ] Confirmation displayed with profile details including model assignments and behavioral emphasis
</success_criteria>
