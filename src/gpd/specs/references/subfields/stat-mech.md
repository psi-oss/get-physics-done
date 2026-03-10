---
load_when:
  - "statistical mechanics"
  - "partition function"
  - "phase transition"
  - "critical phenomena"
  - "Ising model"
  - "free energy"
  - "ensemble"
tier: 2
context_cost: medium
---

# Statistical Mechanics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/monte-carlo.md` (Metropolis, cluster algorithms, histogram methods), `references/protocols/order-of-limits.md` (thermodynamic limit, critical limits), `references/protocols/finite-temperature-field-theory.md` (Matsubara formalism, thermal field theory), `references/protocols/numerical-computation.md` (general numerical methods), `references/protocols/exact-diagonalization.md` (small systems, symmetry sectors), `references/protocols/stochastic-processes.md` (Langevin dynamics, master equations, FDT), `references/protocols/renormalization-group.md` (RG flows, critical exponents, universality), `references/protocols/bethe-ansatz.md` (exact solutions for integrable models), `references/protocols/large-n-expansion.md` (1/N expansion for critical exponents), `references/protocols/resummation.md` (Borel summation of asymptotic series), `references/protocols/kinetic-theory.md` (Boltzmann equation, transport coefficients).

**Partition Functions:**

- Canonical: Z = sum_states exp(-beta * E_i) = Tr[exp(-beta * H)]
- Grand canonical: Xi = sum_N z^N * Z_N where z = exp(beta * mu) is fugacity
- Microcanonical: Omega(E) = number of states with energy in [E, E+delta_E]
- Equivalence of ensembles in thermodynamic limit (N -> infinity) for short-range interactions
- Path integral: quantum partition function = classical partition function in d+1 dimensions (Euclidean time)

**Phase Transitions and Critical Phenomena:**

- First-order: discontinuity in first derivative of free energy (latent heat, density jump)
- Continuous (second-order): divergent susceptibilities, correlation length, specific heat
- Critical exponents: alpha (specific heat), beta (order parameter), gamma (susceptibility), delta (critical isotherm), nu (correlation length), eta (anomalous dimension)
- Scaling relations: alpha + 2*beta + gamma = 2 (Rushbrooke), gamma = nu*(2-eta) (Fisher), hyperscaling: 2 - alpha = d\*nu
- Universality: critical exponents depend only on d, n (order parameter dimension), range of interactions

**Renormalization Group:**

- **Real-space RG:** Block spin transformations; Kadanoff, Migdal-Kadanoff approximation; exact for hierarchical lattices
- **Momentum-space RG:** Wilson's approach; integrate out high-momentum modes shell by shell; epsilon-expansion (d = 4 - epsilon)
- **Functional RG:** Wetterstein equation for flowing effective action; non-perturbative; handles strong coupling
- **DMRG / tensor RG:** Numerical RG for lattice models; real-space entanglement structure
- Fixed points: Gaussian (free), Wilson-Fisher (interacting), etc.; relevant/irrelevant/marginal operators

**Monte Carlo Methods:**

- **Metropolis algorithm:** Single-site updates; accept with probability min(1, exp(-beta \* Delta_E)); simple but slow near T_c
- **Cluster algorithms:** Swendsen-Wang (all clusters), Wolff (single cluster); dramatically reduce critical slowing down for O(n) models
- **Wang-Landau:** Flat-histogram method; estimates density of states g(E) directly; useful for first-order transitions and complex energy landscapes
- **Parallel tempering (replica exchange):** Run replicas at multiple temperatures; exchange configurations; overcomes free-energy barriers
- **Worm algorithm:** For high-precision studies of superfluid/BEC transitions and loop models

**Mean-Field Theory:**

- Weiss/Bragg-Williams: replace fluctuating neighbors by average; exact in d -> infinity
- Landau theory: expand free energy in powers of order parameter; predicts mean-field exponents (beta=1/2, gamma=1, etc.)
- Ginzburg criterion: mean-field breaks down when fluctuations comparable to order parameter; defines upper critical dimension d_c
- Variational mean field: optimize over product states; Bogoliubov inequality F <= F_0 + <H - H_0>\_0
- Self-consistent field theories: Hartree, Hartree-Fock, BCS as mean-field approximations

**Exactly Solved Models:**

