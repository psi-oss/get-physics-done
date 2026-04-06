# Hydrogen Atom: Algebraic Solution via so(4) Symmetry

## Problem Statement

The hydrogen atom energy spectrum E_n = -13.6 eV / n^2 has a characteristic n^2 degeneracy that is larger than what rotational symmetry alone explains. Rotational so(3) symmetry accounts for the (2l+1)-fold degeneracy within each l, but not the degeneracy across different l values at the same n. This "accidental" degeneracy is explained by the same so(4) symmetry that appears in the classical Kepler problem.

**Goal:** Use the quantum LRL operator and the so(4) Lie algebra to derive the hydrogen spectrum E_n = -me^4/(2 hbar^2 n^2) purely algebraically, without solving the Schrodinger equation.

## GPD Workflow

### Step 1: Initialize project and lock conventions

```
/gpd:new-project
> Derive the hydrogen atom energy spectrum algebraically using
> the quantum Laplace-Runge-Lenz operator and so(4) symmetry.
> No differential equations -- pure Lie algebra.
```

**Convention lock:**

| Convention | Choice |
|------------|--------|
| Potential | V(r) = -e^2/(4 pi epsilon_0 r), abbreviated as V = -k/r with k = e^2/(4 pi epsilon_0) |
| Units | Gaussian CGS for intermediate steps; final answers in SI |
| Commutator convention | [A, B] = AB - BA |
| Angular momentum | L = r x p, [L_i, L_j] = i hbar epsilon_{ijk} L_k |
| Quantum LRL vector | A_hat = (1/2)(p x L - L x p) - mk r-hat |

### Step 2: Construct the quantum LRL operator

```
/gpd:derive-equation
> Construct the Hermitian quantum LRL operator and verify
> it commutes with the hydrogen Hamiltonian.
```

The classical LRL vector A = p x L - mk r-hat is not Hermitian as a quantum operator because p and L do not commute. The symmetrized form is:

```
A_hat = (1/2)(p x L - L x p) - mk r-hat
```

**Verification that [H, A_hat] = 0:**

The Hamiltonian is H = p^2/(2m) - k/r. The proof proceeds by computing [H, A_hat_i] component by component, using:

```
[p_i, 1/r] = -i hbar x_i / r^3
[L_i, p_j] = i hbar epsilon_{ijk} p_k
[L_i, x_j] = i hbar epsilon_{ijk} x_k
```

After a lengthy but systematic computation, all terms cancel: [H, A_hat] = 0.

**GPD self-critique:**
- Hermiticity check: A_hat^dagger = A_hat by construction (symmetrized cross product). PASS.
- Dimension check: [A_hat] = [p][L] = (kg m/s)(kg m^2/s) = kg^2 m^3/s^2. Same as [mk] = kg * kg m^3/s^2. PASS.

### Step 3: Derive the so(4) commutation relations

```
/gpd:derive-equation
> Compute [L_i, A_j], [A_i, A_j] and show the algebra closes to so(4)
> for bound states.
```

The commutation relations are:

```
[L_i, L_j] = i hbar epsilon_{ijk} L_k
[L_i, A_j] = i hbar epsilon_{ijk} A_k
[A_i, A_j] = -2m H i hbar epsilon_{ijk} L_k
```

The third relation involves the Hamiltonian operator H. For an eigenstate with energy E < 0 (bound state), H can be replaced by E, giving:

```
[A_i, A_j] = -2mE (i hbar) epsilon_{ijk} L_k
```

Define the scaled operator:

```
M_i = A_i / sqrt(-2mE)
```

Then:

```
[L_i, L_j] = i hbar epsilon_{ijk} L_k
[L_i, M_j] = i hbar epsilon_{ijk} M_k
[M_i, M_j] = i hbar epsilon_{ijk} L_k
```

This is so(4). Defining J = (L + M)/2 and K = (L - M)/2:

```
[J_i, J_j] = i hbar epsilon_{ijk} J_k
[K_i, K_j] = i hbar epsilon_{ijk} K_k
[J_i, K_j] = 0
```

This is su(2) x su(2), the double cover of so(4).

### Step 4: Extract the spectrum from representation theory

```
/gpd:derive-equation
> Use the Casimir operators of su(2) x su(2) to derive the
> hydrogen energy levels.
```

