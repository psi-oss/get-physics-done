# LLM Physics Error Catalog

Language models make characteristic physics errors that differ from human errors. Human physicists make sign errors and algebraic mistakes; LLMs confuse conventions between sources, hallucinate identities, and get combinatorial factors wrong in systematic ways. This catalog documents the most common LLM physics error classes with detection strategies.

Consult this catalog before trusting any LLM-generated physics calculation. Every error class below has been observed in production.

## Error Class Index

The full catalog is split across 4 files for efficient context loading:

| File | Error Classes | Domain |
|---|---|---|
| [references/verification/errors/llm-errors-core.md](references/verification/errors/llm-errors-core.md) | #1-25 | Core error classes: CG coefficients, Green's functions, group theory, asymptotics, delta functions, phase conventions, thermodynamics, field theory basics, variational bounds, partition functions |
| [references/verification/errors/llm-errors-field-theory.md](references/verification/errors/llm-errors-field-theory.md) | #26-51 | Field theory & advanced: coherent states, second quantization, angular momentum coupling, Boltzmann factors, path ordering, ensembles, numerical methods, regularization, Fierz identities, effective potentials, metric signatures, topological terms |
| [references/verification/errors/llm-errors-extended.md](references/verification/errors/llm-errors-extended.md) | #52-81, #102-104 | Extended & deep domain: numerical relativity, stellar structure, quantum chemistry, plasma physics, fluid dynamics, quantum computing, biophysics, turbulence, finite-size effects. New: catastrophic cancellation, functional Jacobians, IR safety |
| [references/verification/errors/llm-errors-deep.md](references/verification/errors/llm-errors-deep.md) | #82-101 | Cross-domain: nuclear shell model, astrophysics, AMO physics, superconductivity, magnetic reconnection, decoherence, constraints, critical phenomena, conformal mappings, Brillouin zones, Penrose diagrams, entanglement |

## Error Class to Verification Check Traceability

This table maps each error class to the verification checks (from `../core/verification-core.md` and the domain-specific verification files) most likely to catch it. Use this to select targeted verification strategies.

