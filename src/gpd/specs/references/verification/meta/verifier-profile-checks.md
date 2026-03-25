# Verifier Profile-Specific Checks

Subfield-specific verification checklists for the GPD verifier agent. Load ONLY the checklist(s) matching the phase's physics domain.

**For every checklist item: perform the CHECK, do not search_files for the CONCEPT.**
Profiles may change breadth, but they still run every contract-aware check required by the plan.

---

## Domain Loading Map

| Phase Domain | Load Checklist(s) |
|---|---|
| QFT, gauge theory, scattering | QFT Checklist |
| Condensed matter, many-body, materials | Condensed Matter / Many-Body Checklist |
| General relativity, cosmology, black holes | GR / Cosmology Checklist |
| Quantum gravity, semiclassical gravity, holography | GR / Cosmology Checklist + QFT Checklist |
| String theory, worldsheet CFT, compactification, D-branes | QFT Checklist + Mathematical Physics Checklist (+ GR / Cosmology Checklist when spacetime gravity is dynamical) |
| String field theory, tachyon condensation, off-shell string amplitudes | String Field Theory Checklist + QFT Checklist + Mathematical Physics Checklist (+ GR / Cosmology Checklist when spacetime gravity is dynamical) |
| Quantum mechanics, atomic physics, AMO | QM / Atomic Physics Checklist |
| Statistical mechanics, thermodynamics, phase transitions | Statistical Mechanics / Thermodynamics Checklist |
| Nuclear physics, particle physics, collider | Nuclear / Particle Physics Checklist |
| Astrophysics, stellar physics, accretion, gravitational waves | Astrophysics Checklist |
| Fluid dynamics, MHD, turbulence, plasma | Fluid Dynamics / Plasma Physics Checklist |
| Rigorous proofs, topology, representation theory, integrability | Mathematical Physics Checklist |
| Quantum computing, entanglement, error correction | Quantum Information Checklist |
| Polymers, membranes, active matter, biophysics | Soft Matter / Biophysics Checklist |
| Cross-disciplinary (e.g., AdS/CFT, topological matter) | Load checklists for BOTH relevant domains |

**Skip all other checklists.** Do NOT mechanically apply all 6 checklists to every phase — this wastes context and produces irrelevant checks. If a checklist is not loaded, report those subfield checks as `N/A (domain not applicable)` in the consistency summary.

---

## Quantum Field Theory Checklist

```
[] Gauge invariance
  - COMPUTE: Evaluate physical observable with two different gauge parameter values; verify they agree
  - COMPUTE: Substitute test momenta into Ward-Takahashi identity q_mu Gamma^mu = S^{-1}(p+q) - S^{-1}(p); verify both sides match
  - If gauge-fixing used: evaluate result at xi=0, xi=1; verify physical quantities unchanged

[] Renormalization
  - COMPUTE: Count powers of momentum in loop integrals to verify superficial degree of divergence
  - COMPUTE: Check that counterterms have the same operator structure as the Lagrangian
  - COMPUTE: Verify one-loop beta-function coefficient against known result for the theory
  - COMPUTE: Take mu d/dmu of physical quantity; verify it vanishes

[] Unitarity and optical theorem
  - COMPUTE: Evaluate Im[f(0)] and k*sigma_tot/(4*pi) independently; verify they agree
  - COMPUTE: Check |a_l| <= 1/2 for each partial wave at each energy
  - COMPUTE: Apply cutting rules to specific diagram; compare with imaginary part

[] Crossing symmetry
  - COMPUTE: Evaluate amplitude at test (s,t,u) values; verify crossing relation holds
  - COMPUTE: Verify s + t + u = sum of squared masses

[] CPT invariance
  - COMPUTE: Verify particle and antiparticle masses agree in the result
  - No approximation should violate CPT in a local QFT

[] Lorentz covariance
  - COMPUTE: Verify cross-section depends only on Mandelstam variables (not on frame-dependent quantities)
  - COMPUTE: Apply a boost to test case; verify result transforms correctly

[] Decoupling
  - COMPUTE: Take heavy particle mass M -> infinity; verify it decouples from low-energy result

[] Anomalies
  - COMPUTE: Evaluate triangle diagram coefficient for specific fermion content
  - COMPUTE: Verify anomaly cancellation: sum of charges cubed = 0 for gauge anomaly-free theory
  - COMPUTE: Check axial anomaly coefficient against (e^2/16pi^2) * F * F-tilde
```

