# Warp Simulation Container Template

Run NVIDIA Warp simulations inside Docker. Copy files into your project, write `src/main.py`, run.

## Quick Start

```bash
cp Dockerfile.cpu Dockerfile.gpu requirements.txt run.sh /path/to/project/
# write simulation in src/main.py
chmod +x run.sh && ./run.sh
cat output/metrics.json
```

## Files

| File | Purpose |
|------|---------|
| `Dockerfile.cpu` | python:3.11-slim base |
| `Dockerfile.gpu` | nvcr.io/nvidia/pytorch base (CUDA) |
| `requirements.txt` | numpy, matplotlib, Pillow, warp-lang |
| `run.sh` | Builds container, auto-detects GPU, mounts output/ |

## Examples

| Directory | Physics | Task |
|-----------|---------|------|
| `example/` | 1D heat PDE | Design optimization |
| `example-oscillator/` | Damped ODE | Inverse problem |
| `example-barrier/` | 2D heat + variable k | Design optimization |

Run any example:
```bash
mkdir test && cd test
cp ../Dockerfile.cpu ../Dockerfile.gpu ../requirements.txt ../run.sh .
mkdir src && cp ../example/main.py src/
chmod +x run.sh && ./run.sh
```
