# Subfield-Specific Execution Guidance

Protocol bundles are an additive routing layer for specialized files. Use this guide only as a fallback index or a manual cross-check when bundle metadata is absent, incomplete, or clearly mismatched to the work.

This guide is not a default route, an exhaustive ontology, or permission to force every task into a named physics bucket. When the work is cross-domain, unusually scoped, or still method-uncertain, keep the generic execution flow and load only the minimum extra files justified by the plan contract and current task.

When executing tasks in a specific subfield, apply these additional protocols only when the current work actually makes that subfield clear. This is not exhaustive --- for detailed subfield references, consult `references/physics-subfields.md`.

## Subfield Reference Index

For deep domain guidance, load the minimum subfield and verification files that the current task actually needs:

| Domain | Subfield Guide | Verification Domain |
|--------|---------------|-------------------|
| QFT | `references/subfields/qft.md` | `references/verification/domains/verification-domain-qft.md` |
| Quantum Gravity | `references/subfields/quantum-gravity.md` | `references/verification/domains/verification-domain-gr-cosmology.md` + `references/verification/domains/verification-domain-qft.md` |
| String Theory | `references/subfields/string-theory.md` | `references/verification/domains/verification-domain-qft.md` + `references/verification/domains/verification-domain-mathematical-physics.md` + `references/verification/domains/verification-domain-gr-cosmology.md` |
| Condensed Matter | `references/subfields/condensed-matter.md` | `references/verification/domains/verification-domain-condmat.md` |
| Statistical Mechanics | `references/subfields/stat-mech.md` | `references/verification/domains/verification-domain-statmech.md` |
| General Relativity & Cosmology | `references/subfields/gr-cosmology.md` | `references/verification/domains/verification-domain-gr-cosmology.md` |
| AMO | `references/subfields/amo.md` | `references/verification/domains/verification-domain-amo.md` |
| Nuclear & Particle Physics | `references/subfields/nuclear-particle.md` | `references/verification/domains/verification-domain-nuclear-particle.md` |
| Astrophysics | `references/subfields/astrophysics.md` | `references/verification/domains/verification-domain-astrophysics.md` |
| Mathematical Physics | `references/subfields/mathematical-physics.md` | `references/verification/domains/verification-domain-mathematical-physics.md` |
| Algebraic QFT | `references/subfields/algebraic-qft.md` | `references/verification/domains/verification-domain-algebraic-qft.md` |
| String Field Theory | `references/subfields/string-field-theory.md` | `references/verification/domains/verification-domain-string-field-theory.md` |
| Quantum Information | `references/subfields/quantum-info.md` | `references/verification/domains/verification-domain-quantum-info.md` |
| Fluid Dynamics & Plasma | `references/subfields/fluid-plasma.md` | `references/verification/domains/verification-domain-fluid-plasma.md` |
| Soft Matter & Biophysics | `references/subfields/soft-matter-biophysics.md` | `references/verification/domains/verification-domain-soft-matter.md` |
| Classical Mechanics | `references/subfields/classical-mechanics.md` | `references/verification/core/verification-core.md` |

**Loading rule:** Use this table only after the current plan, observable, or method family makes a subfield genuinely clear. For cross-domain projects, load only the relevant slices. If no row cleanly fits, stay with generic execution guidance plus core verification expectations instead of guessing.

## Quantum Field Theory

