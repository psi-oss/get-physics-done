# Does DSSYK Have a Semiclassical de Sitter Bulk Dual?

**Date:** 2026-04-09
**Workspace:** `01-almheiri-r02`

## Short answer

Not as a clean, controlled statement about generic DSSYK.

After re-checking the citations, the scaling relations, and the later 2025-2026 literature, the strongest defensible claim is narrower:

- DSSYK has real de Sitter-flavored sectors and controlled de Sitter limits.
- The cleanest global holographic statement still points to sine-dilaton or periodic-dilaton gravity.
- No paper I found removes the entropy, Hilbert-space, and temperature-dictionary objections strongly enough to justify the slogan "DSSYK has a controlled semiclassical de Sitter bulk dual."

## Corrections from this review

- `arXiv:2206.01083` is by Henry Lin and Leonard Susskind, submitted on June 2, 2022, not by Susskind alone.
- `arXiv:2209.09999` is Leonard Susskind's companion paper, not Adel Rahman's.
- The original draft under-described the control parameter behind the Narovlansky-Verlinde radius formula. Their abstract gives `R_{dS}/G_N = 4\pi N/p^2 = 4\pi/\lambda` with `\lambda = p^2/N`, so a parametrically semiclassical bulk requires small `\lambda`, not merely `N -> infinity` at fixed `\lambda`.
- The original draft also omitted directly relevant 2025 papers that sharpen both sides of the question: Verlinde's chord/de Sitter paper, Verlinde-Zhang's Liouville-de Sitter correlator paper, Okuyama's upper-edge dS JT paper, and Miyashita-Sekino-Susskind's flat-space-limit paper.

## What supports a de Sitter reading

- Lin and Susskind's `Infinite Temperature's Not So Hot` (`arXiv:2206.01083`) is the clean starting point for the infinite-temperature DSSYK to de Sitter idea and the tomperature discussion.
- Rahman's `dS JT Gravity and Double-Scaled SYK` (`arXiv:2209.09997`) and Susskind's companion `De Sitter Space, Double-Scaled SYK, and the Separation of Scales in the Semiclassical Limit` (`arXiv:2209.09999`) push that idea into a dS-JT and semiclassical static-patch story.
- Narovlansky and Verlinde's `Double-scaled SYK and de Sitter Holography` (`arXiv:2310.16994`) gives the sharpest early positive result: in the doubled equal-energy sector, a dressed two-point function matches a massive-scalar Green function in 3D de Sitter, with `R_{dS}/G_N = 4\pi N/p^2`.
- Later work strengthens the claim that de Sitter structures are genuinely present. Verlinde's `Double-scaled SYK, chords and de Sitter gravity` (`arXiv:2402.00635`) matches the exact chord rules and energy spectrum to 3D de Sitter gravity, and Verlinde-Zhang's `SYK correlators from 2D Liouville-de Sitter gravity` (`arXiv:2402.02584`) reproduces the doubled-model two-point function to all orders in `\lambda = p^2/N`.
- Okuyama's `de Sitter JT gravity from double-scaled SYK` (`arXiv:2505.08116`) is especially important for the self-audit because it narrows the conceptual gap between the de Sitter and sine-dilaton stories: the upper edge `E = E_0` gives a dS-JT scaling limit, and the paper argues that this is consistent with the classical sine-dilaton solution.

These are not empty analogies. They are enough to rule out a dismissive "there is no de Sitter content here" response.

## Why that still does not amount to a clean semiclassical dS bulk dual

- The main positive formula is not yet a global semiclassical control parameter. Since `R_{dS}/G_N = 4\pi/\lambda`, the doubled-model result only becomes parametrically semiclassical when `\lambda << 1`. Large `N` alone, with `\lambda` fixed and order one, does not force a large de Sitter radius in Planck units.
- Rahman and Susskind's `Comments on a Paper by Narovlansky and Verlinde` (`arXiv:2312.04097`) still matters because it attacks the safest place a semiclassical claim should survive: entropy-area scaling, temperature identification, Hamiltonian-to-mass mapping, and the placement of conical-defect states. Their abstract explicitly says the competing conclusions differ by factors that diverge as `N -> infinity`.
- Blommaert, Mertens, and Papalini's `The dilaton gravity hologram of double-scaled SYK` (`arXiv:2404.03535`) supplies the cleanest global duality statement I found: canonical sine-dilaton quantization reproduces the q-Schwarzian system behind DSSYK. But that same paper emphasizes fake temperature, defects, and discrete bulk structure rather than an ordinary semiclassical de Sitter geometry.
- Blommaert, Levine, Mertens, Papalini, and Parmentier's `An entropic puzzle in periodic dilaton gravity and DSSYK` (`arXiv:2411.16922`) sharpens the objection by arguing that gauging the periodic shift symmetry discretizes geodesic length, creates null states below a threshold, and makes the Hilbert space finite dimensional. That is difficult to reconcile with a naive Bekenstein-Hawking reading.
- Miyashita, Sekino, and Susskind's `DSSYK at infinite temperature: the flat-space limit and the 't Hooft model` (`arXiv:2506.18054`) cuts against any too-simple global dS slogan: in the infinite-radius limit the bulk description flows to a flat-space or Rindler-like theory rather than staying uniquely de Sitter.
- Cui and Rozali's `Splitting and gluing in sine-dilaton gravity: matter correlators and the wormhole Hilbert space` (`arXiv:2509.01680`, JHEP 02 (2026) 160) extends the sine-dilaton line to general matter correlators and wormhole Hilbert-space structure. It strengthens the exact dilaton-gravity story, not the claim that the full DSSYK bulk is an uncontested semiclassical de Sitter spacetime.

