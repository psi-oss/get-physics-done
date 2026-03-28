"""Example: optimize thermal barrier position on a 2D plate.

Demonstrates differentiable simulation for 2D DESIGN OPTIMIZATION
with spatially varying material properties.

Physics: 2D steady-state heat equation with variable conductivity.
  k(x,y) * laplacian(T) + Q - h*(T) = 0

Setup: Small 2D plate with a heat source on the left and convective
cooling everywhere. A low-conductivity barrier can slide vertically.
Objective: position the barrier to MINIMIZE temperature at a probe
point on the far side of the barrier (best thermal shielding).
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

NX = 30
NY = 20
n_cells = NX * NY

n_iters = int(os.environ.get("SIM_STEPS", "600"))
opt_steps = int(os.environ.get("OPT_STEPS", "40"))
output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
output_dir.mkdir(parents=True, exist_ok=True)

# Probe is at column 8, midway vertically — right behind where the barrier sits
PROBE_IDX = 8 * NY + 10


@wp.kernel
def jacobi_2d(
    T_in: wp.array(dtype=wp.float32),
    T_out: wp.array(dtype=wp.float32),
    k_field: wp.array(dtype=wp.float32),
    Q: wp.array(dtype=wp.float32),
    h_val: float,
    nx: int, ny: int,
):
    tid = wp.tid()
    i = tid // ny
    j = tid - i * ny

    left = T_in[wp.max(i - 1, 0) * ny + j]
    right = T_in[wp.min(i + 1, nx - 1) * ny + j]
    down = T_in[i * ny + wp.max(j - 1, 0)]
    up = T_in[i * ny + wp.min(j + 1, ny - 1)]

    kc = k_field[tid]
    diff = kc * (left + right + down + up)
    diag = 4.0 * kc

    T_out[tid] = (diff + Q[tid]) / (diag + h_val + 1.0e-10)


@wp.kernel
def build_k_field(
    k_out: wp.array(dtype=wp.float32),
    barrier_y: wp.array(dtype=wp.float32),
    nx: int, ny: int,
):
    """Conductivity field: base=1.0 with a Gaussian low-k barrier at column 10."""
    tid = wp.tid()
    i = tid // ny
    j = tid - i * ny

    # Barrier centered at column 10, sliding vertically
    dx_b = (float(i) - 10.0) / 1.5
    dy_b = (float(j) - barrier_y[0]) / 4.0
    blend = wp.exp(-2.0 * (dx_b * dx_b + dy_b * dy_b))

    # k goes from 1.0 (base) to 0.05 (barrier)
    k_out[tid] = 1.0 - 0.95 * blend


@wp.kernel
def probe_loss(T: wp.array(dtype=wp.float32), idx: int, loss: wp.array(dtype=wp.float32)):
    """Minimize probe temperature = find best shielding position."""
    loss[0] = T[idx]


def build_source():
    """Heat source: strong on left 3 columns."""
    Q = np.zeros(n_cells, dtype=np.float32)
    for i in range(3):
        for j in range(NY):
            Q[i * NY + j] = 10.0
    return Q


def forward(barrier_y_np, Q_wp, device, grad=False):
    by = wp.array(barrier_y_np, dtype=wp.float32, device=device, requires_grad=grad)
    tape = wp.Tape() if grad else None

    with (tape if tape else nullcontext()):
        k_field = wp.zeros(n_cells, dtype=wp.float32, device=device, requires_grad=grad)
        wp.launch(build_k_field, dim=n_cells, inputs=[k_field, by, int(NX), int(NY)], device=device)

        T = wp.zeros(n_cells, dtype=wp.float32, device=device, requires_grad=grad)
        for _ in range(n_iters):
            T2 = wp.zeros(n_cells, dtype=wp.float32, device=device, requires_grad=grad)
            wp.launch(jacobi_2d, dim=n_cells, inputs=[T, T2, k_field, Q_wp, 0.1, int(NX), int(NY)], device=device)
            T = T2

        loss = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=grad)
        wp.launch(probe_loss, dim=1, inputs=[T, int(PROBE_IDX)], outputs=[loss], device=device)

    wp.synchronize()
    return T, loss, tape, by


def main():
    print("=" * 60)
    print("  Warp Example: 2D thermal barrier placement")
    print("  Minimize probe temperature via optimal shielding")
    print("=" * 60)

    device = "cpu"
    Q_wp = wp.array(build_source(), dtype=wp.float32, device=device)

    # Start barrier off-center (y=5), probe is at y=10
    barrier_y_np = np.array([5.0], dtype=np.float32)
    print(f"  Grid: {NX}x{NY}  Probe at cell ({PROBE_IDX // NY}, {PROBE_IDX % NY})")
    print(f"  Initial barrier y={barrier_y_np[0]:.0f}")

    # Sanity check
    T_test, _, _, _ = forward(barrier_y_np, Q_wp, device)
    T_np = T_test.numpy().reshape(NX, NY)
    print(f"  Sanity: T_max={T_np.max():.3f}  T_probe={T_np.ravel()[PROBE_IDX]:.3f}")

    m_adam, v_adam = np.zeros(1), np.zeros(1)
    lr = float(os.environ.get("LEARNING_RATE", "0.3"))
    history = []
    t0 = time.time()

    for step in range(opt_steps):
        T, loss_arr, tape, by = forward(barrier_y_np, Q_wp, device, grad=True)
        tape.backward(loss_arr); wp.synchronize()
        g = float(by.grad.numpy()[0])
        lo = float(loss_arr.numpy()[0])
        T_np = T.numpy().reshape(NX, NY)
        t_probe = float(T_np.ravel()[PROBE_IDX])
        tape.zero()

        history.append({"step": step, "barrier_y": round(float(barrier_y_np[0]), 2),
                        "T_probe": round(t_probe, 4), "loss": round(lo, 4), "grad": round(g, 4)})

        if step % 5 == 0 or step == opt_steps - 1:
            print(f"  step {step:02d}: barrier_y={barrier_y_np[0]:5.1f}  T_probe={t_probe:.4f}  grad={g:.4f}")

        m_adam = 0.9 * m_adam + 0.1 * g
        v_adam = 0.999 * v_adam + 0.001 * g ** 2
        mh = m_adam / (1 - 0.9 ** (step + 1))
        vh = v_adam / (1 - 0.999 ** (step + 1))
        barrier_y_np = barrier_y_np - lr * mh / (np.sqrt(vh) + 1e-8)
        barrier_y_np = np.clip(barrier_y_np, 2.0, NY - 2.0).astype(np.float32)

    elapsed = time.time() - t0

    # Gradient validation
    test_y = np.array([8.0], dtype=np.float32)
    eps = 0.1
    _, la, ta, pa = forward(test_y, Q_wp, device, grad=True)
    ta.backward(la); wp.synchronize()
    g_ad = float(pa.grad.numpy()[0])
    _, lp, _, _ = forward(test_y + eps, Q_wp, device)
    _, lm, _, _ = forward(test_y - eps, Q_wp, device)
    g_fd = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / (2 * eps)
    rel = abs(g_ad - g_fd) / (abs(g_fd) + 1e-8)

    print(f"\n  Gradient check: AD={g_ad:.4f}  FD={g_fd:.4f}  rel_err={rel:.4f}  {'PASS' if rel < 0.15 else 'FAIL'}")
    print(f"  Result: barrier_y={barrier_y_np[0]:.1f}  T_probe: {history[0]['T_probe']:.4f} -> {history[-1]['T_probe']:.4f}")
    print(f"  Time: {elapsed:.1f}s")

    metrics = {
        "question": "Position barrier to minimize probe temperature (best shielding)",
        "grid": {"nx": NX, "ny": NY},
        "barrier_y_final": round(float(barrier_y_np[0]), 2),
        "T_probe_initial": history[0]["T_probe"],
        "T_probe_final": history[-1]["T_probe"],
        "gradient_check_pass": bool(rel < 0.15),
        "elapsed_s": round(elapsed, 2),
        "history": history,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"  Output: {output_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()
