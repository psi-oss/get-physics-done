---
template_version: 1
---

> **Context:** This template is for the `new-project` literature survey — researching a topic BEFORE
> starting a new project. For analyzing an existing project's methods, use the split `map-research`
> outputs in `.gpd/research-map/` (`FORMALISM.md`, `ARCHITECTURE.md`, `CONVENTIONS.md`,
> `VALIDATION.md`, `STRUCTURE.md`) rather than a standalone methods template.

> **Used by:** `workflows/new-project.md` (as template for researcher subagents). Its content is
> incorporated into `templates/research.md` (the primary research template — see the "Methods and
> Approaches" section there). Do not use this file as a standalone user-facing template.

# Methods Research Template

Template for `.gpd/research/METHODS.md` - recommended methods and computational tools for the research domain.

<template>

````markdown
# Methods Research

**Domain:** [physics domain]
**Researched:** [date]
**Confidence:** [HIGH/MEDIUM/LOW]

## Recommended Methods

### Analytical Methods

| Method   | Purpose            | Why Recommended                      |
| -------- | ------------------ | ------------------------------------ |
| [method] | [what it computes] | [why experts use it for this domain] |
| [method] | [what it computes] | [why experts use it for this domain] |
| [method] | [what it computes] | [why experts use it for this domain] |

### Numerical Methods

| Method   | Purpose          | When to Use                              |
| -------- | ---------------- | ---------------------------------------- |
| [method] | [what it solves] | [specific use case and parameter regime] |
| [method] | [what it solves] | [specific use case]                      |
| [method] | [what it solves] | [specific use case]                      |

### Computational Tools

| Tool           | Version   | Purpose        | Notes                |
| -------------- | --------- | -------------- | -------------------- |
| [tool/library] | [version] | [what it does] | [configuration tips] |
| [tool/library] | [version] | [what it does] | [configuration tips] |

## Software Stack

### Core Technologies

| Technology | Version   | Purpose        | Why Recommended                      |
| ---------- | --------- | -------------- | ------------------------------------ |
| [name]     | [version] | [what it does] | [why it is standard for this domain] |
| [name]     | [version] | [what it does] | [why it is standard for this domain] |
| [name]     | [version] | [what it does] | [why it is standard for this domain] |

### Supporting Libraries

| Library | Version   | Purpose        | When to Use         |
| ------- | --------- | -------------- | ------------------- |
| [name]  | [version] | [what it does] | [specific use case] |
| [name]  | [version] | [what it does] | [specific use case] |
| [name]  | [version] | [what it does] | [specific use case] |

### Symbolic Computation

| Tool       | Version   | Purpose        | Notes                          |
| ---------- | --------- | -------------- | ------------------------------ |
| [CAS name] | [version] | [what it does] | [when to use vs. alternatives] |
| [CAS name] | [version] | [what it does] | [configuration notes]          |

## Installation

```bash
# Core computational environment
[e.g., "uv sync --extra dev"]

# Additional tools
[e.g., "pip install lalsuite"]

# External codes
[e.g., "See CONNECTIONS.md for external dependencies"]
```
````

## Alternatives Considered

| Recommended  | Alternative    | When to Use Alternative                  |
| ------------ | -------------- | ---------------------------------------- |
| [our choice] | [other option] | [conditions where alternative is better] |
| [our choice] | [other option] | [conditions where alternative is better] |

## What NOT to Use

| Avoid         | Why                | Use Instead               |
| ------------- | ------------------ | ------------------------- |
| [method/tool] | [specific problem] | [recommended alternative] |
| [method/tool] | [specific problem] | [recommended alternative] |

## Method Selection by Problem Type

**If [problem type: e.g., "weak coupling, high precision needed"]:**

- Use [method/approach]
- Because [reason]

**If [problem type: e.g., "strong coupling, qualitative behavior needed"]:**

- Use [method/approach]
- Because [reason]

**If [problem type: e.g., "large parameter space survey"]:**

- Use [method/approach]
- Because [reason]

## Validation Strategy by Method

| Method   | Validation Approach     | Key Benchmarks        |
| -------- | ----------------------- | --------------------- |
| [method] | [how to verify results] | [standard test cases] |
| [method] | [how to verify results] | [standard test cases] |

## Version Compatibility

| Tool A         | Compatible With | Notes                 |
| -------------- | --------------- | --------------------- |
| [tool@version] | [tool@version]  | [compatibility notes] |

## Sources

- [Textbooks on methods]
- [Review articles on computational techniques]
- [Official documentation for key tools]
- [Community best practices]

---

_Methods research for: [domain]_
_Researched: [date]_

```

</template>

<guidelines>

**Analytical Methods:**
- Include the regime of validity for each method
- Explain why this is the standard choice, not just what it does
- Focus on methods that affect the reliability of results

**Numerical Methods:**
- Include specific algorithms, not just categories
- Note parameter regime where each method is appropriate
- Include configuration recommendations (tolerances, grid sizes)

**Software Stack:**
- Include specific version numbers for reproducibility
- Explain why this tool is standard in the field
- Note when alternatives make sense

**Alternatives:**
- Do not just dismiss alternatives
- Explain when alternatives are genuinely better
- Helps researchers make informed decisions

**What NOT to Use:**
- Actively warn against outdated or problematic choices
- Explain the specific problem, not just "it is old"
- Provide the recommended alternative

**Validation Strategy:**
- Every method should have a validation approach
- Standard benchmarks exist for most methods in physics
- Not validating is not acceptable

</guidelines>
```