---

## Condensed Matter / Many-Body Checklist

```
[] Luttinger theorem
  - COMPUTE: Evaluate Fermi surface volume from computed Green's function; compare with electron density

[] Sum rules
  - COMPUTE: Numerically integrate spectral function; verify integral = 1
  - COMPUTE: Evaluate f-sum rule: integrate omega * Im[epsilon(omega)]
  - COMPUTE: Check first few moment sum rules of spectral function

[] Kramers-Kronig consistency
  - COMPUTE: Numerically perform KK transform of Im[chi]; compare with Re[chi] from artifact

[] Mermin-Wagner theorem
  - CHECK: If ordered phase found in d<=2 at T>0, verify it's discrete symmetry (not continuous)

[] Goldstone modes
  - COMPUTE: Count gapless modes in dispersion; verify equals number of broken generators

[] Conservation laws in transport
  - COMPUTE: Verify continuity equation numerically for computed current and density
  - COMPUTE: Check Onsager reciprocal relations L_ij(B) = L_ji(-B) if magnetic field present

[] Spectral properties
  - COMPUTE: Evaluate A(k,omega) at grid of points; verify non-negative everywhere
  - COMPUTE: Evaluate Im[Sigma^R(omega)]; verify <= 0 (quasiparticle decay)
  - COMPUTE: Extract quasiparticle weight Z; verify 0 <= Z <= 1

[] Thermodynamic consistency
  - COMPUTE: Evaluate C_V and verify >= 0
  - COMPUTE: Evaluate compressibility and verify >= 0
  - COMPUTE: Verify Maxwell relations by numerical differentiation
  - COMPUTE: Check S -> 0 (or k_B ln g) as T -> 0
```

---

## General Relativity / Cosmology Checklist

```
[] Newtonian limit
  - COMPUTE: Take weak-field, slow-motion limit of derived metric; verify g_00 = -(1 + 2*Phi/c^2)

[] Energy conditions
  - COMPUTE: Evaluate T_mu_nu u^mu u^nu for specific stress-energy; verify sign

[] Bianchi identity / conservation
  - COMPUTE: Evaluate nabla_mu T^{mu nu} numerically; verify = 0 to machine precision

[] Asymptotic behavior
  - COMPUTE: Evaluate metric components as r -> infinity; verify approach Minkowski
  - COMPUTE: Evaluate ADM mass; verify positive

[] Singularity classification
  - COMPUTE: Evaluate Kretschmann scalar R_{mu nu rho sigma} R^{mu nu rho sigma} at suspected singularity

[] Cosmological consistency
  - COMPUTE: Verify both Friedmann equations are simultaneously satisfied with given matter content
  - COMPUTE: Evaluate H(z) from derived expression; compare with standard LCDM
```

---

## Quantum Mechanics / Atomic Physics Checklist

```
[] Hermiticity and unitarity
  - COMPUTE: Construct H matrix for test case; verify H = H^dagger element by element
  - COMPUTE: Evolve test state; verify norm is preserved to machine precision

[] Variational principle
  - COMPUTE: Evaluate <psi_trial|H|psi_trial>; verify >= exact E_0 if known

[] Selection rules
  - COMPUTE: Evaluate matrix element <f|d|i> for forbidden transition; verify = 0
  - COMPUTE: Check Thomas-Reiche-Kuhn sum rule: sum of oscillator strengths = Z

[] Symmetry degeneracies
  - COMPUTE: Count eigenvalue degeneracies; verify match 2L+1 or expected group theory prediction

[] Uncertainty relations
  - COMPUTE: Evaluate Delta_x * Delta_p for computed state; verify >= hbar/2
```

---

## Statistical Mechanics / Thermodynamics Checklist

```
[] Partition function properties
  - COMPUTE: Evaluate Z at several temperatures; verify Z > 0 always
  - COMPUTE: Evaluate Z(T -> infinity); verify approaches total number of states
  - COMPUTE: Check extensivity: ln(Z) scales linearly with N

[] Thermodynamic identities
  - COMPUTE: Derive S = -dF/dT numerically; cross-check with S = -<dH/dT>
  - COMPUTE: Verify C_V = (<E^2> - <E>^2) / (k_B T^2) against direct computation

[] Phase transition checks
  - COMPUTE: Extract critical exponents; verify alpha + 2*beta + gamma = 2
  - COMPUTE: Verify hyperscaling d*nu = 2 - alpha

[] Exactly solvable benchmarks
  - COMPUTE: For 2D Ising, verify T_c = 2J/[k_B * ln(1+sqrt(2))]
  - COMPUTE: For ideal gas, verify PV = NkT at computed data points

[] Fluctuation-dissipation
  - COMPUTE: Evaluate both fluctuation and response; verify FDT relation holds
```

