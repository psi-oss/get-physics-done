# Warp Example: 2D Thermal Barrier Placement

Design optimization: position an insulating barrier on a 2D heated plate to minimize temperature at a shielded probe point.

## What's different from the other examples

| Dimension | Heat source (1D) | Oscillator | This example |
|-----------|-----------------|------------|--------------|
| Physics | 1D PDE | ODE | **2D PDE** |
| Task | Design opt | Inverse problem | **Design opt** |
| Grid | 1D (200 cells) | N/A | **2D (60x40 = 2400 cells)** |
| Material | Uniform | N/A | **Spatially varying k(x,y)** |
| Objective | Min peak T | Min observation MSE | **Min probe T (shielding)** |
| Interface | N/A | N/A | **Harmonic mean at material boundaries** |

## Run

```bash
mkdir my-project && cd my-project
cp ../../Dockerfile.cpu ../../Dockerfile.gpu ../../requirements.txt ../../run.sh .
mkdir src && cp ../example-barrier/main.py src/
chmod +x run.sh
./run.sh -e SIM_STEPS=400 -e OPT_STEPS=40
cat output/metrics.json
```
