# GPD Examples Gallery

Worked examples showing how GPD structures and solves physics research problems. Each example walks through a concrete problem from statement to verified result, demonstrating the GPD workflow in practice.

## By Subfield

### Classical Mechanics

| Example | Key Technique | GPD Features Used |
|---------|--------------|-------------------|
| [Kepler Problem: Closed Orbits from Symmetry](classical-mechanics/kepler-problem.md) | Laplace-Runge-Lenz vector, Hamilton-Jacobi theory | Convention locking, derive-equation, limiting-cases |

### Quantum Mechanics

| Example | Key Technique | GPD Features Used |
|---------|--------------|-------------------|
| [Hydrogen Atom: Algebraic Solution via so(4) Symmetry](quantum-mechanics/hydrogen-atom-so4.md) | Lie algebra, representation theory | Convention locking, derive-equation, dimensional-analysis |
| [Quantum Harmonic Oscillator: Coherent State Dynamics](quantum-mechanics/coherent-state-dynamics.md) | Coherent states, Heisenberg picture | Convention locking, derive-equation, limiting-cases |

### Statistical Mechanics

| Example | Key Technique | GPD Features Used |
|---------|--------------|-------------------|
| [2D Ising Model: Critical Exponents via Monte Carlo](statistical-mechanics/ising-model-critical-exponents.md) | Wolff cluster algorithm, finite-size scaling | Experiment design, numerical-convergence, parameter-sweep |

### Electrodynamics

| Example | Key Technique | GPD Features Used |
|---------|--------------|-------------------|
| [Radiation from an Accelerated Charge: Larmor Formula and Beyond](electrodynamics/larmor-radiation.md) | Retarded potentials, Lienard-Wiechert fields | Convention locking, derive-equation, limiting-cases |

### Fluid Dynamics

| Example | Key Technique | GPD Features Used |
|---------|--------------|-------------------|
| [Rayleigh-Benard Convection: Linear Stability Analysis](fluid-dynamics/rayleigh-benard.md) | Navier-Stokes perturbation theory, eigenvalue problem | Derive-equation, numerical-convergence, parameter-sweep |

### Quantum Field Theory

| Example | Key Technique | GPD Features Used |
|---------|--------------|-------------------|
| [One-Loop QED Vertex Correction and the Anomalous Magnetic Moment](qft/qed-anomalous-magnetic-moment.md) | Dimensional regularization, Feynman parameters | Convention locking, derive-equation, verify-work |

## How to Read These Examples

Each example follows the same structure:

1. **Problem Statement** -- the physics question and why it matters.
2. **GPD Workflow** -- the sequence of GPD commands and what each produces.
3. **Key Derivation Steps** -- the core physics, showing how GPD's verification catches errors.
4. **Results and Verification** -- final answers with dimensional checks, limiting cases, and literature comparison.

These are not minimal textbook exercises. They are structured as realistic research workflows, showing how GPD manages conventions, tracks assumptions, and verifies results across multiple steps.

## Running These Yourself

To reproduce any example, install GPD and start a new project:

```bash
npx get-physics-done
```

Then in your runtime:

```
/gpd:new-project
> [paste the problem statement from any example]
```

GPD will guide you through the same workflow shown in the example. Your results should agree within the stated precision.
