---
load_when:
  - "machine learning"
  - "neural network"
  - "deep learning"
  - "physics-informed"
  - "surrogate model"
  - "neural network potential"
  - "equivariant"
tier: 3
context_cost: high
---

# Machine Learning for Physics Protocol

Machine learning applied to physics problems must respect physical constraints — symmetries, conservation laws, dimensional consistency, and known limiting behavior. A neural network that fits training data but violates gauge invariance or produces negative probabilities is not a physics result. This protocol ensures ML models are physically meaningful and not just statistically good.

## Related Protocols
- `numerical-computation.md` — Convergence testing, error budgets for numerical outputs
- `monte-carlo.md` — ML-enhanced sampling, neural network potentials in MC
- `molecular-dynamics.md` — Neural network force fields
- `symmetry-analysis.md` — Symmetries that ML architectures must respect

## Step 1: Problem Formulation

1. **Define what the ML model replaces.** Is it replacing: (a) an expensive ab initio calculation (surrogate model), (b) an unknown functional (learning from data), (c) an intractable integral or optimization (variational method), or (d) a classification/detection task? The validation requirements differ for each case.
2. **Identify the physics constraints.** Before choosing an architecture, list every constraint the output must satisfy:
   - Symmetries (translation, rotation, permutation, gauge, parity, time-reversal)
   - Conservation laws (energy, momentum, charge, particle number)
   - Boundary conditions and asymptotic behavior
   - Positivity constraints (probabilities, densities, cross-sections)
   - Dimensional consistency
3. **Define the loss function from physics.** Where possible, use physics-informed losses rather than generic MSE. Examples: variational energy for quantum wavefunctions, residual of the governing PDE (physics-informed neural networks), KL divergence for generative models of distributions.
4. **State the baseline.** Every ML result must be compared to a non-ML baseline: the best available analytic approximation, conventional numerical method, or experimental data. ML that underperforms the baseline is not useful regardless of its novelty.

## Step 2: Data and Symmetries

1. **Training data provenance.** State exactly how training data was generated: which code, which method (DFT functional, MD force field, MC algorithm), which parameters. The ML model cannot be more accurate than its training data. Systematic errors in the training data propagate directly into the model.
2. **Data distribution vs deployment distribution.** The model is only reliable within the distribution of its training data. If trained on equilibrium configurations, it cannot predict far-from-equilibrium behavior. Document the training distribution explicitly and flag any extrapolation.
3. **Symmetry enforcement.** There are two approaches:
   - **Hard enforcement (architectural).** Build the symmetry into the network architecture. Examples: equivariant neural networks (E(3)-equivariant for rotations/translations), permutation-invariant pooling for identical particles, gauge-equivariant layers. This guarantees the symmetry exactly.
   - **Soft enforcement (data augmentation + loss penalty).** Augment training data with symmetry-transformed examples and/or add symmetry-violation penalties to the loss. This does NOT guarantee the symmetry — violations persist at finite precision. Avoid for exact symmetries; use only for approximate symmetries.
4. **For exact symmetries: always use hard enforcement.** A rotation-equivariant potential trained on 1000 configurations outperforms a generic network trained on 100,000 augmented configurations, because equivariance is guaranteed rather than learned.

## Step 3: Architecture Selection

1. **Neural network potentials (NNP).** For atomic-scale simulations:
   - **Behler-Parrinello** (atom-centered symmetry functions): simple, well-tested, but descriptor quality limits accuracy.
   - **SchNet / DimeNet / NequIP / MACE**: message-passing neural networks with increasing sophistication. NequIP and MACE use E(3)-equivariant features and achieve chemical accuracy with small training sets.
   - Always output energy as a scalar and compute forces as the negative gradient: F = -dE/dr. This guarantees energy conservation by construction. Never train a separate force model.
2. **Normalizing flows.** For sampling distributions (lattice field theory, molecular configurations):
   - Build the flow from invertible, differentiable transformations with tractable Jacobians.
   - Enforce symmetries in the flow architecture (e.g., gauge-equivariant flows for lattice gauge theory).
   - Verify that the learned distribution reproduces known observables (energy, correlation functions) and that the effective sample size (ESS) is not too low.
