---
template_version: 1
---

> **Status:** Supplemental research template. The current `new-project` workflow does not spawn a
> standalone `KEY_RESULTS.md`; its live outputs are `PRIOR-WORK.md`, `METHODS.md`,
> `COMPUTATIONAL.md`, `PITFALLS.md`, and `SUMMARY.md`.
>
> Keep this template only if you intentionally add an extra key-results survey artifact. For
> analyzing existing project artifacts, see `templates/analysis/`.

# Key Results Research Template

Template for `.gpd/research/KEY_RESULTS.md` - key results, predictions, and deliverables for the research domain.

<template>

```markdown
# Key Results Research

**Domain:** [physics domain]
**Researched:** [date]
**Confidence:** [HIGH/MEDIUM/LOW]

## Results Landscape

### Established Results (Community Expects These)

Results that any serious calculation in this domain must reproduce. Missing these means something is wrong.

| Result   | Why Expected         | Complexity      | Notes                  |
| -------- | -------------------- | --------------- | ---------------------- |
| [result] | [standard benchmark] | LOW/MEDIUM/HIGH | [implementation notes] |
| [result] | [community standard] | LOW/MEDIUM/HIGH | [implementation notes] |
| [result] | [textbook result]    | LOW/MEDIUM/HIGH | [implementation notes] |

### Novel Predictions (Research Contribution)

Results that would constitute a genuine advance. Not required to reproduce known physics, but valuable.

| Prediction   | Scientific Value | Complexity      | Notes            |
| ------------ | ---------------- | --------------- | ---------------- |
| [prediction] | [why it matters] | LOW/MEDIUM/HIGH | [approach notes] |
| [prediction] | [why it matters] | LOW/MEDIUM/HIGH | [approach notes] |
| [prediction] | [why it matters] | LOW/MEDIUM/HIGH | [approach notes] |

### Non-Results (Commonly Attempted, Often Misleading)

Calculations that seem valuable but create problems or have been superseded.

| Calculation   | Why Attempted    | Why Problematic   | Alternative       |
| ------------- | ---------------- | ----------------- | ----------------- |
| [calculation] | [surface appeal] | [actual problems] | [better approach] |
| [calculation] | [surface appeal] | [actual problems] | [better approach] |

## Result Dependencies
```

[Result A]
└──requires──> [Result B]
└──requires──> [Result C]

[Result D] ──extends──> [Result A]

[Result E] ──conflicts──> [Result F]

```

### Dependency Notes

- **[Result A] requires [Result B]:** [why the dependency exists]
- **[Result D] extends [Result A]:** [how they build on each other]
- **[Result E] conflicts with [Result F]:** [why they are incompatible assumptions]

## Minimum Viable Calculation

### Core Results (Phase 1)

Minimum set of results needed to validate the approach and have a publishable unit.

- [ ] [Result] -- [why essential]
- [ ] [Result] -- [why essential]
- [ ] [Result] -- [why essential]

### Extensions After Validation (Phase 2)

Results to add once the core calculation is verified.

- [ ] [Result] -- [trigger for adding: e.g., "once leading order is validated"]
- [ ] [Result] -- [trigger for adding]

### Future Work (Phase 3+)

Results to defer until the main paper is complete.

- [ ] [Result] -- [why defer: e.g., "requires new formalism"]
- [ ] [Result] -- [why defer]

## Result Prioritization Matrix

| Result | Scientific Impact | Computational Cost | Priority |
|--------|------------------|--------------------| ---------|
| [result] | HIGH/MEDIUM/LOW | HIGH/MEDIUM/LOW | P1/P2/P3 |
| [result] | HIGH/MEDIUM/LOW | HIGH/MEDIUM/LOW | P1/P2/P3 |
| [result] | HIGH/MEDIUM/LOW | HIGH/MEDIUM/LOW | P1/P2/P3 |

**Priority key:**
- P1: Must have for the paper
- P2: Should have, strengthens the paper significantly
- P3: Nice to have, future publication

## Comparison with Existing Literature

| Result | Group A | Group B | Our Approach |
|--------|---------|---------|--------------|
| [result] | [their method/value] | [their method/value] | [our plan] |
| [result] | [their method/value] | [their method/value] | [our plan] |

## Sources

- [Key papers in this domain]
- [Review articles surveying the field]
- [Experimental results that motivate predictions]

---
*Key results research for: [domain]*
*Researched: [date]*
```

</template>

<guidelines>

**Established Results:**

- These are non-negotiable benchmarks
- Failing to reproduce them signals an error, not new physics
- Example: Any PN waveform code must match Newtonian orbital decay

**Novel Predictions:**

- These are where the scientific contribution lies
- Should be clearly motivated by either theoretical interest or experimental need
- Do not overreach; a solid incremental result beats a speculative large claim

**Non-Results:**

- Prevent wasted effort by documenting what seems valuable but is not
- Include the alternative approach
- Example: "Computing to extremely high PN order" may be less valuable than "resumming the known orders"

**Result Dependencies:**

- Critical for planning the order of calculations
- If Result A requires Result B, derive B first
- Conflicts inform what cannot be combined in the same framework

**Minimum Viable Calculation:**

- Be ruthless about what is truly minimum for a publishable paper
- "Nice to have" is not minimum
- Compute the core result, validate it, then extend

</guidelines>
