---
name: gpd:debug
description: Systematic debugging of physics calculations with persistent state across context resets
argument-hint: "[issue description]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - task
  - ask_user
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Debug physics calculations using systematic isolation with subagent investigation.

**Orchestrator role:** Gather symptoms, spawn gpd-debugger agent, handle checkpoints, spawn continuations.

**Why subagent:** Investigation burns context fast (reading derivations, forming hypotheses, testing limiting cases, running numerical checks). Fresh 200k context per investigation. Main context stays lean for user interaction.

Physics debugging differs fundamentally from software debugging. In software, a bug is deterministic: same input gives same wrong output. In physics calculations, errors can be subtle — a sign error that only matters in one regime, a factor of 2 from a symmetry argument, a gauge artifact that looks like a physical effect, a numerical instability that masquerades as a phase transition. The debugger must think like a physicist, not a programmer.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/debug.md
</execution_context>

<context>
User's issue: $ARGUMENTS

Check for active sessions:

```bash
ls .gpd/debug/*.md 2>/dev/null | grep -v resolved | head -5
```

</context>

<process>

## 0. Initialize Context

```bash
INIT=$(gpd init progress --include state,roadmap,config)
```

Extract `commit_docs` from init JSON. Resolve debugger model:

```bash
DEBUGGER_MODEL=$(gpd resolve-model gpd-debugger)
```

## 1. Check Active Sessions

If active sessions exist AND no $ARGUMENTS:

- List sessions with status, current hypothesis, next action
- User picks number to resume OR describes new issue

If $ARGUMENTS provided OR user describes new issue:

- Continue to symptom gathering

## 2. Gather Symptoms (if new issue)

Use ask_user for each. Physics-specific symptom gathering:

1. **Expected result** — What should the calculation give? (analytical prediction, known limit, published value, physical intuition)
2. **Actual result** — What do you get instead? (wrong magnitude, wrong sign, wrong functional form, divergence, nonsensical value)
3. **Discrepancy character** — How does the error behave?
   - Constant factor off (suggests combinatorial or normalization error)
   - Wrong sign (suggests convention mismatch or parity error)
   - Wrong power law (suggests missed contribution or wrong scaling argument)
   - Divergence where finite result expected (suggests regularization issue or missed cancellation)
   - Numerical instability (suggests ill-conditioned formulation or inadequate precision)
   - Gauge-dependent result for gauge-invariant observable (suggests gauge artifact)
4. **Where it breaks** — In what regime or parameter range does the problem appear?
   - Always wrong, or only for certain parameter values?
   - Does it get worse as some parameter increases?
   - Does the problem appear at a specific step in the derivation?
5. **What you have tried** — Any checks already performed?
   - Dimensional analysis?
   - Limiting cases?
   - Comparison with alternative derivation?
   - Numerical spot-checks?

After all gathered, confirm ready to investigate.

## 3. Spawn gpd-debugger Agent

Fill prompt and spawn:

