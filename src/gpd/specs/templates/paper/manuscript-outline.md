---
template_version: 1
---

<!-- Used by: write-paper workflow for initial manuscript planning. -->

# Manuscript Outline Template

Template for `.gpd/paper/MANUSCRIPT_OUTLINE.md` — maps research results to paper sections following standard physics paper structure.

---

## File Template

```markdown
# Manuscript Outline: [Paper Title]

**Target journal:** [e.g., Physical Review Letters, JHEP, Physical Review B]
**Format constraints:** [e.g., PRL: 4 pages + references; PRB: no limit; JHEP: no limit]
**LaTeX class:** [e.g., revtex4-2, jheppub, elsarticle]

## Title and Authors

**Working title:** [Title — aim for specific and descriptive]
**Authors:** [Author list in order]
**Affiliations:** [Institution(s)]

## Abstract

**Status:** [Draft / Revised / Final]

[One paragraph, ~150-250 words. Structure: context (1-2 sentences), gap/problem (1 sentence), what we did (1-2 sentences), key result (1-2 sentences), implication (1 sentence).]

**Key numbers to include:** [e.g., "critical temperature T_c = 0.893(5)", "cross section sigma = 12.3 +/- 0.4 pb"]

## Section Map

### 1. Introduction

**Purpose:** Motivate the work, state the problem, summarize the result
**Source phases:** [Phase 1 (literature review)]
**Key points:**

- [Context: what is known and why it matters]
- [Gap: what is not known or what discrepancy exists]
- [This work: what we do and why it resolves the gap]
- [Preview of main result — one sentence]

**Key references:** [List 5-10 essential references to cite here]
**Estimated length:** [e.g., 1-1.5 pages]
**Status:** [Not started / Draft / Revised / Final]

### 2. [Setup / Model / Formalism]

**Purpose:** Define the system, Lagrangian/Hamiltonian, approximations, and notation
**Source phases:** [Phase 2 (formalism development)]
**Key content:**

- [Starting Lagrangian/Hamiltonian/model definition]
- [Key approximations and their justification]
- [Notation conventions established here]
- [Connection to previous work — what is new vs standard]

**Key equations:** [List equation labels from CALCULATION_LOG.md, e.g., Eq. (02.1), Eq. (02.3)]
**Estimated length:** [e.g., 2-3 pages]
**Status:** [Not started / Draft / Revised / Final]

### 3. [Method / Calculation / Derivation]

**Purpose:** Present the core technical work
**Source phases:** [Phase 3 (calculation/simulation)]
**Key content:**

- [Method description: analytic technique or numerical algorithm]
- [Key intermediate steps the reader needs to follow the argument]
- [Technical details that enable reproducibility]

**Key equations:** [e.g., Eq. (03.2), Eq. (03.5)]
**Figures in this section:** [Fig. X: description]
**Estimated length:** [e.g., 3-5 pages]
**Status:** [Not started / Draft / Revised / Final]

### 4. Results

**Purpose:** Present the main findings
**Source phases:** [Phase 3 (calculation), Phase 4 (validation)]
**Key content:**

- [Result 1: description, equation/table/figure reference]
- [Result 2: description, equation/table/figure reference]
- [Comparison with known limits or previous work]
- [Error analysis and uncertainty quantification]

**Key equations:** [e.g., Eq. (03.8) — main result]
**Figures in this section:** [Fig. Y: main result plot; Fig. Z: comparison]
**Tables in this section:** [Table I: numerical results]
**Estimated length:** [e.g., 2-4 pages]
**Status:** [Not started / Draft / Revised / Final]

### 5. Discussion

**Purpose:** Interpret results, compare with literature, discuss limitations
**Source phases:** [Phase 4 (validation), Phase 1 (literature context)]
**Key points:**

- [Interpretation of main result — what does it mean physically?]
- [Comparison with prior work: agreement or disagreement and why]
- [Limitations: which approximations might break down?]
- [Future directions: what should be done next?]

**Estimated length:** [e.g., 1-2 pages]
**Status:** [Not started / Draft / Revised / Final]

### 6. Conclusion

**Purpose:** Summarize findings and state the takeaway
**Key points:**

- [Restate the problem and what was accomplished]
- [The main quantitative result(s)]
- [Broader significance]

**Estimated length:** [e.g., 0.5-1 page]
**Status:** [Not started / Draft / Revised / Final]

### Appendices

**Appendix A: [Title]**

- **Purpose:** [e.g., Detailed derivation of Eq. (03.2)]
- **Source phase:** [Phase X]
- **Status:** [Not started / Draft / Revised / Final]

**Appendix B: [Title]**

- **Purpose:** [e.g., Convergence tests for numerical results]
- **Source phase:** [Phase X]
- **Status:** [Not started / Draft / Revised / Final]

## Supplemental Material

[If applicable — additional data, extended tables, code availability statement]

- [Item 1: description and source]
- [Item 2: description and source]

## Cross-Reference Map

| Paper Element        | Source Phase | Source File(s)                   | Key Equations/Results |
| -------------------- | ------------ | -------------------------------- | --------------------- |
| [Section 2, Eq. 1]   | [Phase 2]    | [CALCULATION_LOG.md, Eq. (02.1)] | [Lagrangian]          |
| [Section 4, Fig. 2]  | [Phase 3]    | [results/plot_main.py]           | [Main result plot]    |
| [Section 4, Table I] | [Phase 3]    | [results/data.json]              | [Numerical values]    |
| [Appendix A]         | [Phase 2]    | [CALCULATION_LOG.md, Calc. 02.3] | [Detailed derivation] |

## Writing Progress

| Section      | Draft | Self-Review | Co-author Review | Final |
| ------------ | ----- | ----------- | ---------------- | ----- |
| Abstract     | [ ]   | [ ]         | [ ]              | [ ]   |
| Introduction | [ ]   | [ ]         | [ ]              | [ ]   |
| Setup        | [ ]   | [ ]         | [ ]              | [ ]   |
| Method       | [ ]   | [ ]         | [ ]              | [ ]   |
| Results      | [ ]   | [ ]         | [ ]              | [ ]   |
| Discussion   | [ ]   | [ ]         | [ ]              | [ ]   |
| Conclusion   | [ ]   | [ ]         | [ ]              | [ ]   |
| Appendix A   | [ ]   | [ ]         | [ ]              | [ ]   |
| References   | [ ]   | [ ]         | [ ]              | [ ]   |
```

