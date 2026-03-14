---
template_version: 1
---

# PROJECT.md Template

Template for `.gpd/PROJECT.md` — the living physics research project context document.

<template>

```markdown
# {project_title}

## What This Is

[Current accurate description — 2-3 sentences. What is the physics question being investigated?
What subfield does it belong to? What is the expected deliverable (paper, calculation, simulation)?
Update whenever the research direction drifts from this description.]

## Core Research Question

[The ONE question this project must answer. If everything else fails, this must be resolved.
One sentence that drives prioritization when tradeoffs arise.]

## Scoping Contract Summary

### Contract Coverage

- [Claim / deliverable]: [What counts as success]
- [Acceptance signal]: [Benchmark match, proof obligation, figure, dataset, or review artifact]
- [False progress to reject]: [Proxy that must NOT count as success]

### User Guidance To Preserve

- **User-stated observables:** [Specific quantity, signal, figure, or smoking-gun the user explicitly named]
- **User-stated deliverables:** [Specific table, plot, derivation, dataset, note, or code output the user expects]
- **Must-have references / prior outputs:** [Paper, notebook, baseline run, figure, or benchmark the user said must stay visible]
- **Stop / rethink conditions:** [What should make the system pause, ask again, or re-scope]

### Scope Boundaries

**In scope**

- [What this project explicitly covers]

**Out of scope**

- [What this project explicitly does not cover]

### Active Anchor Registry

- [Anchor ID or short label]: [Paper, dataset, spec, benchmark, or prior artifact]
  - Why it matters: [What claim, observable, or deliverable it constrains]
  - Carry forward: [planning | execution | verification | writing]
  - Required action: [read | use | compare | cite | avoid]

### Carry-Forward Inputs

- [Internal artifact, prior run, notebook, figure, baseline, or "None confirmed yet"]
- [User-asserted anchor or crucial prior output]

### Skeptical Review

- **Weakest anchor:** [Least-certain benchmark, assumption, or prior result]
- **Unvalidated assumptions:** [What is currently assumed rather than checked]
- **Competing explanation:** [Plausible alternative story that could also fit]
- **Disconfirming observation:** [What result would make you stop and rethink]
- **False progress to reject:** [What might look encouraging but should not count as success]

### Open Contract Questions

- [Unresolved question 1]
- [Unresolved question 2]

## Research Questions

### Answered

(None yet — investigate to answer)

### Active

- [ ] [Research question 1]
- [ ] [Research question 2]
- [ ] [Research question 3]

### Out of Scope

- [Question 1] — [why: e.g., requires experiment, different subfield]

## Research Context

### Physical System

[Description of the system under study]

### Theoretical Framework

[QFT / condensed matter / GR / statistical mechanics / etc.]

### Key Parameters and Scales

| Parameter | Symbol | Regime  | Notes   |
| --------- | ------ | ------- | ------- |
| [param 1] | [sym]  | [range] | [notes] |

### Known Results

- [Prior work 1] — [reference]
- [Prior work 2] — [reference]

### What Is New

[What this project contributes beyond existing work]

### Target Venue

[Journal or conference, with rationale]

### Computational Environment

[Available resources: local workstation, cluster, cloud, specific codes]

## Notation and Conventions

See `.gpd/CONVENTIONS.md` for all notation and sign conventions.
See `.gpd/NOTATION_GLOSSARY.md` for symbol definitions.

## Unit System

[e.g., Natural units (hbar = c = k_B = 1), SI, Gaussian CGS, Planck units, lattice units]

## Requirements

See `.gpd/REQUIREMENTS.md` for the detailed requirements specification.

Key requirement categories: DERV (derivation), CALC (calculation), SIMU (simulation), VALD (validation)

## Key References

Mirror only the contract-critical anchors from `## Scoping Contract Summary`.
Do not introduce new must-read references here unless they are also added to the contract/state registry.

## Constraints

- **[Type]**: [What] — [Why]
- **[Type]**: [What] — [Why]

Common types: Computational resources, Accuracy required, Experimental data availability,
Collaboration dependencies, Time to publication, Code availability, Symmetry requirements

## Key Decisions

| Decision | Rationale | Outcome   |
| -------- | --------- | --------- |
| [Choice] | [Why]     | — Pending |

Full log: `.gpd/DECISIONS.md`

---

