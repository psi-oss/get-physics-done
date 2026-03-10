# Subfield Convention Defaults

When establishing conventions for a project, use the subfield (from PROJECT.md `physics_area` or inferred from the problem description) to auto-suggest a complete convention set. These are starting points — the user confirms or overrides.

## How to Use This Table

1. Read `PROJECT.md` and extract the physics subfield
2. Look up the subfield below
3. Pre-populate CONVENTIONS.md with the default choices
4. Present to user: "Based on [subfield], I suggest these conventions. Confirm or override each."
5. For cross-disciplinary projects (e.g., condensed matter + QFT), identify conflicts between default sets and resolve explicitly

## Convention Defaults by Subfield

**Quantum Field Theory (Particle Physics)**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Natural: ℏ = c = 1 | Universal in particle physics |
| Metric signature | (+,−,−,−) (West Coast) | Peskin & Schroeder, Weinberg |
| Fourier convention | Physics: e^{−ikx} forward, dk/(2π) measure | Standard in particle physics |
| Coupling | α = g²/(4π) | Standard QED/QCD convention |
| Covariant derivative | D_μ = ∂_μ + igA_μ | Peskin & Schroeder convention |
| State normalization | Relativistic: ⟨p\|q⟩ = (2π)³ 2E δ³(p−q) | Lorentz-invariant phase space |
| Spinor convention | Dirac (Peskin & Schroeder) | {γ^μ, γ^ν} = 2g^{μν} |
| Renormalization | MS-bar | Default for perturbative QCD |
| Gamma matrices | Dirac basis (P&S Ch. 3) | γ^0 = diag(1,1,−1,−1) |

**String Theory**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Natural: hbar = c = 1; keep `alpha'` explicit until fixed | Avoids hiding the string scale |
| String tension | `T = 1/(2*pi*alpha')` | Standard Polyakov/Polchinski normalization |
| Expansion parameters | Track `alpha'` and `g_s` separately | Derivative corrections and genus expansion are different approximations |
| Spacetime signature | Mostly minus Lorentzian for target space; Wick rotate worldsheet when using Euclidean CFT/path integrals | Standard split between target-space and worldsheet calculations |
| Worldsheet gauge | Conformal gauge unless otherwise stated | Default in perturbative worldsheet computations |
| Physical state condition | BRST cohomology (or equivalent Virasoro constraints in older notation) | Modern consistency language |
| Compactification hierarchy | Keep `M_KK`, `M_s`, and low-energy EFT scale explicit | Needed for controlled dimensional reduction |
| Duality language | State exactly which duality is used (T, S, U, mirror, AdS/CFT) and what is matched | Prevents slogan-level "duality" claims |

**Condensed Matter (Analytical)**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | SI with explicit ℏ, k_B | Standard in CM literature |
| Lattice convention | Site labeling i,j; lattice constant a | Standard |
| Brillouin zone | First BZ; high-symmetry points (Γ, X, M, K) | Setyawan & Curtarolo notation |
| Band structure | E(k) with k in inverse length | Standard |
| Fourier convention | Condensed matter: f_k = (1/√N) Σ_j f_j e^{ikR_j} | Symmetric normalization over N sites |
| Green's function | Retarded: G^R(ω) = ⟨⟨A; B⟩⟩_{ω+iη} | Zubarev convention |
| Spin operators | S = (ℏ/2)σ with σ Pauli matrices | Standard |
| Temperature | k_B T explicit (or set k_B = 1 and state it) | Avoid silent k_B=1 |
| Electron charge | e > 0 (electron has charge −e) | Standard convention |

**General Relativity**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Geometrized: G = c = 1 | Standard in GR |
| Metric signature | (−,+,+,+) (East Coast / MTW) | Misner-Thorne-Wheeler, Wald |
| Index convention | Greek μ,ν = 0,...,3 (spacetime); Latin i,j = 1,...,3 (spatial) | Universal |
| Riemann tensor | R^ρ_{σμν} = ∂_μΓ^ρ_{νσ} − ∂_νΓ^ρ_{μσ} + ... | MTW sign convention |
| Ricci tensor | R_{μν} = R^ρ_{μρν} (contraction on 1st and 3rd) | MTW convention |
| Einstein equation | G_{μν} = 8πT_{μν} | With G = c = 1 |
| Covariant derivative | ∇_μ V^ν = ∂_μ V^ν + Γ^ν_{μρ} V^ρ | Standard |
| ADM decomposition | ds² = −α²dt² + γ_{ij}(dx^i + β^i dt)(dx^j + β^j dt) | MTW/York convention |

