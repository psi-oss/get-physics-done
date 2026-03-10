---
template_version: 1
---

<!-- For the detailed archive format used by $gpd-complete-milestone, see milestone-archive.md -->

# Milestone Entry Template

Add this entry to `.gpd/MILESTONES.md` when completing a research milestone:

```markdown
## [Milestone Name] (Completed: YYYY-MM-DD)

**Delivered:** [One sentence describing what was achieved]

**Phases completed:** [X-Y] ([Z] plans total)

**Key results:**

- [Major result 1: e.g., Derived RG flow equations for long-range XY model]
- [Major result 2: e.g., Identified critical alpha_c = 2.3 +/- 0.1 from numerical solution]
- [Major result 3: e.g., Monte Carlo confirms BKT universality class for alpha > alpha_c]
- [Major result 4: e.g., Paper submitted to Physical Review Letters]

**Key equations/values:**

- [Central result: e.g., T_c(alpha) = T_BKT * f(alpha) where f is given in Eq. (23)]
- [Important parameter: e.g., Critical exponent nu = 0.672(3) at alpha = 2.5]

**Stats:**

- [x] derivation pages / calculation notebooks
- [Y] simulation runs completed
- [Z] phases, [N] plans, [M] tasks
- [D] days from start to completion

**Validation status:**

- [Check 1: e.g., Short-range limit reproduces Kosterlitz (1974) — PASSED]
- [Check 2: e.g., RG and MC agree within 0.5% — PASSED]
- [Check 3: e.g., Ward identity satisfied to machine precision — PASSED]

**What's next:** [Brief description of next milestone goals, or "Project complete"]

---
```

<structure>
If MILESTONES.md doesn't exist, create it with header:

```markdown
# Research Milestones: [Project Title]

[Entries in reverse chronological order - newest first]
```

</structure>

<guidelines>
**When to create milestones:**
- Paper submitted to journal
- Major calculation completed (e.g., "Perturbative calculation complete to 2-loop order")
- Significant validation checkpoint passed
- Referee response submitted
- Paper published / posted to arXiv
- Before archiving planning (capture what was achieved)

**Don't create milestones for:**

- Individual phase completions (normal workflow)
- Work in progress (wait until a coherent result is obtained)
- Minor corrections that don't constitute a research checkpoint

**Key results to include:**

- Central equations or numerical values obtained
- Comparisons with known results (agreement/disagreement)
- New predictions made
- Validation checks passed/failed

**Validation status:**

- List all cross-checks performed and their outcomes
- Be explicit about pass/fail — this is the scientific record
- Note any checks that were inconclusive and why
  </guidelines>

<example>
```markdown
# Research Milestones: BKT Transitions with Long-Range Interactions

## Paper Submitted to PRL (Completed: 2025-06-20)

**Delivered:** Submitted manuscript demonstrating modified BKT transition in long-range XY model

**Phases completed:** 1-5 (12 plans total)

**Key results:**

- Derived RG flow equations incorporating 1/r^alpha interactions
- Identified critical alpha_c = 2.32(5) below which BKT transition is destroyed
- Monte Carlo simulations on lattices up to L=128 confirm RG predictions
- T_c(alpha) curve mapped for alpha in [1.5, 4.0]
- Universal jump in helicity modulus confirmed for alpha > alpha_c

**Key equations/values:**

- T_c(alpha)/T_BKT = 1 - A\*(alpha - alpha_c)^beta for alpha near alpha_c, with A = 0.47(3), beta = 0.51(4)
- alpha_c = 2.32(5) from finite-size scaling collapse
- Universal helicity modulus jump: Delta_rho = 2T_c/pi confirmed to 0.1%

**Stats:**

- 45 pages of derivations across 8 notebooks
- 2400 Monte Carlo runs (5 alpha values x 4 system sizes x 120 temperature points)
- 5 phases, 12 plans, 47 tasks
- 62 days from literature review to submission

**Validation status:**

- Short-range limit (alpha -> inf) reproduces T_BKT = 0.8929(1) — PASSED
- RG equations reduce to Kosterlitz (1974) form — PASSED
- RG and MC T_c values agree within 0.4% for all alpha — PASSED
- Finite-size scaling quality chi^2/dof < 1.2 for all fits — PASSED
- Ward identity for U(1) symmetry satisfied — PASSED

**What's next:** Address referee comments (expected 6-8 weeks), begin extension to quantum regime

---

## Formalism and Calculation Complete (Completed: 2025-05-10)

**Delivered:** Complete RG analysis and numerical solution for long-range BKT transition

**Phases completed:** 1-3 (8 plans total)

**Key results:**

- Literature review identified gap: no systematic RG treatment for continuously varying alpha
- Effective Hamiltonian constructed with long-range vortex interactions
- RG flow equations derived to leading order in fugacity
- Numerical solution yields T_c(alpha) for 20 values of alpha in [1.5, 4.0]

**Key equations/values:**

- RG beta functions: see notebook 02-03 Eqs. (15)-(17)
- alpha_c = 2.3 (preliminary, before MC refinement)

**Stats:**

- 30 pages of derivations across 5 notebooks
- 3 phases, 8 plans, 31 tasks
- 41 days from start

**Validation status:**

- Limiting case alpha -> inf matches standard BKT — PASSED
- RG flow topology consistent with Kosterlitz-Thouless picture — PASSED
- Numerical convergence with RG truncation order verified — PASSED

**What's next:** Monte Carlo simulations and full validation (Phase 4)

```
</example>
