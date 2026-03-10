# Subfield-Specific Execution Guidance

When executing tasks in a specific subfield, apply these additional protocols. This is not exhaustive --- for detailed subfield references, consult `references/physics-subfields.md`.

## Subfield Reference Index

For deep domain guidance, load the appropriate subfield and verification files:

| Domain | Subfield Guide | Verification Domain |
|--------|---------------|-------------------|
| QFT | `subfields/qft.md` | `verification-domain-qft.md` |
| Condensed Matter | `subfields/condensed-matter.md` | `verification-domain-condmat.md` |
| Statistical Mechanics | `subfields/stat-mech.md` | `verification-domain-statmech.md` |
| General Relativity & Cosmology | `subfields/gr-cosmology.md` | `verification-domain-gr-cosmology.md` |
| AMO | `subfields/amo.md` | `verification-domain-amo.md` |
| Nuclear & Particle Physics | `subfields/nuclear-particle.md` | `verification-domain-nuclear-particle.md` |
| Astrophysics | `subfields/astrophysics.md` | `verification-domain-astrophysics.md` |
| Mathematical Physics | `subfields/mathematical-physics.md` | `verification-domain-mathematical-physics.md` |
| Quantum Information | `subfields/quantum-info.md` | `verification-domain-quantum-info.md` |
| Fluid Dynamics & Plasma | `subfields/fluid-plasma.md` | `verification-domain-fluid-plasma.md` |
| Soft Matter & Biophysics | `subfields/soft-matter-biophysics.md` | `verification-domain-soft-matter.md` |
| Classical Mechanics | `subfields/classical-mechanics.md` | `verification-core.md` |

**Loading rule:** When the executor identifies the project's primary subfield, `@`-include the corresponding subfield guide and verification domain file. For cross-domain projects, load both relevant subfield files.

## Quantum Field Theory

- **Renormalization:** Always state the scheme (MS-bar, on-shell, momentum subtraction). Track the renormalization scale mu through every expression. Verify beta functions and anomalous dimensions at each computed order.
- **Feynman rules:** Derive from the Lagrangian, do not transcribe from memory. Verify against a textbook (Peskin & Schroeder, Weinberg, Schwartz) for standard theories. For non-standard theories: derive and verify by checking Ward identities.
- **Regularization:** Default to dimensional regularization for gauge theories. If using cutoff: document which symmetries are broken and how counterterms restore them.
- **Infrared structure:** For massless theories, IR divergences cancel between virtual and real corrections (KLN theorem). Verify this cancellation explicitly. Do not claim "IR safe" without checking.

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

## General Relativity

- **Coordinate vs. gauge artifacts:** Before claiming a physical result, verify it is coordinate-independent. Curvature scalars (R, R\_{mu nu} R^{mu nu}, Kretschner) are invariant. Christoffel symbols are not.
- **ADM vs. covariant formulation:** ADM (3+1 decomposition) gives lapse, shift, 3-metric. Covariant gives 4-metric. Results must agree. When comparing: verify the gauge/slicing condition.
- **Energy conditions:** State which energy conditions matter is assumed to satisfy (weak, strong, dominant, null). The dominant energy condition (T^{mu nu} u_mu is causal) is physical; the strong energy condition (violated by cosmological constant) is mathematical.
- **Singularity analysis:** Distinguish coordinate singularities (removable by coordinate change, like r=2M in Schwarzschild with bad coordinates) from physical singularities (curvature invariants diverge). Always compute curvature invariants.
- **de Sitter and cosmological horizons:** Distinguish global, planar, and static-patch observables. Verify `L = H^{-1}`, `T_dS = H/(2*pi)`, and `S_GH = A_H/(4G_N)`. For inflationary observables, use in-in/gauge-invariant data rather than flat-space S-matrix language.

## AMO (Atomic, Molecular, Optical)

- **Rotating wave approximation (RWA):** Valid only near resonance (detuning << frequency). State the detuning explicitly and verify |Delta/omega| << 1. Beyond RWA: use Floquet theory or numerical integration.
- **Selection rules:** Electric dipole transitions: Delta L = +/- 1, Delta M = 0, +/- 1, parity change. Verify every claimed transition satisfies the selection rules for the relevant multipole.
- **Dipole approximation:** Valid when the wavelength >> atomic size (lambda >> a_0). For X-rays or inner-shell transitions: may need multipole expansion.
- **Light-atom interaction gauges:** Length gauge (E.r) vs velocity gauge (A.p). Physical results (transition rates, cross sections) must be gauge-independent. Intermediate quantities (matrix elements) are gauge-dependent.

## Path Integrals

<!-- Load path-integrals.md protocol dynamically per protocol_loading section. -->

## Effective Field Theory

<!-- Load effective-field-theory.md, analytic-continuation.md, order-of-limits.md
     protocols dynamically per protocol_loading section. -->
