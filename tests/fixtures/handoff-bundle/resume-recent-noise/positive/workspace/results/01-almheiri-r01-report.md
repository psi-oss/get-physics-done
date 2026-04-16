# Does DSSYK Have a Semiclassical dS Bulk Dual?

Date: 2026-04-09

## Abstract

I re-audited the four anchor citations against arXiv and their INSPIRE-linked journal metadata, checked the formulas that support the strongest positive claims, and compared the manuscript against the live GPD state. I found no arXiv-ID mismatch: all four citations point to the intended papers. The main correction is interpretive rather than bibliographic. The Narovlansky-Verlinde radius relation implies a parametrically semiclassical bulk only when `lambda = p^2/N << 1`, and the scalar-mass formula should be read in de Sitter-radius units as `m^2 R_dS^2 = 4 Delta (1 - Delta)`. The procedural state also had one stale surface: Phase 01 is `Ready to execute`, not `Ready to plan`. With those corrections, my verdict is sharper but unchanged: the literature supports a serious de Sitter-related holographic sector for doubled or auxiliary DSSYK constructions, but it does not yet establish a qualification-free full semiclassical de Sitter bulk dual of DSSYK proper.

## Citation audit

I verified every citation used in the original report.

- `2209.09997` is **Adel A. Rahman, "dS JT Gravity and Double-Scaled SYK"**, submitted on **September 20, 2022**. The arXiv identifier is correct and matches the title and author used in the report.
- `2310.16994` is **Vladimir Narovlansky and Herman Verlinde, "Double-scaled SYK and de Sitter Holography"**, submitted on **October 25, 2023**. The arXiv identifier is correct. The published version is `JHEP05(2025)032`.
- `2402.02584` is **Herman Verlinde and Mengyang Zhang, "SYK Correlators from 2D Liouville-de Sitter Gravity"**, submitted on **February 4, 2024**. The arXiv identifier is correct. The published version is `JHEP05(2025)053`.
- `2404.03535` is **Andreas Blommaert, Thomas G. Mertens, and Jacopo Papalini, "The dilaton gravity hologram of double-scaled SYK"**, submitted on **April 4, 2024** and revised on **June 16, 2025**. The arXiv identifier is correct. The published version is `JHEP06(2025)050`.

I found no case where an arXiv ID in the manuscript pointed to an unrelated paper.

## Equation and limit audit

The original report did not write equations explicitly, so I audited the equations implicit in the cited abstracts and in the report's strongest claims.

- From `2310.16994`, the bulk-radius relation is `R_dS / G_N = 4 pi N / p^2`. This is dimensionally consistent in three bulk dimensions because both `R_dS` and `G_N` carry length units, so the left-hand side is dimensionless.
- Using `2402.02584`, which states the exact result to all orders in `lambda = p^2 / N`, the same relation becomes `R_dS / G_N = 4 pi / lambda`.
  - Inference from the cited formula: only `lambda << 1` gives a parametrically large radius in Planck units.
  - `N -> infinity` at fixed `lambda = O(1)` does not by itself make the bulk parametrically semiclassical.
- The `2310.16994` abstract writes `m^2 = 4 Delta (1 - Delta)`. Taken literally, that is dimensionally inconsistent unless the de Sitter radius is set to 1. The dimensionally correct invariant statement is therefore `m^2 R_dS^2 = 4 Delta (1 - Delta)`.
  - This is an inference from dimensional consistency, not a verbatim formula from the abstract.
  - Limiting checks are sensible: `Delta -> 0` or `Delta -> 1` gives `m^2 R_dS^2 -> 0`, while `Delta = 1/2` gives `m^2 R_dS^2 = 1`.
- `2209.09997` explicitly concerns a high-temperature `DSSYK_infty` limit. It should not be cited as if it already established a generic DSSYK bulk dual without that limit.
- `2402.02584` strengthens the two-point-function evidence to all orders in `lambda`, but it still does not by itself settle the thermal, entropic, or operator-dictionary questions.
- `2404.03535` strengthens the auxiliary bulk interpretation by deriving the q-Schwarzian/sine-dilaton dual and a fake-temperature dictionary, but that makes the final picture more subtle than a plain semiclassical de Sitter bulk for DSSYK proper.

## GPD state audit

The physics verdict and the project state are not in conflict, but the old manuscript mixed them together too loosely.

- The authoritative state snapshot still says Phase 01 is `Ready to execute`, with `2` validated plans, `0` summaries, `0%` progress, and `R-01-05-first-pass-verdict` as the last canonical result.
- The result dependency chain is still internally consistent: `R-01-01-dsjt -> R-01-02-ds3corr -> R-01-03-liouvilleds -> R-01-04-faketemp -> R-01-05-first-pass-verdict`.
- Those results remain unverified. The verdict is therefore still a defended literature synthesis, not a workflow-complete verification artifact.
- One stale value did persist in the project documents: `GPD/ROADMAP.md` still said Phase 1 was `Ready to plan`. I corrected that to `Ready to execute`.
- I also tightened the `R-01-02-ds3corr` validity statement in the state artifacts so it no longer reads like a generic large-`N` semiclassical theorem. The small-`lambda` caveat is now explicit.

## Corrected verdict

My corrected verdict is:

**DSSYK supports a strong de Sitter-related holographic sector, but the cleanest positive evidence still runs through doubled or auxiliary constructions and a nontrivial temperature dictionary. That is not yet the same thing as a qualification-free full semiclassical de Sitter bulk dual of DSSYK proper.**

More concretely:

1. `2209.09997` supports a positive dS-JT interpretation, but only in a high-temperature limit.
2. `2310.16994` gives a sharp doubled-sector correlator match and a radius formula, but the parametrically semiclassical regime is narrower than the old prose made explicit.
3. `2402.02584` strengthens the two-point-function evidence dramatically, but still at the level of correlators.
4. `2404.03535` gives the most precise auxiliary holographic dictionary, while simultaneously making clear that fake temperature and bulk quantization prevent an easy upgrade to a plain vanilla semiclassical dS dual of DSSYK itself.

So the right classification remains:

**sector-restricted or dictionary-dependent semiclassical correspondence, not yet a fully settled semiclassical dS bulk dual of DSSYK proper.**

## Sources

- [arXiv:2209.09997, "dS JT Gravity and Double-Scaled SYK"](https://arxiv.org/abs/2209.09997)
- [arXiv:2310.16994, "Double-scaled SYK and de Sitter Holography"](https://arxiv.org/abs/2310.16994)
- [SCOAP3 record for `2310.16994` / `JHEP05(2025)032`](https://repo.scoap3.org/records/97899)
- [arXiv:2402.02584, "SYK Correlators from 2D Liouville-de Sitter Gravity"](https://arxiv.org/abs/2402.02584)
- [Springer page for `JHEP05(2025)053`](https://link.springer.com/article/10.1007/JHEP05%282025%29053)
- [arXiv:2404.03535, "The dilaton gravity hologram of double-scaled SYK"](https://arxiv.org/abs/2404.03535)
- [Springer page for `JHEP06(2025)050`](https://link.springer.com/article/10.1007/JHEP06%282025%29050)