## Equation audit

- `R_{dS}/G_N = 4\pi N/p^2` is dimensionally consistent in the 3D gravity setup used by Narovlansky-Verlinde because both `R_{dS}` and `G_N` carry length units, so the left-hand side is dimensionless, matching the dimensionless right-hand side.
- Rewriting the same relation as `R_{dS}/G_N = 4\pi/\lambda` with `\lambda = p^2/N` exposes the real limiting-case statement:
  - `\lambda << 1` gives a parametrically large radius in Planck units.
  - `\lambda = O(1)` keeps `R_{dS}/G_N = O(1)`, so the geometry is not parametrically semiclassical.
  - `N -> infinity` at fixed `\lambda` does not by itself make the bulk semiclassical.
- The GPD result registry should therefore treat the de Sitter matching result as a doubled-sector statement with a small-`\lambda` or upper-edge caveat, not as a generic large-`N` theorem about all of DSSYK.

## Corrected verdict

As of **April 9, 2026**, my best-supported verdict is:

> DSSYK has controlled de Sitter-like sectors and limits, together with a precise sine-dilaton or periodic-dilaton bulk dual, but I do not find a paper that establishes a clean, global, controlled semiclassical de Sitter bulk dual for generic DSSYK.

My confidence is:

- **High** that the literature supports genuine de Sitter-flavored physics in restricted sectors or limits.
- **High** that the cleanest exact holographic statement currently runs through sine-dilaton or periodic-dilaton gravity.
- **Medium** that the later dS-JT and Liouville-de Sitter constructions can be unified with the sine-dilaton picture without leaving the "sector/limit" level.
- **High** that the original one-line slogan "DSSYK has a semiclassical dS bulk dual" is too strong.

## What would change the answer

I would revise this judgment if a later paper did one of the following:

- derived an uncontested entropy-area relation in a controlled DSSYK limit;
- resolved the fake-temperature dictionary without shifting to a non-semiclassical or discrete bulk picture;
- showed that the exact sine-dilaton or periodic-dilaton hologram reduces to an ordinary semiclassical de Sitter spacetime beyond a special sector or edge limit;
- demonstrated that the finite-dimensional or null-state Hilbert-space structure is fully compatible with the semiclassical de Sitter interpretation rather than a warning against it.

## Sources

- Henry Lin and Leonard Susskind, `Infinite Temperature's Not So Hot` (`arXiv:2206.01083`): https://arxiv.org/abs/2206.01083
- Adel A. Rahman, `dS JT Gravity and Double-Scaled SYK` (`arXiv:2209.09997`): https://arxiv.org/abs/2209.09997
- Leonard Susskind, `De Sitter Space, Double-Scaled SYK, and the Separation of Scales in the Semiclassical Limit` (`arXiv:2209.09999`): https://arxiv.org/abs/2209.09999
- Vladimir Narovlansky and Herman Verlinde, `Double-scaled SYK and de Sitter Holography` (`arXiv:2310.16994`): https://arxiv.org/abs/2310.16994
- Herman Verlinde, `Double-scaled SYK, chords and de Sitter gravity` (JHEP 03 (2025) 076): https://link.springer.com/article/10.1007/JHEP03%282025%29076
- Herman Verlinde and Mengyang Zhang, `SYK correlators from 2D Liouville-de Sitter gravity` (JHEP 05 (2025) 053; `arXiv:2402.02584`): https://link.springer.com/article/10.1007/JHEP05%282025%29053
- Adel A. Rahman and Leonard Susskind, `Comments on a Paper by Narovlansky and Verlinde` (`arXiv:2312.04097`): https://arxiv.org/abs/2312.04097
- Andreas Blommaert, Thomas G. Mertens, and Jacopo Papalini, `The dilaton gravity hologram of double-scaled SYK` (`arXiv:2404.03535`; JHEP 06 (2025) 050): https://arxiv.org/abs/2404.03535
- Andreas Blommaert, Adam Levine, Thomas G. Mertens, Jacopo Papalini, and Klaas Parmentier, `An entropic puzzle in periodic dilaton gravity and DSSYK` (`arXiv:2411.16922`; JHEP 07 (2025) 093): https://arxiv.org/abs/2411.16922
- Kazumi Okuyama, `de Sitter JT gravity from double-scaled SYK` (`arXiv:2505.08116`; JHEP 08 (2025) 181): https://link.springer.com/article/10.1007/JHEP08%282025%29181
- Shoichiro Miyashita, Yasuhiro Sekino, and Leonard Susskind, `DSSYK at infinite temperature: the flat-space limit and the 't Hooft model` (`arXiv:2506.18054`; JHEP 11 (2025) 107): https://link.springer.com/article/10.1007/JHEP11%282025%29107
- Chuanxin Cui and Moshe Rozali, `Splitting and gluing in sine-dilaton gravity: matter correlators and the wormhole Hilbert space` (`arXiv:2509.01680`; JHEP 02 (2026) 160): https://link.springer.com/article/10.1007/JHEP02%282026%29160
