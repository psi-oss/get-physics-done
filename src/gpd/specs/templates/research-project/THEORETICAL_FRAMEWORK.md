---
template_version: 1
---

> **Context:** This template is for the `new-project` literature survey — researching a topic BEFORE
> starting a new project. For analyzing existing project artifacts, see `templates/analysis/`.

> **Used by:** `workflows/new-project.md` (as template for researcher subagents) and incorporated
> into `templates/research.md` (combined research template). Do not use this file as a standalone
> user-facing template — it is consumed by workflows and other templates.

# Theoretical Framework Research Template

Template for `.gpd/research/THEORETICAL_FRAMEWORK.md` - theoretical structure and framework for the research domain.

<template>

```markdown
# Theoretical Framework Research

**Domain:** [physics domain]
**Researched:** [date]
**Confidence:** [HIGH/MEDIUM/LOW]

## Standard Theoretical Framework

### Framework Overview
```

┌─────────────────────────────────────────────────────────────┐
│ [Fundamental Theory] │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ │
│ │ [Approx] │ │ [Approx] │ │ [Approx] │ │ [Approx] │ │
│ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ │
│ │ │ │ │ │
├───────┴────────────┴────────────┴────────────┴──────────────┤
│ [Working Equations] │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────────┐ │
│ │ [Computational Layer] │ │
│ └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────────┤
│ [Observable Predictions] │
│ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│ │ [Pred 1] │ │ [Pred 2] │ │ [Pred 3] │ │
│ └──────────┘ └──────────┘ └──────────┘ │
└─────────────────────────────────────────────────────────────┘

```

### Layer Responsibilities

| Layer | Responsibility | Typical Implementation |
|-------|----------------|------------------------|
| [Fundamental theory] | [What it governs] | [How it is usually formulated] |
| [Approximation scheme] | [What it simplifies] | [How it is usually applied] |
| [Computational method] | [What it computes] | [Standard algorithms/codes] |
| [Observables] | [What connects to experiment] | [How predictions are extracted] |

## Recommended Project Organization

```

research-project/
├── derivations/ # [purpose: symbolic/analytical work]
│ ├── [topic]/ # [organized by physical quantity]
│ └── [topic]/ # [organized by physical quantity]
├── src/ # [purpose: computational implementation]
│ ├── [module]/ # [purpose]
│ └── [module]/ # [purpose]
├── data/ # [purpose: input data and references]
├── tests/ # [purpose: validation suite]
└── paper/ # [purpose: manuscript]

```

### Organization Rationale

- **derivations/:** [Why separated from code - analytical vs. numerical]
- **src/:** [Why organized this way - follows the physics layers]
- **tests/:** [Why validation is first-class - physics has no compiler]

## Theoretical Patterns

### Pattern 1: [Pattern Name, e.g., "Perturbative Expansion"]

**What:** [description]
**When to use:** [conditions: e.g., "coupling constant << 1"]
**Trade-offs:** [e.g., "systematic but slow convergence; finite radius of convergence"]

**Example:**
```

[Brief mathematical example showing the pattern]

```

### Pattern 2: [Pattern Name, e.g., "Effective Field Theory"]

**What:** [description]
**When to use:** [conditions: e.g., "clear separation of scales"]
**Trade-offs:** [e.g., "model-independent but requires matching to UV completion"]

### Pattern 3: [Pattern Name, e.g., "Resummation"]

**What:** [description]
**When to use:** [conditions: e.g., "perturbative series has poor convergence"]
**Trade-offs:** [e.g., "improves strong-field behavior but introduces model dependence"]

## Calculation Flow

### From Theory to Observables

```

[Fundamental Lagrangian / Action]
|
v
[Equations of Motion] --> [Perturbative Solution] --> [Asymptotic Quantities]
| | |
v v v
[Exact Symmetries] [Order-by-order Terms] [Observable Predictions]

```

### Key Calculation Flows

1. **[Flow name]:** [description of how a calculation proceeds from theory to result]
2. **[Flow name]:** [description of another calculation pathway]

## Regime Map

| Parameter Regime | Appropriate Method | Accuracy |
|-----------------|-------------------|----------|
| [weak coupling] | [perturbation theory] | [O(alpha^{n+1})] |
| [strong coupling] | [lattice / numerical] | [systematic, improvable] |
| [extreme mass ratio] | [perturbation in mass ratio] | [O(q^{n+1})] |
| [comparable masses] | [numerical simulation] | [truncation error] |

### Regime Boundaries

1. **[Boundary 1]:** [What determines when one method breaks down and another is needed]
2. **[Boundary 2]:** [Another regime boundary]

## Common Theoretical Pitfalls

### Pitfall 1: [Name, e.g., "Gauge-Dependent Results"]

**What people do:** [the mistake]
**Why it is wrong:** [the problem it causes]
**Do this instead:** [the correct approach]

### Pitfall 2: [Name, e.g., "Truncation Without Error Estimate"]

**What people do:** [the mistake]
**Why it is wrong:** [the problem it causes]
**Do this instead:** [the correct approach]

## Connections to Experiment

### Observational Channels

| Observable | Experiment/Detector | Theoretical Input Required |
|-----------|--------------------|-----------------------------|
| [observable] | [experiment] | [what calculation provides] |
| [observable] | [experiment] | [what calculation provides] |

### Theory-Experiment Interface

| Boundary | Communication | Notes |
|----------|---------------|-------|
| [theory A <-> observation B] | [what quantity connects them] | [caveats] |

## Sources

- [Textbook references]
- [Review articles]
- [Key original papers]

---
*Theoretical framework research for: [domain]*
*Researched: [date]*
```

</template>

<guidelines>

**Framework Overview:**

- Use ASCII box-drawing diagrams for clarity
- Show the chain from fundamental theory to observables
- Identify where approximations enter

**Project Organization:**

- Separate derivations from computational code
- Organize code to mirror the physics layers
- Validation is not optional - physics has no type checker

**Theoretical Patterns:**

- Include the regime of validity for each pattern
- Explain trade-offs honestly (every approximation has a cost)
- Note when a pattern is overkill for the problem at hand

**Regime Map:**

- Be explicit about where different methods apply
- Include accuracy estimates for each regime
- Identify the boundaries where one method must hand off to another

**Common Pitfalls:**

- Specific to this physics domain, not generic advice
- Include what to do instead
- Helps prevent common errors during calculation

</guidelines>
