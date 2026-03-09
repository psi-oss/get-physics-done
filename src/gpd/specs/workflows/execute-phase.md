<purpose>
Execute all plans in a research phase using wave-based parallel execution. Orchestrator stays lean -- delegates plan execution to subagents. Each plan may involve derivations, calculations, simulations, or analysis with proper checkpointing and validation at each step.
</purpose>

<core_principle>
Orchestrator coordinates, not executes. Each subagent loads the full execute-plan context. Orchestrator: discover plans -> analyze deps -> group waves -> spawn agents -> handle checkpoints -> collect results -> validate physics.
</core_principle>

<required_reading>
Read STATE.md before any operation to load project context.
For agent selection strategy and verification failure routing, see `@{GPD_INSTALL_DIR}/references/meta-orchestration.md`.
</required_reading>

<process>

<step name="initialize" priority="first">
Load all context in one call:

```bash
INIT=$(gpd init execute-phase "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  exit 1
fi
```

Parse JSON for: `executor_model`, `verifier_model`, `commit_docs`, `autonomy`, `research_mode`, `parallelization`, `verifier_enabled`, `branching_strategy`, `branch_name`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `phase_slug`, `plans`, `incomplete_plans`, `plan_count`, `incomplete_count`, `state_exists`, `roadmap_exists`.

**If `phase_found` is false:** Error -- phase directory not found.
**If `plan_count` is 0:** Error -- no plans found in phase.
**If `state_exists` is false but `.planning/` exists:** Offer reconstruct or continue.

When `parallelization` is false, plans within a wave execute sequentially.

**Mode-aware behavior:**
- `autonomy=supervised`: Pause for user confirmation before each wave. Show plan summary and wait for approval.
- `autonomy=guided` (default): Pause only at wave boundaries if errors or ambiguities arise.
- `autonomy=autonomous`: Execute all waves without pausing. Report results at end.
- `autonomy=yolo`: Execute all waves, skip optional verification steps, commit immediately.
- `research_mode=explore`: Favor thoroughness — always run verification, expand context budget.
- `research_mode=exploit`: Favor speed — skip optional research steps, tighter context budget.
- `research_mode=adaptive`: Start with exploit, switch to explore if verification fails.
</step>

<step name="handle_branching">
Check `branching_strategy` from init:

**"none":** Skip, continue on current branch.

**"phase" or "milestone":** Use pre-computed `branch_name` from init:

```bash
git checkout -b "$BRANCH_NAME" 2>/dev/null || git checkout "$BRANCH_NAME"
```

All subsequent commits go to this branch. User handles merging.
</step>

<step name="classify_phase">
Classify the phase type to drive agent selection and context budget decisions. Scan the phase goal and plan objectives for indicator keywords.

