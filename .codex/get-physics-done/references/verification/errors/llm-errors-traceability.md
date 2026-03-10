---
load_when:
  - "error traceability"
  - "which check catches which error"
  - "verification strategy"
  - "LLM error detection"
tier: 2
context_cost: medium
---

# LLM Error Traceability Matrix

Extracted from `references/verification/errors/llm-physics-errors.md` for lightweight loading. Maps each error class to the verification checks most likely to catch it.

**Full catalog:** See `references/verification/errors/llm-physics-errors.md` (index) for detailed descriptions, detection strategies, and examples of all 104 error classes across 4 part files.

## Traceability Matrix

| Error Class | Dimensional Analysis | Limiting Cases | Symmetry | Conservation | Sum Rules / Ward | Numerical Convergence | Cross-Check Literature | Positivity / Unitarity |
|---|---|---|---|---|---|---|---|---|
| 1. Wrong CG coefficients | | | angular momentum algebra | | | | tabulated values | |
| 2. N-particle symmetrization | | N=1 limit | exchange symmetry | | | | | normalization |
| 3. Green's function confusion | | T->0, omega->0 | | | KMS relation | | known propagators | spectral positivity, causality |
| 4. Wrong group theory | | Abelian limit | dimension counting | | | | Casimir tables | |
| 5. Wrong asymptotics | yes | large/small argument | | | | numerical evaluation | DLMF tables | |
| 6. Delta function mishandling | yes | | | | test function integration | numerical integration | | |
| 7. Wrong phase conventions | | | consistency check | | | | standard tables | |
| 8. Intensive/extensive confusion | yes | N->1, thermo limit | | | | | known thermodynamics | |
| 9. Thermal field theory errors | | T->0 limit | | | KMS, sum rules | | known results | spectral positivity |
| 10. Wrong tensor decompositions | trace structure | flat space limit | Bianchi identities | contracted Bianchi | | | Schwarzschild test | |
| 11. Hallucinated identities | | special values | | | | numerical test at 3-5 points | multiple sources | |
| 12. Grassmann sign errors | | 2x2 case | anticommutation | | | small system check | | det vs Pf relation |
| 13. BC hallucination | | known solutions | boundary symmetry | | | substitution check | textbook solutions | |
| 14. Operator ordering | | commutative limit | | | Ward identities | small system | known VEVs | |
| 15. Dimensional failures | **primary detection** | | | | | | | |
| 16. Series truncation | | known orders | | | Ward at each order | compare N and N+1 | known coefficients | |
| 17. Correlation/response confusion | | T->0 agreement | | | KMS relation | | Kubo formula | spectral positivity, causality |
| 18. Integration constant omission | | verify all BCs | | | | substitution | known solutions | |
| 19. Wrong DOF counting | | known limits | gauge counting | | | | known DOF | partition function |
| 20. Classical/quantum conflation | | hbar->0, T->inf | | | equipartition check | | known quantum results | |
| 21. Branch cut errors | | known asymptotics | crossing symmetry | | dispersion relations | numerical continuation | | spectral positivity |
| 22. HS sign errors | | mean-field limit | | | | convergence of integral | known saddle points | convergent Gaussian |
| 23. Diagram miscounting | | | gauge invariance | | Ward identity fails | | automated tools | unitarity cuts |
| 24. Variational bound violations | | | | | | compare with exact | known ground states | E_trial >= E_exact |
| 25. Partition fn vs generating fn | Z dimensionless vs functional | free field limit | | | | | textbook definitions | |
| 26. Coherent state normalization | | alpha->0 limit | | | completeness relation | numerical overlap check | known coherent state formulas | normalization <a|a>=1 |
| 27. First/second quantization | operator dimensions | N=1 limit | particle statistics | particle number | commutation relations | | known matrix elements | |
| 28. Angular momentum j>1 | | j=1/2 limit | dimension counting | total J conservation | | numerical CG check | tabulated CG, 6j | |
| 29. Wrong Boltzmann factor | exponent must be dimensionless | classical limit, ideal gas | | | Gibbs paradox test | numerical comparison | textbook partition functions | Z > 0 |
| 30. Incorrect path ordering | | Abelian limit | gauge covariance | | Wilson loop identities | | lattice gauge theory | |
| 31. Wrong ensemble | | thermo limit equivalence | | fixed vs fluctuating quantities | ensemble equivalence check | finite-size comparison | textbook ensembles | |
| 32. Numerical linear algebra | matrix dimensions | identity matrix limit | unitarity of exp(iH) | | | condition number, eigenvalue check | known spectra | unitarity, positive-definiteness |
| 33. Natural unit restoration | **primary detection** | known SI values | | | | numerical comparison | textbook conversions | |
| 34. Regularization scheme mixing | | scheme-independent observables | gauge invariance | | Ward identities, RG consistency | | known beta functions | |
| 35. Incorrect Fierz identity | | 2x2 case | completeness relation | | Fierz coefficient sum rules | numerical spinor contraction | tabulated Fierz coefficients | |
| 36. Effective potential sign errors | | free field limit | | | boson/fermion sign rule | numerical second derivative | Coleman-Weinberg paper | V''(phi_min) > 0 |
| 37. Metric signature inconsistency | p^2 sign check | flat space limit | Lorentz invariance | | | p^2 = +/-m^2 numerical check | convention tables | positive energy |
| 38. Covariant vs partial derivative | covariant divergence | flat space limit: Gamma->0 | general covariance | nabla_mu T^munu = 0 | | Schwarzschild geodesics | Christoffel tables | |
| 39. Wick contraction miscounting | | free field limit | crossing symmetry | | (2n-1)!! counting rule | numerical Wick evaluation | known n-point functions | |
| 40. Scaling dimension errors | engineering dimension | free field limit: gamma->0 | conformal algebra | | unitarity bounds | | known anomalous dimensions | unitarity bounds Delta >= (d-2)/2 |
| 41. Index (anti)symmetrization | | 2-index case | symmetry property check | | Bianchi identities | explicit component check | convention tables | |
| 42. Noether current / anomaly | current dimensions | free field limit | gauge covariance | div j = anomaly | Ward identities, ABJ anomaly | triangle diagram coefficient | Adler-Bardeen, pi0->gamma-gamma rate | |
| 43. Legendre transform errors | H dimensions = energy | free particle H=p^2/2m | | Hamilton's eqs <-> EL | | numerical trajectory comparison | textbook Hamiltonians | |
| 44. Spin-statistics violations | | single constituent | exchange symmetry | | | | known composite particles | spin-statistics theorem |
| 45. Topological term mishandling | | Abelian limit | P, CP properties | | instanton number integrality | BPST instanton S=8pi^2/g^2 | neutron EDM bound | |
| 46. Adiabatic vs sudden confusion | timescale comparison | slow/fast limits | | energy conservation check | | transition probability calculation | known transition rates | probability <= 1, sum = 1 |
| 47. Incorrect complex conjugation | | T->0, single-state limit | Hermiticity of rho | probability conservation | | eigenvalues of rho in [0,1] | known transition rates | rho^dag = rho, Tr(rho) = 1, P >= 0 |
| 48. Hellmann-Feynman misapplication | force dimensions | free particle limit | | force = -dE/dR consistency | | compare numerical gradient | known equilibrium geometries | |
| 49. Incorrect replica trick | | T->inf: paramagnetic | replica permutation symmetry | | | entropy >= 0 check | Parisi solution, SK model | non-negative entropy |
| 50. Wrong zero mode treatment | | dilute gas limit | broken symmetry counting | | zero mode norm = sqrt(S_0) | compare with exact tunneling | known instanton prefactors | |
| 51. Wrong HS channel selection | | weak coupling: RPA | order parameter symmetry | | susceptibility divergence | compare saddle point with known order | known phase diagrams | free energy real, bounded below |

