"""Example: optimal heat source placement on a 1D rod using Warp autodiff.

Demonstrates the differentiable simulation workflow:
  1. Define a forward PDE solver as Warp kernels
  2. Compute gradients via wp.Tape (automatic differentiation)
  3. Optimize with Adam
  4. Validate gradients against finite differences
  5. Write machine-readable results to output/metrics.json

Physics: 1D steady-state heat equation with convective cooling.
  k * d²T/dx² + Q(x) - h*(T - T_amb) = 0
  BC: Neumann (zero flux) at both endpoints.
  Source: Gaussian centered at optimizable position.

Question: Where should the source be placed to minimize the peak temperature?
Answer: The center (x = L/2), by symmetry of the convection-only problem.
"""

from __future__ import annotations

import json
import os
import time
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import warp as wp

wp.init()

# --- Grid and physics ---
N = 200
L = 1.0
k = 1.0          # conductivity
h_conv = 0.1     # convective loss
Q_amp = 50.0     # source amplitude
sigma = 0.08     # source width
T_amb = 0.0

n_iters = int(os.environ.get("SIM_STEPS", "500"))
opt_steps = int(os.environ.get("OPT_STEPS", "50"))
output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
output_dir.mkdir(parents=True, exist_ok=True)


@wp.kernel
def jacobi_step(
    T_in: wp.array(dtype=wp.float32),
    T_out: wp.array(dtype=wp.float32),
    source_pos: wp.array(dtype=wp.float32),
    dx: float, k_val: float, h_val: float,
    q_amp: float, sigma_val: float, t_amb: float, n: int,
):
    i = wp.tid()
    x = float(i) * dx

    # Neumann BC via clamped indices (autodiff-safe, no branching)
    left = T_in[wp.max(i - 1, 0)]
    right = T_in[wp.min(i + 1, n - 1)]

    # Gaussian heat source
    dist = x - source_pos[0]
    q = q_amp * wp.exp(-0.5 * dist * dist / (sigma_val * sigma_val))

    cx = k_val / (dx * dx)
    T_out[i] = (cx * (left + right) + q + h_val * t_amb) / (2.0 * cx + h_val)


@wp.kernel
def softmax_loss(
    T: wp.array(dtype=wp.float32),
    n: int,
    loss: wp.array(dtype=wp.float32),
):
    """Differentiable approximation to max(T) via log-sum-exp."""
    i = wp.tid()
    wp.atomic_add(loss, 0, wp.exp(T[i] * 20.0))


def forward(pos_np, device, grad=False):
    dx = L / (N - 1)
    sp = wp.array(pos_np, dtype=wp.float32, device=device, requires_grad=grad)
    tape = wp.Tape() if grad else None

    with (tape if tape else nullcontext()):
        T = wp.array(np.full(N, T_amb, dtype=np.float32), dtype=wp.float32,
                     device=device, requires_grad=grad)
        for _ in range(n_iters):
            T2 = wp.zeros(N, dtype=wp.float32, device=device, requires_grad=grad)
            wp.launch(jacobi_step, dim=N, inputs=[
                T, T2, sp, float(dx), float(k), float(h_conv),
                float(Q_amp), float(sigma), float(T_amb), int(N)], device=device)
            T = T2
        loss = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=grad)
        wp.launch(softmax_loss, dim=N, inputs=[T, int(N)], outputs=[loss], device=device)

    wp.synchronize()
    return T, loss, tape, sp


def main():
    print("=" * 60)
    print("  Warp Example: Optimal heat source placement (1D rod)")
    print("=" * 60)

    device = "cpu"
    pos = np.array([0.25], dtype=np.float32)  # start off-center

    # Adam state
    m, v = np.zeros(1), np.zeros(1)
    lr, beta1, beta2 = 0.01, 0.9, 0.999
    history = []
    t0 = time.time()

    for step in range(opt_steps):
        T, loss_arr, tape, sp = forward(pos, device, grad=True)
        tape.backward(loss_arr)
        wp.synchronize()
        g = float(sp.grad.numpy()[0])
        lo = float(loss_arr.numpy()[0])
        mx = float(T.numpy().max())
        tape.zero()

        history.append({"step": step, "x": round(float(pos[0]), 4),
                        "max_T": round(mx, 4), "loss": round(lo, 2), "grad": round(g, 4)})
        if step % 10 == 0 or step == opt_steps - 1:
            print(f"  step {step:02d}: x={pos[0]:.3f}  T_max={mx:.4f}  grad={g:.2f}")

        m = beta1 * m + (1 - beta1) * g
        v = beta2 * v + (1 - beta2) * g ** 2
        mh = m / (1 - beta1 ** (step + 1))
        vh = v / (1 - beta2 ** (step + 1))
        pos = pos - lr * mh / (np.sqrt(vh) + 1e-8)
        pos = np.clip(pos, 0.05, L - 0.05).astype(np.float32)

    elapsed = time.time() - t0
    final = float(pos[0])

    # --- Gradient validation (AD vs FD) ---
    test = np.array([0.3], dtype=np.float32)
    eps = 0.001
    _, la, ta, sa = forward(test, device, grad=True)
    ta.backward(la); wp.synchronize()
    g_ad = float(sa.grad.numpy()[0])
    _, lp, _, _ = forward(test + eps, device)
    _, lm, _, _ = forward(test - eps, device)
    g_fd = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / (2 * eps)
    rel = abs(g_ad - g_fd) / (abs(g_fd) + 1e-8)

    print(f"\n  Gradient check: AD={g_ad:.4f}  FD={g_fd:.4f}  rel_err={rel:.4f}  {'PASS' if rel < 0.1 else 'FAIL'}")
    print(f"  Result: x={final:.3f}  (optimal: 0.500)  error={abs(final - 0.5):.3f}")
    print(f"  Time: {elapsed:.1f}s")

    metrics = {
        "question": "Optimal heat source position to minimize peak temperature",
        "analytical_answer": 0.5,
        "numerical_answer": round(final, 4),
        "error": round(abs(final - 0.5), 4),
        "gradient_check_pass": rel < 0.1,
        "gradient_relative_error": round(rel, 6),
        "elapsed_s": round(elapsed, 2),
        "history": history,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"  Output: {output_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()