3. **Physics-informed neural networks (PINNs).** For solving PDEs:
   - The loss function is the PDE residual evaluated at collocation points: L = sum |PDE(u_theta(x))| ^2.
   - PINNs struggle with: high-frequency solutions, multi-scale problems, sharp gradients, and stiff systems. If the PDE has known difficulties, PINNs will inherit them.
   - Always compare with a conventional PDE solver (finite element, spectral method) on the same problem.
4. **Variational Monte Carlo (VMC) with neural networks.** For quantum many-body wavefunctions:
   - The wavefunction ansatz psi_theta(r) is parameterized by a neural network (FermiNet, PauliNet, DeepErwin).
   - The loss is the variational energy: E[psi_theta] = <psi_theta|H|psi_theta> / <psi_theta|psi_theta>.
   - Enforce antisymmetry for fermions (via Slater determinants or antisymmetric layers), correct cusp conditions, and correct asymptotic decay.

## Step 4: Training Protocol

1. **Train/validation/test split.** The test set must be drawn from physically distinct conditions (different temperatures, pressures, compositions), not just randomly held-out points from the same trajectory. Random splits from correlated trajectories massively overestimate generalization.
2. **Learning rate schedule.** Use warmup + cosine decay or reduce-on-plateau. Report the learning rate, batch size, optimizer (Adam, AdamW), and total training epochs/steps.
3. **Early stopping.** Monitor the validation loss (not training loss) to detect overfitting. For physics surrogates, also monitor physics metrics (energy conservation violation, symmetry violation) on the validation set.
4. **Reproducibility.** Report: random seed, hardware (GPU model), software versions, total training time, and final loss values. Provide trained model weights or training scripts.

## Step 5: Uncertainty Quantification

1. **Point predictions are insufficient.** Every ML prediction must have an uncertainty estimate. Methods:
   - **Ensemble methods:** Train N independent models (different initializations, different data splits). The spread of predictions gives an uncertainty. N >= 5 for reasonable statistics.
   - **MC dropout:** Apply dropout at inference time, run multiple forward passes. Cheap but often underestimates uncertainty.
   - **Deep evidential regression:** Single forward pass uncertainty. Fast but requires careful calibration.
   - **Bayesian neural networks:** Principled but expensive. Use for small models or critical applications.
2. **Calibration.** The predicted uncertainty must be calibrated: the fraction of true values falling within the predicted X% confidence interval should be X%. Plot the calibration curve. Overconfident models (common) underestimate uncertainty in the tails.
3. **Out-of-distribution detection.** The model must flag when it is extrapolating. Use: ensemble disagreement, latent space distance to training data, or input feature monitoring. A model that silently extrapolates and returns confident-looking predictions is dangerous.

## Step 6: Physics Validation

1. **Conservation law tests.** If the model predicts a conserved quantity (energy, momentum), verify conservation in dynamical simulations using the model. Energy drift in MD with a neural network potential signals a problem with force consistency or training.
2. **Known limits.** Test the model in every analytically solvable limit: harmonic oscillator, ideal gas, non-interacting particles, high-temperature/low-temperature, weak-coupling/strong-coupling. If the model fails in a known limit, it is wrong everywhere.
3. **Symmetry verification.** Apply symmetry transformations to the input and verify the output transforms correctly. For a rotation-equivariant potential: E(R * config) = E(config) for all rotations R. Test with random rotations, not just 90-degree rotations.
4. **Extrapolation boundaries.** Systematically map where the model breaks down. Vary each input parameter beyond the training range and identify where predictions become unreliable (uncertainty explodes, conservation laws are violated, unphysical values appear).
5. **Comparison with conventional methods.** Run the same calculation with a conventional method (DFT, MC, exact diagonalization) for a subset of test cases. The ML model should agree within its stated uncertainty. Disagreement means either the model or the uncertainty estimate is wrong.

## Worked Example: Neural Network Potential for Liquid Water

