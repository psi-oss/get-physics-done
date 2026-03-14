---
load_when:
  - "open quantum system"
  - "Lindblad"
  - "master equation"
  - "decoherence"
  - "quantum channel"
  - "Kraus operator"
  - "quantum optics"
  - "cavity QED"
  - "Jaynes-Cummings"
  - "Rabi oscillation"
  - "rotating wave"
  - "dissipation"
  - "quantum noise"
  - "T1"
  - "T2"
  - "dephasing"
  - "Purcell effect"
  - "quantum trajectory"
  - "Redfield"
tier: 2
context_cost: medium
---

# Open Quantum Systems and Quantum Optics Protocol

Open quantum systems are where quantum mechanics meets the environment. Every real quantum device — qubits, atoms in cavities, photons in fibers — is an open system. The theory of open quantum systems determines decoherence times, gate fidelities, and the fundamental limits of quantum technologies.

**Core discipline:** The density matrix must remain a valid quantum state at ALL times: Hermitian, unit trace, and positive semidefinite. Any approximation that violates these properties produces unphysical results (negative probabilities, trace loss). Every step below exists because these violations are common and subtle.

## Related Protocols

- `perturbation-theory.md` — Perturbative system-bath coupling (Born approximation)
- `numerical-computation.md` — ODE integration for master equations, convergence testing
- `exact-diagonalization.md` — Small system exact dynamics
- `path-integrals.md` — Feynman-Vernon influence functional approach

---

## Step 1: System-Bath Decomposition

Explicitly identify the system, bath, and interaction:

| Component | Hilbert Space | Description |
|-----------|--------------|-------------|
| **System** | H_S (finite-dimensional) | The quantum degrees of freedom you track |
| **Bath** | H_B (infinite-dimensional, typically) | Environment causing decoherence |
| **Interaction** | H_SB | System-bath coupling |

Total: H = H_S + H_B + H_SB

**CRITICAL:** The system-bath boundary is a CHOICE, not a physical fact. Moving the boundary changes the dynamics. A qubit coupled to a cavity can be modeled as:
- System = qubit, bath = cavity + photon loss → Purcell decay
- System = qubit + cavity, bath = photon loss → Jaynes-Cummings + cavity decay

**Common LLM Error:** Treating the system-bath decomposition as unique. Different decompositions give different master equations with different validity regimes.

---

## Step 2: Choose the Dynamical Framework

| Framework | Validity | Strengths | Limitations |
|-----------|----------|-----------|-------------|
| **Lindblad master equation** | Markov, weak coupling, secular | Guarantees CPTP, simple | Misses non-Markovian effects |
| **Redfield equation** | Weak coupling, Born | Captures some non-Markovian | Can violate positivity |
| **HEOM** | Any coupling, non-Markovian | Numerically exact for specific baths | Expensive, limited bath types |
| **Stochastic Schrodinger** | Equivalent to Lindblad | Efficient for large Hilbert spaces | Individual trajectories not physical |
| **Input-output theory** | Markov, specific geometries | Natural for quantum optics | Less general |

### Lindblad Master Equation (Most Common)

dρ/dt = -i[H_S, ρ] + Σ_k γ_k (L_k ρ L_k† - ½{L_k†L_k, ρ})

where L_k are Lindblad operators (jump operators) and γ_k ≥ 0 are decay rates.

**MANDATORY checks:**
- [ ] All γ_k ≥ 0 (negative rates violate complete positivity)
- [ ] Trace preservation: Tr(dρ/dt) = 0 (automatically satisfied by Lindblad form)
- [ ] Hermiticity: (dρ/dt)† = dρ/dt (automatically satisfied if H_S is Hermitian and L_k are operators)

### Deriving Lindblad from Microscopic Model

1. Start with total Hamiltonian H = H_S + H_B + H_SB
2. Move to interaction picture: H_I(t) = e^{i(H_S+H_B)t} H_SB e^{-i(H_S+H_B)t}
3. Born approximation: ρ_total(t) ≈ ρ_S(t) ⊗ ρ_B (weak coupling)
4. Markov approximation: bath correlations decay fast → memoryless dynamics
5. Secular approximation: drop fast-oscillating terms (rotating wave approximation in the master equation)

**Common LLM Error:** Skipping the secular approximation. Without it, the Redfield equation can violate positivity (give negative diagonal density matrix elements). The secular approximation is what makes the result Lindblad-form.

---

## Step 3: Identify Decoherence Channels

For a qubit (two-level system), the standard decoherence channels are:

