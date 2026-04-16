# Finite-c Modular Bootstrap

## Benchmark chain

This note tracks the benchmark chain that matters for finite-central-charge Virasoro modular bootstrap.

1. **arXiv:1307.6562** establishes the modern linear-functional modular-invariance constraint on 2d CFT partition functions.
2. **arXiv:1608.06241** is the canonical finite-c Virasoro benchmark for near-c=1 gap bounds and extremal-spectrum numerics.
3. **arXiv:1903.06272** develops a fast polynomial-truncation algorithm for 2d modular bootstrap and computes spectral gaps to high precision.
4. **arXiv:2308.08725** adds integrality as a finite-c strengthening mechanism and reports a slight near-`c = 1` numerical improvement, not a universal closed-form replacement for the 2016 bound.
5. **arXiv:2308.11692** reframes the modular bootstrap geometrically and identifies the threshold window `(c-1)/12 < Delta_gap^* < c/12`.
6. **arXiv:2604.01275** is the latest direct ML-style search paper and reports candidate truncated partition functions for `1 < c <= 8/7`.

## Working interpretation

- The finite-c project anchor is still arXiv:1608.06241.
- The 2023 papers are best treated as non-ML strengthening and interpretation layers.
- The integrality paper should be cited as a numerical refinement near `c = 1`, not as a new closed-form formula.
- The 2026 paper is the decisive modern motivation, but it remains a candidate-spectrum result rather than a proof of new exact CFTs.

## False progress to reject

- Treating the `1 < c <= 8/7` window as proof of exact new theories.
- Comparing gap statements across papers without checking whether the same observable is meant.
- Using ML loss alone as a substitute for truncation uncertainty, residual checks, or non-ML consistency tests.