**Problem:** Train an E(3)-equivariant neural network potential (NNP) for liquid water that reproduces DFT-level accuracy for the radial distribution function g(r), self-diffusion coefficient D, and density at ambient conditions (T = 300 K, P = 1 atm). This example targets three common errors: force/energy inconsistency, data correlation in train/test splits, and extrapolation without warning.

### Step 1: Training Data

Generate DFT-RPBE-D3 (with dispersion correction) training data:
- 64 water molecules in a periodic box, NVT ensemble
- DFT code: VASP, PAW pseudopotentials, 400 eV cutoff, Gamma-point only (sufficient for this cell size)
- 5 independent MD trajectories at T = 280, 300, 320, 340, 360 K (10 ps each, dt = 0.5 fs)
- Sample every 50 fs to reduce correlation -> 1000 frames per trajectory, 5000 total

**Train/test split (CORRECT):**
- Training: trajectories at T = 280, 300, 340 K (3000 frames)
- Validation: trajectory at T = 320 K (1000 frames)
- Test: trajectory at T = 360 K (1000 frames)
- This ensures physically distinct conditions between splits

**Train/test split (WRONG — what to avoid):**
- Random 80/10/10 split across all trajectories
- Consecutive frames at same T are correlated (autocorrelation time ~ 200 fs > sampling interval of 50 fs)
- Test MAE would appear 2-3x smaller than true generalization error

**Training data limitations:**
- RPBE-D3 overestimates the density of liquid water by ~3% at 300 K
- RPBE-D3 slightly underestimates the first peak of g_OO(r)
- The NNP will reproduce these DFT errors faithfully — it cannot be more accurate than its training data

### Step 2: Architecture — E(3)-Equivariant NNP

Use MACE (Multi-ACE message-passing neural network):
- E(3)-equivariant by construction: rotational and translational symmetry hard-enforced
- Permutation invariance: symmetric aggregation over atom types
- Energy as scalar output, forces from automatic differentiation: F_i = -dE/dr_i
- Two message-passing layers, max body-order = 4, cutoff r_c = 5.0 Angstrom
- Total parameters: ~450,000

**Force consistency check:** Forces MUST be derived from the energy via autodiff, not trained independently. Verify: for a test configuration, compute F_i^{autodiff} = -dE/dr_i (finite difference with dr = 10^{-4} Angstrom) and compare with the model's output forces. Agreement to < 10^{-5} eV/Angstrom confirms consistency. If using separate force and energy models (a common error), this check will fail by orders of magnitude, and MD with this potential will show energy drift.

### Step 3: Training

- Optimizer: AdamW, lr = 0.001, weight decay = 0.01
- Loss: L = w_E * MAE(E) + w_F * MAE(F) + w_S * MAE(stress)
  - w_E = 1.0, w_F = 100.0, w_S = 10.0 (force-weighted; forces are more important than energies for MD)
- Batch size: 4 configurations
- Training: 500 epochs, ~2 hours on 1 A100 GPU
- Early stopping on validation MAE(F)

Training convergence:

| Epoch | Train MAE(E) (meV/atom) | Train MAE(F) (meV/Ang) | Val MAE(F) (meV/Ang) |
|---|---|---|---|
| 1 | 85.3 | 412.0 | 425.0 |
| 50 | 2.1 | 52.3 | 78.4 |
| 100 | 0.8 | 21.5 | 34.2 |
| 200 | 0.4 | 12.1 | 18.7 |
| 300 | 0.3 | 8.4 | 15.2 |
| 500 | 0.2 | 6.1 | 14.8 |

**Gap between train and val MAE(F)** (6.1 vs 14.8): a factor of ~2.4x indicates mild overfitting. Acceptable if the test MAE is similar to validation. If the gap exceeds 5x, reduce model capacity or add regularization.

### Step 4: Validation on Test Set (T = 360 K)

Test set performance:

