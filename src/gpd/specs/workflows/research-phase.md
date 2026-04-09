<purpose>
Research mathematical methods, physical principles, and computational tools needed to approach a phase. Spawns gpd-phase-researcher with phase context.

Standalone, one-shot research command. For most workflows, use `gpd:plan-phase` which integrates research automatically.
</purpose>

<process>

## Step 0: Initialize Context

**Load phase context and resolve model:**

```bash
load_research_phase_stage() {
  local stage_name="$1"
  local phase_arg="$2"
  local init_payload=""

  init_payload=$(gpd --raw init research-phase "${phase_arg}" --stage "${stage_name}" 2>/dev/null)
  if [ $? -ne 0 ] || [ -z "$init_payload" ]; then
    echo "ERROR: staged gpd initialization failed for stage '${stage_name}': ${init_payload}"
    return 1
  fi

  printf '%s' "$init_payload"
  return 0
}

BOOTSTRAP_INIT=$(load_research_phase_stage phase_bootstrap "${PHASE}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $BOOTSTRAP_INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `autonomy`, `research_mode`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`.

```bash
RESEARCH_MODE=$(echo "$BOOTSTRAP_INIT" | gpd json get .research_mode --default balanced)
```

The init-derived `RESEARCH_MODE` is the single source of truth for depth; do not re-query config later in the workflow.

**If `phase_found` is false:** Error and exit.

**Mode-aware behavior:**
- `research_mode=explore`: Comprehensive research — survey all viable methods, include failed approaches from literature, 10+ papers.
- `research_mode=exploit`: Focused research — direct methods only, 3-5 key papers, skip speculative approaches.
- `research_mode=balanced` (default): Use the standard research depth for this workflow and keep the default contract and anchor coverage unless the topic calls for broader or narrower review.
- `research_mode=adaptive`: Start broad enough to compare viable method families, then narrow only after prior decisive evidence or an explicit approach lock shows the method family is stable.
- `autonomy=supervised`: Present the `RESEARCH.md` draft for user review before treating the handoff as complete.
- `autonomy=balanced`: Accept the researcher handoff automatically once `RESEARCH.md` exists and passes the artifact check, then present the research summary before returning control.
- `autonomy=yolo`: Accept the researcher handoff automatically once `RESEARCH.md` exists and passes the artifact check without any extra summary-review pause.

@{GPD_INSTALL_DIR}/references/orchestration/model-profile-resolution.md

```bash
RESEARCHER_MODEL=$(gpd resolve-model gpd-phase-researcher)
```

## Step 1: Validate Phase

```bash
PHASE_INFO=$(gpd --raw roadmap get-phase "${phase_number}")
```

If `found` is false: Error and exit. Extract `goal` and `section` from JSON.

## Step 2: Check Existing Research

```bash
ls "${phase_dir}/"*-RESEARCH.md 2>/dev/null
```

If exists: Offer update/view/skip options.

## Step 3: Gather Phase Context

```bash
# Phase section from roadmap (already loaded in PHASE_INFO)
echo "$PHASE_INFO" | gpd json get .section --default ""
cat GPD/REQUIREMENTS.md 2>/dev/null
cat "${phase_dir}/"*-CONTEXT.md 2>/dev/null
# Decisions from gpd state snapshot (structured JSON)
gpd --raw state snapshot | gpd json get .decisions --default "[]"
```

## Step 4: Spawn Researcher

Load the heavier handoff slice only after phase validation, existing-research routing, and context gathering are complete:

This is a one-shot handoff: if the researcher needs user input, it must return a checkpoint rather than wait in place.

```bash
HANDOFF_INIT=$(load_research_phase_stage research_handoff "${phase_number}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $HANDOFF_INIT"
  exit 1
fi
```

Use the staged refresh for `contract_intake`, `effective_reference_intake`, `active_reference_context`, `reference_artifact_files`, `reference_artifacts_content`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `state_content`, `config_content`, and `roadmap_content` before assembling the child handoff.

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.

<objective>
Research mathematical methods, physical principles, and computational approaches for Phase {phase}: {name}
</objective>

Research depth: use the active workflow research_mode from init/config ({RESEARCH_MODE}).

<context>
Phase description: {description}
Requirements: {requirements}
Prior decisions: {decisions}
Phase context: {context_md}
</context>

<physics_research_directives>
Structure your research around these areas:

