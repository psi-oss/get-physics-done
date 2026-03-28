# Containerized NVIDIA Warp Simulation

Template for running differentiable physics simulations using NVIDIA Warp inside Docker. Use this when the host environment does not have Warp installed or when GPU isolation is needed.

## Template Files

Copy the contents of `warp/` into the project root:

```
warp/
├── Dockerfile.cpu       # Python 3.11-slim, for dev and CI
├── Dockerfile.gpu       # nvcr.io/nvidia/pytorch base, for CUDA runs
├── requirements.txt     # numpy, matplotlib, Pillow, warp-lang
└── run.sh               # Auto-detects GPU, selects Dockerfile, builds and runs
```

The agent should copy these files to the project root, then place simulation source code in `src/`. The run script handles GPU detection and Dockerfile selection automatically.

## When to Use Containers

Warp simulations require `warp-lang` and optionally CUDA. Do not assume these are available in the host environment. Always containerize when:

- The project uses `warp-lang` (GPU-accelerated differentiable simulation)
- The project needs a specific Python version or NumPy version for Warp compatibility
- Reproducibility requires pinned dependencies

## Environment Variables

The simulation entry point (`src/main.py`) should accept configuration via environment variables so the container can be parameterized without rebuilding:

| Variable | Purpose | Example |
|----------|---------|---------|
| `OUTPUT_DIR` | Where to write results | `/app/output` |
| `WARP_DEVICE` | Compute device | `cpu` or `cuda:0` |
| `GRID_X`, `GRID_Y` | Spatial resolution | `160`, `140` |
| `SIM_STEPS` | Solver iteration count | `800` |
| `OPT_STEPS` | Optimization steps | `40` |
| `RANDOM_SEED` | Reproducibility seed | `42` |

Pass extra env vars to the container via the run script:

```bash
./run.sh -e SIM_STEPS=500 -e GRID_X=200
```

## Project Layout

```
project-root/
├── src/
│   ├── main.py           # Entry point, reads env vars
│   ├── geometry.py        # Domain geometry and material properties
│   ├── solver.py          # Warp kernels and forward solver
│   ├── optimize.py        # Gradient-based optimization loop
│   └── visualize.py       # Output rendering
├── output/                # Generated at runtime (mounted volume)
├── Dockerfile.cpu
├── Dockerfile.gpu
├── requirements.txt
└── run.sh
```

## Execution From GPD Agent

When a GPD executor agent needs to run a Warp simulation:

```bash
# 1. Copy template files to project root
cp ${GPD_INSTALL_DIR}/templates/compute/warp/* ./

# 2. Build and run (run.sh auto-detects GPU)
chmod +x run.sh
./run.sh

# 3. Read results
cat output/metrics.json
```

For verification runs (e.g., mesh convergence study), run the container multiple times with different parameters:

```bash
# Convergence study: run at increasing resolution
for grid in 40 80 160; do
    OUTPUT_DIR="$(pwd)/output-${grid}" \
    ./run.sh -e GRID_X=${grid} -e GRID_Y=${grid}
done
# Compare peak values across resolutions to estimate convergence order
```
