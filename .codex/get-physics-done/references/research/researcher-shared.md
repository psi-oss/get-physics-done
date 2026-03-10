# Shared Research Philosophy and Protocols

Shared by `gpd-project-researcher` and `gpd-phase-researcher`. Loaded via `@` reference.

## Training Data = Hypothesis

The assistant's training is 6-18 months stale. Knowledge may be outdated, incomplete, or wrong. Physics moves fast at the frontier, especially in areas like lattice QCD, quantum computing, cosmological surveys, and machine-learning-assisted methods.

**Discipline:**

1. **Verify before asserting** — check arXiv, official documentation, or published literature before stating capabilities or results
2. **Prefer current sources** — recent arXiv preprints and published reviews trump training data
3. **Flag uncertainty** — LOW confidence when only training data supports a claim
4. **Distinguish conjecture from theorem** — clearly separate proven results from conjectures, numerical evidence, and heuristic arguments

## The Literature as Ground Truth

Physics research builds on centuries of accumulated knowledge. The literature is not optional background reading — it IS the foundation.

**The trap:** Attempting to derive everything from first principles when the result is well-established, or worse, unknowingly reproducing a known incorrect approach.

**The discipline:**

1. **Search before deriving** — check whether the result exists in Landau-Lifshitz, Weinberg, Peskin-Schroeder, Jackson, Sakurai, or the relevant standard references before planning a derivation from scratch
2. **Know the classic papers** — every subfield has seminal papers that define the standard approach; identify them
3. **Respect known no-go theorems** — Coleman-Mandula, Weinberg-Witten, Mermin-Wagner, Hohenberg, etc. constrain what is possible
4. **Track the state of the art** — review articles on arXiv (hep-th, cond-mat, astro-ph, quant-ph, etc.) summarize current understanding

## Honest Reporting

Research value comes from accuracy, not completeness theater.

**Report honestly:**

- "I couldn't find X" is valuable (investigate differently)
- "LOW confidence" is valuable (flags for validation)
- "Sources contradict" is valuable (surfaces genuine scientific disagreement)
- "This is an open problem" is valuable (prevents wasting effort on solved/unsolved confusion)
- "This integral has no known closed form" is valuable (now we plan numerical evaluation)
- "The sign convention varies across references" is valuable (now we fix conventions early)
- "This approximation breaks down for strong coupling" is valuable (flags regime of validity)

**Avoid:** Padding findings, stating unverified claims as fact, hiding uncertainty behind confident notation, presenting a specific gauge or convention choice as unique, citing papers you have not actually found or verified exist.

## Investigation, Not Confirmation

**Bad research:** Start with a preferred approach, find supporting evidence
**Good research:** Survey the landscape of approaches, identify which is appropriate for THIS problem, document why alternatives fail or are less suitable

Don't cherry-pick papers supporting your initial guess — find what the field actually does and let evidence drive recommendations. Pay special attention to negative results, no-go theorems, and known impossibility proofs.

## Physics-Specific Integrity

- **Respect dimensionality:** Every quantity must carry correct units. Flag dimensionless combinations.
- **Respect symmetries:** Identify all relevant symmetry groups before proposing methods. A method that breaks a physical symmetry is suspect.
- **Respect limiting cases:** Every proposed approach must reproduce known limiting cases (non-relativistic limit, classical limit, weak-coupling limit, etc.).
- **Respect conservation laws:** Energy, momentum, charge, and other conserved quantities must be preserved by numerical methods or the violation must be quantified.

## Rigor Calibration

Different phases require different levels of rigor. Identify the appropriate level:

| Level                        | Description                                       | When Appropriate                                     |
| ---------------------------- | ------------------------------------------------- | ---------------------------------------------------- |
| **Formal proof**             | Mathematically rigorous, all steps justified      | Mathematical physics, exact results, theorems        |
| **Physicist's proof**        | Logically sound, standard manipulations assumed   | Most theoretical calculations                        |
| **Controlled approximation** | Systematic expansion with error estimates         | Perturbation theory, asymptotic analysis             |
| **Numerical evidence**       | Computational verification without analytic proof | Complex systems, lattice calculations                |
| **Physical argument**        | Dimensional analysis, symmetry, limiting cases    | Initial estimates, sanity checks, intuition building |
| **Phenomenological**         | Fit to data, effective descriptions               | Contact with experiment, effective theories          |

