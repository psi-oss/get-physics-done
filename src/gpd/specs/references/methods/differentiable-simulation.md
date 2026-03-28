---
load_when:
  - "differentiable simulation"
  - "differentiable physics"
  - "autodiff through solver"
  - "inverse problem PDE"
  - "topology optimization"
  - "adjoint method"
  - "warp autodiff"
  - "optimize through physics"
  - "parameter estimation PDE"
  - "neural surrogate"
tier: 2
context_cost: medium
---

# Differentiable Simulation

A method protocol for optimizing through physics solvers using automatic differentiation. Covers when to use it, how to verify gradient correctness, common failure modes, and the relationship to classical adjoint methods.

**Related files:**
- `../approximation-selection.md` — broader method selection framework
- `../../verification/core/verification-numerical.md` — convergence and numerical stability
- `../../verification/core/verification-core.md` — conservation laws, limiting cases
- `../../templates/compute/warp-simulation.md` — containerized Warp simulation guide
- `../../templates/compute/warp/` — ready-to-copy Dockerfiles, requirements.txt, and run script

---

<core_principle>

## When Differentiable Simulation Is The Right Tool

Differentiable simulation computes gradients of a scalar objective through a physics solver, enabling gradient-based optimization of physical systems. Use it when:

1. **You have a well-posed forward solver** — the PDE or simulation produces correct physics
2. **You need gradients of an objective w.r.t. design parameters** — fan placement, material distribution, boundary shape, control inputs
3. **The objective is smooth enough for gradient descent** — no hard discontinuities in the loss landscape
4. **The parameter space is too large for finite differences** — more than ~5 parameters makes FD expensive

**Do not use it when:**
- The forward solver is not validated (gradients of wrong physics are useless)
- The objective has many local minima and you need global search (use sampling methods)
- The design space is discrete with no continuous relaxation
- You only need a single evaluation, not optimization

**Key insight:** Differentiable simulation is a method for computing gradients, not a method for solving physics. The forward solver must be correct first. Validate the solver independently before trusting its gradients.

</core_principle>

<gradient_methods>

## Gradient Computation Methods

Three approaches, in order of preference when available:

### 1. Tape-Based Automatic Differentiation

Record all operations on a computational tape, then replay in reverse to compute gradients. Used by Warp (`wp.Tape`), JAX (`jax.grad`), PyTorch (`autograd`), Taichi (`ti.ad`).

```
Advantages:
- Exact gradients (to floating-point precision)
- No manual derivation
- Cost: 1 forward + 1 backward ≈ 2-3x forward cost
- Scales to any number of parameters

Limitations:
- Memory: tape stores all intermediate states (N_iters × grid_size × 4 bytes)
- Cannot differentiate through non-differentiable operations (branching on values, integer indexing)
- Some solvers (sparse direct solves, FFTs) may not be on-tape
```

**Critical rule:** Use the same iteration count and solver fidelity for both forward and backward passes. Reducing iterations for the backward pass (e.g., 3000 forward, 10 backward) produces noisy, unreliable gradients.

### 2. Adjoint Method

Derive the adjoint PDE analytically, solve it backward in time/iteration. Classical approach in optimal control, aerodynamic shape optimization.

```
Advantages:
- Memory-efficient: O(1) storage (no tape)
- Exact for the continuous PDE (discretization error only)
- Well-understood theory

Limitations:
- Requires manual derivation per PDE
- Adjoint PDE may be harder to solve than forward PDE
- Discretize-then-differentiate ≠ differentiate-then-discretize (consistency gap)
```

### 3. Finite Differences

Perturb each parameter, re-solve, compute gradient from function values.

```
Cost: 2N forward solves for N parameters (central differences)
      N+1 forward solves (forward differences, less accurate)

Use only when:
- N ≤ 5 parameters (otherwise too expensive)
- Forward solver cannot be differentiated (black-box legacy code)
- As a validation check against autodiff gradients
```

### Decision Table

| Parameters | Solver on tape? | Adjoint derived? | Method |
|-----------|----------------|-----------------|--------|
| Any | Yes | — | Tape-based AD |
| Any | No | Yes | Adjoint method |
| ≤ 5 | No | No | Finite differences |
| > 5 | No | No | Derive adjoint or rewrite solver for AD |

</gradient_methods>

<verification_protocol>

## Gradient Verification

**Always verify gradients before trusting optimization results.** This is the single most important check for differentiable simulation.

### Autodiff vs Finite-Difference Comparison

At a representative parameter point, compare tape-based gradients against central finite differences:

```python
# For each parameter i:
eps = 1e-4 * max(abs(param[i]), 1.0)  # relative step size
loss_plus  = forward_solve(param + eps * e_i)
loss_minus = forward_solve(param - eps * e_i)
grad_fd[i] = (loss_plus - loss_minus) / (2 * eps)

# Compare:
relative_error = abs(grad_ad[i] - grad_fd[i]) / (abs(grad_fd[i]) + 1e-8)
# PASS if relative_error < 0.05 for all parameters
# INVESTIGATE if 0.05 < relative_error < 0.20
# FAIL if relative_error > 0.20
```

