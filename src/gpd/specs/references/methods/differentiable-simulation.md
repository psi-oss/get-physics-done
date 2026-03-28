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
tier: 2
context_cost: medium
---

# Differentiable Simulation

Optimize through a physics solver using automatic differentiation. The forward solver must be correct first — gradients of wrong physics are useless.

**Related files:**
- `approximation-selection.md` — broader method selection framework
- `../verification/core/verification-numerical.md` — convergence and numerical stability
- `../../templates/compute/warp/README.md` — container template with Dockerfiles, run script, and 3 examples

---

<gradient_methods>

## Choosing a Gradient Method

| Parameters | Solver on tape? | Method | Cost |
|-----------|----------------|--------|------|
| Any | Yes | **Tape-based AD** (Warp, JAX, PyTorch) | ~2x forward |
| Any | No, adjoint derived | **Adjoint method** | ~2x forward, O(1) memory |
| ≤ 5 | No | **Finite differences** | 2N forward solves |
| > 5 | No | Derive adjoint or rewrite solver for AD | — |

**Always verify gradients** by comparing AD against finite differences at a test point. If relative error > 10%, the gradient is unreliable.

</gradient_methods>

<warp_kernel_rules>

## Warp Kernel Rules

These rules prevent the specific failures that occur when writing differentiable Warp kernels. Violating any of them produces silent wrong gradients or NaN.

**1. No in-place mutation.** `x[i] = x[i] + delta` breaks the tape. Always use separate input and output arrays per timestep:
```python
# WRONG: in-place update
v[i] = v[i] + dt * accel

# RIGHT: separate arrays
v_out[i] = v_in[i] + dt * accel
```

**2. No branching on array values.** `if i == 0: T[i] = T_amb` zeros the gradient through that branch. Use clamped indices instead:
```python
# WRONG: branch kills gradient at boundary
left = T[i-1] if i > 0 else T_amb

# RIGHT: clamped index, autodiff-safe
left = T[wp.max(i - 1, 0)]
```

**3. Same iterations for forward and backward.** Using 3000 iterations forward but 10 for the gradient tape produces noisy, unreliable gradients. Always use the same solver fidelity for both.

**4. Keep unrolls under ~500 steps.** Gradients through >500 iterations of an iterative solver often explode or vanish. Use gradient clipping (`g = g * max_norm / norm(g)`) or reduce iteration count. For long time integrations, use checkpointing.

**5. Unit scaling matters.** The Jacobi update normalizes by `k/dx²`. If `dx` is in meters (tiny) and `k` is large, then `k/dx² >> Q` and the source term has no effect. Use dimensionless or unit-scale domains, or scale Q to match `k/dx²`.

**6. Match your loss to your question.** `sum(exp(T))` minimizes total temperature. With Dirichlet BCs (T=0 at boundaries), this pushes heat sources *toward* boundaries where T is killed — the opposite of minimizing peak T. Use `sum(exp(T * scale))` with scale ≥ 10 for a soft-max approximation to `max(T)`.

</warp_kernel_rules>

<verification_protocol>

## Gradient Verification

At a representative parameter point:

```python
eps = 1e-4 * max(abs(param[i]), 1.0)
grad_fd[i] = (loss(param + eps*e_i) - loss(param - eps*e_i)) / (2*eps)
rel_err = abs(grad_ad - grad_fd) / (abs(grad_fd) + 1e-8)
# PASS: < 0.05    INVESTIGATE: 0.05-0.20    FAIL: > 0.20
```

**Common causes of mismatch:** in-place mutation, branching, unconverged solver, float32 precision through long unrolls. **Also:** if the loss value is very small (near-converged), both AD and FD gradients approach zero and relative error blows up even when gradients are qualitatively correct. Validate at a point where the loss is not near its minimum.

</verification_protocol>

<tools_landscape>

## Tool Landscape

| Framework | Best for |
|-----------|----------|
| **NVIDIA Warp** | Geometry-aware sims (meshes, volumes), engineering optimization |
| **JAX** | ML-physics hybrid, batched parameter sweeps |
| **PyTorch** | Neural surrogates, learned simulators |
| **Taichi** | Graphics, MPM, particle-based simulation |
| **FEniCS/dolfin-adjoint** | Standard PDEs, automatic adjoint |

GPU simulation frameworks require Docker containers. See `templates/compute/warp/` for ready-to-use Dockerfiles with CPU and GPU support.

</tools_landscape>

<optimization_loop>

## Standard Optimization Loop

1. **Validate forward solver** independently (conservation, convergence, plausible temperatures)
2. **Verify gradients** (AD vs FD at a test point)
3. **Optimize** with Adam (handles noisy/ill-conditioned gradients), project constraints after each step
4. **Run multiple initializations** (3-6) to explore multimodality
5. **Validate result** at higher fidelity than the optimization used

</optimization_loop>