---

## Nuclear / Particle Physics Checklist

```
[] Cross section constraints
  - COMPUTE: Verify sigma >= 0 at all computed energies
  - COMPUTE: Check optical theorem at each energy point
  - COMPUTE: Verify partial wave unitarity: sigma_l <= 4*pi*(2l+1)/k^2

[] Decay properties
  - COMPUTE: Sum branching ratios; verify = 1
  - COMPUTE: Verify Gamma >= 0 for all decay channels

[] Quantum number conservation
  - COMPUTE: Verify charge, baryon number, lepton number balance in each process

[] PDG comparison
  - COMPUTE: Compare computed masses, lifetimes with PDG values; report relative errors
```

---

## Astrophysics Checklist

```
[] Virial theorem / energy balance
  - COMPUTE: Evaluate 2K + U for self-gravitating system; verify equals 0 (equilibrium) or check sign (collapsing/expanding)
  - COMPUTE: For accretion: verify luminosity L <= L_Eddington = 4*pi*G*M*m_p*c/sigma_T

[] Hydrostatic equilibrium
  - COMPUTE: Verify dP/dr = -G*M(r)*rho(r)/r^2 is satisfied at multiple radial points
  - COMPUTE: For neutron stars: verify TOV equation is satisfied (not just Newtonian hydrostatic)

[] Equation of state consistency
  - COMPUTE: Verify P(rho) is monotonically increasing (thermodynamic stability)
  - COMPUTE: Verify sound speed c_s^2 = dP/drho < c^2 (causality bound)
  - COMPUTE: For degenerate matter: verify non-relativistic/relativistic Fermi pressure limits

[] Nuclear reaction rates
  - COMPUTE: Verify Gamow peak energy E_0 = (b*k_B*T/2)^{2/3} for thermonuclear reactions
  - COMPUTE: Compare reaction rates with JINA REACLIB or NACRE databases

[] Gravitational wave consistency
  - COMPUTE: Verify quadrupole formula P_GW = -(32/5)*G/c^5 * <I_ij^{(3)} I^{ij(3)}> gives correct sign (energy loss)
  - COMPUTE: For circular binary: verify chirp mass M_c = (m1*m2)^{3/5}/(m1+m2)^{1/5} matches waveform
  - COMPUTE: Verify h_+ and h_x polarizations satisfy transverse-traceless gauge

[] Radiative transfer
  - COMPUTE: Verify optical depth integral tau = integral kappa*rho ds gives consistent opacity
  - COMPUTE: In optically thick limit: verify diffusion approximation F = -c/(3*kappa*rho) * grad(aT^4)

[] Cosmological distance measures
  - COMPUTE: Verify d_L = (1+z)*d_M (luminosity distance) and d_A = d_M/(1+z) (angular diameter distance)
  - COMPUTE: At z << 1: verify Hubble law d_L ~ c*z/H_0

[] Mass-radius relations
  - COMPUTE: For white dwarfs: verify Chandrasekhar limit M_Ch ~ 1.44 M_sun
  - COMPUTE: For neutron stars: verify M_max depends on EOS (typically 2.0-2.5 M_sun)

[] Scaling relations
  - COMPUTE: For main sequence: verify L ~ M^3.5 to M^4 (mass-luminosity relation)
  - COMPUTE: For galaxy clusters: verify M-T relation M ~ T^{3/2} (self-similar scaling)

[] Numerical convergence for N-body / hydro
  - COMPUTE: Verify energy conservation drift < tolerance over simulation time
  - COMPUTE: Run at 2+ resolutions; verify converged quantities (density profile, mass function)
```

---

## Fluid Dynamics / Plasma Physics Checklist

