# Warp Differentiable Simulation Example

Minimal working example: find the optimal position for a heat source on a 1D rod using Warp autodiff + Adam optimizer.

## Run

From the `warp/` parent directory, copy the template files and this example together:

```bash
mkdir my-project && cd my-project
cp ../Dockerfile.cpu ../Dockerfile.gpu ../requirements.txt ../run.sh .
mkdir src && cp ../example/main.py src/
chmod +x run.sh
./run.sh
cat output/metrics.json
```

## What it demonstrates

1. Warp kernel with `wp.Tape` automatic differentiation
2. Jacobi PDE solver with autodiff-safe boundary conditions (clamped indices, no branching)
3. Adam optimizer reading gradients from the tape
4. Gradient validation (AD vs finite differences)
5. Parameterization via environment variables (`SIM_STEPS`, `OPT_STEPS`)
6. Machine-readable output (`metrics.json`)