**1. Mathematical Framework**
- Governing equations (PDEs, ODEs, integral equations, variational principles)
- Symmetry groups and conservation laws (Noether's theorem applications)
- Relevant function spaces, Hilbert spaces, or manifold structures
- Boundary and initial conditions

**2. Known Solutions and Standard Results**
- Exact solutions (if any) and their derivations
- Standard approximation schemes: perturbation theory, WKB, mean-field, saddle-point, renormalization group
- Regimes of validity for each approximation (dimensionless parameter ranges)
- Textbook treatments and key review articles

**3. Limiting Cases**
- All physically meaningful limits that must be recovered
- Classical limit (hbar -> 0), non-relativistic limit (v/c -> 0), thermodynamic limit (N -> infinity)
- Weak and strong coupling limits
- Known asymptotic behaviors and scaling laws

**4. Computational Methods**
- Numerical approaches: finite element, spectral methods, Monte Carlo, tensor networks, molecular dynamics
- Existing software packages and libraries (e.g., QuTiP, SciPy, FEniCS, LAMMPS, Quantum ESPRESSO)
- Convergence properties and error scaling
- Parallelization and performance considerations

**5. Dimensional Analysis and Natural Scales**
- Identify all relevant physical scales (energy, length, time, temperature)
- Construct dimensionless parameters that govern the physics
- Determine which regime the problem lives in

**6. Potential Pitfalls**
- Known numerical instabilities or ill-conditioned problems
- Gauge choices, regularization requirements, renormalization subtleties
- Sign conventions and notation conflicts across literature
- Common errors in the literature for this class of problems
</physics_research_directives>

<output>
Write to: {phase_dir}/{phase_number}-RESEARCH.md
</output>",
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false
)
```

Add this contract inside the spawned prompt when adapting it:

```markdown
<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - {phase_dir}/{phase_number}-RESEARCH.md
expected_artifacts:
  - {phase_dir}/{phase_number}-RESEARCH.md
shared_state_policy: return_only
</spawn_contract>
```

Accept the researcher handoff automatically only once `expected_artifacts` exist and pass the artifact check. Do not trust the runtime handoff status by itself.
Human-readable headings such as `## RESEARCH COMPLETE` and `## CHECKPOINT REACHED` are presentation only; route on `gpd_return.status`, `gpd_return.files_written`, and the artifact gate.

## Step 5: Handle Return

**If the researcher agent fails to spawn or returns an error:** Report the failure. Offer: 1) Retry with the same context, 2) Execute the research in the main context (slower but reliable), 3) Skip research and proceed to `gpd:plan-phase` directly (planner will work with less context). Do not silently continue without research output.

- **Artifact gate:** If `gpd_return.status: completed` but the `expected_artifacts` entry (`RESEARCH.md`) is missing from the phase directory or absent from `gpd_return.files_written`, treat the handoff as incomplete. Offer: 1) Retry researcher, 2) Execute the research in the main context, 3) Abort.
- `gpd_return.status: completed` -- Display summary, offer: Plan/Dig deeper/Review/Done
- `gpd_return.status: checkpoint` -- Present the checkpoint to the user, collect the response, and spawn a fresh continuation handoff. Do not resume the same spawned run.
- `gpd_return.status: blocked` or `failed` -- Show attempts, offer: Add context/Try different approach/Manual

## Step 6: Spawn Continuation Researcher

```markdown
<objective>
Continue research as a fresh continuation handoff for Phase {phase_number}: {phase_name}
</objective>

<prior_state>
Research file path: {phase_dir}/{phase_number}-RESEARCH.md
Read that file before continuing so you inherit the prior research state instead of relying on inline prompt state.
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - {phase_dir}/{phase_number}-RESEARCH.md
expected_artifacts:
  - {phase_dir}/{phase_number}-RESEARCH.md
shared_state_policy: return_only
</spawn_contract>
```

```bash
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.\n\n" + continuation_prompt,
  subagent_type="gpd-phase-researcher",
  model="{researcher_model}",
  readonly=false,
  description="Continue research Phase {phase}"
)
```

</process>

<success_criteria>
- [ ] Phase argument validated and phase info loaded
- [ ] Existing research checked (update/skip offered if present)
- [ ] Phase context gathered (roadmap section, requirements, prior decisions)
- [ ] gpd-phase-researcher spawned with physics research directives
- [ ] RESEARCH.md written to phase directory and named in `gpd_return.files_written`
- [ ] Research return handled via typed `gpd_return.status` and artifact gating
- [ ] Research covers: mathematical framework, known solutions, limiting cases, computational methods, dimensional analysis, potential pitfalls
- [ ] Return handled (complete/checkpoint/inconclusive)
- [ ] Next action offered (plan phase, dig deeper, review)
</success_criteria>