```
[] Reynolds number scaling
  - COMPUTE: Verify drag/friction coefficients follow known Re-dependent scaling laws
  - COMPUTE: For pipe flow: verify f = 64/Re (laminar) or Colebrook equation (turbulent)

[] CFL condition
  - COMPUTE: Verify Courant number C = (u + c_s)*dt/dx <= C_max for the numerical scheme used
  - COMPUTE: For MHD: include Alfven speed v_A = B/sqrt(mu_0*rho) in CFL constraint

[] Conservation laws in simulations
  - COMPUTE: Monitor total mass, momentum, energy vs time; verify drift < tolerance
  - COMPUTE: For ideal MHD: also verify magnetic helicity and cross-helicity conservation

[] Divergence-free magnetic field
  - COMPUTE: Evaluate div(B) at grid points; verify = 0 to machine precision
  - CHECK: If div(B) != 0: identify whether constrained transport or divergence cleaning is used

[] Energy spectrum / Kolmogorov scaling
  - COMPUTE: For turbulent flows: verify E(k) ~ k^{-5/3} in inertial range
  - COMPUTE: Verify dissipation rate epsilon = nu*<|grad u|^2> matches energy injection rate
  - COMPUTE: Verify Kolmogorov scale eta = (nu^3/epsilon)^{1/4} is resolved by grid

[] MHD stability
  - COMPUTE: For tokamak equilibria: verify Grad-Shafranov equation is satisfied
  - COMPUTE: Check Suydam criterion (local stability) and Kruskal-Shafranov limit (kink stability)

[] Plasma kinetics
  - COMPUTE: For PIC simulations: verify charge neutrality sum_s n_s*q_s = 0 globally
  - COMPUTE: Verify Debye length lambda_D = sqrt(epsilon_0*k_B*T/(n*e^2)) is resolved by grid

[] Boundary condition consistency
  - CHECK: Verify inflow/outflow conditions don't produce spurious reflections
  - COMPUTE: For periodic BCs: verify Fourier spectrum shows no artificial periodicity artifacts

[] Dimensionless number verification
  - COMPUTE: Verify Re, Ma, Pr, Ra are consistent with stated physical parameters
  - COMPUTE: For MHD: verify magnetic Reynolds number Rm = U*L/eta is in stated regime

[] Exact solution benchmarks
  - COMPUTE: Compare with Couette/Poiseuille/Stokes flow for viscous cases
  - COMPUTE: For MHD: compare with Alfven wave propagation test or Orszag-Tang vortex
```

---

## Mathematical Physics Checklist

```
[] Index theorem verification
  - COMPUTE: For Atiyah-Singer: count zero modes of Dirac operator; compare with topological integral
  - COMPUTE: Gauss-Bonnet: verify integral R dA = 2*pi*chi(M) where chi is Euler characteristic

[] Topological invariant quantization
  - COMPUTE: Verify Chern numbers are integers (non-integer = numerical error or band crossing)
  - COMPUTE: Verify winding numbers are integers via contour integration

[] Representation theory checks
  - COMPUTE: Dimension formula: verify dim(R) from Weyl formula matches weight diagram state count
  - COMPUTE: Tensor product: verify sum of dim(R_i) in decomposition = product of input dimensions
  - COMPUTE: Character orthogonality: sum_g chi_R(g)*chi_S(g)* = |G|*delta_RS

[] Spectral theory
  - COMPUTE: For self-adjoint operators: verify all eigenvalues are real
  - COMPUTE: Verify spectral decomposition reproduces the operator: A = sum lambda_n |n><n|
  - COMPUTE: For compact operators: verify eigenvalues accumulate only at 0

[] Lie algebra structure
  - COMPUTE: Verify Jacobi identity [A,[B,C]] + [B,[C,A]] + [C,[A,B]] = 0 for computed brackets
  - COMPUTE: Casimir eigenvalue: compute by direct matrix trace AND by eigenvalue formula; compare

[] Exact integrability
  - COMPUTE: For Lax pair: verify [L,M] = dL/dt reproduces equations of motion
  - COMPUTE: Verify conserved quantities are in involution: {I_m, I_n} = 0

[] Proof structure
  - CHECK: All hypotheses explicitly stated; boundary/edge cases verified
  - CHECK: Each step follows from previous steps and stated hypotheses (no gaps)
  - CHECK: Quantifiers correct (for-all vs there-exists)

[] Analytic structure
  - COMPUTE: Verify monodromy: going around branch point returns to correct Riemann sheet
  - COMPUTE: Residue theorem applications: verify all poles are correctly identified and enclosed

[] Differential geometry
  - COMPUTE: Verify metric is non-degenerate: det(g) != 0 at all points
  - COMPUTE: Verify connection is metric-compatible: nabla_mu g_{nu rho} = 0
  - COMPUTE: Verify Bianchi identity: nabla_{[mu} R_{nu rho]sigma tau} = 0

[] Symmetry group verification
  - COMPUTE: Verify group axioms: closure, associativity, identity, inverse
  - COMPUTE: For finite groups: verify |G| = sum dim(R_i)^2
```

