---
template_version: 1
---

> **Context:** This template is for the `new-project` literature survey — researching a topic BEFORE
> starting a new project. For analyzing existing project artifacts, see `templates/analysis/`.

> **NOTE:** Project-type pitfalls are inherited from `templates/project-types/`. This file captures project-SPECIFIC pitfalls not covered by the generic template.

# Pitfalls Research Template

Template for `.gpd/research/PITFALLS.md` -- survey of known subtleties, common errors, and pitfalls in the research domain.

<template>

```markdown
# Known Pitfalls Research

**Domain:** [physics domain]
**Researched:** [date]
**Confidence:** [HIGH/MEDIUM/LOW]

## Critical Pitfalls

### Pitfall 1: [Name]

**What goes wrong:**
[Description of the failure mode]

**Why it happens:**
[Root cause - why physicists make this mistake]

**How to avoid:**
[Specific prevention strategy]

**Warning signs:**
[How to detect this early before it corrupts results]

**Phase to address:**
[Which research phase should prevent this]

---

### Pitfall 2: [Name]

**What goes wrong:**
[Description of the failure mode]

**Why it happens:**
[Root cause]

**How to avoid:**
[Prevention strategy]

**Warning signs:**
[Early detection]

**Phase to address:**
[Research phase]

---

### Pitfall 3: [Name]

**What goes wrong:**
[Description]

**Why it happens:**
[Root cause]

**How to avoid:**
[Prevention]

**Warning signs:**
[Detection]

**Phase to address:**
[Phase]

---

[Continue for all critical pitfalls...]

## Approximation Shortcuts

Shortcuts that seem reasonable but introduce systematic errors.

| Shortcut   | Immediate Benefit | Long-term Cost | When Acceptable          |
| ---------- | ----------------- | -------------- | ------------------------ |
| [shortcut] | [benefit]         | [cost]         | [conditions, or "never"] |
| [shortcut] | [benefit]         | [cost]         | [conditions, or "never"] |
| [shortcut] | [benefit]         | [cost]         | [conditions, or "never"] |

## Convention Traps

Common mistakes when converting between different conventions or comparing with literature.

| Convention Issue                         | Common Mistake         | Correct Approach     |
| ---------------------------------------- | ---------------------- | -------------------- |
| [issue: e.g., "metric signature"]        | [what people do wrong] | [what to do instead] |
| [issue: e.g., "Fourier convention"]      | [what people do wrong] | [what to do instead] |
| [issue: e.g., "normalization of states"] | [what people do wrong] | [what to do instead] |

## Numerical Traps

Patterns that work for simple cases but fail for realistic calculations.

| Trap   | Symptoms         | Prevention     | When It Breaks     |
| ------ | ---------------- | -------------- | ------------------ |
| [trap] | [how you notice] | [how to avoid] | [parameter regime] |
| [trap] | [how you notice] | [how to avoid] | [parameter regime] |
| [trap] | [how you notice] | [how to avoid] | [parameter regime] |

## Interpretation Mistakes

Domain-specific errors in interpreting results beyond computational bugs.

| Mistake                                                                            | Risk                             | Prevention     |
| ---------------------------------------------------------------------------------- | -------------------------------- | -------------- |
| [mistake: e.g., "confusing coordinate and physical quantities"]                    | [what conclusion would be wrong] | [how to avoid] |
| [mistake: e.g., "over-interpreting perturbative result beyond regime of validity"] | [what goes wrong]                | [how to avoid] |
| [mistake: e.g., "ignoring systematic uncertainties"]                               | [what goes wrong]                | [how to avoid] |

## Publication Pitfalls

Common mistakes specific to writing up and presenting physics results.

| Pitfall                                                                  | Impact                 | Better Approach      |
| ------------------------------------------------------------------------ | ---------------------- | -------------------- |
| [pitfall: e.g., "claiming precision beyond validation"]                  | [credibility risk]     | [what to do instead] |
| [pitfall: e.g., "not stating all assumptions explicitly"]                | [reproducibility risk] | [what to do instead] |
| [pitfall: e.g., "comparing with literature using different conventions"] | [wrong conclusions]    | [what to do instead] |

## "Looks Correct But Is Not" Checklist

Things that appear right but are missing critical pieces.

- [ ] **[Calculation]:** Often missing [thing] -- verify [check]
- [ ] **[Calculation]:** Often missing [thing] -- verify [check]
- [ ] **[Calculation]:** Often missing [thing] -- verify [check]
- [ ] **[Calculation]:** Often missing [thing] -- verify [check]

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall   | Recovery Cost   | Recovery Steps |
| --------- | --------------- | -------------- |
| [pitfall] | LOW/MEDIUM/HIGH | [what to do]   |
| [pitfall] | LOW/MEDIUM/HIGH | [what to do]   |
| [pitfall] | LOW/MEDIUM/HIGH | [what to do]   |

## Pitfall-to-Phase Mapping

How research phases should address these pitfalls.

| Pitfall   | Prevention Phase | Verification                      |
| --------- | ---------------- | --------------------------------- |
| [pitfall] | Phase [X]        | [how to verify prevention worked] |
| [pitfall] | Phase [X]        | [how to verify prevention worked] |
| [pitfall] | Phase [X]        | [how to verify prevention worked] |

## Sources

- [Erratum papers and corrections in the literature]
- [Review articles noting common errors]
- [Textbook warnings and exercises designed around common mistakes]
- [Personal experience and group knowledge]

---

_Known pitfalls research for: [domain]_
_Researched: [date]_
```

</template>

<guidelines>

**Critical Pitfalls:**

- Focus on physics-domain-specific issues, not generic computational mistakes
- Include warning signs -- early detection prevents months of wasted work
- Link to specific research phases -- makes pitfalls actionable

**Approximation Shortcuts:**

- Be realistic -- some shortcuts are acceptable in exploratory work
- Note when shortcuts are "never acceptable" vs. "only for order-of-magnitude estimates"
- Include the long-term cost (systematic error, wrong physics) to inform tradeoffs

**Convention Traps:**

- These are the #1 source of errors when comparing with literature
- Metric signature, Fourier convention, and normalization differences cause the most pain
- Always specify which convention is used and how to convert

**Numerical Traps:**

- Include the parameter regime where problems appear
- Focus on what is relevant for this project's parameter space
- Do not over-engineer for hypothetical regimes

**Interpretation Mistakes:**

- Beyond computational correctness -- is the physics conclusion correct?
- Example: A gauge-dependent quantity plotted as if it were physical
- Include what wrong conclusion would be drawn

**"Looks Correct But Is Not":**

- Checklist format for verification during research
- Common when moving from derivation to paper
- Prevents "the algebra is right but the physics is wrong" situations

**Pitfall-to-Phase Mapping:**

- Critical for research planning
- Each pitfall should map to a phase that prevents it
- Informs the order of calculations and checks

</guidelines>
