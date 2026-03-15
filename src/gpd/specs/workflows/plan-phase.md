<purpose>
Create executable phase prompts (PLAN.md files) for a research phase with integrated literature review and verification. Default flow: Research (if needed) -> Plan -> Verify -> Done. Orchestrates gpd-phase-researcher, gpd-planner, and gpd-plan-checker agents with a revision loop (max 3 iterations).
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.

Read these files using the file_read tool:
- {GPD_INSTALL_DIR}/references/ui/ui-brand.md
- {GPD_INSTALL_DIR}/templates/planner-subagent-prompt.md -- Template for spawning gpd-planner agents (placeholders, continuation format, failure protocol)
- {GPD_INSTALL_DIR}/templates/phase-prompt.md -- PLAN.md output format (frontmatter, task XML, contract-native wiring)
</required_reading>

<process>

## 1. Initialize

Load all context in one call (include file contents to avoid redundant reads):

```bash
INIT=$(gpd init plan-phase "$PHASE" --include state,roadmap,requirements,context,research,verification,validation)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  exit 1
fi
```

Parse JSON for: `researcher_model`, `planner_model`, `checker_model`, `research_enabled`, `plan_checker_enabled`, `commit_docs`, `autonomy`, `research_mode`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `phase_slug`, `padded_phase`, `has_research`, `has_context`, `has_plans`, `plan_count`, `planning_exists`, `roadmap_exists`, `project_contract`, `contract_intake`, `effective_reference_intake`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `protocol_bundle_verifier_extensions`, `active_reference_context`, `reference_artifacts_content`.

**File contents (from --include):** `state_content`, `roadmap_content`, `requirements_content`, `context_content`, `research_content`, `verification_content`, `validation_content`, plus reference-artifact fields from init JSON. These are null if files don't exist.

**Mode-aware behavior:**
- `autonomy=supervised`: Present the written draft plans for user review before treating them as approved or moving on to execution. Do not weaken the contract gate just because the draft is human-reviewed.
- `autonomy=balanced` (default): Write the plan and pause only if the plan-checker raises issues or the planning choices need user judgment.
- `autonomy=yolo`: Write the plan and proceed without pausing.
- `research_mode=explore`: Always run research step even if research exists. Expand wave count for thorough coverage.
- `research_mode=exploit`: Reuse existing research only when it already covers the exact method family, anchors, and decisive evidence path for this phase. Otherwise run targeted research.
- `research_mode=adaptive`: Start broad until prior decisive evidence or an explicit approach lock justifies narrowing. Do not infer “safe to narrow” from phase number alone.
- All modes still require contract completeness, decisive outputs, required anchors, forbidden-proxy handling, and disconfirming paths before execution starts.

**Set shell variables from init JSON:**

```bash
REQUESTED_PHASE="${PHASE}"
PHASE=$(echo "$INIT" | gpd json get .phase_number --default "${REQUESTED_PHASE}")
PHASE_DIR=$(echo "$INIT" | gpd json get .phase_dir --default "")
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```

**If `planning_exists` is false:** Error -- run `/gpd:new-project` first.

**If `project_contract` is empty or null:** STOP and checkpoint with the user. Planning requires an approved scoping contract in `.gpd/state.json`; do not infer phase scope from `ROADMAP.md` or `REQUIREMENTS.md` alone.

Treat `effective_reference_intake` as the machine-readable carry-forward anchor ledger for this phase. Do not rely only on the rendered `active_reference_context` prose when deciding what must stay visible.

## 2. Parse and Normalize Arguments

Extract from $ARGUMENTS: phase number (integer or decimal like `2.1`), flags (`--research`, `--skip-research`, `--gaps`, `--skip-verify`, `--light`, `--inline-discuss`).

### `--inline-discuss` Flag (Combined Discuss + Plan)

When `--inline-discuss` is present, combine discuss-phase and plan-phase into a single session. This eliminates the 3-session friction (discuss → plan → execute) for straightforward phases.

**Before step 5 (Handle Research), insert a quick gray-area probe:**

1. Read the phase goal and description from ROADMAP.md
2. Present 2-3 critical decision points to the researcher — focus on the gray areas most likely to affect planning:
   - "What formalism/method do you envision for this phase?" (if multiple valid approaches exist)
   - "Are there any constraints or conventions from prior phases that should carry through?" (if phase has dependencies)
   - "What precision level is acceptable?" (for numerical/computational phases)
3. Record responses as a lightweight CONTEXT.md in the phase directory (same format as discuss-phase output, but with only the critical decisions — skip the full Socratic dialogue)
4. Proceed to step 5 with the context populated

This is NOT the full discuss-phase flow — just the 2-3 most impactful questions. If the phase is complex enough to need full discussion, the researcher should run `/gpd:discuss-phase` separately.

**If no phase number:** Detect next unplanned phase from roadmap.