<guidelines>

**When to create this file:**

- During paper-writing phase planning (Phase 5 or equivalent)
- After all calculation and validation phases are complete
- Can be drafted earlier as a skeleton to guide what results are needed

**Section structure:**

- Follow the standard physics paper structure: Intro, Setup, Method, Results, Discussion, Conclusion
- Adapt section names to the subfield (e.g., "Model" for condensed matter, "Formalism" for QFT, "Observations" for astrophysics)
- PRL papers may merge Setup+Method and Discussion+Conclusion due to length constraints

**Cross-reference map:**

- Every equation, figure, and table in the paper must trace back to a specific phase and source file
- This ensures no result appears in the paper without a verified derivation/computation behind it
- Update the map as sections are drafted

**Writing order (recommended):**

1. Figures and tables first (the results drive the narrative)
2. Results section (describe what the figures show)
3. Method/Calculation section (how we got the results)
4. Setup/Model section (what system we studied)
5. Discussion (what it means)
6. Introduction (now you know the full story)
7. Conclusion and Abstract (summary of the above)

**Journal-specific notes:**

- PRL: 4 pages (3750 words) + references; 1 Supplemental Material file allowed
- PRB/PRD/PRC: no strict page limit but be concise
- JHEP: no page limit; extensive appendices are common
- Nature/Science: ~3000 words main text; extensive Methods and Supplementary

</guidelines>