- **Renormalization:** Always state the scheme (MS-bar, on-shell, momentum subtraction). Track the renormalization scale mu through every expression. Verify beta functions and anomalous dimensions at each computed order.
- **Feynman rules:** Derive from the Lagrangian, do not transcribe from memory. Verify against a textbook (Peskin & Schroeder, Weinberg, Schwartz) for standard theories. For non-standard theories: derive and verify by checking Ward identities.
- **Regularization:** Default to dimensional regularization for gauge theories. If using cutoff: document which symmetries are broken and how counterterms restore them.
- **Infrared structure:** For massless theories, IR divergences cancel between virtual and real corrections (KLN theorem). Verify this cancellation explicitly. Do not claim "IR safe" without checking.
- **CFT and fixed points:** If the task is about operator dimensions, OPE coefficients, RG fixed points, AdS boundary data, or crossing constraints, load `references/protocols/conformal-bootstrap.md`. State whether the work is numerical bootstrap, analytic bootstrap, or a comparison against bootstrap data, and write the operator sector being constrained before computing anything.
- **Supersymmetry and protected sectors:** Distinguish rigid SUSY from supergravity, state the preserved supercharge or BPS condition, and identify whether the result is a component computation, an index, or a localization calculation. Do not treat protected observables as generic ones.
- **Asymptotic symmetries and soft limits:** For massless gauge bosons or gravitons, state the null-infinity boundary conditions and whether a soft theorem is being used as a Ward identity of a large gauge/BMS charge. Do not quote the infrared triangle heuristically without matching the charge, flux, and observable conventions.
- **Generalized symmetries:** Identify the charged extended operators, the degree of the background field, and whether dynamical matter screens the operator. Do not claim center symmetry, higher-group structure, or non-invertible defects without writing the corresponding defect action or fusion data explicitly.

## Quantum Gravity

- **Regime declaration:** State whether the task is semiclassical gravity, holography, black-hole-information bookkeeping, asymptotic safety/FRG, or a canonical/discrete approach. Do not mix their observables or approximation schemes by slogan.
- **Semiclassical control:** Verify the curvature and backreaction regime explicitly before trusting Hawking, horizon, or QFT-in-curved-spacetime reasoning. A low-curvature background plus a renormalized stress tensor is a prerequisite, not an afterthought.
- **Generalized entropy and islands:** For Page-curve or entropy claims, state the radiation subsystem, the candidate quantum extremal surfaces, and the competing saddles. No "information recovery" claim is complete without this saddle comparison.
- **Boundary conditions matter:** AdS, flat, and de Sitter asymptotics use different observables and different dictionaries. Load `references/protocols/holography-ads-cft.md`, `references/protocols/asymptotic-symmetries.md`, or `references/protocols/de-sitter-space.md` explicitly rather than importing one regime's logic into another.
- **UV-completion claims:** In asymptotic-safety or discrete/canonical work, demand approach-specific control: truncation/regulator stability for FRG, or a clean continuum/semi-classical observable for discrete/canonical constructions such as CDT or causal-set calculations.

## String Theory

- **Framework declaration:** State whether the task is perturbative worldsheet string theory, D-brane/duality physics, compactification/moduli stabilization, or swampland reasoning. Do not flatten them into generic "stringy effects."
- **Worldsheet consistency first:** For perturbative spectra or amplitudes, verify central-charge balance, BRST/GSO conditions, level matching, and modular invariance before interpreting spacetime states or couplings.
- **Expansion bookkeeping:** Keep `alpha'` and `g_s` separate. Higher-derivative corrections, string loops, and non-perturbative effects are different approximation layers and should never be merged into one generic uncertainty.
- **Compactification discipline:** State the internal geometry, flux/orientifold data, tadpole conditions, stabilized moduli, and the hierarchy among the low-energy scale, KK scale, and string scale. A 4d EFT is not controlled until this hierarchy is explicit.
- **Conjectural vs. established claims:** Swampland arguments, de Sitter constructions, and phenomenological statements must be labeled by their status: theorem, explicit example, controlled approximation, or conjecture. Do not present active debates as settled.
- **Off-shell handoff:** If the task is genuinely off-shell string field theory, switch to the `String Field Theory` section below rather than treating it as generic string theory.

## Renormalization Group

<!-- Load renormalization-group.md protocol dynamically per protocol_loading section. -->

## Condensed Matter

