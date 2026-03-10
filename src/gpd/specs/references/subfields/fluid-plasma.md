---
load_when:
  - "fluid dynamics"
  - "Navier-Stokes"
  - "MHD"
  - "magnetohydrodynamics"
  - "plasma"
  - "turbulence"
  - "Reynolds number"
tier: 2
context_cost: medium
---

# Fluid Dynamics and Plasma Physics

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/fluid-dynamics-mhd.md` (regime identification, governing equations, turbulence, MHD checks), `references/protocols/numerical-computation.md` (CFD methods, convergence testing), `references/protocols/stochastic-processes.md` (turbulence models, Langevin approaches), `references/protocols/non-equilibrium-transport.md` (transport coefficients, Kubo formulae for viscosity and conductivity), `references/protocols/molecular-dynamics.md` (particle-in-cell methods, kinetic simulations), `references/protocols/order-of-limits.md` (ideal vs resistive limits, incompressible limit), `references/protocols/kinetic-theory.md` (Boltzmann equation, Chapman-Enskog, transport coefficients from first principles). For verification formulas: `references/verification/domains/verification-domain-fluid-plasma.md` (MHD equilibrium, Alfven waves, reconnection, conservation laws).

**Navier-Stokes Equations:**

- Incompressible: rho _ (du/dt + u . grad u) = -grad P + mu _ nabla^2 u + f; div u = 0
- Compressible: conservation form for mass, momentum, energy with equation of state
- Reynolds number: Re = U\*L/nu; laminar (Re < ~2000 for pipe), turbulent (Re >> 1)
- Dimensionless groups: Re (inertia/viscosity), Ma (flow/sound speed), Pr (viscous/thermal diffusion), Ra (buoyancy/diffusion)

**Magnetohydrodynamics (MHD):**

- Ideal MHD: d(rho)/dt + div(rho*u) = 0; rho*(du/dt) = -grad P + (J x B); dB/dt = curl(u x B)
- Resistive MHD: adds eta*nabla^2 B term; magnetic Reynolds number Rm = U*L/eta
- Alfven wave: v_A = B/sqrt(mu_0\*rho); propagates along field lines
- Magnetic reconnection: topology change of field lines; Sweet-Parker rate ~ Rm^{-1/2}, Petschek rate ~ 1/ln(Rm)
- MHD stability: Rayleigh-Taylor, Kelvin-Helmholtz, kink, sausage modes; energy principle

**Turbulence:**

- **Kolmogorov theory (K41):** E(k) ~ epsilon^{2/3} \* k^{-5/3} in inertial range; energy cascades from large to small scales
- **Direct Numerical Simulation (DNS):** Resolve all scales from integral to Kolmogorov; N ~ Re^{9/4} grid points in 3D
- **Large Eddy Simulation (LES):** Resolve large scales; model sub-grid stress (Smagorinsky, dynamic, etc.)
- **Reynolds-Averaged Navier-Stokes (RANS):** Time-average; model Reynolds stress tensor; k-epsilon, k-omega SST models
- **Intermittency:** Deviations from K41; structure function exponents zeta_p != p/3; multifractal models

**Spectral Methods:**

- Expand in orthogonal basis (Fourier for periodic, Chebyshev for bounded domains)
- Pseudo-spectral: evaluate nonlinear terms in physical space, linear terms in spectral space; dealiasing (2/3 rule or padding)
- Exponential convergence for smooth solutions; Gibbs phenomenon for discontinuities
- Time integration: semi-implicit (implicit for diffusion, explicit for advection); typical: IMEX-RK or CNAB

**Lattice Boltzmann Method (LBM):**

- Mesoscopic: evolve distribution functions f_i(x, t) on discrete velocity lattice
- Collision operator: BGK (single relaxation time) or MRT (multiple relaxation times)
- Recovers Navier-Stokes in the hydrodynamic limit via Chapman-Enskog expansion
- Naturally handles complex geometries, multiphase flows, porous media
- Parallelizes well; local operations only

**Plasma Kinetics:**

- Vlasov equation: df/dt + v . df/dx + (q/m)\*(E + v x B) . df/dv = 0 (collisionless)
- Particle-in-Cell (PIC): sample distribution with macro-particles; solve fields on grid
- Fokker-Planck: includes collisional diffusion in velocity space; Landau operator
- Gyrokinetics: average over fast cyclotron motion; reduces 6D to 5D; standard for fusion

## Key Tools and Software

| Tool                       | Purpose                          | Notes                                                                 |
| -------------------------- | -------------------------------- | --------------------------------------------------------------------- |
| **OpenFOAM**               | General CFD (finite volume)      | Open-source; incompressible/compressible; turbulence models           |
| **Nek5000 / NekRS**        | Spectral element CFD             | High-order; DNS and LES; GPU-accelerated (NekRS)                      |
| **Dedalus**                | Spectral PDE solver              | Python; flexible; ideal for DNS of custom equations                   |
| **Athena++**               | Astrophysical MHD                | AMR; Riemann solvers; relativistic MHD option                         |
| **FLASH**                  | Multi-physics AMR code           | MHD, radiation, nuclear burning; astrophysical flows                  |
| **Pencil Code**            | High-order finite-difference MHD | DNS; astrophysical applications; particles                            |
| **BOUT++**                 | Plasma edge simulation           | Field-aligned coordinates; tokamak edge turbulence                    |
| **GENE**                   | Gyrokinetic turbulence           | Flux-tube and global; standard for fusion micro-turbulence            |
| **OSIRIS / EPOCH / WarpX** | PIC codes                        | Laser-plasma interaction, particle acceleration; WarpX is GPU-enabled |
| **Palabos**                | Lattice Boltzmann                | Open-source; 2D/3D; parallelized                                      |
| **waLBerla**               | High-performance LBM             | Scalable; GPU-enabled; complex geometries                             |
| **FEniCS**                 | Finite element PDE solver        | General; Stokes, Navier-Stokes; Python/C++                            |
| **Firedrake**              | Finite element (Python)          | Composable; multigrid; variational formulations                       |
| **ParaView / VisIt**       | Visualization                    | 3D visualization; parallel; standard for CFD                          |

## Validation Strategies

**Reynolds Number Scaling:**

- Laminar pipe flow: friction factor f = 64/Re (Hagen-Poiseuille)
- Turbulent: Moody chart; Colebrook equation for rough pipes
- Drag on sphere: C_D ~ 24/Re (Stokes), C_D ~ 0.44 (turbulent, Re ~ 10^3-10^5)
- Check: computed drag/friction must follow known scaling laws

**Energy Cascade:**

- Kolmogorov spectrum: E(k) = C_K * epsilon^{2/3} \_ k^{-5/3}; C_K ~ 1.5 (Kolmogorov constant)
- Dissipation scale: eta = (nu^3 / epsilon)^{1/4}; grid must resolve down to ~eta for DNS
- Energy dissipation rate: epsilon = nu \* <|grad u|^2>; should match energy injection rate in stationary turbulence
- Check: energy spectrum slope in inertial range; dissipation balance

**Conservation in Ideal Systems:**

- Euler equations conserve: kinetic energy (in 2D, enstrophy too), helicity (in 3D)
- Ideal MHD conserves: energy, cross-helicity, magnetic helicity
- Check: monitor conserved quantities; drift indicates numerical error

**Exact Solutions:**

- Couette flow: linear velocity profile for plane Couette
- Poiseuille flow: parabolic profile; u(r) = (dP/dx) * (R^2 - r^2) / (4*mu)
- Stokes flow past sphere: drag F = 6*pi*mu*R*U
- Taylor-Green vortex: known initial-value problem with analytical short-time solution; standard DNS benchmark
- Orszag-Tang vortex: standard 2D MHD benchmark; develops current sheets

**CFL Condition:**

- Courant number: C = (u + c) \* dt/dx <= C_max (scheme-dependent; C_max = 1 for explicit)
- Check: time step satisfies CFL constraint for stability
- For diffusion: von Neumann number D\*dt/dx^2 <= 1/2 (1D, explicit)

## Common Pitfalls

- **Under-resolving turbulence:** DNS requires grid spacing ~ Kolmogorov scale; for LES, sub-grid model quality matters. Under-resolved simulations produce wrong statistics
- **Numerical dissipation masking physical dissipation:** Low-order schemes (first-order upwind) add artificial viscosity that can dominate physical viscosity. Use high-order methods or quantify numerical diffusion
- **Pressure-velocity coupling (incompressible):** Naive explicit treatment leads to checkerboard pressure oscillations. Use staggered grids or pressure-correction methods (SIMPLE, Chorin projection)
- **Aliasing errors in spectral methods:** Nonlinear terms generate high-frequency modes that alias to low frequencies. Apply 2/3 dealiasing rule or use padding
- **Magnetic divergence errors:** div(B) = 0 must be maintained numerically. Constrained transport or divergence cleaning (Dedner) methods required; unchecked div(B) causes spurious forces
- **Wrong boundary conditions for turbulence:** Periodic boundaries impose artificial periodicity length scale. Inflow/outflow require careful treatment (convective outflow, sponge layers, recycling)
- **Ignoring compressibility at low Mach number:** Incompressible solvers fail for Ma > ~0.3. Conversely, compressible solvers at low Ma suffer from acoustic CFL constraint (very small time step)
- **Grid-dependent results in RANS:** RANS models have model-form error that cannot be reduced by grid refinement. Always compare with experimental data or DNS for the specific flow configuration

---

## Research Frontiers (2024-2026)

| Frontier | Key question | GPD suitability |
|----------|-------------|-----------------|
| **Turbulence theory** | Universal statistics beyond Kolmogorov 1941, intermittency, anomalous scaling | Good — DNS analysis + field theory |
| **Magnetic reconnection** | Onset mechanism, particle acceleration, plasmoid-mediated fast reconnection | Good — PIC simulations + analytics |
| **Plasma-based accelerators** | Laser/beam-driven wakefield acceleration, energy frontier | Moderate — PIC codes (OSIRIS, WarpX) |
| **Quantum fluids** | Superfluid turbulence, quantum vortex dynamics in BECs and He-II | Good — Gross-Pitaevskii + vortex filament |
| **Active fluids** | Bacterial turbulence, active nematics, odd viscosity | Excellent — continuum theory + simulation |
| **Fusion plasma confinement** | Turbulent transport in tokamaks, gyrokinetic simulations | Moderate — requires gyrokinetic codes |

## Methodology Decision Tree

```
Flow regime?
├── Incompressible (Ma < 0.3)
│   ├── Laminar (Re < ~2000)? → Direct solution of Navier-Stokes
│   ├── Turbulent, DNS feasible (Re < ~10^4)? → Spectral or high-order FD
│   ├── Turbulent, DNS infeasible? → LES (Smagorinsky, dynamic) or RANS
│   └── Free surface? → Level set, VOF, or phase field method
├── Compressible (Ma > 0.3)
│   ├── Smooth flow? → High-order FD or spectral element
│   ├── Shocks? → Godunov-type (HLLC, Roe) or WENO schemes
│   └── Hypersonic? → Real gas effects, chemical kinetics
├── Plasma
│   ├── Collisional (MHD valid)? → Ideal/resistive MHD (Athena, PLUTO)
│   ├── Weakly collisional? → Gyrokinetics (GS2, GENE) or Vlasov
│   └── Kinetic? → Particle-in-cell (OSIRIS, WarpX, EPOCH)
└── Multiphysics
    ├── Radiation + hydro? → Radiation transport (flux-limited diffusion, M1)
    ├── MHD + particles? → Hybrid PIC-MHD
    └── Fluid + structure? → Immersed boundary or ALE methods
```

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | DNS of one flow configuration + scaling analysis | "Energy cascade in 2D turbulence with inverse cascade and condensate" |
| **Postdoc** | New simulation method or multi-physics coupling | "Gyrokinetic simulation of ion-temperature-gradient turbulence in ITER geometry" |
| **Faculty** | Fundamental theory or new paradigm | "Universal intermittency exponents from conformal field theory in 2+1D turbulence"
