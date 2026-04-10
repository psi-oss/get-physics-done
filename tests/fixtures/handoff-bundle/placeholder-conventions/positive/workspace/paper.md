# Quantum-Information Routes to the Ryu-Takayanagi Formula

_Corrected manuscript drafted from the verified project record on 2026-04-09. The workspace did not contain a standalone paper source file, so this document serves as the rewritten paper._

## Abstract

The central question is whether the leading Ryu-Takayanagi (RT) area term can be derived from quantum-information structure alone, rather than imported from semiclassical gravity. A citation re-audit confirms that the core anchor papers were cited with the correct arXiv identifiers: RT06 (`hep-th/0603001`), ADH14 (`1411.7041`), JLMS15 (`1512.06431`), DHW16 (`1601.05416`), HNQTWY16 (`1601.01694`), and Gao24 (`2402.18655`). A post-2024 update also verifies Bao25 (`2504.12388`), which makes an explicit RT-derivation claim for a restricted class of multi-boundary AdS\(_3\)/CFT\(_2\) large-`c` ensemble states. The corrected synthesis is therefore more precise than the earlier workspace summary: quantum-information methods robustly explain reconstruction structure and subleading correction patterns, and now also support one nontrivial special-case derivation claim, but they do not yet furnish a generic QI-only derivation of the leading RT term across holographic states.

## 1. Citation Audit

The existing six anchor citations were checked directly against arXiv and against the INSPIRE cross-links exposed on each arXiv record. No arXiv identifier in the project pointed to the wrong paper.

- RT06: Shinsei Ryu and Tadashi Takayanagi, _Holographic Derivation of Entanglement Entropy from AdS/CFT_, `hep-th/0603001`. This remains the benchmark statement of the static RT formula.
- ADH14: Ahmed Almheiri, Xi Dong, and Daniel Harlow, _Bulk Locality and Quantum Error Correction in AdS/CFT_, `1411.7041`. This correctly anchors the operator-algebra / QEC language.
- JLMS15: Daniel L. Jafferis, Aitor Lewkowycz, Juan Maldacena, and S. Josephine Suh, _Relative entropy equals bulk relative entropy_, `1512.06431`. This correctly anchors the relative-entropy route to entanglement wedge reasoning.
- DHW16: Xi Dong, Daniel Harlow, and Aron C. Wall, _Reconstruction of Bulk Operators within the Entanglement Wedge in Gauge-Gravity Duality_, `1601.05416`. This correctly anchors entanglement wedge reconstruction.
- HNQTWY16: Patrick Hayden, Sepehr Nezami, Xiao-Liang Qi, Nathaniel Thomas, Michael Walter, and Zhao Yang, _Holographic duality from random tensor networks_, `1601.01694`. This correctly anchors the random-tensor-network toy-model route.
- Gao24: Ping Gao, _Modular flow in JT gravity and entanglement wedge reconstruction_, `2402.18655`. This correctly anchors the modular-flow reconstruction frontier.

The self-review also verified one missing post-2024 frontier anchor:

- Bao25: Ning Bao, Hao Geng, and Yikun Jiang, _Ryu-Takayanagi Formula for Multi-Boundary Black Holes from 2D Large-$c$ CFT Ensemble_, `2504.12388`. This is a real 2025 derivation claim and cannot be ignored in an up-to-date synthesis.

## 2. Equation Audit

Only three equations were materially present in the project state, and all three needed explicit scope checks.

### 2.1 Static RT formula

The benchmark formula is

`S(A) = Area(gamma_A)/(4 G_N)`.

This is dimensionally consistent. In bulk dimension `d+1`, the codimension-2 area has dimension `L^(d-1)` and Newton's constant has the same dimension, so the ratio is dimensionless, as entropy must be. The natural limiting checks are also consistent:

- If `A` shrinks to the empty region, the homologous extremal surface has vanishing area and `S(A) -> 0`.
- For a pure global state, taking `A` to the full boundary gives `S(A) = 0`; in static examples this is consistent with the complementary-region prescription.

The workspace's use of RT06 as a benchmark input is therefore dimensionally and conceptually sound, provided the statement stays restricted to static semiclassical settings.