| Channel | Lindblad Operator | Rate | Physical Process |
|---------|------------------|------|-----------------|
| **Relaxation (T1)** | L = σ₋ = |0⟩⟨1| | γ₁ = 1/T1 | Energy decay to ground state |
| **Excitation** | L = σ₊ = |1⟩⟨0| | γ↑ ∝ n̄_th × γ₁ | Thermal excitation (T > 0) |
| **Pure dephasing (Tφ)** | L = σ_z | γφ = 1/Tφ | Phase randomization without energy change |

**CRITICAL RELATION:**

1/T2 = 1/(2T1) + 1/Tφ

This is NOT 1/T2 = 1/T1 + 1/Tφ. The factor of 2 comes from the fact that T1 processes also cause dephasing (at half the rate of population decay).

**Common LLM Error:** Wrong T1/T2/Tφ relation. The most common mistake is forgetting the factor of 2: writing 1/T2 = 1/T1 + 1/Tφ instead of 1/T2 = 1/(2T1) + 1/Tφ. This leads to incorrect decoherence time predictions.

**Verification:**
- [ ] T2 ≤ 2T1 always (equality when pure dephasing = 0)
- [ ] At T = 0: γ↑ = 0 (no thermal excitation)
- [ ] Detailed balance: γ↑/γ₁ = exp(-ℏω/k_BT) for thermal bath

---

## Step 4: Quantum Optics Specific

### Jaynes-Cummings Model

H_JC = ω_a σ₊σ₋ + ω_c a†a + g(σ₊a + σ₋a†)

where ω_a = atom frequency, ω_c = cavity frequency, g = coupling strength.

**Rotating wave approximation (RWA):** The counter-rotating terms σ₊a† and σ₋a are dropped. Valid when g ≪ ω_a, ω_c.

**Key results (verify these):**
- Vacuum Rabi splitting: Δ = 2g (splitting of dressed states at resonance)
- Purcell decay rate: γ_P = g²/κ (cavity-enhanced decay, valid when g ≪ κ)
- Strong coupling criterion: g > (κ, γ)/2 where κ = cavity decay, γ = atom decay

**Common LLM Error:** Confusing the vacuum Rabi frequency (g) with the vacuum Rabi splitting (2g). The splitting of the two dressed states at resonance is 2g, not g. This factor of 2 error propagates to every spectroscopic prediction.

### Rotating Frame

Transform to a frame rotating at the drive frequency ω_d:

H_rot = Δ σ₊σ₋ + (Ω/2)(σ₊ + σ₋)

where Δ = ω_a - ω_d (detuning) and Ω = Rabi frequency.

**Verification:** In the rotating frame, the dynamics should be slow (frequencies ~ Δ, Ω, not ~ ω_a). If you see oscillations at frequency ω_a in the rotating frame, the transformation was done wrong.

---

## Step 5: Quantum Channels and CPTP Maps

A quantum channel E is a completely positive, trace-preserving (CPTP) map: ρ → E(ρ).

**Kraus representation:** E(ρ) = Σ_k K_k ρ K_k† with Σ_k K_k† K_k = I (trace preservation)

**Verification checklist for quantum channels:**
- [ ] Completeness: Σ_k K_k† K_k = I (verify by computing the sum explicitly)
- [ ] Complete positivity: apply the channel to half of a maximally entangled state; the result must be a valid density matrix (Choi-Jamiolkowski theorem)
- [ ] Trace preservation: Tr(E(ρ)) = 1 for any input ρ

**Common LLM Error:** Confusing positive maps with completely positive maps. The transpose map ρ → ρ^T is positive but NOT completely positive — it sends entangled states to unphysical (negative eigenvalue) states. Every physical quantum channel must be COMPLETELY positive, not just positive.

---

## Step 6: Numerical Integration

For the Lindblad equation, the density matrix ρ is N×N for an N-dimensional Hilbert space. The equation of motion is a system of N² coupled ODEs.

**Method selection:**

| Method | When to Use | Cost per Step |
|--------|------------|--------------|
| **RK4/RK45** | Small systems (N < 100), smooth dynamics | O(N⁴) |
| **Matrix exponential** | Constant Hamiltonian, pulsed dynamics | O(N³) per segment |
| **Stochastic Schrodinger** | Large N, averaging over trajectories | O(N²) per trajectory |
| **Tensor network** | 1D chains, moderate entanglement | O(χ³N) where χ = bond dimension |

