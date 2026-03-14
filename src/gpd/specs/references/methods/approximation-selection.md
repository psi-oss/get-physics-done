# Approximation Selection

A decision framework for choosing approximation methods in physics. The wrong approximation wastes compute and produces misleading results; the right one turns an intractable problem into a solved one.

<core_principle>

**Match the method to the physics, not the other way around.**

Before choosing an approximation:

1. Identify the small parameter (if one exists)
2. Characterize the regime (weak/strong coupling, few/many body, classical/quantum)
3. Check what is known exactly (symmetries, limiting cases, conservation laws)
4. Choose the method that preserves the most important physics
5. Verify convergence before trusting results

**If no small parameter exists and the system is not amenable to mean-field, variational, or exact methods, this is a research problem in itself.** Document it as such rather than forcing an inappropriate approximation.

</core_principle>

<decision_flowchart>

## Decision Flowchart

```
START: What kind of problem?
  |
  ├─ Is there a small parameter (g, alpha, epsilon)?
  │    ├─ YES, and g << 1
  │    │    └─ PERTURBATION THEORY (see §1)
  │    │         ├─ Does the series converge?
  │    │         │    ├─ YES → Use fixed-order perturbation theory
  │    │         │    └─ NO → Resummation (Padé, Borel, RG) or switch method
  │    │         └─ Are there infrared/secular divergences?
  │    │              ├─ YES → Renormalization group (see §1.3)
  │    │              └─ NO → Standard perturbation theory sufficient
  │    └─ NO (g ~ 1 or g >> 1)
  │         └─ Go to "No small parameter" branch
  │
  ├─ No small parameter identified
  │    ├─ Is this a ground state / low-energy problem?
  │    │    ├─ YES → VARIATIONAL METHODS (see §2)
  │    │    │    ├─ Can you guess the wavefunction form?
  │    │    │    │    ├─ YES → Direct variational (Ritz)
  │    │    │    │    └─ NO → Systematic expansion (CI, CC, DMRG)
  │    │    │    └─ Is the system 1D?
  │    │    │         ├─ YES → DMRG / tensor networks (see §2.3)
  │    │    │         └─ NO → VMC or coupled cluster
  │    │    └─ NO
  │    │         └─ Continue below
  │    │
  │    ├─ Is this a many-body system (N >> 1)?
  │    │    ├─ YES → MEAN-FIELD METHODS (see §3)
  │    │    │    ├─ Is the interaction long-range or high-dimensional?
  │    │    │    │    ├─ YES → Mean-field likely accurate
  │    │    │    │    └─ NO → Mean-field as starting point, add fluctuations
  │    │    │    └─ Are quantum fluctuations important?
  │    │    │         ├─ YES → Beyond mean-field (RPA, 1/N, functional RG)
  │    │    │         └─ NO → Classical mean-field sufficient
  │    │    └─ NO (few-body, N ~ 2-20)
  │    │         └─ NUMERICAL EXACT METHODS (see §4)
  │    │
  │    └─ Is there a known exact solution or integrable structure?
  │         ├─ YES → Use it (Bethe ansatz, conformal field theory, etc.)
  │         └─ NO → Combine methods; see §5 (Hybrid Strategies)
  │
  └─ Special regimes
       ├─ Near a phase transition → RG / scaling / conformal bootstrap (see §1.3)
       ├─ Semiclassical (large quantum numbers) → WKB / saddle-point (see §1.4)
       ├─ High temperature → High-T expansion / classical limit
       └─ Strong disorder → Real-space RG / replica method / SDRG
```

</decision_flowchart>

<perturbation_theory>

## 1. Perturbation Theory

**When to use:** A small dimensionless parameter exists and has been identified.

### 1.1 Identifying the Small Parameter

