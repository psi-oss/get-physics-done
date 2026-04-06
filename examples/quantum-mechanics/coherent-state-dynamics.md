# Quantum Harmonic Oscillator: Coherent State Dynamics

## Problem Statement

Coherent states |alpha> of the quantum harmonic oscillator are the "most classical" quantum states: they minimize the Heisenberg uncertainty relation and their expectation values follow classical trajectories. They are central to quantum optics, quantum information, and semiclassical approximations.

**Goal:** Construct coherent states, derive their time evolution, show that expectation values obey classical equations of motion, and compute the uncertainty product Delta_x Delta_p as a function of time.

## GPD Workflow

### Step 1: Initialize project and lock conventions

```
/gpd:new-project
> Construct coherent states of the quantum harmonic oscillator,
> derive their time evolution, and verify the classical limit.
```

**Convention lock:**

| Convention | Choice |
|------------|--------|
| Hamiltonian | H = hbar omega (a^dagger a + 1/2) |
| Ladder operators | a = sqrt(m omega / (2 hbar)) x + i p / sqrt(2 m omega hbar) |
| Commutator | [a, a^dagger] = 1 |
| Coherent state definition | a \|alpha> = alpha \|alpha> (eigenstate of annihilation operator) |
| Units | Natural units for intermediate steps; SI for final results |

### Step 2: Construct coherent states in the Fock basis

```
/gpd:derive-equation
> Express the coherent state |alpha> in the number state basis
> and verify normalization.
```

Starting from a|alpha> = alpha|alpha> and expanding |alpha> = sum_n c_n |n>:

```
a sum_n c_n |n> = sum_n c_n sqrt(n) |n-1> = alpha sum_n c_n |n>
```

Matching coefficients: c_n sqrt(n) = alpha c_{n-1}, giving c_n = (alpha^n / sqrt(n!)) c_0.

Normalization: sum_n |c_n|^2 = |c_0|^2 sum_n |alpha|^{2n}/n! = |c_0|^2 exp(|alpha|^2) = 1.

Therefore c_0 = exp(-|alpha|^2/2) and:

```
|alpha> = exp(-|alpha|^2 / 2) sum_{n=0}^{infinity} (alpha^n / sqrt(n!)) |n>
```

**GPD self-critique:**
- Normalization check: <alpha|alpha> = exp(-|alpha|^2) sum_n |alpha|^{2n}/n! = exp(-|alpha|^2) exp(|alpha|^2) = 1. PASS.
- Poisson distribution: P(n) = |c_n|^2 = exp(-|alpha|^2) |alpha|^{2n}/n!. Mean <n> = |alpha|^2. Variance = |alpha|^2. Correct Poisson statistics. PASS.

### Step 3: Derive time evolution

```
/gpd:derive-equation
> Compute the time evolution of a coherent state under the
> harmonic oscillator Hamiltonian.
```

Apply the time evolution operator U(t) = exp(-iHt/hbar):

```
U(t)|alpha> = exp(-i omega t(a^dagger a + 1/2)) |alpha>
            = exp(-i omega t / 2) sum_n c_n exp(-i n omega t) |n>
            = exp(-i omega t / 2) exp(-|alpha|^2 / 2) sum_n (alpha exp(-i omega t))^n / sqrt(n!) |n>
            = exp(-i omega t / 2) |alpha exp(-i omega t)>
```

The coherent state remains a coherent state at all times, with the parameter rotating in the complex plane:

```
|alpha(t)> = exp(-i omega t / 2) |alpha_0 exp(-i omega t)>
```

The global phase exp(-i omega t/2) is physically irrelevant. The coherent state label simply rotates: alpha(t) = alpha_0 exp(-i omega t).

**GPD verification:**
- Unitarity check: the state stays normalized since |alpha(t)| = |alpha_0|. PASS.
- Periodicity: alpha(t + 2 pi/omega) = alpha(t). The state returns to itself (up to global phase) after one period. PASS.

### Step 4: Compute expectation values

```
/gpd:derive-equation
> Compute <x(t)>, <p(t)>, and show they satisfy
> the classical equations of motion.
```

Using x = sqrt(hbar/(2m omega))(a + a^dagger) and p = i sqrt(m omega hbar / 2)(a^dagger - a):