| Metric | Value | DFT chemical accuracy |
|---|---|---|
| MAE(E) | 0.35 meV/atom | < 1 meV/atom |
| MAE(F) | 16.2 meV/Ang | < 50 meV/Ang |
| MAE(stress) | 0.8 kbar | < 1 kbar |
| Max |F_err| | 142 meV/Ang | Flag if > 200 meV/Ang |

All within chemical accuracy thresholds. The max force error (142 meV/Ang) occurs on an H atom involved in a hydrogen bond rearrangement — a region of configuration space where the potential energy surface is steep.

### Step 5: MD Simulation and Physics Validation

Run NVT MD at T = 300 K, 64 molecules, for 100 ps (dt = 0.5 fs, Nose-Hoover thermostat):

**Energy conservation test (NVE, 10 ps):**
- Energy drift: 0.003 meV/atom/ps
- Acceptable: < 0.1 meV/atom/ps
- If energy drift > 1 meV/atom/ps, force/energy consistency is violated (most likely cause: separate force model, or numerical precision issue in autodiff)

**Radial distribution function g_OO(r):**

| r (Ang) | g_OO (NNP-MD) | g_OO (DFT-MD) | g_OO (experiment) |
|---|---|---|---|
| 2.75 (1st peak) | 2.85 | 2.80 | 2.76 |
| 3.45 (1st min) | 0.78 | 0.80 | 0.84 |
| 4.50 (2nd peak) | 1.12 | 1.13 | 1.12 |

NNP reproduces DFT within statistical noise. Both slightly overstructure the first peak vs experiment — this is a DFT-RPBE-D3 limitation, not an NNP error.

**Self-diffusion coefficient:**
- D (NNP-MD) = 2.1 x 10^{-5} cm^2/s
- D (DFT-MD) = 2.0 x 10^{-5} cm^2/s (from same functional, literature value)
- D (experiment) = 2.3 x 10^{-5} cm^2/s

Agreement within 15%. The NNP faithfully reproduces the DFT dynamics.

**Density at 1 atm (NPT):**
- rho (NNP) = 1.03 g/cm^3
- rho (DFT-RPBE-D3) = 1.03 g/cm^3
- rho (experiment) = 1.00 g/cm^3

The 3% overestimate is inherited from the DFT functional, not from the NNP.

### Step 6: Uncertainty Quantification and OOD Detection

Train an ensemble of 5 NNPs (different random seeds):

| Quantity | Mean | Std (ensemble) | Interpretation |
|---|---|---|---|
| E per atom (300 K equilibrium) | -14.221 eV | 0.0003 eV | Low uncertainty — in-distribution |
| E per atom (ice Ih, 100 K) | -14.318 eV | 0.003 eV | Moderate — near edge of training |
| E per atom (dissociated water, 3000 K) | -13.89 eV | 0.08 eV | High — extrapolation, UNRELIABLE |

**OOD detection threshold:** Ensemble std > 10x the in-distribution std (0.003 eV) flags the prediction as unreliable. At 3000 K, molecules dissociate (O-H bond breaking) — a configuration never seen in training. The ensemble disagreement correctly flags this.

### Verification

1. **Rotation equivariance:** Apply 100 random SO(3) rotations to a test configuration. |E(R*config) - E(config)| < 10^{-8} eV for all R (hard-enforced by architecture). If the maximum violation is > 10^{-6} eV, the equivariant layers have a bug.

2. **Force/energy consistency:** Compute F_autodiff vs F_model for 10 test configurations. Max deviation: 3 x 10^{-6} eV/Angstrom (numerical precision of finite differences). This confirms forces are properly derived from the energy.

3. **Energy conservation in NVE:** Drift < 0.003 meV/atom/ps over 10 ps. For comparison, a model with independent force training shows drift > 1 meV/atom/ps — detectable within 1 ps.

4. **Harmonic limit:** Compute phonon frequencies of ice Ih at 0 K by finite displacement. Compare with DFT phonon frequencies. Agreement within 5% for all modes below 1000 cm^{-1} confirms the potential energy surface is accurate near equilibrium. Disagreement > 10% in any mode indicates insufficient training data near the crystalline minimum.