```bash
PHASE_GOAL=$(gpd roadmap get-phase "${phase_number}" | gpd json get .goal --default "")
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
- Verifier check prioritization (derivation phases promote L5 Tier 2-3; numerical phases promote 5.9 convergence; validation phases run all 15 checks)
- Computation-type-aware execution adaptation (see `adapt_to_computation_type` below)
</step>

<step name="adapt_to_computation_type">
Translate the phase classification into concrete execution parameters that drive wave-loop behavior. Set these variables before entering `execute_waves`:

```bash
# Defaults
CONVENTION_LOCK_REQUIRED=false
PRE_EXECUTION_AGENTS=()
INTER_WAVE_CHECKS=("convention" "dimensional")
EXECUTOR_CONTEXT_HINT="standard"
WAVE_TIMEOUT_FACTOR=1.0
FORCE_SEQUENTIAL=false
YOLO_RESTRICTIONS=()
```

**Per-class overrides (applied cumulatively for multi-class phases):**

| Class | Parameter Overrides |
|---|---|
| **derivation** | `CONVENTION_LOCK_REQUIRED=true` — refuse to start if conventions unlocked. `INTER_WAVE_CHECKS+=("identity_scan")` — check for unverified identities between waves. `EXECUTOR_CONTEXT_HINT="derivation-heavy"` — hint executors to allocate 70% of context to step-by-step work. `WAVE_TIMEOUT_FACTOR=1.5` — derivations run longer. `YOLO_RESTRICTIONS+=("no_skip_verification")` — even in yolo mode, do NOT skip verification for derivation phases (sign errors cost more than the verification). |
| **numerical** | `INTER_WAVE_CHECKS+=("convergence_spot_check")` — between waves, scan SUMMARY for convergence metrics and flag regressions. `EXECUTOR_CONTEXT_HINT="code-heavy"` — hint executors to reserve context for code output and numerical tables. `PRE_EXECUTION_AGENTS+=("experiment-designer")` — if experiment-designer is enabled, spawn before wave 1 to validate parameter ranges. |
| **literature** | `FORCE_SEQUENTIAL=true` — literature plans build on each other's findings; parallel risks redundant searches. `EXECUTOR_CONTEXT_HINT="reading-heavy"` — hint executors to budget for large literature ingestion. `INTER_WAVE_CHECKS=("convention")` — skip dimensional checks (no equations). |
| **paper-writing** | `PRE_EXECUTION_AGENTS+=("notation-coordinator")` — ensure notation glossary is current before any section drafting. `INTER_WAVE_CHECKS+=("latex_compile")` — compile after each wave to catch LaTeX errors early. `EXECUTOR_CONTEXT_HINT="prose-heavy"` — hint executors to balance equation density with exposition. |
| **formalism** | `CONVENTION_LOCK_REQUIRED=true`. `PRE_EXECUTION_AGENTS+=("notation-coordinator")` — conventions must be established before framework setup. `INTER_WAVE_CHECKS+=("identity_scan")`. |
| **analysis** | `INTER_WAVE_CHECKS+=("plausibility_scan")` — between waves, scan results for physically implausible values (NaN, sign changes, order-of-magnitude jumps). |
| **validation** | `YOLO_RESTRICTIONS+=("no_skip_verification" "no_skip_inter_wave")` — validation phases must run all checks regardless of autonomy mode. `INTER_WAVE_CHECKS+=("identity_scan" "convergence_spot_check" "plausibility_scan")` — run all inter-wave checks. |

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
      PRE_EXECUTION_AGENTS+=("experiment-designer")
      ;;
    literature)
      FORCE_SEQUENTIAL=true
      EXECUTOR_CONTEXT_HINT="reading-heavy"
      INTER_WAVE_CHECKS=("convention")
      ;;
    paper-writing)
      PRE_EXECUTION_AGENTS+=("notation-coordinator")
      INTER_WAVE_CHECKS+=("latex_compile")
      EXECUTOR_CONTEXT_HINT="prose-heavy"
      ;;
    formalism)
      CONVENTION_LOCK_REQUIRED=true
      PRE_EXECUTION_AGENTS+=("notation-coordinator")
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

echo "Execution adaptation: convention_lock=${CONVENTION_LOCK_REQUIRED}, pre_agents=[${PRE_EXECUTION_AGENTS[*]}], inter_wave=[${INTER_WAVE_CHECKS[*]}], context_hint=${EXECUTOR_CONTEXT_HINT}, timeout_factor=${WAVE_TIMEOUT_FACTOR}"
```

**Convention lock enforcement:**

If `CONVENTION_LOCK_REQUIRED=true`:

```bash
CONV_STATUS=$(gpd convention check --raw)
if [ "$CONV_STATUS" != "locked" ] && [ "$CONV_STATUS" != "complete" ]; then
  echo "ERROR: Phase class (${PHASE_CLASSES[*]}) requires locked conventions before execution."
  echo "Convention status: ${CONV_STATUS}"
  echo ""
  echo "Fix with one of:"
  echo "  gpd convention set"
  echo "  $gpd-validate-conventions"
  echo ""
  echo "HALTING — convention errors in derivation/formalism phases compound across every step."
  exit 1
fi
```

**This is a hard gate.** When `CONVENTION_LOCK_REQUIRED=true` and conventions are not locked, execution MUST NOT proceed. Do not skip this gate in any autonomy mode (including yolo). Convention errors are irreversible — they invalidate all downstream results.

**Pre-execution agent spawning:**

If `PRE_EXECUTION_AGENTS` is non-empty, spawn them sequentially before wave 1:

```bash
for AGENT_TYPE in "${PRE_EXECUTION_AGENTS[@]}"; do
  case "$AGENT_TYPE" in
    notation-coordinator)
      AGENT_MODEL=$(gpd resolve-model gpd-notation-coordinator --raw)
      # Spawn notation-coordinator to verify/establish conventions
      # Task(subagent_type="gpd-notation-coordinator", model="{AGENT_MODEL}", ...)
      ;;
    experiment-designer)
      AGENT_MODEL=$(gpd resolve-model gpd-experiment-designer --raw)
      # Spawn experiment-designer to validate parameter ranges
      # Task(subagent_type="gpd-experiment-designer", model="{AGENT_MODEL}", ...)
      ;;
  esac
done
```

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

<step name="structural_validation">
Run structural validation on all plans before execution begins:

