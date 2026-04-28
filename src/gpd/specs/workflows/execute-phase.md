<purpose>
Execute all plans in a research phase using wave-based parallel execution. Orchestrator stays lean -- delegates plan execution to subagents. Each plan may involve derivations, calculations, simulations, or analysis with proper checkpointing and validation at each step.
</purpose>

<core_principle>
Orchestrator coordinates, not executes. Each subagent loads the full execute-plan context. Orchestrator: discover plans -> analyze deps -> group waves -> spawn agents -> handle checkpoints -> collect results -> validate physics.
</core_principle>

<required_reading>
Load the structured init-state payload first; reopen STATE.md only if a later staged refresh is missing, stale, or flagged by `state_load_source` / `state_integrity_issues`.
For agent selection strategy and verification failure routing, see `{GPD_INSTALL_DIR}/references/orchestration/meta-orchestration.md`.
For artifact class definitions and review priority rules, see `{GPD_INSTALL_DIR}/references/orchestration/artifact-surfacing.md`.
</required_reading>

<process>

<step name="normalize_arguments" priority="first">
Normalize phase and flags before any init call. The first non-flag positional token is the phase; flags may appear before or after it.

```bash
PHASE_ARG=""
EXECUTE_FLAGS=()
for token in $ARGUMENTS; do
  case "$token" in
    --*) EXECUTE_FLAGS+=("$token") ;;
    *) [ -z "$PHASE_ARG" ] && PHASE_ARG="$token" ;;
  esac
done
GAPS_ONLY=false
for flag in "${EXECUTE_FLAGS[@]}"; do
  [ "$flag" = "--gaps-only" ] && GAPS_ONLY=true
done

if [ -z "$PHASE_ARG" ]; then
  echo "ERROR: missing phase. Usage: gpd:execute-phase <phase-number> [--gaps-only]"
  exit 1
fi
```
</step>

<step name="initialize" priority="first">
Load the bootstrap stage first. Keep later wave and closeout context on demand.

```bash
load_execute_phase_stage() {
  local stage_name="$1"
  local init_payload=""
  local init_stderr=""
  local init_status=0

  if [ -n "$stage_name" ]; then
    init_stderr=$(mktemp)
    init_payload=$(gpd --raw init execute-phase "${PHASE_ARG}" --stage "${stage_name}" 2>"$init_stderr")
    init_status=$?
    if [ "$init_status" -ne 0 ] || [ -z "$init_payload" ]; then
      echo "ERROR: staged gpd initialization failed for stage '${stage_name}' (exit ${init_status})."
      [ -n "$init_payload" ] && echo "stdout: ${init_payload}"
      [ -s "$init_stderr" ] && echo "stderr: $(cat "$init_stderr")"
      rm -f "$init_stderr"
      return 1
    fi
    rm -f "$init_stderr"

    printf '%s' "$init_payload"
    return 0
  fi

  gpd --raw init execute-phase "${PHASE_ARG}"
}

BOOTSTRAP_INIT=$(load_execute_phase_stage phase_bootstrap)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $BOOTSTRAP_INIT"
  exit 1
fi
```

Parse JSON for: `executor_model`, `verifier_model`, `commit_docs`, `autonomy`, `review_cadence`, `research_mode`, `parallelization`, `max_unattended_minutes_per_plan`, `max_unattended_minutes_per_wave`, `checkpoint_after_n_tasks`, `checkpoint_after_first_load_bearing_result`, `checkpoint_before_downstream_dependent_tasks`, `verifier_enabled`, `branching_strategy`, `branch_name`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `phase_slug`, `plans`, `incomplete_plans`, `plan_count`, `incomplete_count`, `state_exists`, `roadmap_exists`, `project_contract`, `project_contract_gate`, `project_contract_validation`, `project_contract_load_info`, `platform`.

**If `phase_found` is false:** Error -- phase directory not found.
**If `plan_count` is 0:** Error -- no plans found in phase.
**If `state_exists` is false but `GPD/` exists:** Offer reconstruct or continue.

If `project_contract_load_info.status` starts with `blocked`, STOP and show the concrete `project_contract_load_info.errors` / `warnings` before execution. A contract that could not be loaded cleanly is not safe to execute from.

If `project_contract_validation.valid` is false, STOP and show the explicit `project_contract_validation.errors` before execution. Do not treat a visible-but-blocked contract as an approved execution contract.

Treat `project_contract` as the authoritative machine-readable execution contract only when `project_contract_gate.authoritative` is true.
Later staged refreshes surface `effective_reference_intake`, `active_reference_context`, and `reference_artifacts_content` for anchor-aware routing and wave planning. Stable knowledge docs may appear only through those shared reference surfaces as reviewed background; they do not become a separate authority tier. Do not assume bootstrap already loaded that broader reference context.
Before launching any plan, require that the selected `PLAN.md` passes `gpd validate plan-preflight <PLAN.md>` when specialized tool requirements are declared.

When `parallelization` is false, plans within a wave execute sequentially.

**Mode-aware behavior:**
- `autonomy` controls who gets interrupted at a wave boundary.
- `research_mode` only adjusts depth and optional tangents; it does not relax required gates.
- `research_mode=balanced` (default): Use the standard execution depth and keep the default contract, anchor, and review coverage unless the wave needs broader or narrower review.
- `review_cadence` controls bounded phase pauses.
- `execute-plan.md owns plan-local execution semantics; this workflow only owns phase-wide routing and wave risk.`
- Even in `yolo`, do NOT skip required correctness gates, first-result sanity checks, skeptical review stops, or anchor-gated fanout reviews. A clean pass may auto-continue only after the gate is explicitly cleared.
- `research_mode=adaptive`: Start with explore-style coverage, then narrow only after prior decisive `contract_results`, decisive `comparison_verdicts`, or an explicit approach lock show that the method family is stable. Do NOT narrow just because a wave advanced or one proxy passed.
- Model profile may change depth, task granularity, or prose volume, but it does not waive required gates.
- `review_cadence` is read here only to schedule phase pauses; detailed gate ownership remains in `execute-plan.md`.
- `workflow.verifier=false`, sparse cadence, yolo autonomy, or any manual "skip verification" request do NOT disable mandatory proof red-teaming for proof-bearing or `proof_obligation` work.
</step>

<step name="handle_branching">
Check `branching_strategy` from init:

**"none":** Skip, continue on current branch.

**"per-phase" or "per-milestone":** Use pre-computed `branch_name` from init:

```bash
git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
```

All subsequent commits go to this branch. User handles merging.
</step>

<step name="classify_phase">
Classify the phase type to drive agent selection and context budget decisions. Scan the phase goal and plan objectives for indicator keywords.

```bash
PHASE_CLASSIFICATION_INIT=$(load_execute_phase_stage phase_classification) || { echo "ERROR: phase_classification init failed"; exit 1; }
PHASE_GOAL=$(gpd --raw roadmap get-phase "${phase_number}" | gpd json get .goal --default "")
PLAN_OBJECTIVES=""
for plan in "$phase_dir"/*-PLAN.md; do
  OBJ=$(gpd frontmatter get "$plan" --field objective 2>/dev/null)
  PLAN_OBJECTIVES="${PLAN_OBJECTIVES} ${OBJ}"
done
PHASE_TEXT="${PHASE_GOAL} ${PLAN_OBJECTIVES}"
```

Classify using keyword matching (a phase may have multiple classes):

```bash
PHASE_CLASSES=()
echo "$PHASE_TEXT" | grep -qiE "derive|prove|show that|analytical|closed.form|exact result" && PHASE_CLASSES+=("derivation")
echo "$PHASE_TEXT" | grep -qiE "simulat|compute|discretiz|grid|convergence|benchmark|finite.element|Monte Carlo|numerical" && PHASE_CLASSES+=("numerical")
echo "$PHASE_TEXT" | grep -qiE "survey|review|compare approaches|what is known|prior work|literature" && PHASE_CLASSES+=("literature")
echo "$PHASE_TEXT" | grep -qiE "write paper|draft|manuscript|submit|LaTeX" && PHASE_CLASSES+=("paper-writing")
echo "$PHASE_TEXT" | grep -qiE "define|set up framework|establish conventions|Lagrangian|Hamiltonian|action" && PHASE_CLASSES+=("formalism")
echo "$PHASE_TEXT" | grep -qiE "analyz|compare|interpret|extract|fit|scaling" && PHASE_CLASSES+=("analysis")
echo "$PHASE_TEXT" | grep -qiE "verify|cross.check|reproduce|validate|test against" && PHASE_CLASSES+=("validation")
[ ${#PHASE_CLASSES[@]} -eq 0 ] && PHASE_CLASSES+=("mixed")
```

Log the classification: `"Phase ${phase_number} classified as: ${PHASE_CLASSES[*]}"`

**Use classification for:**
- Agent selection (see `agent-infrastructure.md` Meta-Orchestration Intelligence > Agent Selection by Phase Type)
- Context budget targets (see `agent-infrastructure.md` Meta-Orchestration Intelligence > Context Budget Allocation)
- Verifier check prioritization (derivation phases promote dimensional / limit / identity-critical checks; numerical phases promote `5.5` convergence and `5.14` statistics; validation phases run the full relevant registry)
- Computation-type-aware execution adaptation (see `adapt_to_computation_type` below)
</step>

<step name="adapt_to_computation_type">
Translate the phase classification into concrete execution parameters that drive wave-loop behavior. Set these variables before entering `execute_waves`:

```bash
# Defaults
CONVENTION_LOCK_REQUIRED=false
PRE_EXECUTION_SPECIALISTS=()
INTER_WAVE_CHECKS=("convention" "dimensional")
EXECUTOR_CONTEXT_HINT="standard"
WAVE_TIMEOUT_FACTOR=1.0
FORCE_SEQUENTIAL=false
YOLO_RESTRICTIONS=()
```

**Per-class overrides:** Apply the case block below cumulatively for multi-class phases. It is the executable source of truth for convention locks, specialist routing, inter-wave checks, executor context hints, timeout factors, sequential forcing, and yolo restrictions.

**Apply overrides:**

```bash
for CLASS in "${PHASE_CLASSES[@]}"; do
  case "$CLASS" in
    derivation)
      CONVENTION_LOCK_REQUIRED=true
      INTER_WAVE_CHECKS+=("identity_scan")
      EXECUTOR_CONTEXT_HINT="derivation-heavy"
      WAVE_TIMEOUT_FACTOR=1.5
      YOLO_RESTRICTIONS+=("no_skip_verification")
      ;;
    numerical)
      INTER_WAVE_CHECKS+=("convergence_spot_check")
      EXECUTOR_CONTEXT_HINT="code-heavy"
      PRE_EXECUTION_SPECIALISTS+=("experiment-designer")  # gpd-experiment-designer
      ;;
    literature)
      FORCE_SEQUENTIAL=true
      EXECUTOR_CONTEXT_HINT="reading-heavy"
      INTER_WAVE_CHECKS=("convention")
      ;;
    paper-writing)
      PRE_EXECUTION_SPECIALISTS+=("notation-coordinator")
      INTER_WAVE_CHECKS+=("latex_compile")
      EXECUTOR_CONTEXT_HINT="prose-heavy"
      ;;
    formalism)
      CONVENTION_LOCK_REQUIRED=true
      PRE_EXECUTION_SPECIALISTS+=("notation-coordinator")
      INTER_WAVE_CHECKS+=("identity_scan")
      ;;
    analysis)
      INTER_WAVE_CHECKS+=("plausibility_scan")
      ;;
    validation)
      YOLO_RESTRICTIONS+=("no_skip_verification" "no_skip_inter_wave")
      INTER_WAVE_CHECKS+=("identity_scan" "convergence_spot_check" "plausibility_scan")
      ;;
  esac
done

echo "Execution adaptation: convention_lock=${CONVENTION_LOCK_REQUIRED}, pre_specialists=[${PRE_EXECUTION_SPECIALISTS[*]}], inter_wave=[${INTER_WAVE_CHECKS[*]}], context_hint=${EXECUTOR_CONTEXT_HINT}, timeout_factor=${WAVE_TIMEOUT_FACTOR}"
```

**Convention lock enforcement:**

If `CONVENTION_LOCK_REQUIRED=true`:

