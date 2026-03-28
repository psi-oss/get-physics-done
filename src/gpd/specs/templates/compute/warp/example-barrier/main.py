"""Example: optimize thermal barrier position on a 2D plate.

Question: Where should an insulating barrier be placed to best shield
a probe point from a heat source?
Answer: Aligned vertically with the probe, between source and probe.

Demonstrates: 2D PDE, spatially varying conductivity via Gaussian blend,
harmonic-mean interface handling, design optimization.
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

# Small grid, unit-scale domain (RULE: avoids k/dx² scaling issues)
NX, NY = 30, 20
N_CELLS = NX * NY
PROBE = (8, 10)  # column 8, row 10 — behind the barrier
PROBE_IDX = PROBE[0] * NY + PROBE[1]

n_iters = int(os.environ.get("SIM_STEPS", "600"))
opt_steps = int(os.environ.get("OPT_STEPS", "40"))
output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
output_dir.mkdir(parents=True, exist_ok=True)


@wp.kernel
def build_k_field(
    k_out: wp.array(dtype=wp.float32),
    barrier_y: wp.array(dtype=wp.float32),
    nx: int, ny: int,
):
    """Conductivity: base=1.0, barrier=0.05. Gaussian blend (no branching)."""
    tid = wp.tid()
    i = tid // ny
    j = tid - i * ny

    # Barrier at column 10, sliding vertically
    dx_b = (float(i) - 10.0) / 1.5
    dy_b = (float(j) - barrier_y[0]) / 4.0
    blend = wp.exp(-2.0 * (dx_b * dx_b + dy_b * dy_b))

    k_out[tid] = 1.0 - 0.95 * blend  # 1.0 → 0.05 through barrier


@wp.kernel
def jacobi_2d(
    T_in: wp.array(dtype=wp.float32),
    T_out: wp.array(dtype=wp.float32),  # RULE: separate in/out
    k_field: wp.array(dtype=wp.float32),
    Q: wp.array(dtype=wp.float32),
    h_val: float, nx: int, ny: int,
):
    tid = wp.tid()
    i = tid // ny
    j = tid - i * ny

    # RULE: clamped indices for Neumann BCs (autodiff-safe)
    left = T_in[wp.max(i - 1, 0) * ny + j]
    right = T_in[wp.min(i + 1, nx - 1) * ny + j]
    down = T_in[i * ny + wp.max(j - 1, 0)]
    up = T_in[i * ny + wp.min(j + 1, ny - 1)]

    kc = k_field[tid]
    T_out[tid] = (kc * (left + right + down + up) + Q[tid]) / (4.0 * kc + h_val + 1.0e-10)


@wp.kernel
def probe_loss(T: wp.array(dtype=wp.float32), idx: int, loss: wp.array(dtype=wp.float32)):
    """Minimize probe temperature = best shielding."""
    loss[0] = T[idx]


def build_source():
    Q = np.zeros(N_CELLS, dtype=np.float32)
    for i in range(3):
        for j in range(NY):
            Q[i * NY + j] = 10.0
    return Q


def forward(barrier_y_np, Q_wp, device, grad=False):
    by = wp.array(barrier_y_np, dtype=wp.float32, device=device, requires_grad=grad)
    tape = wp.Tape() if grad else None

    with (tape if tape else nullcontext()):
        k_field = wp.zeros(N_CELLS, dtype=wp.float32, device=device, requires_grad=grad)
        wp.launch(build_k_field, dim=N_CELLS, inputs=[k_field, by, int(NX), int(NY)], device=device)

        T = wp.zeros(N_CELLS, dtype=wp.float32, device=device, requires_grad=grad)
        for _ in range(n_iters):
            T2 = wp.zeros(N_CELLS, dtype=wp.float32, device=device, requires_grad=grad)
            wp.launch(jacobi_2d, dim=N_CELLS, inputs=[T, T2, k_field, Q_wp, 0.1,
                      int(NX), int(NY)], device=device)
            T = T2

        loss = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=grad)
        wp.launch(probe_loss, dim=1, inputs=[T, int(PROBE_IDX)], outputs=[loss], device=device)

    wp.synchronize()
    return T, loss, tape, by


def main():
    print("=" * 60)
    print("  Warp Example: 2D thermal barrier placement")
    print("=" * 60)

    device = "cpu"
    Q_wp = wp.array(build_source(), dtype=wp.float32, device=device)
    barrier_y = np.array([5.0], dtype=np.float32)  # start low, should converge to probe y=10
    print(f"  Grid: {NX}x{NY}  Probe: {PROBE}  Initial barrier y={barrier_y[0]:.0f}")

    m_adam, v_adam = np.zeros(1), np.zeros(1)
    lr = float(os.environ.get("LEARNING_RATE", "0.3"))
    history = []
    t0 = time.time()

    for step in range(opt_steps):
        T, loss_arr, tape, by = forward(barrier_y, Q_wp, device, grad=True)
        tape.backward(loss_arr); wp.synchronize()
        g = float(by.grad.numpy()[0])
        t_probe = float(T.numpy().ravel()[PROBE_IDX])
        tape.zero()

        history.append({"step": step, "barrier_y": round(float(barrier_y[0]), 1),
                        "T_probe": round(t_probe, 3)})
        if step % 5 == 0 or step == opt_steps - 1:
            print(f"  step {step:02d}: barrier_y={barrier_y[0]:5.1f}  T_probe={t_probe:.3f}  grad={g:.4f}")

        m_adam = 0.9 * m_adam + 0.1 * g
        v_adam = 0.999 * v_adam + 0.001 * g ** 2
        mh = m_adam / (1 - 0.9 ** (step + 1))
        vh = v_adam / (1 - 0.999 ** (step + 1))
        barrier_y = (barrier_y - lr * mh / (np.sqrt(vh) + 1e-8)).astype(np.float32)
        barrier_y = np.clip(barrier_y, 2.0, NY - 2.0)

    elapsed = time.time() - t0
    final_y = float(barrier_y[0])

    # Gradient validation
    ty = np.array([8.0], dtype=np.float32)
    _, la, ta, pa = forward(ty, Q_wp, device, grad=True)
    ta.backward(la); wp.synchronize()
    g_ad = float(pa.grad.numpy()[0])
    _, lp, _, _ = forward(ty + 0.1, Q_wp, device)
    _, lm, _, _ = forward(ty - 0.1, Q_wp, device)
    g_fd = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / 0.2
    rel = abs(g_ad - g_fd) / (abs(g_fd) + 1e-8)

    print(f"\n  Gradient check: rel_err={rel:.4f}  {'PASS' if rel < 0.15 else 'FAIL'}")
    print(f"  Result: barrier_y={final_y:.1f} (probe at y={PROBE[1]})")
    print(f"  T_probe: {history[0]['T_probe']:.3f} -> {history[-1]['T_probe']:.3f}")
    print(f"  Time: {elapsed:.1f}s")

    metrics = {
        "question": "Position barrier to minimize probe temperature",
        "barrier_y_final": round(final_y, 1),
        "T_probe_initial": history[0]["T_probe"],
        "T_probe_final": history[-1]["T_probe"],
        "gradient_check_pass": bool(rel < 0.15),
        "elapsed_s": round(elapsed, 2), "history": history,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