```bash
VALIDATION_FAILED=false

# Validate each plan's frontmatter and structure
for plan in "$phase_dir"/*-PLAN.md; do
  if ! gpd verify plan-structure "$plan"; then
    echo "ERROR: plan-structure validation failed for $(basename "$plan")"
    VALIDATION_FAILED=true
  fi
done

# Validate wave dependencies
if ! gpd validate-waves "$phase_number"; then
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

<step name="discover_and_group_plans">
Load plan inventory with wave grouping in one call:

```bash
PLAN_INDEX=$(gpd phase-plan-index "${phase_number}")
```

Parse JSON for: `phase`, `plans[]` (each with `id`, `wave`, `autonomous`, `objective`, `files_modified`, `task_count`, `has_summary`), `waves` (map of wave number -> plan IDs), `incomplete`, `has_checkpoints`.

**Filtering:** Skip plans where `has_summary: true`. If `--gaps-only`: also skip non-gap_closure plans. If all filtered: "No matching incomplete plans" -> exit.

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

<step name="execute_waves">
Execute each wave in sequence. Within a wave: parallel if `PARALLELIZATION=true` AND `FORCE_SEQUENTIAL=false`, sequential otherwise. (Literature phases force sequential execution — see `adapt_to_computation_type`.)

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
   WAVE_CHECKPOINT="gpd-checkpoint/phase-${phase_number}-wave-${WAVE_NUM}-$(date +%s)-$$"
   git tag "${WAVE_CHECKPOINT}"
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

4. **Spawn executor agents:**

   Pass paths only -- executors read files themselves with their fresh 200k context.
   This keeps orchestrator context lean (~10-15%).

   > **Runtime delegation:** Spawn a subagent for the task below. Adapt the `Task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.

   ```
   Task(
     subagent_type="gpd-executor",
     model="{executor_model}",
     prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

       <objective>
       Execute plan {plan_number} of phase {phase_number}-{phase_name}.
       Commit each task atomically. Create SUMMARY.md.
       Return state updates (position, decisions, metrics) in your response -- do NOT write STATE.md directly.
       </objective>

       <context_hint>{EXECUTOR_CONTEXT_HINT}</context_hint>
       <phase_class>{PHASE_CLASSES}</phase_class>

       <files_to_read>
       Read these files at execution start using the Read tool:
       - Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
       - Summary template: {GPD_INSTALL_DIR}/templates/summary.md
       - Checkpoints ref: {GPD_INSTALL_DIR}/references/checkpoints.md
       - Validation ref: {GPD_INSTALL_DIR}/references/verification-core.md (+ domain-specific verification file)
       - Plan: {phase_dir}/{plan_file}
       - State: .planning/STATE.md
       - Config: .planning/config.json (if exists)
       </files_to_read>

       <success_criteria>
       - [ ] All tasks executed with mathematical rigor
       - [ ] Each task committed individually
       - [ ] Dimensional consistency verified at each step
       - [ ] Limiting cases checked where specified in plan
       - [ ] SUMMARY.md created in plan directory
       - [ ] State updates returned (NOT written to STATE.md directly)
       </success_criteria>
     "
   )
   ```

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
   - Check `git log --oneline --grep="{phase}-{plan}"` returns >=1 commit
   - Check for `## Self-Check: FAILED` marker
   - Check for `## Validation: FAILED` marker (physics-specific)
   - Validate the gpd_return envelope:

     ```bash
     RETURN_CHECK=$(gpd validate-return "${SUMMARY_FILE}" --raw)
     if [ "$RETURN_CHECK" != "passed" ]; then
       echo "WARNING: validate-return failed for $(basename "$SUMMARY_FILE")"
       # Mark plan as NEEDS_REVIEW but continue — missing envelope is not fatal
     fi
     ```

   If ANY spot-check fails: report which plan failed, route to `wave_failure_handling` -- do NOT silently continue.

   **IMPORTANT: Executor subagents MUST NOT write STATE.md directly.** Return state updates (position, decisions, metrics) in the structured return envelope. The orchestrator applies them sequentially after each agent completes. This prevents parallel write conflicts where multiple agents overwrite each other's STATE.md changes.

   After each plan completes successfully (not just after each wave), the **orchestrator** runs:
   1. `gpd state advance-plan` immediately
   2. `gpd state record-metric` for the completed plan
   3. This ensures crash recovery loses at most ONE plan's state, not an entire wave

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

7. **Handle failures** -- see `wave_failure_handling` below.

8. **Execute checkpoint plans between waves** -- see `<checkpoint_handling>`.

