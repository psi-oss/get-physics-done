---
template_version: 1
---

> **Context:** This template is for the `new-project` literature survey — researching a topic BEFORE
> starting a new project. For analyzing existing project artifacts, see `templates/analysis/`.

# Research Summary Template

Template for `.gpd/research/SUMMARY.md` - executive summary of research analysis with roadmap implications.

<template>

```markdown
# Research Summary

**Project:** [name from project definition]
**Domain:** [physics domain]
**Researched:** [date]
**Confidence:** [HIGH/MEDIUM/LOW]

## Executive Summary

[2-3 paragraph overview of the research analysis findings]

- What type of physics problem this is and how experts approach it
- The recommended theoretical and computational approach based on analysis
- Key risks and how to mitigate them

## Key Findings

### Computational Approaches

[Summary from COMPUTATIONAL.md -- 1-2 paragraphs]

**Core approach:**

- [Theory/method]: [purpose] -- [why recommended]
- [Theory/method]: [purpose] -- [why recommended]
- [Theory/method]: [purpose] -- [why recommended]

### Prior Work Landscape

[Summary from PRIOR-WORK.md]

**Must reproduce (benchmarks):**

- [Result] -- community expects this
- [Result] -- community expects this

**Novel predictions (contributions):**

- [Result] -- scientific advance
- [Result] -- scientific advance

**Defer (future work):**

- [Result] -- not essential for first paper

### Methods and Tools

[Summary from METHODS.md -- 1 paragraph]

**Major components:**

1. [Method/tool] -- [purpose]
2. [Method/tool] -- [purpose]
3. [Method/tool] -- [purpose]

### Critical Pitfalls

[Top 3-5 from PITFALLS.md]

1. **[Pitfall]** -- [how to avoid]
2. **[Pitfall]** -- [how to avoid]
3. **[Pitfall]** -- [how to avoid]

## Implications for Research Plan

Based on analysis, suggested phase structure:

### Phase 1: [Name, e.g., "Foundation and Leading Order"]

**Rationale:** [why this comes first based on analysis]
**Delivers:** [what this phase produces]
**Validates:** [what benchmarks are checked]
**Avoids:** [pitfall from PITFALLS.md]

### Phase 2: [Name, e.g., "Higher-Order Corrections"]

**Rationale:** [why this order]
**Delivers:** [what this phase produces]
**Uses:** [methods from METHODS.md]
**Builds on:** [what from Phase 1]

### Phase 3: [Name, e.g., "Applications and Predictions"]

**Rationale:** [why this order]
**Delivers:** [what this phase produces]

[Continue for suggested phases...]

### Phase Ordering Rationale

- [Why this order based on dependencies discovered]
- [Why this grouping based on theoretical structure]
- [How this avoids pitfalls from analysis]

### Phases Requiring Deep Investigation

Phases likely needing additional theoretical or computational exploration:

- **Phase [X]:** [reason -- e.g., "novel derivation needed, no literature precedent"]
- **Phase [Y]:** [reason -- e.g., "numerical method untested in this regime"]

Phases with established methodology (straightforward execution):

- **Phase [X]:** [reason -- e.g., "well-documented technique, multiple references available"]

## Confidence Assessment

| Area                     | Confidence        | Notes    |
| ------------------------ | ----------------- | -------- |
| Computational Approaches | [HIGH/MEDIUM/LOW] | [reason] |
| Prior Work               | [HIGH/MEDIUM/LOW] | [reason] |
| Methods                  | [HIGH/MEDIUM/LOW] | [reason] |
| Pitfalls                 | [HIGH/MEDIUM/LOW] | [reason] |

**Overall confidence:** [HIGH/MEDIUM/LOW]

### Gaps to Address

[Any areas where analysis was inconclusive or needs work during execution]

- [Gap]: [how to handle during research]
- [Gap]: [how to handle during research]

## Sources

### Primary (HIGH)

- [Textbook/review] -- [topics]
- [Key paper] -- [what was verified]

### Secondary (MEDIUM)

- [Source] -- [finding]

### Tertiary (LOW)

- [Source] -- [finding, needs independent verification]

---

_Research analysis completed: [date]_
_Ready for research plan: yes_
```

</template>

<guidelines>

**Executive Summary:**

- Write for someone who will only read this section
- Include the key recommendation and main risk
- 2-3 paragraphs maximum

**Key Findings:**

- Summarize, do not duplicate full documents
- Reference detailed docs (PRIOR-WORK.md, COMPUTATIONAL.md, etc.)
- Focus on what matters for planning the research

**Implications for Research Plan:**

- This is the most important section
- Directly informs the order and grouping of calculations
- Be explicit about phase suggestions and rationale
- Include flags for phases needing deeper investigation

**Confidence Assessment:**

- Be honest about uncertainty
- Note gaps that need resolution during execution
- HIGH = verified with textbooks and multiple references
- MEDIUM = community consensus, multiple sources agree
- LOW = single source, inference, or novel territory

**Integration with research planning:**

- This file is loaded as context during research planning
- Phase suggestions here become the starting point for the research roadmap
- Investigation flags inform which phases need extra care

</guidelines>
