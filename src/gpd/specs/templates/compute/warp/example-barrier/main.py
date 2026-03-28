"""Optimize thermal barrier position on a 2D plate using Warp autodiff.

Question: Where to place an insulating barrier to best shield a probe from heat?
Answer: Aligned with the probe, between source and probe.
"""

import json
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import warp as wp

wp.init()

NX, NY = 30, 20
N_CELLS = NX * NY
PROBE_IDX = 8 * NY + 10  # cell (8, 10)


@wp.kernel
def build_k(k: wp.array(dtype=wp.float32), by: wp.array(dtype=wp.float32), ny: int):
    """Conductivity: 1.0 base, Gaussian low-k barrier at column 10. No branching."""
    tid = wp.tid()
    i = tid // ny; j = tid - i * ny
    dx = (float(i) - 10.0) / 1.5
    dy = (float(j) - by[0]) / 4.0
    k[tid] = 1.0 - 0.95 * wp.exp(-2.0 * (dx * dx + dy * dy))


@wp.kernel
def jacobi_2d(T_in: wp.array(dtype=wp.float32), T_out: wp.array(dtype=wp.float32),
              k: wp.array(dtype=wp.float32), Q: wp.array(dtype=wp.float32),
              nx: int, ny: int):
    tid = wp.tid()
    i = tid // ny; j = tid - i * ny
    left = T_in[wp.max(i - 1, 0) * ny + j]       # clamped indices
    right = T_in[wp.min(i + 1, nx - 1) * ny + j]
    down = T_in[i * ny + wp.max(j - 1, 0)]
    up = T_in[i * ny + wp.min(j + 1, ny - 1)]
    kc = k[tid]
    T_out[tid] = (kc * (left + right + down + up) + Q[tid]) / (4.0 * kc + 0.1)


@wp.kernel
def probe_loss(T: wp.array(dtype=wp.float32), idx: int, loss: wp.array(dtype=wp.float32)):
    loss[0] = T[idx]


# Heat source on left 3 columns
Q_np = np.zeros(N_CELLS, dtype=np.float32)
for i in range(3):
    for j in range(NY):
        Q_np[i * NY + j] = 10.0
Q_wp = wp.array(Q_np, dtype=wp.float32, device="cpu")


def solve(by_np, grad=False):
    by = wp.array(by_np, dtype=wp.float32, device="cpu", requires_grad=grad)
    tape = wp.Tape() if grad else None
    with (tape if tape else nullcontext()):
        k = wp.zeros(N_CELLS, dtype=wp.float32, device="cpu", requires_grad=grad)
        wp.launch(build_k, dim=N_CELLS, inputs=[k, by, NY], device="cpu")
        T = wp.zeros(N_CELLS, dtype=wp.float32, device="cpu", requires_grad=grad)
        for _ in range(600):
            T2 = wp.zeros(N_CELLS, dtype=wp.float32, device="cpu", requires_grad=grad)
            wp.launch(jacobi_2d, dim=N_CELLS, inputs=[T, T2, k, Q_wp, NX, NY], device="cpu")
            T = T2
        loss = wp.zeros(1, dtype=wp.float32, device="cpu", requires_grad=grad)
        wp.launch(probe_loss, dim=1, inputs=[T, PROBE_IDX], outputs=[loss], device="cpu")
    wp.synchronize()
    return T, loss, tape, by


by = np.array([5.0], dtype=np.float32)  # start low, probe is at y=10
ma, va = np.zeros(1), np.zeros(1)

for step in range(40):
    T, loss, tape, sp = solve(by, grad=True)
    tape.backward(loss); wp.synchronize()
    g = float(sp.grad.numpy()[0]); tape.zero()
    tp = float(T.numpy().ravel()[PROBE_IDX])
    if step % 5 == 0:
        print(f"  step {step:02d}: barrier_y={by[0]:5.1f}  T_probe={tp:.3f}")
    ma = 0.9 * ma + 0.1 * g
    va = 0.999 * va + 0.001 * g ** 2
    mh = ma / (1 - 0.9 ** (step + 1))
    vh = va / (1 - 0.999 ** (step + 1))
    by = np.clip(by - 0.3 * mh / (np.sqrt(vh) + 1e-8), 2.0, NY - 2.0).astype(np.float32)

# Gradient validation
ty = np.array([8.0], dtype=np.float32)
_, la, ta, pa = solve(ty, grad=True); ta.backward(la); wp.synchronize()
g_ad = float(pa.grad.numpy()[0])
_, lp, _, _ = solve(ty + 0.1); _, lm, _, _ = solve(ty - 0.1)
g_fd = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / 0.2
rel = abs(g_ad - g_fd) / (abs(g_fd) + 1e-8)

print(f"\n  Gradient check: rel_err={rel:.4f} {'PASS' if rel < 0.15 else 'FAIL'}")
print(f"  Result: barrier at y={by[0]:.1f} (probe at y=10)")

Path("/app/output").mkdir(parents=True, exist_ok=True)
Path("/app/output/metrics.json").write_text(json.dumps({
    "barrier_y": round(float(by[0]), 1),
    "gradient_check_pass": bool(rel < 0.15),
}))