---

## Quantum Information Checklist

```
[] Density matrix validity
  - COMPUTE: Verify Tr(rho) = 1, rho = rho^dagger, and all eigenvalues in [0,1]
  - COMPUTE: For pure states: verify Tr(rho^2) = 1; for mixed: Tr(rho^2) < 1

[] Quantum channel properties (CPTP)
  - COMPUTE: Verify complete positivity: Choi matrix (I tensor Phi)(|Omega><Omega|) is positive semidefinite
  - COMPUTE: Verify trace preservation: Tr(Phi(rho)) = 1 for all rho
  - COMPUTE: For Kraus representation: verify sum_k E_k^dagger E_k = I

[] Entanglement measures
  - COMPUTE: Entanglement entropy S = -Tr(rho_A ln rho_A); verify S >= 0
  - COMPUTE: For bipartite pure states: verify S(A) = S(B)
  - COMPUTE: Concurrence or negativity: verify in allowed range [0,1]

[] No-cloning / no-signaling
  - CHECK: Any apparent state copying must violate unitarity — flag as error
  - CHECK: Reduced density matrix of one subsystem must be independent of operations on the other (no-signaling)

[] Gate fidelity and error bounds
  - COMPUTE: Process fidelity F = Tr(U^dagger V) / d for d-dimensional system; verify F in [0,1]
  - COMPUTE: Diamond norm distance for channel comparison; verify triangle inequality

[] Error correction properties
  - COMPUTE: For stabilizer codes: verify S_i commute pairwise and with logical operators
  - COMPUTE: Verify code distance d by checking minimum weight of undetectable errors
  - COMPUTE: Knill-Laflamme condition: <i|E_a^dagger E_b|j> = C_ab delta_ij for correctable errors

[] Circuit complexity / depth
  - COMPUTE: Verify circuit output matches expected unitary to specified fidelity
  - COMPUTE: For variational circuits: verify gradient is non-zero (barren plateau check)

[] Measurement consistency
  - COMPUTE: Verify POVM elements sum to identity: sum_m M_m^dagger M_m = I
  - COMPUTE: Born rule: verify p(m) = Tr(M_m rho M_m^dagger) >= 0 and sum p(m) = 1

[] Entanglement witnesses
  - COMPUTE: For witness W: verify Tr(W*rho_sep) >= 0 for all separable states
  - COMPUTE: Verify Tr(W*rho_ent) < 0 for the target entangled state

[] Quantum thermodynamics
  - COMPUTE: Verify Landauer bound: erasure cost >= k_B T ln 2 per bit
  - COMPUTE: For quantum heat engines: verify efficiency <= Carnot bound
```

---

## Soft Matter / Biophysics Checklist

```
[] Polymer scaling laws
  - COMPUTE: Verify R_g ~ N^nu with correct Flory exponent (nu=3/5 good solvent, 1/2 theta, 1/3 poor)
  - COMPUTE: For polymer melts: verify Rouse/reptation scaling of viscosity eta ~ N (Rouse) or N^3.4 (entangled)

[] Membrane mechanics
  - COMPUTE: Verify Helfrich energy E = integral (kappa/2)(2H-c_0)^2 + kappa_bar*K dA gives correct bending
  - COMPUTE: For vesicles: verify area and volume constraints are satisfied

[] Self-assembly thermodynamics
  - COMPUTE: Verify critical micelle concentration follows exp(-epsilon/k_B*T) scaling
  - COMPUTE: For liquid crystals: verify order parameter S = <P_2(cos theta)> in [0,1]

[] Active matter
  - CHECK: For active systems: energy is NOT conserved (driven). Don't apply equilibrium thermodynamics
  - COMPUTE: Verify motility-induced phase separation follows known density thresholds

[] Coarse-graining consistency
  - COMPUTE: Verify thermodynamic properties (pressure, compressibility) match between fine and coarse models
  - COMPUTE: Verify structural properties (RDF, structure factor) are preserved at target resolution

[] Diffusion and transport
  - COMPUTE: Verify Einstein relation D = k_B*T/(6*pi*eta*R) for spherical particles
  - COMPUTE: For anomalous diffusion: verify MSD ~ t^alpha with correct exponent (alpha != 1)

[] Force field validation
  - COMPUTE: For MD: verify radial distribution function g(r) matches experimental/ab-initio data
  - COMPUTE: Verify equation of state (density vs pressure) at simulation conditions

[] Fluctuation-dissipation
  - COMPUTE: Verify FDT: chi''(omega) = omega/(2*k_B*T) * S(omega) for equilibrium systems
  - COMPUTE: For non-equilibrium: verify violations of FDT are physically consistent (effective temperature)

[] Elastic properties
  - COMPUTE: Verify stress-strain relation in linear regime gives correct Young's modulus / shear modulus
  - COMPUTE: For networks: verify Maxwell counting (rigidity = bonds - degrees of freedom)

[] Biological relevance checks
  - COMPUTE: Verify binding energies are in biologically relevant range (1-20 k_B*T)
  - COMPUTE: For protein folding: verify contact map and secondary structure match known PDB data
```

