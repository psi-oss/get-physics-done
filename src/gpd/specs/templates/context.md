---
template_version: 1
---

# Phase Context Template

Template for `.gpd/phases/XX-name/{phase}-CONTEXT.md` - captures research decisions for a phase.

**Purpose:** Document decisions that downstream agents need. The researcher-agent uses this to know WHAT to investigate in the literature. The planner-agent uses this to know WHAT calculations are locked vs flexible.

**Key principle:** Categories are NOT predefined. They emerge from what was actually discussed for THIS phase. A formalism phase has formalism-relevant sections, a simulation phase has simulation-relevant sections.

**Downstream consumers:**

- `gpd-phase-researcher` — Reads decisions to focus literature review (e.g., "dimensional regularization" -> research dim-reg techniques for this class of integrals)
- `gpd-planner` — Reads decisions to create specific tasks (e.g., "Wolff cluster algorithm" -> task includes cluster update implementation)

---

## File Template

```markdown
# Phase [X]: [Name] - Context

**Gathered:** [date]
**Status:** Ready for planning

<domain>
## Phase Boundary

[Clear statement of what this phase delivers — the scope anchor. This comes from ROADMAP.md and is fixed. Discussion clarifies approach within this boundary.]

Requirements: [{REQ-ID-1}, {REQ-ID-2}]  <!-- from ROADMAP.md phase details -->

</domain>

<contract_coverage>
## Contract Coverage

[List the decisive outputs, acceptance signals, and false-progress traps for this phase.]

- [Claim / deliverable]: [What counts as success]
- [Acceptance signal]: [Benchmark match, proof obligation, figure, dataset, or note]
- [False progress to reject]: [Proxy that must not count]

</contract_coverage>

<decisions>
## Methodological Decisions

### [Physics Category 1 that was discussed]

- [Decision or preference captured]
- [Physical justification given by user]
- [Regime of validity or known limitations]

### [Physics Category 2 that was discussed]

- [Decision or preference captured]
- [Physical justification given by user]

### Agent's Discretion

[Areas where the user said "you decide" — note that the AI has flexibility here, with any constraints mentioned]

</decisions>

<assumptions>
## Physical Assumptions

[Assumptions surfaced during Socratic dialogue]

- [Assumption 1]: [Justification] | [What breaks if wrong]
- [Assumption 2]: [Justification] | [What breaks if wrong]

</assumptions>

<limiting_cases>
## Expected Limiting Behaviors

[Limiting cases identified during discussion that results must satisfy]

- [Limit 1]: When [parameter] -> [value], result should -> [expected behavior]
- [Limit 2]: When [parameter] -> [value], result should -> [expected behavior]

</limiting_cases>

<anchor_registry>
## Active Anchor Registry

[References, baselines, prior outputs, and user anchors that must remain visible during planning and execution.]

- [Anchor ID or short label]: [Paper, dataset, spec, benchmark, prior artifact, or "None confirmed yet"]
  - Why it matters: [What claim, observable, or deliverable it constrains]
  - Carry forward: [planning | execution | verification | writing]
  - Required action: [read | use | compare | cite | avoid]

</anchor_registry>

<skeptical_review>
## Skeptical Review

[The load-bearing uncertainty check for this phase. Keep it concrete.]

- **Weakest anchor:** [Least-certain assumption, benchmark, or prior result]
- **Unvalidated assumptions:** [What is currently assumed rather than checked]
- **Competing explanation:** [Alternative story that could also fit]
- **Disconfirming check:** [Earliest observation or comparison that would force a re-think]
- **False progress to reject:** [What might look promising but should not count as success]

</skeptical_review>

<deferred>
## Deferred Ideas

[Ideas that came up during discussion but belong in other phases. Captured here so they're not lost, but explicitly out of scope for this phase.]

[If none: "None — discussion stayed within phase scope"]

</deferred>

---

_Phase: XX-name_
_Context gathered: [date]_
```

<good_examples>

**Example 1: Formalism development phase**

