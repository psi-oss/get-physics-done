---
load_when:
  - "atomic physics"
  - "molecular physics"
  - "optical physics"
  - "AMO"
  - "cold atoms"
  - "laser"
  - "Rabi oscillation"
  - "Feshbach resonance"
tier: 2
context_cost: medium
---

# Atomic, Molecular, and Optical (AMO) Physics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/perturbation-theory.md` (time-dependent perturbation theory, Fermi's golden rule), `references/protocols/electrodynamics.md` (light-matter interaction, selection rules), `references/protocols/scattering-theory.md` (partial waves, Born approximation, resonances), `references/protocols/numerical-computation.md` (general numerical methods), `references/protocols/variational-methods.md` (Hartree-Fock, configuration interaction, DMRG for ultracold atoms), `references/protocols/group-theory.md` (angular momentum coupling, Wigner-Eckart theorem, selection rules), `references/protocols/wkb-semiclassical.md` (tunneling, Bohr-Sommerfeld, semiclassical dynamics), `references/protocols/green-functions.md` (retarded propagators, spectral functions, Dyson equation).

**Scattering Theory:**

- Born approximation: f(theta) = -(m/(2*pi*hbar^2)) _ integral V(r') _ exp(-i*q*r') d^3r' (first order; valid for weak potentials or high energy)
- Partial wave expansion: f(theta) = sum_l (2l+1) * f_l * P_l(cos(theta)); f_l = (exp(2*i*delta_l) - 1) / (2ik)
- Phase shifts delta_l: encode all scattering information for central potentials
- S-matrix: S_l = exp(2*i*delta_l); unitarity requires |S_l| = 1 for elastic scattering
- T-matrix: relates to scattering amplitude; Lippmann-Schwinger equation T = V + V*G_0*T
- Feshbach resonances: coupling between open and closed channels; scattering length a(B) = a_bg \* (1 - Delta/(B - B_0)); critical for cold atom experiments

**Optical Bloch Equations:**

- Two-level atom in classical field: coupled equations for density matrix elements
- Rabi oscillations: population oscillates at frequency Omega_R = d\*E_0/hbar (on resonance)
- Optical Bloch equations: d(rho)/dt = -(i/hbar)[H, rho] + L[rho]; include spontaneous emission via Lindblad
- Steady state: rho_ee = (s/2) / (1 + s + (2\*Delta/Gamma)^2) where s = I/I_sat is saturation parameter
- Bloch sphere representation: pure state on surface; mixed states inside; T1 and T2 relaxation

**Master Equations (Open Quantum Systems):**

- Lindblad form: d(rho)/dt = -i[H, rho] + sum_k (L_k rho L_k^dag - (1/2){L_k^dag L_k, rho})
- Markov approximation: environment correlation time << system timescale; memoryless bath
- Quantum jump / Monte Carlo wavefunction method: stochastic unraveling of master equation; efficient for large Hilbert spaces
- Redfield equation: weakly coupled system-bath; can violate positivity (careful with secular approximation)
- Non-Markovian dynamics: HEOM (hierarchical equations of motion), process tensor, reaction coordinate methods

**Semiclassical Methods:**

- WKB approximation: valid when de Broglie wavelength varies slowly; quantization: integral p dx = (n + 1/2) \* h
- Eikonal approximation: high-energy scattering; phase accumulated along classical trajectory
- Maslov index: correction at classical turning points; important for tunneling calculations
- Semiclassical propagator (Van Vleck): K(x_f, x_i; t) = sum over classical paths with amplitude and phase

**Cold Atoms and BEC:**

- Gross-Pitaevskii equation: i*hbar * d(psi)/dt = (-hbar^2/(2m) _ nabla^2 + V_ext + g_|psi|^2) \* psi; mean-field for BEC
- Interaction parameter: g = 4*pi*hbar^2\*a/m where a is s-wave scattering length
- Thomas-Fermi limit: large N; kinetic energy negligible; density profile n(r) = (mu - V(r))/g for mu > V
- Bogoliubov theory: excitations above BEC; phonon-like at long wavelength (speed of sound c = sqrt(g\*n/m))
- Optical lattices: periodic potential from standing laser waves; realizes Hubbard models; Mott insulator transition

