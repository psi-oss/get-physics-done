---
template_version: 1
---

> **Context:** This template is for the `map-theory` workflow — analyzing an EXISTING research project
> to understand its current state. For pre-project literature research, see `templates/research-project/`.

# Open Questions Template

Template for `.planning/analysis/OPEN_QUESTIONS.md` - captures known issues, unresolved questions, and potential problems with the approach.

**Purpose:** Surface actionable warnings about the research. Focused on "what to watch out for when extending or relying on these results."

---

## File Template

```markdown
# Open Questions

**Analysis Date:** [YYYY-MM-DD]

## Theoretical Gaps

**[Area/Topic]:**

- Issue: [What is missing or uncertain in the theoretical framework]
- Why it matters: [What conclusions are affected]
- Impact: [What breaks or becomes unreliable because of it]
- Resolution approach: [How to properly address it]

**[Area/Topic]:**

- Issue: [What is missing or uncertain]
- Why it matters: [Consequences]
- Impact: [What is affected]
- Resolution approach: [Path forward]

## Known Inconsistencies

**[Inconsistency description]:**

- Symptoms: [What looks wrong - e.g., "gauge dependence in physical observable"]
- Where it appears: [In which calculation or comparison]
- Workaround: [Temporary mitigation if any]
- Root cause: [If known - e.g., "incomplete cancellation at this order"]
- Blocked by: [If waiting on something - e.g., "requires 2-loop calculation"]

**[Inconsistency description]:**

- Symptoms: [What looks wrong]
- Where it appears: [Which calculation]
- Workaround: [Temporary mitigation if any]
- Root cause: [If known]

## Approximation Concerns

**[Approximation requiring care]:**

- Risk: [What could go wrong - e.g., "expansion parameter not small in this regime"]
- Current justification: [Why we think it is OK]
- Recommendations: [What checks should be performed]

**[Approximation requiring care]:**

- Risk: [What could go wrong]
- Current justification: [What is in place now]
- Recommendations: [What should be verified]

## Numerical Issues

**[Slow or unstable computation]:**

- Problem: [What is slow or numerically unstable]
- Measurement: [Actual numbers: e.g., "convergence requires N > 10^6 samples", "3 hours per parameter point"]
- Cause: [Why it is slow or unstable - e.g., "sign problem", "stiff ODE"]
- Improvement path: [How to speed it up or stabilize it]

**[Slow or unstable computation]:**

- Problem: [What is slow or unstable]
- Measurement: [Actual numbers]
- Cause: [Root cause]
- Improvement path: [Approach to fix]

## Fragile Derivations

**[Derivation/Calculation]:**

- Why fragile: [What makes it easy to get wrong - e.g., "many cancellations between large terms"]
- Common errors: [What typically goes wrong]
- Safe modification: [How to change it without introducing errors]
- Verification status: [Has it been independently checked? Against what?]

**[Derivation/Calculation]:**

- Why fragile: [What makes it delicate]
- Common errors: [What goes wrong]
- Safe modification: [How to change safely]
- Verification status: [Cross-checks performed?]

## Regime Limitations

**[Regime/Parameter range]:**

- Current capability: [What parameter range is covered]
- Limit: [Where the approach breaks down]
- Symptoms at limit: [What happens - e.g., "series diverges", "unphysical negative cross section"]
- Extension path: [How to extend the valid range]

## Missing Physics

**[Physical effect not included]:**

- What is missing: [Specific physical effect]
- Expected magnitude: [How large the correction could be]
- When it matters: [Parameter regime where it becomes important]
- Implementation complexity: [Rough effort to include it]

## Literature Discrepancies

**[Discrepancy with published result]:**

- Our result: [What we find]
- Published result: [What the literature says, with reference]
- Magnitude of discrepancy: [How large]
- Possible explanations: [Convention difference? Error? Different approximation?]
- Resolution status: [Resolved / Under investigation / Unresolved]

## Validation Gaps

**[Untested regime or prediction]:**

- What is not validated: [Specific result or parameter range]
- Risk: [What could be wrong unnoticed]
- Priority: [High/Medium/Low]
- Difficulty to validate: [Why it has not been checked yet]

---

_Open questions audit: [date]_
_Update as issues are resolved or new ones discovered_
```

