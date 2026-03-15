<purpose>
Research mathematical methods, physical principles, and computational tools needed to approach a phase. Spawns gpd-phase-researcher with phase context.

Standalone research command. For most workflows, use `/gpd:plan-phase` which integrates research automatically.
</purpose>

<process>

## Step 0: Initialize Context

**Load phase context and resolve model:**

```bash
INIT=$(gpd init phase-op --include state,config "${PHASE}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `phase_dir`, `phase_number`, `phase_name`, `phase_found`, `autonomy`, `research_mode`.

**If `phase_found` is false:** Error and exit.

**Mode-aware behavior:**
- `research_mode=explore`: Comprehensive research — survey all viable methods, include failed approaches from literature, 10+ papers.
- `research_mode=exploit`: Focused research — direct methods only, 3-5 key papers, skip speculative approaches.
- `research_mode=adaptive`: Start broad enough to compare viable method families, then narrow only after prior decisive evidence or an explicit approach lock shows the method is stable.
- `autonomy=supervised`: Present the `RESEARCH.md` draft for user review before treating the handoff as complete.
- `autonomy=balanced/yolo`: Accept the researcher handoff automatically once `RESEARCH.md` exists and passes the artifact check.

@{GPD_INSTALL_DIR}/references/orchestration/model-profile-resolution.md

```bash
RESEARCHER_MODEL=$(gpd resolve-model gpd-phase-researcher)
```

## Step 1: Validate Phase

```bash
PHASE_INFO=$(gpd roadmap get-phase "${phase_number}")
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
cat .gpd/REQUIREMENTS.md 2>/dev/null
cat "${phase_dir}/"*-CONTEXT.md 2>/dev/null
# Decisions from gpd state snapshot (structured JSON)
gpd state snapshot | gpd json get .decisions --default "[]"
```

## Step 4: Spawn Researcher
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-phase-researcher.md for your role and instructions.

<objective>
Research mathematical methods, physical principles, and computational approaches for Phase {phase}: {name}
</objective>

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
Write to: .gpd/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md
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
    - .gpd/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md
expected_artifacts:
  - .gpd/phases/${PHASE}-{slug}/${PHASE}-RESEARCH.md
shared_state_policy: return_only
</spawn_contract>
```

Accept the researcher handoff automatically only once `expected_artifacts` exist and pass the artifact check. Do not trust the runtime handoff status by itself.

## Step 5: Handle Return

**If the researcher agent fails to spawn or returns an error:** Report the failure. Offer: 1) Retry with the same context, 2) Execute the research in the main context (slower but reliable), 3) Skip research and proceed to `/gpd:plan-phase` directly (planner will work with less context). Do not silently continue without research output.

- **Artifact gate:** If the researcher reports `## RESEARCH COMPLETE` but the `expected_artifacts` entry (`RESEARCH.md`) is missing from the phase directory, treat the handoff as incomplete. Offer: 1) Retry researcher, 2) Execute research in the main context, 3) Abort.
- `## RESEARCH COMPLETE` -- Display summary, offer: Plan/Dig deeper/Review/Done
- `## CHECKPOINT REACHED` -- Present to user, spawn continuation
- `## RESEARCH INCONCLUSIVE` -- Show attempts, offer: Add context/Try different approach/Manual

</process>

<success_criteria>
- [ ] Phase argument validated and phase info loaded
- [ ] Existing research checked (update/skip offered if present)
- [ ] Phase context gathered (roadmap section, requirements, prior decisions)
- [ ] gpd-phase-researcher spawned with physics research directives
- [ ] RESEARCH.md written to phase directory
- [ ] Research covers: mathematical framework, known solutions, limiting cases, computational methods, dimensional analysis, potential pitfalls
- [ ] Return handled (complete/checkpoint/inconclusive)
- [ ] Next action offered (plan phase, dig deeper, review)
</success_criteria>