- 1D Ising: Z = (2*cosh(beta*J))^N for zero field; no phase transition at T > 0
- 2D Ising (Onsager): T_c = 2*J / (k_B * ln(1 + sqrt(2))); beta = 1/8, nu = 1, gamma = 7/4, alpha = 0 (log)
- 6-vertex / 8-vertex models: Bethe ansatz; Baxter's exact solution
- XY model in 2D: Berezinskii-Kosterlitz-Thouless transition (topological, no symmetry breaking); T_BKT determined by universal jump in superfluid stiffness
- Hard rods in 1D: Tonks gas; exact partition function via transfer matrix

## Key Tools and Software

| Tool                           | Purpose                             | Notes                                                         |
| ------------------------------ | ----------------------------------- | ------------------------------------------------------------- |
| **Monte Carlo codes (custom)** | Ising, Potts, XY, Heisenberg models | Often written per-project; use Mersenne Twister or better RNG |
| **ALPS**                       | Lattice model simulations           | MC, classical MC, Wang-Landau, exact diag                     |
| **emcee**                      | MCMC sampler (Python)               | Affine-invariant ensemble sampler; general purpose            |
| **Stan**                       | Probabilistic programming           | Hamiltonian MC (NUTS); Bayesian inference                     |
| **LAMMPS**                     | Molecular dynamics                  | Classical MD; many pair potentials; extensive                 |
| **OpenMM**                     | GPU-accelerated MD                  | Biomolecular and soft matter                                  |
| **SymPy**                      | Symbolic partition functions        | Series expansions, exact results                              |
| **NetworkX**                   | Graph-based lattice models          | Lattice generation, percolation                               |
| **numba / JAX**                | JIT compilation for MC loops        | Critical for performance in custom MC codes                   |

## Validation Strategies

**Known Exact Solutions:**

- 1D Ising: check partition function, correlation function <S_0 S_r> = tanh(beta\*J)^r
- 2D Ising: Onsager solution for critical temperature, free energy, specific heat
- 2D Ising on square lattice: T_c/J = 2/ln(1+sqrt(2)) = 2.26918...
- Ideal gas: Z = V^N / (N! * lambda^{3N}); F = -NkT*ln(V/(N\*lambda^3)) - NkT (Sackur-Tetrode)
- Harmonic chain: exact dispersion omega(k) = 2*sqrt(K/m)*|sin(k\*a/2)|

**Universality Class Matching:**

- d=2 Ising: beta = 1/8, gamma = 7/4, nu = 1, eta = 1/4, alpha = 0 (log)
- d=3 Ising: beta = 0.3265, gamma = 1.2372, nu = 0.6301 (high-precision MC + conformal bootstrap)
- d=3 XY: beta = 0.3486, gamma = 1.3178, nu = 0.6717 (superfluid helium universality)
- d=3 Heisenberg: beta = 0.3689, gamma = 1.3960, nu = 0.7112
- Mean-field (d >= d_c): beta = 1/2, gamma = 1, nu = 1/2, eta = 0, alpha = 0

**Detailed Balance:**

- Transition rates must satisfy: W(A->B) _ P_eq(A) = W(B->A) _ P_eq(B)
- Check: verify Metropolis acceptance ratio satisfies detailed balance
- For cluster algorithms: verify that cluster construction preserves detailed balance (this is subtle -- refer to Swendsen-Wang proof)

**Thermodynamic Consistency:**

- Maxwell relations: (dS/dV)\_T = (dP/dT)\_V, etc.
- Specific heat from energy fluctuations: C_V = (1/kT^2) \* (<E^2> - <E>^2)
- Susceptibility from order parameter fluctuations: chi = beta _ N _ (<m^2> - <m>^2)
- Compressibility from number fluctuations (grand canonical)

**Finite-Size Scaling:**

- Near T_c: observable O(T, L) = L^{x/nu} * f((T - T_c) * L^{1/nu})
- Binder cumulant: U_L = 1 - <m^4>/(3\*<m^2>^2); crossing point of U_L for different L gives T_c
- Data collapse: plot O * L^{-x/nu} vs (T-T_c)*L^{1/nu}; all system sizes should collapse to single curve
- Corrections to scaling: include L^{-omega} terms for quantitative fits

## Common Pitfalls

