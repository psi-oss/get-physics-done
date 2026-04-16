# Does Double-Scaled SYK Have a Semiclassical de Sitter Bulk Dual?

## Abstract

I revisit the current DSSYK/de Sitter literature with one narrow goal: to separate what is actually established from what is still extrapolation. Every citation in this note was rechecked against arXiv metadata and the corresponding current INSPIRE-linked publication record where one exists. After that audit, the strongest defensible claim remains limited. The literature supports semiclassical de Sitter-like bulk descriptions for restricted DSSYK sectors, observables, and scaling limits. It does not yet establish a complete, thermodynamically standard semiclassical de Sitter bulk dual for full DSSYK.

## 1. Citation-Checked Source Set

The corrected source set contains seven papers and no placeholders. Their roles are distinct.

`[1]` Narovlansky and Verlinde identify a doubled infinite-temperature DSSYK sector with an equal-energy constraint and show that its dressed two-point function matches a scalar Green function in de Sitter space. This is the original positive anchor for the dS interpretation.

`[2]` Verlinde and Zhang construct a 2D Liouville-de Sitter gravity model whose boundary two-point function reproduces the exact DSSYK two-point function to all orders in the double-scaling parameter `\lambda = p^2/N`. This sharpens the correlator evidence beyond a semiclassical leading-order match.

`[3]` Blommaert, Mertens, and Papalini reformulate the bulk picture as sine-dilaton gravity and show that canonical quantization reproduces the q-Schwarzian auxiliary system behind DSSYK chord diagrams. This supplies the strongest controlled low-dimensional bulk realization in the present literature.

`[4]` Okuyama shows that the upper edge of the DSSYK spectrum reproduces de Sitter JT gravity in a scaling limit. This provides a second route to a de Sitter-like semiclassical model, distinct from the original doubled-sector argument.

`[5]` Cui and Rozali extend the sine-dilaton bulk reconstruction to general matter correlators, including OTOCs and double-trumpet observables, and build a wormhole Hilbert-space picture from splitting and gluing.

`[6]` Rahman and Susskind argue that the early entropy-area mismatch depends on assumptions about the doubled DSSYK dictionary. Their point is not that the positive evidence vanishes, but that its interpretation is not assumption-free.

`[7]` Blommaert, Levine, Mertens, Papalini, and Parmentier sharpen the obstruction: periodic/sine-dilaton models require gauging a discrete shift symmetry, which discretizes lengths, yields null states, and makes the physical Hilbert space finite-dimensional. A naive Bekenstein-Hawking reading then fails.

## 2. Clean Positive Evidence

The positive case is now stronger than a slogan about one correlator. It contains three separate layers.

First, the original doubled-sector matching in `[1]` gives a concrete bulk observable. In dimensionally clean form the relation is

$$
m^2 R_{\mathrm{dS}}^2 = 4\Delta(1-\Delta).
$$

The older shorthand `m^2 = 4\Delta(1-\Delta)` hides the de Sitter radius and is therefore not the form I keep in the corrected manuscript. With `R_{\mathrm{dS}}` restored, the equation is dimensionless and its limiting behavior is explicit: `\Delta \to 0` or `\Delta \to 1` gives a massless scalar, while `\Delta = 1/2` gives `m^2 R_{\mathrm{dS}}^2 = 1`.

Second, `[2]` promotes the discussion from a semiclassical match to an exact two-point-function statement within the double-scaling regime:

$$
G_{\mathrm{Liouville-dS}}^{(2)}(\tau_1,\tau_2;\lambda)
=
G_{\mathrm{DSSYK}}^{(2)}(\tau_1,\tau_2;\lambda).
$$

This equality is still narrower than a claim of full theory equivalence. It is an exact statement about the normalized boundary two-point function. In the limit `\lambda \to 0`, it reduces to the semiclassical picture behind `[1]`; at finite `\lambda`, it remains a correlator statement rather than a complete thermodynamic dictionary.

Third, `[3]`, `[4]`, and `[5]` broaden the bulk story. Sine-dilaton gravity reproduces the q-Schwarzian sector, the upper spectral edge yields de Sitter JT gravity, and bulk matter correlators and OTOCs can be reproduced geometrically. The positive evidence is therefore now a network of mutually reinforcing low-dimensional constructions rather than a single isolated observation.

