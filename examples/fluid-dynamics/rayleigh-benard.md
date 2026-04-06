# Rayleigh-Benard Convection: Linear Stability Analysis

## Problem Statement

A horizontal fluid layer heated from below (Rayleigh-Benard convection) is one of the classic instability problems in fluid dynamics. Below a critical Rayleigh number Ra_c, heat transfer occurs purely by conduction. Above Ra_c, the conductive state becomes unstable and convection rolls form spontaneously.

**Goal:** Derive the critical Rayleigh number Ra_c = 27 pi^4 / 4 ~ 657.5 for the case of two free (stress-free) boundaries using linear stability analysis of the Boussinesq equations. Determine the critical wavenumber and compare with the rigid-boundary result.

## GPD Workflow

### Step 1: Initialize project and lock conventions

```
/gpd:new-project
> Linear stability analysis of Rayleigh-Benard convection.
> Derive the critical Rayleigh number for stress-free boundaries
> from the Boussinesq equations. Compare with rigid boundaries.
```

**Convention lock:**

| Convention | Choice |
|------------|--------|
| Geometry | Fluid layer of depth d, heated from below (z = 0 hot, z = d cold) |
| Boussinesq approximation | Density variations only in buoyancy term: rho = rho_0 (1 - alpha Delta T) |
| Rayleigh number | Ra = g alpha Delta T d^3 / (nu kappa) |
| Prandtl number | Pr = nu / kappa |
| Boundary conditions | Stress-free: w = 0, d^2 w/dz^2 = 0, theta = 0 at z = 0 and z = d |
| Non-dimensionalization | Length: d, Time: d^2/kappa, Temperature: Delta T |

### Step 2: Write the linearized Boussinesq equations

```
/gpd:derive-equation
> Linearize the Boussinesq equations about the conductive
> base state and derive the perturbation equations.
```

**Base state:** The conductive solution has T_0(z) = T_hot - (Delta T / d) z (linear temperature profile), with no fluid motion (u_0 = 0).

**Perturbation:** Write T = T_0(z) + theta(x, y, z, t) and u = u_perturbation. The linearized Boussinesq equations (in non-dimensional form) are:

```
(1/Pr) * d(u)/dt = -grad(p') + Ra * theta * z-hat + nabla^2 u
div(u) = 0
d(theta)/dt = w + nabla^2 theta
```

where w is the vertical velocity component, p' is the pressure perturbation, and Ra is the Rayleigh number.

Taking the curl twice to eliminate pressure and extracting the z-component:

```
(1/Pr) * d/dt (nabla^2 w) = Ra * nabla_H^2 theta + nabla^4 w
d(theta)/dt = w + nabla^2 theta
```

where nabla_H^2 = d^2/dx^2 + d^2/dy^2 is the horizontal Laplacian.

**GPD self-critique:**
- The sign of the buoyancy term Ra * theta * z-hat is positive because hot fluid (theta > 0) is buoyant. Consistent with the convention that heating is from below. PASS.
- The w equation involves nabla^4 (biharmonic) from taking the double curl. Correct. PASS.

### Step 3: Normal mode analysis

```
/gpd:derive-equation
> Apply normal mode decomposition and derive the eigenvalue
> problem for the critical Rayleigh number.
```

Assume normal mode solutions:

```
w = W(z) exp(i(k_x x + k_y y)) exp(sigma t)
theta = Theta(z) exp(i(k_x x + k_y y)) exp(sigma t)
```

where k^2 = k_x^2 + k_y^2 is the horizontal wavenumber. Substituting:

```
(sigma/Pr) (D^2 - k^2) W = -Ra k^2 Theta + (D^2 - k^2)^2 W
sigma Theta = W + (D^2 - k^2) Theta
```

where D = d/dz.

At marginal stability (sigma = 0, onset of convection):

```
(D^2 - k^2)^2 W = Ra k^2 Theta
(D^2 - k^2) Theta = -W
```

Eliminating Theta:

```
(D^2 - k^2)^3 W = -Ra k^2 W
```

This is a sixth-order ODE eigenvalue problem for Ra as a function of k.

### Step 4: Solve for stress-free boundaries

```
/gpd:derive-equation
> Solve the eigenvalue problem for stress-free boundaries
> to obtain the critical Rayleigh number.
```

**Boundary conditions (stress-free, non-dimensional):**

At z = 0 and z = 1: W = 0, D^2 W = 0, Theta = 0.

The simplest eigenfunction satisfying these conditions is W = sin(n pi z) with n = 1, 2, 3, ... The condition D^2 W = -n^2 pi^2 sin(n pi z) vanishes at the boundaries automatically.