### Extended Error Classes (#52-81)

| Error Class | Dimensional Analysis | Limiting Cases | Symmetry | Conservation | Sum Rules / Ward | Numerical Convergence | Cross-Check Literature | Positivity / Unitarity |
|---|---|---|---|---|---|---|---|---|
| 52. NR constraint violation | | flat space limit | diffeomorphism | constraint propagation | | constraint monitor | known initial data | constraint energy non-negative |
| 53. Wrong stellar structure eqn | dp/dr dimensions | Newtonian limit | | hydrostatic equilibrium | | M_max convergence | TOV vs Lane-Emden | mass > 0, pressure > 0 |
| 54. Basis set superposition | | complete basis limit | | | | basis set extrapolation | benchmark databases | binding energy sign |
| 55. Wrong XC functional | | known gap values | | | | convergence vs U | experimental gaps | gap > 0 for known insulators |
| 56. Plasma instability criteria | growth rate [1/time] | equal density limit | | | | growth rate vs wavenumber | textbook criteria | growth rate real for instability |
| 57. Reynolds number regime | | Re -> 0 Stokes | | | | grid convergence | experimental drag data | drag > 0 |
| 58. Entanglement vs thermo entropy | | T=0: S_thermo = 0 | | | | area law check | known CFT results | S >= 0 |
| 59. Wrong quantum gate count | | single qubit limit | | | | circuit simulation | known gate counts | depth >= 0 |
| 60. Coarse-graining artifacts | | all-atom limit | | | | resolution convergence | multi-scale comparison | free energy consistency |
| 61. Gauge-fixing artifacts | | gauge-invariant obs | gauge independence | | | compare 2 gauges | known gauge-invariant results | |
| 62. Missing finite-size effects | | L -> infinity | | | | finite-size scaling | known exponents | |
| 63. GW template mismatch | | known binary limits | | energy/momentum balance | | convergence vs resolution | NR catalogs | match filtered SNR |
| 64. Optical depth confusion | tau dimensionless | optically thin limit | | | | numerical integration | known optical depths | tau >= 0 |
| 65. Wrong dispersion relation | omega dimensions | long wavelength limit | | | | numerical dispersion | textbook relations | omega real for stable modes |
| 66. Semiclassical beyond validity | | hbar -> 0 consistency | | | | compare with exact | quantum corrections known | |
| 67. Adiabatic elimination | | slow/fast timescale ratio | | | | compare full vs reduced | known reduced models | |
| 68. Wrong Kramers-Kronig | | static limit | causality | | KK consistency | numerical KK check | known response functions | Im chi >= 0 |
| 69. Molecular symmetry misID | | known point groups | representation dimension | | character table | vibrational mode count | spectroscopic databases | |
| 70. Wrong Landau levels | energy dimensions | B -> 0 free particle | cyclotron symmetry | | degeneracy counting | numerical eigenvalues | known LL spectrum | E_n >= 0 |
| 71. Missing Berry phase | | Abelian limit | gauge structure | | Chern number integrality | numerical Berry curvature | known topological indices | |
| 72. NR gauge mode leakage | | Minkowski gauge | diffeomorphism | constraint growth | | constraint convergence | known gauge conditions | constraint norm |
| 73. CFL violation | Courant number dimensionless | | | | | stability test | | |
| 74. DFT+U double counting | | U=0 reduces to DFT | | | | magnetic moments vs expt | known Hubbard corrections | total energy physical |
| 75. Broken spin symmetry | | <S^2> = S(S+1) | spin rotation | | | compare with CASSCF | known singlet-triplet gaps | |
| 76. Debye length resolution | | analytic Debye screening | | | | resolution convergence | known plasma parameters | temperature physical |
| 77. Kinetic vs fluid mismatch | | collisional limit | | | | compare kinetic vs fluid | known reconnection rates | |
| 78. Numerical diffusion | Peclet number dimensionless | | | | | resolution convergence | analytical solutions | |
| 79. Turbulence model extrapolation | | known benchmark flows | | | | compare multiple models | DNS/experimental data | |
| 80. Implicit solvent artifacts | | explicit solvent comparison | | | | ΔG_solv comparison | experimental solvation | |
| 81. Force field transferability | | known structures | | | | structural parameters | QM reference data | |

