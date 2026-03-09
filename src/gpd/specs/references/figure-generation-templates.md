# Figure Generation Templates

Publication-quality matplotlib templates for common physics plot types. Referenced by gpd-paper-writer.

## Base Configuration (Apply to ALL Figures)

```python
import matplotlib.pyplot as plt
import matplotlib as mpl
import numpy as np

# Publication defaults — apply once at script start
plt.rcParams.update({
    'font.family': 'serif',
    'font.serif': ['Computer Modern Roman', 'Times New Roman'],
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 11,
    'legend.fontsize': 9,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'text.usetex': True,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.6,
    'ytick.major.width': 0.6,
    'xtick.minor.width': 0.4,
    'ytick.minor.width': 0.4,
    'xtick.direction': 'in',
    'ytick.direction': 'in',
    'xtick.top': True,
    'ytick.right': True,
})

# Colorblind-safe palette (Wong 2011, Nature Methods)
COLORS = {
    'blue': '#0072B2',
    'orange': '#E69F00',
    'green': '#009E73',
    'red': '#D55E00',
    'purple': '#CC79A7',
    'cyan': '#56B4E9',
    'yellow': '#F0E442',
    'black': '#000000',
}
COLOR_CYCLE = [COLORS[c] for c in ['blue', 'orange', 'green', 'red', 'purple', 'cyan']]

# Line styles for grayscale readability
LINE_STYLES = ['-', '--', '-.', ':', (0, (3, 1, 1, 1, 1, 1))]
MARKERS = ['o', 's', '^', 'D', 'v', 'p']

# Figure sizing
SINGLE_COL = 3.375  # inches (PRL/PRD single column)
DOUBLE_COL = 7.0    # inches (PRL/PRD double column)
NATURE_COL = 3.5    # inches (Nature single column)
NATURE_WIDE = 7.3   # inches (Nature double column)
```

## Phase Diagram (2D Color Map with Boundaries)

```python
def plot_phase_diagram(x, y, Z, boundaries=None, labels=None,
                       xlabel=r'$g/J$', ylabel=r'$T/J$',
                       cbar_label=r'Order parameter $\langle m \rangle$'):
    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 0.85))
    im = ax.pcolormesh(x, y, Z, shading='gouraud', cmap='viridis', rasterized=True)
    if boundaries:
        for bx, by, style, label in boundaries:
            ax.plot(bx, by, style, color='white', lw=1.5, label=label)
    cbar = fig.colorbar(im, ax=ax, pad=0.02)
    cbar.set_label(cbar_label)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if labels:
        for lx, ly, text in labels:
            ax.text(lx, ly, text, color='white', fontsize=10,
                    ha='center', va='center', fontweight='bold')
    ax.legend(loc='best', framealpha=0.9)
    return fig, ax
```

## Energy Spectrum / Dispersion Relation

```python
def plot_dispersion(k, bands, labels=None,
                    xlabel=r'$k\,[\pi/a]$', ylabel=r'$E(k)\,[t]$',
                    symmetry_points=None):
    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 0.75))
    for i, band in enumerate(bands):
        label = labels[i] if labels else None
        ax.plot(k, band, color=COLOR_CYCLE[i % len(COLOR_CYCLE)],
                ls=LINE_STYLES[i % len(LINE_STYLES)], lw=1.2, label=label)
    if symmetry_points:
        for pos, name in symmetry_points:
            ax.axvline(pos, color='gray', ls=':', lw=0.5)
            ax.text(pos, ax.get_ylim()[0], name, ha='center', va='top', fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if labels:
        ax.legend(loc='best')
    return fig, ax
```

## Correlation Function (Log-Log with Power-Law Fit)

```python
def plot_correlation(r, C, C_err=None, fit_range=None, fit_params=None,
                     xlabel=r'$r/a$', ylabel=r'$C(r)$'):
    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 0.75))
    if C_err is not None:
        ax.errorbar(r, np.abs(C), yerr=C_err, fmt='o', ms=4, capsize=2,
                     color=COLORS['blue'], label='Data')
    else:
        ax.plot(r, np.abs(C), 'o', ms=4, color=COLORS['blue'], label='Data')
    if fit_range and fit_params:
        r_fit = np.linspace(*fit_range, 200)
        A, alpha = fit_params
        ax.plot(r_fit, A * r_fit**(-alpha), '--', color=COLORS['orange'],
                lw=1.2, label=rf'$C(r) \sim r^{{-{alpha:.2f}}}$')
    ax.set_xscale('log')
    ax.set_yscale('log')
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend()
    return fig, ax
```

