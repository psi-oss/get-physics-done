# Containerized NVIDIA Warp Simulation

Template for running differentiable physics simulations using NVIDIA Warp inside Docker. Use this when the host environment does not have Warp installed or when GPU isolation is needed.

## When to Use Containers

Warp simulations require `warp-lang` and optionally CUDA. Do not assume these are available in the host environment. Always containerize when:

- The project uses `warp-lang` (GPU-accelerated differentiable simulation)
- The project needs a specific Python version or NumPy version for Warp compatibility
- Reproducibility requires pinned dependencies

## Dockerfile — CPU

Use this for development, CI, and machines without NVIDIA GPUs.

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "src/main.py"]
```

## Dockerfile — GPU (CUDA)

Use this for production runs on machines with NVIDIA GPUs.

```dockerfile
FROM nvcr.io/nvidia/pytorch:24.01-py3

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "src/main.py"]
```

Note: The `nvcr.io/nvidia/pytorch` base image includes CUDA, cuDNN, and Python. Warp will detect CUDA automatically. For GPU execution, pass `--gpus all` to `docker run`.

## requirements.txt

Minimal dependencies for a Warp simulation project:

```
numpy>=1.26,<2.1
matplotlib>=3.9
Pillow>=11.0
warp-lang>=1.12
```

Pin versions for reproducibility. Warp 1.12+ supports Python 3.10-3.12.

## Run Script

Place at project root as `run.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

IMAGE="${PROJECT_NAME:-warp-sim}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUTPUT_DIR="${SCRIPT_DIR}/output"

mkdir -p "${OUTPUT_DIR}"

echo "Building ${IMAGE}..."
docker build -t "${IMAGE}" "${SCRIPT_DIR}"

# Detect GPU availability
DOCKER_GPU_FLAG=""
if command -v nvidia-smi &>/dev/null && nvidia-smi &>/dev/null; then
    DOCKER_GPU_FLAG="--gpus all"
    echo "GPU detected, using CUDA acceleration"
fi

echo "Running ${IMAGE}..."
docker run --rm \
    ${DOCKER_GPU_FLAG} \
    -v "${OUTPUT_DIR}:/app/output" \
    -e OUTPUT_DIR=/app/output \
    -e WARP_DEVICE="${WARP_DEVICE:-cpu}" \
    "${IMAGE}"

echo "Outputs: ${OUTPUT_DIR}/"
```

## Environment Variables

The simulation entry point should accept configuration via environment variables so the container can be parameterized without rebuilding:

| Variable | Purpose | Example |
|----------|---------|---------|
| `OUTPUT_DIR` | Where to write results | `/app/output` |
| `WARP_DEVICE` | Compute device | `cpu` or `cuda:0` |
| `GRID_X`, `GRID_Y` | Spatial resolution | `160`, `140` |
| `SIM_STEPS` | Solver iteration count | `800` |
| `OPT_STEPS` | Optimization steps | `40` |
| `RANDOM_SEED` | Reproducibility seed | `42` |

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
├── Dockerfile
├── requirements.txt
└── run.sh
```

## Execution From GPD Agent

When a GPD executor agent needs to run a Warp simulation:

```bash
# 1. Build the container (first run only, cached after)
docker build -t ${project_name} .

# 2. Run with specific parameters
docker run --rm \
    -v "$(pwd)/output:/app/output" \
    -e OUTPUT_DIR=/app/output \
    -e SIM_STEPS=500 \
    -e OPT_STEPS=30 \
    ${project_name}

# 3. Read results
cat output/metrics.json
```

For verification runs (e.g., mesh convergence study), run the container multiple times with different parameters:

```bash
# Convergence study: run at increasing resolution
for grid in 40 80 160; do
    docker run --rm \
        -v "$(pwd)/output-${grid}:/app/output" \
        -e OUTPUT_DIR=/app/output \
        -e GRID_X=${grid} \
        -e GRID_Y=${grid} \
        ${project_name}
done
# Compare peak values across resolutions to estimate convergence order
```