**Convergence checks (MANDATORY):**
- [ ] Trace Tr(ρ) = 1 preserved to machine precision at all times
- [ ] Eigenvalues of ρ remain non-negative (no eigenvalue crosses below -ε for ε = 10⁻¹⁰)
- [ ] Steady state (if it exists): dρ/dt → 0 at late times
- [ ] Energy conservation in closed system limit (γ_k → 0): ⟨H⟩ should be constant

---

## Common LLM Error Patterns

| Error | LLM Symptom | Detection | Error Class |
|-------|-------------|-----------|-------------|
| T1/T2 factor of 2 | 1/T2 = 1/T1 + 1/Tφ (wrong) | Check T2 ≤ 2T1 constraint | #1, #2 |
| RWA outside validity | Uses RWA when g/ω ~ 0.1+ | Check g/ω ratio; if >0.05, ultra-strong coupling | #5 |
| Negative decay rate | γ < 0 in Lindblad equation | Check all rates are non-negative | #8 |
| Rabi splitting vs frequency | 2g vs g confusion | Check dressed state energy difference at resonance | #1 |
| Positive but not CP | Uses transpose as a channel | Check Choi matrix eigenvalues | #14 |
| Redfield without secular | Applies Born-Markov without secular approx | Check positivity of ρ at all times | #5 |
| Trace violation | Numerical error accumulates | Monitor Tr(ρ) - 1 throughout integration | #27 |
| Wrong rotating frame | Frame at wrong frequency | Check that rotating-frame dynamics are slow | #15 |

---

## Worked Example: Qubit Decoherence in Thermal Bath

**Problem:** A qubit with splitting ω₀ = 5 GHz is coupled to a thermal bath at T = 50 mK. The bare relaxation rate is γ₁ = 1/(20 μs) and pure dephasing rate is γφ = 1/(30 μs). Compute T2 and the steady-state population.

### Solution

**Step 1:** Check temperature regime:
- ℏω₀/(k_BT) = (5 GHz × 6.626×10⁻³⁴)/(1.381×10⁻²³ × 0.05) = 4.8
- Since ℏω₀ ≫ k_BT, thermal occupation is small: n̄ = 1/(e^{4.8} - 1) ≈ 0.0083

**Step 2:** Compute rates:
- γ₁ = 1/T1 = 1/(20 μs) = 50,000 s⁻¹
- γ↑ = n̄ × γ₁ = 0.0083 × 50,000 = 415 s⁻¹ (thermal excitation — small but nonzero)
- γφ = 1/(30 μs) = 33,333 s⁻¹

**Step 3:** Compute T2:
- 1/T2 = 1/(2T1) + 1/Tφ = 50,000/2 + 33,333 = 25,000 + 33,333 = 58,333 s⁻¹
- T2 = 17.1 μs

**Step 4:** Verify T2 ≤ 2T1:
- 2T1 = 40 μs, T2 = 17.1 μs < 40 μs ✓

**Step 5:** Steady-state population:
- P_excited = γ↑/(γ₁ + γ↑) = 415/(50,000 + 415) = 0.0082 ≈ n̄/(2n̄+1)
- P_ground = 1 - 0.0082 = 0.9918

**Verification:**
- [ ] T2 < 2T1 ✓ (17.1 < 40)
- [ ] Steady-state P_excited ≈ Boltzmann factor e^{-ℏω₀/k_BT}/(1 + e^{-ℏω₀/k_BT}) ≈ 0.0082 ✓
- [ ] At T → 0: P_excited → 0, T2 → 2T1 = 40 μs (pure dephasing dominates over T1 contribution at finite T) ✓
- [ ] Dimensional check: all rates in s⁻¹, times in μs, energies in GHz (natural units ℏ = 1) ✓

---

## Verification Checklist

Before finalizing any open quantum system calculation:

- [ ] System-bath decomposition explicitly stated
- [ ] Lindblad operators identified with physical interpretation
- [ ] All decay rates γ_k ≥ 0
- [ ] Trace Tr(ρ) = 1 preserved at all times
- [ ] Density matrix positive semidefinite at all times
- [ ] T1/T2 relation correct: 1/T2 = 1/(2T1) + 1/Tφ (not 1/T1 + 1/Tφ)
- [ ] Rotating wave approximation validity checked: g/ω ≪ 1
- [ ] Thermal occupation computed correctly: n̄ = 1/(e^{ℏω/k_BT} - 1)
- [ ] Detailed balance satisfied: γ↑/γ₁ = n̄/(n̄+1)
- [ ] Steady state matches thermal equilibrium (for thermal bath)
- [ ] Quantum channel completeness relation verified: Σ K†K = I
- [ ] Numerical convergence tested (timestep, Hilbert space truncation)