| Error Class | Dimensional Analysis | Limiting Cases | Symmetry | Conservation | Sum Rules / Ward | Numerical Convergence | Cross-Check Literature | Positivity / Unitarity |
|---|---|---|---|---|---|---|---|---|
| 1. Wrong CG coefficients | | | ✓ (angular momentum algebra) | | | | ✓ (tabulated values) | |
| 2. N-particle symmetrization | | ✓ (N=1 limit) | ✓ (exchange symmetry) | | | | | ✓ (normalization) |
| 3. Green's function confusion | | ✓ (T→0, ω→0) | | | ✓ (KMS relation) | | ✓ (known propagators) | ✓ (spectral positivity, causality) |
| 4. Wrong group theory | | ✓ (Abelian limit) | ✓ (dimension counting) | | | | ✓ (Casimir tables) | |
| 5. Wrong asymptotics | ✓ | ✓ (large/small argument) | | | | ✓ (numerical evaluation) | ✓ (DLMF tables) | |
| 6. Delta function mishandling | ✓ | | | | ✓ (test function integration) | ✓ (numerical integration) | | |
| 7. Wrong phase conventions | | | ✓ (consistency check) | | | | ✓ (standard tables) | |
| 8. Intensive/extensive confusion | ✓ | ✓ (N→1, thermodynamic limit) | | | | | ✓ (known thermodynamics) | |
| 9. Thermal field theory errors | | ✓ (T→0 limit) | | | ✓ (KMS, sum rules) | | ✓ (known results) | ✓ (spectral positivity) |
| 10. Wrong tensor decompositions | ✓ (trace structure) | ✓ (flat space limit) | ✓ (Bianchi identities) | ✓ (contracted Bianchi) | | | ✓ (Schwarzschild test) | |
| 11. Hallucinated identities | | ✓ (special values) | | | | ✓ (numerical test at 3-5 points) | ✓ (multiple sources) | |
| 12. Grassmann sign errors | | ✓ (2×2 case) | ✓ (anticommutation) | | | ✓ (small system check) | | ✓ (det vs Pf relation) |
| 13. BC hallucination | | ✓ (known solutions) | ✓ (boundary symmetry) | | | ✓ (substitution check) | ✓ (textbook solutions) | |
| 14. Operator ordering | | ✓ (commutative limit) | | | ✓ (Ward identities) | ✓ (small system) | ✓ (known VEVs) | |
| 15. Dimensional failures | ✓ (primary detection) | | | | | | | |
| 16. Series truncation | | ✓ (known orders) | | | ✓ (Ward at each order) | ✓ (compare N and N+1) | ✓ (known coefficients) | |
| 17. Correlation/response confusion | | ✓ (T→0 agreement) | | | ✓ (KMS relation) | | ✓ (Kubo formula) | ✓ (spectral positivity, causality) |
| 18. Integration constant omission | | ✓ (verify all BCs) | | | | ✓ (substitution) | ✓ (known solutions) | |
| 19. Wrong DOF counting | | ✓ (known limits) | ✓ (gauge counting) | | | | ✓ (known DOF) | ✓ (partition function) |
| 20. Classical/quantum conflation | | ✓ (hbar→0, T→∞) | | | ✓ (equipartition check) | | ✓ (known quantum results) | |
| 21. Branch cut errors | | ✓ (known asymptotics) | ✓ (crossing symmetry) | | ✓ (dispersion relations) | ✓ (numerical continuation) | | ✓ (spectral positivity) |
| 22. HS sign errors | | ✓ (mean-field limit) | | | | ✓ (convergence of integral) | ✓ (known saddle points) | ✓ (convergent Gaussian) |
| 23. Diagram miscounting | | | ✓ (gauge invariance) | | ✓ (Ward identity fails) | | ✓ (automated tools) | ✓ (unitarity cuts) |
| 24. Variational bound violations | | | | | | ✓ (compare with exact) | ✓ (known ground states) | ✓ (E_trial ≥ E_exact) |
| 25. Partition fn vs generating fn | ✓ (Z dimensionless vs functional) | ✓ (free field limit) | | | | | ✓ (textbook definitions) | |
| 26. Coherent state normalization | | ✓ (alpha→0 limit) | | | ✓ (completeness relation) | ✓ (numerical overlap check) | ✓ (known coherent state formulas) | ✓ (normalization <α\|α>=1) |
| 27. First/second quantization | ✓ (operator dimensions) | ✓ (N=1 limit) | ✓ (particle statistics) | ✓ (particle number) | ✓ (commutation relations) | | ✓ (known matrix elements) | |
| 28. Angular momentum j>1 | | ✓ (j=1/2 limit) | ✓ (dimension counting) | ✓ (total J conservation) | | ✓ (numerical CG check) | ✓ (tabulated CG, 6j) | |
| 29. Wrong Boltzmann factor / partition fn normalization | ✓ (exponent must be dimensionless) | ✓ (classical limit, ideal gas) | | | ✓ (Gibbs paradox test) | ✓ (numerical comparison) | ✓ (textbook partition functions) | ✓ (Z > 0) |
| 30. Incorrect path ordering (non-Abelian) | | ✓ (Abelian limit) | ✓ (gauge covariance) | | ✓ (Wilson loop identities) | | ✓ (lattice gauge theory) | |
| 31. Wrong statistical mechanics ensemble | | ✓ (thermodynamic limit equivalence) | | ✓ (fixed vs fluctuating quantities) | ✓ (ensemble equivalence check) | ✓ (finite-size comparison) | ✓ (textbook ensembles) | |
| 32. Numerical linear algebra errors | ✓ (matrix dimensions) | ✓ (identity matrix limit) | ✓ (unitarity of exp(iH)) | | | ✓ (condition number, eigenvalue check) | ✓ (known spectra) | ✓ (unitarity, positive-definiteness) |
| 33. Natural unit restoration errors | ✓ (primary detection) | ✓ (known SI values) | | | | ✓ (numerical comparison) | ✓ (textbook conversions) | |
| 34. Regularization scheme mixing | | ✓ (scheme-independent observables) | ✓ (gauge invariance) | | ✓ (Ward identities, RG consistency) | | ✓ (known beta functions) | |
| 35. Incorrect Fierz identity | | ✓ (2×2 case) | ✓ (completeness relation) | | ✓ (Fierz coefficient sum rules) | ✓ (numerical spinor contraction) | ✓ (tabulated Fierz coefficients) | |
| 36. Effective potential sign errors | | ✓ (free field limit) | | | ✓ (boson/fermion sign rule) | ✓ (numerical second derivative) | ✓ (Coleman-Weinberg original paper) | ✓ (V''(φ_min) > 0 for stability) |
| 37. Metric signature inconsistency | ✓ (p² sign check) | ✓ (flat space limit) | ✓ (Lorentz invariance) | | | ✓ (p² = ±m² numerical check) | ✓ (convention tables) | ✓ (positive energy) |
| 38. Covariant vs partial derivative | ✓ (covariant divergence) | ✓ (flat space limit: Γ→0) | ✓ (general covariance) | ✓ (∇_μ T^μν = 0) | | ✓ (Schwarzschild geodesics) | ✓ (Christoffel tables) | |
| 39. Wick contraction miscounting | | ✓ (free field limit) | ✓ (crossing symmetry) | | ✓ ((2n-1)!! counting rule) | ✓ (numerical Wick evaluation) | ✓ (known n-point functions) | |
| 40. Scaling dimension errors | ✓ (engineering dimension) | ✓ (free field limit: γ→0) | ✓ (conformal algebra) | | ✓ (unitarity bounds) | | ✓ (known anomalous dimensions) | ✓ (unitarity bounds Δ ≥ (d-2)/2) |
| 41. Index (anti)symmetrization factors | | ✓ (2-index case) | ✓ (symmetry property check) | | ✓ (Bianchi identities) | ✓ (explicit component check) | ✓ (convention tables) | |
| 42. Noether current / anomaly errors | ✓ (current dimensions) | ✓ (free field limit) | ✓ (gauge covariance) | ✓ (∂_μ j^μ = anomaly) | ✓ (Ward identities, ABJ anomaly) | ✓ (triangle diagram coefficient) | ✓ (Adler-Bardeen, π⁰→γγ rate) | |
| 43. Legendre transform errors | ✓ (H dimensions = energy) | ✓ (free particle H=p²/2m) | | ✓ (Hamilton's equations ↔ EL) | | ✓ (numerical trajectory comparison) | ✓ (textbook Hamiltonians) | |
| 44. Spin-statistics violations | | ✓ (single constituent) | ✓ (exchange symmetry) | | | | ✓ (known composite particles) | ✓ (spin-statistics theorem) |
| 45. Topological term mishandling | | ✓ (Abelian limit) | ✓ (P, CP properties) | | ✓ (instanton number integrality) | ✓ (BPST instanton S=8π²/g²) | ✓ (neutron EDM bound) | |
| 46. Adiabatic vs sudden confusion | ✓ (timescale comparison) | ✓ (slow/fast limits) | | ✓ (energy conservation check) | | ✓ (transition probability calculation) | ✓ (known transition rates) | ✓ (probability ≤ 1, sum = 1) |
| 47. Incorrect complex conjugation | | ✓ (T→0, single-state limit) | ✓ (Hermiticity of ρ) | ✓ (probability conservation) | | ✓ (eigenvalues of ρ in [0,1]) | ✓ (known transition rates) | ✓ (ρ† = ρ, Tr(ρ) = 1, P ≥ 0) |
| 48. Hellmann-Feynman misapplication | ✓ (force dimensions) | ✓ (free particle limit) | | ✓ (force = -dE/dR consistency) | | ✓ (compare numerical gradient) | ✓ (known equilibrium geometries) | |
| 49. Incorrect replica trick | | ✓ (T→∞: paramagnetic) | ✓ (replica permutation symmetry) | | | ✓ (entropy ≥ 0 check) | ✓ (Parisi solution, SK model) | ✓ (non-negative entropy) |
| 50. Wrong zero mode treatment | | ✓ (dilute gas limit) | ✓ (broken symmetry counting) | | ✓ (zero mode norm = √S₀) | ✓ (compare with exact tunneling) | ✓ (known instanton prefactors) | |
| 51. Wrong HS channel selection | | ✓ (weak coupling: RPA) | ✓ (order parameter symmetry) | | ✓ (susceptibility divergence) | ✓ (compare saddle point with known order) | ✓ (known phase diagrams) | ✓ (free energy is real, bounded below) |
| 82. Wrong nuclear shell magic numbers | | ✓ (known magic nuclei) | ✓ (shell closure signatures) | | | ✓ (E(2+) and B(E2) values) | ✓ (NUBASE/AME tables) | |
| 83. Eddington luminosity errors | ✓ (L_Edd dimensions) | ✓ (solar mass benchmark) | | ✓ (radiation pressure balance) | | ✓ (L_Edd = 1.26e38 M/M_sun erg/s) | ✓ (known accretion rates) | |
| 84. Wrong Friedmann equation usage | ✓ (H² dimensions) | ✓ (matter-only, radiation-only limits) | | ✓ (energy conservation: rho ~ a^{-3(1+w)}) | | ✓ (age of universe = 13.8 Gyr) | ✓ (Planck cosmological parameters) | |
| 85. Wrong multiphoton selection rules | | ✓ (single-photon limit) | ✓ (parity: (-1)^n rule) | | ✓ (sum rules for transition rates) | | ✓ (known two-photon cross sections) | |
| 86. BCS gap equation errors | ✓ (gap has energy dimensions) | ✓ (weak-coupling: 2Δ/k_BT_c = 3.53) | ✓ (s-wave vs d-wave symmetry) | | ✓ (BCS ratio as consistency check) | ✓ (compare with experiment) | ✓ (known T_c values) | |
| 87. Wrong reconnection topology | ✓ (reconnection rate dimensions) | ✓ (large-S limit) | ✓ (magnetic topology) | ✓ (energy conservation) | | ✓ (reconnection rate vs observations) | ✓ (PIC simulation benchmarks) | |
| 88. Wrong decoherence channel | | ✓ (noiseless limit: identity channel) | ✓ (CPTP conditions) | ✓ (trace preservation) | ✓ (T2 ≤ 2T1 constraint) | ✓ (gate fidelity comparison) | ✓ (experimental T1, T2 values) | ✓ (complete positivity) |
| 89. Holonomic vs non-holonomic | | ✓ (unconstrained limit) | ✓ (integrability condition) | ✓ (DOF counting) | | ✓ (trajectory comparison) | ✓ (textbook examples: rolling sphere) | |
| 90. Hyperscaling and critical exponents | | ✓ (mean-field limit d > d_uc) | ✓ (scaling relations: Rushbrooke, Widom, Fisher) | | ✓ (hyperscaling d*nu = 2-alpha) | ✓ (known exponents: 3D Ising) | ✓ (Monte Carlo and conformal bootstrap) | |
| 91. Wrong conformal mapping | | ✓ (identity map limit) | ✓ (analyticity: Cauchy-Riemann) | ✓ (boundary point mapping) | | ✓ (numerical verification) | ✓ (known Schwarz-Christoffel transforms) | |
| 92. Wrong Lyapunov exponent | | ✓ (integrable limit: all λ = 0) | ✓ (Hamiltonian: sum = 0) | ✓ (phase space volume: Liouville) | | ✓ (convergence with trajectory length) | ✓ (known Lorenz exponents) | |
| 93. Fresnel vs Fraunhofer confusion | ✓ (Fresnel number dimensionless) | ✓ (far-field and near-field limits) | | ✓ (energy conservation: Parseval) | | ✓ (numerical diffraction pattern) | ✓ (known slit patterns) | |
| 94. Wrong Maxwell construction | ✓ (pressure dimensions) | ✓ (T → T_c: single-phase limit) | ✓ (equal-area rule) | ✓ (Gibbs free energy equal in both phases) | ✓ (Clausius-Clapeyron consistency) | ✓ (numerical integration check) | ✓ (known van der Waals coexistence) | |
| 95. Wrong Brillouin zone | ✓ (reciprocal lattice dimensions) | ✓ (cubic lattice: known BZ) | ✓ (space group symmetry) | | | ✓ (BZ volume = (2π)³/V_cell) | ✓ (Bilbao Server, Bradley-Cracknell) | |
| 96. Nuclear binding energy errors | ✓ (B has energy dimensions) | ✓ (known B/A for He-4, Fe-56, U-238) | | ✓ (B/A at iron peak) | ✓ (Bethe-Weizsacker coefficients) | ✓ (compare with AME mass table) | ✓ (experimental binding energies) | |
| 97. Wrong Penrose diagram | | ✓ (flat space: Minkowski diamond) | ✓ (causal structure: null at 45°) | | | | ✓ (known Schwarzschild, Kerr diagrams) | |
| 98. Wrong entanglement measure | | ✓ (separable state: all measures = 0) | ✓ (entanglement monotone conditions) | | ✓ (CKW monogamy inequality) | ✓ (Bell state: known values) | ✓ (known GHZ, W state entanglement) | ✓ (non-negativity, ≤ log(d)) |
| 99. Wrong magnetic mirror ratio | ✓ (loss cone angle dimensionless) | ✓ (R=1: no confinement) | | ✓ (adiabatic invariant mu = const) | | ✓ (numerical orbit tracing) | ✓ (Earth magnetosphere values) | |
| 100. Jeans instability errors | ✓ (lambda_J has length dimensions) | ✓ (known molecular cloud M_J ~ 5 M_sun) | | ✓ (mass conservation) | | ✓ (numerical N-body comparison) | ✓ (observed cloud masses) | |
| 101. Kramers degeneracy misapplication | | ✓ (single electron: 2-fold) | ✓ (time-reversal check) | | | | ✓ (known ferromagnet band structures) | |

## Usage Guidelines

1. **Proactive checking.** When an LLM generates a physics calculation, scan for ALL error classes, not just the ones that seem relevant. Errors from class 11 (hallucinated identities), class 15 (dimensional failures), class 33 (natural unit restoration), and class 37 (metric signature inconsistency) can appear in any context.
2. **Priority ordering.** The most dangerous errors are those that produce plausible-looking results: classes 3, 5, 9, 11, 17, 21, 42 (missing anomalies), 84 (Friedmann equation), 90 (critical exponents). Sign errors (classes 7, 12, 22, 36, 37) are usually caught by consistency checks. Factor errors (classes 2, 6, 8, 19, 41, 83, 96) are caught by dimensional analysis and limiting cases. Structural errors (classes 13, 14, 16, 18, 43, 46, 89, 97) are caught by substitution checks. Convention errors (classes 34, 37, 38, 45) require tracking conventions from the start. Domain-specific errors (classes 82-101) are particularly insidious because they require specialized knowledge to detect — the cross-domain classes cover nuclear, astrophysical, AMO, condensed matter, plasma, and mathematical physics pitfalls.
3. **Compound errors.** LLMs can make multiple errors from different classes in a single calculation. A wrong CG coefficient (class 1) combined with a wrong phase convention (class 7) can accidentally cancel, producing a "correct" result for the wrong reason. Similarly, a metric signature error (class 37) combined with a covariant derivative error (class 38) can produce a doubly-wrong result that passes superficial checks. Always verify intermediate steps, not just the final answer.
4. **Confidence calibration.** LLMs present all results with equal confidence. A standard textbook identity and a hallucinated generalization are stated with the same certainty. The absence of hedging language does NOT indicate correctness.
5. **Cross-referencing.** For any non-trivial identity or coefficient: verify against at least two independent sources (textbooks, published tables, numerical computation). LLMs can reproduce errors from a single training source.
6. **Use the traceability matrix.** When a specific error class is suspected, consult the traceability table above to identify which verification checks are most effective for detection. A lightweight version is available in `references/verification/errors/llm-errors-traceability.md` for context-efficient loading.