5. **Calibration:** Over 100 test configurations, the fraction of true energies falling within the ensemble's +/- 1 sigma should be ~68%. If it is ~40% (overconfident) or ~95% (too conservative), adjust the uncertainty estimate by recalibrating.

6. **Training data accuracy:** The NNP cannot exceed DFT accuracy. Report: "This NNP reproduces RPBE-D3 to within 0.4 meV/atom (energy) and 16 meV/Ang (forces). RPBE-D3 overestimates liquid water density by 3% and slightly overstructures g_OO(r). These systematic errors are inherited by the NNP."

## Worked Example: Normalizing Flow for 2D Lattice Phi-4 Field Theory

**Problem:** Train a normalizing flow to generate field configurations for the 2D scalar phi-4 theory on an 8x8 lattice at coupling lambda = 0.5, and use it to compute the susceptibility chi = <phi^2> - <phi>^2. Demonstrate that symmetry-equivariant architecture matters for sampling efficiency and that the effective sample size (ESS) is the true measure of performance, not the loss function. This example targets two common errors: using a non-equivariant flow for a lattice field theory (producing low ESS despite good training loss) and confusing the KL divergence with the physical observables.

### Step 1: The Target Distribution

The 2D phi-4 action on a lattice with spacing a = 1:

```
S[phi] = sum_x [(d/2) sum_mu (phi(x+mu) - phi(x))^2 + m^2/2 phi(x)^2 + lambda phi(x)^4]
```

with d = 2 spacetime dimensions, m^2 = -0.6 (negative mass-squared, broken phase), lambda = 0.5, on an 8x8 lattice with periodic boundary conditions. The target distribution is P[phi] = exp(-S[phi]) / Z.

This system has a Z_2 symmetry: S[phi] = S[-phi]. The probability distribution must respect this: P[phi] = P[-phi]. Any sampling method that violates this symmetry will produce biased estimates for Z_2-odd observables.

### Step 2: Architecture Comparison

**Model A -- Generic RealNVP (NOT equivariant):**
- Affine coupling layers with checkerboard masking
- 8 coupling layers, each with a 2-hidden-layer MLP (64 units)
- No Z_2 symmetry enforcement
- Parameters: ~50,000

**Model B -- Z_2-Equivariant RealNVP:**
- Same architecture as Model A, but with symmetrized coupling layers: for each configuration phi, the flow also processes -phi and averages the log-probability
- Equivalently: enforce s(phi) = s(-phi) and t(phi) = -t(-phi) for scale s and translation t in each coupling layer
- Parameters: ~50,000 (same as Model A)

### Step 3: Training

Both models trained with the same protocol:
- Loss: reverse KL divergence, D_KL(q || p) = E_q[ln q(phi) - ln p(phi)] = E_q[ln q(phi) + S(phi)] + ln Z
- Optimizer: Adam, lr = 0.001
- Batch size: 512
- Training steps: 20,000

| Metric | Model A (generic) | Model B (equivariant) |
|--------|-------------------|----------------------|
| Final KL divergence | 3.2 | 2.8 |
| Acceptance rate (MCMC correction) | 0.15 | 0.62 |
| Effective sample size (ESS/N) | 0.08 | 0.45 |
| <phi> | 0.32 +/- 0.15 | 0.002 +/- 0.01 |
| <phi^2> | 0.85 +/- 0.04 | 0.87 +/- 0.02 |
| chi (susceptibility) | 0.75 +/- 0.08 | 0.87 +/- 0.02 |

**Key observations:**

Model A has a reasonable KL divergence (3.2 is not terrible for 64 lattice sites) but terrible ESS (8%). The flow generates configurations that look plausible but have wrong weights. The Metropolis correction (accept/reject with ratio p(phi)/q(phi)) fixes the distribution but rejects 85% of proposals, making sampling very inefficient.

Model A also gives <phi> = 0.32, suggesting the flow has collapsed to one of the two Z_2-related minima. This is a mode collapse failure: the flow maps to only one sector (phi > 0), missing the other sector entirely. The susceptibility is correspondingly wrong (0.75 instead of 0.87).

