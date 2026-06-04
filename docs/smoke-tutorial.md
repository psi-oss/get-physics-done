# Smoke-test ideas and assumptions before you build a project

`gpd:smoke` is a pre-commit sniff-test. You give it a quantitative claim or an
unverified assumption; it writes the smallest possible script that would
reproduce or refute the claim, runs it, and emits a PASS / FAIL / INCONCLUSIVE
verdict — *before* you scaffold a whole research project or execute a phase.

This tutorial walks through both modes end-to-end with a real worked example:
verifying the "butterfly effect" in the logistic map, then scaffolding a real
chaos-systems project around it.

---

## When to use smoke

Two situations.

**Pre-project anchor.** You have a published number you want to reproduce
before committing to a project. Example: Onsager's 2D Ising critical
temperature, the Lyapunov exponent of the logistic map at r=4, the period of a
small-angle pendulum. If the smallest viable version of the claim does not
reproduce, `gpd:new-project` is probably premature.

**In-project assumption gate.** Your plan rests on an assumption that has not
been tested at the parameters you actually use. Example: "Forward Euler is
good enough for the simple harmonic oscillator at dt=0.05 over 100 periods"
or "burn-in of 2000 iterations is sufficient near the critical r." Smoke
verifies the assumption against the plan *before* you run
`gpd:execute-phase` and burn real compute.

`gpd:smoke` is NOT `gpd:verify-work` (post-result consistency checks),
`gpd:limiting-cases` (analytic-limit audits inside a project), or
`gpd:numerical-convergence` (grid-refinement studies). Those run after a
result exists; smoke runs *before* you commit to producing one.

---

## Three invocation forms

```text
gpd:smoke "[claim text with a number and a source]"          # anchor mode
gpd:smoke --assumption "<text>"                              # assumption mode
gpd:smoke --from-plan                                        # read from PLAN.md
```

A "claim" is a published quantitative statement with a source. An "assumption"
is a local statement that you or another GPD command is about to commit to
without verification. Both route through the same propose-confirm-run-verdict
machinery; the only difference is how the verdict is framed.

---

## Worked example — the butterfly effect

### 1. Smoke the foundational claim

```text
gpd:smoke "The butterfly effect: in the logistic map at r=4, two trajectories
starting 1e-10 apart diverge exponentially. The Lyapunov exponent — the
per-step divergence rate — equals ln(2) ≈ 0.6931 (May, Nature 1976)."
```

Smoke parses the claim:

```text
claim_value:  λ = ln(2) ≈ 0.6931
claim_source: R. May, Nature 261, 459 (1976)
parameters:   x_{n+1} = r·x_n·(1−x_n), r = 4
```

…then proposes the smallest viable computation:

```text
setup:        Iterate from x_0 = 0.4 for 400 steps (avoid the degenerate
              orbit through x = 0.5). Estimate λ as the time average of
              log|f'(x_n)| = log|r(1 − 2x_n)| over n ∈ [50, 400].
runtime:      <1 s
tolerance:    ±5%
```

After you confirm, smoke writes `smoke_lyapunov.py` (the actual seed
implementation), runs it, and reports:

```text
Claim:    λ = ln(2) ≈ 0.6931  (May, Nature 1976)
Measured: λ_est = 0.6946       (time avg of log|f'(x)| over n ∈ [50, 400])
Verdict:  PASS  (relative error +0.21%, tolerance ±5%)
```

If the verdict is FAIL, you investigate the gap *before* starting a project.
If PASS, the script remains in the working directory as the seed
implementation.

### 2. Scaffold the real project

PASS justifies the next command:

```text
gpd:new-project --minimal study chaotic systems and measure Feigenbaum's
universal constant δ ≈ 4.6692016 in the logistic and sine maps. Three phases:
bifurcation diagram, measure delta, verify universality.
```

The seed implementation from step 1 carries forward as a `crucial_input` in
the project's scoping contract. Phase 1 will reuse the same iteration kernel.

### 3. Smoke a within-scope anchor

Before the first phase commits compute, smoke a second analytical anchor that
the phase will rely on:

```text
gpd:smoke "Logistic map second period-doubling threshold r_2 = 1 + √6 ≈
3.44949 (Strogatz, Nonlinear Dynamics and Chaos, Sec. 10.3)"
```

If this PASSes the phase's threshold-localization method is validated; if not,
either the method or the bracket needs revision before scaling.

### 4. Smoke an assumption from the plan

After `gpd:plan-phase 1` writes `PLAN.md`, smoke pulls an assumption directly
from its `## My Assumptions for Phase 1` block:

```text
gpd:smoke --from-plan
```

Smoke parses the assumptions section (tolerant of both flat `## Assumptions`
and hierarchical `## My Assumptions for Phase X` + `### <category>` shapes),
lists the bullets with their category tags, and asks which one to smoke.
After you pick, it runs at the worst-case parameters the plan flagged and
emits the verdict.

### 5. Now execute with confidence

If both anchors and the chosen assumption PASS, `gpd:execute-phase 1` runs
against a foundation that is empirically verified at minimum scale. If any
smoke FAILed earlier, you would have revised before reaching this point.

---

## What smoke does NOT do

- It does not auto-route into `gpd:new-project`, `gpd:plan-phase`, or
  `gpd:execute-phase` on a PASS. You explicitly invoke the next command.
- It does not rewrite `PLAN.md`. Even in `--from-plan` mode, smoke is
  read-only against the plan. The user decides whether to revise the
  assumption after a verdict.
- It does not fabricate measured values. If the script fails or is killed,
  the verdict is missing, not PASS.
- It does not create `GPD/`, `state.json`, or any project scaffolding.
  Smoke is pre-commit.

A PASS verdict means "this specific quantitative claim or assumption holds
at the tested parameters" — not "the full study will work." Be honest about
scope. The smoke script is a seed implementation, not a finished study.

---

## Anti-pattern: vague claims

If you hand smoke a qualitative claim ("the system is unstable", "AI improves
productivity"), it will ask once for sharpening and stop. Smoke needs a
number to compare against. Refusing to fabricate a test for a confused claim
is the guardrail, not a bug.

Likewise, if the published "anchor" you cite has no resolvable source,
smoke will accept it but label the verdict as a self-consistency check, not
a reproduction.

---

## Reading the verdict

```text
Claim:    <claim_value> (<claim_source>)
Measured: <measured_value> (±<uncertainty if known>)
Verdict:  PASS | FAIL | INCONCLUSIVE  (tolerance ±<X>)
```

Treat INCONCLUSIVE as not-yet-PASS — usually the smoke needs more samples,
finer dt, or a larger lattice. Re-run with the tightened parameters before
moving on.
