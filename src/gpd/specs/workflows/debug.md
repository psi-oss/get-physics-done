<purpose>
Orchestrate parallel investigation agents to diagnose research problems and find root causes.

After verification finds issues, spawn one investigation agent per issue. Each agent investigates independently with symptoms pre-filled from verification. Collect root causes, update `VERIFICATION.md` gaps with diagnosis, then hand off to `plan-phase --gaps` with actual diagnoses.

Research problems include: calculation errors, numerical instabilities, theoretical inconsistencies, missing physics, wrong approximations, sign errors, convergence failures, unphysical results.

Orchestrator stays lean: parse gaps, spawn agents, collect results, update verification.
</purpose>

<mode_detection>

## Mode Detection

Check invocation context:
- **If called by verify-work** (batch mode): Process all gaps from VERIFICATION.md in parallel. Use `DEBUG-{slug}.md` naming. Return to verify-work.
- **If called by user** (interactive mode): Single issue investigation. Use `{slug}.md` naming. Interactive loop with user.

Detection: If `$ARGUMENTS` contains `--batch` or if `gaps_from_verification` context exists, use batch mode.

**Batch mode:** Parse all gaps from VERIFICATION.md, spawn parallel agents, collect results, update VERIFICATION.md, return to caller.

**Interactive mode:** Present issue to user, investigate interactively, create debug session file, offer next steps.
</mode_detection>

<paths>
DEBUG_DIR=GPD/debug

Debug files use the `GPD/debug/` path.
</paths>

<quick_triage>

## Quick Triage

Before full investigation, match the discrepancy signature against common patterns:

| Signature | Most Likely Cause | First Check |
|-----------|------------------|-------------|
| Factor of 2 | Spin/identical particle symmetrization, missing 1/2 | Check particle statistics |
| Factor of 2pi | Fourier convention mismatch | Check FT convention in CONVENTIONS.md |
| Factor of 4pi | Gaussian vs SI units | Check unit system |
| Sign flip | Metric convention, time-ordering sign | Check metric signature |
| Wrong power law | Dimension error, wrong scaling limit | Dimensional analysis |
| Off by order of magnitude | Unit conversion error | Track units step-by-step |
| Complex when should be real | Wrong branch cut, missing hermitian conjugate | Check analytic structure |
| Divergent/infinite result | Missing regularization, zero mode, wrong contour | Check regularization scheme |
| Non-conservation (energy, charge) | Missing connection terms, wrong operator ordering | Verify continuity equations |
| Violates known bound | Normalization error, missing factors (variational E < E_exact, P > 1) | Check normalization and known limits |
| Wrong symmetry properties | Missing anomaly, wrong topological term, path-ordering | Verify transformation under P, T, gauge |
| Wrong temperature dependence | Classical/quantum conflation, wrong ensemble | Check quantum crossover scale |
| Negative spectral weight | Wrong Green's function type, complex conjugation error | Verify spectral positivity and KMS relation |

If the discrepancy matches a common pattern, test that hypothesis FIRST before entering the full investigation loop. This resolves ~50% of issues immediately.

</quick_triage>

<core_principle>
**Diagnose before planning fixes.**

Validation tells us WHAT is wrong (symptoms). Investigation agents find WHY (root cause). plan-phase --gaps then creates targeted fixes based on actual causes, not guesses.

Without diagnosis: "Energy not conserved" -> guess at fix -> maybe wrong
With diagnosis: "Energy not conserved" -> "Symplectic integrator replaced with forward Euler in refactor" -> precise fix

Without diagnosis: "Result disagrees with literature" -> "redo calculation" -> wasted effort
With diagnosis: "Result disagrees with literature" -> "Missing factor of 2 from spin degeneracy in density of states" -> targeted correction
</core_principle>

<process>

<step name="parse_gaps">
**Extract gaps from VERIFICATION.md:**

Read the "Gaps" section (YAML format):

```yaml
- expectation: "Energy is conserved to machine precision"
  status: failed
  reason: "Researcher reported: energy drifts by 1% over 1000 timesteps"
  severity: major
  check: 2
  missing: []
```

For each gap, also read the corresponding check from "Checks" section to get full context.

Build gap list:

```
gaps = [
  {expectation: "Energy is conserved...", severity: "major", check_num: 2, reason: "..."},
  {expectation: "Critical temperature matches literature...", severity: "blocker", check_num: 5, reason: "..."},
  ...
]
```

</step>

<step name="report_plan">
**Report diagnosis plan to researcher:**

```
## Diagnosing {N} Research Issues

Spawning parallel investigation agents to find root causes:

| Issue (Expected Outcome) | Severity |
|--------------------------|----------|
| Energy is conserved to machine precision | major |
| Critical temperature matches Tc/J = 4.51 | blocker |
| Spectral function satisfies sum rule | major |

Each agent will:
1. Create DEBUG-{slug}.md with symptoms pre-filled
2. Investigate independently (read code/derivations, form hypotheses, test)
3. Return root cause

This runs in parallel - all issues investigated simultaneously.
```

</step>

<step name="spawn_agents">
**Resolve debugger model and mode settings:**

```bash
DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after each debugger agent returns findings. Present the diagnosis to the user before proceeding to a fix.
- `autonomy=balanced` (default): Spawn the debugger agents, collect findings, and apply routine fixes automatically. Pause only if there are multiple plausible root causes or the fix changes assumptions or scope.
- `autonomy=yolo`: Spawn debuggers and continue automatically only after a specific evidence-backed root cause is identified. Do not apply a merely plausible fix.

**Spawn investigation agents in parallel:**

For each gap, fill the debug subagent prompt template (see `{GPD_INSTALL_DIR}/templates/debug-subagent-prompt.md` for the full template with placeholders, continuation format, and failure protocol) and spawn:
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\n" + filled_investigation_subagent_prompt,
  subagent_type="gpd-debugger",
  model="{debugger_model}",
  readonly=false,
  description="Investigate: {truth_short}"
)
```

