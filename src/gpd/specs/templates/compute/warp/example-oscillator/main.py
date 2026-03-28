"""Example: recover spring constant and damping from noisy observations.

Question: Given displacement measurements of a damped oscillator,
what are the unknown spring constant k and damping coefficient c?
Ground truth: k=40, c=2. Initial guess: k=20, c=5.

Demonstrates: ODE time-stepping, inverse problem, 2-parameter estimation,
gradient clipping for long unrolls.
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

K_TRUE, C_TRUE, M = 40.0, 2.0, 1.0
X0, V0 = 1.0, 0.0
DT = 0.01
N_STEPS = int(float(os.environ.get("T_FINAL", "2.0")) / DT)
N_OBS = 40
OBS_NOISE = 0.02

opt_steps = int(os.environ.get("OPT_STEPS", "200"))
output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
output_dir.mkdir(parents=True, exist_ok=True)


@wp.kernel
def euler_step(
    x_in: wp.array(dtype=wp.float32), v_in: wp.array(dtype=wp.float32),
    x_out: wp.array(dtype=wp.float32), v_out: wp.array(dtype=wp.float32),  # RULE: separate in/out
    params: wp.array(dtype=wp.float32), dt: float, mass: float,
):
    i = wp.tid()
    accel = (-params[0] * x_in[i] - params[1] * v_in[i]) / mass
    v_out[i] = v_in[i] + dt * accel
    x_out[i] = x_in[i] + dt * v_in[i]


@wp.kernel
def copy_scalar(src: wp.array(dtype=wp.float32), dst: wp.array(dtype=wp.float32), idx: int):
    dst[idx] = src[0]


@wp.kernel
def mse_loss(x_sim: wp.array(dtype=wp.float32), x_obs: wp.array(dtype=wp.float32),
             n: int, loss: wp.array(dtype=wp.float32)):
    i = wp.tid()
    diff = x_sim[i] - x_obs[i]
    wp.atomic_add(loss, 0, diff * diff / float(n))


def generate_observations(rng):
    t = np.arange(N_STEPS) * DT
    omega = np.sqrt(K_TRUE / M - (C_TRUE / (2 * M)) ** 2)
    gamma = C_TRUE / (2 * M)
    x_true = X0 * np.exp(-gamma * t) * np.cos(omega * t)
    obs_idx = np.linspace(0, N_STEPS - 1, N_OBS, dtype=int)
    return obs_idx, (x_true[obs_idx] + rng.normal(0, OBS_NOISE, N_OBS)).astype(np.float32)


def forward(params_np, obs_indices, x_obs_wp, device, grad=False):
    params = wp.array(params_np, dtype=wp.float32, device=device, requires_grad=grad)
    tape = wp.Tape() if grad else None

    # RULE: keep unrolls under ~500 steps (200 here)
    with (tape if tape else nullcontext()):
        x = wp.array([X0], dtype=wp.float32, device=device, requires_grad=grad)
        v = wp.array([V0], dtype=wp.float32, device=device, requires_grad=grad)
        x_at_obs = wp.zeros(N_OBS, dtype=wp.float32, device=device, requires_grad=grad)
        obs_ptr = 0

        for step in range(N_STEPS):
            if obs_ptr < N_OBS and step == obs_indices[obs_ptr]:
                wp.launch(copy_scalar, dim=1, inputs=[x, x_at_obs, int(obs_ptr)], device=device)
                obs_ptr += 1
            x_new = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=grad)
            v_new = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=grad)
            wp.launch(euler_step, dim=1, inputs=[x, v, x_new, v_new, params,
                      float(DT), float(M)], device=device)
            x, v = x_new, v_new

        loss = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=grad)
        wp.launch(mse_loss, dim=N_OBS, inputs=[x_at_obs, x_obs_wp, int(N_OBS)],
                  outputs=[loss], device=device)

    wp.synchronize()
    return loss, tape, params


def main():
    print("=" * 60)
    print("  Warp Example: Damped oscillator parameter estimation")
    print("=" * 60)
    print(f"  Ground truth: k={K_TRUE}, c={C_TRUE}  |  Steps: {N_STEPS}")

    device = "cpu"
    rng = np.random.default_rng(42)
    obs_idx, x_obs = generate_observations(rng)
    x_obs_wp = wp.array(x_obs, dtype=wp.float32, device=device)

    params_np = np.array([20.0, 5.0], dtype=np.float32)
    print(f"  Initial guess: k={params_np[0]:.0f}, c={params_np[1]:.0f}")

    m_adam, v_adam = np.zeros(2), np.zeros(2)
    lr = float(os.environ.get("LEARNING_RATE", "0.15"))
    history = []
    t0 = time.time()

    for step in range(opt_steps):
        loss_arr, tape, p = forward(params_np, obs_idx, x_obs_wp, device, grad=True)
        tape.backward(loss_arr); wp.synchronize()
        g = p.grad.numpy().copy().astype(np.float64)
        lo = float(loss_arr.numpy()[0])
        tape.zero()

        # RULE: clip gradients to prevent NaN from long unrolls
        gn = np.linalg.norm(g)
        if gn > 10.0:
            g = g * 10.0 / gn

        history.append({"step": step, "k": round(float(params_np[0]), 2),
                        "c": round(float(params_np[1]), 2), "loss": round(lo, 6)})
        if step % 25 == 0 or step == opt_steps - 1:
            print(f"  step {step:3d}: k={params_np[0]:6.2f}  c={params_np[1]:5.2f}  loss={lo:.6f}")

        m_adam = 0.9 * m_adam + 0.1 * g
        v_adam = 0.999 * v_adam + 0.001 * g ** 2
        mh = m_adam / (1 - 0.9 ** (step + 1))
        vh = v_adam / (1 - 0.999 ** (step + 1))
        params_np = (params_np - lr * mh / (np.sqrt(vh) + 1e-8)).astype(np.float32)
        params_np = np.clip(params_np, [1.0, 0.01], [200.0, 50.0])

    elapsed = time.time() - t0
    k_f, c_f = float(params_np[0]), float(params_np[1])

    # Gradient validation
    tp = np.array([35.0, 3.0], dtype=np.float32)
    la, ta, pa = forward(tp, obs_idx, x_obs_wp, device, grad=True)
    ta.backward(la); wp.synchronize()
    g_ad = pa.grad.numpy().copy()
    g_fd = np.zeros(2)
    for i in range(2):
        pp, pm = tp.copy(), tp.copy()
        pp[i] += 0.05; pm[i] -= 0.05
        lp, _, _ = forward(pp, obs_idx, x_obs_wp, device)
        lm, _, _ = forward(pm, obs_idx, x_obs_wp, device)
        g_fd[i] = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / 0.1
    rel = np.max(np.abs(g_ad - g_fd) / (np.abs(g_fd) + 1e-8))

    print(f"\n  Gradient check: rel_err={rel:.4f}  {'PASS' if rel < 0.15 else 'FAIL'}")
    print(f"  Result: k={k_f:.1f} (true {K_TRUE})  c={c_f:.1f} (true {C_TRUE})")
    print(f"  Time: {elapsed:.1f}s")

    metrics = {
        "question": "Recover k and c from noisy observations",
        "ground_truth": {"k": K_TRUE, "c": C_TRUE},
        "recovered": {"k": round(k_f, 2), "c": round(c_f, 2)},
        "relative_errors": {"k": round(abs(k_f - K_TRUE) / K_TRUE, 3),
                            "c": round(abs(c_f - C_TRUE) / C_TRUE, 3)},
        "gradient_check_pass": bool(rel < 0.15),
        "elapsed_s": round(elapsed, 2), "history": history,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
