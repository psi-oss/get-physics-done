"""Example: recover damping and stiffness of a spring-mass system from observations.

Demonstrates differentiable simulation for an INVERSE PROBLEM:
  Given noisy displacement measurements of a damped oscillator,
  recover the unknown spring constant k and damping coefficient c.

Physics: damped harmonic oscillator ODE
  m * x'' + c * x' + k * x = 0
  x(0) = 1.0, x'(0) = 0.0

Ground truth: k=40.0, c=2.0, m=1.0
Initial guess: k=20.0, c=5.0
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

K_TRUE = 40.0
C_TRUE = 2.0
M = 1.0
X0 = 1.0
V0 = 0.0

DT = 0.01
T_FINAL = float(os.environ.get("T_FINAL", "2.0"))
N_STEPS = int(T_FINAL / DT)
N_OBS = 40
OBS_NOISE = 0.02

opt_steps = int(os.environ.get("OPT_STEPS", "80"))
output_dir = Path(os.environ.get("OUTPUT_DIR", "output"))
output_dir.mkdir(parents=True, exist_ok=True)


@wp.kernel
def euler_step(
    x_in: wp.array(dtype=wp.float32),
    v_in: wp.array(dtype=wp.float32),
    x_out: wp.array(dtype=wp.float32),
    v_out: wp.array(dtype=wp.float32),
    params: wp.array(dtype=wp.float32),
    dt: float, mass: float,
):
    """Forward Euler step: separate in/out arrays for autodiff compatibility."""
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
    obs_indices = np.linspace(0, N_STEPS - 1, N_OBS, dtype=int)
    x_obs = x_true[obs_indices] + rng.normal(0, OBS_NOISE, N_OBS)
    return obs_indices, x_obs.astype(np.float32)


def forward(params_np, obs_indices, x_obs_wp, device, grad=False):
    params = wp.array(params_np, dtype=wp.float32, device=device, requires_grad=grad)
    tape = wp.Tape() if grad else None
    rg = grad

    with (tape if tape else nullcontext()):
        x = wp.array([X0], dtype=wp.float32, device=device, requires_grad=rg)
        v = wp.array([V0], dtype=wp.float32, device=device, requires_grad=rg)
        x_at_obs = wp.zeros(N_OBS, dtype=wp.float32, device=device, requires_grad=rg)
        obs_ptr = 0

        for step in range(N_STEPS):
            if obs_ptr < N_OBS and step == obs_indices[obs_ptr]:
                wp.launch(copy_scalar, dim=1, inputs=[x, x_at_obs, int(obs_ptr)], device=device)
                obs_ptr += 1
            x_new = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=rg)
            v_new = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=rg)
            wp.launch(euler_step, dim=1, inputs=[x, v, x_new, v_new, params, float(DT), float(M)], device=device)
            x, v = x_new, v_new

        loss = wp.zeros(1, dtype=wp.float32, device=device, requires_grad=rg)
        wp.launch(mse_loss, dim=N_OBS, inputs=[x_at_obs, x_obs_wp, int(N_OBS)], outputs=[loss], device=device)

    wp.synchronize()
    return loss, tape, params


def main():
    print("=" * 60)
    print("  Warp Example: Damped oscillator parameter estimation")
    print("  Recover k and c from noisy displacement observations")
    print("=" * 60)
    print(f"  Ground truth: k={K_TRUE}, c={C_TRUE}")
    print(f"  Time steps: {N_STEPS} (dt={DT}, T={T_FINAL}s)")

    device = "cpu"
    rng = np.random.default_rng(42)
    obs_indices, x_obs = generate_observations(rng)
    x_obs_wp = wp.array(x_obs, dtype=wp.float32, device=device)

    params_np = np.array([20.0, 5.0], dtype=np.float32)
    print(f"  Initial guess: k={params_np[0]:.1f}, c={params_np[1]:.1f}")

    m_adam, v_adam = np.zeros(2), np.zeros(2)
    lr = float(os.environ.get("LEARNING_RATE", "0.08"))
    history = []
    t0 = time.time()

    for step in range(opt_steps):
        loss_arr, tape, p = forward(params_np, obs_indices, x_obs_wp, device, grad=True)
        tape.backward(loss_arr)
        wp.synchronize()
        g = p.grad.numpy().copy().astype(np.float64)
        lo = float(loss_arr.numpy()[0])
        tape.zero()

        # Gradient clipping to prevent NaN from long unrolls
        g_norm = np.linalg.norm(g)
        if g_norm > 10.0:
            g = g * 10.0 / g_norm

        history.append({
            "step": step, "k": round(float(params_np[0]), 3),
            "c": round(float(params_np[1]), 3), "loss": round(lo, 6),
        })

        if step % 10 == 0 or step == opt_steps - 1:
            print(f"  step {step:02d}: k={params_np[0]:6.2f}  c={params_np[1]:5.2f}  "
                  f"loss={lo:.6f}  |grad|={g_norm:.4f}")

        m_adam = 0.9 * m_adam + 0.1 * g
        v_adam = 0.999 * v_adam + 0.001 * g ** 2
        mh = m_adam / (1 - 0.9 ** (step + 1))
        vh = v_adam / (1 - 0.999 ** (step + 1))
        params_np = params_np - lr * mh / (np.sqrt(vh) + 1e-8)
        params_np = np.clip(params_np, [1.0, 0.01], [200.0, 50.0]).astype(np.float32)

    elapsed = time.time() - t0
    k_final, c_final = float(params_np[0]), float(params_np[1])

    # Gradient validation
    test_params = np.array([35.0, 3.0], dtype=np.float32)
    eps = 0.05
    loss_ad, ta, pa = forward(test_params, obs_indices, x_obs_wp, device, grad=True)
    ta.backward(loss_ad); wp.synchronize()
    g_ad = pa.grad.numpy().copy()
    g_fd = np.zeros(2)
    for i in range(2):
        pp, pm = test_params.copy(), test_params.copy()
        pp[i] += eps; pm[i] -= eps
        lp, _, _ = forward(pp, obs_indices, x_obs_wp, device)
        lm, _, _ = forward(pm, obs_indices, x_obs_wp, device)
        g_fd[i] = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / (2 * eps)
    rel = np.max(np.abs(g_ad - g_fd) / (np.abs(g_fd) + 1e-8))
    grad_ok = rel < 0.15

    print(f"\n  Gradient check: max_rel_err={rel:.4f}  {'PASS' if grad_ok else 'FAIL'}")
    print(f"  Result: k={k_final:.2f} (true {K_TRUE})  c={c_final:.2f} (true {C_TRUE})")
    print(f"  Time: {elapsed:.1f}s")

    metrics = {
        "question": "Recover spring constant and damping from noisy observations",
        "ground_truth": {"k": K_TRUE, "c": C_TRUE},
        "recovered": {"k": round(k_final, 3), "c": round(c_final, 3)},
        "relative_errors": {"k": round(abs(k_final - K_TRUE) / K_TRUE, 4),
                            "c": round(abs(c_final - C_TRUE) / C_TRUE, 4)},
        "gradient_check_pass": bool(grad_ok),
        "elapsed_s": round(elapsed, 2),
        "history": history,
    }
    (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"  Output: {output_dir / 'metrics.json'}")


if __name__ == "__main__":
    main()