---

## Tool Strategy

### Tool Priority

| Priority | Tool                       | Use For                                                                       | Trust Level          |
| -------- | -------------------------- | ----------------------------------------------------------------------------- | -------------------- |
| 1st      | web_search (arXiv)          | Papers, review articles, recent results, known solutions                      | HIGH (peer-reviewed) |
| 2nd      | web_fetch                   | arXiv abstracts, textbook tables of contents, lecture notes, documentation    | HIGH-MEDIUM          |
| 3rd      | web_search (general)        | Community discussions, computational tool comparisons, implementation details | Needs verification   |
| 4th      | Project search (`grep`/`glob`) | Existing implementations in this repo, prior work, related tasks              | HIGH (local)         |

### arXiv Search Strategy

1. Search `site:arxiv.org` with specific physics terms, equation names, or method names
2. Prioritize review articles (look for "review", "introduction to", "lectures on" in titles)
3. Check citation counts and author reputation when possible
4. For recent developments, restrict searches to last 2-3 years
5. For established methods, seek the original seminal paper AND a modern review

### Textbook and Reference Strategy

- Identify the standard textbook for the subfield
- Note specific chapters, sections, or equation numbers when possible
- Cross-reference between textbooks when conventions differ

### Computational Tool Documentation

- Search official documentation for libraries (SymPy, NumPy/SciPy, QuTiP, FEniCS, LAMMPS, Quantum ESPRESSO, etc.)
- Check version-specific features and known limitations
- Look for benchmark results and validation tests

### Reference Databases

For physical constants, particle data, atomic spectra, material properties:

- PDG (Particle Data Group): particle masses, coupling constants, decay rates
- NIST: atomic spectra, fundamental constants, material properties
- HITRAN/GEISA: molecular spectroscopy
- Materials Project / AFLOW: crystal structures, electronic properties
- Sloan Digital Sky Survey / Planck data: cosmological parameters
- LIGO Open Science Center: gravitational wave data

Prefer official database values over values quoted in papers.

### web_search Query Templates

```
Domain:      "[physics topic] computational methods [current year]"
Methods:     "[physics topic] numerical methods review"
Tools:       "[physics topic] simulation software comparison [current year]"
Data:        "[physics topic] experimental data [database name]"
Benchmarks:  "[method] benchmark [physics system]"
Problems:    "[method] numerical instabilities", "[method] known limitations"
```

Always include current year for tool/software queries. Use multiple query variations.

---

## Confidence Levels

| Level  | Sources                                                                                             | Use                         |
| ------ | --------------------------------------------------------------------------------------------------- | --------------------------- |
| HIGH   | Published reviews, textbooks, PDG/NIST values, multiple peer-reviewed papers agree                  | State as established result |
| MEDIUM | Recent arXiv preprints by established groups, single peer-reviewed source, computational benchmarks | State with attribution      |
| LOW    | Single arXiv preprint, blog post, unverified computation, training data only                        | Flag as needing validation  |

**Source priority:** Textbooks/Reviews -> Peer-reviewed papers -> arXiv preprints (cited) -> arXiv preprints (recent) -> web_search (verified) -> web_search (unverified)

### Verification Protocol

**All findings must be cross-checked:**

```
For each finding:
1. Published in peer-reviewed journal or established textbook? → YES: HIGH confidence
2. On arXiv with significant citations or by established group? → YES: MEDIUM-HIGH confidence
3. Do multiple independent references agree? → YES: Increase one level
4. Is it from a single lecture note or blog post? → Remains LOW, flag for validation
5. Does it contradict a known result? → RED FLAG, investigate thoroughly
```

**Never present LOW confidence findings as established physics.** For numerical values, always check against at least two independent sources.

---

## Research Pitfalls

### Approximation Scope Blindness

**Trap:** Assuming an approximation valid in one regime applies universally
**Prevention:** Always document the validity range of every approximation (e.g., perturbation theory requires g << 1, mean-field theory requires d > d_upper, WKB requires slowly varying potential). Identify where approximations break down.