```bash
CONV_STATUS=$(gpd --raw convention check)
if [ "$CONV_STATUS" != "locked" ] && [ "$CONV_STATUS" != "complete" ]; then
  echo "ERROR: Phase class (${PHASE_CLASSES[*]}) requires locked conventions before execution."
  echo "Convention status: ${CONV_STATUS}"
  echo ""
  echo "Fix with one of:"
  echo "  gpd convention set"
  echo "  gpd:validate-conventions"
  echo ""
  echo "HALTING — convention errors in derivation/formalism phases compound across every step."
  exit 1
fi
```

**This is a hard gate.** When `CONVENTION_LOCK_REQUIRED=true` and conventions are not locked, execution MUST NOT proceed. Do not skip this gate in any autonomy mode (including yolo). Convention errors are irreversible — they invalidate all downstream results.

**Pre-execution specialist routing:**

The dedicated `pre_execution_specialists` stage consumes `PRE_EXECUTION_SPECIALISTS` and loads the delegation guidance for any real one-shot handoff. This workflow only decides which specialist types are needed; it does not inline placeholder `task(...)` calls or wait for interactive continuation inside the same run.

**Force-sequential override:**

If `FORCE_SEQUENTIAL=true`, override `PARALLELIZATION` to false for this phase regardless of config setting. Log: `"Phase class (${PHASE_CLASSES[*]}) forces sequential execution within waves."`

**YOLO mode restrictions:**

If `autonomy=yolo` and `YOLO_RESTRICTIONS` is non-empty, restrict yolo behavior:

- `no_skip_verification`: Do not skip the verification step even in yolo mode. Derivation and validation phases produce irreversible errors that cost more to debug than to verify.
- `no_skip_inter_wave`: Do not skip inter-wave gates even in yolo mode. Convention drift between waves in these phase types creates compound errors.

Log any restrictions: `"YOLO mode restricted for phase class (${PHASE_CLASSES[*]}): ${YOLO_RESTRICTIONS[*]}"`

**Context hint propagation:**

Include `EXECUTOR_CONTEXT_HINT` in the executor spawn prompt so subagents can self-regulate:

```
<context_hint>{EXECUTOR_CONTEXT_HINT}</context_hint>
```

Hint meanings:
- `standard`: Default allocation — balanced between derivation, code, and prose.
- `derivation-heavy`: Reserve 70% of context for step-by-step mathematical work. Minimize prose. Use `\therefore` not paragraphs.
- `code-heavy`: Reserve space for code blocks, numerical output tables, and convergence plots. Summarize analytical steps briefly.
- `reading-heavy`: Reserve space for literature citations and comparisons. Budget for reading 5-10 paper summaries.
- `prose-heavy`: Balance equations with exposition. Every equation needs 2-3 sentences of context.
</step>

<step name="validate_phase">
From init JSON: `phase_dir`, `plan_count`, `incomplete_count`.

Report: "Found {plan_count} plans in {phase_dir} ({incomplete_count} incomplete)"
</step>

<step name="detect_proof_obligation_work">
Classify whether any selected plan is proof-bearing before execution and before honoring verifier-disabled or sparse-review settings.

@{GPD_INSTALL_DIR}/references/verification/core/proof-redteam-workflow-gate.md

For each proof-bearing plan, require a sibling `{plan_id}-PROOF-REDTEAM.md` artifact that follows the shared gate above.

Never treat a clean `SUMMARY.md`, correct algebra in a subset of cases, or "human will inspect later" as a substitute for this artifact.
When runtime delegation is available, `gpd-check-proof` is the canonical owner of this sibling artifact. The executor may draft the proof and theorem inventory, but it must not self-certify theorem-proof alignment as its own independent redteam.
</step>

<step name="refresh_wave_planning_context">
Refresh the wave-planning stage so the orchestrator does not keep late execution context pinned in bootstrap state:

```bash
WAVE_PLANNING_INIT=$(load_execute_phase_stage wave_planning)
if [ $? -ne 0 ]; then
  echo "ERROR: wave-planning stage refresh failed: $WAVE_PLANNING_INIT"
  exit 1
fi
```

Parse JSON for: `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`, `reference_artifacts_content`, `intermediate_results`, `intermediate_result_count`, `approximations`, `approximation_count`, `propagated_uncertainties`, `propagated_uncertainty_count`, `derived_convention_lock`, `derived_convention_lock_count`, `derived_intermediate_results`, `derived_intermediate_result_count`, `derived_approximations`, `derived_approximation_count`.
</step>

<step name="structural_validation">
Run structural validation on all plans before execution begins:

```bash
VALIDATION_FAILED=false

# Validate each plan's frontmatter and structure
for plan in "$phase_dir"/*-PLAN.md; do
  if ! gpd verify plan "$plan"; then
    echo "ERROR: plan-structure validation failed for $(basename "$plan")"
    VALIDATION_FAILED=true
  fi
done

# Validate wave dependencies
if ! gpd phase validate-waves "$phase_number"; then
  echo "ERROR: wave dependency validation failed"
  VALIDATION_FAILED=true
fi

# Check cross-references in plans
for plan in "$phase_dir"/*-PLAN.md; do
  if ! gpd verify references "$plan"; then
    echo "ERROR: reference validation failed for $(basename "$plan")"
    VALIDATION_FAILED=true
  fi
done

if [ "$VALIDATION_FAILED" = true ]; then
  echo "Structural validation failed. Fix the issues above before proceeding."
fi
```

**If `VALIDATION_FAILED` is true:** Present all collected errors to the user. Do not proceed with execution until structural issues are resolved.
</step>

<step name="claim_deliverable_alignment_check">
Gate execution on explicit confirmation that the machine-readable claim matches user intent for Phase {N}.

Read the persisted alignment status and the current contract/context fingerprints before rendering anything:

```bash
ALIGNMENT_STATUS=$(gpd contract alignment-status 2>/dev/null || echo '{}')
CONTRACT_HASH=$(gpd contract fingerprint 2>/dev/null)
CONTEXT_HASH=$(gpd contract context-fingerprint 2>/dev/null)
CONFIRMED_AT=$(echo "$ALIGNMENT_STATUS" | gpd json get .confirmed_at --default null)
CONFIRMED_CONTRACT_HASH=$(echo "$ALIGNMENT_STATUS" | gpd json get .confirmed_contract_hash --default null)
CONFIRMED_CONTEXT_HASH=$(echo "$ALIGNMENT_STATUS" | gpd json get .confirmed_context_hash --default null)
```

**Fingerprint gate:** Fail closed if either fingerprint command fails or resolves to an empty value before rendering the prompt or recording confirmation. Do not compare blank hashes, do not suppress the gate, and do not call `gpd contract record-alignment` on this path.

```bash
if [ -z "$CONTRACT_HASH" ] || [ -z "$CONTEXT_HASH" ]; then
  echo "ERROR: claim_deliverable_alignment_check could not resolve contract/context fingerprints."
  echo "Next Up: gpd:execute-phase {N}"
  exit 1
fi
```

**Gating:** This step fires when `autonomy=supervised` OR `review_cadence=dense` OR any selected plan is proof-bearing per `detect_proof_obligation_work`. It is skipped under `autonomy=yolo AND review_cadence in {adaptive, sparse} AND no proof-bearing plans`. When skipping for this reason, log the decision explicitly — for example `claim_deliverable_alignment_check: skipped (autonomy=yolo, cadence=adaptive, no proof-bearing plans)` — and continue to `discover_and_group_plans` without prompting.

**Suppression:** If the persisted `confirmed_at` is set AND the current `contract_fingerprint == confirmed_contract_hash` AND the current `context_guidance_fingerprint == confirmed_context_hash`, skip re-prompting and log `claim_deliverable_alignment_check: skipped (already confirmed this session)`. Read the persisted status via `gpd contract alignment-status`; the hash-equality check uses `CONTRACT_HASH`/`CONTEXT_HASH` computed above.

**Render:** When the step fires and is not suppressed, render a one-screen side-by-side table titled `Claim ↔ Deliverable Alignment` with the following layout. The left column is sourced from user intent (CONTEXT.md + structured `ContractContextIntake` fields); the right column is sourced from the machine contract. Cap each column at 5 bullets, truncating with an ellipsis (`…`) when more entries exist. Use `gpd contract alignment-summary` to obtain the right-column rows.

```
| User intent (CONTEXT)               | Machine contract                    |
|-------------------------------------|-------------------------------------|
| Observables: ...                    | Claims: ...                         |
| Deliverables: ...                   | Deliverables: ...                   |
| Must-have references: ...           | Acceptance tests: ...               |
| Stop-or-rethink conditions: ...     |                                     |
```

Left-column rows MUST be: `Observables`, `Deliverables`, `Must-have references`, `Stop-or-rethink conditions`. Right-column rows MUST be: `Claims`, `Deliverables`, `Acceptance tests`. Each cell lists ≤5 bullets; when truncated, append `…` as the final bullet.

**ask_user:** Present exactly one question with 4 options. Enter selects `Y`. Match the batched shape used elsewhere in the specs.

```
ask_user([
  {
    question: "Does the machine contract above match your intent for Phase {N}? Press Enter to proceed, or pick an option to revise.",
    header: "Claim ↔ Deliverable Alignment",
    multiSelect: false,
    options: [
      { label: "Y: proceed (Recommended, Enter = Y)", description: "Claims, deliverables, and acceptance tests match user intent. Record the confirmation and continue to discover_and_group_plans." },
      { label: "e: edit CONTEXT", description: "User intent is off. Hand off to gpd:discuss-phase {N} to revise CONTEXT.md, then re-enter this step once." },
      { label: "p: edit PLAN contract", description: "The machine contract is off. Hand off to gpd:plan-phase {N} --revise to revise the contract, then re-enter this step once." },
      { label: "n: abort", description: "Stop execution cleanly without spawning any executor. Next Up is gpd:execute-phase {N} once alignment is resolved." }
    ]
  }
])
```

**On "Y: proceed" (or Enter):** Record the confirmation so the same session does not re-prompt while the contract and CONTEXT are unchanged, then continue to `discover_and_group_plans`:

```bash
gpd contract record-alignment --contract-hash "$CONTRACT_HASH" --context-hash "$CONTEXT_HASH"
```

**On "n: abort":** Exit cleanly. Do NOT spawn any executor and do NOT proceed to `discover_and_group_plans`. Emit a final line `"Next Up: gpd:execute-phase {N}"` so the operator can resume after resolving alignment.

**On "e" (edit CONTEXT) / "p" (edit PLAN contract):** Hand off to the corresponding workflow — `gpd:discuss-phase {N}` for `e`, `gpd:plan-phase {N} --revise` for `p`. After it returns, re-enter this step exactly once to re-render the side-by-side against the revised inputs. If the same key is chosen a second time in one invocation, defer to that workflow and stop looping — do not re-enter a third time.
</step>

<step name="discover_and_group_plans">
Load plan inventory with wave grouping in one call:

```bash
PLAN_INDEX=$(gpd phase index "${phase_number}")
```

Parse JSON for: `phase`, `plans[]` (each with `id`, `wave`, `interactive`, `gap_closure`, `objective`, `files_modified`, `task_count`, `has_summary`), `waves` (map of wave number -> plan IDs), `incomplete`, `has_checkpoints`.

**Filtering:** Skip plans where `has_summary: true`. If `$GAPS_ONLY` is true, also skip non-gap_closure plans. If all filtered: "No matching incomplete plans" -> exit.

**Intra-wave dependency validation:** Verify that no plan's `depends_on` references another plan in the SAME wave (which would be a circular dependency within a wave):

```bash
INTRA_WAVE_CONFLICT=false
# For each wave, check that no plan depends on another plan in the same wave
for WAVE_NUM in $(echo "$PLAN_INDEX" | gpd json keys .waves); do
  WAVE_PLANS=$(echo "$PLAN_INDEX" | gpd json list ".waves[\"$WAVE_NUM\"]")
  for PLAN_ID in $WAVE_PLANS; do
    DEPS=$(gpd frontmatter get \
      "${phase_dir}/${PLAN_ID}-PLAN.md" --field depends_on 2>/dev/null)
    for DEP in $(echo "$DEPS" | tr ',' ' '); do
      if echo "$WAVE_PLANS" | grep -q "^${DEP}$"; then
        echo "ERROR: Plan ${PLAN_ID} depends on ${DEP}, but both are in wave ${WAVE_NUM}"
        INTRA_WAVE_CONFLICT=true
      fi
    done
  done
done
```