- **Lattice vs. continuum:** When discretizing a continuum theory, verify: (a) no fermion doubling (use Wilson, staggered, or domain-wall fermions), (b) correct continuum limit (a -> 0 extrapolation), (c) lattice symmetries preserve the essential physics.
- **Mean-field theory:** Always estimate fluctuation corrections. Mean field is exact in d -> infinity but can be qualitatively wrong in low dimensions (d <= 2 for continuous symmetries, by Mermin-Wagner). State the dimension and symmetry.
- **Phase transitions:** Near critical points, verify scaling relations (alpha + 2*beta + gamma = 2, d*nu = 2 - alpha). Check universality class. For first-order transitions: verify the latent heat and coexistence curve.
- **Many-body perturbation theory:** Self-consistent approaches (GW, DMFT, etc.) require iteration to convergence. Track the self-consistency loop and verify convergence of the self-energy, not just the total energy.

## Statistical Mechanics

- **Ensemble choice:** Canonical (fixed N, T), grand canonical (fixed mu, T), microcanonical (fixed E, N). State the ensemble and verify thermodynamic identities within it. Near phase transitions, ensemble choice matters.
- **Thermodynamic limit:** Results must be taken in the N -> infinity, V -> infinity limit with N/V = constant. Verify finite-size corrections scale as expected (1/N, 1/L^d, etc.).
- **Detailed balance:** For Monte Carlo, verify that the update algorithm satisfies detailed balance with respect to the target distribution. Common error: incorrect acceptance ratio.
- **Autocorrelation:** Naive error bars from correlated samples underestimate the true error by a factor of sqrt(2\*tau_int), where tau_int is the integrated autocorrelation time. Measure tau_int and correct.
- **Critical phenomena and universality:** If the calculation targets the critical point itself rather than off-critical thermodynamics, compare extracted exponents or scaling dimensions against RG or conformal-bootstrap benchmarks where available. Load `references/protocols/conformal-bootstrap.md` for Ising, O(N), or mixed-correlator critical-point questions.

## Mathematical Physics

- **Structural claims first:** State the symmetry algebra, operator content, and representation labels before using any exact or numerical method. In CFT work, make explicit whether the symmetry is global conformal, Virasoro, superconformal, or includes a global internal symmetry.
- **Conformal bootstrap routing:** For crossing equations, OPE truncations, semidefinite programming, extremal functionals, or rigorous CFT bounds, load `references/protocols/conformal-bootstrap.md` immediately. Do not treat bootstrap work as generic QFT numerics.
- **Sector bookkeeping:** In mixed-correlator or global-symmetry bootstrap problems, write the representation content of each OPE channel before interpreting a bound. Misplacing the stress tensor, conserved current, or singlet/traceless sectors invalidates the result.
- **Numerical rigor:** Record derivative order `Lambda`, spin truncation, block normalization, and solver precision. A claimed island, kink, or bound is not usable until stability under these controls is checked.

## Algebraic Quantum Field Theory

- **Net first:** State the spacetime, region class, and whether the object is a Haag-Kastler C*-net, a von Neumann net in a chosen representation, or a locally covariant functor before using AQFT vocabulary.
- **Representation discipline:** Any modular, superselection, or type-classification claim must name the state and GNS representation. Do not move between vacuum, thermal, and charged sectors implicitly.
- **Modular caution:** Tomita-Takesaki data are not automatically physical time evolution. If modular flow is identified with boosts, KMS time, or geometric motion, state the theorem and hypotheses explicitly.
- **Factor-type rigor:** Do not call an algebra type `III` because "continuum QFT is infinitely entangled." Check factor status, trace properties, and the relevant modular-spectrum or literature theorem instead.

## String Field Theory

- **Formulation first:** State open vs closed, bosonic vs super, small vs large Hilbert space, and whether the action is cubic, WZW-like, `A_infinity`, `L_infinity`, or 1PI before manipulating any field.
- **Quantum-number bookkeeping:** Ghost number, picture number, BPZ parity, and BRST charge assignments are structural data, not comments. Write them out for every field and gauge parameter.
- **Gauge and truncation discipline:** Do not read physical meaning off a low-level or single-gauge solution. Track Siegel/Schnabl/other gauge assumptions and rerun key observables at multiple truncation levels.
- **Gauge-invariant observables:** For solutions claimed to represent tachyon vacua, marginal deformations, or shifted backgrounds, verify vacuum energy, Ellwood invariants, boundary-state data, or amplitude matching rather than only inspecting the gauge-fixed string field.