Model B, with Z_2 equivariance, automatically generates both sectors equally. <phi> = 0.002 (consistent with zero by symmetry). The ESS is 45% -- six times better than Model A despite the same number of parameters and training steps. The susceptibility agrees with the HMC reference.

### Step 4: Reference Calculation (HMC)

Run Hybrid Monte Carlo (standard lattice field theory algorithm) for comparison:
- 10,000 thermalization sweeps + 100,000 measurement sweeps
- Autocorrelation time: tau_int = 85 sweeps (near the critical point, critical slowing down)
- N_eff = 100,000 / (2 * 85) = 588

| Observable | HMC | Model B (flow) | Model A (flow) |
|-----------|-----|---------------|----------------|
| <phi^2> | 0.871 +/- 0.008 | 0.87 +/- 0.02 | 0.85 +/- 0.04 |
| chi | 0.871 +/- 0.015 | 0.87 +/- 0.02 | 0.75 +/- 0.08 |
| <phi^4> | 1.52 +/- 0.03 | 1.53 +/- 0.05 | 1.41 +/- 0.10 |

Model B agrees with HMC. Model A is biased, especially for chi (14% error, well outside statistics).

### Step 5: The ESS Trap

**The loss function is not the physics metric.** Model A has KL = 3.2 and Model B has KL = 2.8 -- a modest difference. But the ESS differs by 6x and the bias in chi differs by 7x. This is because:

1. The KL divergence averages over all configurations. A flow that gets most configurations right but misses an entire symmetry sector has a moderate KL but catastrophically wrong physics.
2. The ESS directly measures how many independent, correctly-weighted samples the flow produces. It accounts for both the proposal quality AND the reweighting.
3. A flow with ESS < 0.01 is useless for physics regardless of its KL divergence. The effective number of samples is too small for reliable estimates.

### Verification

1. **Z_2 symmetry check.** Generate 10,000 samples from the flow. Compute <phi>. For a Z_2-symmetric theory, <phi> = 0 exactly. If |<phi>| > 3 * sigma_stat, the flow is breaking the symmetry (mode collapse). Model A fails this test; Model B passes.

2. **ESS as primary metric.** Always report ESS, not just the training loss. The ESS is computed from the importance weights w_i = p(phi_i) / q(phi_i): ESS = (sum w_i)^2 / sum w_i^2. Normalize so ESS/N is between 0 and 1. Report both the raw acceptance rate (Metropolis) and ESS.

3. **Known limit -- free field (lambda = 0).** For lambda = 0 and m^2 > 0, the distribution is Gaussian: P[phi] proportional to exp(-1/2 phi^T M phi) where M is the lattice Laplacian + m^2. The flow should reproduce the exact covariance matrix <phi_x phi_y> = M^{-1}_{xy}. Compare element-by-element.

4. **Scaling test.** Increase the lattice to 16x16 (256 sites). The flow's ESS will decrease because the target distribution is more complex. If ESS drops below 0.01, the flow is not a viable sampler at this lattice size. Report the scaling: ESS vs lattice volume.

5. **Topological sectors (if applicable).** For theories with topological sectors (e.g., U(1) gauge theory in 2D), the flow must sample all sectors correctly. Check the distribution of the topological charge Q. If Q is frozen at a single value, the flow has mode collapse in the topological sector -- analogous to the Z_2 mode collapse above but harder to detect.

6. **Do NOT skip the MCMC correction.** Flow-generated samples are approximate. Without the Metropolis accept/reject step, observables are biased by the imperfect flow density. The correction makes the result exact (up to statistical error) regardless of the flow quality. The flow only affects the efficiency (ESS), not the correctness of the corrected samples.

## Common Pitfalls

