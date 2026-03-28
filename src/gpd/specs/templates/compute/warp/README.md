# Warp Simulation Container Template

Run differentiable physics simulations using NVIDIA Warp inside Docker. Copy these files into your project root, write your simulation in `src/main.py`, and run.

## Quick Start

```bash
# Copy template files
cp Dockerfile.cpu Dockerfile.gpu requirements.txt run.sh /path/to/project/
# Write simulation code in src/main.py (see examples below)
chmod +x run.sh
./run.sh                              # builds container, auto-detects GPU
./run.sh -e SIM_STEPS=500             # pass env vars to container
cat output/metrics.json               # read results
```

## Files

| File | Purpose |
|------|---------|
| `Dockerfile.cpu` | python:3.11-slim base, for dev and CI |
| `Dockerfile.gpu` | nvcr.io/nvidia/pytorch base, for CUDA |
| `requirements.txt` | numpy, matplotlib, Pillow, warp-lang |
| `run.sh` | Auto-detects GPU, selects Dockerfile, mounts output/ |

## Examples

Three working examples, each demonstrating a different task:

| Example | Physics | Task | Key lesson |
|---------|---------|------|------------|
| `example/` | 1D heat equation | Design optimization (1 param) | Soft-max loss for peak minimization |
| `example-oscillator/` | Damped ODE | Inverse problem (2 params) | Gradient clipping for long unrolls |
| `example-barrier/` | 2D heat + variable k | Design optimization | Gaussian blend for autodiff-safe materials |

Run any example:
```bash
mkdir test && cd test
cp ../Dockerfile.cpu ../Dockerfile.gpu ../requirements.txt ../run.sh .
mkdir src && cp ../example/main.py src/
chmod +x run.sh && ./run.sh
```

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `OUTPUT_DIR` | `output` | Results directory (mounted volume) |
| `WARP_DEVICE` | `cpu` | Compute device (`cpu` or `cuda:0`) |
| `SIM_STEPS` | varies | Solver iterations |
| `OPT_STEPS` | varies | Optimization steps |

## Convergence Study Pattern

```bash
for n in 100 200 400; do
    ./run.sh -e SIM_STEPS=${n} -e OUTPUT_DIR=/app/output-${n}
done
# Compare metrics across runs
```