### Outdated Results

**Trap:** Citing superseded results (e.g., old PDG values, pre-Planck cosmological parameters, results corrected by erratum)
**Prevention:** Check latest PDG/NIST values. Look for errata. Verify year of most recent review.

### Negative Claims Without Evidence

**Trap:** "This has not been solved" or "No closed-form solution exists" without verification
**Prevention:** Is there a no-go theorem? Has the problem been proven undecidable? Searched recent literature? "I didn't find a solution" does not equal "no solution exists."

### Convention Conflicts

**Trap:** Mixing results from sources using different conventions (East Coast vs. West Coast metric, different normalizations of generators, natural vs. SI units, different Fourier transform conventions)
**Prevention:** Identify conventions at the START. Create a convention table. Convert all referenced results to a single consistent set before planning any calculations.

### Numerical Method Worship / Instability Ignorance

**Trap:** Assuming a numerical method works because it was published, without checking convergence, stability, or applicability to your specific problem (stiff ODEs, ill-conditioned matrices, catastrophic cancellation, sign problems in Monte Carlo)
**Prevention:** Check benchmark results for similar systems. Verify convergence properties. Identify known failure modes of the method. Research the numerical aspects as carefully as the analytical aspects.

### Unit System Confusion

**Trap:** Mixing natural units, Gaussian CGS, SI, and atomic units without tracking conversion factors
**Prevention:** State the unit system up front. Track powers of hbar, c, k_B, and epsilon_0 explicitly until the final result.

### Symmetry-Breaking Artifacts

**Trap:** Using a discretization or approximation that breaks a physical symmetry (gauge invariance, Lorentz invariance, unitarity) without realizing it
**Prevention:** Identify all symmetries of the physical system. For each proposed method, verify which symmetries are preserved and which are broken. Quantify the symmetry violation if applicable.

### Overlooking Anomalies and Subtleties

**Trap:** Missing quantum anomalies, topological terms, boundary conditions, or other subtleties that invalidate a naive approach
**Prevention:** For each method, explicitly ask: "What could go wrong that isn't obvious at tree level / classical level / leading order?" Check the literature for known subtleties in this type of calculation. Specifically:

- **Anomalies:** Does the system have classical symmetries that could be anomalous? Check ABJ (chiral) anomaly, trace anomaly, gravitational anomaly. Verify anomaly matching between UV and IR descriptions ('t Hooft conditions).
- **Topological terms:** Are there theta terms, Chern-Simons terms, or WZW terms that contribute? Are topological invariants (Chern numbers, Berry phases) relevant?
- **Lattice artifacts:** If discretizing, does the method suffer from fermion doubling (Nielsen-Ninomiya theorem)? Does it break physical symmetries?
- **Ensemble subtleties:** Is the chosen thermodynamic ensemble appropriate? Are there non-equivalence issues near phase transitions? Is the order of limits important?

### Reinventing Known Results

**Trap:** Planning to derive something that Landau derived in 1937 or that appears as an exercise in Peskin-Schroeder
**Prevention:** Thorough literature search BEFORE planning derivations. Check standard references. If a result exists, cite it and move on.

---

## Pre-Submission Checklist

- [ ] All research domains investigated (foundations, methods, landscape, pitfalls)
- [ ] Conventions identified and documented (metric signature, units, normalizations)
- [ ] Regime of validity identified for every method recommended
- [ ] Key equations identified with source references
- [ ] Negative claims verified against published literature
- [ ] Multiple sources for critical claims (especially numerical values)
- [ ] arXiv IDs or DOIs provided for key references
- [ ] Alternative approaches documented in case primary approach fails
- [ ] Computational feasibility assessed (runtime estimates, memory requirements, numerical stability)
- [ ] Validation strategies identified (known limits, sum rules, symmetry checks, benchmark comparisons)
- [ ] Confidence levels assigned honestly
- [ ] Unit conventions stated explicitly
- [ ] Symmetries of the problem identified
- [ ] Known limiting cases listed
- [ ] No-go theorems checked — is this calculation actually possible?
- [ ] "What might I have missed?" review completed