**Common causes of gradient mismatch:**
- Non-differentiable operations in the forward pass (`min`, `max`, `abs` with zero-crossing, integer branching)
- Insufficient solver convergence (unconverged forward pass → meaningless gradients)
- Numerical precision (float32 gradients through long unrolls accumulate error)
- Step size too large or too small for FD (try multiple eps values)

### Conservation Through Gradients

If the forward solver conserves a quantity (energy, mass, charge), verify the gradient does not break conservation:

```
1. Run forward solve → check conservation balance
2. Run forward + backward → check conservation balance is unchanged
3. Take one gradient step → re-run forward → check conservation still holds
```

If conservation breaks after a gradient step, the step size is too large or the constraint projection is incorrect.

</verification_protocol>

<failure_modes>

## Common Failure Modes

### Tape Memory Exhaustion

Each solver iteration allocates intermediate arrays on the tape. For iterative solvers:

```
Memory ≈ N_iterations × grid_size × sizeof(float)

Example: 800 Jacobi iterations on 160×140 grid
  = 800 × 22400 × 4 bytes = 72 MB

Mitigation:
- Reduce grid resolution for gradient computation (if convergence allows)
- Use checkpointing: store every k-th state, recompute between checkpoints
- Switch to adjoint method for very long unrolls (>10000 iterations)
```

### Vanishing/Exploding Gradients Through Long Unrolls

Gradients through N iterations of an iterative solver behave like gradients through an N-layer network. The effective condition number compounds.

```
Symptoms:
- Gradient norm grows exponentially with iteration count → exploding
- Gradient norm decays to zero → vanishing
- Optimization makes progress for few iterations then diverges

Mitigation:
- Use an adaptive optimizer (Adam) that normalizes gradient magnitudes
- Verify gradient norm is stable across different iteration counts
- If gradients explode: solver may not be converging (fix forward solver first)
```

### Discrete Operations Breaking the Tape

Operations that are not differentiable produce zero or undefined gradients:

```
Problematic:
- if/else branching on tensor values (gradient is zero through the branch not taken)
- Integer indexing computed from parameters
- Sorting, argmax, top-k
- Projection/clamping to constraints (gradient is zero when active)

Mitigation:
- Use smooth approximations: softmax instead of argmax, sigmoid instead of step
- For constraint projection: accept that gradients through the projection are approximate
- Verify with FD comparison at the specific parameter point
```

</failure_modes>

<tools_landscape>

## Tool Landscape

| Framework | Strengths | Best for |
|-----------|----------|----------|
| **NVIDIA Warp** | Native spatial types (meshes, volumes, hash grids), `wp.Tape` AD, CPU/GPU, Python kernel syntax | Geometry-aware simulations, robotics, engineering optimization |
| **JAX** | Functional transforms (`jit`, `grad`, `vmap`), XLA compilation, ecosystem (Flax, Optax) | Research, ML-physics hybrid, batched parameter sweeps |
| **PyTorch** | Familiar API, huge ecosystem, dynamic graphs | ML-heavy pipelines, neural surrogates, learned simulators |
| **Taichi** | Megakernel compilation, spatial sparse data structures, `ti.ad` | Graphics, MPM, particle-based simulation |
| **DiffTaichi** | Taichi + differentiable programming focus | Soft-body optimization, differentiable rendering |
| **FEniCS/dolfin-adjoint** | FEM with automatic adjoint derivation | PDE-constrained optimization, topology optimization |

**Selection guidance:** If your simulation involves meshes, collisions, or spatial queries → Warp or Taichi. If you need batched parameter sweeps or ML integration → JAX. If the problem is a standard PDE on a fixed domain → FEniCS/dolfin-adjoint gives you the adjoint for free.

**Containerization:** GPU simulation frameworks (Warp, Taichi, JAX with CUDA) require specific dependencies that cannot be assumed in the host environment. Always run these in Docker containers. See `templates/compute/warp-simulation.md` for a ready-to-use template with CPU and GPU Dockerfiles, a run script, and environment variable conventions.

</tools_landscape>

<optimization_loop>

## Standard Optimization Loop

The common pattern across all differentiable simulation work:

```
1. DEFINE forward solver: parameters → physics state → scalar objective
2. VALIDATE forward solver independently (conservation, convergence, limiting cases)
3. VERIFY gradients (AD vs FD comparison at a test point)
4. CHOOSE optimizer:
   - Adam for noisy/ill-conditioned gradients (most common)
   - L-BFGS for smooth, well-conditioned problems
   - Projected gradient descent when constraints are simple (box bounds)
5. RUN optimization with:
   - Constraint enforcement after each step (project back to feasible set)
   - Loss monitoring with early stopping (patience = 10 steps typical)
   - Multiple random initializations to explore multimodality
6. VALIDATE result:
   - Re-run forward solver at optimal parameters with higher fidelity
   - Check physics constraints are satisfied (not just approximately)
   - Compare against baseline (unoptimized) to quantify improvement
```

</optimization_loop>
