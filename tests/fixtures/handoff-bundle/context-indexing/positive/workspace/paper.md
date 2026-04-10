# ML-Optimized Modular Bootstrap at Finite c: Corrected Review Note

_Corrected manuscript drafted from the verified project record on 2026-04-09. The workspace did not contain a standalone paper source file, so this document serves as the rewritten paper._

## Abstract

I re-audited the citation metadata, surviving equations, limiting cases, and GPD-tracked results for the finite-central-charge modular-bootstrap project. All six active arXiv identifiers resolve to the intended benchmark papers, and each arXiv record exposes the matching INSPIRE HEP cross-link. The main correction is scientific rather than bibliographic: the 2023 integrality result was locally represented too much like a universal equation, but the source only supports a slight near-`c = 1` numerical improvement. The corrected synthesis is therefore narrower and cleaner. The finite-`c` benchmark chain from modular invariance through the 2026 machine-learning search remains coherent, all explicit formulas in the project are dimensionless and have sensible limiting behavior, but the workspace still contains no local numerical reproduction. The paper must therefore stay literature-anchored and must not claim new exact conformal field theories.

## 1. Citation Audit

The active citation set was checked directly against arXiv and against the INSPIRE cross-links listed on the arXiv abstract pages. No arXiv identifier in the current workspace points to an unrelated paper.

1. David Friedan and Christoph A. Keller, _Constraints on 2d CFT partition functions_, `arXiv:1307.6562`.
2. Scott Collier, Ying-Hsuan Lin, and Xi Yin, _Modular Bootstrap Revisited_, `arXiv:1608.06241`.
3. Nima Afkhami-Jeddi, Thomas Hartman, and Amirhossein Tajdini, _Fast Conformal Bootstrap and Constraints on 3d Gravity_, `arXiv:1903.06272`.
4. A. Liam Fitzpatrick and Wei Li, _Improving Modular Bootstrap Bounds with Integrality_, `arXiv:2308.08725`.
5. Li-Yuan Chiang, Tzu-Chen Huang, Yu-tin Huang, Wei Li, Laurentiu Rodina, and He-Chen Weng, _The Geometry of the Modular Bootstrap_, `arXiv:2308.11692`.
6. Nathan Benjamin, A. Liam Fitzpatrick, Wei Li, and Jesse Thaler, _Descending into the Modular Bootstrap_, `arXiv:2604.01275`.

The bibliographic problem in this workspace was not misidentification. It was overstated interpretation. The arXiv IDs, titles, and author lists were already aligned with the intended benchmark chain.

## 2. Equation Audit

Only five equations or equation-like statements survive in the current project state, and all must be interpreted narrowly.

### 2.1 Foundational modular invariance

The corrected foundational statement is

`Z(\tau,\bar\tau) = Z(-1/\tau,-1/\bar\tau)`.

This is dimensionally consistent because the torus partition function and the modular parameter are dimensionless. The limiting check is structural rather than numerical: the relation is a symmetry statement, so the "limit" is closure under modular transformations rather than a continuum parameter limit.

### 2.2 2016 finite-`c` gap benchmark

The benchmark inequality carried in the project is

`Delta_gap <= c/6 + 1/3`.

This is dimensionally consistent because both `Delta_gap` and `c` are dimensionless in the active convention lock. The natural limiting checks are sensible:

- As `c -> 1^+`, the bound becomes `Delta_gap <= 1/2`.
- At the top of the 2026 candidate window, `c = 8/7`, the bound gives `Delta_gap <= 11/21`.

This remains the right local benchmark for comparing later numerical claims.

### 2.3 2023 integrality refinement

The important correction is here. The source does support a slight near-`c = 1` improvement, but the project should not present that result as a new universal closed-form formula. The safest representation is the schematic inequality

`Delta_gap^int(c approx 1) < Delta_gap^2016`,

with the explicit warning that this is a summary of the numerical trend, not a literal equation printed by the paper. The dimensional check is still clean, because both sides compare dimensionless gap bounds, but the real correction is logical: the claim is numerical and regime-specific.

### 2.4 2023 geometric threshold window

The geometric paper supports the window