Substituting W = sin(n pi z) into (D^2 - k^2)^3 W = -Ra k^2 W:

```
(-(n pi)^2 - k^2)^3 sin(n pi z) = -Ra k^2 sin(n pi z)
```

Therefore:

```
Ra = (n^2 pi^2 + k^2)^3 / k^2
```

The minimum Ra (most unstable mode) occurs at n = 1 (lowest vertical mode). For n = 1, minimize with respect to k^2:

```
d(Ra)/d(k^2) = 0
d/d(k^2) [(pi^2 + k^2)^3 / k^2] = 0
```

Let q = k^2. Then:

```
[3(pi^2 + q)^2 * q - (pi^2 + q)^3] / q^2 = 0
3q = pi^2 + q
q = pi^2 / 2
```

So k_c^2 = pi^2/2, giving k_c = pi/sqrt(2) ~ 2.221.

Substituting back:

```
Ra_c = (pi^2 + pi^2/2)^3 / (pi^2/2) = (3 pi^2/2)^3 / (pi^2/2)
     = (27 pi^6/8) / (pi^2/2) = 27 pi^4/4
     ~ 657.5
```

**GPD self-critique:**
- Algebra check: (3pi^2/2)^3 = 27 pi^6/8. Divided by pi^2/2 = 27 pi^6/8 * 2/pi^2 = 27 pi^4/4. PASS.
- Minimum verification: d^2 Ra/d(k^2)^2 > 0 at k^2 = pi^2/2 (confirmed by second derivative test). PASS.

### Step 5: Compare with rigid boundaries

```
/gpd:derive-equation
> State the rigid-boundary result and compare scaling.
```

For rigid (no-slip) boundaries, the boundary conditions are W = 0, DW = 0, Theta = 0. The eigenfunctions are no longer simple sines and require numerical solution of a transcendental equation.

| Boundary condition | Ra_c | k_c | Reference |
|-------------------|------|-----|-----------|
| Free-free (stress-free) | 27 pi^4/4 = 657.5 | pi/sqrt(2) = 2.221 | This derivation |
| Rigid-rigid (no-slip) | 1707.8 | 3.117 | Chandrasekhar (1961) |
| Rigid-free (mixed) | 1100.7 | 2.682 | Chandrasekhar (1961) |

The rigid-boundary Ra_c is about 2.6 times larger than the free-boundary case, because no-slip conditions suppress velocity perturbations near the walls, making the system more stable.

## Results and Verification

### Final Results

| Quantity | Expression | Numerical value |
|----------|-----------|-----------------|
| Critical Rayleigh number (free) | Ra_c = 27 pi^4/4 | 657.5 |
| Critical wavenumber (free) | k_c = pi/sqrt(2) | 2.221 |
| Critical wavelength (free) | lambda_c = 2 pi/k_c = 2 sqrt(2) d | 2.828 d |
| Aspect ratio of convection rolls | lambda_c / (2d) = sqrt(2) | 1.414 |

### Verification Checks

```
/gpd:verify-work
```

**Dimensional analysis:**

```
/gpd:dimensional-analysis
```

- Ra = g alpha Delta T d^3 / (nu kappa). [Ra] = (m/s^2)(K^{-1})(K)(m^3)/((m^2/s)(m^2/s)) = dimensionless. PASS.
- k_c = pi/sqrt(2) is dimensionless (in units of 1/d). PASS.

**Limiting cases:**

```
/gpd:limiting-cases
```

| Limit | Expected | Obtained | Status |
|-------|----------|----------|--------|
| k -> 0 (long wavelength) | Ra -> infinity | (pi^2 + k^2)^3/k^2 -> pi^6/k^2 -> infinity | PASS |
| k -> infinity (short wavelength) | Ra -> infinity | k^4 -> infinity | PASS |
| n > 1 higher modes | Higher Ra_c | Ra(n=2) = (4pi^2+k^2)^3/k^2 >> Ra(n=1) | PASS |
| d -> 0 (thin layer) | Stable (conduction dominates) | Ra ~ d^3 -> 0 < Ra_c | PASS |

**Literature comparison:**
- Ra_c = 27 pi^4/4 for free boundaries matches Chandrasekhar, Hydrodynamic and Hydromagnetic Stability, Ch. II, Eq. (31). PASS.
- k_c = pi/sqrt(2) matches Drazin & Reid, Hydrodynamic Stability, Table 2.1. PASS.
- Rigid-boundary Ra_c = 1707.8 matches Chandrasekhar, Table III. PASS.

**Confidence: HIGH** -- Exact analytical solution for free-free boundaries. All steps involve standard eigenvalue analysis with explicit verification. Numerical rigid-boundary value quoted from Chandrasekhar.
