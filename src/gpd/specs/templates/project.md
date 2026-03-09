---
template_version: 1
---

# PROJECT.md Template

Template for `.planning/PROJECT.md` — the living physics research project context document.

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

See `.planning/CONVENTIONS.md` for all notation and sign conventions.
See `.planning/NOTATION_GLOSSARY.md` for symbol definitions.

## Unit System

[e.g., Natural units (hbar = c = k_B = 1), SI, Gaussian CGS, Planck units, lattice units]

## Requirements

See `.planning/REQUIREMENTS.md` for the detailed requirements specification.

Key requirement categories: DERV (derivation), CALC (calculation), SIMU (simulation), VALD (validation)

## Key References

[Papers, textbooks, and preprints central to this work:

- [Author et al., Journal, Year] — [why it matters: e.g., original derivation of method we extend]
- [Author et al., arXiv:XXXX.XXXXX] — [why it matters: e.g., most recent lattice data for comparison]
- [Textbook, Chapter X] — [why it matters: e.g., standard reference for formalism]]

## Constraints

- **[Type]**: [What] — [Why]
- **[Type]**: [What] — [Why]

Common types: Computational resources, Accuracy required, Experimental data availability,
Collaboration dependencies, Time to publication, Code availability, Symmetry requirements

## Key Decisions

| Decision | Rationale | Outcome   |
| -------- | --------- | --------- |
| [Choice] | [Why]     | — Pending |

Full log: `.planning/DECISIONS.md`

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

**Requirements:** Tracked in `.planning/REQUIREMENTS.md` (single source of truth). Do not duplicate requirements content in PROJECT.md.

**Key References:**

- Papers, textbooks, and preprints essential to the project
- Include why each reference matters (method source, comparison data, formalism reference)
- Update as new relevant literature is discovered

**Notation and Conventions:**

- Populated during project initialization into `.planning/CONVENTIONS.md` and `.planning/NOTATION_GLOSSARY.md`
- PROJECT.md contains only a pointer, not inline convention definitions

**Constraints:**

- Hard limits on research choices
- Computational resources, required accuracy, data availability, symmetry requirements
- Include the "why" — constraints without rationale get questioned

**Key Decisions:**

- Inline summary table for quick access; full log in `.planning/DECISIONS.md`
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
5. Decisions to log? — Add row to Key Decisions table and to `.planning/DECISIONS.md`
6. Research Context: Update Known Results with new findings; refine Key Parameters if values changed
7. "What This Is" still accurate? — Update if research direction drifted
8. New references discovered? — Add to Key References

**After each milestone:**

1. Full review of all sections
2. Core Research Question check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update notation if conventions were refined
5. Review target publication — still appropriate venue?

</evolution>

<continuation_projects>

For ongoing research projects:

1. **Map existing work first** via `$gpd-map-theory`

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

See: .planning/PROJECT.md (updated [date])

**Core research question:** [One-liner from Core Research Question section]
**Current focus:** [Current phase name]
```

This ensures the agent reads current PROJECT.md context.

</state_reference>