**Parallel file conflict detection:** For waves with 2+ plans, check `files_modified` frontmatter for overlaps:

```bash
FILE_CONFLICT=false
# For each wave with 2+ plans, check for file modification overlaps
for WAVE_NUM in $(echo "$PLAN_INDEX" | gpd json keys .waves); do
  WAVE_PLANS=($(echo "$PLAN_INDEX" | gpd json list ".waves[\"$WAVE_NUM\"]"))
  if [ ${#WAVE_PLANS[@]} -gt 1 ]; then
    ALL_FILES=()
    for PLAN_ID in "${WAVE_PLANS[@]}"; do
      FILES=$(gpd frontmatter get \
        "${phase_dir}/${PLAN_ID}-PLAN.md" --field files_modified 2>/dev/null)
      for F in $(echo "$FILES" | tr ',' ' '); do
        if [[ " ${ALL_FILES[*]} " =~ " ${F} " ]]; then
          echo "WARNING: File '${F}' modified by multiple plans in wave ${WAVE_NUM}"
          FILE_CONFLICT=true
        fi
        ALL_FILES+=("${F}")
      done
    done
  fi
done
```

If `INTRA_WAVE_CONFLICT` is true: STOP — present the dependency issue and do not proceed.
If `FILE_CONFLICT` is true: WARN — present the overlap and offer to serialize the conflicting plans within the wave.

Report:

```
## Execution Plan

**Phase {X}: {Name}** -- {total_plans} plans across {wave_count} waves

| Wave | Plans | What it builds |
|------|-------|----------------|
| 1 | 01-01, 01-02 | {from plan objectives, 3-8 words} |
| 2 | 01-03 | ... |
```

</step>

<step name="resolve_execution_cadence">
Translate cadence config plus wave risk into concrete execution boundaries before any executor is spawned.

```bash
REVIEW_CADENCE=$(echo "$INIT" | gpd json get .review_cadence --default dense)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
MAX_UNATTENDED_MINUTES_PER_PLAN=$(echo "$INIT" | gpd json get .max_unattended_minutes_per_plan --default 45)
MAX_UNATTENDED_MINUTES_PER_WAVE=$(echo "$INIT" | gpd json get .max_unattended_minutes_per_wave --default 90)
CHECKPOINT_AFTER_N_TASKS=$(echo "$INIT" | gpd json get .checkpoint_after_n_tasks --default 3)
CHECKPOINT_AFTER_FIRST_RESULT=$(echo "$INIT" | gpd json get .checkpoint_after_first_load_bearing_result --default true)
CHECKPOINT_BEFORE_DOWNSTREAM=$(echo "$INIT" | gpd json get .checkpoint_before_downstream_dependent_tasks --default true)
STRICT_WAIT=$(gpd --raw config get strict_wait 2>/dev/null || echo false)
NEVER_INTERRUPT_WORKERS=$(gpd --raw config get never_interrupt_running_workers 2>/dev/null || echo false)
NEVER_AUTO_CLOSE_CHILDREN=$(gpd --raw config get never_auto_close_child_agents 2>/dev/null || echo false)

# strict_wait disables the unattended-minutes timeouts entirely: workers are
# allowed to run to natural completion rather than returning early checkpoints
# at the 45 / 90 minute marks. never_interrupt_running_workers is a narrower
# form of the same guarantee.
if [ "$STRICT_WAIT" = "true" ] || [ "$NEVER_INTERRUPT_WORKERS" = "true" ]; then
  MAX_UNATTENDED_MINUTES_PER_PLAN=0
  MAX_UNATTENDED_MINUTES_PER_WAVE=0
fi
```

**Core invariant:** `autonomy` decides who gets interrupted. `review_cadence` decides when the system must stop, inspect, or re-question. Even in `yolo`, required first-result and pre-fanout gates still run; the difference is that a clean pass can auto-continue.

These gates are task-level safety rails, not line-by-line interruptions. Even in `supervised`, checkpoint after each plan task or required gate, not after every algebraic micro-step.

For each wave, classify whether downstream fanout is risky:

- risky when a wave has multiple plans and any later wave depends on it
- risky when any plan has `task_count >= CHECKPOINT_AFTER_N_TASKS`, no authored checkpoints, or is likely to exceed `MAX_UNATTENDED_MINUTES_PER_PLAN`
- risky for `derivation`, `formalism`, `numerical`, or `validation` phase classes
- risky when file conflicts, convention-lock requirements, or benchmark-critical anchors are present
- risky when the wave creates a new estimator, baseline, or branch point whose downstream usefulness depends on a decisive comparison still to be earned
- never mark a wave "safe" merely because it happens later in the phase or follows an earlier partial pass

When a wave is risky:

- set `FIRST_RESULT_GATE_REQUIRED=true`
- set `PRE_FANOUT_REVIEW_REQUIRED=true`
- set `SEGMENT_TASK_CAP=${CHECKPOINT_AFTER_N_TASKS}`
- force bounded continuation segments even when the authored plan has no checkpoints

**Dense cadence override:** when `review_cadence=dense`, treat every wave as risky regardless of the heuristic checks above, applying the "When a wave is risky" bullets unconditionally (in particular `FIRST_RESULT_GATE_REQUIRED=true` and `PRE_FANOUT_REVIEW_REQUIRED=true`). The "not risky" branch does not apply; a clean pass may auto-continue once the gate fires, but the gate must fire.

When a wave is not risky:

- keep bounded execution available for long plans, wall-clock budgets, and context pressure
- allow checkpoint-free plans to run normally when task count is small and fanout is low

**Skeptical re-questioning rule:** if the first material result only validates a proxy, internal consistency story, or supporting artifact while decisive anchors, benchmark references, or contract-backed acceptance tests remain unresolved, stop and explicitly re-question the framing before allowing downstream fanout. Record:

- weakest unchecked anchor
- what still looks assumed rather than verified
- the disconfirming observation that would most quickly break the current path
- which downstream plans would become wasted work if that decisive evidence failed

**Proposal-first tangent control:** if an unexpected but non-blocking alternative path appears during execution, do not silently pursue it. Treat it as a tangent proposal and classify it using exactly one of these four decisions at the existing review stop:

- `ignore` — not a real tangent; continue the approved mainline plan
- `defer` — record it briefly in the wave report / SUMMARY as future follow-up, then continue the mainline plan
- `branch_later` — recommend `gpd:tangent ...` or `gpd:branch-hypothesis ...` for explicit follow-up, but do not create new side work during this execution pass
- `pursue_now` — only when the user explicitly requested tangent exploration or the approved contract already includes that alternative path

This is proposal-first, not a new execution state machine. Tangent proposals ride on the existing first-result / skeptical / pre-fanout review stops.

When `RESEARCH_MODE=exploit`, suppress optional tangents by default: classify them as `ignore` or `defer` unless the prompt or the user explicitly asked for tangent exploration.
</step>

<step name="prepare_pre_execution_specialists">
Load the specialist-routing stage only when a pre-wave specialist is actually needed.

```bash
if [ ${#PRE_EXECUTION_SPECIALISTS[@]} -gt 0 ]; then
  PRE_EXECUTION_INIT=$(load_execute_phase_stage pre_execution_specialists)
  if [ $? -ne 0 ]; then
    echo "ERROR: pre-execution-specialists stage refresh failed: $PRE_EXECUTION_INIT"
    exit 1
  fi
fi
```

Use this stage only at explicit one-shot specialist handoff sites. Do not recreate placeholder `task(...)` examples here, do not wait in place for user approval inside a child run, and do not treat a named specialist route as complete unless its later artifact gate passes.
</step>

<step name="execute_waves">
Execute each wave in sequence. Within a wave: parallel if `PARALLELIZATION=true` AND `FORCE_SEQUENTIAL=false`, sequential otherwise. (Literature phases force sequential execution — see `adapt_to_computation_type`.)

Refresh the wave-dispatch stage immediately before spawning executors so plan execution sees only the late-loaded context it actually needs:

```bash
WAVE_DISPATCH_INIT=$(load_execute_phase_stage wave_dispatch)
if [ $? -ne 0 ]; then
  echo "ERROR: wave-dispatch stage refresh failed: $WAVE_DISPATCH_INIT"
  exit 1
fi
```

Parse JSON for: `selected_protocol_bundle_ids`, `protocol_bundle_context`, `current_execution`, `has_live_execution`, `execution_review_pending`, `execution_pre_fanout_review_pending`, `execution_skeptical_requestioning_required`, `execution_downstream_locked`, `execution_blocked`, `execution_resumable`, `execution_paused_at`, `current_execution_resume_file`, `handoff_resume_file`, `recorded_handoff_resume_file`, `missing_handoff_resume_file`, `execution_resume_file`, `execution_resume_file_source`, `resume_projection`, `current_hostname`, `current_platform`, `session_hostname`, `session_platform`, `session_last_date`, `session_stopped_at`, `machine_change_detected`, `machine_change_notice`, `state_load_source`, `state_integrity_issues`.

**For each wave:**

1. **Convention lock check (before parallel execution):**

   Before launching parallel plans, verify convention consistency:

   ```bash
   gpd convention check
   ```

   - If conventions are unlocked for any field that parallel plans will use, LOCK them first via `gpd convention set`
   - Do NOT proceed with parallel execution if convention conflicts exist

   **Pre-flight convention check for parallel waves:** Before spawning wave executors in parallel, verify all plans in the wave reference the same `convention_lock` values. For each plan in the wave, extract any convention references (metric signature, Fourier convention, unit system) and cross-compare. If any plan's conventions differ from the locked values, resolve the discrepancy before spawning. This prevents the most insidious class of parallel execution bugs: two agents computing with different sign conventions whose results are later combined.

2. **Create wave-level checkpoint** before any plan in the wave starts:

   ```bash
   WAVE_CHECKPOINT="gpd-checkpoint-phase-${phase_number}-wave-${WAVE_NUM}-$(date +%s)-$$"
   if git rev-parse --verify "refs/tags/${WAVE_CHECKPOINT}" >/dev/null 2>&1; then
     WAVE_CHECKPOINT="${WAVE_CHECKPOINT}-retry"
   fi
   if ! git tag "${WAVE_CHECKPOINT}"; then
     echo "ERROR: failed to create wave checkpoint tag ${WAVE_CHECKPOINT}" >&2
     exit 1
   fi
   ```

   Store the tag for wave-level recovery.

3. **Describe what's being done (BEFORE spawning):**

   Read each plan's `<objective>`. Extract what's being computed/derived and why.

   ```
   ---
   ## Wave {N}

   **{Plan ID}: {Plan Name}**
   {2-3 sentences: what this derives/computes/simulates, mathematical approach, why it matters for the overall research}

   Spawning {count} agent(s)...
   ---
   ```

   - Bad: "Executing Hamiltonian diagonalization plan"
   - Good: "Diagonalizing the spin-chain Hamiltonian using Bethe ansatz -- extracts exact energy spectrum and correlation functions in the thermodynamic limit. Required before computing transport coefficients in Wave 3."

   **If this wave is marked risky fanout:** run `probe_then_fanout` instead of blind full-wave scaleout.

   - First launch each risky plan only to its first-result gate or bounded segment boundary
   - Collect first-result sanity outcomes, decisive-evidence status, and anchor status
   - If an executor surfaces an unexpected but non-blocking alternative path, treat it as a tangent proposal, not permission for silent side exploration
   - Resolve tangent proposals with the four-way decision model (`ignore | defer | branch_later | pursue_now`) before any extra side work, branch work, or follow-on fanout is allowed
   - Only unlock the remainder of the wave when those gates pass with decisive evidence or the remaining work is explicitly independent of the unresolved comparison
   - If any plan fails the gate or requires re-questioning, STOP the wave before spawning more downstream work