**If any debugger agent fails to spawn or returns an error:** Continue with remaining agents. A single failed agent does not invalidate other investigations. After all agents complete, report which investigations failed and offer: 1) Retry failed investigations, 2) Investigate the failed truths in the main context, 3) Proceed only with the evidence-backed root causes that were actually established while keeping unresolved gaps open.

**All agents spawn in single message** (parallel execution).

Template placeholders:

- `{truth}`: The expected physics outcome that failed
- `{expected}`: From validation check
- `{actual}`: Verbatim researcher description from reason field
- `{errors}`: Any error messages or numerical values from validation (or "None reported")
- `{reproduction}`: "Check {check_num} in validation"
- `{timeline}`: "Discovered during research validation"
- `{goal}`: `find_root_cause_only` (validation flow - plan-phase --gaps handles fixes)
- `{slug}`: Generated from truth

**Investigation strategies for physics problems:**

Each agent should consider these common root causes:

- **Sign errors:** Flipped sign in Hamiltonian term, wrong convention for Fourier transform, metric signature
- **Missing factors:** Factor of 2 from spin, factor of 2\*pi from Fourier conventions, degeneracy factors
- **Wrong approximation:** Approximation invalid in parameter regime being tested, higher-order terms needed
- **Numerical issues:** Insufficient resolution, wrong integrator, floating-point cancellation, ill-conditioned matrix
- **Implementation bugs:** Array indexing off-by-one, wrong variable in expression, copy-paste error
- **Conceptual errors:** Wrong physical picture, missing physics (e.g., forgot about exchange interaction)
- **Unit/convention mismatch:** Different conventions in different parts of code, missing conversion factors
- **Regularization/renormalization:** Scheme mixing (dim reg + cutoff), missing counterterms, wrong renormalization scale
- **Topological/global issues:** Missing anomalies (ABJ), wrong path ordering for non-Abelian fields, zero mode miscounting
- **Wrong regime:** Adiabatic vs sudden approximation, classical vs quantum statistics, wrong ensemble for system size
  </step>

<step name="collect_results">
**Collect root causes from the typed return envelope:**

Each agent returns one typed `gpd_return` envelope and points to `GPD/debug/{slug}.md` as the session file.

- If `gpd_return.status: completed`, read `gpd_return.session_file` and use the file-backed diagnosis as the authoritative root-cause record.
- If `gpd_return.status: checkpoint`, present the checkpoint details to the user and spawn a fresh continuation run.
- If `gpd_return.status: blocked` or `failed`, report what was checked and keep the investigation incomplete.
- Do not route on heading markers in the returned text; use the typed `gpd_return` envelope and the session file instead.
  </step>

<step name="update_validation">
**Update VERIFICATION.md gaps with diagnosis:**

For each gap in the Gaps section, record the diagnosis fields the verifier actually consumes: `root_cause`, `missing`, `physics_impact`, and `debug_session`. Keep the update focused on the diagnosis rather than restating artifact inventories or path lists.

Keep canonical verification `status` unchanged and set `session_status: diagnosed` in that verification frontmatter. The debug session file at `GPD/debug/{slug}.md` keeps the debug-session `status` lifecycle and does not use `session_status`.

Commit the updated VERIFICATION.md:

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${phase_dir}/{phase}-VERIFICATION.md" 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs({phase}): add root causes from diagnosis" --files "${phase_dir}/{phase}-VERIFICATION.md"
```

</step>

<step name="report_results">
**Report diagnosis results and hand off:**

Display:

```
====================================================
 GPD > DIAGNOSIS COMPLETE
====================================================

| Issue (Expected Outcome) | Root Cause | Files |
|--------------------------|------------|-------|
| Energy conserved | Forward Euler instead of symplectic integrator | integrator.py |
| Tc matches literature | Missing spin degeneracy factor of 2 | density_of_states.py |
| Sum rule satisfied | Integration cutoff too low | spectral.py |

Debug sessions: ${DEBUG_DIR}/

Proceeding to plan fixes...
```

Return to verify-work orchestrator for automatic planning.
Do NOT offer manual next steps - verify-work handles the rest.
</step>

</process>

<context_efficiency>
Agents start with symptoms pre-filled from validation (no symptom gathering).
Agents only diagnose -- plan-phase --gaps handles fixes (no fix application).
</context_efficiency>

<failure_handling>
**Agent fails to find root cause:**

- Mark gap as "needs expert review"
- Continue with other gaps
- Report incomplete diagnosis and keep the gap unresolved; do not generate a speculative fix plan for that gap

**Agent times out:**

- Check DEBUG-{slug}.md for partial progress
- Can resume with gpd:debug

**All agents fail:**

- Something systemic (environment, dependencies, etc.)
- Report for expert investigation
- Return blocked with the unresolved gaps and missing diagnostic evidence; do not fall back to plan-phase --gaps without root causes
  </failure_handling>

<success_criteria>

- [ ] Gaps parsed from VERIFICATION.md
- [ ] Investigation agents spawned in parallel
- [ ] Root causes collected from all agents
- [ ] VERIFICATION.md gaps updated with diagnosis and missing actions
- [ ] Debug sessions saved to ${DEBUG_DIR}/
- [ ] Hand off to verify-work for automatic planning

</success_criteria>