## Convergence Study

```python
def plot_convergence(param, error, param_label=r'$N$', error_label=r'$|E - E_{\mathrm{exact}}|$',
                     expected_rate=None):
    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 0.7))
    ax.loglog(param, error, 'o-', ms=5, color=COLORS['blue'], lw=1.0, label='Computed')
    if expected_rate:
        p0 = error[0] * (param[0] / param)**expected_rate
        ax.loglog(param, p0, '--', color=COLORS['orange'], lw=0.8,
                  label=rf'$\propto N^{{-{expected_rate}}}$')
    ax.set_xlabel(param_label)
    ax.set_ylabel(error_label)
    ax.legend()
    ax.grid(True, which='both', ls=':', lw=0.3, alpha=0.5)
    return fig, ax
```

## Theory vs Experiment Comparison

```python
def plot_theory_vs_experiment(x_exp, y_exp, y_exp_err, x_th, y_th, y_th_band=None,
                               xlabel=r'$T\,[\mathrm{K}]$', ylabel=r'$\chi\,[1/J]$'):
    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 0.75))
    ax.errorbar(x_exp, y_exp, yerr=y_exp_err, fmt='o', ms=4, capsize=2,
                color=COLORS['blue'], label='Experiment')
    ax.plot(x_th, y_th, '-', color=COLORS['orange'], lw=1.2, label='This work')
    if y_th_band is not None:
        y_lo, y_hi = y_th_band
        ax.fill_between(x_th, y_lo, y_hi, color=COLORS['orange'], alpha=0.2)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend()
    return fig, ax
```

## Scaling Collapse

```python
def plot_scaling_collapse(datasets, x_rescale_fn, y_rescale_fn,
                          xlabel=r'$(T - T_c) L^{1/\nu}$',
                          ylabel=r'$\chi / L^{\gamma/\nu}$'):
    """Plot scaling collapse from multiple system sizes.

    datasets: list of (x, y, yerr, label) tuples
    x_rescale_fn: callable(x, params) -> rescaled x
    y_rescale_fn: callable(y, params) -> rescaled y
    """
    fig, ax = plt.subplots(figsize=(SINGLE_COL, SINGLE_COL * 0.75))
    for i, (x, y, yerr, label) in enumerate(datasets):
        ax.errorbar(x, y, yerr=yerr, fmt=MARKERS[i % len(MARKERS)],
                    ms=4, capsize=2, color=COLOR_CYCLE[i % len(COLOR_CYCLE)],
                    label=label)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.legend()
    return fig, ax
```

## Feynman Diagram Guidance

For Feynman diagrams, prefer TikZ-Feynman in LaTeX (generates vector graphics natively):

```latex
\usepackage{tikz-feynman}
\feynmandiagram [horizontal=a to b] {
  i1 -- [fermion] a -- [fermion] i2,
  a -- [photon, edge label=$q$] b,
  f1 -- [fermion] b -- [fermion] f2,
};
```

If generating programmatically in Python, use the `feynman` package or draw with matplotlib patches:

```python
# Minimal Feynman diagram with matplotlib (for simple diagrams only)
# For complex multi-loop diagrams, always use TikZ-Feynman in the LaTeX source
from matplotlib.patches import FancyArrowPatch
from matplotlib.collections import LineCollection
import matplotlib.patheffects as pe
```

## Saving Figures

```python
# Always save as PDF for vector quality in LaTeX
fig.savefig('figures/phase_diagram.pdf', format='pdf')

# For Nature-family journals that require EPS:
fig.savefig('figures/phase_diagram.eps', format='eps')

# For rasterized heavy figures (e.g., large Monte Carlo density plots):
fig.savefig('figures/density_map.png', dpi=600, format='png')
```