4. **Spawn executor agents:**

   Pass paths only -- executors read files themselves with fresh context.
   This keeps orchestrator context lean; use `references/orchestration/context-budget.md` for numeric budget targets.

   Canonical runtime delegation convention for every `task()` block in this workflow:

   @{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

   The shared note owns runtime-neutral task construction and handoff gates. Later handoff blocks should reference this convention instead of restating those rules.

   ```
   task(
     subagent_type="gpd-executor",
     model="{executor_model}",
     readonly=false,
     prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

       <objective>
       Execute plan {plan_number} of phase {phase_number}-{phase_name}.
       Commit each task atomically. Create SUMMARY.md.
       Return state updates (position, decisions, metrics) in your response -- do NOT write STATE.md directly.
       </objective>

       <context_hint>{EXECUTOR_CONTEXT_HINT}</context_hint>
       <phase_class>{PHASE_CLASSES}</phase_class>
       <research_mode>{RESEARCH_MODE}</research_mode>
       <protocol_bundles>{selected_protocol_bundle_ids}</protocol_bundles>
       <protocol_bundle_context>{protocol_bundle_context}</protocol_bundle_context>
       <review_cadence>{REVIEW_CADENCE}</review_cadence>
       <max_unattended_minutes_per_plan>{MAX_UNATTENDED_MINUTES_PER_PLAN}</max_unattended_minutes_per_plan>
       <max_unattended_minutes_per_wave>{MAX_UNATTENDED_MINUTES_PER_WAVE}</max_unattended_minutes_per_wave>
       <segment_task_cap>{SEGMENT_TASK_CAP}</segment_task_cap>
       <first_result_gate>{FIRST_RESULT_GATE_REQUIRED}</first_result_gate>
       <checkpoint_before_downstream>{CHECKPOINT_BEFORE_DOWNSTREAM}</checkpoint_before_downstream>
       <bounded_execution>{true}</bounded_execution>
       <proof_redteam_gate>
       If this plan is proof-bearing, you must leave behind the proof artifact, theorem inventory, and enough supporting context for the orchestrator to spawn `gpd-check-proof`.
       Do NOT self-certify the sibling `{plan_id}-PROOF-REDTEAM.md` artifact as your own independent proof critic when a fresh `gpd-check-proof` subagent is available.
       If any named parameter, hypothesis, or quantifier is missing from the proof, surface that gap immediately and do NOT claim the theorem is established.
       Do not bypass this gate because the algebra looks clean, because the result reduces correctly in one special case, or because verification is disabled elsewhere.
       </proof_redteam_gate>
       <tangent_control>
       Proposal-first. If an unexpected but non-blocking alternative path appears, classify it as `ignore`, `defer`, `branch_later`, or `pursue_now`.
       Do not silently pursue optional tangents.
       `pursue_now` requires explicit user request or existing approved scope.
       If `research_mode=exploit`, suppress optional tangents unless tangent exploration was explicitly requested.
       </tangent_control>

       <files_to_read>
       Read these files at execution start using the file_read tool:
       - Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
       - Summary template: {GPD_INSTALL_DIR}/templates/summary.md
       - Checkpoints ref: {GPD_INSTALL_DIR}/references/orchestration/checkpoints.md
       - Validation ref: {GPD_INSTALL_DIR}/references/verification/core/verification-core.md (+ domain-specific verification file)
       - Plan: {phase_dir}/{plan_file}
       - State: GPD/STATE.md
       - Config: GPD/config.json (if exists)
       </files_to_read>

	       <success_criteria>
	       - [ ] All tasks executed with mathematical rigor
	       - [ ] Each task committed individually
	       - [ ] Dimensional consistency verified at each step
	       - [ ] Limiting cases checked where specified in plan
	       - [ ] Proof-bearing plans leave enough artifact context for the orchestrator to run `gpd-check-proof`
	       - [ ] Proof-bearing plans receive `{plan_id}-PROOF-REDTEAM.md` with `status: passed` before completion is claimed
	       - [ ] SUMMARY.md created in plan directory
	       - [ ] State updates returned (NOT written to STATE.md directly)
	     </success_criteria>
     "
   )
   ```

5a. **For proof-bearing plans, spawn the independent proof critic before accepting the result.**

   Resolve the proof-critic model once per wave when any selected plan is proof-bearing:

   ```bash
   CHECK_PROOF_MODEL=$(gpd resolve-model gpd-check-proof)
   ```

   After a proof-bearing executor has written its proof artifact(s) and `SUMMARY.md`, but before the wave-level spot-check accepts the plan, spawn `gpd-check-proof` in a fresh context:

   > Apply the canonical runtime delegation convention above.

   ```
   task(
     subagent_type="gpd-check-proof",
     model="{check_proof_model}",
     readonly=false,
     prompt="First, read {GPD_AGENTS_DIR}/gpd-check-proof.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/templates/proof-redteam-schema.md and {GPD_INSTALL_DIR}/references/verification/core/proof-redteam-protocol.md before writing any proof audit artifact.

       Operate in proof-redteam mode with a fresh context and follow the proof-redteam protocol's one-shot return semantics.

       Write to: {phase_dir}/{plan_id}-PROOF-REDTEAM.md

       Files to read:
       - {phase_dir}/{plan_file}
       - {phase_dir}/{plan_id}-SUMMARY.md
       - Proof / derivation artifacts produced by the executor
       - Supporting verification or summary artifacts referenced by the plan

       Reconstruct the theorem inventory explicitly before judging the proof.
       Fail closed on missing parameter coverage, missing hypotheses, narrowed quantifiers, or special-case proofs sold as general claims.",
     description="Proof redteam for phase {phase_number} plan {plan_id}"
   )
   ```

   If `gpd-check-proof` cannot be spawned, returns malformed output, or reports `status != passed`, route the plan to `wave_failure_handling`. Do not treat executor self-review as an acceptable substitute.

5. **Wait for all agents in wave to complete.**

   **Progress feedback during wave execution:** As each plan completes (or fails), immediately report to the user:

   ```
   [Phase {N}, Wave {W}] Plan {plan_id} complete ({completed}/{total} in wave)
     Result: {one-line summary from SUMMARY.md or failure reason}
   ```

   This ensures the user sees progress even when waves have multiple parallel plans. Do not wait for the entire wave to finish before showing any output.

   **If any executor agent fails to spawn or returns an error:** Check if the agent committed any work (`git log --oneline -3`). If commits exist, the agent may have completed but failed to report — spot-check output files and proceed. If no work was done, record the plan as failed for this wave. After all other agents complete, report failed plans and offer: 1) Retry failed plans in a new wave, 2) Execute failed plans in the main context, 3) Skip failed plans and continue. Do not abort the entire phase for individual plan failures.

6. **Report completion -- spot-check claims first:**

   For each SUMMARY.md:

   - Verify first 2 files from `key-files.created` exist on disk
   - If the SUMMARY marks any `key-files.created` / `key-files.modified` paths as required or final-deliverable, verify those paths on disk before accepting success
	   - Check `git log --oneline --grep="{phase}-{plan}"` returns >=1 commit
	   - Check for `## Self-Check: FAILED` marker
	   - Check for `## Validation: FAILED` marker (physics-specific)
	   - For proof-bearing plans, verify the sibling `{plan_id}-PROOF-REDTEAM.md` artifact exists and has `status: passed`
	   - Validate and apply the gpd_return envelope through the canonical child-return path:

     ```bash
     RETURN_APPLY=$(gpd --raw apply-return-updates "${SUMMARY_FILE}")
     RETURN_PASSED=$(python -c 'import json, sys; print(str(bool(json.loads(sys.argv[1]).get("passed", False))).lower())' "$RETURN_APPLY")
     if [ "$RETURN_PASSED" != "true" ]; then
       echo "ERROR: apply-return-updates failed for $(basename "$SUMMARY_FILE")"
       exit 1
     fi
     ```

	   If ANY spot-check fails, including a missing or non-passing proof-redteam artifact for proof-bearing work, or if `apply-return-updates` does not report `passed: true`: report which plan failed, route to `wave_failure_handling` -- do NOT silently continue.

   **IMPORTANT: Executor subagents MUST NOT write STATE.md directly.** Return state updates (position, decisions, metrics) in the structured return envelope. The orchestrator applies them through `gpd apply-return-updates` after each agent completes. This prevents parallel write conflicts where multiple agents overwrite each other's STATE.md changes and keeps durable child-return ownership in one place.

   By the time the wave-complete report is emitted, the canonical applicator has already persisted every successful plan from that wave. Do not duplicate that state mutation here.

   If pass:

   ```
   ---
   ## Wave {N} Complete

   **{Plan ID}: {Plan Name}**
   {What was derived/computed -- from SUMMARY.md}
   {Notable deviations or unexpected results, if any}
   {Limiting cases verified: list}

   {If more waves: what this enables for next wave}
   ---
   ```

   - Bad: "Wave 2 complete. Proceeding to Wave 3."
   - Good: "Spin-chain spectrum computed -- Bethe ansatz solution yields N-magnon energies with correct Heisenberg limit. Finite-size scaling exponents match CFT prediction (nu = 1.00 +/- 0.02). Transport coefficient calculation (Wave 3) can now use these eigenstates."

7. **Artifact summary** -- surface key artifacts produced in the completed wave.

   After verifying wave completion, collect the artifacts from each plan's SUMMARY.md (`key-files.created`, `key-files.modified`) and emit a compact summary with review priorities. See `references/orchestration/artifact-surfacing.md` for artifact class definitions and review priority rules.

   ```
   ## Artifacts: Wave {N}

   | Path | Class | Review |
   |------|-------|--------|
   | {relative_path} | {artifact_class} | {required | optional | final-deliverable} |
   ...

   Required review: {count} artifact(s) -- inspect before Wave {N+1}
   ```

   **Classification rules:**
   - Assign artifact class from file extension and path (see artifact-surfacing.md section 1)
   - Mark as `required` if the artifact is a load-bearing derivation, a numerical result consumed by later waves, or a contract deliverable that is the `subject` of an acceptance test
   - Mark as `final-deliverable` for completed manuscript outputs, compiled PDFs, and peer review reports
   - Mark as `optional` for supporting plots, intermediate notebooks, and literature notes

   **If any artifacts are marked `required`:** Include their paths in the wave completion report so the researcher can prioritize review. Do not block execution for optional artifacts.

8. **Handle failures** -- see `wave_failure_handling` below.

9. **Execute checkpoint plans between waves** -- see `<checkpoint_handling>`.

   Before unlocking downstream dependent waves, confirm that risky-wave plans passed the first meaningful review point:

	   - the first load-bearing result exists
	   - the result is tied to a contract-relevant output, not only a proxy
	   - one quick sanity/benchmark/convention check passed
	   - if the plan is proof-bearing, `{plan_id}-PROOF-REDTEAM.md` exists and reports `status: passed`
	   - decisive anchors still missing were explicitly named and re-questioned if necessary
	   - if the contract owed a decisive comparison, either that comparison now has a pass verdict or the downstream work was explicitly scoped so it does not rely on that unresolved claim
	   - if `review_cadence=dense` and the just-completed first wave emitted no `result/produce` or `result/log` event at all, STOP and require explicit user confirmation before advancing — a dense wave that produced no result event is indistinguishable from a silent failure and the first-result gate never had anything to trip on

   If this gate fails: STOP — do not let wrong early assumptions scale out.

   **Machine-state requirement for risky fanout gates:** when this review point pauses execution, record it as live execution state, not only prose. Emit an execution gate event with:

	   - `checkpoint_reason: pre_fanout`
	   - `pre_fanout_review_pending: true`
	   - `downstream_locked: true`
	   - `last_result_label` or `last_artifact_path` for the first load-bearing output being reviewed
	   - `proof_redteam_required: true` and `proof_redteam_status` when the reviewed output is proof-bearing
	   - `skeptical_requestioning_required: true` when the first result still looks proxy-only, anchor-thin, or otherwise short of the decisive evidence the contract still owes
   - `skeptical_requestioning_summary`, `weakest_unchecked_anchor`, and `disconfirming_observation` whenever skeptical re-questioning is required
   - optional `tangent_summary` and `tangent_decision` when the same bounded stop surfaced an unexpected but non-blocking alternative path that still needs explicit handling

   If the runtime or agent only emits a fanout-lock event, normalize it into the same live review stop: treat the lock as `checkpoint_reason=pre_fanout`, mark `waiting_for_review=true`, and keep downstream locked until the review is explicitly cleared.

   Gate clears are reason-scoped: clearing `first_result` must not erase `pre_fanout` or skeptical review flags, and skeptical re-questioning should be cleared explicitly when it is resolved.

   For `pre_fanout`, the matching gate-clear and `fanout unlock` are separate transitions: the clear records the review outcome, the unlock releases downstream work. Keep the segment live on status, notify, and resume surfaces until both have been observed. Do not silently continue on "looks fine" prose alone.

   **Tangent proposals at the same stop:** if the first result suggests an unexpected but non-blocking alternative path, keep it inside the same review conversation rather than spawning extra work. Resolve it with one of:

   - `ignore` — continue mainline execution unchanged
   - `defer` — note it in outputs as future work and continue
   - `branch_later` — recommend an explicit `gpd:tangent ...` or `gpd:branch-hypothesis ...` follow-up after the bounded stop
   - `pursue_now` — only if the user explicitly asked for tangent exploration or the approved contract already covers it

   **Machine-state bridge for tangent proposals:** when a tangent proposal is relevant at this stop, keep it inside the same live execution payload instead of inventing a new tangent state machine. Emit:

   - `tangent_summary` — one short description of the alternative path
   - `tangent_decision` — one of `ignore | defer | branch_later | pursue_now` once classified

   Do not create a new branch, child plan, or side subagent from executor initiative alone. In `research_mode=exploit`, treat optional tangent proposals as suppressed unless explicit request overrides that default.