**If `phase_found` is false:** Validate phase exists in ROADMAP.md. If valid, resolve directory metadata from the roadmap before continuing:

```bash
PHASE_INFO=$(gpd roadmap get-phase "${PHASE}")
if [ "$(echo "$PHASE_INFO" | gpd json get .found --default false)" != "true" ]; then
  echo "Error: Phase ${PHASE} not found in ROADMAP.md."
  exit 1
fi

PHASE_NAME=$(echo "$PHASE_INFO" | gpd json get .phase_name --default "")
PHASE_SLUG=$(gpd slug "$PHASE_NAME")
PADDED_PHASE=$(printf '%s' "${PHASE}" | python3 -c "import sys; parts=sys.stdin.read().strip().split('.'); head=str(int(parts[0])).zfill(2); tail=[str(int(part)) for part in parts[1:] if part]; print('.'.join([head, *tail]))")
PHASE="${PADDED_PHASE}"
PHASE_DIR=".gpd/phases/${PADDED_PHASE}-${PHASE_SLUG}"
mkdir -p "${PHASE_DIR}"
```

Use these resolved values for all later references to `PHASE_DIR`, `PHASE_SLUG`, and `PADDED_PHASE`.

**Existing artifacts from init:** `has_research`, `has_plans`, `plan_count`.

## 3. Validate Phase

```bash
PHASE_INFO=$(gpd roadmap get-phase "${PHASE}")
```

**If `found` is false:** Error with available phases. **If `found` is true:** Extract `phase_number`, `phase_name`, `goal` from JSON.

## 4. Load CONTEXT.md and Hypothesis Context

Use `context_content` from init JSON (already loaded via `--include context`).

**CRITICAL:** Use `context_content` from INIT -- pass to researcher, planner, checker, and revision agents.

If `context_content` is not null, display: `Using phase context from: ${PHASE_DIR}/*-CONTEXT.md`

### Hypothesis-Aware Planning

Check if STATE.md contains an active hypothesis:

```bash
HYPOTHESIS_SECTION=$(echo "$STATE_CONTENT" | grep -A5 "## Active Hypothesis")
```

**If an active hypothesis exists:**

1. Extract the hypothesis branch slug from STATE.md
2. Read the HYPOTHESIS.md file:

```bash
HYPOTHESIS_SLUG=$(echo "$HYPOTHESIS_SECTION" | grep "Branch:" | sed 's/.*hypothesis\///')
HYPOTHESIS_FILE=".gpd/hypotheses/${HYPOTHESIS_SLUG}/HYPOTHESIS.md"
HYPOTHESIS_CONTENT=$(cat "$HYPOTHESIS_FILE" 2>/dev/null)
```

3. Display: `Active hypothesis detected: hypothesis/${HYPOTHESIS_SLUG}`
4. The hypothesis description, motivation, expected outcome, and success criteria become a **primary constraint** for all downstream agents (researcher, planner, checker). Inject the hypothesis context into every agent prompt:

```markdown
<hypothesis_constraint>
This phase is being planned on a HYPOTHESIS BRANCH. The plan must serve
the hypothesis investigation, not the default approach.

{HYPOTHESIS_CONTENT}

**Planning constraint:** Every plan task must either:
- Directly test or advance the hypothesis, OR
- Provide infrastructure required by hypothesis-specific tasks

Do NOT plan tasks that follow the parent branch approach. The parent branch
already explores that path.
</hypothesis_constraint>
```

5. Append this `<hypothesis_constraint>` block to the prompts for: gpd-phase-researcher (step 5), gpd-planner (step 8), gpd-plan-checker (step 10), and revision agents (step 12).

## 4.5. Convention Verification

**Verify conventions before planning** — plans that depend on conventions from prior phases must use the correct ones:

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — resolve before planning"
  echo "$CONV_CHECK"
fi
```

If the check fails, warn the user before spawning the researcher or planner. Convention mismatches in the plan will propagate into every task during execution.

## 5. Handle Research

**Skip if:** `--gaps` flag, `--skip-research` flag, or `research_enabled` is false (from init) without `--research` override.

**Read research mode from init JSON:**

```bash
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```

### Research Mode Decision Matrix

| Mode | RESEARCH.md exists | RESEARCH.md missing | `--research` flag |
|------|-------------------|--------------------|--------------------|
| **explore** | Re-research always (expand scope, compare alternatives, refresh anchors) | Research (comprehensive — multiple methods, broad survey) | Research (comprehensive) |
| **balanced** (default) | Skip by default, but re-research if inputs look stale or missing for the current contract slice | Research (standard) | Research (standard) |
| **exploit** | Skip only if the existing research already covers the exact method family, anchor set, and decisive evidence path; otherwise run targeted method research | Research (minimal — method-specific only, no broad survey) | Research (minimal) |
| **adaptive** | Reuse existing research only after prior decisive evidence or explicit approach-lock markers show the method is stable; otherwise refresh research in a balanced or explore-style pass | Research (broad enough to choose and lock an approach) | Research (standard) |

**If `has_research` is true (from init) AND no `--research` flag:**

Route by research mode:

```bash
if [ "$RESEARCH_MODE" = "explore" ]; then
  # Explore: always re-research for broader coverage
  echo "Research mode: explore — re-researching for comprehensive coverage"
  # Proceed to spawn researcher below
