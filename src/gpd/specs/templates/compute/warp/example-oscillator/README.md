# Warp Example: Damped Oscillator Parameter Estimation

Inverse problem: recover the spring constant `k` and damping coefficient `c` of a damped harmonic oscillator from noisy displacement measurements.

## What's different from the heat source example

| Dimension | Heat source | This example |
|-----------|------------|--------------|
| Physics | PDE (heat equation) | ODE (Newton's 2nd law) |
| Task | Design optimization | Parameter estimation (inverse problem) |
| Time | Steady-state | Time-dependent (transient dynamics) |
| Parameters | 1 (position) | 2 (stiffness + damping) |
| Objective | Minimize peak temperature | Minimize observation MSE |

## Run

```bash
mkdir my-project && cd my-project
cp ../../Dockerfile.cpu ../../Dockerfile.gpu ../../requirements.txt ../../run.sh .
mkdir src && cp ../example-oscillator/main.py src/
chmod +x run.sh
./run.sh -e OPT_STEPS=80
cat output/metrics.json
```