10. **Inter-wave verification gate (if more waves remain):**

   Before spawning the next wave, run lightweight verification on the just-completed wave's outputs. This catches errors cheaply before they propagate to downstream waves.

   **Determine if gate is enabled from init/context fields only:**

   - if `review_cadence == dense`: enable inter-wave verification
   - if `review_cadence == adaptive`: enable it when the completed wave established or challenged a decisive evidence path, introduced a new baseline/estimator that later waves depend on, or left any skeptical or pre-fanout state unresolved
   - if `review_cadence == sparse`: skip the routine gate unless the just-completed wave triggered a failed sanity check, anchor gap, or pre-fanout dependency warning

	   **If enabled:**

   First, collect the SUMMARY.md files produced by the just-completed wave:

   ```bash
   # Collect SUMMARY files from the plans that executed in the current wave
   wave_summaries=()
   for PLAN_ID in $(echo "$PLAN_INDEX" | gpd json list ".waves[\"$WAVE_NUM\"]"); do
     SUMMARY_PATH="${phase_dir}/${PLAN_ID}-SUMMARY.md"
     [ -f "$SUMMARY_PATH" ] && wave_summaries+=("$SUMMARY_PATH")
   done
   ```

   Run lightweight checks on the wave's SUMMARY.md outputs:

   a. **Convention consistency** — verify convention lock hasn't drifted:

   ```bash
   CONV_CHECK=$(gpd --raw convention check)
   if [ "$CONV_CHECK" = "incomplete" ]; then
     echo "WARNING: Convention lock has unlocked fields"
   fi
   ```

   b. **Dimensional spot-check** — scan the wave's SUMMARY.md files for key results and verify dimensional consistency:

   For each SUMMARY.md produced in the just-completed wave, extract key equations (from `key_results` or `equations` frontmatter fields) and verify that:
   - Both sides of each equation have the same dimensions
   - Function arguments are dimensionless
   - No bare dimensionful quantities appear where dimensionless ones are expected

   This is a lightweight scan (~2-5k tokens), not a full dimensional analysis. It checks the SUMMARY outputs, not the derivation internals.

   c. **Unverified identity scan** — check for IDENTITY_CLAIM tags without verification:

   ```bash
   # Scan wave artifacts for unverified identity claims
   PHASE_ARTIFACT_DIR="artifacts/phases/${phase_number}-${phase_slug}"
   for summary in ${wave_summaries[@]}; do
     grep -rl "IDENTITY_SOURCE: training_data" \
       "$summary" "${PHASE_ARTIFACT_DIR}" figures/ data/ simulations/ paper/figures/ \
       2>/dev/null | while read f; do
       if ! grep -q "IDENTITY_VERIFIED:" "$f" 2>/dev/null; then
         echo "WARNING: Unverified training_data identity in $f"
       fi
     done
   done
   ```

   Prefer paths surfaced through SUMMARY `key-files` or contract deliverables. Do not assume durable artifacts live beside the SUMMARY in `GPD/phases/**`.

   If unverified identities are found: flag as WARNING. These identities may be correct but have not been numerically tested — downstream waves building on them carry unquantified risk.

   d. **Computation-type-specific checks** (driven by `INTER_WAVE_CHECKS` from `adapt_to_computation_type`):

   **If `convergence_spot_check` in INTER_WAVE_CHECKS** (numerical phases):

   Scan the wave's SUMMARY.md files for convergence-related metrics. Look for keywords: `convergence`, `error`, `residual`, `tolerance`, `iterations`, `grid_size`. Flag if:
   - A convergence metric worsened compared to the previous wave's output
   - A residual exceeds 1e-3 without explicit justification
   - An iteration count hit a hard limit (suggests non-convergence)

   ```bash
   for summary in ${wave_summaries[@]}; do
     # Extract numerical metrics from SUMMARY frontmatter or key_results
     grep -iE "converge|residual|error.*=.*[0-9]|tolerance" "$summary" 2>/dev/null | while read line; do
       echo "CONVERGENCE: $line"
     done
   done
   ```

   **If `plausibility_scan` in INTER_WAVE_CHECKS** (analysis/validation phases):

   Scan the wave's SUMMARY.md outputs for physically implausible values:
   - NaN or Inf in results
   - Negative values where positivity is expected (energies of bound states, probabilities, cross-sections)
   - Order-of-magnitude jumps (>10x) between related quantities in successive waves

   ```bash
   for summary in ${wave_summaries[@]}; do
     grep -iE "NaN|Inf|= -[0-9]|diverge" "$summary" 2>/dev/null | while read line; do
       echo "PLAUSIBILITY WARNING: $line"
     done
   done
   ```

   **If `latex_compile` in INTER_WAVE_CHECKS** (paper-writing phases):

   If `pdflatex` is available, compile the paper after each wave to catch LaTeX errors early:

   If a manuscript root has already been resolved for this workflow, bind it as `MANUSCRIPT_ROOT` before compiling from that root. Otherwise, resolve it locally from `paper/`, `manuscript/`, or `draft/` before checking for the manifest.

   ```bash
   if [ -z "${MANUSCRIPT_ROOT:-}" ]; then
     for candidate in paper manuscript draft; do
       if [ -f "${candidate}/ARTIFACT-MANIFEST.json" ]; then
         MANUSCRIPT_ROOT="${candidate}"
         break
       fi
     done
   fi
   if command -v pdflatex &>/dev/null && [ -f "${MANUSCRIPT_ROOT}/ARTIFACT-MANIFEST.json" ]; then
     MANIFEST_PATH="${MANUSCRIPT_ROOT}/ARTIFACT-MANIFEST.json"
     MANUSCRIPT_BASENAME="$(MANIFEST_PATH="$MANIFEST_PATH" python - <<'PY'
import json
import os
from pathlib import Path
manifest = json.loads(Path(os.environ["MANIFEST_PATH"]).read_text(encoding='utf-8'))
tex_path = next(artifact["path"] for artifact in manifest["artifacts"] if artifact["category"] == "tex")
print(Path(tex_path).name)
PY
)"
     (
       cd "${MANUSCRIPT_ROOT}" || exit 1
       pdflatex -interaction=nonstopmode "${MANUSCRIPT_BASENAME}"
     ) 2>&1 | grep -E "^!" | head -5
   fi
   ```

   Flag any LaTeX errors as WARNING — they should be fixed before the next wave adds more content.

	   For proof-bearing waves, treat the proof-redteam artifact as part of this inter-wave gate even when the cadence would otherwise skip routine checks. Missing or open proof audits keep downstream work locked.

	   **If any check fails:**

   ```
   ---
   ## Inter-wave verification gate

   **Convention check:** {PASS | WARNING: {details}}
   **Dimensional check:** {PASS | WARNING: {details}}
   **Identity check:** {PASS | WARNING: {N} unverified training_data identities}
   **Convergence check:** {PASS | WARNING: {details} | SKIPPED (not numerical phase)}
   **Plausibility check:** {PASS | WARNING: {details} | SKIPPED (not analysis/validation phase)}
   **LaTeX compile:** {PASS | WARNING: {N} errors | SKIPPED (not paper-writing phase)}

   Options:
   1. Continue to next wave (accept warnings)
   2. Fix issues before continuing
   3. Stop execution and investigate
   ---
   ```

   Present options and wait for user response (or auto-continue in YOLO mode if both are warnings, not errors — unless `YOLO_RESTRICTIONS` includes `no_skip_inter_wave`, in which case always present).

   **If disabled:** Skip verification gate, proceed directly to step 11. Exception: if `YOLO_RESTRICTIONS` includes `no_skip_inter_wave`, the gate runs even when disabled by config.

   **Cost:** ~2-5k tokens per inter-wave gate. For a 4-wave phase with deep-theory profile, this is ~10-15k tokens overhead — negligible compared to the cost of a sign error propagating through 3 subsequent waves.

11. **Inter-wave transition display:**

   Before spawning the next wave, display a physics-meaningful progress update that connects what was just computed to what comes next:

   ```
   ---
   Wave {N} -> Wave {N+1} transition

   Completed: {brief physics summary of wave N results -- e.g., "Exact diagonalization of 2D Hubbard model for N=4,8,12 sites"}
   Enables: {what wave N+1 will use from these results -- e.g., "Finite-size scaling analysis using the energy spectra from Wave 1"}
   Starting: {brief description of wave N+1 plans -- e.g., "Extracting critical exponents via data collapse (plans 03, 04)"}
   ---
   ```

   Extract the "Completed" summary from the wave N completion report (step 6 above). Extract "Enables" and "Starting" from the wave N+1 plan objectives. Keep each line to one sentence.

12. **Proceed to next wave.**
   </step>

<step name="wave_failure_handling">
When a plan within a wave fails (spot-check failure, agent crash, or plan-level failure reported by execute-plan):

**1. Identify the failure and its downstream impact:**

```bash
# Collect all plans from waves AFTER the current wave
LATER_PLANS=()
for LATER_WAVE in $(echo "$PLAN_INDEX" | gpd json keys .waves | awk -v w="$WAVE_NUM" '$1 > w'); do
  for P in $(echo "$PLAN_INDEX" | gpd json list ".waves[\"$LATER_WAVE\"]"); do
    LATER_PLANS+=("$P")
  done
done

# Which of those later plans depend on the failed plan?
DEPENDENT_PLANS=()
for LATER_PLAN in "${LATER_PLANS[@]}"; do
  DEPS=$(gpd frontmatter get \
    "${phase_dir}/${LATER_PLAN}-PLAN.md" --field depends_on 2>/dev/null)
  if echo "$DEPS" | grep -q "${FAILED_PLAN_ID}"; then
    DEPENDENT_PLANS+=("${LATER_PLAN}")
  fi
done
```

**2. Report failure with dependency analysis:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > WAVE {N} FAILURE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Failed plan:** {PLAN_ID} -- {plan name}
**Reason:** {failure description from spot-check or agent report}

### Wave {N} Status
| Plan | Status |
| ---- | ------ |
| {plan-A} | Passed |
| {plan-B} | FAILED |
| {plan-C} | Passed |

### Downstream Impact
Plans that depend on {FAILED_PLAN_ID} (will be auto-skipped):
{list of dependent plans with their wave numbers, or "None -- no downstream dependencies"}

──────────────────────────────────────────────────────
Options:
  1. "Rollback failed plan only" (preferred) -- revert only the commits from the failed plan
     using the TASK_COMMITS record. Keep all successful plans in this wave.
  2. "Continue" -- skip failed plan + dependents, execute remaining waves
  3. "Rollback wave" -- revert all wave {N} work to wave checkpoint
  4. "Stop" -- halt phase execution, preserve all completed work