elif [ "$RESEARCH_MODE" = "exploit" ]; then
  # Exploit: reuse only if existing research already covers the exact method family
  # and contract-critical anchor/comparison path for this phase
  if echo "$INIT" | gpd json get .research_content --default "" | grep -qi "method\\|benchmark\\|anchor"; then
    echo "Research mode: exploit — existing targeted research appears sufficient"
    # Skip to step 6
  else
    echo "Research mode: exploit — existing research is too generic, refreshing targeted method context"
    # Proceed to spawn researcher below
  fi
elif [ "$RESEARCH_MODE" = "adaptive" ]; then
  # Adaptive: narrow only after prior decisive evidence or an explicit approach lock
  VALIDATED=$(ls .gpd/phases/*/*-SUMMARY.md 2>/dev/null | xargs grep -El "approach_validated: true|comparison_verdicts:|contract_results:" 2>/dev/null | head -1)
  if [ -n "$VALIDATED" ]; then
    echo "Research mode: adaptive — prior decisive evidence found, using existing research as the starting point"
    # Skip to step 6
  else
    echo "Research mode: adaptive — approach not yet locked, refreshing research before planning"
    # Proceed to spawn researcher below
  fi
else
  # Balanced (default): check staleness before skipping
  RESEARCH_MOD=$(stat -f %m "${PHASE_DIR}"/*-RESEARCH.md 2>/dev/null || stat -c %Y "${PHASE_DIR}"/*-RESEARCH.md 2>/dev/null || echo 0)
  STATE_MOD=$(stat -f %m .gpd/STATE.md 2>/dev/null || stat -c %Y .gpd/STATE.md 2>/dev/null || echo 0)
  DIFF_DAYS=$(( (STATE_MOD - RESEARCH_MOD) / 86400 ))

  if [ "$DIFF_DAYS" -gt 1 ]; then
    echo "Research may be stale (created ${RESEARCH_MOD}, state updated ${STATE_MOD}). Re-research with --research?"
    # If user chooses to re-research, proceed to spawn researcher below. Otherwise, use existing and skip to step 6.
  fi
fi
```

**If RESEARCH.md missing OR `--research` flag OR explore mode with existing research:**

Display banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > RESEARCHING PHASE {X}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

* Spawning researcher...
```

### Spawn gpd-phase-researcher
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```bash
PHASE_DESC=$(gpd roadmap get-phase "${PHASE}" | gpd json get .section --default "")
# Use requirements_content from INIT (already loaded via --include requirements)
REQUIREMENTS=$(echo "$INIT" | gpd json get .requirements_content --default "" | grep -A100 "## Requirements" | head -50)
STATE_SNAP=$(gpd state snapshot)
# Extract decisions from gpd state snapshot JSON: echo "$STATE_SNAP" | gpd json list .decisions
```

Research prompt:

```markdown
<objective>
Research how to approach Phase {phase_number}: {phase_name}
Answer: "What mathematical methods, physical principles, and computational tools do I need to PLAN this phase rigorously?"
</objective>

<phase_context>
IMPORTANT: If CONTEXT.md exists below, it contains user decisions from /gpd:discuss-phase.

- **Decisions** = Locked -- research THESE deeply, no alternatives
- **Agent's Discretion** = Freedom areas -- research options, recommend
- **Deferred Ideas** = Out of scope -- ignore

{context_content}
</phase_context>

<additional_context>
**Phase description:** {phase_description}
**Requirements:** {requirements}
**Prior decisions:** {decisions}
**Project contract:** {project_contract}
**Active references:** {active_reference_context}
**Reference artifacts:** {reference_artifacts_content}
</additional_context>

<research_mode>{RESEARCH_MODE}</research_mode>

<physics_research_focus>

**Research depth by mode:**
- **explore:** COMPREHENSIVE — survey ALL viable methods, compare 3+ approaches, include failed approaches from literature, broad literature search (10+ papers), identify unexplored angles
- **balanced** (default): STANDARD — identify best approach, document known difficulties, targeted literature (5-7 key papers)
- **exploit:** MINIMAL — method-specific details only (parameters, convergence criteria, implementation notes). Skip broad survey. Only papers directly relevant to the exact computation.
- **adaptive:** Use explore-style until prior decisive evidence or an explicit approach lock shows the method family is stable. Then narrow to a balanced or exploit-style pass for the locked method.

**Core research areas (all modes):**
- **Mathematical framework:** Identify the governing equations, symmetry groups, relevant Hilbert spaces, or variational principles
- **Known solutions:** Find exact solutions, standard approximations (perturbative, WKB, mean-field), and their regimes of validity
- **Limiting cases:** Identify all limiting cases that must be recovered (classical limit, weak-coupling, non-relativistic, thermodynamic limit, etc.)
- **Computational methods:** Survey numerical approaches (finite element, Monte Carlo, spectral methods) and existing packages
- **Literature:** Key papers, textbook treatments, and review articles relevant to this phase
- **Dimensional analysis:** Identify natural scales and dimensionless parameters that govern the physics
</physics_research_focus>

<output>
Write to: {phase_dir}/{phase}-RESEARCH.md
</output>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.\n\n" + research_prompt,
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false,
  description="Research Phase {phase}"
)
```

**If the researcher agent fails to spawn or returns an error:** Report the failure. Offer: 1) Retry with the same context, 2) Execute the research in the main context (slower but reliable), 3) Skip research and proceed directly to planning (planner will work with less context). Do not silently continue without research output.

### Handle Researcher Return

- **`## RESEARCH COMPLETE`:** Verify RESEARCH.md exists (below), then display confirmation, continue to step 6
- **`## RESEARCH BLOCKED`:** Display blocker, offer: 1) Provide context, 2) Skip research, 3) Abort

**Verify RESEARCH.md was written (guard against silent researcher failure):**

```bash
if ! ls "${PHASE_DIR}"/*-RESEARCH.md 1>/dev/null 2>&1; then
  echo "WARNING: Researcher agent returned but RESEARCH.md was not created."
fi
```

If RESEARCH.md is missing after the researcher returned, present:

```
WARNING: Researcher completed but did not write RESEARCH.md.

Options:
1. Retry research (re-spawn researcher)
2. Continue without research (planner will have no research context)
3. Abort
```

Wait for user decision before proceeding to step 6.

## 5.5. Experiment Design (Numerical/Computational Phases)

**Skip if:** `--light` flag, `--skip-research` flag, or the phase description does not involve numerical computation.

**Research mode effects on experiment design:**

| Mode | Experiment Designer | Rationale |
|------|-------------------|-----------|
| **explore** | Always spawn (even if numerical indicators are weak) | Broad exploration benefits from structured experiment design |
| **balanced** | Spawn if numerical indicators detected (default behavior) | Standard heuristic |
| **exploit** | Skip unless EXPERIMENT-DESIGN.md is explicitly required by CONTEXT.md | Exploit mode minimizes overhead |
| **adaptive** | Follow balanced behavior until prior decisive evidence or an explicit approach lock stabilizes the method family; then reuse validated experiment templates for the locked approach | Evidence-driven reuse once the method is stable |

**Detection:** Check the phase goal and research content for numerical indicators:

```bash
PHASE_GOAL=$(echo "$INIT" | gpd json get .phase_name --default "")

# Re-read RESEARCH.md from disk — the value from INIT (step 1) is stale
# because the researcher in step 5 may have just created/updated it.
RESEARCH_FILE=$(ls "${PHASE_DIR}"/*-RESEARCH.md 2>/dev/null | head -1)
if [ -n "$RESEARCH_FILE" ]; then
  RESEARCH_CONTENT=$(cat "$RESEARCH_FILE")
fi
```

Scan `PHASE_GOAL` and `RESEARCH_CONTENT` for indicators of computational work: "Monte Carlo", "simulation", "numerical", "finite-size", "convergence", "parameter sweep", "benchmark", "grid", "discretization", "timestep", "sampling".

**If numerical indicators found AND no existing EXPERIMENT-DESIGN.md:**

Display banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > DESIGNING NUMERICAL EXPERIMENT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

* Spawning experiment designer...
```

### Spawn gpd-experiment-designer

```bash
EXPERIMENT_MODEL=$(gpd resolve-model gpd-experiment-designer)
```

Experiment design prompt:

```markdown
<objective>
Design the numerical experiment protocol for Phase {phase_number}: {phase_name}
</objective>

<phase_context>
**Phase description:** {phase_description}
**Research:** {research_content}
**Conventions:** $(gpd --raw convention list 2>/dev/null)
**Context:** {context_content}
</phase_context>

<output>
Write to: {phase_dir}/{phase}-EXPERIMENT-DESIGN.md
</output>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-experiment-designer.md for your role and instructions.\n\n" + experiment_prompt,
  subagent_type="gpd-experiment-designer",
  model="{experiment_model}",
  readonly=false,
  description="Design experiment for Phase {phase}"
)
```

### Handle Experiment Designer Return

**If the experiment designer agent fails to spawn or returns an error:** Experiment design is optional supplementary context for the planner. Proceed without it — the planner will work with RESEARCH.md and CONTEXT.md. Note that experiment design was skipped.

- **`EXPERIMENT DESIGN COMPLETE`:** Verify EXPERIMENT-DESIGN.md exists, display confirmation, continue to step 6
- **`DESIGN BLOCKED`:** Display blocker, offer: 1) Provide context, 2) Skip experiment design, 3) Abort

**If EXPERIMENT-DESIGN.md created:** The planner (step 8) receives this as additional context. Add to the planner prompt:

```markdown
**Experiment Design:** {experiment_design_content}
```

**If no numerical indicators OR `--light` mode:** Skip silently.

## 6. Check Existing Plans

```bash
ls "${PHASE_DIR}"/*-PLAN.md 2>/dev/null
```

**If exists:** Offer: 1) Add more plans, 2) View existing, 3) Replan from scratch.

## 7. Use Context Files from INIT

Most file contents are already loaded via `--include` in step 1 (`@` syntax doesn't work across task() boundaries):

```bash
# Extract from INIT JSON
STATE_CONTENT=$(echo "$INIT" | gpd json get .state_content --default "")
ROADMAP_CONTENT=$(echo "$INIT" | gpd json get .roadmap_content --default "")
REQUIREMENTS_CONTENT=$(echo "$INIT" | gpd json get .requirements_content --default "")
VERIFICATION_CONTENT=$(echo "$INIT" | gpd json get .verification_content --default "")
UAT_CONTENT=$(echo "$INIT" | gpd json get .validation_content --default "")
CONTEXT_CONTENT=$(echo "$INIT" | gpd json get .context_content --default "")
PROJECT_CONTRACT=$(echo "$INIT" | gpd json get .project_contract --default "")
PROTOCOL_BUNDLE_CONTEXT=$(echo "$INIT" | gpd json get .protocol_bundle_context --default "")
ACTIVE_REFERENCE_CONTEXT=$(echo "$INIT" | gpd json get .active_reference_context --default "")
REFERENCE_ARTIFACTS_CONTENT=$(echo "$INIT" | gpd json get .reference_artifacts_content --default "")
```

**CRITICAL: Re-read RESEARCH.md from disk if the researcher was spawned in step 5.**

The `research_content` from INIT (step 1) is **stale** — it was loaded before the researcher wrote RESEARCH.md.
If you pass the stale INIT value to the planner, the planner will plan WITHOUT the researcher's output.
**ALWAYS** read the fresh file from disk after step 5 completes:

```bash
# Re-read RESEARCH.md from disk (researcher may have just created/updated it)
RESEARCH_FILE=$(ls "${PHASE_DIR}"/*-RESEARCH.md 2>/dev/null | head -1)
if [ -n "$RESEARCH_FILE" ]; then
  RESEARCH_CONTENT=$(cat "$RESEARCH_FILE")
else
  RESEARCH_CONTENT=$(echo "$INIT" | gpd json get .research_content --default "")
fi
```

**Load EXPERIMENT-DESIGN.md if it was created in step 5.5:**

```bash
EXPERIMENT_FILE=$(ls "${PHASE_DIR}"/*-EXPERIMENT-DESIGN.md 2>/dev/null | head -1)
if [ -n "$EXPERIMENT_FILE" ]; then
  EXPERIMENT_DESIGN_CONTENT=$(cat "$EXPERIMENT_FILE")
fi
```

## 8. Spawn gpd-planner Agent

Display banner:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PLANNING PHASE {X}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

* Spawning planner...
```

Planner prompt:

```markdown
<planning_context>
**Phase:** {phase_number}
**Mode:** {standard | gap_closure}
**Plan depth:** {full | light}
**Research mode:** {RESEARCH_MODE}
**Autonomy:** {AUTONOMY}

Planning requires an approved project contract. If `{project_contract}` is empty, stale, or too underspecified to identify the phase contract slice, return `## CHECKPOINT REACHED` instead of writing or revising plans from inferred scope.

**Project State:** {state_content}
**Project Contract:** {project_contract}
**Roadmap:** {roadmap_content}
**Requirements:** {requirements_content}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

**Phase Context:**
IMPORTANT: If context exists below, it contains USER DECISIONS from /gpd:discuss-phase.

- **Decisions** = LOCKED -- honor exactly, do not revisit
- **Agent's Discretion** = Freedom -- make methodological choices
- **Deferred Ideas** = Out of scope -- do NOT include

{context_content}

**Research:** {research_content}
**Experiment Design (if exists):** {experiment_design_content}
**Gap Closure (if --gaps):** {verification_content} {validation_content}
</planning_context>

<physics_planning_requirements>
Each plan MUST include:

- **Mathematical rigor checkpoints:** Points where derivations must be verified for dimensional consistency, symmetry preservation, and correct tensor structure
- **Limiting case validation:** Explicit checks that results reduce correctly in all known limits (classical, non-relativistic, weak-coupling, thermodynamic, etc.)
- **Order-of-magnitude estimates:** Before any detailed calculation, estimate the expected scale of the answer
- **Error budget:** For numerical work, specify target precision and identify dominant error sources
- **Consistency checks:** Cross-checks between independent methods or approaches where possible
- **Anchor discipline:** If a benchmark, paper, dataset, or prior artifact is contract-critical, surface it in the plan instead of treating it as optional background
- **Contract completeness:** Every plan must include claims, deliverables, references, acceptance tests, forbidden proxies, and uncertainty markers in frontmatter
- **Protocol bundle coverage:** If protocol bundles are selected, carry their estimator policies, decisive artifact guidance, and verifier extensions into the plan explicitly
</physics_planning_requirements>

<contract_requirements>
Planning requires `project_contract`:

- If `project_contract` is empty, stale, or too underspecified to identify the phase contract slice, return `## CHECKPOINT REACHED` instead of writing a weak or guessed plan.
- Every PLAN.md must include a `contract` frontmatter block with exact IDs for claims, deliverables, references, acceptance tests, and forbidden proxies.
- Every PLAN.md must carry forward required context from the contract: must-read refs, prior outputs, baselines, and user anchors when execution depends on them.
- Every PLAN.md must include uncertainty markers from the contract when they constrain interpretation or verification.
- Every PLAN.md should express result wiring through `contract.links` or explicit task/verification handoffs, not through a second ad hoc success schema.
- Validate each finished plan with `gpd validate plan-contract <PLAN.md>` before treating it as approved.
- Autonomy mode and model profile may change cadence or detail, but they do NOT relax contract completeness.
</contract_requirements>

<light_mode_instructions>
**If plan depth is `light`:** Keep the full canonical frontmatter, including `wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, and `contract`.

Simplify only the body: one high-level task block per plan, concise verification, concise success criteria. The light plan is a shorter execution script, not a strategic outline that drops required contract fields.
</light_mode_instructions>

<context_budget_guidance>
Context windows are finite (~200k tokens, ~80% usable). Plans must be sized accordingly:

- **Target per plan:** ~50% context budget (40% for hypothesis-driven plans)
- **Segment large phases** into multiple plans rather than one overloaded plan
- **Flag context-heavy plans** in frontmatter: `context_note: "Heavy - consider splitting if >6 tasks"`
- **Group related tasks** that share intermediate results in the same plan
- **Use waves** for independent work -- each subagent gets a fresh context window

**Signs a plan needs splitting:** >6-8 substantive tasks, multiple independent derivations, tasks requiring different large reference files, mix of symbolic derivation and numerical verification.

See `{GPD_INSTALL_DIR}/references/orchestration/context-budget.md` for detailed budget allocation by workflow type.
</context_budget_guidance>

<downstream_consumer>
Output consumed by /gpd:execute-phase. Plans need:

- Frontmatter (wave, depends_on, files_modified, interactive, contract)
- Tasks in XML format
- Verification criteria with mathematical rigor requirements
- contract-complete frontmatter before execution starts
- contract links or explicit task-level dependency wiring for critical handoffs, including limiting-case checks
- protocol-bundle guidance reflected in task structure, verification, and decisive artifact selection when applicable
</downstream_consumer>

<quality_gate>

- [ ] PLAN.md files created in phase directory
- [ ] Each plan has valid frontmatter
- [ ] Each plan has a complete contract block (claims, deliverables, references, acceptance tests, forbidden proxies, uncertainty markers)
- [ ] Each plan passes `gpd validate plan-contract <PLAN.md>`
- [ ] Tasks are specific and actionable with clear mathematical deliverables
- [ ] Dependencies correctly identified (including prerequisite derivations)
- [ ] Waves assigned for parallel execution
- [ ] Contract links or explicit task-level dependency wiring cover the decisive handoffs and limiting-case recovery path
- [ ] Required refs, prior outputs, and baselines are surfaced in `<context>` or verification paths
- [ ] Selected protocol bundles are reflected in verification paths or decisive artifact choices where relevant
- [ ] Forbidden proxies are rejected explicitly in `<done>` or `<success_criteria>`
- [ ] Dimensional analysis check specified for each quantitative result
- [ ] Validation checkpoints placed after each major derivation step
</quality_gate>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.\n\n" + filled_prompt,
  subagent_type="gpd-planner",
  model="{planner_model}",
  readonly=false,
  description="Plan Phase {phase}"
)
```

## 9. Handle Planner Return

**If the planner agent fails to spawn or returns an error:** Check if any PLAN.md files were written to the phase directory (agents write files first). If plans exist, proceed as if PLANNING COMPLETE. If no plans, offer: 1) Retry planner, 2) Create plans in the main context, 3) Abort.

- **`## PLANNING COMPLETE`:** Display plan count. If `AUTONOMY=supervised`, show the written draft plans and get user confirmation before advancing to checker or next-step output. If `--skip-verify` or `plan_checker_enabled` is false (from init): skip to step 13. Otherwise: step 10.
- **`## CHECKPOINT REACHED`:** Present to user, get response, spawn continuation (step 12)
- **`## PLANNING INCONCLUSIVE`:** Show attempts, offer: Add context / Retry / Manual

## 10. Spawn gpd-plan-checker Agent

Display banner (include iteration count if in revision loop):

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > VERIFYING PLANS (attempt {iteration_count}/3)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

* Spawning plan checker...
```

```bash
PLANS_CONTENT=$(cat "${PHASE_DIR}"/*-PLAN.md 2>/dev/null)
```

Checker prompt:

```markdown
<verification_context>
**Phase:** {phase_number}
**Phase Goal:** {goal from ROADMAP}

**Plans to verify:** {plans_content}
**Requirements:** {requirements_content}
**Project Contract:** {project_contract}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Reference Artifacts:** {reference_artifacts_content}

**Phase Context:**
IMPORTANT: Plans MUST honor user decisions. Flag as issue if plans contradict.

- **Decisions** = LOCKED -- plans must implement exactly
- **Agent's Discretion** = Freedom areas -- plans can choose approach
- **Deferred Ideas** = Out of scope -- plans must NOT include

{context_content}
</verification_context>

<physics_verification_criteria>
In addition to structural checks, verify:

- [ ] **Dimensional consistency:** All equations are dimensionally correct
- [ ] **Limiting cases specified:** Plans identify which limits must be recovered and where checks occur
- [ ] **Approximation validity:** Each approximation has stated regime of validity and error estimates
- [ ] **Conservation laws:** Plans respect relevant conservation laws (energy, momentum, charge, unitarity, etc.)
- [ ] **Symmetry preservation:** Approximations and numerical methods preserve relevant symmetries
- [ ] **Independent cross-checks:** At least one independent verification method per major result
- [ ] **Order-of-magnitude sanity:** Expected scales are stated before detailed calculations
- [ ] **Anchor coverage:** Required references, baselines, and prior outputs are surfaced where the plan depends on them
- [ ] **Protocol-bundle coverage:** Selected protocol bundles are reflected in task structure, estimator guards, decisive artifacts, or verification paths
- [ ] **Contract completeness:** Each plan includes decisive claims, deliverables, acceptance tests, forbidden proxies, and uncertainty markers
- [ ] **Decisive outputs:** The plan set covers decisive claims and deliverables rather than only infrastructure or proxy work
- [ ] **Acceptance tests:** Every decisive claim or deliverable has at least one executable or reviewable test
- [ ] **Disconfirming path:** Risky plans name the observation or comparison that would force a rethink
- [ ] **Forbidden proxies:** Proxy-only success conditions are rejected explicitly
</physics_verification_criteria>

<expected_output>

- ## VERIFICATION PASSED -- all checks pass
- ## ISSUES FOUND -- structured issue list
- ## PARTIAL APPROVAL -- some plans approved, others need revision (see partial_approval protocol in your agent instructions)
</expected_output>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-plan-checker.md for your role and instructions.\n\n" + checker_prompt,
  subagent_type="gpd-plan-checker",
  model="{checker_model}",
  readonly=false,
  description="Verify Phase {phase} plans"
)
```

## 11. Handle Checker Return

**If the plan-checker agent fails to spawn or returns an error:** Proceed without plan verification. Plans are still executable. Note that verification was skipped and recommend the user review the plans manually before executing.

- **`## VERIFICATION PASSED`:** Display iteration-aware confirmation and proceed to step 13:

  ```
  Plan passed checker (attempt {iteration_count}/3)
  ```

- **`## ISSUES FOUND`:** Display iteration-aware status, show issues, check iteration count, proceed to step 12:

  ```
  Checker found {N} issues (attempt {iteration_count}/3). Revising plan...
  ```

- **`## PARTIAL APPROVAL`:** Some plans passed, others need revision. Split the work:

  1. Record approved plans (from the checker's "Approved Plans" table)
  2. Display status:

     ```
     Partial approval (attempt {iteration_count}/3): {N_approved} plans approved, {N_blocked} need revision
     ```

  3. Send ONLY the blocked plans to the revision loop (step 12). Pass the checker's blocker details as `{structured_issues_from_checker}`. Do NOT re-check already-approved plans unless their inputs change during revision.
  4. After revision + re-check cycle, if the re-check returns VERIFICATION PASSED for the revised plans, merge approved sets and proceed to step 13. If it returns PARTIAL APPROVAL again, repeat. If ISSUES FOUND, enter standard revision loop for remaining plans.
  5. Approved plans from partial approval are final — they proceed to execution regardless of the revision outcome for blocked plans.

## 12. Revision Loop (Max 3 Iterations)

Maximum iterations: 3. After 3 rejections by the plan-checker:
1. Present the best plan to the user with the checker's remaining objections
2. Ask: "The plan-checker has rejected this plan 3 times. Would you like to: (a) proceed anyway, (b) modify the plan manually, or (c) abandon this phase?"
3. Do NOT loop indefinitely

Track `iteration_count` (starts at 1 after initial plan + check).

**If iteration_count < 3:**

Display: `Checker found issues, revising plan (attempt {N}/3)...`

```bash
# If PARTIAL APPROVAL: only load blocked plans (stored in BLOCKED_PLANS list from step 11)
# If ISSUES FOUND: load all plans
if [ -n "$BLOCKED_PLANS" ]; then
  PLANS_CONTENT=""
  for plan_id in $BLOCKED_PLANS; do
    PLANS_CONTENT="${PLANS_CONTENT}$(cat "${PHASE_DIR}"/*-${plan_id}-PLAN.md 2>/dev/null)"
  done
else
  PLANS_CONTENT=$(cat "${PHASE_DIR}"/*-PLAN.md 2>/dev/null)
fi
```

Revision prompt:

```markdown
<revision_context>
**Phase:** {phase_number}
**Mode:** revision

**Existing plans:** {plans_content}
**Checker issues:** {structured_issues_from_checker}
**Protocol Bundles:** {protocol_bundle_context}
**Active References:** {active_reference_context}
**Project Contract:** {project_contract}
**Reference Artifacts:** {reference_artifacts_content}

**Phase Context:**
Revisions MUST still honor user decisions.
{context_content}
</revision_context>

<instructions>
Make targeted updates to address checker issues.
Do NOT replan from scratch unless issues are fundamental (e.g., wrong physical regime, missing conservation law, incorrect symmetry).
If the approved project contract is missing or no longer sufficient to identify the right phase slice, return `## CHECKPOINT REACHED` instead of patching plans against guessed scope.
Pay special attention to:
- Dimensional consistency fixes
- Missing limiting case checks
- Approximation validity bounds
- Missing decisive outputs or deliverables
- Missing acceptance tests, anchor refs, or forbidden-proxy handling
- Missing protocol-bundle-driven estimator guards, decisive artifacts, or verifier extensions
- Missing disconfirming paths
Return what changed.
</instructions>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions.\n\n" + revision_prompt,
  subagent_type="gpd-planner",
  model="{planner_model}",
  readonly=false,
  description="Revise Phase {phase} plans"
)
```

**If the revision planner agent fails to spawn or returns an error:** Check if any revised PLAN.md files were written. If revisions exist, proceed to re-check (step 10). If no revisions, offer: 1) Retry revision planner, 2) Apply revisions manually in the main context using checker feedback, 3) Force proceed with current plans despite checker issues.

After planner returns -> spawn checker again (step 10), increment iteration_count. If revising from PARTIAL APPROVAL, only pass the revised plans (not already-approved plans) to the checker.

**If iteration_count >= 3:**

Display: `Max iterations reached. {N} issues remain:` + issue list

Offer: 1) Force proceed, 2) Provide guidance and retry, 3) Abandon

## 13. Present Final Status

Route to `<offer_next>`.

</process>

<offer_next>
Output this markdown directly (not as a code block):

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PHASE {X} PLANNED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Phase {X}: {Name}** -- {N} plan(s) in {M} wave(s)

| Wave | Plans  | What it builds |
| ---- | ------ | -------------- |
| 1    | 01, 02 | [objectives]   |
| 2    | 03     | [objective]    |

Research: {Completed | Used existing | Skipped}
Verification: {Passed | Partial (N approved, M revised) | Passed with override | Skipped}

---

## >> Next Up

**Execute Phase {X}** -- run all {N} plans

/gpd:execute-phase {X}

<sub>/clear first -> fresh context window</sub>

---

**Also available:**

- cat .gpd/phases/{phase-dir}/\*-PLAN.md -- review plans
- /gpd:plan-phase {X} --research -- re-research first

---

</offer_next>

<success_criteria>

- [ ] .gpd/ directory validated
- [ ] Phase validated against roadmap
- [ ] Phase directory created if needed
- [ ] CONTEXT.md loaded early (step 4) and passed to ALL agents
- [ ] Research completed (unless --skip-research or --gaps or exists)
- [ ] gpd-phase-researcher spawned with CONTEXT.md
- [ ] gpd-experiment-designer spawned for numerical phases (unless --light or no numerical indicators)
- [ ] Existing plans checked
- [ ] gpd-planner spawned with CONTEXT.md + RESEARCH.md
- [ ] Plans created (PLANNING COMPLETE or CHECKPOINT handled)
- [ ] gpd-plan-checker spawned with CONTEXT.md
- [ ] Verification passed OR user override OR max iterations with user decision
- [ ] Plans include dimensional consistency checks
- [ ] Plans include limiting case validation
- [ ] Plans include approximation validity bounds
- [ ] User sees status between agent spawns
- [ ] User knows next steps
</success_criteria>