`(c-1)/12 < Delta_gap^* < c/12`.

This is dimensionally consistent for the same reason as the 2016 benchmark. Its limiting cases are useful:

- As `c -> 1^+`, the window becomes `0 < Delta_gap^* < 1/12`.
- At `c = 8/7`, it becomes `1/84 < Delta_gap^* < 2/21`.

The width of the window is always `1/12`, so the statement remains numerically meaningful throughout the range of interest.

### 2.5 2026 ML search window

The 2026 paper's headline range,

`1 < c <= 8/7`,

is dimensionally consistent because it is only a central-charge interval. It is not by itself a dynamical equation and must not be read as an existence theorem. The source supports candidate truncated partition functions in that window, not exact solved CFT data.

## 3. Corrected Benchmark Chain

The audited literature now supports the following cleaned-up narrative.

`arXiv:1307.6562` supplies the foundational modular-invariance setup. `arXiv:1608.06241` is the decisive finite-`c` Virasoro benchmark for near-`c = 1` gap bounds and extremal-spectrum numerics. `arXiv:1903.06272` contributes a fast truncation algorithm for modular bootstrap and high-precision spectral-gap numerics. `arXiv:2308.08725` adds an integrality-based numerical refinement near `c = 1`, but not a new universal formula. `arXiv:2308.11692` adds the geometric/Hankel interpretation and the threshold window for `Delta_gap^*`. `arXiv:2604.01275` is the current machine-learning-style frontier and reports candidate truncated partition functions for `1 < c <= 8/7`, together with evidence for a stronger near-`c = 1` constraint than the 2016 benchmark.

That leaves the bottom line unchanged in substance but cleaner in wording: the 2026 paper justifies a modern ML-centered project framing, yet it does not justify claims of new exact finite-`c` CFTs without tighter truncation, residual, integrality, and non-ML cross-checks.

## 4. GPD State Audit

I rechecked the live GPD state after the textual corrections. The current machine-facing status is:

- `gpd --raw state validate`: valid, with only convention-lock warnings for 13 unused global slots.
- `gpd --raw health`: warn, with no failing checks.
- `gpd --raw validate project-contract GPD/project_contract.json`: valid, with zero warnings.
- `gpd --raw regression-check`: passes only because `phases_checked = 0`, so it is not real evidence that downstream numerical phases have been regression-tested.

The project record is therefore internally consistent at the coarse validator level, but the scientific claim set remains literature-only. No local solver campaign or independent numerical reproduction exists in this workspace. Any manuscript that claims more than a corrected literature synthesis would overstate the evidence.

## 5. Conclusion

The corrected paper is narrower than the original project rhetoric but stronger in the only way that matters: every citation now points to the intended source, every equation-like claim is dimensionally sensible, the limiting cases are explicit, and the local GPD record no longer treats the 2023 integrality refinement as a universal formula. The right present conclusion is fail-closed. The finite-`c` benchmark chain is real, the 2026 ML paper is a legitimate modern anchor, and the candidate `1 < c <= 8/7` window is worth studying. What is still missing is any local calculation that upgrades those candidate spectra into verified exact CFT data.

## References

1. D. Friedan and C. A. Keller, _Constraints on 2d CFT partition functions_, `arXiv:1307.6562`.
2. S. Collier, Y.-H. Lin, and X. Yin, _Modular Bootstrap Revisited_, `arXiv:1608.06241`.
3. N. Afkhami-Jeddi, T. Hartman, and A. Tajdini, _Fast Conformal Bootstrap and Constraints on 3d Gravity_, `arXiv:1903.06272`.
4. A. Liam Fitzpatrick and W. Li, _Improving Modular Bootstrap Bounds with Integrality_, `arXiv:2308.08725`.
5. L.-Y. Chiang, T.-C. Huang, Y.-t. Huang, W. Li, L. Rodina, and H.-C. Weng, _The Geometry of the Modular Bootstrap_, `arXiv:2308.11692`.
6. N. Benjamin, A. Liam Fitzpatrick, W. Li, and J. Thaler, _Descending into the Modular Bootstrap_, `arXiv:2604.01275`.