**Statistical Mechanics**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | k_B = 1 (temperature in energy units) | Standard in theory |
| Partition function | Z = Σ_n e^{−βE_n}, β = 1/T | Canonical ensemble |
| Free energy | F = −T ln Z | Helmholtz |
| Entropy | S = −∂F/∂T = −Σ_n p_n ln p_n | Gibbs entropy |
| Ising convention | H = −J Σ_{⟨ij⟩} s_i s_j, J > 0 ferromagnetic | Standard; note some refs use +J |
| Transfer matrix | T_{s,s'} = e^{−βH(s,s')} | Row-to-row transfer |
| Correlation function | ⟨s_i s_j⟩ − ⟨s_i⟩⟨s_j⟩ for connected | Standard |
| Critical exponents | α, β, γ, δ, ν, η per Fisher convention | Standard notation |

**AMO (Atomic, Molecular, Optical)**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Atomic units: ℏ = m_e = e = 4πε₀ = 1 | Standard in AMO |
| Energy unit | Hartree (E_h = 27.211 eV) or eV | Context-dependent |
| Light-matter coupling | Electric dipole: H_int = −d·E (length gauge) | Standard starting point |
| Rotating frame | ψ̃ = e^{iωt} ψ for near-resonant interactions | Standard RWA setup |
| Angular momentum | J = L + S, with standard Clebsch-Gordan conventions (Condon-Shortley phase) | Standard |
| Dipole matrix element | d_{if} = ⟨f|er|i⟩ (not ⟨i|er|f⟩) | Matches transition i→f |
| Rabi frequency | Ω = d·E₀/ℏ | Standard |
| Detuning | Δ = ω_laser − ω_atom | Positive = blue-detuned |

**Quantum Information / Quantum Computing**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Dimensionless (ℏ = 1, energies in Hz or rad/s) | Standard in QI |
| State notation | \|0⟩, \|1⟩ computational basis | Standard |
| Density matrix | ρ = Σ_i p_i \|ψ_i⟩⟨ψ_i\| | Standard |
| Entanglement | Von Neumann entropy S = −Tr(ρ log₂ ρ) | Standard; note log base |
| Gate convention | U\|ψ⟩ (left multiplication) | Standard |

**Soft Matter / Polymer Physics**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | SI (with nm, μm length scales) | Standard in soft matter |
| Temperature | k_B T as energy unit | Thermal energy scale |
| Polymer | N = degree of polymerization, b = Kuhn length | Standard |
| Correlation function | S(q) = (1/N) Σ_{ij} ⟨e^{iq·(r_i − r_j)}⟩ | Structure factor |
| Viscosity | η in Pa·s | SI standard |

**Fluid Dynamics / Plasma Physics**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | CGS-Gaussian for plasma; SI for hydrodynamics | Traditional in plasma physics (Freidberg, Boyd & Sanderson); SI for engineering fluids |
| Magnetic field | B in Gauss (CGS) or Tesla (SI) | Magnetic pressure: B²/(8π) in CGS, B²/(2μ₀) in SI |
| Velocity normalization | Alfven units: v_A = B/√(4πρ) = 1 | Non-dimensionalizes MHD equations cleanly |
| Length scale | System size L, ion skin depth d_i, or Debye length λ_D | Depends on regime: MHD (L), Hall MHD (d_i), kinetic (λ_D) |
| Time scale | Alfven time t_A = L/v_A | Natural for MHD dynamics |
| Plasma beta | β = 8πp/B² (CGS) or β = 2μ₀p/B² (SI) | High-β: pressure-dominated; low-β: magnetically dominated |
| Equation of state | Ideal gas with γ = 5/3 | Monatomic gas default; isothermal γ = 1 if specified |
| Reynolds numbers | Re = vL/ν, Rm = vL/η, S = v_A·L/η | Fluid, magnetic, and Lundquist numbers |
| Resistivity | Spitzer (collisional) or uniform η | State explicitly; anomalous only if justified |