### Cross-Domain & Deep Domain Error Classes (#82-104)

| Error Class | Dimensional Analysis | Limiting Cases | Symmetry | Conservation | Sum Rules / Ward | Numerical Convergence | Cross-Check Literature | Positivity / Unitarity |
|---|---|---|---|---|---|---|---|---|
| 82. Wrong nuclear magic numbers | | known shell closures | | | | shell model | experimental magic numbers | binding energy > 0 |
| 83. Eddington luminosity errors | luminosity dimensions | known stellar limits | | energy conservation | | compare with observations | known luminosities | L > 0 |
| 84. Wrong Friedmann equation | | flat space, Λ=0 | isotropy/homogeneity | energy-momentum | Friedmann consistency | | Planck parameters | H^2 >= 0 |
| 85. Wrong multiphoton selection rules | | single-photon limit | parity, angular momentum | | | selection rule check | spectroscopic data | |
| 86. BCS gap equation errors | gap has energy dim | T -> 0, T -> T_c | particle-hole | | gap equation self-consistency | T_c convergence | known superconductors | Δ >= 0 |
| 87. Wrong reconnection topology | rate dimensions | large S limit | | magnetic flux conservation | | scaling vs S | known reconnection rates | |
| 88. Wrong decoherence channel | | unitary limit | CPTP | trace preservation | | Lindblad vs exact | known T1, T2 | eigenvalues >= 0 |
| 89. Holonomic vs non-holonomic | | unconstrained limit | DOF counting | constraint preservation | | Dirac bracket check | known constrained systems | |
| 90. Hyperscaling / critical exponents | | mean-field limit | universality class | scaling relations | hyperscaling relations | finite-size scaling | known exponents | |
| 91. Wrong conformal mapping | | known domain limits | analyticity | | | boundary check | known mappings | |
| 92. Wrong Lyapunov exponent | [1/time] | integrable limit | symplectic structure | | | convergence vs trajectory length | known chaotic systems | sum of exponents = 0 (Hamiltonian) |
| 93. Fresnel vs Fraunhofer | | far-field limit | | | | compare exact vs approx | known diffraction patterns | intensity >= 0 |
| 94. Wrong Maxwell construction | | single-phase limit | | | | free energy convexity | known coexistence curves | pressure >= 0 |
| 95. Wrong Brillouin zone | | reciprocal lattice check | space group | | | k-point convergence | known band structures | |
| 96. Wrong nuclear binding energy | energy per nucleon | known nuclei | isospin | | Weiszacker formula check | | NNDC database | B/A > 0 |
| 97. Wrong Penrose diagram | | known spacetime limits | | causal structure | | null geodesic check | known Penrose diagrams | |
| 98. Wrong entanglement measure | | pure state limit | LOCC monotonicity | | | numerical LOCC check | known entanglement values | E >= 0 |
| 99. Wrong magnetic mirror ratio | | uniform B limit | adiabatic invariant | magnetic moment | | particle tracing | known mirror ratios | |
| 100. Jeans instability | Jeans length dimensions | homogeneous limit | | | | dispersion relation | known Jeans mass | M_J > 0 |
| 101. Kramers degeneracy | | spin-1/2 limit | time-reversal | | | degeneracy count | known spectra | |
| 102. Catastrophic cancellation | | known difference values | | | | high-precision comparison | analytical reformulation | |
| 103. Functional Jacobian | | linear field redef: J=1 | gauge covariance | anomaly matching | ABJ anomaly | | Fujikawa derivation | |
| 104. IR-unsafe observable | | IR-safe observable comparison | | | | add soft parton test | IRC-safe definitions | cross section >= 0 |