9. **Inter-wave verification gate (if more waves remain):**

   Before spawning the next wave, run lightweight verification on the just-completed wave's outputs. This catches errors cheaply before they propagate to downstream waves.

   **Determine if gate is enabled:**

   ```bash
   # Read verify_between_waves from config (default: "auto")
   # Uses nullish check (not ||) so explicit false is respected
   VERIFY_BETWEEN=$(node -e "
     try {
       const c = JSON.parse(require('fs').readFileSync('.planning/config.json','utf8'));
       const v = c.workflow && c.workflow.verify_between_waves;
       console.log(v !== null && v !== undefined ? String(v) : 'auto');
     } catch(e) { console.log('auto'); }
   ")

   # Resolve "auto" based on model profile
   if [ "$VERIFY_BETWEEN" = "auto" ]; then
     PROFILE=$(node -e "
       try {
         const c = JSON.parse(require('fs').readFileSync('.planning/config.json','utf8'));
         console.log(c.model_profile || 'review');
       } catch(e) { console.log('review'); }
     ")
     # auto defaults: enabled for deep-theory and review, disabled for others
     case "$PROFILE" in
       deep-theory|review) VERIFY_BETWEEN="true" ;;
       *) VERIFY_BETWEEN="false" ;;
     esac
   fi
   ```

   **If enabled (`VERIFY_BETWEEN` is `"true"`):**

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
   CONV_CHECK=$(gpd convention check --raw)
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
   for summary in ${wave_summaries[@]}; do
     plan_dir=$(dirname "$summary")
     grep -rl "IDENTITY_SOURCE: training_data" "$plan_dir" 2>/dev/null | while read f; do
       if ! grep -q "IDENTITY_VERIFIED:" "$f" 2>/dev/null; then
         echo "WARNING: Unverified training_data identity in $f"
       fi
     done
   done
   ```

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

   ```bash
   if command -v pdflatex &>/dev/null && [ -f paper/main.tex ]; then
     cd paper && pdflatex -interaction=nonstopmode main.tex 2>&1 | grep -E "^!" | head -5
     cd ..
   fi
   ```

   Flag any LaTeX errors as WARNING — they should be fixed before the next wave adds more content.

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

   **If disabled:** Skip verification gate, proceed directly to step 10. Exception: if `YOLO_RESTRICTIONS` includes `no_skip_inter_wave`, the gate runs even when disabled by config.

   **Cost:** ~2-5k tokens per inter-wave gate. For a 4-wave phase with deep-theory profile, this is ~10-15k tokens overhead — negligible compared to the cost of a sign error propagating through 3 subsequent waves.

10. **Inter-wave transition display:**

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

11. **Proceed to next wave.**
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

> **Known bug workaround:** The `classifyHandoffIfNeeded` bug may report successful subagents as failed. Always spot-check output files and git commits before treating a result as failed. See `{GPD_INSTALL_DIR}/references/known-bugs.md` §1 for details.
</step>

<step name="checkpoint_handling">
Plans with `autonomous: false` require user interaction.

**Flow:**

1. Spawn agent for checkpoint plan
2. Agent runs until checkpoint task or validation gate -> returns structured state
3. Agent return includes: completed tasks table, current task + blocker, checkpoint type/details, what's awaited
4. **Present to user:**

   ```
   ## Checkpoint: [Type]

   **Plan:** 03-03 Perturbation Expansion
   **Progress:** 2/3 tasks complete

   [Checkpoint Details from agent return]
   [Awaiting section from agent return]
   ```

5. User responds: "approved"/"done" | issue description | decision selection
6. **Spawn continuation agent (NOT resume)** using `{GPD_INSTALL_DIR}/templates/continuation-prompt.md` template:
   - `{completed_tasks_table}`: From checkpoint return
   - `{resume_task_number}` + `{resume_task_name}`: Current task
   - `{user_response}`: What user provided
   - `{resume_instructions}`: Based on checkpoint type (see template for type-specific instructions)
7. Continuation agent verifies previous commits, continues from resume point
8. Repeat until plan completes or user stops

**Why fresh agent, not resume:** Resume relies on internal serialization that breaks with parallel tool calls. Fresh agents with explicit state are more reliable.

**Checkpoints in parallel waves:** Agent pauses and returns while other parallel agents may complete. Present checkpoint, spawn continuation, wait for all before next wave.
</step>

<step name="context_budget_check">
**Before aggregating results, estimate context consumption:**

Count the SUMMARY files that will be read and estimate their impact on orchestrator context:

```bash
SUMMARY_COUNT=$(ls "${phase_dir}"/*-SUMMARY.md 2>/dev/null | wc -l)
ESTIMATED_TOKENS=$(( SUMMARY_COUNT * 3000 ))
CONTEXT_BUDGET=${CONTEXT_BUDGET:-200000}  # Model-dependent; 200k for most current models
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
  gpd summary-extract "$summary" --fields one_liner
done
```
</step>

<step name="aggregate_results">
After all waves:

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

# Also scan for generated plot files in the phase directory and .planning/
find "${phase_dir}" .planning/paper/ -maxdepth 2 \( -name "*.pdf" -o -name "*.png" -o -name "*.eps" \) 2>/dev/null | \
  grep -iE "fig|plot|phase_diag|spectrum|convergence|diagram" 2>/dev/null
```

**If any figures found:**

Read the figure tracker template:

```bash
cat {GPD_INSTALL_DIR}/templates/paper/figure-tracker.md
```

**If `.planning/paper/FIGURE_TRACKER.md` already exists:** Append new figures to the existing registry. Do not overwrite existing entries.

**If it does not exist:** Create it from the template:

```bash
mkdir -p .planning/paper
```

Write `.planning/paper/FIGURE_TRACKER.md` with:

- One entry per discovered figure/plot
- `Source phase` set to the current phase number
- `Source file` set to the script or notebook that generated it (from SUMMARY key-files)
- `Data file(s)` set to any associated data files (from SUMMARY key-files)
- `Status` set to "Data ready" or "Draft" based on file inspection
- `Last updated` set to today's date

Commit:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .planning/paper/FIGURE_TRACKER.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs(phase-${phase_number}): update figure tracker" \
  --files .planning/paper/FIGURE_TRACKER.md
```

**If no figures found:** Skip silently (not all phases produce visual outputs).

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

Create a recovery section in the phase directory:

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

1. Fix failing plans and re-execute: `$gpd-execute-phase {X}` (auto-detects partial completion)
2. Re-plan failed tasks: `$gpd-plan-phase {X} --gaps` (creates new plans for unfinished work)
3. Revise phase goal: `$gpd-discuss-phase {X}` (rethink approach based on what failed)
4. Continue to next phase: `$gpd-plan-phase {X+1}` (if remaining work is non-critical)
```

Commit recovery document:

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${RECOVERY_FILE}" .planning/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs(phase-${phase_number}): phase recovery report" \
  --files "${RECOVERY_FILE}" .planning/STATE.md
```

**5. Offer actionable next steps based on failure pattern:**

```
──────────────────────────────────────────────────────
## Next Steps

{If single plan failed, rest passed:}
  The failure is isolated. Fix and re-execute:
  `$gpd-execute-phase {X}` -- will resume from the failed plan

{If multiple plans failed in same wave:}
  Multiple failures in Wave {N} suggest a systemic issue.
  Review the phase approach before retrying:
  `$gpd-discuss-phase {X}` -- reassess methodology

{If failures cascaded through dependencies:}
  The root failure in {ROOT_PLAN} cascaded to {N} dependent plans.
  Fix the root cause first:
  Review: ${phase_dir}/RECOVERY-{ROOT_PLAN}.md

{If all plans failed:}
  Complete phase failure. The phase goal or approach may need revision:
  `$gpd-plan-phase {X}` -- re-plan from scratch
──────────────────────────────────────────────────────
```

</step>

<step name="verify_phase_goal">
**If `verifier_enabled` is false** (from init JSON config / `workflow.verifier` in config.json): Skip phase verification entirely. Log: "Verification skipped (disabled in config)." Proceed directly to phase transition (update_roadmap step).

Verify phase achieved its GOAL, not just completed tasks.

**Phase-class-aware verification:** Pass the phase classification (from `classify_phase` step) to the verifier so it can prioritize checks:
- **Derivation phases:** Promote L5 checks 5.3 (limiting cases), 5.6 (symmetry), 5.8 (math consistency). These catch the most common derivation errors.
- **Numerical phases:** Promote 5.9 (convergence), 5.12 (statistics), 5.2 (numerical spot-check). Convergence verification is critical.
- **Formalism phases:** Promote 5.6 (symmetry), 5.7 (conservation), 5.1 (dimensional). Framework consistency is the priority.
- **Validation phases:** Run all 15 checks -- validation IS the purpose. Do not use the 7-check exploratory floor.
- **Analysis phases:** Promote 5.11 (plausibility), 5.3 (limiting cases). Results must be physically sensible.

Include in the verifier spawn prompt: `<phase_class>{PHASE_CLASSES}</phase_class>` so the verifier can adjust its check prioritization.

Follow the verification workflow. Read `{GPD_INSTALL_DIR}/workflows/verify-phase.md` using the Read tool.

Read status after verification completes:

```bash
grep "^status:" "$phase_dir"/*-VERIFICATION.md | head -1 | cut -d: -f2 | tr -d ' '
```

| Status         | Action                                                      |
| -------------- | ----------------------------------------------------------- |
| `passed`       | -> update_roadmap                                           |
| `completed`    | -> update_roadmap (interactive verify-work equivalent)      |
| `human_needed`  | Present items for human review, get approval or feedback    |
| `expert_needed` | Domain expert review required; present items, escalate      |
| `gaps_found`    | Present gap summary, offer `$gpd-plan-phase {phase} --gaps` |
| `diagnosed`    | Gaps were debugged; review fixes, then -> update_roadmap    |
| `validating`   | Verification in progress; wait or re-run verify-phase       |

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

**Score:** {N}/{M} must-haves verified
**Report:** {phase_dir}/{phase}-VERIFICATION.md

### What's Missing
{Gap summaries from VERIFICATION.md}

### Physics Issues
{Any dimensional inconsistencies, failed limiting cases, or conservation law violations}

---
## >> Next Up

`$gpd-plan-phase {X} --gaps`

<sub>`/clear` first -> fresh context window</sub>

Also: `cat {phase_dir}/{phase}-VERIFICATION.md` -- full report
Also: `$gpd-verify-work {X}` -- manual review first
```

Gap closure cycle: `$gpd-plan-phase {X} --gaps` reads VERIFICATION.md -> creates gap plans with `gap_closure: true` -> user runs `$gpd-execute-phase {X} --gaps-only` -> automatic re-verification (below).

**Smart failure recovery (replaces blunt circuit breaker):**

Before triggering gap closure, classify the failure to select the minimum-cost recovery strategy. See `agent-infrastructure.md` Meta-Orchestration Intelligence > Feedback Loop Intelligence for the full classification table.

```bash
# Count failed must-haves and classify
FAILED_COUNT=$(grep -c "status: failed" "${phase_dir}"/*-VERIFICATION.md 2>/dev/null || echo 0)
TOTAL_COUNT=$(grep -c "status:" "${phase_dir}"/*-VERIFICATION.md 2>/dev/null || echo 0)
```

| Failure Pattern | Recovery | Cost |
|---|---|---|
| 1 must-have failed, rest passed | Re-execute the specific failing plan only | 1 subagent |
| Multiple failures, same error type (e.g., all sign errors) | Spawn notation-coordinator to check conventions, then re-execute | 2 subagents |
| Multiple failures, different error types | Escalate to user -- approach may be fundamentally wrong | 0 (user decides) |
| Same gap persists after 1 gap-closure | Spawn debugger to identify root cause before 2nd attempt | 1-2 subagents |

**For localized failures (1 must-have):** Skip full gap-closure planning. Instead, directly re-execute the single plan that produced the failed result with explicit error context:

```
Task(
  subagent_type="gpd-executor",
  model="{executor_model}",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-executor.md for your role and instructions.

  Re-execute plan {FAILED_PLAN} with focus on fixing: {FAILURE_DESCRIPTION}.
  The verifier found: {VERIFICATION_DETAIL}.
  Read the original SUMMARY.md for what was attempted. Fix the specific error.

  <context_hint>{EXECUTOR_CONTEXT_HINT}</context_hint>
  <phase_class>{PHASE_CLASSES}</phase_class>

  <files_to_read>
  - Workflow: {GPD_INSTALL_DIR}/workflows/execute-plan.md
  - Plan: {phase_dir}/{FAILED_PLAN}-PLAN.md
  - Previous SUMMARY: {phase_dir}/{FAILED_PLAN}-SUMMARY.md
  - State: .planning/STATE.md
  </files_to_read>",
  description="Targeted re-execution of {FAILED_PLAN}"
)
```

**For systematic failures:** Spawn notation-coordinator first to check for convention drift, then re-execute with corrected conventions.

**For persistent failures (same gap after 1 cycle):** Spawn debugger BEFORE the second gap-closure attempt:

```bash
DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger --raw)
```

```
Task(
  subagent_type="gpd-debugger",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.
  Investigate why gap closure did not resolve this verification failure.
  Read: {VERIFICATION_FILE}, {GAP_CLOSURE_SUMMARY}, {ORIGINAL_SUMMARY}
  Identify the root cause and recommend: fix-and-retry vs re-plan vs escalate.",
  model="{debugger_model}",
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
1. `$gpd-debug` — Systematic investigation of the persistent failure
2. `$gpd-discuss-phase {X}` — Reassess the approach with fresh perspective
3. Manual intervention — The issue may require researcher insight

Do NOT attempt a third automated cycle.
```

**After gap closure execution completes (`--gaps-only` mode):**

Automatically re-verify the phase to confirm gaps are closed:

```bash
VERIFIER_MODEL=$(gpd resolve-model gpd-verifier --raw)
```

```
Task(
  subagent_type="gpd-verifier",
  model="{verifier_model}",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-verifier.md for your role and instructions.

Re-verify Phase {PHASE_NUMBER} after gap closure.

<phase_class>{PHASE_CLASSES}</phase_class>

<files_to_read>
Read these files using the Read tool:
- Verification: {phase_dir}/{phase}-VERIFICATION.md
- All SUMMARY.md files in {phase_dir}/
- State: .planning/STATE.md
- Roadmap: .planning/ROADMAP.md
</files_to_read>

Focus on the gaps that were marked as 'failed' or 'diagnosed' in the previous verification.
Check whether the gap closure plans have resolved each issue.
Update VERIFICATION.md with new status for each gap.
Return verification status: passed | gaps_found.",
  description="Re-verify Phase {PHASE_NUMBER} after gap closure"
)
```

**If the verifier agent fails to spawn or returns an error:** Proceed without automated re-verification. Note in the phase status that post-gap-closure verification was skipped. The user should run `$gpd-verify-work` separately to confirm gaps are closed.

| Re-verification Result | Action |
| ---------------------- | ------ |
| `passed` | Mark phase complete, proceed to `update_roadmap` |
| `gaps_found` | Report remaining gaps and STOP -- do not auto-loop. Present: "Re-verification found {N} remaining gaps. Review: {phase_dir}/{phase}-VERIFICATION.md" |

</step>

<step name="rapid_consistency_check">
Run a rapid cross-phase consistency check to catch convention violations and sign errors before they propagate to future phases.

Resolve consistency checker model:

```bash
CONSISTENCY_MODEL=$(gpd resolve-model gpd-consistency-checker --raw)
```

Spawn the consistency checker in rapid mode:

Task(prompt="First, read {GPD_AGENTS_DIR}/gpd-consistency-checker.md for your role and instructions.

<mode>rapid</mode>
<phase>{PHASE_NUMBER}</phase>

Check phase {PHASE_NUMBER} results against the full conventions ledger and all accumulated project state.
Read conventions from state.json via: gpd convention list
And from SUMMARY.md frontmatter convention fields.
Read: .planning/STATE.md, .planning/state.json
Read: All SUMMARY.md files from phase {PHASE_NUMBER}

Return consistency_status with any issues found.
", subagent_type="gpd-consistency-checker", model="{consistency_model}", description="Rapid consistency check")

**If the consistency checker agent fails to spawn or returns an error:** Proceed without cross-phase consistency checking for this wave. Note in the phase status that consistency verification was skipped. The user should run `$gpd-validate-conventions` after execution completes to catch any convention drift.

**If INCONSISTENT:** STOP execution. Present issues to user with resolution options:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > CONVENTION INCONSISTENCY DETECTED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{issues from consistency checker}

──────────────────────────────────────────────────────
Options:
  1. "Resolve conventions" -- spawn notation coordinator to fix (Recommended)
  2. "Force continue" -- proceed despite inconsistency (--force-inconsistent)
  3. "Stop" -- halt and investigate manually
──────────────────────────────────────────────────────
```

**If "Resolve conventions":** Spawn gpd-notation-coordinator to fix the conflicts:

```bash
NOTATION_MODEL=$(gpd resolve-model gpd-notation-coordinator --raw)
```

```
Task(
  subagent_type="gpd-notation-coordinator",
  model="{notation_model}",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-notation-coordinator.md for your role and instructions.

<task>
Resolve convention inconsistencies found by consistency checker after phase {PHASE_NUMBER} execution.
</task>

<issues>
{consistency_checker_issues}
</issues>

<project_context>
Read: .planning/STATE.md, .planning/state.json, .planning/CONVENTIONS.md
Read: All SUMMARY.md files from phase {PHASE_NUMBER}
Load conventions: gpd convention list
</project_context>

<output>
1. Update convention lock via gpd convention set (if lock is wrong)
2. Update CONVENTIONS.md (if doc is stale)
3. Flag any phase artifacts that need re-execution with corrected conventions
4. Return CONVENTION UPDATE or CONVENTION CONFLICT
</output>
",
  description="Resolve convention conflicts after Phase {PHASE_NUMBER}"
)
```

**If the notation coordinator agent fails to spawn or returns an error:** The consistency issues remain unresolved. Offer: 1) Retry notation coordinator, 2) Resolve conflicts manually by editing CONVENTIONS.md and using `gpd convention set`, 3) Force continue with known inconsistencies (log to DECISIONS.md). Do not silently proceed — convention errors compound across phases.

Handle notation-coordinator return:
- **`CONVENTION UPDATE`:** Conventions fixed. Commit CONVENTIONS.md. If any phase artifacts were flagged for re-execution, present them to user. Continue to phase completion.
- **`CONVENTION CONFLICT`:** Unresolvable conflict requiring user decision. Present options and wait.

**If "Force continue":** Log the forced override to DECISIONS.md:

```bash
gpd state add-decision \
  --phase "${phase_number}" \
  --summary "Forced past consistency check (--force-inconsistent)" \
  --rationale "${USER_RATIONALE}"
```

**If WARNING:** Present warnings, ask user whether to proceed or investigate.
**If CONSISTENT:** Continue to phase completion.
</step>

<step name="update_roadmap">
Mark phase complete in ROADMAP.md (date, status).

Follow the full transition protocol. Read `{GPD_INSTALL_DIR}/workflows/transition.md` using the Read tool for PROJECT.md evolution, DECISIONS.md updates, and parallel phase detection.

```bash
PRE_CHECK=$(gpd pre-commit-check --files .planning/ROADMAP.md .planning/STATE.md "${phase_dir}"/*-VERIFICATION.md .planning/REQUIREMENTS.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs(phase-${phase_number}): complete phase execution" --files .planning/ROADMAP.md .planning/STATE.md "${phase_dir}"/*-VERIFICATION.md .planning/REQUIREMENTS.md
```

</step>

<step name="cleanup_phase_checkpoints">
**After successful phase completion (all plans passed + verification passed):**

Remove all `gpd-checkpoint/*` tags for this phase -- they are no longer needed.

```bash
# List all checkpoint tags for this phase
PHASE_TAGS=$(git tag -l "gpd-checkpoint/phase-${phase_number}-*")

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
| All plans passed + verification passed  | Delete all `gpd-checkpoint/phase-{X}-*` tags       |
| Any plans failed (even if kept partial) | Keep all checkpoint tags                           |
| Verification found gaps                 | Keep all checkpoint tags                           |
| Phase marked complete after gap closure | Delete checkpoint tags from successful re-run only |

</step>

<step name="offer_next">

**If more phases:**

```
## Next Up

**Phase {X+1}: {Name}** -- {Goal}

`$gpd-plan-phase {X+1}`

<sub>`/clear` first for fresh context</sub>
```

**If milestone complete:**

```
MILESTONE COMPLETE!

All {N} phases executed.

`$gpd-complete-milestone`
```

</step>

</process>

<context_efficiency>
Orchestrator: ~10-15% context. Subagents: fresh 200k each. No polling (Task blocks). No context bleed.
</context_efficiency>

<failure_handling>

- **classifyHandoffIfNeeded false failure:** See `{GPD_INSTALL_DIR}/references/known-bugs.md`. Spot-check (SUMMARY exists, commits present) -> if pass, treat as success
- **Agent fails mid-plan:** Missing SUMMARY.md -> report, route to wave_failure_handling for user decision
- **Dependency chain breaks:** Wave N plan fails -> identify Wave N+1 dependents via `depends_on` frontmatter -> auto-skip with clear message -> user chooses at wave level
- **All agents in wave fail:** Systemic issue -> stop, report for investigation, offer wave-level rollback
- **Checkpoint unresolvable:** "Skip this plan?" or "Abort phase execution?" -> record partial progress in STATE.md
- **Physics validation failure:** Dimensional inconsistency or conservation law violation detected -> STOP, do not proceed to next wave, report for investigation
  </failure_handling>

<resumption>
Re-run `$gpd-execute-phase {phase}` -> discover_plans finds completed SUMMARYs -> skips them -> resumes from first incomplete plan -> continues wave execution.

STATE.md tracks: last completed plan, current wave, pending checkpoints.

**Partial completion detection:** execute-plan's `detect_previous_attempt` step checks git log for task-level commits. Plans with partial commits offer resume-from-task-N. Plans with RECOVERY-{PLAN}.md files surface recovery options.
</resumption>
