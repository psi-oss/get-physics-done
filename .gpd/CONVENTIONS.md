# Conventions: Lattice N=4 SYM Orbifold Daughter — Witten Index

**Established:** 2026-03-13
**Primary references:** CKKU (Cohen-Kaplan-Katz-Unsal, hep-lat/0302017), Catterall (hep-lat/0503036, 0811.1203)

## Unit System

- **Lattice units:** a = 1 (lattice spacing), hbar = 1, c = 1
- All dimensionful quantities in units of lattice spacing

## Spacetime and Metric

- **Dimension:** d = 4 Euclidean
- **Metric:** delta_{mu,nu} (flat Euclidean, no Lorentzian signature)
- **Lattice type:** A_4^* body-centered hypercubic lattice (5 links per site, sum_a e_a = 0)
- **Topology:** Torus L^4 with periodic boundary conditions

## Gauge Group

- **Parent theory:** SU(kN) = SU(6) for k=3, N=2
- **Daughter theory:** SU(N)^k = SU(2)^3 circular quiver with bi-fundamental matter
- **Generator normalization:** Tr(T^a T^b) = (1/2) delta^{ab} (fundamental rep)
- **Structure constants:** [T^a, T^b] = i f^{abc} T^c

## Orbifold Embedding

- **Orbifold group:** Z_3
- **Generator:** gamma = diag(1, omega, omega^2) tensor I_2 where omega = e^{2*pi*i/3}
- **Projection:** Fields X -> gamma X gamma^{-1}; diagonal blocks = gauge, off-diagonal = bi-fundamentals

## Twisted Field Content (Catterall formulation)

| Field | Type | Form degree | Lattice location |
|-------|------|-------------|-----------------|
| eta | Scalar fermion | 0-form | Sites |
| psi_a (a=1..5) | Vector fermion | 1-form | Links |
| chi_{ab} | Tensor fermion (self-dual) | 2-form | Faces |
| U_a (a=1..5) | Complexified gauge link | 1-form | Links |
| d | Auxiliary scalar | 0-form | Sites |

- **16 bosonic + 16 fermionic** real d.o.f. per site per color (matching N=4 SUSY)

## Gauge Link Variables

- U_a(n) in GL(N,C) — **complexified, NOT unitary**
- U_a_bar(n) is **independent** of U_a(n)^dagger (holomorphicity of Q-exact action)
- Unitarity restores dynamically in continuum limit

## Lattice Action

- **S = Q * Lambda** (Q-exact) where Q is the nilpotent scalar supercharge
- **Q^2 = 0** (exact on lattice, off-shell)
- S_B >= 0 (positive semi-definite bosonic action)
- **Euclidean weight:** Z = integral DU D(Psi) exp(-S)

## Coupling Convention

- **'t Hooft coupling:** lambda = g^2 N
- **Lattice coupling:** lambda_lat = g^2 N (dimensionless in 4D with a=1 since g is dimensionless in 4D)
- **Action prefactor:** N/lambda_lat
- **Weak coupling:** lambda_lat -> 0; strong coupling: lambda_lat -> infinity

## Fermion Conventions

- **Grassmann integration:** Berezin: integral d(theta) theta = 1
- **Fermion bilinear:** S_F = Psi^T M Psi with M antisymmetric (M^T = -M)
- **Fermion measure:** integral D[Psi] exp(-Psi^T M Psi) = Pf(M)

## Pfaffian Convention

- Pf(M) with Pf(M)^2 = det(M)
- **Phase:** Pf(M) = |Pf(M)| * exp(i*alpha)
- **Computation:** Parlett-Reid tridiagonalization (Wimmer algorithm) for exact evaluation
- **Monte Carlo:** Phase-reweighting: sample |Pf(M)|^2 * exp(-S_B), reweight by exp(i*alpha)

## Boundary Conditions

- **Witten index:** Periodic for ALL fields (bosonic AND fermionic) in ALL directions
- **Thermal partition function** (NOT used): anti-periodic fermions in temporal direction
- **Flat direction lifting:** Soft SUSY-breaking mass mu^2 with mu -> 0 extrapolation

## Witten Index

- **Definition:** I_W = Tr[(-1)^F e^{-beta H}] (beta-independent for gapped theories)
- **Lattice computation:** W = Pf(M_PBC) / Pf(M_APBC) via boundary condition ratio
- **Expected:** Integer; for parent SU(N) N=4 SYM, I_W = N on R^3 x S^1

## Convention Warnings

- **SU(N) vs U(N):** This project uses SU(N). Some references (Kanamori-Suzuki) use U(N) — Witten index differs.
- **Action prefactor:** Catterall uses N/lambda_lat; some papers use 1/g^2 (differs by factor N).
- **Twisted field notation:** Catterall notation (eta, psi_a, chi_{ab}) used throughout. Other groups use different letters.

---

_Established: 2026-03-13_