| Domain | Common Small Parameters | Typical Value |
|--------|------------------------|---------------|
| QED | alpha = e^2/(4*pi) | 1/137 |
| Weak interactions | G_F * E^2 | << 1 at low energy |
| Gravity | G*M/(r*c^2) | << 1 far from compact objects |
| Condensed matter | U/t (weak coupling Hubbard) | < 1 |
| BCS superconductivity | λ = N(0)V (BCS mean-field valid for λ ≲ 1; weak-coupling perturbation theory requires λ ≪ 1; gap Δ ~ ω_D exp(-1/λ); Eliashberg extends to strong coupling) | |
| Dilute gases | n*a^3 (gas parameter) | << 1 |
| Semiclassical | hbar / S_classical | << 1 for large quantum numbers |
| Born approximation | V / E (scattering) | << 1 for fast particles |

**Concrete criterion:** If the dimensionless coupling g satisfies g < 0.3, perturbation theory to a few orders is usually reliable. If 0.3 < g < 1, include higher orders or resum. If g > 1, perturbation theory will fail.

### 1.2 Convergence Indicators

**Signs that perturbation theory is working:**

- Each successive order contributes less than the previous
- The ratio |a_{n+1}/a_n| decreases (or at least doesn't grow)
- Results at order n and n+1 bracket the exact answer (for alternating series)
- Physical quantities (cross sections, energies) remain in the physically allowed range

**Signs that perturbation theory is failing:**

- Higher-order corrections are comparable to or larger than lower-order ones
- The perturbative result violates unitarity bounds or positivity constraints
- Logarithmic enhancements: terms like g^n * log^n(Q/mu) grow despite small g
- Factorial growth of coefficients: |a_n| ~ n! (asymptotic series)
- IR divergences that don't cancel between diagrams at the same order
- Secular terms: corrections that grow with time (t * g * ...)

**Quantitative convergence test:**

```python
def check_perturbative_convergence(coefficients, coupling):
    """
    Check if perturbation series is converging.

    Args:
        coefficients: [a_0, a_1, a_2, ...] series coefficients
        coupling: dimensionless coupling constant g
    """
    terms = [c * coupling**n for n, c in enumerate(coefficients)]
    partial_sums = [sum(terms[:n+1]) for n in range(len(terms))]

    for n in range(1, len(terms)):
        ratio = abs(terms[n] / terms[n-1]) if terms[n-1] != 0 else float('inf')
        relative_correction = abs(terms[n] / partial_sums[n-1]) if partial_sums[n-1] != 0 else float('inf')
        converging = ratio < 1 and relative_correction < 0.3
        status = "ok" if converging else "WARNING"
        print(f"  Order {n}: |a_n g^n / a_(n-1) g^(n-1)| = {ratio:.3f}, "
              f"relative correction = {relative_correction:.3f} [{status}]")
```

### 1.3 Renormalization Group (RG)

**When to use RG instead of fixed-order perturbation theory:**

- Large logarithms: terms like alpha * log(Q/mu) become O(1) even though alpha << 1
- Multiple scales: physics at scale Q involves physics at all scales between Q and mu
- Near a critical point: correlation length diverges, fluctuations on all scales matter
- Running couplings: effective coupling depends on energy scale

**RG strategy:**

1. Identify the relevant scales (UV cutoff, IR scale, physical scale)
2. Compute beta function: dg/d(log mu) = beta(g) at one loop minimum
3. Solve RG equation to resum leading logarithms
4. Check that the running coupling remains perturbative at all relevant scales

**Convergence criterion:** If beta(g) drives g to smaller values at the scale of interest (asymptotic freedom in QCD, for example), the RG-improved perturbation theory is reliable. If g grows and approaches a Landau pole, the method breaks down near that scale.

### 1.4 Semiclassical / WKB

**When to use:**

- Large quantum numbers (n >> 1)
- Action much larger than hbar (S/hbar >> 1)
- Slowly varying potential (de Broglie wavelength << potential variation length)
- Path integral dominated by saddle point

**Failure modes:**

- Near classical turning points (use connection formulas or uniform approximation)
- Tunneling through wide barriers (exponentially small, hard to get prefactor right)
- Chaotic classical dynamics (no simple WKB; use random matrix theory instead)
- Near caustics (where classical trajectories focus)

### 1.5 Fallback When Perturbation Theory Fails

If perturbative expansion shows poor convergence:

1. **Resum:** Padé approximants, Borel summation, conformal mapping
2. **Reorganize:** Choose a different expansion parameter (1/N, epsilon = 4-d, strong-coupling expansion)
3. **Switch method:** Go to variational, mean-field, or numerical exact
4. **Use RG:** If the problem is large logarithms rather than large coupling

</perturbation_theory>

<variational_methods>

## 2. Variational Methods

**When to use:** No small parameter, ground state or low-energy properties needed, or you can make an educated guess about the wavefunction structure.

### 2.1 Direct Variational (Ritz Method)

**Principle:** Any trial wavefunction gives an upper bound on the ground state energy. Minimize over parameters to get the best bound.

**When it works well:**

- You have physical intuition about the wavefunction form
- The system has a clear ground state structure (no frustration, no competing phases)
- Few parameters capture the essential physics

**When it fails:**

- Excited states (no variational bound in general)
- Strongly correlated systems where the wavefunction has complex entanglement structure
- Phase boundaries where the nature of the ground state changes qualitatively

**Quality indicators:**

| Indicator | Good | Suspect | Bad |
|-----------|------|---------|-----|
| Energy relative to exact (if known) | < 1% above | 1-5% above | > 5% above |
| Overlap with exact ground state | > 0.95 | 0.8-0.95 | < 0.8 |
| Variance of energy <(H-E)^2> | << E^2 | ~ 0.1 * E^2 | ~ E^2 |
| Sensitivity to initial parameters | Stable | Mild dependence | Multiple minima |

### 2.2 Systematic Variational Expansions

**Configuration Interaction (CI):**

- Expand in Slater determinants built from single-particle basis
- Full CI is exact but scales exponentially: dim ~ (N choose N_e)
- Truncated CI (CISD, CISDT) gives systematic improvement
- Use when: quantum chemistry accuracy needed, N_electrons < ~20

**Coupled Cluster (CC):**

- Exponential ansatz: |psi> = exp(T) |phi_0>
- CCSD: singles and doubles, scales as N^6
- CCSD(T): perturbative triples, "gold standard" of quantum chemistry
- Size-extensive by construction (CI is not, except full CI)
- Use when: molecules, weakly correlated systems, need size-extensivity

**Variational Monte Carlo (VMC):**

- Stochastic evaluation of variational energy
- Can use complex trial wavefunctions (Jastrow factors, backflow, neural network)
- Scales well to large systems
- Use when: many-body quantum systems, especially when analytical integration is impossible

### 2.3 Tensor Network Methods (DMRG, MPS, PEPS)

**When to use:**

- 1D systems: DMRG / MPS is often the method of choice
- Gapped 1D systems: area law guarantees MPS is efficient
- 2D systems: PEPS possible but much more expensive
- Ground state and low-lying excitations

**Convergence criterion:** Truncation error (discarded weight) and entanglement entropy vs bond dimension chi:

- Gapped 1D: S ~ const, chi ~ O(1) sufficient, exponential convergence in chi
- Critical 1D: S ~ (c/6) log(L), chi ~ poly(L) needed, algebraic convergence
- 2D: S ~ L (area law but with large prefactor), chi requirements can be severe

**Decision criteria for DMRG vs other methods:**

- 1D gapped system with N < 1000 sites: DMRG wins, almost always
- 1D critical system: DMRG works but needs scaling analysis in chi
- 2D system: DMRG on cylinders (circumference ~ 6-12 sites), or iPEPS
- Finite temperature: purification or METTS (minimally entangled typical thermal states)
- Dynamics: tDMRG for short to moderate times; limited by entanglement growth

</variational_methods>

<mean_field>

## 3. Mean-Field Methods

**When to use:** Many-body systems (N >> 1) where collective behavior dominates over individual fluctuations.

### 3.1 Classical Mean-Field (Weiss, Bragg-Williams)

**Principle:** Replace interactions with an average (mean) field. Each particle/site sees the average effect of all others.

**When it works:**

- Long-range interactions (each site interacts with many others)
- High dimensionality (d > d_c, the upper critical dimension; d_c = 4 for Ising/O(n))
- Large coordination number z >> 1
- Far from phase transitions (fluctuations suppressed)

**When it fails:**

- Low dimensions (d = 1: never orders at T > 0 for short-range; d = 2: Mermin-Wagner for continuous symmetry)
- Near critical points (fluctuations diverge, mean-field exponents wrong for d < d_c)
- Frustrated systems (no single dominant order parameter)
- Strong quantum fluctuations (Mott transition, spin liquids)

**Quantitative criterion:** Mean-field is reliable when the Ginzburg criterion is satisfied:

```
Ginzburg number: Gi = (T_c^MF - T_c^true) / T_c^MF

Gi << 1: mean-field is accurate (e.g., BCS superconductors, Gi ~ 10^{-14})
Gi ~ 1: mean-field gives qualitative picture only (e.g., 3D Ising, Gi ~ 0.01)
Gi > 1: mean-field unreliable (low-dimensional systems, strongly fluctuating)
```

### 3.2 Quantum Mean-Field (Hartree-Fock, BCS, DFT)

**Hartree-Fock:**

- Self-consistent single-particle approximation
- Good for weakly interacting fermions
- Missing: correlation energy (typically 1-5% of total energy in atoms)
- Failure: metallic hydrogen, strongly correlated oxides, Mott insulators

**BCS:**

- Mean-field for pairing instability
- Exact in the weak-coupling limit (N(0)*V << 1)
- Predicts gap, T_c, thermodynamics correctly in conventional superconductors
- Failure: strong-coupling superconductors (use Eliashberg), cuprates (mechanism unclear)

**Density Functional Theory (DFT):**

- In principle exact for ground state density
- In practice: exchange-correlation functional is approximate
- LDA/GGA: good for metals, semiconductors (band gaps underestimated by ~50%)
- Hybrid functionals: better gaps (B3LYP, HSE06)
- Failure: strongly correlated (NiO, FeO), van der Waals (need DFT-D or vdW-DF)

### 3.3 Beyond Mean-Field

When mean-field is the starting point but fluctuations matter:

| Method | What It Adds | Regime |
|--------|-------------|--------|
| Random Phase Approximation (RPA) | Collective excitations (plasmons, magnons) | Metallic systems, long-range order |
| GW approximation | Dynamical screening of self-energy | Band gaps, quasiparticle spectra |
| 1/N expansion | Systematic corrections in 1/N | Large-N models (O(N), SU(N)) |
| Functional RG | Non-perturbative flow of effective action | Near criticality, competing orders |
| Dynamical Mean-Field Theory (DMFT) | Local quantum fluctuations | Strongly correlated lattice models |
| Fluctuation exchange (FLEX) | Self-consistent treatment of particle-hole and particle-particle channels | Weak to moderate coupling |

**Decision: when to go beyond mean-field:**

- Mean-field transition temperature is much higher than observed T_c → fluctuations lower it
- Mean-field predicts wrong universality class → need RG or numerical
- Spectral function has no incoherent weight → mean-field misses the physics
- Transport properties at finite temperature → need vertex corrections and proper self-energy

</mean_field>

<numerical_exact>

## 4. Numerical Exact Methods

**When to use:** Small systems where exact answers are needed as benchmarks, or when no controlled approximation exists.

### 4.1 Exact Diagonalization (ED)

**What it is:** Construct the full Hamiltonian matrix and diagonalize.

**System size limits:**

| System | Hilbert Space Dim | Max Feasible (dense) | Max Feasible (Lanczos) |
|--------|-------------------|---------------------|----------------------|
| Spin-1/2 chain | 2^N | N ~ 16-18 | N ~ 36-44 |
| Spinless fermions | C(L, N_e) | L ~ 20-24 | L ~ 30-36 |
| Hubbard model | C(L, N_up) * C(L, N_down) | L ~ 12-14 | L ~ 18-22 |
| Bosons (truncated) | C(L+N-1, N) | depends on truncation | depends on truncation |

**Use when:**

- You need exact eigenvalues/eigenvectors (benchmarking other methods)
- Dynamical response functions at all frequencies (Lanczos continued fraction)
- Finite-size scaling studies (need exact results at multiple sizes)
- Entanglement entropy, entanglement spectrum

**Limitations:**

- Exponential scaling with system size (no way around this)
- Finite-size effects can be large, especially near phase transitions
- No thermal averaging without full spectrum (use FTLM or typicality methods)

### 4.2 Quantum Monte Carlo (QMC)

**Variants and when to use each:**

| Method | Systems | Advantage | Limitation |
|--------|---------|-----------|------------|
| Diffusion MC (DMC) | Continuum, atoms, molecules | Exact for bosons | Fixed-node for fermions |
| Auxiliary-field QMC (AFQMC) | Lattice models, ab initio | No sign problem for some | Sign problem for general fermions |
| Determinantal QMC (DQMC) | Lattice models at finite T | Unbiased at half-filling | Sign problem away from half-filling |
| Stochastic Series Expansion (SSE) | Quantum spin models | Efficient, no Trotter error | Sign problem for frustrated magnets |
| World-line QMC | Bosonic systems | Exact, efficient | Not applicable to fermions directly |

**The sign problem:** For fermionic systems or frustrated magnets, the Monte Carlo weight can be negative, making importance sampling inefficient. The average sign <sign> → 0 exponentially with system size and inverse temperature.

**Decision criterion:**

```
Average sign > 0.1:  QMC is feasible, results reliable
Average sign 0.01-0.1:  QMC possible but expensive, error bars large
Average sign < 0.01:  QMC effectively useless, switch method
```

**Sign-problem-free cases:** Half-filled Hubbard (bipartite lattice), attractive Hubbard, unfrustrated Heisenberg, bosonic systems, certain time-reversal-invariant models.

### 4.3 Other Exact/Near-Exact Methods

**Bethe ansatz:** Exact solution for integrable 1D models (XXX/XXZ spin chains, Hubbard, Lieb-Liniger). Limited to 1D, specific models, but gives exact thermodynamics and excitation spectra.

**Conformal field theory:** Exact at critical points in 1D+1. Determines correlation function exponents, operator content, entanglement entropy. Limited to conformally invariant systems.

**Conformal bootstrap:** Rigorous bounds on scaling dimensions and OPE coefficients from crossing symmetry + unitarity. Non-perturbative, works in any dimension. Limited to CFTs.

</numerical_exact>

<hybrid_strategies>

## 5. Hybrid and Fallback Strategies

When a single method is insufficient, combine approaches:

### 5.1 Method Combination Patterns

| Pattern | How It Works | Example |
|---------|-------------|---------|
| Mean-field + fluctuations | Start from MF solution, add corrections | Hartree-Fock + RPA, DFT + GW |
| Perturbation theory + RG | Resum large logs in perturbative coefficients | QCD running coupling, critical exponents |
| Variational + QMC | Use VMC with optimized trial wavefunction from VMC, then project with DMC | FN-DMC for molecular systems |
| ED + finite-size scaling | Exact results at multiple sizes, extrapolate to thermodynamic limit | Critical exponents from ED + scaling |
| DMRG + field theory | DMRG for numerics, CFT for interpretation | Central charge and scaling dimensions from entanglement |
| Mean-field + DMFT | Lattice mean-field with local quantum corrections | Strongly correlated lattice models |

### 5.2 When an Approximation Breaks Down

**Symptoms and responses:**

| Symptom | Likely Cause | Response |
|---------|-------------|----------|
| Series coefficients grow factorially | Asymptotic series | Borel-Padé resummation or switch to non-perturbative method |
| Result violates unitarity/positivity | Expansion parameter not small enough | Include higher orders or switch to non-perturbative |
| Convergence plateaus at wrong value | Systematic error from truncation | Increase basis/grid/order or switch method |
| Different methods give very different answers | Problem is in a difficult regime | Use method with rigorous error bounds; benchmark on simpler version |
| Result depends sensitively on cutoff/regulator | Physical result is non-perturbative | Need resummation or non-perturbative method |
| Variational energy far above exact | Trial wavefunction misses essential physics | Redesign trial function; use systematic expansion instead |

### 5.3 The "Two Methods" Rule

**For any result you intend to publish or build upon, compute it with two independent methods.** If they agree, confidence is high. If they disagree, you have learned something important about the limitations of at least one method.

Examples:

- Perturbation theory + exact diagonalization (in the regime where both are applicable)
- DMRG + QMC (for sign-problem-free 1D systems)
- DFT + CCSD(T) (for molecular energies)
- Analytical limiting case + numerical solution (always available)

</hybrid_strategies>

<common_pitfalls>

## 6. Common Pitfalls

**Using perturbation theory when the coupling isn't small:**

- QCD at low energies (alpha_s ~ 1 at 1 GeV) -- use lattice QCD or chiral perturbation theory instead
- Hubbard model at U/t ~ 8 -- this is strong coupling; mean-field or DMFT, not perturbation theory
- Kondo problem at T << T_K -- perturbation in J diverges; use Wilson NRG or Bethe ansatz

**Mean-field in low dimensions:**

- 1D Ising model at T > 0: mean-field predicts ordering, exact solution shows no transition
- 2D Heisenberg model: mean-field predicts Néel order at finite T, Mermin-Wagner forbids it
- 1D metals: Fermi liquid theory fails; use Luttinger liquid theory

**Variational with wrong ansatz:**

- Hartree-Fock for a Mott insulator: predicts metal, misses the physics entirely
- Product state for a spin liquid: zero overlap with the true ground state
- Gaussian wavefunction for double-well potential: misses tunneling splitting

**Ignoring the sign problem in QMC:**

- Reporting QMC results with average sign < 0.01 without acknowledging the exponential noise
- Comparing QMC results across parameters where sign severity changes dramatically
- Using constrained-path or fixed-node QMC without estimating the systematic bias

**Not checking convergence:**

- Reporting ED result at one system size as "the answer" without finite-size scaling
- DMRG with fixed bond dimension without checking truncation error
- DFT with one functional without comparing LDA/GGA/hybrid
- Perturbation theory at one loop without estimating higher-order corrections

</common_pitfalls>

<quick_reference>

## Quick Reference Table

| Problem Type | First Choice | Second Choice | Avoid |
|-------------|-------------|---------------|-------|
| Weakly coupled QFT (g << 1) | Perturbation theory | RG-improved PT | Non-perturbative (overkill) |
| Strongly coupled QFT (g ~ 1) | Lattice gauge theory | AdS/CFT (if applicable) | Fixed-order PT |
| 1D gapped quantum | DMRG | ED + scaling | Mean-field |
| 1D critical quantum | DMRG + CFT | Bethe ansatz (if integrable) | Mean-field |
| 2D quantum (no sign problem) | QMC | iPEPS, DMRG on cylinders | ED (too small) |
| 2D quantum (sign problem) | DMFT, iPEPS | Constrained-path QMC | Standard QMC |
| Molecular ground state | CCSD(T) | DFT (larger systems) | Hartree-Fock alone |
| Strongly correlated lattice | DMFT, DMRG | Cluster extensions (DCA, CDMFT) | RPA, perturbation theory |
| Phase transition (d < d_c) | RG / scaling | QMC + finite-size scaling | Mean-field exponents |
| Phase transition (d >= d_c) | Mean-field / Landau | Ginzburg criterion check | Ignoring fluctuations near T_c |
| Dilute quantum gas | Gross-Pitaevskii / Bogoliubov | QMC (benchmarking) | Full many-body for N > 10^4 |
| Nuclear structure | Shell model / DFT | Ab initio (light nuclei) | Naive perturbation theory |
| Molecular/solid excitations | TDDFT (adiabatic LDA/GGA) | BSE (GW+BSE for accurate exciton binding) | CIS, raw DFT eigenvalue differences |
| Turbulence | DNS (small Re) | LES (large Re) | RANS for detailed flow structure |

**See also:** `../planning/planner-approximations.md` — how the planner tracks approximation choices and validity ranges throughout a research plan.

</quick_reference>