- **Critical slowing down:** Local-update MC near T_c has autocorrelation time tau ~ L^z with z ~ 2. Use cluster algorithms (z ~ 0.2 for Wolff) or non-local updates
- **Confusing ensembles:** Free energy is NOT the same in different ensembles for finite systems. F_canonical != F_grand_canonical for small N
- **Neglecting finite-size effects at phase transitions:** First-order transitions are rounded and shifted; continuous transitions show drift in T_c(L). Always perform finite-size scaling analysis
- **Wrong identification of transition order:** A steep but continuous transition can look first-order for small systems. Use Binder cumulant, energy histogram, or Lee-Yang zero analysis
- **Ignoring autocorrelations in MC:** Independent measurements require separation by ~2*tau_auto. Reporting statistical errors without accounting for autocorrelation underestimates uncertainty by factor of sqrt(2*tau_auto)
- **Premature thermalization:** System may appear equilibrated but be trapped in metastable state. Run multiple independent simulations from different initial conditions; check for hysteresis
- **Mean-field for low dimensions:** Mean-field critical exponents are wrong below d_c (d_c = 4 for Ising/O(n), d_c = 6 for percolation, d_c = 8 for self-avoiding walks). Do not trust mean-field in d = 2 or 3 for quantitative predictions near T_c
- **Forgetting the N! in classical partition function:** Gibbs 1/N! factor for identical particles; without it, entropy is non-extensive (Gibbs paradox)

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Kardar-Parisi-Zhang universality** | KPZ exponents in higher dimensions, exact solutions for KPZ equation | Corwin, Quastel, Takeuchi | Good — analytical + MC simulation |
| **Active matter** | Phase separation in self-propelled particles, motility-induced phase separation (MIPS) | Cates, Marchetti, Tailleur | Good — Langevin dynamics, field theory |
| **Machine learning for phase transitions** | Unsupervised detection of phase boundaries, neural network RG | Carleo, Carrasquilla, Melko | Excellent — MC data + ML analysis |
| **Eigenstate thermalization** | ETH violations (MBL, quantum scars), thermalization timescales | Rigol, Deutsch, Srednicki | Good — exact diag, TEBD |
| **Information-theoretic stat mech** | Entropy production in non-equilibrium, thermodynamic uncertainty relations | Seifert, Esposito, Peliti | Excellent — analytical + simulation |
| **Conformal field theory in stat mech** | CFT data from Monte Carlo, conformal bootstrap for 3D critical phenomena | Kos, Poland, Simmons-Duffin | Excellent — MC + numerical bootstrap |

## Methodology Decision Tree

```
What type of problem?
├── Equilibrium phase transition
│   ├── Known universality class? → MC with cluster algorithm + FSS
│   ├── Unknown universality class? → MC with multiple observables + Binder cumulant analysis
│   ├── First-order suspected? → Multicanonical/Wang-Landau + energy histograms
│   └── Exactly solvable? → Transfer matrix, Bethe ansatz, or exact enumeration
├── Non-equilibrium
│   ├── Steady state exists? → Kinetic MC + master equation analysis
│   ├── Driven system? → Langevin dynamics or lattice Boltzmann
│   └── Far from equilibrium? → Stochastic field theory (Martin-Siggia-Rose)
├── Disordered system
│   ├── Quenched disorder? → Replica method or replica-symmetric breaking (RSB)
│   ├── Annealed disorder? → Standard stat mech with effective Hamiltonian
│   └── Spin glass? → Parallel tempering MC + overlap distributions
└── Exact results desired
    ├── 1D? → Transfer matrix or Bethe ansatz
    ├── 2D conformal? → CFT (central charge, scaling dimensions)
    └── Mean-field exact (d >= d_c)? → Landau theory + Ginzburg criterion
```

## Common Collaboration Patterns

- **Stat mech + Probability theory:** Exact solutions (SLE, KPZ) involve rigorous probability. Physicists provide conjectures and scaling arguments; mathematicians provide proofs.
- **Stat mech + Biophysics:** Protein folding, gene regulatory networks, population dynamics use stat mech methods (Ising-like models, master equations, stochastic processes).
- **Stat mech + Machine learning:** Boltzmann machines ARE stat mech. RBMs, variational autoencoders, and generative models have direct stat mech interpretations.
- **Stat mech + Materials science:** Phase diagrams of alloys (CALPHAD), crystal growth kinetics, polymer physics.

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | MC study of one model with full FSS analysis, or exact solution of a new 1D/2D model | "Critical behavior of the 3-state Potts model with quenched bond disorder" |
| **Postdoc** | New universality class identification, or method development (new MC algorithm, new exact solution) | "Wang-Landau study of the random-field Ising model: violation of hyperscaling" |
| **Faculty** | New paradigm (active matter theory, information engines) or resolution of long-standing controversy | "Proof that MBL exists/doesn't exist in the thermodynamic limit"
