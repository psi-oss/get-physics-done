"""Example: optimal heat source placement on a 1D rod using Warp autodiff.

Question: Where should a point heat source be placed on a 1D rod with
convective cooling to minimize the peak temperature?
Answer: The center (x = L/2), by symmetry.

Demonstrates: PDE solver as Warp kernels, wp.Tape autodiff, Adam optimizer,
gradient validation (AD vs FD), parameterization via env vars.
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

# Dimensionless parameters (unit domain avoids scaling issues with k/dx²)
N = 200
L = 1.0
K = 1.0
H_CONV = 0.1
Q_AMP = 50.0
SIGMA = 0.08
T_AMB = 0.0

n_iters = int(os.environ.get("SIM_STEPS", "500"))
opt_steps = int(os.environ.get("OPT_STEPS", "50"))
output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
output_dir.mkdir(parents=True, exist_ok=True)


@wp.kernel
def jacobi_1d(
    T_in: wp.array(dtype=wp.float32),
    T_out: wp.array(dtype=wp.float32),   # RULE: separate in/out arrays for autodiff
    source_pos: wp.array(dtype=wp.float32),
    dx: float, k_val: float, h_val: float,
    q_amp: float, sigma_val: float, n: int,
):
    i = wp.tid()
    x = float(i) * dx

    # RULE: clamped indices instead of if/else (branching kills gradients)
    left = T_in[wp.max(i - 1, 0)]
    right = T_in[wp.min(i + 1, n - 1)]

    dist = x - source_pos[0]
    q = q_amp * wp.exp(-0.5 * dist * dist / (sigma_val * sigma_val))

    cx = k_val / (dx * dx)
    T_out[i] = (cx * (left + right) + q) / (2.0 * cx + h_val)


@wp.kernel
def softmax_loss(T: wp.array(dtype=wp.float32), n: int, loss: wp.array(dtype=wp.float32)):
    """Soft-max: scale=20 makes the hottest cell dominate (approximates max(T))."""
    i = wp.tid()
    wp.atomic_add(loss, 0, wp.exp(T[i] * 20.0))


def forward(pos_np, device, grad=False):
    dx = L / (N - 1)
    sp = wp.array(pos_np, dtype=wp.float32, device=device, requires_grad=grad)
    tape = wp.Tape() if grad else None

    with (tape if tape else nullcontext()):
        T = wp.array(np.zeros(N, dtype=np.float32), dtype=wp.float32,
                     device=device, requires_grad=grad)
        for _ in range(n_iters):  # RULE: same iteration count for forward and gradient
            T2 = wp.zeros(N, dtype=wp.float32, device=device, requires_grad=grad)
            wp.launch(jacobi_1d, dim=N, inputs=[T, T2, sp, float(dx), float(K),
                      float(H_CONV), float(Q_AMP), float(SIGMA), int(N)], device=device)
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
                        "max_T": round(mx, 4), "loss": round(lo, 2)})
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

    # Gradient validation
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
        "analytical_answer": 0.5, "numerical_answer": round(final, 4),
        "error": round(abs(final - 0.5), 4),
        "gradient_check_pass": rel < 0.1,
        "elapsed_s": round(elapsed, 2), "history": history,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
