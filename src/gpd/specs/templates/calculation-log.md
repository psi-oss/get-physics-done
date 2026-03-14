---
template_version: 1
---

<!-- Used by: gpd-executor during multi-step derivations. Reference from execute-plan workflow. -->

# Calculation Log Template

Template for `.gpd/phases/XX-name/CALCULATION_LOG.md` - detailed record of derivations and computations within a phase.

**Purpose:** Tracks the step-by-step reasoning of each calculation, including intermediate results, checks performed, and errors caught. Serves as a lab notebook for theoretical and computational work.

---

## File Template

```markdown
# Calculation Log: Phase [XX] - [Name]

**Phase:** [XX-name]
**Started:** [YYYY-MM-DD]
**Status:** [In Progress / Complete]

---

## Calculation [XX.1]: [Name]

**Objective:** [What is being computed and why]
**Method:** [Analytical / Numerical / Mixed]
**Started:** [timestamp]

### Setup

**Starting point:**

- [Equation or expression being evaluated, with reference: e.g., "Starting from Eq. (03.2)"]
- [Key assumptions: e.g., "Assuming $T \ll T_c$, so thermal fluctuations negligible"]

**Expected result:**

- [Prediction from hypothesis-driven analysis, or "exploratory - no prediction"]
- [Known limiting cases to check against]

### Steps

**Step 1: [Description]**

$$
[Key intermediate expression]
$$

- [Reasoning or technique applied: e.g., "Integration by parts on the second term"]
- [Check: e.g., "Dimensions: $[E] \cdot [L]^{-3}$ ✓"]

**Step 2: [Description]**

$$
[Next intermediate expression]
$$

- [Reasoning]
- [Check: e.g., "Reduces to free-particle result when $g \to 0$ ✓"]

**Step 3: [Description]**

$$
[Result]
$$

- [Final simplification]

### Result

**Final expression:**

$$
[Equation, labeled as Eq. (XX.N)]
$$

**Verification:**

- [ ] Dimensional analysis: [Result]
- [ ] Limiting case 1: [parameter] → [value]: [Expected] vs [Got]
- [ ] Limiting case 2: [parameter] → [value]: [Expected] vs [Got]
- [ ] Numerical cross-check: [Description and result]
- [ ] Symmetry check: [e.g., "Result invariant under $x \to -x$ ✓"]

**Errors caught:**

- [Any mistakes found and corrected during the calculation, or "None"]

**Completed:** [timestamp]
**Committed:** [hash] `calc(XX-NN): [description]`

---

## Calculation [XX.2]: [Name]

[Same structure as above]

---

## Numerical Computation [XX.3]: [Name]

**Objective:** [What is being computed numerically]
**Method:** Numerical
**Code:** [`path/to/script.py`]
**Started:** [timestamp]

### Configuration

| Parameter   | Value | Units   | Notes                           |
| ----------- | ----- | ------- | ------------------------------- |
| [Grid size] | [N]   | —       | [Convergence tested]            |
| [Time step] | [dt]  | [units] | [Stability criterion satisfied] |

### Convergence Tests

| Resolution | Result  | Relative Change | Notes                  |
| ---------- | ------- | --------------- | ---------------------- |
| [N=128]    | [value] | —               | [Baseline]             |
| [N=256]    | [value] | [e.g., 2.3%]    | [Not converged]        |
| [N=512]    | [value] | [e.g., 0.08%]   | [Converged]            |
| [N=1024]   | [value] | [e.g., 0.002%]  | [Confirms convergence] |

### Result

**Final value:** [value ± uncertainty] [units]
**At resolution:** [N=512]
**Runtime:** [e.g., 45s on M1 MacBook]

**Comparison with analytical result:**

- Analytical: [value] (from Eq. (XX.N))
- Numerical: [value ± error]
- Agreement: [e.g., "Within 0.1%, consistent with $O(1/N^2)$ discretization error"]

**Completed:** [timestamp]
**Committed:** [hash] `calc(XX-NN): [description]`

---

## Error Log

[Document errors found during calculations - these are valuable for future reference]

### Error [XX.E1]: [Brief description]

- **Found in:** Calculation [XX.N], Step [M]
- **Symptom:** [How the error manifested: e.g., "Wrong sign in limiting case"]
- **Root cause:** [e.g., "Forgot factor of $(-1)^l$ from angular momentum coupling"]
- **Fix:** [What was corrected]
- **Lesson:** [What to watch for in future: e.g., "Always track phase factors through Clebsch-Gordan"]

---

## Summary

| Calculation  | Result                       | Status                               | Commit |
| ------------ | ---------------------------- | ------------------------------------ | ------ |
| [XX.1: Name] | [Key result or equation ref] | [✓ Verified / ⚠ Partial / ✗ Failed] | [hash] |
| [XX.2: Name] | [Key result or equation ref] | [status]                             | [hash] |
| [XX.3: Name] | [Key result or equation ref] | [status]                             | [hash] |

**Errors caught:** [N] (see Error Log)
**Open issues:** [Any unresolved problems]

---

_Calculation log: Phase [XX-name]_
_Last updated: [date]_
```

<guidelines>
**What belongs in CALCULATION_LOG.md:**
- Step-by-step derivation records with intermediate expressions
- Dimensional analysis and limiting case checks at each step
- Numerical computation details with convergence tests
- Error log documenting mistakes found and corrected
- Links between calculations (which result feeds into which)

**What does NOT belong here:**

- Final polished results (those go in SUMMARY.md)
- Project-wide notation (that's NOTATION_GLOSSARY.md)
- Broad theoretical framing (that's PRIOR-WORK.md or FORMALISM.md)
- Code documentation (that lives in source files)

**When filling this template:**

- Create one entry per distinct calculation or derivation
- Record intermediate steps, not just start and finish
- Perform dimensional analysis at EVERY step, not just the end
- Check limiting cases as you go, not just at the final result
- Document ALL errors found - they're valuable for future phases

**Relationship to other templates:**

- CALCULATION_LOG.md is the detailed "lab notebook" within a phase
- SUMMARY.md extracts the key results and equations for cross-phase reference
- Verification reports (VERIFICATION.md) formalize the checks noted here
- Hypothesis-driven plans reference predictions that are checked in the log

**Why a calculation log matters:**

- Debugging: when a later phase finds an error, trace back through steps
- Reproducibility: exact sequence of operations recorded
- Learning: error log captures common pitfalls for the specific problem
- Verification: dimensional checks and limiting cases documented as performed
- Context preservation: future sessions can reconstruct the reasoning
  </guidelines>