- **Symmetry by data augmentation only.** Augmenting data with rotated/translated examples does not guarantee equivariance. The model will violate the symmetry at unseen orientations, and the violation may be small in aggregate metrics but large for specific configurations. Use equivariant architectures for exact symmetries.
- **Overfitting to correlated data.** Consecutive frames from an MD trajectory are highly correlated. Random train/test splits from the same trajectory produce test errors that vastly underestimate the true generalization error. Use temporally separated or physically distinct test sets.
- **Force/energy inconsistency.** Training forces and energies independently (separate models or separate loss terms without gradient consistency) produces a model where F is not equal to -dE/dr. This violates energy conservation in MD and produces drift. Always derive forces from the energy via automatic differentiation.
- **Ignoring the training data accuracy.** An ML model trained on DFT-PBE data inherits all of PBE's systematic errors (wrong band gaps, missing dispersion, etc.). The model can be a perfect surrogate of PBE and still give wrong physics. Report the training data method and its known limitations.
- **No uncertainty quantification.** A neural network that outputs a point prediction with no uncertainty is almost useless for physics. The prediction could be in a well-trained region (reliable) or far from training data (unreliable), and there is no way to tell without uncertainty quantification.
- **Extrapolation without warning.** ML models do not know they are extrapolating. A model trained on T = 300 K configurations will happily predict at T = 3000 K with no error message but completely wrong results. Always monitor the input distribution and flag out-of-distribution queries.

## Verification Checklist

- [ ] Physics constraints listed and enforcement method stated (hard vs soft)
- [ ] Training data: method, code, parameters documented; known limitations stated
- [ ] Architecture: symmetries built in (equivariant layers for exact symmetries)
- [ ] Forces derived from energy via gradient (not independently trained)
- [ ] Train/test split: physically distinct conditions, not random frames from same trajectory
- [ ] Uncertainty quantification: method stated, calibration curve plotted
- [ ] Out-of-distribution detection: mechanism in place and tested
- [ ] Known limits: model reproduces all analytically solvable cases
- [ ] Conservation laws: verified in dynamical simulations using the model
- [ ] Baseline comparison: ML model vs conventional method on identical test cases
- [ ] Reproducibility: seeds, hardware, software versions, training time reported

## Worked Example: Symmetry-Violating Neural Network for Molecular Potential Energy Surface

**Problem:** Train a neural network to predict the potential energy of a diatomic molecule as a function of interatomic distance, and demonstrate that a naive architecture (MLP taking Cartesian coordinates as input) violates rotational symmetry while a descriptor-based architecture (using interatomic distance) does not. Quantify the symmetry violation and show it corrupts the predicted equilibrium bond length and vibrational frequency. This targets the LLM error class of using Cartesian coordinates as NN input for molecular systems without building in rotational invariance, producing a model that gives different energies for the same molecule in different orientations.

### Step 1: Setup — H2 Potential Energy Curve

Training data: 500 DFT (PBE/cc-pVTZ) energy evaluations for H2 at bond lengths r in [0.5, 5.0] Angstrom. The true potential has a minimum at r_e = 0.743 A with depth D_e = 4.75 eV.

**Model A (symmetry-violating):** MLP with input = (x1, y1, z1, x2, y2, z2) — the Cartesian coordinates of both atoms. Architecture: 6 -> 64 -> 64 -> 1.

**Model B (symmetry-preserving):** MLP with input = r = |r2 - r1| — the interatomic distance. Architecture: 1 -> 64 -> 64 -> 1.

Both trained on the same data (all training geometries aligned along the z-axis) with the same loss function (MSE on energy) for 10000 epochs.

### Step 2: Training Performance (Misleading)

| Metric | Model A | Model B |
|--------|---------|---------|
| Training MSE (eV^2) | 1.2e-5 | 1.8e-5 |
| Test MSE (z-aligned) | 2.1e-5 | 2.5e-5 |
| r_e predicted (z-aligned) | 0.742 A | 0.743 A |
| omega_e predicted (z-aligned) | 4395 cm^{-1} | 4401 cm^{-1} |

Model A has LOWER training error. It appears to be the better model.

### Step 3: Rotation Test (Reveals the Error)

Evaluate both models on the SAME H2 configuration (r = 0.743 A) rotated to different orientations:

