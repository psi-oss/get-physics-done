# Error Thresholds in Holographic Codes

## Executive Verdict

The checked literature supports a narrow conclusion, not a sweeping one. Erasure-threshold behavior is well established for HaPPY-style and heptagon/Steane constructions, phenomenological Pauli and depolarizing thresholds are supported under named decoders, and arXiv:2408.06232v3 gives a strong zero-rate biased-noise benchmark. What remains unresolved in the inspected source set is a finite-rate biased-noise threshold map under matched decoder and observable conventions.

## Audit Basis

This revision rechecked all five anchor citations against their arXiv abstract records on 2026-04-09. All five arXiv IDs resolve to the intended papers, author lists, and publication metadata. The only citation irregularity is arXiv:2408.06232: the official arXiv abstract page lists the title "Biased-Noise Thresholds of Zero-Rate Holographic Codes with Tensor-Network Decoding," with submission on 2024-08-12 and v3 revised on 2025-12-31, so I cite it by arXiv ID and version/date rather than by year alone.

This note contains no analytic equations or derived formulae. The quantitative content is limited to quoted threshold probabilities and threshold-class statements. The dimensional audit therefore reduces to checking that every quoted number is a dimensionless physical error probability. That check passes for the 7%-16% Pauli-threshold range and the 9.4% depolarizing threshold.

## Live GPD Status

A fresh runtime check still reports seven intermediate results, zero phase-1 plans, zero summaries, zero validation artifacts, and zero verification artifacts. `gpd health` and `gpd validate consistency` still return warnings only, while `gpd --raw query search --text threshold` returns zero matches and `gpd --raw result search --text threshold` returns five matches. The result registry is coherent, but it is still unverified through phase artifacts, so every scientific conclusion here remains provisional.

## Threshold Map

| Source | Code family / rate regime | Channel | Decoder / observable | Supported claim after audit | Audit note |
| ------ | ------------------------- | ------- | -------------------- | --------------------------- | ---------- |
| Pastawski et al. (2015) | HaPPY-style holographic code; foundational baseline | Erasure / recovery baseline | Tensor-network holographic-code construction | Establishes the canonical HaPPY-style baseline and the qualitative erasure-threshold story | Do not quote a precise threshold number from this note without reopening the full paper |
| Harris et al. (2018) | CSS heptagon holographic code; finite-rate | Erasure | Optimal erasure decoder, central logical qubit | Supports the claim that the heptagon construction improves on earlier holographic erasure benchmarks | The abstract supports only a qualitative benchmark claim; no exact threshold number is quoted here |
| Harris et al. (2020) | Multiple holographic families with varying code rates | Pauli errors | Integer-optimization decoder, bulk qubits | Reports phenomenological Pauli thresholds from 7% to 16%, depending on code rate | Quantitative claim matches the arXiv abstract |
| Farrelly et al. (2022) | Max-rate holographic Steane code | Depolarizing | Parallel tensor-network decoder, bulk qubits | Reports a 9.4% bulk depolarizing threshold | Quantitative claim matches the arXiv abstract |
| Fan et al., arXiv:2408.06232v3 | Zero-rate holographic families | Biased Pauli noise | Tensor-network decoding | Reports that all tested zero-rate codes reach the hashing bound in some bias regime, with several exceeding prior 2-Pauli benchmarks | Cite by arXiv ID/version because the record is a 2024 submission with a 2025 v3 revision and mirror title drift |

## Interpretation

The literature does not describe a single threshold observable. Erasure, depolarizing, and biased-noise results are reported with different decoders and different logical-qubit observables, so direct ranking is unsafe unless those choices are aligned first.

Within the inspected anchor set, the clearest asymmetry is between a recent zero-rate biased-noise map and the absence of a matched finite-rate biased-noise threshold map in the same comparison language. That is weaker than claiming the entire literature has no such result, but it is strong enough to justify a focused follow-on search or computation.

## Revised Open Problem

The most defensible next step is:

**Build or locate a finite-rate biased-noise threshold map for a representative holographic family and compare it to arXiv:2408.06232v3 under matched decoder and observable definitions.**

Minimum comparison discipline:

1. Hold the decoder family fixed, or benchmark the decoder mismatch explicitly.
2. Keep the logical-qubit observable explicit: central, bulk, or whole-code.
3. Use the same biased-noise parameterization as the zero-rate benchmark.
4. State whether the finite-rate family reaches, misses, or exceeds the relevant hashing-bound comparison.

## Caveats

- This report remains upstream of phase execution. The workspace still has no completed phase summaries and no verification artifacts.
- The 2018 heptagon paper was only used here for the qualitative erasure-benchmark claim visible on the arXiv abstract page. A manuscript-quality numerical quote would require reopening the full text.
- INSPIRE record bodies were not directly renderable in this environment. Citation-ID verification therefore rests on the arXiv abstract pages and their INSPIRE mappings, not on a full INSPIRE metadata scrape.
- The frontier claim is only as strong as the checked source set. A credible finite-rate biased-noise threshold paper under matched conventions would force revision.

## Sources

- Pastawski, Yoshida, Harlow, and Preskill, "Holographic quantum error-correcting codes: Toy models for the bulk/boundary correspondence," JHEP 06 (2015) 149, [arXiv:1503.06237](https://arxiv.org/abs/1503.06237)
- Harris, McMahon, Brennen, and Stace, "Calderbank-Steane-Shor Holographic Quantum Error Correcting Codes," Phys. Rev. A 98, 052301 (2018), [arXiv:1806.06472](https://arxiv.org/abs/1806.06472)
- Harris, Coupe, McMahon, Brennen, and Stace, "Decoding Holographic Codes with an Integer Optimisation Decoder," Phys. Rev. A 102, 062417 (2020), [arXiv:2008.10206](https://arxiv.org/abs/2008.10206)
- Farrelly, Harris, McMahon, and Stace, "Parallel decoding of multiple logical qubits in tensor-network codes," Phys. Rev. A 105, 052446 (2022), [arXiv:2012.07317](https://arxiv.org/abs/2012.07317)
- Fan, Steinberg, Jahn, Cao, and Feld, arXiv:2408.06232v3, submitted 2024-08-12 and revised 2025-12-31, [arXiv:2408.06232](https://arxiv.org/abs/2408.06232)