```markdown
# Phase 2: RG Flow Equations - Context

**Gathered:** 2025-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Derive renormalization group flow equations for the XY model with 1/r^alpha interactions. Must obtain beta functions for vortex fugacity y and spin stiffness K as functions of alpha. Numerical solution of the RG equations is a separate phase.

</domain>

<decisions>
## Methodological Decisions

### RG scheme

- Momentum-shell RG following Kosterlitz (1974) approach
- Integrate out modes in shell [Lambda/b, Lambda] with b = 1 + dl
- Keep terms to leading order in vortex fugacity y

### Treatment of long-range coupling

- Decompose 1/r^alpha interaction into short-range and long-range parts at cutoff scale
- Long-range part modifies the bare spin stiffness K_0(alpha)
- Follow approach of Defenu et al. (2015) for the decomposition

### Regularization

- No UV divergences expected at leading order in y
- If divergences appear at higher order, use dimensional regularization to preserve U(1) symmetry
- Cutoff regularization acceptable only if symmetry-preserving

### Agent's Discretion

- Specific form of the momentum-shell integration measure
- Whether to work in real space or Fourier space for intermediate steps
- Level of detail in documenting intermediate algebra

</decisions>

<assumptions>
## Physical Assumptions

- Vortex fugacity y << 1: Justified for temperatures well below BKT transition | Results break down near T_c where y ~ O(1)
- Continuum approximation valid: Lattice spacing a << correlation length xi | Breaks down at very high T or very small system sizes
- O(2) symmetry exact: No anisotropy terms in the Hamiltonian | If anisotropy added, BKT physics replaced by Ising-like behavior

</assumptions>

<limiting_cases>
## Expected Limiting Behaviors

- When alpha -> infinity: Must recover standard BKT flow equations dK^{-1}/dl = 4pi^3 y^2, dy/dl = (2 - pi*K)y
- When y -> 0 (low temperature): Flow equations should give dK/dl = 0 at leading order (spin stiffness constant)
- When alpha -> 2 (long-range dominated): Mean-field-like behavior expected, BKT transition may disappear

</limiting_cases>

<anchor_registry>
## Active Anchor Registry

- Altland & Simons, Chapter 8
  - Why it matters: notation anchor for the Coulomb gas mapping
  - Carry forward: planning, execution, writing
  - Required action: read, use, cite
- Defenu et al., PRB 92, 014512 (2015)
  - Why it matters: long-range decomposition benchmark
  - Carry forward: planning, execution, verification
  - Required action: read, compare, cite
- Vortex-antivortex representation
  - Why it matters: formulation choice locked during discussion
  - Carry forward: planning, execution
  - Required action: use

</anchor_registry>

<skeptical_review>
## Skeptical Review

- **Weakest anchor:** Defenu et al. long-range decomposition is being reused outside its original parameter choices
- **Unvalidated assumptions:** Long-range part can be cleanly folded into the bare stiffness without changing vortex counting
- **Competing explanation:** Apparent agreement could come from a convention choice rather than real physics
- **Disconfirming check:** Failure to recover the short-range BKT equations in the alpha -> infinity limit
- **False progress to reject:** Algebra that looks clean but never checks the known limiting case

</skeptical_review>

<deferred>
## Deferred Ideas

- Higher-order corrections in fugacity — Phase 3 if needed for quantitative accuracy
- Connection to conformal field theory at critical point — future paper

</deferred>

---

_Phase: 02-rg-flow-equations_
_Context gathered: 2025-04-01_
```

**Example 2: Numerical simulation phase** (abbreviated)

```markdown
# Phase 3: Monte Carlo Simulations - Context

**Gathered:** 2025-04-20
**Status:** Ready for planning

<domain>
## Phase Boundary
Run Monte Carlo simulations of the long-range XY model to independently determine T_c(alpha).
</domain>

<decisions>
## Research Decisions
### Algorithm choice
- Wolff cluster algorithm adapted for long-range interactions
- Parallel tempering across temperature points for efficiency
### System sizes and parameters
- Square lattice, L = 16, 32, 64, 128; PBC with Ewald summation
- alpha values: 2.0, 2.5, 3.0, 3.5, 4.0
### Error analysis
- Bootstrap error estimation; statistical error target: < 0.3% on energy per spin
</decisions>

<!-- See full examples in project archives -->
```

**Example 3: Validation phase** (abbreviated)

```markdown
# Phase 4: Validation and Cross-checks - Context

**Gathered:** 2025-05-15
**Status:** Ready for planning

<domain>
## Phase Boundary
Systematically validate all results: limiting cases, cross-method comparison (RG vs MC), literature values.
</domain>

<decisions>
## Research Decisions
### Limiting case checks
- alpha -> infinity: Must recover standard BKT T_c = 0.8929(1)
- alpha -> 2: Check against mean-field prediction
### Cross-method comparison
- Agreement criterion: within combined error bars (RG truncation + MC statistical)
</decisions>

<!-- See full examples in project archives -->
```

</good_examples>

<guidelines>
**This template captures DECISIONS for downstream agents.**

The output should answer: "What does the researcher-agent need to investigate in the literature? What methodological choices are locked for the planner?"

**Requirements linkage:** The Phase Boundary section must list requirement IDs from ROADMAP.md. These anchor the phase scope — decisions captured in this file must serve the listed requirements. If discussion reveals that a requirement is underspecified, note it and defer to the researcher for clarification.

**Good content (concrete physics decisions):**

- "Momentum-shell RG following Kosterlitz (1974) approach"
- "Wolff cluster algorithm adapted for long-range interactions"
- "Dimensional regularization to preserve gauge invariance"
- "System sizes L = 16, 32, 64, 128 with periodic boundary conditions"
- "Statistical error target < 0.3% on energy per spin"

**Bad content (too vague):**

- "Use a good algorithm"
- "Accurate calculation"
- "Standard methods from the literature"
- "Sufficient system sizes"

**After creation:**

- File lives in phase directory: `.gpd/phases/XX-name/{phase}-CONTEXT.md`
- `gpd-phase-researcher` uses decisions to focus literature investigation
- `gpd-planner` uses decisions + research to create executable tasks
- Downstream agents should NOT need to ask the researcher again about captured decisions
  </guidelines>