### 2.2 JLMS relative entropy equality

The JLMS relation was stored as

`S_rel^CFT(A) = S_rel^bulk(a)`.

This is dimensionally consistent because both sides are relative entropies and therefore dimensionless. The key limiting case is the trivial one: for identical reference and perturbed states, both sides vanish. The more important correction is not dimensional but logical: JLMS is a semiclassical code-subspace statement and should not be promoted into an origin-derivation of the leading RT term.

### 2.3 Random tensor network formula

The project's stored shorthand

`S(A) = mincut(A) + S_bulk`

was too loose. A bare graph-theoretic cut count is not itself an entropy unless it is converted into a weighted cut cost. The corrected statement is

`S(A) ≈ S_cut(A) + S_bulk`,

where `S_cut(A)` is the entropy weight of the minimal cut, for example `|gamma_A| log D` in a uniform-bond-dimension network. With that interpretation the formula is dimensionally consistent, because both terms are entropies. The correct limiting case is that when bulk entanglement is turned off, the expression reduces to the weighted minimal-cut term alone. This remains heuristic support, not a derivation of the geometric area term in semiclassical gravity.

## 3. Corrected Synthesis

The citation and equation audit supports the following cleaned-up narrative.

RT06 still sets the benchmark problem. ADH14, JLMS15, and DHW16 explain how subregion duality, relative entropy, and entanglement wedge reconstruction fit together once the semiclassical setup is granted. HNQTWY16 gives the cleanest toy-model realization of RT-like structure, but only after geometric or network-design input is built in. Gao24 strengthens the modular-flow and reconstruction side of the story in JT gravity. Bao25 goes further: it claims a derivation of RT from boundary CFT data in a restricted multi-boundary AdS\(_3\)/CFT\(_2\) large-`c` ensemble framework.

That means the older blanket statement "no post-2024 derivation-style progress exists" is no longer defensible. The corrected claim is narrower and stronger at once:

1. There is now verified post-2024 progress on deriving RT-like behavior from boundary data in a special setting.
2. The most general and portable quantum-information results still concern reconstruction structure and subleading correction patterns rather than a generic leading-area derivation.
3. The open problem is no longer whether _any_ recent derivation claim exists, but whether Bao25-style mechanisms generalize beyond special AdS\(_3\)/CFT\(_2\) ensemble states without reimporting semiclassical structure in disguise.

## 4. Conclusion

The corrected bottom line is fail-closed and should replace the earlier workspace shorthand. Quantum-information methods do not yet provide a generic, fully established derivation of the leading RT area term across holographic states. However, the literature is no longer static at Gao24: Bao25 is a real 2025 derivation claim in a restricted setting and must be treated as the current sharpest positive signal rather than omitted from the story. The right present verdict is therefore: generic closure remains open, restricted-scope progress is real, and the distinction between those two statements is the main thing the paper must preserve.

## References

- RT06: S. Ryu and T. Takayanagi, _Holographic Derivation of Entanglement Entropy from AdS/CFT_, `hep-th/0603001`.
- ADH14: A. Almheiri, X. Dong, and D. Harlow, _Bulk Locality and Quantum Error Correction in AdS/CFT_, `1411.7041`.
- JLMS15: D. L. Jafferis, A. Lewkowycz, J. Maldacena, and S. J. Suh, _Relative entropy equals bulk relative entropy_, `1512.06431`.
- DHW16: X. Dong, D. Harlow, and A. C. Wall, _Reconstruction of Bulk Operators within the Entanglement Wedge in Gauge-Gravity Duality_, `1601.05416`.
- HNQTWY16: P. Hayden, S. Nezami, X.-L. Qi, N. Thomas, M. Walter, and Z. Yang, _Holographic duality from random tensor networks_, `1601.01694`.
- Gao24: P. Gao, _Modular flow in JT gravity and entanglement wedge reconstruction_, `2402.18655`.
- Bao25: N. Bao, H. Geng, and Y. Jiang, _Ryu-Takayanagi Formula for Multi-Boundary Black Holes from 2D Large-$c$ CFT Ensemble_, `2504.12388`.