**Quantum Optics:**

- Jaynes-Cummings model: single atom in single-mode cavity; vacuum Rabi splitting g = d*sqrt(omega/(2*epsilon_0*hbar*V))
- Cavity QED: strong coupling (g > kappa, gamma); Purcell effect in weak coupling
- Photon statistics: g^(2)(0) < 1 (antibunching, single-photon source); g^(2)(0) > 1 (bunching, thermal light); g^(2)(0) = 1 (coherent)
- Squeezed states: reduced noise in one quadrature below vacuum level; enhanced metrology

## Key Tools and Software

| Tool                                | Purpose                                       | Notes                                                                       |
| ----------------------------------- | --------------------------------------------- | --------------------------------------------------------------------------- |
| **QuTiP**                           | Open quantum systems                          | Master equation, Monte Carlo, Floquet theory; Python                        |
| **Molpro / ORCA / Gaussian**        | Molecular electronic structure                | CI, CC, DFT for molecules; scattering potentials                            |
| **Cowan's code (RCN/RCG)**          | Atomic structure                              | Hartree-Fock with relativistic corrections; energy levels, transition rates |
| **GRASP**                           | General-purpose Relativistic Atomic Structure | Multi-configuration Dirac-Hartree-Fock                                      |
| **MESA / BSR**                      | Electron-atom scattering                      | R-matrix method; photoionization                                            |
| **GPELab**                          | Gross-Pitaevskii equation solver              | MATLAB; 1D/2D/3D; rotating BEC; multi-component                             |
| **XMDS2**                           | PDE solver for quantum field simulations      | Stochastic PDE; truncated Wigner; c-field methods                           |
| **QuantumOptics.jl**                | Quantum optics (Julia)                        | Lindblad, MCWF, semiclassical; modern and fast                              |
| **Strawberry Fields**               | Photonic quantum computing                    | Gaussian/Fock state manipulation                                            |
| **ARC (Alkali Rydberg Calculator)** | Rydberg atom properties                       | Energy levels, dipole matrix elements, Stark maps                           |
| **NIST ASD**                        | Atomic Spectra Database                       | Energy levels, wavelengths, transition probabilities                        |

## Validation Strategies

**Optical Theorem:**

- sigma_total = (4*pi/k) * Im[f(theta=0)] (forward scattering amplitude)
- Relates total cross section to imaginary part of forward amplitude
- Check: computed total cross section from partial wave sum must agree with optical theorem
- Generalization: unitarity of S-matrix implies sum of partial cross sections equals total

**Detailed Balance:**

- Rate(A -> B) _ P_eq(A) = Rate(B -> A) _ P_eq(B) in thermal equilibrium
- For optical transitions: Einstein A and B coefficients related by A = (8*pi*h*nu^3/c^3) * B
- For scattering: principle of microreversibility (time-reversal invariance); d_sigma/d_Omega(A->B) * k_A^2 = d_sigma/d_Omega(B->A) * k_B^2

**Thomas-Reiche-Kuhn Sum Rule:**

- sum_n f_n = Z (number of electrons); oscillator strengths sum to electron count
- f_n = (2*m*omega_n / hbar) \* |<n|x|0>|^2
- Check: computed oscillator strengths must sum to number of active electrons

**Kramers-Kronig Relations:**