_Last updated: [date] after [trigger]_
```

</template>

<guidelines>

**What This Is:**

- Current accurate description of the research project
- 2-3 sentences capturing the physics question and expected deliverable
- Use precise physics language appropriate to the subfield
- Update when the research direction evolves beyond this description

**Core Research Question:**

- The single most important question to answer
- Everything else can fail; this must be resolved
- Drives prioritization when tradeoffs arise (e.g., accuracy vs. generality)
- Rarely changes; if it does, it's a significant pivot in the research program

**Scoping Contract Summary:**

- Short human-readable projection of the authoritative scoping contract
- Capture contract coverage, user guidance, active anchors, carry-forward inputs, skeptical review items, and open contract questions
- Keep this concise and concrete so later workflows can scan it quickly
- If an anchor or prior artifact is unknown, say so explicitly instead of implying certainty
- Preserve the user's wording when they explicitly name an observable, deliverable, prior output, or required reference
- Record user-stated pause / rethink conditions rather than only abstract risks

**Research Questions:**

- Tracks the lifecycle of research questions through three states: Answered, Active, Out of Scope
- `transition.md` moves questions between states after each phase
- `resume-work.md` reads this section for session context
- Active questions guide prioritization; Answered questions record progress

**Research Context:**

- Consolidates physical system, theoretical framework, key parameters, known results, novelty, venue, and computational environment
- Subsumes the roles of standalone Physics Subfield, Mathematical Framework, Computational Tools, and Target Publication sections
- `transition.md` updates Known Results and Key Parameters after analytical/numerical phases
- Key Parameters table should include symbol, regime of validity, and notes

**Requirements:** Tracked in `.gpd/REQUIREMENTS.md` (single source of truth). Do not duplicate requirements content in PROJECT.md.

**Key References:**

- Treat this as a readability mirror of the active anchor registry, not a second source of truth
- Include only references that are already in the structured contract or bibliography flow
- Distinguish must-read anchors from general background when possible
- Update as new relevant literature is discovered

**Notation and Conventions:**

- Populated during project initialization into `.gpd/CONVENTIONS.md` and `.gpd/NOTATION_GLOSSARY.md`
- PROJECT.md contains only a pointer, not inline convention definitions

**Constraints:**

- Hard limits on research choices
- Computational resources, required accuracy, data availability, symmetry requirements
- Include the "why" — constraints without rationale get questioned

**Key Decisions:**

- Inline summary table for quick access; full log in `.gpd/DECISIONS.md`
- `transition.md` adds rows after each phase
- `resume-work.md` reads the table for session context

**Last Updated:**

- Always note when and why the document was updated
- Format: `after Phase 2` or `after validation milestone`
- Triggers review of whether content is still accurate

</guidelines>

<evolution>

PROJECT.md evolves throughout the research lifecycle.

**After each phase transition:**

1. Research Questions: Move answered questions to Answered; add newly emerged questions to Active
2. Requirements invalidated? — Move to Out of Scope with reason
3. Requirements validated? — Move to Validated with phase reference
4. New requirements emerged? — Add to Active
5. Decisions to log? — Add row to Key Decisions table and to `.gpd/DECISIONS.md`
6. Research Context: Update Known Results with new findings; refine Key Parameters if values changed
7. "What This Is" still accurate? — Update if research direction drifted
8. New references discovered? — Add to Key References
9. Revisit the Scoping Contract Summary — weakest anchor, false-progress risks, and open questions still accurate?

**After each milestone:**

1. Full review of all sections
2. Core Research Question check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update notation if conventions were refined
5. Review target publication — still appropriate venue?

</evolution>

<continuation_projects>

For ongoing research projects:

1. **Map existing work first** via `/gpd:map-research`

2. **Infer Validated requirements** from existing calculations:

   - What results have already been derived?
   - What formalisms are established?
   - What numerical results are confirmed?

3. **Gather Active requirements** from researcher:

   - Present inferred current state
   - Ask what they want to calculate/derive next

4. **Initialize:**
   - Validated = confirmed results from existing work
   - Active = researcher's goals for current phase
   - Out of Scope = boundaries researcher specifies
   - Key References = papers already cited in existing drafts

</continuation_projects>

<state_reference>

STATE.md references PROJECT.md:

```markdown
## Project Reference

See: .gpd/PROJECT.md (updated [date])

**Core research question:** [One-liner from Core Research Question section]
**Current focus:** [Current phase name]
```

This ensures the agent reads current PROJECT.md context.

</state_reference>