## General Relativity

- **Coordinate vs. gauge artifacts:** Before claiming a physical result, verify it is coordinate-independent. Curvature scalars (R, R\_{mu nu} R^{mu nu}, Kretschmann scalar) are invariant. Christoffel symbols are not.
- **ADM vs. covariant formulation:** ADM (3+1 decomposition) gives lapse, shift, 3-metric. Covariant gives 4-metric. Results must agree. When comparing: verify the gauge/slicing condition.
- **Energy conditions:** State which energy conditions matter is assumed to satisfy (weak, strong, dominant, null). The dominant energy condition (T^{mu nu} u_mu is causal) is physical; the strong energy condition (violated by cosmological constant) is mathematical.
- **Singularity analysis:** Distinguish coordinate singularities (removable by coordinate change, like r=2M in Schwarzschild with bad coordinates) from physical singularities (curvature invariants diverge). Always compute curvature invariants.
- **de Sitter and cosmological horizons:** Distinguish global, planar, and static-patch observables. Verify `L = H^{-1}`, `T_dS = H/(2*pi)`, and `S_GH = A_H/(4G_N)`. For inflationary observables, use in-in/gauge-invariant data rather than flat-space S-matrix language.
- **Bondi frame and memory:** Near null infinity, define Bondi shear/news explicitly and fix the BMS frame before comparing waveforms, memory observables, or asymptotic charges across calculations.

## AMO (Atomic, Molecular, Optical)

- **Rotating wave approximation (RWA):** Valid only near resonance (detuning << frequency). State the detuning explicitly and verify |Delta/omega| << 1. Beyond RWA: use Floquet theory or numerical integration.
- **Selection rules:** Electric dipole transitions: Delta L = +/- 1, Delta M = 0, +/- 1, parity change. Verify every claimed transition satisfies the selection rules for the relevant multipole.
- **Dipole approximation:** Valid when the wavelength >> atomic size (lambda >> a_0). For X-rays or inner-shell transitions: may need multipole expansion.
- **Light-atom interaction gauges:** Length gauge (E.r) vs velocity gauge (A.p). Physical results (transition rates, cross sections) must be gauge-independent. Intermediate quantities (matrix elements) are gauge-dependent.

## Nuclear & Particle Physics

- **Observable definition:** Distinguish inclusive, fiducial, unfolded, detector-level, and particle-level observables before comparing with theory. Do not compare a parton-level prediction directly to a detector-level measurement.
- **Likelihoods and covariance:** Use the published covariance matrix or public likelihood when available. Correlated experimental systematics, PDF errors, and theory nuisances should not be added in quadrature as if independent.
- **Phenomenology pipeline:** State the full chain: matching/running -> hard process -> shower/hadronization -> detector/reconstruction -> statistical inference. For flavor observables, replace the shower/detector stages with hadronic matrix elements and experimental likelihoods, but keep the same bookkeeping discipline.
- **EFT validity:** In SMEFT or WET fits, state the operator basis, matching scale, RG running, truncation order, and the kinematic regime used to justify the EFT. Do not interpret events with `E ~ Lambda` as controlled EFT constraints without explicit discussion.
- **Recasting and reinterpretation:** Validate any recast against published benchmark cutflows, efficiencies, or SM yields before claiming limits. If a public likelihood or `pyhf` model exists, prefer it over ad hoc `chi^2` approximations.

## Path Integrals

<!-- Load path-integrals.md protocol dynamically per protocol_loading section. -->

## Effective Field Theory

<!-- Load effective-field-theory.md, analytic-continuation.md, order-of-limits.md
     protocols dynamically per protocol_loading section. -->