<good_examples>

```markdown
# Open Questions

**Analysis Date:** 2025-06-15

## Theoretical Gaps

**Spin-orbit coupling at 4PN:**

- Issue: Complete 4PN spin-orbit contribution to the energy flux is not yet available in the literature
- Why it matters: Limits waveform accuracy for spinning binary systems
- Impact: Systematic bias in spin parameter estimation for high-mass systems (M > 50 M_sun)
- Resolution approach: Either derive from first principles using ADM Hamiltonian approach, or wait for Bini-Damour completion (expected late 2025)
- Files: `derivations/spin_orbit_flux.nb` (partial result), `references/bini_damour_2024.pdf`

**Tidal deformability in the strong-field regime:**

- Issue: Linear tidal response assumed, but nonlinear tidal effects could matter near merger
- Why it matters: Affects neutron star equation of state constraints from GW observations
- Impact: Systematic error in tidal deformability extraction of order ~5-15%
- Resolution approach: Include dynamical tides via effective action approach (Steinhoff et al.)

## Known Inconsistencies

**Gauge-dependent binding energy at 4PN:**

- Symptoms: ADM and harmonic gauge results differ by a rational number at 4PN
- Where it appears: Comparison in `checks/gauge_comparison.py`, specifically the 4PN non-logarithmic coefficient
- Workaround: Use only harmonic gauge results consistently
- Root cause: Likely an error in the ADM-to-harmonic gauge transformation at this order
- Blocked by: Requires independent recalculation of the ADM 4PN Hamiltonian

**Energy balance vs. direct integration:**

- Symptoms: Orbital phase accumulated differs by ~0.1 radians over 1000 cycles between methods
- Where it appears: `tests/phase_comparison.py` output at v/c = 0.3
- Workaround: Use energy balance method (better convergence properties)
- Root cause: Truncation of tail-of-tail terms in direct integration method

## Approximation Concerns

**Adiabatic approximation near ISCO:**

- Risk: Radiation reaction timescale approaches orbital timescale for v/c > 0.35
- Current justification: Comparison with numerical relativity shows < 1 radian phase error up to v/c = 0.4 for equal mass
- Recommendations: Add non-adiabatic corrections via osculating orbits; benchmark against NR for mass ratios q < 3

**Point-particle limit for neutron stars:**

- Risk: Finite-size effects (tidal, spin-induced quadrupole) neglected in current implementation
- Current justification: Tidal corrections are formally 5PN and small for BH-NS systems with q > 5
- Recommendations: Include leading tidal correction (k_2 Love number) in `src/waveform/tidal.py`; validate against LIGO/Virgo tidal measurements

## Numerical Issues

**PN flux series convergence:**

- Problem: Alternating-sign series for energy flux shows poor convergence beyond 3PN
- File: `src/flux/pn_flux.py`, function `compute_flux_pn()`
- Measurement: Partial sums oscillate with amplitude > 10% at v/c = 0.3
- Cause: Large PN coefficients due to pi^2 terms from tail integrals
- Improvement path: Apply Pade resummation or factored resummation (Damour, Iyer, Nagar method); prototype in `notebooks/resummation_study.ipynb`

**Adaptive ODE integration stiffness:**

- Problem: Orbital evolution becomes stiff near plunge, requiring dt < 10^-6 M
- File: `src/dynamics/orbital_evolution.py`
- Measurement: Wall time increases 100x in last 50 cycles vs. first 1000 cycles
- Cause: Radiation reaction diverges as v -> c
- Improvement path: Switch to implicit integrator (BDF) near ISCO; implement in `src/dynamics/stiff_integrator.py`

## Fragile Derivations

**Hereditary tail contributions:**

- File: `derivations/tail_integrals.nb`
- Why fragile: Involves regularization of divergent integrals with multiple scales; requires careful treatment of IR and UV divergences that must cancel
- Common errors: Sign errors in Hadamard partie finie terms; incorrect matching of near-zone and far-zone expansions
- Safe modification: Always verify Hadamard coefficients against Blanchet & Damour (1992); check that all poles cancel before taking limits
- Verification status: Checked against published results at 3PN; 4PN terms independently verified by two group members

## Regime Limitations

**Post-Newtonian expansion validity:**

- Current capability: Reliable up to v/c ~ 0.35 (frequency ~200 Hz for 30 M_sun total mass)
- Limit: Formally divergent as v/c -> 1; practically unreliable for v/c > 0.4
- Symptoms at limit: Unphysical oscillations in phase; flux can become negative
- Extension path: EOB resummation maps PN results to a strong-field effective description; implement in `src/waveform/eob.py`

## Missing Physics

**Gravitational wave memory effect:**

- What is missing: Nonlinear (Christodoulou) memory contribution to waveform
- Expected magnitude: ~10% of peak strain, but at very low frequency (below LIGO band for stellar mass)
- When it matters: Relevant for LISA sources and pulsar timing arrays
- Implementation complexity: Medium (requires time integration of energy flux; add to `src/waveform/memory.py`)

**Eccentricity:**

- What is missing: All current calculations assume quasi-circular orbits
- Expected magnitude: Residual eccentricity e ~ 0.01-0.1 for dynamically formed binaries
- When it matters: Globular cluster binaries, hierarchical triples
- Implementation complexity: High (requires reformulation of PN equations in terms of quasi-Keplerian parametrization)

## Validation Gaps

**Intermediate mass ratio regime (q = 10-100):**

- What is not validated: PN waveforms for mass ratios between comparable mass (NR-calibrated) and extreme mass ratio (self-force)
- Risk: Both PN and NR have largest errors here; no reliable benchmark exists
- Priority: High (relevant for LIGO O4 sources)
- Difficulty to validate: NR simulations at q > 20 are extremely expensive; self-force results at finite mass ratio are only now becoming available

---

_Open questions audit: 2025-06-15_
_Update as issues are resolved or new ones discovered_
```

