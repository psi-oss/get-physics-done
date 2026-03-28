"""Optimize thermal barrier position on a 2D plate using Warp autodiff.

Question: Where to place an insulating barrier to best shield a probe from heat?
Answer: Aligned with the probe, between source and probe.

Produces: metrics.json + a publication-quality figure (barrier-optimization.pdf)
following GPD figure-generation-templates.md conventions.
"""

import json
from contextlib import nullcontext
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import warp as wp

wp.init()

NX, NY = 30, 20
N_CELLS = NX * NY
PROBE = (8, 10)
PROBE_IDX = PROBE[0] * NY + PROBE[1]

# --- GPD figure conventions (figure-generation-templates.md) ---
SINGLE_COL = 3.375  # inches, PRL/PRD single column
COLORS = {
    'blue': '#0072B2', 'orange': '#E69F00', 'green': '#009E73',
    'red': '#D55E00', 'purple': '#CC79A7', 'cyan': '#56B4E9',
}
_USE_TEX = False
try:
    plt.rcParams.update({'text.usetex': True})
    fig_test = plt.figure(); fig_test.text(0.5, 0.5, r'$T$'); fig_test.savefig('/dev/null', format='png')
    plt.close(fig_test); _USE_TEX = True
except Exception:
    _USE_TEX = False

plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Computer Modern Roman', 'DejaVu Serif'],
    'font.size': 10, 'axes.labelsize': 11, 'axes.titlesize': 11,
    'legend.fontsize': 9, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
    'text.usetex': _USE_TEX,
    'figure.dpi': 300, 'savefig.dpi': 300, 'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
    'xtick.direction': 'in', 'ytick.direction': 'in',
    'xtick.top': True, 'ytick.right': True,
})


@wp.kernel
def build_k(k: wp.array(dtype=wp.float32), by: wp.array(dtype=wp.float32), ny: int):
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
    left = T_in[wp.max(i - 1, 0) * ny + j]
    right = T_in[wp.min(i + 1, nx - 1) * ny + j]
    down = T_in[i * ny + wp.max(j - 1, 0)]
    up = T_in[i * ny + wp.min(j + 1, ny - 1)]
    kc = k[tid]
    T_out[tid] = (kc * (left + right + down + up) + Q[tid]) / (4.0 * kc + 0.1)


@wp.kernel
def probe_loss(T: wp.array(dtype=wp.float32), idx: int, loss: wp.array(dtype=wp.float32)):
    loss[0] = T[idx]


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


# --- Optimize ---
by = np.array([5.0], dtype=np.float32)
ma, va = np.zeros(1), np.zeros(1)
T_initial = None
history = []

for step in range(40):
    T, loss, tape, sp = solve(by, grad=True)
    tape.backward(loss); wp.synchronize()
    g = float(sp.grad.numpy()[0]); tape.zero()
    T_np = T.numpy().reshape(NX, NY)
    tp = float(T_np[PROBE])
    if step == 0:
        T_initial = T_np.copy()
    history.append({"step": step, "barrier_y": round(float(by[0]), 1), "T_probe": round(tp, 3)})
    if step % 5 == 0:
        print(f"  step {step:02d}: barrier_y={by[0]:5.1f}  T_probe={tp:.3f}")
    ma = 0.9 * ma + 0.1 * g
    va = 0.999 * va + 0.001 * g ** 2
    mh = ma / (1 - 0.9 ** (step + 1))
    vh = va / (1 - 0.999 ** (step + 1))
    by = np.clip(by - 0.3 * mh / (np.sqrt(vh) + 1e-8), 2.0, NY - 2.0).astype(np.float32)

T_final = T.numpy().reshape(NX, NY)

# --- Gradient validation ---
ty = np.array([8.0], dtype=np.float32)
_, la, ta, pa = solve(ty, grad=True); ta.backward(la); wp.synchronize()
g_ad = float(pa.grad.numpy()[0])
_, lp, _, _ = solve(ty + 0.1); _, lm, _, _ = solve(ty - 0.1)
g_fd = (float(lp.numpy()[0]) - float(lm.numpy()[0])) / 0.2
rel = abs(g_ad - g_fd) / (abs(g_fd) + 1e-8)

print(f"\n  Gradient check: rel_err={rel:.4f} {'PASS' if rel < 0.15 else 'FAIL'}")
print(f"  Result: barrier at y={by[0]:.1f} (probe at y={PROBE[1]})")

# --- Publication figure (GPD conventions) ---
out = Path("/app/output")
out.mkdir(parents=True, exist_ok=True)

fig, axes = plt.subplots(1, 3, figsize=(SINGLE_COL * 2.2, SINGLE_COL * 0.7))
fig.subplots_adjust(wspace=0.35)

vmin, vmax = 0, max(T_initial.max(), T_final.max())
labels = [
    ('(a) Initial', T_initial, 5.0),
    ('(b) Optimized', T_final, float(by[0])),
]
for ax, (title, T_plot, b_y) in zip(axes[:2], labels):
    im = ax.imshow(T_plot.T, origin='lower', cmap='inferno', vmin=vmin, vmax=vmax,
                   interpolation='bilinear', aspect='equal', rasterized=True)
    ax.plot(PROBE[0], PROBE[1], 'D', color=COLORS['cyan'], ms=5, mew=0.5, mec='white', zorder=5)
    # Barrier outline
    from matplotlib.patches import Rectangle
    rect = Rectangle((10 - 1.5, b_y - 4), 3, 8, lw=0.8, ec=COLORS['green'], fc='none', ls='--')
    ax.add_patch(rect)
    ax.set_title(title, fontsize=10)
    ax.set_xlabel('$x$' if _USE_TEX else 'x')
    ax.set_ylabel('$y$' if _USE_TEX else 'y')

cb = fig.colorbar(im, ax=axes[:2].tolist(), shrink=0.9, pad=0.03)
temp_label = '$T$' if _USE_TEX else 'T'
cb.set_label(temp_label)

# Convergence panel
steps = [h["step"] for h in history]
temps = [h["T_probe"] for h in history]
axes[2].plot(steps, temps, '-', color=COLORS['blue'], lw=1.0)
axes[2].scatter(steps[0], temps[0], color=COLORS['red'], s=25, zorder=5, label='initial')
axes[2].scatter(steps[-1], temps[-1], color=COLORS['green'], s=25, zorder=5, label='optimized')
probe_label = '$T_{\\mathrm{probe}}$' if _USE_TEX else 'T_probe'
axes[2].set_xlabel('Optimization step')
axes[2].set_ylabel(probe_label)
axes[2].set_title('(c) Convergence', fontsize=10)
axes[2].legend(fontsize=7)
axes[2].grid(True, ls=':', lw=0.3, alpha=0.5)

fig.savefig(out / "barrier-optimization.pdf", format='pdf')
fig.savefig(out / "barrier-optimization.png", format='png')
plt.close(fig)
print(f"  Figure: {out / 'barrier-optimization.pdf'}")

# --- Metrics ---
(out / "metrics.json").write_text(json.dumps({
    "barrier_y": round(float(by[0]), 1),
    "T_probe_initial": round(float(T_initial[PROBE]), 3),
    "T_probe_final": round(float(T_final[PROBE]), 3),
    "gradient_check_pass": bool(rel < 0.15),
    "figure": "barrier-optimization.pdf",
    "history": history,
}))
