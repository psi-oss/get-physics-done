"""Recover spring constant and damping from noisy observations using Warp autodiff.

Question: Given noisy displacement data, what are k and c?
Ground truth: k=40, c=2. Initial guess: k=20, c=5.
"""

import json
from contextlib import nullcontext
from pathlib import Path

import numpy as np
import warp as wp

wp.init()

K_TRUE, C_TRUE, M, DT = 40.0, 2.0, 1.0, 0.01
N_STEPS, N_OBS = 200, 40


@wp.kernel
def euler_step(x_in: wp.array(dtype=wp.float32), v_in: wp.array(dtype=wp.float32),
               x_out: wp.array(dtype=wp.float32), v_out: wp.array(dtype=wp.float32),
               params: wp.array(dtype=wp.float32)):
    """Separate in/out arrays — in-place mutation breaks autodiff."""
    i = wp.tid()
    a = (-params[0] * x_in[i] - params[1] * v_in[i]) / 1.0
    v_out[i] = v_in[i] + 0.01 * a
    x_out[i] = x_in[i] + 0.01 * v_in[i]


@wp.kernel
def copy_scalar(src: wp.array(dtype=wp.float32), dst: wp.array(dtype=wp.float32), idx: int):
    dst[idx] = src[0]


@wp.kernel
def mse(x_sim: wp.array(dtype=wp.float32), x_obs: wp.array(dtype=wp.float32),
        n: int, loss: wp.array(dtype=wp.float32)):
    i = wp.tid()
    d = x_sim[i] - x_obs[i]
    wp.atomic_add(loss, 0, d * d / float(n))


# Generate ground-truth observations
rng = np.random.default_rng(42)
t = np.arange(N_STEPS) * DT
omega = np.sqrt(K_TRUE / M - (C_TRUE / (2 * M)) ** 2)
x_true = np.exp(-C_TRUE / (2 * M) * t) * np.cos(omega * t)
obs_idx = np.linspace(0, N_STEPS - 1, N_OBS, dtype=int)
x_obs = wp.array((x_true[obs_idx] + rng.normal(0, 0.02, N_OBS)).astype(np.float32),
                 dtype=wp.float32, device="cpu")


def solve(params_np, grad=False):
    params = wp.array(params_np, dtype=wp.float32, device="cpu", requires_grad=grad)
    tape = wp.Tape() if grad else None
    with (tape if tape else nullcontext()):
        x = wp.array([1.0], dtype=wp.float32, device="cpu", requires_grad=grad)
        v = wp.array([0.0], dtype=wp.float32, device="cpu", requires_grad=grad)
        x_at = wp.zeros(N_OBS, dtype=wp.float32, device="cpu", requires_grad=grad)
        ptr = 0
        for step in range(N_STEPS):
            if ptr < N_OBS and step == obs_idx[ptr]:
                wp.launch(copy_scalar, dim=1, inputs=[x, x_at, int(ptr)], device="cpu")
                ptr += 1
            xn = wp.zeros(1, dtype=wp.float32, device="cpu", requires_grad=grad)
            vn = wp.zeros(1, dtype=wp.float32, device="cpu", requires_grad=grad)
            wp.launch(euler_step, dim=1, inputs=[x, v, xn, vn, params], device="cpu")
            x, v = xn, vn
        loss = wp.zeros(1, dtype=wp.float32, device="cpu", requires_grad=grad)
        wp.launch(mse, dim=N_OBS, inputs=[x_at, x_obs, N_OBS], outputs=[loss], device="cpu")
    wp.synchronize()
    return loss, tape, params


p = np.array([20.0, 5.0], dtype=np.float32)
ma, va = np.zeros(2), np.zeros(2)

for step in range(200):
    loss, tape, sp = solve(p, grad=True)
    tape.backward(loss); wp.synchronize()
    g = sp.grad.numpy().copy().astype(np.float64); tape.zero()
    gn = np.linalg.norm(g)
    if gn > 10.0: g = g * 10.0 / gn  # gradient clipping for long unrolls
    if step % 25 == 0:
        print(f"  step {step:3d}: k={p[0]:6.2f}  c={p[1]:5.2f}  loss={float(loss.numpy()[0]):.6f}")
    ma = 0.9 * ma + 0.1 * g
    va = 0.999 * va + 0.001 * g ** 2
    mh = ma / (1 - 0.9 ** (step + 1))
    vh = va / (1 - 0.999 ** (step + 1))
    p = np.clip(p - 0.15 * mh / (np.sqrt(vh) + 1e-8), [1, 0.01], [200, 50]).astype(np.float32)

# Gradient validation
tp = np.array([35.0, 3.0], dtype=np.float32)
la, ta, pa = solve(tp, grad=True); ta.backward(la); wp.synchronize()
g_ad = pa.grad.numpy().copy()
g_fd = np.zeros(2)
for i in range(2):
    pp, pm = tp.copy(), tp.copy(); pp[i] += 0.05; pm[i] -= 0.05
    lp, _, _ = solve(pp); lm, _, _ = solve(pm)
    g_fd[i] = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / 0.1
rel = np.max(np.abs(g_ad - g_fd) / (np.abs(g_fd) + 1e-8))

print(f"\n  Gradient check: rel_err={rel:.4f} {'PASS' if rel < 0.15 else 'FAIL'}")
print(f"  Result: k={p[0]:.1f} (true {K_TRUE})  c={p[1]:.1f} (true {C_TRUE})")

Path("/app/output").mkdir(parents=True, exist_ok=True)
Path("/app/output/metrics.json").write_text(json.dumps({
    "recovered": {"k": round(float(p[0]), 2), "c": round(float(p[1]), 2)},
    "ground_truth": {"k": K_TRUE, "c": C_TRUE},
    "gradient_check_pass": bool(rel < 0.15),
}))