## How to Use This Matrix

1. **When a specific error class is suspected:** Read across the row to find which verification checks detect it
2. **When planning verification:** Read down each column to see which error classes a given check catches
3. **Most broadly effective checks:** Limiting cases and cross-check literature catch the most error classes
4. **Primary detectors:** Dimensional analysis is the PRIMARY detector for classes 15 and 33
5. **Compound errors:** Multiple errors can cancel superficially; verify intermediate steps, not just final answers

## Priority Error Classes

The most dangerous errors produce plausible-looking results:

- **CRITICAL (0-1 layers):** 11 (hallucinated identities), 13 (BC hallucination)
- **HIGH danger (plausible wrong results, core):** 3, 5, 9, 17, 21, 42
- **HIGH danger (extended/deep):** 52 (NR constraints), 63 (GW templates), 71 (Berry phase), 72 (gauge leakage), 76 (Debye resolution), 77 (kinetic/fluid mismatch), 87 (reconnection topology)
- **HIGH danger (uncataloged):** 102 (catastrophic cancellation), 103 (functional Jacobian), 104 (IR safety)
- **Caught by consistency (sign/factor errors):** 7, 12, 22, 36, 37
- **Caught by dimensional analysis:** 2, 6, 8, 15, 19, 33, 41, 64
- **Caught by substitution:** 13, 14, 16, 18, 43, 46
- **Convention tracking required:** 34, 37, 38, 45

For a compact summary of HIGH-risk classes, see `../audits/verification-gap-summary.md`.