```markdown
<objective>
Investigate physics issue: {slug}

**Summary:** {trigger}
</objective>

<symptoms>
expected: {expected}
actual: {actual}
discrepancy_character: {discrepancy_character}
where_it_breaks: {where_it_breaks}
already_tried: {already_tried}
</symptoms>

<mode>
symptoms_prefilled: true
goal: find_and_fix
</mode>

<investigation_strategy>
Physics debugging follows a hierarchy of checks, ordered from cheapest to most expensive:

1. **Dimensional analysis** — Check dimensions of every intermediate expression. This catches ~30% of errors and costs almost nothing.
2. **Special/limiting cases** — Evaluate the expression in limits where the answer is known. Catches ~20% of remaining errors.
3. **Sign and symmetry audit** — Track signs through the derivation. Check that symmetries of the problem are preserved. Catches sign errors and parity mistakes.
4. **Term-by-term comparison** — If an alternative derivation exists, compare term by term to isolate where they diverge.
5. **Numerical spot-check** — Evaluate both sides of key equations numerically at random parameter values. Catches algebraic errors that are hard to see symbolically.
6. **Bisection** — If the derivation is long, check the result at the midpoint. Is it already wrong there? Binary search for the first wrong step.
7. **Simplification** — Strip the problem to its simplest version that still exhibits the bug. Remove all complications (interactions, finite size, finite temperature) until the error disappears, then add them back one at a time.
   </investigation_strategy>

<common_physics_errors>

- Factor of 2 from double-counting (symmetry factors, identical particles, Wick contractions)
- Factor of 2 from real vs complex conventions (Fourier transforms, field normalizations)
- Factor of pi from Fourier transform conventions (2pi in measure vs in exponential)
- Sign from metric signature convention (+--- vs -+++)
- Sign from Wick rotation (Euclidean vs Minkowski)
- Sign from fermion anti-commutation (ordering of Grassmann variables)
- Missing Jacobian from coordinate transformation
- Wrong measure in path integral or partition function
- Forgetting that trace is cyclic but not symmetric under transposition for non-Hermitian operators
- Regularization-scheme-dependent finite parts
- Gauge artifact mistaken for physical effect
- Infrared divergence from massless limit taken too early
- Numerical precision loss from catastrophic cancellation
- Stiff ODE requiring implicit integrator
- Aliasing from insufficient spatial resolution
  </common_physics_errors>

<debug_file>
Create: .gpd/debug/{slug}.md
</debug_file>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\n" + filled_prompt,
  subagent_type="gpd-debugger",
  model="{debugger_model}",
  readonly=false,
  description="Debug {slug}"
)
```

## 4. Handle Agent Return

**If `## ROOT CAUSE FOUND`:**

- Display root cause and evidence summary
- Classify the error type (sign error, missing factor, wrong convention, numerical issue, conceptual error)
- Offer options:
  - "Fix now" — spawn fix subagent
  - "Plan fix" — suggest /gpd:plan-phase --gaps
  - "Manual fix" — done (provide the identified error location and correction)

**If `## CHECKPOINT REACHED`:**

- Present checkpoint details to user
- Common checkpoint reasons in physics debugging:
  - "Need to know which convention you are using for X"
  - "Found two candidate errors — which regime matters more to you?"
  - "Numerical test requires running a simulation — should I proceed?"
  - "Discrepancy might be a known issue in the literature — should I search?"
- Get user response
- Spawn continuation agent (see step 5)

**If `## INVESTIGATION INCONCLUSIVE`:**

- Show what was checked and eliminated
- Offer options:
  - "Continue investigating" — spawn new agent with additional context
  - "Manual investigation" — done, provide summary of what was ruled out
  - "Add more context" — gather more symptoms, spawn again
  - "Simplify the problem" — suggest stripping to minimal reproducing case

## 5. Spawn Continuation agent (After Checkpoint)

When user responds to checkpoint, spawn fresh agent:

```markdown
<objective>
Continue debugging {slug}. Evidence is in the debug file.
</objective>

<prior_state>
Debug file path: .gpd/debug/{slug}.md
Read that file before continuing so you inherit the prior investigation state instead of relying on an inline `@...` attachment.
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>

<mode>
goal: find_and_fix
</mode>
```

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-debugger.md for your role and instructions.\n\n" + continuation_prompt,
  subagent_type="gpd-debugger",
  model="{debugger_model}",
  readonly=false,
  description="Continue debug {slug}"
)
```

</process>

<success_criteria>

- [ ] Active sessions checked
- [ ] Symptoms gathered with physics-specific characterization (if new)
- [ ] gpd-debugger spawned with context and investigation strategy
- [ ] Checkpoints handled correctly
- [ ] Root cause confirmed and classified before fixing
- [ ] Error type identified (algebraic, numerical, conceptual, conventional)
      </success_criteria>