## 3. Why the Evidence Still Falls Short

The obstruction is no longer that there is no positive evidence. The obstruction is that the positive evidence does not yet assemble into a full semiclassical de Sitter bulk dual with standard thermodynamic meaning.

The first caution, emphasized in `[6]`, is that early entropy-area disagreements are dictionary-sensitive. This makes the literature less decisive than a superficial “paper A versus paper B” narrative would suggest.

The second caution, sharpened in `[7]`, is more structural. In periodic/sine-dilaton gravity the physical Hilbert space can become finite-dimensional after gauging the discrete shift symmetry, and lengths below a threshold become null states. That is not a small technical wrinkle. It directly pressures the naive horizon-entropy interpretation one would want for an ordinary semiclassical de Sitter bulk.

The third caution is scope. The cleanest positive evidence lives in one of three settings:

- doubled constrained sectors,
- upper-edge spectral scaling limits,
- or specific observables such as two-point functions and OTOCs.

That is not the same as a statement about generic DSSYK states and observables.

## 4. Corrected Claim Hierarchy

The corrected hierarchy is therefore:

1. DSSYK has verified de Sitter-like semiclassical bulk descriptions for restricted sectors and limits.
2. Those descriptions are most sharply realized in Liouville-de Sitter, sine-dilaton, and de Sitter JT models.
3. The literature does not yet show that these reconstructions glue into one globally coherent, entropy-consistent semiclassical de Sitter bulk dual for full DSSYK.

This is the key place where the paper had to be rewritten. The earlier report language was too close to a workflow verdict and too loose about what kind of duality was actually being claimed. The corrected note keeps the restricted-sector statement and removes any wording that suggests the full problem is settled.

## 5. Bottom Line

The best current statement is:

> DSSYK admits credible semiclassical de Sitter-like bulk descriptions in specific constrained sectors, observables, and spectral limits. However, the present literature still falls short of establishing a complete semiclassical de Sitter bulk dual for DSSYK as a whole.

That means the answer is qualified rather than binary:

- **Yes**, for restricted dS/JT/sine-dilaton reconstructions of selected observables and limits.
- **No**, for a finished full-model semiclassical de Sitter dual with a standard thermodynamic and Hilbert-space interpretation.

The main open problem is no longer whether one can match any de Sitter-flavored observable at all. It is whether the successful low-dimensional reconstructions can be shown to describe one and the same bulk theory, with a consistent entropy and state-counting dictionary, beyond the special sectors where they currently work best.

## References

`[1]` Vladimir Narovlansky and Herman Verlinde, *Double-scaled SYK and de Sitter Holography*, `arXiv:2310.16994`, `JHEP 05 (2025) 032`.

`[2]` Herman Verlinde and Mengyang Zhang, *SYK Correlators from 2D Liouville-de Sitter Gravity*, `arXiv:2402.02584`, `JHEP 05 (2025) 053`.

`[3]` Andreas Blommaert, Thomas G. Mertens, and Jacopo Papalini, *The dilaton gravity hologram of double-scaled SYK*, `arXiv:2404.03535`, `JHEP 06 (2025) 050`.

`[4]` Kazumi Okuyama, *de Sitter JT gravity from double-scaled SYK*, `arXiv:2505.08116`, `JHEP 08 (2025) 181`.

`[5]` Chuanxin Cui and Moshe Rozali, *Splitting and gluing in sine-dilaton gravity: matter correlators and the wormhole Hilbert space*, `arXiv:2509.01680`, `JHEP 02 (2026) 160`.

`[6]` Adel A. Rahman and Leonard Susskind, *Comments on a Paper by Narovlansky and Verlinde*, `arXiv:2312.04097`.

`[7]` Andreas Blommaert, Adam Levine, Thomas G. Mertens, Jacopo Papalini, and Klaas Parmentier, *An entropic puzzle in periodic dilaton gravity and DSSYK*, `arXiv:2411.16922`, `JHEP 07 (2025) 093`.