| Orientation | E_true (eV) | E_Model_A (eV) | E_Model_B (eV) |
|------------|------------|----------------|----------------|
| Along z: (0,0,0), (0,0,0.743) | -31.76 | -31.76 | -31.76 |
| Along x: (0,0,0), (0.743,0,0) | -31.76 | -31.52 | -31.76 |
| Along y: (0,0,0), (0,0.743,0) | -31.76 | -31.48 | -31.76 |
| 45 deg in xz: (0,0,0), (0.525,0,0.525) | -31.76 | -31.63 | -31.76 |
| Random orientation | -31.76 | -31.41 | -31.76 |

Model A predicts different energies for the SAME molecule in different orientations. The maximum energy variation across orientations is 0.35 eV (8 kcal/mol) — a catastrophic error for chemistry. Model B gives the correct (rotation-invariant) energy for all orientations.

### Step 4: Impact on Physical Predictions

**Vibrational frequency from Model A in a random orientation:**

Compute the second derivative d^2E/dr^2 at the minimum for a molecule aligned along a random direction:

```
omega_e (z-aligned) = 4395 cm^{-1}    (correct)
omega_e (random) = 3820 cm^{-1}       (13% error)
omega_e (along x) = 4890 cm^{-1}      (11% error, WRONG DIRECTION)
```

The vibrational frequency depends on the molecule's orientation in the lab frame. This is physically absurd — the vibrational frequency of an isolated molecule cannot depend on its orientation.

**MD simulation with Model A:** Run NVE dynamics of H2 starting in a random orientation. The molecule experiences a spurious torque (because the energy depends on orientation), causing it to rotate toward the z-axis (the training geometry). The rotational kinetic energy is extracted from vibrational energy, cooling the vibrational mode. After 10 ps, the molecule is vibrating at a lower effective temperature than the rotation — violating equipartition.

### Step 5: Fix — Invariant Descriptors

For general polyatomic molecules, the fix is not just using distances. The standard approach:

1. **Interatomic distances:** r_ij = |r_i - r_j|. Invariant under translation and rotation. Sufficient for small molecules but the number grows as N(N-1)/2.

2. **Symmetry functions (Behler-Parrinello):** Radial G^2 and angular G^4 functions centered on each atom. Invariant by construction. Standard for neural network potentials.

3. **Equivariant architectures (NequIP, MACE, PaiNN):** Use spherical harmonic features that TRANSFORM correctly under rotation (equivariant, not just invariant). Forces are computed as the gradient of the invariant energy, guaranteeing F = -dE/dr.

4. **Message-passing networks on graphs:** Atoms = nodes, bonds = edges. Edge features use r_ij (invariant). Node features updated by aggregating neighbor information. Architectures like SchNet, DimeNet, GemNet build in invariance at the graph level.

### Verification

1. **Rotation test (mandatory).** Generate 100 random orientations of each test geometry. Compute E for all orientations. The standard deviation sigma_rot MUST be zero (to numerical precision) for an invariant model. For Model A: sigma_rot = 0.12 eV. For Model B: sigma_rot = 1e-7 eV (machine precision). Report sigma_rot as a model quality metric.

2. **Permutation test.** For identical atoms (e.g., both H atoms in H2), swapping atom labels must not change the energy. Test: E(r1, r2) = E(r2, r1). Model A may violate this if the architecture does not enforce permutation symmetry.

3. **Force consistency.** Forces must equal -dE/dr computed by automatic differentiation through the model. If forces are trained independently (separate output head), verify F = -dE/dr to numerical precision. Inconsistency violates energy conservation in MD.

4. **Known limit — dissociation.** At large r: E(r -> inf) = E_atom1 + E_atom2. Both models should give the correct dissociation limit. If the energy diverges or oscillates at large r, the model is extrapolating badly.

5. **Data augmentation is NOT a fix.** Training Model A on randomly rotated data improves the rotation test but does NOT guarantee invariance — the model approximates invariance rather than enforcing it exactly. With 10x augmented data: sigma_rot drops from 0.12 eV to 0.01 eV but never reaches zero. For production use, build invariance into the architecture.
