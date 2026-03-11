---
template_version: 1
type: supplemental-material
---

# Supplemental Material Template

Template for supplemental material accompanying a physics paper.

---

## File Template

```markdown
# Supplemental Material for "[Paper Title]"

[Authors]

## Contents

| Section | Description | Page |
|---------|-------------|------|
| A | Extended Derivations | |
| B | Computational Details | |
| C | Additional Figures | |
| D | Data Tables | |
| E | Code and Data Availability | |

---

## Section A: Extended Derivations

[Derivations too long for the main text but necessary for reproducibility. Each derivation should:]
- State the starting point (equation from main text)
- Show all intermediate steps
- Arrive at the result quoted in the main text
- Note any approximations made and their validity

### A.1 [Derivation Name]

Starting from Eq. (N) of the main text:

$$
[starting equation]
$$

[Step-by-step derivation...]

This yields Eq. (M) of the main text.

### A.2 [Derivation Name]

[...]

---

## Section B: Computational Details

### B.1 Algorithm Parameters

| Parameter | Value | Justification |
|-----------|-------|---------------|
| [e.g., Grid size] | [value] | [convergence test reference] |
| [e.g., Time step] | [value] | [stability criterion] |
| [e.g., Disorder samples] | [value] | [error bar target] |

### B.2 Convergence Tests

[Document convergence of numerical results with respect to key parameters. Include convergence plots or tables showing how the result changes as resolution/samples increase.]

### B.3 Computational Resources

- **Hardware:** [CPU/GPU specs, cluster name]
- **Total CPU hours:** [estimate]
- **Memory requirements:** [per-job peak]
- **Software versions:** See `reproducibility-manifest.json`

---

## Section C: Additional Figures

[Figures referenced in the main text as "see Supplemental Material". Each figure should have a full caption.]

### Figure S1: [Description]

[Figure and caption]

### Figure S2: [Description]

[Figure and caption]

---

## Section D: Data Tables

[Extended numerical data, parameter scans, convergence tests. Tables too large for the main text.]

### Table S1: [Description]

| [Column 1] | [Column 2] | [Column 3] | [Uncertainty] |
|-------------|-------------|-------------|---------------|
| | | | |

---

## Section E: Code and Data Availability

- **Repository:** [URL]
- **DOI:** [Zenodo/Figshare DOI for archived version]
- **License:** [License]
- **Requirements:** See `reproducibility-manifest.json` for environment specifications
- **Data:** [Where raw/processed data can be obtained]

---

## References

[References specific to the supplemental material that are not in the main text]
```

---

## Guidelines

**What belongs in Supplemental Material:**
- Derivations longer than ~10 lines that would break the flow of the main text
- Convergence tests and parameter sensitivity studies
- Additional figures that support but don't drive the narrative
- Extended data tables (parameter scans, benchmark comparisons)
- Algorithm details and pseudocode
- Proof of technical lemmas

**What does NOT belong in SM:**
- Core results (these must be in the main text)
- Key figures that drive the paper's narrative
- Method descriptions needed to understand the results
- Anything the referee needs to evaluate the paper's claims

**Cross-referencing:**
- Main text refers to SM sections as "see Supplemental Material, Sec. A"
- SM refers back to main text equations by number
- Keep SM self-contained enough that a reader can follow each section independently

**For PRL:**
- SM is essential — the 4-page limit means most technical details go here
- Referees review SM equally, so it must be complete and rigorous