```
<x(t)> = sqrt(hbar/(2m omega)) (<alpha(t)| (a + a^dagger) |alpha(t)>)
        = sqrt(hbar/(2m omega)) (alpha(t) + alpha*(t))
        = sqrt(2 hbar/(m omega)) Re(alpha_0 exp(-i omega t))
        = sqrt(2 hbar/(m omega)) |alpha_0| cos(omega t - phi_0)
```

where alpha_0 = |alpha_0| exp(i phi_0). Similarly:

```
<p(t)> = -sqrt(2 m omega hbar) |alpha_0| sin(omega t - phi_0)
```

These satisfy the classical equations:

```
d<x>/dt = <p>/m         (Newton's second law, first order form)
d<p>/dt = -m omega^2 <x>   (Hooke's law)
```

This is Ehrenfest's theorem in action, but for coherent states it is exact (not just an approximation for narrow wavepackets) because the harmonic oscillator potential is at most quadratic.

### Step 5: Compute the uncertainty product

```
/gpd:derive-equation
> Compute Delta_x and Delta_p for the coherent state
> and show the uncertainty product is minimized.
```

For any coherent state |alpha>:

```
<x^2> - <x>^2 = hbar/(2m omega) * (<alpha|(a + a^dagger)^2|alpha> - <alpha|(a + a^dagger)|alpha>^2)
              = hbar/(2m omega) * (1)
```

The "1" comes from the commutator [a, a^dagger] = 1: expanding (a + a^dagger)^2 gives a^2 + a a^dagger + a^dagger a + (a^dagger)^2, and the cross terms produce <alpha|[a, a^dagger]|alpha> = 1 as the only surviving contribution to the variance.

Similarly:

```
<p^2> - <p>^2 = m omega hbar / 2
```

Therefore:

```
Delta_x = sqrt(hbar / (2 m omega))
Delta_p = sqrt(m omega hbar / 2)
Delta_x * Delta_p = hbar / 2
```

The uncertainty product is exactly hbar/2 -- the minimum allowed by the Heisenberg relation -- and it is independent of time and independent of alpha.

## Results and Verification

### Final Results

| Quantity | Expression |
|----------|-----------|
| Coherent state | \|alpha> = exp(-\|alpha\|^2/2) sum_n (alpha^n/sqrt(n!)) \|n> |
| Time evolution | alpha(t) = alpha_0 exp(-i omega t) |
| Position expectation | <x(t)> = sqrt(2hbar/(m omega)) \|alpha_0\| cos(omega t - phi_0) |
| Momentum expectation | <p(t)> = -sqrt(2 m omega hbar) \|alpha_0\| sin(omega t - phi_0) |
| Uncertainty product | Delta_x Delta_p = hbar/2 (time-independent, minimum uncertainty) |
| Photon statistics | P(n) = exp(-\|alpha\|^2) \|alpha\|^{2n}/n! (Poisson) |

### Verification Checks

```
/gpd:verify-work
```

**Dimensional analysis:**

```
/gpd:dimensional-analysis
```

- [sqrt(hbar/(m omega))] = sqrt((J s)/(kg * s^{-1})) = sqrt(kg m^2 s^{-1} / (kg s^{-1})) = sqrt(m^2) = m. PASS.
- [Delta_x * Delta_p] = m * (kg m/s) = kg m^2/s = J s = [hbar]. PASS.

**Limiting cases:**

```
/gpd:limiting-cases
```

| Limit | Expected | Obtained | Status |
|-------|----------|----------|--------|
| alpha = 0 (vacuum) | Ground state \|0> | exp(0)\|0> = \|0> | PASS |
| \|alpha\| >> 1 | Classical oscillator | <x(t)> follows classical trajectory, Delta_x/\|<x>\| -> 0 | PASS |
| omega -> 0 | Free particle limit | Delta_x -> infinity (delocalized) | PASS |
| t = 0 | Initial coherent state | alpha(0) = alpha_0 | PASS |

**Literature comparison:**
- Coherent state definition matches Glauber (1963), Phys. Rev. 131, 2766. PASS.
- Minimum uncertainty property matches Sakurai, Modern Quantum Mechanics, Sec. 2.3. PASS.
- Poisson photon statistics matches Mandel & Wolf, Optical Coherence and Quantum Optics, Ch. 11. PASS.

**Confidence: HIGH** -- Exact analytical results with multiple independent checks. All computations are algebraic with no approximations.