</good_examples>

<guidelines>
**What belongs in OPEN_QUESTIONS.md:**
- Theoretical gaps with clear impact and resolution approach
- Known inconsistencies with reproduction details
- Approximation concerns and justifications
- Numerical issues with measurements
- Fragile derivations that break easily
- Regime limitations with quantitative boundaries
- Missing physics that could matter
- Literature discrepancies with references
- Validation gaps

**What does NOT belong here:**

- Opinions without evidence ("this derivation looks wrong")
- Complaints without solutions ("the numerics are bad")
- Future research directions that are not problems (that is for research planning)
- Normal TODOs (those live in code comments or research notes)
- Well-understood limitations that are working as designed
- Minor notation inconsistencies

**When filling this template:**

- **Always include file paths or references** - Questions without locations are not actionable. Use backticks: `derivations/file.nb`
- Be specific with measurements ("convergence at N=10^6" not "slow convergence")
- Include comparison details for discrepancies
- Suggest resolution approaches, not just problems
- Focus on actionable items
- Prioritize by impact on final results
- Update as issues get resolved
- Add new questions as discovered

**Tone guidelines:**

- Professional, not emotional ("series shows poor convergence" not "terrible series")
- Solution-oriented ("Apply Pade resummation" not "needs fixing")
- Risk-focused ("Could introduce 5% systematic bias" not "results are unreliable")
- Quantitative ("0.1 radian phase difference" not "noticeable disagreement")

**Useful for research planning when:**

- Deciding what to work on next
- Estimating risk of extending calculations
- Understanding where to be careful
- Prioritizing improvements
- Onboarding new collaborators or GPD contexts
- Planning systematic error budgets

**How this gets populated:**
GPD agents detect these during analysis mapping. Manual additions welcome for researcher-discovered issues. This is living documentation, not a complaint list.
</guidelines>