---

## String Field Theory Checklist

```
[] BRST and quantum numbers
  - COMPUTE: Verify Q_B^2 = 0 in the chosen background and Hilbert space
  - COMPUTE: Check ghost number and picture number for every field, vertex, and gauge parameter; for closed strings verify b_0^-, L_0^- constraints

[] Algebraic consistency
  - COMPUTE: Verify BPZ cyclicity and, as applicable, associativity or A_infinity / L_infinity identities for the products actually used
  - COMPUTE: If working around a shifted background, re-derive the shifted BRST operator and shifted products

[] Gauge fixing and truncation
  - COMPUTE: Check the stated gauge choice (Siegel, Schnabl, WZW-like partial gauge, etc.) is admissible in the sector studied
  - COMPUTE: Compare key observables across multiple truncation levels and verify convergence or stabilization before drawing physical conclusions

[] Canonical benchmarks
  - COMPUTE: For tachyon-vacuum claims, verify the vacuum energy approaches minus the unstable D-brane tension in the stated normalization
  - COMPUTE: For physical-background or marginal-deformation claims, verify Ellwood invariants, boundary-state data, or worldsheet factorization/amplitude matching
```

---

## Profile-Specific Behavioral Details

### deep-theory (full details)

**Full verification.** Run the full universal verifier registry plus every required contract-aware check. Require INDEPENDENTLY CONFIRMED confidence for every key derivation result. Re-derive every limiting case. Full dimensional analysis trace. No shortcuts.

Additional requirements:
- Every analytical step must be verified independently
- All limiting cases must be explicitly re-derived (not just checked structurally)
- Cross-checks must use a genuinely independent method
- Convention consistency must be traced through every equation

### numerical (full details)

**Computation-focused verification.** Emphasize: convergence testing (5.5), numerical spot-checks (5.2), error budgets, code validation. De-emphasize: analytical re-derivation (unless it validates numerics). Run all numerical checks at 3+ resolution levels.

Additional requirements:
- Convergence tests at minimum 3 resolution levels
- Richardson extrapolation where applicable
- Error budget accounting for all numerical approximations
- Code validation against known analytical results in limiting cases

### exploratory (full details)

**Exploratory verification with full guardrails.** Keep the contract gate and every applicable decisive-anchor, forbidden-proxy, benchmark-reproduction, direct-vs-proxy, and formulation-critical check. Exploratory mode may compress optional depth; it does NOT waive the checks that would catch false progress.

### review (full details)

**Cross-validation focused.** Run ALL checks. Additionally: compare every numerical result against at least 2 literature values. Verify every approximation is justified with explicit bounds. Check that error bars are conservative. Flag any result that cannot be cross-validated.

Additional requirements:
- Every result compared against 2+ literature sources
- Approximation bounds explicitly verified
- Error bars checked for conservatism (not just existence)
- Any result without cross-validation explicitly flagged

### paper-writing (full details)

**Publication-readiness verification.** Run all checks. Additionally verify: figures match data, equations in text match derivation files, notation is consistent throughout, all symbols are defined, references exist.

Additional requirements:
- Figure-data consistency check
- Notation audit across all sections
- Symbol definition completeness
- Reference existence verification
- Equation numbering and cross-reference consistency