──────────────────────────────────────────────────────
```

**3. Handle user choice:**

**Continue:**

- Mark the failed plan as skipped in the wave tracker
- Auto-skip all plans in `DEPENDENT_PLANS` in subsequent waves with message:

  ```
  Skipping {PLAN_ID}: depends on failed plan {FAILED_PLAN_ID}
  ```

- Track skipped plans in `SKIPPED_PLANS` array with reasons for the recovery report
- Proceed to next wave, filtering out dependent plans

**Rollback wave:**

- Revert to the wave checkpoint:

  ```bash
  WAVE_CHECKPOINT_COMMIT=$(git rev-list -n 1 "${WAVE_CHECKPOINT}")
  git revert --no-commit HEAD...${WAVE_CHECKPOINT_COMMIT}
  git commit -m "$(cat <<EOF
  revert: rollback wave ${WAVE_NUM} of phase ${phase_number}

  Failed plan: ${FAILED_PLAN_ID}
  Reason: ${FAILURE_REASON}
  Checkpoint: ${WAVE_CHECKPOINT}
  EOF
  )"
  ```

- Ask: "Retry wave {N}?" or "Stop execution?"
- If retry: re-enter the wave execution loop for wave N
- If stop: proceed to recovery report

**Stop:**

- Preserve all committed work
- Proceed directly to recovery report

**4. Auto-skip dependent plans during subsequent waves:**

When processing plans in waves N+1, N+2, etc., check each plan against the `SKIPPED_PLANS` list:

```bash
for DEP in $(echo "$PLAN_DEPS" | tr ',' ' '); do
  if [[ " ${SKIPPED_PLANS[*]} " =~ " ${DEP} " ]]; then
    echo "SKIP: Plan ${PLAN_ID} depends on skipped/failed plan ${DEP}"
    SKIPPED_PLANS+=("${PLAN_ID}:depends_on_${DEP}")
    continue 2
  fi