**Astrophysics / Stellar Physics**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | CGS (cm, g, s, erg) | Traditional in stellar astrophysics |
| Solar units | M☉ = 1.989×10³³ g, R☉ = 6.957×10¹⁰ cm, L☉ = 3.828×10³³ erg/s | IAU 2015 nominal values |
| Abundances | Mass fractions X (H), Y (He), Z (metals) | Standard; or [Fe/H] for metallicity |
| Solar composition | Asplund et al. 2009: X=0.7381, Y=0.2485, Z=0.0134 | Current standard; note older GS98 gives Z=0.017 |
| Magnitude system | AB magnitudes unless stated otherwise | Specify AB vs Vega explicitly |
| Opacity | Rosseland mean κ in cm²/g | For diffusion approximation; Planck mean for optically thin |
| Nuclear rates | JINA REACLIB or NACRE II compilation | Cite specific compilation version |
| Mixing length | α_MLT = 1.82 (solar calibrated) | State calibration source; varies with EOS/opacity |
| Convection criterion | Schwarzschild: ∇_rad > ∇_ad → convective | Ledoux if composition gradients matter |

**Mathematical Physics**

| Category | Default | Rationale |
|----------|---------|-----------|
| Function spaces | L²(Ω) with Lebesgue measure | Standard Hilbert space; specify Ω and measure |
| Inner product | ⟨f,g⟩ = ∫ f*(x)g(x)dx | Physics convention (conjugate-linear in 1st argument) |
| Fourier transform | f̂(k) = ∫ f(x)e^{−ikx}dx | Physics convention; state if using symmetric (2π)^{−d/2} |
| Operator domains | D(A) explicitly stated | Required for unbounded operators; cite self-adjointness proof |
| Asymptotic notation | f ~ g means f/g → 1; f = O(g) means \|f/g\| bounded | Bachmann-Landau; always specify limit point |
| Branch cuts | log(z): cut along (−∞, 0] | Principal branch default; document any departure |
| Summation | Einstein convention for repeated indices | State explicitly; identify which indices are summed |
| Boundary conditions | Dirichlet, Neumann, or Robin — state regularity | Specify data regularity (H^{1/2}, L², etc.) |

**Algebraic Quantum Field Theory**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Natural: `c = ħ = 1` | Standard relativistic-QFT normalization |
| Metric signature | `(+,−,−,−)` unless another convention is stated explicitly | Matches mainstream AQFT/QFT operator-algebra literature |
| Fourier convention | Physics: `e^{−ikx}` forward, `dk/(2π)` measure | Standard for operator-valued distributions when transforms are needed |
| State normalization | Relativistic | Keeps compatibility with vacuum and spectral-condition statements |
| Algebraic level | Start with a Haag-Kastler C*-net and specify the von Neumann completion in a chosen GNS representation | Factor type and modular theory are representation-dependent |
| Reference state | Vacuum GNS representation unless thermal or charged sectors are the object of study | Prevents drifting between incompatible representations |
| Region class | Double cones for local observables; wedges only when modular-flow arguments require them | Distinguishes local and modular benchmark settings |
| Type language | State explicitly: factor, type `I/II/III`, `III_lambda`, hyperfinite/injective status | Prevents slogan-level "type III" claims |

**String Field Theory**

| Category | Default | Rationale |
|----------|---------|-----------|
| Units | Natural: `c = ħ = 1`; state explicitly whether `alpha' = 1` or `alpha' = 2` | Both conventions are common and materially different |
| Target-space metric | `(+,−,−,−)` for spacetime observables; worldsheet Euclidean after Wick rotation | Keeps target-space and worldsheet roles distinct |
| Fourier convention | Physics: `e^{−ikx}` forward, `dk/(2π)` measure | Standard when extracting spacetime fields and amplitudes |
| Hilbert space | State explicitly: small or large Hilbert space | Superstring formulations are not interchangeable across this choice |
| Ghost number | Open bosonic field usually ghost number `1`; closed bosonic field ghost number `2` | Canonical covariant SFT assignments |
| Picture number | State sector-by-sector (NS/R) and formulation explicitly | Superstring consistency depends on it |
| BPZ / reality | BPZ inner product and reality condition written explicitly | Needed for cyclicity and gauge invariance |
| Gauge choice | Siegel gauge for level truncation unless another gauge is justified | Standard numerical starting point |
| Closed-string constraints | State whether `b_0^- = 0`, `L_0^- = 0`, and level matching are imposed | Required for closed-string fields and vertices |
