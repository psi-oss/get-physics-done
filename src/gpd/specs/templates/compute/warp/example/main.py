"""Optimal heat source placement on a 1D rod using Warp autodiff.

Question: Where to place a heat source to minimize peak temperature?
Answer: Center of the rod (x = L/2), by symmetry.
"""

import json
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import warp as wp

wp.init()

N, L, K, H, Q, SIGMA = 200, 1.0, 1.0, 0.1, 50.0, 0.08


@wp.kernel
def jacobi(
    T_in: wp.array(dtype=wp.float32),
    T_out: wp.array(dtype=wp.float32),
    pos: wp.array(dtype=wp.float32),
    dx: float,
    n: int,
):
    i = wp.tid()
    x = float(i) * dx
    left = T_in[wp.max(i - 1, 0)]  # clamped index: no branching
    right = T_in[wp.min(i + 1, n - 1)]
    dist = x - pos[0]
    q = 50.0 * wp.exp(-0.5 * dist * dist / (0.08 * 0.08))
    cx = 1.0 / (dx * dx)
    T_out[i] = (cx * (left + right) + q) / (2.0 * cx + 0.1)


@wp.kernel
def softmax_loss(T: wp.array(dtype=wp.float32), loss: wp.array(dtype=wp.float32)):
    wp.atomic_add(loss, 0, wp.exp(T[wp.tid()] * 20.0))


def solve(pos_np, grad=False):
    dx = L / (N - 1)
    sp = wp.array(pos_np, dtype=wp.float32, device="cpu", requires_grad=grad)
    tape = wp.Tape() if grad else None
    with tape if tape else nullcontext():
        T = wp.zeros(N, dtype=wp.float32, device="cpu", requires_grad=grad)
        for _ in range(500):
            T2 = wp.zeros(N, dtype=wp.float32, device="cpu", requires_grad=grad)
            wp.launch(jacobi, dim=N, inputs=[T, T2, sp, float(dx), N], device="cpu")
            T = T2
        loss = wp.zeros(1, dtype=wp.float32, device="cpu", requires_grad=grad)
        wp.launch(softmax_loss, dim=N, inputs=[T], outputs=[loss], device="cpu")
    wp.synchronize()
    return T, loss, tape, sp


pos = np.array([0.25], dtype=np.float32)
m, v = np.zeros(1), np.zeros(1)

for step in range(50):
    T, loss, tape, sp = solve(pos, grad=True)
    tape.backward(loss)
    wp.synchronize()
    g = float(sp.grad.numpy()[0])
    tape.zero()
    if step % 10 == 0:
        print(f"  step {step:02d}: x={pos[0]:.3f}  T_max={T.numpy().max():.4f}")
    m = 0.9 * m + 0.1 * g
    v = 0.999 * v + 0.001 * g**2
    mh = m / (1 - 0.9 ** (step + 1))
    vh = v / (1 - 0.999 ** (step + 1))
    pos = np.clip(pos - 0.01 * mh / (np.sqrt(vh) + 1e-8), 0.05, 0.95).astype(np.float32)

# Gradient validation
tp = np.array([0.3], dtype=np.float32)
_, la, ta, sa = solve(tp, grad=True)
ta.backward(la)
wp.synchronize()
g_ad = float(sa.grad.numpy()[0])
_, lp, _, _ = solve(tp + 0.001)
_, lm, _, _ = solve(tp - 0.001)
g_fd = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / 0.002
rel = abs(g_ad - g_fd) / (abs(g_fd) + 1e-8)

print(f"\n  Gradient check: rel_err={rel:.4f} {'PASS' if rel < 0.1 else 'FAIL'}")
print(f"  Result: x={pos[0]:.3f} (optimal: 0.500)")

Path("/app/output").mkdir(parents=True, exist_ok=True)
Path("/app/output/metrics.json").write_text(
    json.dumps(
        {
            "answer": round(float(pos[0]), 4),
            "optimal": 0.5,
            "gradient_check_pass": rel < 0.1,
        }
    )
)