Each su(2) factor has a Casimir: J^2 = j(j+1) hbar^2 and K^2 = k(k+1) hbar^2.

**Constraint from A . L = 0:**

The classical identity A . L = 0 persists quantum mechanically: A_hat . L = 0. This means M . L = 0, which implies:

```
J^2 = K^2
```

Therefore j = k. Label this common value j (which takes values 0, 1/2, 1, 3/2, ...).

**Casimir of so(4):**

The quadratic Casimir is:

```
C_2 = L^2 + M^2 = 2(J^2 + K^2) = 4 j(j+1) hbar^2
```

But also, from the definition M = A/sqrt(-2mE) and the operator identity A^2 = 2mH(L^2 + hbar^2) + m^2 k^2:

```
L^2 + M^2 = L^2 + A^2/(-2mE) = L^2 + (2mE(L^2 + hbar^2) + m^2 k^2)/(-2mE)
           = L^2 - L^2 - hbar^2 - m^2 k^2/(2mE)
           = -hbar^2 - mk^2/(2E)
```

Setting this equal to 4 j(j+1) hbar^2:

```
-hbar^2 - mk^2/(2E) = 4 j(j+1) hbar^2
mk^2/(2|E|) = (4j(j+1) + 1) hbar^2 = (2j+1)^2 hbar^2
```

Define n = 2j + 1 (takes values 1, 2, 3, ...):

```
E_n = -mk^2 / (2 hbar^2 n^2)
```

With k = e^2/(4 pi epsilon_0) in SI:

```
E_n = -m e^4 / (2 (4 pi epsilon_0)^2 hbar^2 n^2) = -13.6 eV / n^2
```

**The spectrum is derived without solving any differential equation.**

### Step 5: Verify the degeneracy count

For a given n = 2j + 1, each su(2) factor has dimension (2j + 1) = n. The representation space of su(2) x su(2) with j = k has dimension n * n = n^2.

But the physical angular momentum quantum number l is related to j by the Clebsch-Gordan decomposition of J and K (which combine to L). The allowed values are l = 0, 1, ..., n-1, and each l has (2l+1) states. Total:

```
sum_{l=0}^{n-1} (2l + 1) = n^2
```

This confirms the n^2 degeneracy of the hydrogen atom.

## Results and Verification

### Final Results

| Quantity | Expression |
|----------|-----------|
| Symmetry algebra | su(2) x su(2) (double cover of so(4)) |
| Constraint | j = k (from A . L = 0) |
| Principal quantum number | n = 2j + 1 = 1, 2, 3, ... |
| Energy spectrum | E_n = -mk^2 / (2 hbar^2 n^2) |
| Degeneracy | n^2 (ignoring spin) |

### Verification Checks

```
/gpd:verify-work
```

**Dimensional analysis:**

```
/gpd:dimensional-analysis
```

- [mk^2 / hbar^2] = kg * (kg m^3/s^2)^2 / (kg m^2/s)^2 = kg * kg^2 m^6 s^{-4} / (kg^2 m^4 s^{-2}) = kg m^2 / s^2 = energy. PASS.
- [E_n] = energy. PASS.

**Limiting cases:**

```
/gpd:limiting-cases
```

| Limit | Expected | Obtained | Status |
|-------|----------|----------|--------|
| n = 1 (ground state) | E_1 = -13.6 eV | -mk^2/(2 hbar^2) = -13.6 eV | PASS |
| n -> infinity | E -> 0 (ionization threshold) | -13.6/n^2 -> 0 | PASS |
| hbar -> 0 | Classical Kepler problem recovered | E_n spacing -> 0, quasi-continuum | PASS |
| l degeneracy | n^2 total states | sum_{l=0}^{n-1}(2l+1) = n^2 | PASS |

**Literature comparison:**
- Spectrum matches Pauli (1926), Z. Physik 36, 336. PASS.
- so(4) algebra matches Fock (1935), Z. Physik 98, 145. PASS.
- Degeneracy formula matches Griffiths, Introduction to Quantum Mechanics, Eq. (4.70). PASS.

**Confidence: HIGH** -- Algebraic derivation with multiple independent verification paths. No numerical computation involved; result is exact.