done
```

> **Handoff verification:** Do not trust the runtime handoff status by itself. Verify expected output files, the structured return envelope, and git commits before treating a subagent as failed.
</step>

<step name="checkpoint_handling">
Plans with `interactive: true` require user interaction.

```bash
CHECKPOINT_RESUME_INIT=$(load_execute_phase_stage checkpoint_resume) || { echo "ERROR: checkpoint_resume init failed"; exit 1; }
```

**Flow:**

1. Spawn agent for checkpoint plan
2. Agent runs until checkpoint task or validation gate -> returns structured state
3. Agent return includes completed tasks, current blocker, awaited item, and bounded execution segment; first-result/pre-fanout pauses add gate flags, skeptical re-questioning fields, and `downstream_locked`.
4. **Present to user:**

   ```
   ## Checkpoint: [Type]

   **Plan:** 03-03 Perturbation Expansion
   **Progress:** 2/3 tasks complete

   [Checkpoint Details from agent return]
   [Awaiting section from agent return]

   ## > Next Up

   `gpd:resume-work`

   Also available: `gpd:execute-phase {PHASE_NUMBER}` or `gpd:suggest-next`
   ```

5. User responds: "approved"/"done" | issue description | decision selection
6. **Spawn continuation agent (NOT resume)** using `{GPD_INSTALL_DIR}/templates/continuation-prompt.md` template:
   - `{completed_tasks_table}`: From checkpoint return
   - `{resume_task_number}` + `{resume_task_name}`: Current task
   - `{user_response}`: What user provided
   - `{resume_instructions}`: Based on checkpoint type (see template for type-specific instructions)
   - `{execution_segment}`: The returned bounded-segment state, including checkpoint cause, current cursor, resume preconditions, downstream-lock status, and any skeptical re-questioning fields that must survive into the continuation
7. Continuation agent verifies previous commits, continues from resume point
8. Repeat until plan completes or user stops

**Why fresh agent, not resume:** Resume relies on internal serialization that breaks with parallel tool calls. Fresh agents with explicit state are more reliable.

**Checkpoints in parallel waves:** Agent pauses and returns while other parallel agents may complete. Present checkpoint, spawn continuation, wait for all before next wave.
</step>

<step name="context_budget_check">
**Before aggregating results, estimate context consumption:**

Count the SUMMARY files that will be read and estimate their impact on orchestrator context using the summary-aggregation heuristic in `references/orchestration/context-budget.md`.

```bash
SUMMARY_COUNT=$(ls "${phase_dir}"/*-SUMMARY.md 2>/dev/null | wc -l)
ESTIMATED_TOKENS=$(( SUMMARY_COUNT * 3000 ))
CONTEXT_BUDGET=${CONTEXT_BUDGET:-160000}  # Approximate usable-token budget (about 80% of window)
BUDGET_PERCENT=$(( ESTIMATED_TOKENS * 100 / CONTEXT_BUDGET ))
```

If `BUDGET_PERCENT` exceeds 15%: warn before proceeding:

```
WARNING: Reading ${SUMMARY_COUNT} SUMMARY files will consume ~${BUDGET_PERCENT}% of orchestrator context.
Consider using summary-extract for one-liners only instead of full SUMMARY reads.
```

If >15%, use `summary-extract` for one-liners instead of reading full SUMMARY files:

```bash
for summary in "${phase_dir}"/*-SUMMARY.md; do
  gpd --raw summary-extract "$summary" --field one_liner | gpd json get .one_liner --default ""
done
```
</step>

<step name="aggregate_results">
After all waves:

```bash
AGGREGATE_VERIFY_INIT=$(load_execute_phase_stage aggregate_and_verify) || { echo "ERROR: aggregate_and_verify init failed"; exit 1; }
```

```markdown
## Phase {X}: {Name} Execution Complete

**Waves:** {N} | **Plans:** {M}/{total} complete

| Wave | Plans            | Status   |
| ---- | ---------------- | -------- |
| 1    | plan-01, plan-02 | Complete |
| CP   | plan-03          | Verified |
| 2    | plan-04          | Complete |

### Plan Details

1. **03-01**: [one-liner from SUMMARY.md]
2. **03-02**: [one-liner from SUMMARY.md]

### Validation Summary

[Aggregate limiting case checks, dimensional consistency results, cross-checks]

### Issues Encountered

[Aggregate from SUMMARYs, or "None"]
```

</step>

<step name="generate_figure_tracker">
**After all waves complete successfully, inventory generated figures/plots into FIGURE_TRACKER.md:**

Scan all SUMMARY.md files from this phase for figure-related artifacts:

```bash
# Find figures referenced in SUMMARY files
for SUMMARY in "${phase_dir}"/*-SUMMARY.md; do
  # Extract key-files.created entries that look like figures
  grep -E '\.(pdf|png|eps|svg|jpg|jpeg|tiff)' "$SUMMARY" 2>/dev/null
done

# Also scan durable figure roots for generated plot files
PHASE_ARTIFACT_DIR="artifacts/phases/${phase_number}-${phase_slug}"
find "${PHASE_ARTIFACT_DIR}" figures/ paper/figures/ -maxdepth 3 \
  \( -name "*.pdf" -o -name "*.png" -o -name "*.eps" \) 2>/dev/null | \
  grep -iE "fig|plot|phase_diag|spectrum|convergence|diagram" 2>/dev/null
```

Generated figures and plots should live in stable workspace roots such as `artifacts/phases/${phase_number}-${phase_slug}/`, `figures/`, or `paper/figures/`, not under `GPD/phases/**`.

**If any figures found:**

Read the figure tracker template from `{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md` using the runtime's normal file-read mechanism.

**If `paper/FIGURE_TRACKER.md` already exists:** Append new figures to the existing registry. Do not overwrite existing entries.

**If it does not exist:** Create it from the template:

```bash
mkdir -p paper
```

Write `paper/FIGURE_TRACKER.md` with:

- One entry per discovered figure/plot
- `Source phase` set to the current phase number
- `Source file` set to the script or notebook that generated it (from SUMMARY key-files)
- `Data file(s)` set to any associated data files (from SUMMARY key-files)
- `Status` set to "Data ready" or "Draft" based on file inspection
- `Last updated` set to today's date

Commit:

```bash
PRE_CHECK=$(gpd pre-commit-check --files paper/FIGURE_TRACKER.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs(phase-${phase_number}): update figure tracker" \
  --files paper/FIGURE_TRACKER.md
```

**If no figures found:** Skip silently (not all phases produce visual outputs).

**Experimental comparison artifact:** If any plan in this phase compared theoretical predictions with experimental or observational data (PHENO-type objectives, or plans whose SUMMARY mentions "experimental comparison", "pull", "chi-squared", or "theory vs data"), create `paper/EXPERIMENTAL_COMPARISON.md` using `{GPD_INSTALL_DIR}/templates/paper/experimental-comparison.md`. Populate with comparison tables, pull values, and discrepancy classifications from the plan SUMMARYs. Skip if no experimental comparison was performed.

</step>

<step name="recovery_report">
**After all waves complete (including any failures, skips, or rollbacks), generate a recovery report.**

This step runs unconditionally -- for fully successful phases it is a brief confirmation; for phases with failures it is the critical decision point.

**1. Collect execution outcomes:**

```bash
# Collect all plan IDs from the phase plan index
ALL_PLAN_IDS=($(echo "$PLAN_INDEX" | gpd json pluck .plans id))

# Initialize outcome tracking arrays
# Note: FAILED_IDS, SKIPPED_IDS, and their reason maps should be maintained
# by the orchestrator during execute_waves and wave_failure_handling steps.
# FAILED_IDS+=("plan_id") when a plan fails spot-checks or agent reports failure.
# SKIPPED_IDS+=("plan_id") when a plan is auto-skipped due to dependency on failed plan.
declare -A FAILURE_REASONS  # Map plan_id -> failure description
declare -A SKIP_REASONS     # Map plan_id -> "depends_on_${dep_id}"

PLANS_SUCCEEDED=()    # Plans with SUMMARY.md and passing spot-checks
PLANS_FAILED=()       # Plans that failed during execution
PLANS_SKIPPED=()      # Plans skipped due to dependency on failed plans
PLANS_ROLLED_BACK=()  # Plans whose work was reverted

for PLAN_ID in "${ALL_PLAN_IDS[@]}"; do
  if [ -f "${phase_dir}/${PLAN_ID}-SUMMARY.md" ]; then
    PLANS_SUCCEEDED+=("${PLAN_ID}")
  elif [[ " ${FAILED_IDS[*]} " =~ " ${PLAN_ID} " ]]; then
    PLANS_FAILED+=("${PLAN_ID}:${FAILURE_REASONS[$PLAN_ID]}")
  elif [[ " ${SKIPPED_IDS[*]} " =~ " ${PLAN_ID} " ]]; then
    PLANS_SKIPPED+=("${PLAN_ID}:${SKIP_REASONS[$PLAN_ID]}")
  fi
done
```

**2. Present recovery report:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PHASE {X} EXECUTION REPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Results

| Plan | Status | Detail |
| ---- | ------ | ------ |
| {id} | Passed | {one-liner from SUMMARY} |
| {id} | FAILED | {failure reason} |
| {id} | Skipped | Depends on failed {dep_id} |

**Summary:** {succeeded_count} passed, {failed_count} failed, {skipped_count} skipped
```

**3. If ALL plans passed:** Proceed to `verify_phase_goal` as normal. Report is informational only.

**4. If ANY failures or skips occurred:**

Create a recovery section in the phase directory. For physics-specific root cause analysis, consult `{GPD_INSTALL_DIR}/templates/recovery-plan.md`:

```bash
RECOVERY_FILE="${phase_dir}/PHASE-RECOVERY.md"
```

Write `PHASE-RECOVERY.md`:

```markdown
---
phase: { PHASE_NUMBER }
phase_name: { PHASE_NAME }
created: { ISO timestamp }
plans_succeeded: [{ list }]
plans_failed: [{ list }]
plans_skipped: [{ list }]
checkpoint_tags: [{ list of all remaining gpd-checkpoint tags for this phase }]
---

# Phase {X} Recovery

## Execution Summary

{succeeded_count}/{total_count} plans completed successfully.

## Failed Plans

### {PLAN_ID}: {plan name}

- **Failed at:** Task {N} -- {task name}
- **Reason:** {detailed failure reason}
- **Checkpoint:** {checkpoint tag, if preserved}
- **Recovery:** See RECOVERY-{PLAN}.md (created by execute-plan)

## Skipped Plans

### {PLAN_ID}: {plan name}

- **Skipped because:** Depends on failed plan {dep_id}
- **Would have computed:** {objective from PLAN.md}

## Recovery Options

1. Fix failing plans and re-execute: `gpd:execute-phase {X}` (auto-detects partial completion)
2. Re-plan failed tasks: `gpd:plan-phase {X} --gaps` (creates new plans for unfinished work)
3. Revise phase goal: `gpd:discuss-phase {X}` (rethink approach based on what failed)
4. Continue to next phase: `gpd:plan-phase {X+1}` (if remaining work is non-critical)
```

Commit recovery document:

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${RECOVERY_FILE}" GPD/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs(phase-${phase_number}): phase recovery report" \
  --files "${RECOVERY_FILE}" GPD/STATE.md
```

**5. Offer actionable next steps based on failure pattern:**

```
──────────────────────────────────────────────────────
## Next Steps

{If single plan failed, rest passed:}
  The failure is isolated. Fix and re-execute:
  `gpd:execute-phase {X}` -- will resume from the failed plan

{If multiple plans failed in same wave:}
  Multiple failures in Wave {N} suggest a systemic issue.
  Review the phase approach before retrying:
  `gpd:discuss-phase {X}` -- reassess methodology

{If failures cascaded through dependencies:}
  The root failure in {ROOT_PLAN} cascaded to {N} dependent plans.
  Fix the root cause first:
  Review: ${phase_dir}/RECOVERY-{ROOT_PLAN}.md

{If all plans failed:}
  Complete phase failure. The phase goal or approach may need revision:
  `gpd:plan-phase {X}` -- re-plan from scratch
──────────────────────────────────────────────────────
```

</step>

<step name="verify_phase_goal">
**If `verifier_enabled` is false** (from init JSON config / `workflow.verifier` in config.json): Skip only the generic post-execution verifier for non-proof phases. If any executed plan is proof-bearing, proof verification still runs and missing/open `*-PROOF-REDTEAM.md` artifacts keep the phase fail-closed. Log the distinction explicitly instead of treating verifier-disabled config as a blanket bypass.

Verify phase achieved its GOAL, not just completed tasks.

**Phase-class-aware verification:** Pass the phase classification from `classify_phase` so the verifier prioritizes checks: derivation -> dimensional/numerical spot/limit/identity checks; numerical -> convergence, statistical validation, spot checks, decisive benchmarks; formalism -> dimensional, limiting, Ward/sum-rule, literature checks; validation -> full relevant universal registry plus contract-aware checks; analysis -> order-of-magnitude, plausibility, literature, and fit/estimator checks.

Include in the verifier spawn prompt: `<phase_class>{PHASE_CLASSES}</phase_class>` so the verifier can adjust its check prioritization.

Spawn `gpd-verifier` in a fresh context; the child reads `{GPD_INSTALL_DIR}/workflows/verify-phase.md`.

> Apply the canonical runtime delegation convention above.

```
task(
  subagent_type="gpd-verifier",
  model="{verifier_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-verifier.md for your role and instructions.

Verify Phase {PHASE_NUMBER} against its phase goal and plan contracts.

<phase_class>{PHASE_CLASSES}</phase_class>

Load before verdict:
- {GPD_INSTALL_DIR}/workflows/verify-phase.md
- {GPD_INSTALL_DIR}/templates/verification-report.md
- {GPD_INSTALL_DIR}/templates/contract-results-schema.md

<files_to_read>
- Phase plans and summaries: {phase_dir}
- Roadmap: GPD/ROADMAP.md
- State: GPD/STATE.md and GPD/state.json
</files_to_read>

Run `gpd --raw init phase-op {PHASE_NUMBER}` and keep the project contract, reference/protocol context, and `phase_proof_review_status` visible. Stable knowledge docs surfaced there are background only.

Write to: {phase_dir}/{phase_number}-VERIFICATION.md

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - "{phase_dir}/{phase_number}-VERIFICATION.md"
expected_artifacts:
  - "{phase_dir}/{phase_number}-VERIFICATION.md"
shared_state_policy: return_only
</spawn_contract>

Return one typed `gpd_return` envelope with `status`, `files_written`, and canonical `verification_status` (`passed | gaps_found | expert_needed | human_needed`).",
  description="Verify Phase {PHASE_NUMBER} goal"
)
```

Read status after verification completes through the typed child-return contract:

- `gpd_return.status: completed` means success only after verifying that:
  1. `${phase_dir}/${phase_number}-VERIFICATION.md` exists on disk and is readable
  2. the same path appears in `gpd_return.files_written`
  3. `gpd validate verification-contract "${phase_dir}/${phase_number}-VERIFICATION.md"` passes before any downstream routing
- If a canonical verification file already existed before this run, do not treat it as fresh verifier output unless the child reported that same path in `gpd_return.files_written`.
- Route only on `gpd_return.status` and the validated frontmatter; do not use `grep "^status:"`, headings, or marker strings to decide success.

| Status         | Action                                                      |
| -------------- | ----------------------------------------------------------- |
| `passed`       | -> update_roadmap                                           |
| `human_needed`  | Present items for human review, get approval or feedback    |
| `expert_needed` | Domain expert review required; present items, escalate      |
| `gaps_found`    | Present gap summary, offer `gpd:plan-phase {phase} --gaps` |

If the same report also carries `session_status: validating|completed|diagnosed`, treat that as conversational progress only. It does not replace the canonical verification `status` read above. A diagnosed verification session will normally still report `status: gaps_found` until the fixes are re-verified.

**If human_needed:**

```
## Phase {X}: {Name} -- Human Verification Required

All automated checks passed. {N} items need human review:

{From VERIFICATION.md human_verification section}

"approved" -> continue | Report issues -> gap closure
```

**If gaps_found:**

```
## Phase {X}: {Name} -- Gaps Found

**Score:** {N}/{M} contract targets verified
**Report:** {phase_dir}/{phase}-VERIFICATION.md

### What's Missing
{Gap summaries from VERIFICATION.md}

### Physics Issues
{Any dimensional inconsistencies, failed limiting cases, or conservation law violations}

---
## > Next Up

`gpd:plan-phase {X} --gaps`

<sub>Start a fresh context window</sub>

Also: `cat {phase_dir}/{phase}-VERIFICATION.md` -- full report
Also: `gpd:verify-work {X}` -- manual review first
```

Gap closure cycle: `gpd:plan-phase {X} --gaps` reads VERIFICATION.md -> creates gap plans with `gap_closure: true` -> user runs `gpd:execute-phase {X} --gaps-only` -> automatic re-verification (below).

**Smart failure recovery (replaces blunt circuit breaker):**

Before triggering gap closure, classify the failure to select the minimum-cost recovery strategy. See `agent-infrastructure.md` Meta-Orchestration Intelligence > Feedback Loop Intelligence for the full classification table.

```bash
# Count only top-level verification outcomes. Nested contract-results and gap
# ledgers also have `status:` fields, so unanchored grep would overcount them.
FAILED_COUNT=$(rg -c '^status: (gaps_found|expert_needed|human_needed)$' "${phase_dir}"/*-VERIFICATION.md 2>/dev/null | awk -F: '{sum += $2} END {print sum+0}')
TOTAL_COUNT=$(rg -c '^status: (passed|gaps_found|expert_needed|human_needed)$' "${phase_dir}"/*-VERIFICATION.md 2>/dev/null | awk -F: '{sum += $2} END {print sum+0}')
```

| Failure Pattern | Recovery | Cost |
|---|---|---|
| 1 contract target failed, rest passed | Re-execute the specific failing plan only | 1 subagent |
| Multiple failures, same error type (e.g., all sign errors) | Stop and route through `gpd:validate-conventions`; repair happens in a fresh continuation before re-execution | validate + follow-up |
| Multiple failures, different error types | Escalate to user -- approach may be fundamentally wrong | 0 (user decides) |
| Same gap persists after 1 gap-closure | Spawn debugger to identify root cause before 2nd attempt | 1-2 subagents |

**For localized failures (1 contract target):** Skip full gap-closure planning. Instead, directly re-execute the single plan that produced the failed result with explicit error context:

> Apply the canonical runtime delegation convention above.

```
task(
  subagent_type="gpd-executor",
  model="{executor_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

  Re-execute plan {FAILED_PLAN} with focus on fixing: {FAILURE_DESCRIPTION}.
  The verifier found: {VERIFICATION_DETAIL}.
  Read the original SUMMARY.md for what was attempted. Fix the specific error.

  <context_hint>{EXECUTOR_CONTEXT_HINT}</context_hint>
  <phase_class>{PHASE_CLASSES}</phase_class>
  <protocol_bundles>{selected_protocol_bundle_ids}</protocol_bundles>
  <protocol_bundle_context>{protocol_bundle_context}</protocol_bundle_context>

  <files_to_read>
  - Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
  - Plan: {phase_dir}/{FAILED_PLAN}-PLAN.md
  - Previous SUMMARY: {phase_dir}/{FAILED_PLAN}-SUMMARY.md
  - State: GPD/STATE.md
  </files_to_read>",
  description="Targeted re-execution of {FAILED_PLAN}"
)
```

**For systematic failures:** Do not route notation repair inline from this workflow. Stop and point the user to `gpd:validate-conventions`; if convention repair is needed, that workflow and the fresh continuation handoff own the `gpd-notation-coordinator` spawn and typed return routing. After conventions are validated, re-enter `gpd:execute-phase {X}` or `gpd:execute-phase {X} --gaps-only` as appropriate.

**For persistent failures (same gap after 1 cycle):** Spawn debugger BEFORE the second gap-closure attempt:

```bash
DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)
```

> Apply the canonical runtime delegation convention above.

```
task(
  subagent_type="gpd-debugger",
  model="{debugger_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.

  Use {GPD_INSTALL_DIR}/templates/debug-subagent-prompt.md as the explicit one-shot debug contract. Populate it from the failed verification file, the gap-closure summary, and the original summary; set `goal: find_root_cause_only`, `symptoms_prefilled: true`, and `Create: GPD/debug/{FAILED_PLAN}.md`.

  Return exactly one typed `gpd_return` envelope with `status: completed | checkpoint | blocked | failed`, include the session file, and stop. Do not route on heading markers or continue the investigation interactively inside the child.",
  description="Diagnose persistent verification failure"
)
```

**Circuit breaker (hard stop): Maximum 2 verification-gap closure cycles.** After 2 failed verification cycles (with debugger diagnosis on the second), STOP the loop. Present a diagnostic summary to the user:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > CIRCUIT BREAKER: VERIFICATION LOOP HALTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phase {X} has failed verification twice after gap closure attempts.

### Attempt 1
- Gaps found: {list from first VERIFICATION.md}
- Gap closure plans: {list of plans created}
- Re-verification result: {what still failed}

### Attempt 2
- Remaining gaps: {list from second VERIFICATION.md}
- Gap closure plans: {list of plans created}
- Re-verification result: {what still failed}

### Root Cause Hypothesis
{System's best hypothesis for why gap closure is not resolving the issue}

### Suggested Actions
1. `gpd:debug` — Systematic investigation of the persistent failure
2. `gpd:discuss-phase {X}` — Reassess the approach with fresh perspective
3. Manual intervention — The issue may require researcher insight

Do NOT attempt a third automated cycle.
```

**After gap closure execution completes (`$GAPS_ONLY` is true):**

Automatically re-verify the phase to confirm gaps are closed:

```bash
VERIFIER_MODEL=$(gpd resolve-model gpd-verifier)
```

> Apply the canonical runtime delegation convention above.

```
task(
  subagent_type="gpd-verifier",
  model="{verifier_model}",
  readonly=false,
 prompt="First, read {GPD_AGENTS_DIR}/gpd-verifier.md for your role and instructions.

Reload these canonical verifier surfaces before updating any verdicts:
- {GPD_INSTALL_DIR}/workflows/verify-phase.md
- {GPD_INSTALL_DIR}/templates/verification-report.md
- {GPD_INSTALL_DIR}/templates/contract-results-schema.md

Treat `VERIFICATION.md` as contract-backed only through the schema-owned ledgers `plan_contract_ref`, `contract_results`, `comparison_verdicts`, and `suggested_contract_checks`; do not expect verifier-local aliases or ad hoc machine-readable artifact fields.

Re-verify Phase {PHASE_NUMBER} after gap closure.

<phase_class>{PHASE_CLASSES}</phase_class>

	<files_to_read>
	Read these files using the file_read tool:
	- Verification: {phase_dir}/{phase}-VERIFICATION.md
	- All SUMMARY.md files in {phase_dir}/
	- All `*-PROOF-REDTEAM.md` files in {phase_dir}/
	- State: GPD/STATE.md
	- Roadmap: GPD/ROADMAP.md
	</files_to_read>

	Rebuild the structured phase context with `gpd --raw init phase-op {PHASE_NUMBER}` and keep `project_contract`, `project_contract_gate`, `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, and `phase_proof_review_status` visible while re-checking the remaining gaps. Treat any stable knowledge docs surfaced in those fields as reviewed background only: they may inform interpretation, but they do not override the contract, proof audits, or decisive evidence.

	Focus on the gaps that were previously marked failed, partial, blocked, or otherwise unresolved in the previous verification. If the prior report carries `session_status: diagnosed`, use the recorded root causes and missing actions as the starting point for re-verification. For proof-bearing work, re-check every required `*-PROOF-REDTEAM.md` artifact and keep the phase blocked until those audits report `status: passed`.
	Check whether the gap closure plans have resolved each issue.
	Update VERIFICATION.md with new status for each gap.
	Return exactly one typed `gpd_return` envelope with `status: completed | checkpoint | blocked | failed`, include `files_written`, and write `{phase_dir}/{phase}-VERIFICATION.md` before returning. Use the verifier's canonical `verification_status: passed | gaps_found | expert_needed | human_needed` inside the structured return or the written report; do not return bare `passed | gaps_found` text as the routing surface.",
  description="Re-verify Phase {PHASE_NUMBER} after gap closure"
)
```

**If the verifier agent fails to spawn or returns an error:** Stop in a blocked state. Do not mark the phase complete or clear gap-closure state on this path. End with `## > Next Up`: primary `gpd:verify-work {PHASE_NUMBER}` to confirm gaps are closed, plus `gpd:resume-work` and `gpd:suggest-next`. If the phase is proof-bearing, do NOT mark it complete on this path; proof-obligation work remains blocked until re-verification and proof-redteam audits actually clear. Do not trust the runtime handoff status by itself. Do not let a stale existing verification file satisfy the success path.

**Handle the verifier response through `gpd_return.status`:**

- `gpd_return.status: completed`:
  1. Do not accept `gpd_return.status: completed` until `{phase_dir}/{phase}-VERIFICATION.md` exists on disk.
  2. The same path appears in `gpd_return.files_written`.
  3. If either check fails, treat the re-verification handoff as blocked. Do not let a stale existing verification file satisfy the success path.
  4. After the artifact gate passes, use the canonical verifier verdict from `gpd_return.verification_status` or the written report frontmatter:
     - `passed` -> mark phase complete, proceed to `update_roadmap`
     - `gaps_found` / `expert_needed` / `human_needed` -> report remaining gaps and STOP -- do not auto-loop. Present: "Re-verification found {N} remaining gaps. Review: {phase_dir}/{phase}-VERIFICATION.md" and end with `## > Next Up`: primary `gpd:plan-phase {PHASE_NUMBER} --gaps`, then `gpd:execute-phase {PHASE_NUMBER} --gaps-only`, `gpd:verify-work {PHASE_NUMBER}`, and `gpd:suggest-next`.
- `gpd_return.status: checkpoint`: stop, surface the checkpoint payload, and end with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:verify-work {PHASE_NUMBER}` and `gpd:suggest-next`. Do not wait in place for user input inside this run.
- `gpd_return.status: blocked` / `gpd_return.status: failed`: stop in a blocked state, surface the issues, keep gap-closure state intact, and end with `## > Next Up`: primary `gpd:verify-work {PHASE_NUMBER}`, plus `gpd:resume-work` and `gpd:suggest-next`.

**If the verifier output is malformed or omits `gpd_return.status`:** Treat it as blocked. Do not infer success from prose headings or untyped routing.

</step>

<step name="rapid_consistency_check">
Run a rapid cross-phase consistency check to catch convention violations and sign errors before they propagate to future phases.

Resolve consistency checker model:

```bash
CONSISTENCY_MODEL=$(gpd resolve-model gpd-consistency-checker)
```

Spawn the consistency checker in rapid mode:

> Apply the canonical runtime delegation convention above.

task(prompt="First, read {GPD_AGENTS_DIR}/gpd-consistency-checker.md for your role and instructions.

<mode>rapid</mode>
<phase>{PHASE_NUMBER}</phase>

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - "{phase_dir}/CONSISTENCY-CHECK.md"
expected_artifacts:
  - "{phase_dir}/CONSISTENCY-CHECK.md"
shared_state_policy: return_only
</spawn_contract>

Check phase {PHASE_NUMBER} results against the full conventions ledger and all accumulated project state.
Use the structured init-state payload (`convention_lock` / `derived_convention_lock`) and SUMMARY.md frontmatter convention fields first.
Use `gpd convention list` and `file_read: GPD/STATE.md, GPD/state.json` only if the payload is missing or inconsistent.
file_read: All SUMMARY.md files from phase {PHASE_NUMBER}

Return exactly one typed `gpd_return` envelope with `status: completed | checkpoint | blocked | failed`, include `files_written`, and write `{phase_dir}/CONSISTENCY-CHECK.md`.
", subagent_type="gpd-consistency-checker", model="{consistency_model}", readonly=false, description="Rapid consistency check")

**Artifact gate:** Do not accept `gpd_return.status: completed` until `{phase_dir}/CONSISTENCY-CHECK.md` exists on disk. If the artifact is missing, treat the handoff as blocked even when the runtime reported success.

```bash
CONSISTENCY_REPORT="${phase_dir}/CONSISTENCY-CHECK.md"
if [ ! -f "$CONSISTENCY_REPORT" ]; then
  echo "ERROR: consistency-check artifact missing: $CONSISTENCY_REPORT"
  exit 1
fi
```

**If the consistency checker agent fails to spawn or returns an error:** Treat the consistency check as blocked. Do not proceed as if the phase was checked. End with `## > Next Up`: primary `gpd:validate-conventions`, plus `gpd:resume-work`, `gpd:execute-phase {PHASE_NUMBER}`, and `gpd:suggest-next`.

**Handle the checker response through `gpd_return.status`:**
- `gpd_return.status: completed`: accept only if the artifact gate passes. Surface any `issues` as warnings, then continue.
- `gpd_return.status: checkpoint`: stop, surface the checkpoint payload from the checker, and end with `## > Next Up`: primary `gpd:resume-work`, plus `gpd:validate-conventions` and `gpd:suggest-next`. Do not wait in place for user input inside this run.
- `gpd_return.status: blocked` / `gpd_return.status: failed`: stop execution, surface the returned issues, and end with `## > Next Up`: primary `gpd:validate-conventions`, plus `gpd:resume-work` and `gpd:suggest-next`. If the user wants convention repair, route through `gpd:validate-conventions`; the fresh continuation handoff owns any notation-coordinator work.

**If the checker output is malformed or omits `gpd_return.status`:** Treat it as blocked. Do not infer success from prose headings or untyped routing.

Convention repair is intentionally out-of-line here. Do not spawn `gpd-notation-coordinator` from `execute-phase`, do not route on checker-local prose markers, and do not accept a stale convention document as proof of repair. The next step is `gpd:validate-conventions`, followed by `gpd:resume-work` or a fresh `gpd:execute-phase {PHASE_NUMBER}` continuation after that workflow reports a typed result and the convention lock is valid.

**If "Force continue":** Log the forced override to DECISIONS.md:

```bash
gpd state add-decision \
  --phase "${phase_number}" \
  --summary "Forced past consistency check (--force-inconsistent)" \
  --rationale "${USER_RATIONALE}"
```

**If `gpd_return.status: completed`:** Continue to phase completion.
</step>

<step name="orchestrator_self_check">

Before marking complete, verify VERIFICATION.md lists attack vectors, limiting cases, and literature cross-references. If no issues appeared, run one targeted check on the most load-bearing result.

</step>

<step name="update_roadmap">
Mark phase complete in ROADMAP.md (date, status).

```bash
CLOSEOUT_INIT=$(load_execute_phase_stage closeout) || { echo "ERROR: closeout init failed"; exit 1; }
```

Follow `{GPD_INSTALL_DIR}/workflows/transition.md` for PROJECT.md, DECISIONS.md, and parallel phase detection.

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/ROADMAP.md GPD/STATE.md "${phase_dir}"/*-VERIFICATION.md GPD/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(phase-${phase_number}): complete phase execution" --files GPD/ROADMAP.md GPD/STATE.md "${phase_dir}"/*-VERIFICATION.md GPD/REQUIREMENTS.md
```

</step>

<step name="cleanup_phase_checkpoints">
**After successful phase completion (all plans passed + verification passed):**

Remove all `gpd-checkpoint-phase-{phase}-*` tags for this phase -- they are no longer needed.

```bash
PHASE_TAGS=$(git tag -l "gpd-checkpoint-phase-${phase_number}-*")

if [ -n "${PHASE_TAGS}" ]; then
  echo "Cleaning up ${phase_number} checkpoint tags..."
  for TAG in ${PHASE_TAGS}; do
    git tag -d "${TAG}" 2>/dev/null
  done
  echo "Checkpoint tags removed for phase ${phase_number}."
fi
```

**If there were ANY failures during the phase** (even if subsequently resolved via re-execution), keep all checkpoint tags. They provide audit trail and enable future rollback if issues surface later.

**Decision logic:**

| Condition                               | Action                                             |
| --------------------------------------- | -------------------------------------------------- |
| All plans passed + verification passed  | Delete all `gpd-checkpoint-phase-{X}-*` tags       |
| Any plans failed (even if kept partial) | Keep all checkpoint tags                           |
| Verification found gaps                 | Keep all checkpoint tags                           |
| Phase marked complete after gap closure | Delete checkpoint tags from successful re-run only |

</step>

<step name="offer_next">

<continuation_routing>
After phase completion, check the project's autonomy mode. If yolo or balanced with no pending checkpoint, auto-route to the next phase. If supervised, or if a checkpoint requires review, pause with a clear status message showing: current phase completed, why execution paused, exact next command to continue, and key artifacts to review. See `{GPD_INSTALL_DIR}/references/orchestration/continuous-execution.md` for the standard checkpoint protocol.
</continuation_routing>

Never end with only "ready to plan/continue" prose. After a successful closeout, choose exactly one matching variant and emit a `Next Up` block with concrete commands; do not print conditional "if context is missing/exists" labels in the final answer.

- If the next phase has no `*-CONTEXT.md`, make `gpd:discuss-phase {X+1}` the primary command and show `gpd:plan-phase {X+1}` as the direct-plan alternative.
- If the next phase already has context, make `gpd:plan-phase {X+1}` the primary command.
- Always include `gpd:suggest-next` as the shortest recovery/confirmation command when the user only wants the next action.

**If more phases:**

```
## > Next Up

**Phase {X+1}: {Name}** -- {Goal}

Primary: `{chosen primary command}`

**Also available:**
- `{secondary command}` -- when relevant
- `gpd:suggest-next` -- confirm the next action

<sub>Start a fresh context window, then run the primary command above.</sub>
```

**If milestone complete:**

```
MILESTONE COMPLETE!

All {N} phases executed.

`gpd:complete-milestone`

**Also available:** `gpd:suggest-next`

<sub>Start a fresh context window, then run `gpd:complete-milestone`.</sub>
```

</step>

</process>

<context_efficiency>
Orchestrator stays lean per `references/orchestration/context-budget.md`; subagents get fresh contexts. No polling (Task blocks). No context bleed.
</context_efficiency>

<failure_handling>

- **False failure report despite delivered work:** Spot-check (SUMMARY exists, commits present, expected artifacts exist) -> if pass, treat as success
- **Agent fails mid-plan:** Missing SUMMARY.md -> report, route to wave_failure_handling for user decision
- **Dependency chain breaks:** Wave N plan fails -> identify Wave N+1 dependents via `depends_on` frontmatter -> auto-skip with clear message -> user chooses at wave level
- **All agents in wave fail:** Systemic issue -> stop, report for investigation, offer wave-level rollback
- **Checkpoint unresolvable:** "Skip this plan?" or "Abort phase execution?" -> record partial progress in STATE.md
- **Physics validation failure:** Dimensional inconsistency or conservation law violation detected -> STOP, do not proceed to next wave, report for investigation
  </failure_handling>

<resumption>
Re-run `gpd:execute-phase {phase}` -> discover_plans finds completed SUMMARYs -> skips them -> resumes from first incomplete plan -> continues wave execution.

STATE.md tracks: last completed plan, current wave, pending checkpoints.

**Partial completion detection:** execute-plan's `detect_previous_attempt` step checks git log for task-level commits. Plans with partial commits offer resume-from-task-N. Plans with RECOVERY-{PLAN}.md files surface recovery options.
</resumption>