- Relate real and imaginary parts of susceptibility: Re[chi(omega)] = (1/pi) _ P _ integral Im[chi(omega')] / (omega' - omega) d\*omega'
- Check: computed absorption spectrum (Im[chi]) and refractive index (Re[chi]) must satisfy KK relations

**Kato Cusp Condition:**

- Electron-nucleus wavefunction has a cusp at r = 0: d(psi)/dr|\_{r=0} / psi(0) = -Z/a_0
- For electron-electron: cusp condition with Z -> -1/2
- Check: many-body wavefunctions (VMC trial functions) must satisfy cusp conditions

## Common Pitfalls

- **Rotating wave approximation (RWA) breakdown:** RWA fails when Rabi frequency approaches or exceeds transition frequency; ultrastrong coupling regime requires full treatment
- **Confusing scattering length and cross section:** sigma = 4*pi*a^2 (identical bosons) vs sigma = 8*pi*a^2 (distinguishable particles) vs sigma = 4*pi*a^2 unitarity-limited at threshold. Factor-of-2 errors are epidemic
- **Neglecting light shifts in driven systems:** AC Stark shifts from off-resonant driving; can dominate dynamics in optical lattices
- **Markov approximation for structured reservoirs:** Non-Markovian effects important for photonic crystals, phonon baths at low temperature, and strong coupling to environment
- **Missing dipole selection rules:** Electric dipole transitions require Delta_l = +/-1, Delta_m = 0, +/-1. Forbidden transitions may still occur via magnetic dipole, electric quadrupole, or two-photon processes
- **Ignoring Doppler and recoil effects:** Laser cooling and trapping require accounting for recoil momentum hbar*k and Doppler shifts k*v. Recoil limit T_r = (hbar*k)^2 / (m*k_B)
- **Incorrect basis for angular momentum coupling:** j-j coupling vs LS coupling; intermediate coupling requires full diagonalization. Light atoms (Z < 30): LS coupling. Heavy atoms: j-j coupling. Between: neither is good

---

## Research Frontiers (2024-2026)

| Frontier | Key question | GPD suitability |
|----------|-------------|-----------------|
| **Optical clocks** | 10^{-19} fractional uncertainty; test GR, search for dark matter | Good — precision spectroscopy calculations |
| **Quantum simulation with cold atoms** | Programmable Hubbard models, gauge theories on optical lattices | Good — model Hamiltonian analysis |
| **Rydberg arrays** | Neutral atom quantum computing, many-body entanglement | Excellent — Rydberg interaction calculations |
| **Ultrastrong light-matter coupling** | Breakdown of RWA, vacuum physics, polariton chemistry | Good — full Jaynes-Cummings beyond RWA |
| **Attosecond science** | Electron dynamics on natural timescale, photoionization delays | Moderate — TDSE + strong-field approximation |
| **Precision tests of QED** | Hydrogen Lamb shift, muonic hydrogen, g-2 of bound electron | Excellent — multi-loop bound-state QED |

## Methodology Decision Tree

```
What system?
├── Few-electron atoms
│   ├── Hydrogen-like? → Exact solutions + QED corrections (Lamb shift)
│   ├── Helium-like? → Hylleraas variational or CI with large basis
│   └── Alkali (one valence)? → Model potential + core polarization (or MBPT)
├── Many-electron atoms
│   ├── Low Z? → MCHF (multi-configuration Hartree-Fock)
│   ├── High Z? → MCDHF (relativistic, GRASP code)
│   └── Highly charged ions? → Relativistic CI or MBPT
├── Atom-light interaction
│   ├── Weak field, near-resonance? → Optical Bloch equations (RWA)
│   ├── Strong field? → Floquet theory or full numerical propagation
│   └── Ultrastrong coupling? → Full Rabi model (no RWA), polaron transforms
├── Scattering
│   ├── Low energy? → Partial wave expansion, scattering length
│   ├── Resonances? → R-matrix or close-coupling
│   └── Ionization? → Time-dependent close-coupling or exterior complex scaling
└── Quantum optics
    ├── Few photons? → Jaynes-Cummings, dressed states
    ├── Open system? → Lindblad master equation (QuTiP)
    └── Non-Markovian? → HEOM, process tensor, or polaron master equation
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One atomic system, one observable, full calculation with validation | "Blackbody radiation shift of the Sr optical clock transition" |
| **Postdoc** | Multi-system comparison or new computational method | "Non-Markovian dynamics of a quantum emitter coupled to a photonic crystal waveguide" |
| **Faculty** | New measurement technique, precision test, or many-body quantum simulation | "Analog quantum simulation of lattice gauge theories with Rydberg atoms"
