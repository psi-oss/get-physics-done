# Cosmological Singularity Diagnostics from Entangled CFTs

## Abstract

This manuscript is a corrected synthesis of the current project record after a citation and state audit. Three changes were necessary. First, `arXiv:2307.14416` is not a dS/dS entropy-matching paper: it constructs entangled microstates of a pair of holographic CFTs whose dual semiclassical description includes big-bang/big-crunch AdS cosmologies. Second, `arXiv:2411.14673` is a nearby multi-CFT cosmology construction, not a stand-alone singularity-diagnostic calculation. Third, the benchmark set was incomplete without `arXiv:1404.2309`, which supplies the clearest boundary-correlator signature of a cosmological singularity. With those corrections in place, the strongest defensible conclusion is conservative: the Antonini construction is best treated as a benchmarked singularity-diagnostic framework, not as a demonstrated mechanism of microscopic singularity resolution.

## 1. Corrected Scope

The project question is whether entangled holographic CFT sectors can diagnose or resolve cosmological singularities more sharply than existing Kasner-like benchmarks. The corrected benchmark map separates three roles that had become blurred in the prior draft. Antonini-Sasieta-Swingle provides the target entangled-CFT cosmology. Manu-Narayan-Paul and Narayan-Saini-Yadav provide the strongest extremal-surface and complexity evidence for probe avoidance near singularities. Engelhardt-Hertog-Horowitz provides the cleanest boundary-field-theory signature of a singularity through heavy-operator correlators. Sahu-Van Raamsdonk supplies a structurally nearby multi-CFT cosmology, but not a decisive diagnostic of singularity resolution in the Antonini setup.

Two earlier overstatements had to be removed. The Antonini paper was previously described in the project state as if it identified de Sitter entropy with inter-sector entanglement entropy in a dS/dS construction. That is not what the verified record says. The corrected description is that the paper constructs entangled microstates of two holographic CFTs with big-bang/big-crunch AdS cosmologies encoded in the entanglement wedge of one CFT. Likewise, the Sahu-Van Raamsdonk paper was previously described as extending singularity diagnostics. The verified paper instead constructs a nearby black-hole-lattice cosmology dual to entangled multi-CFT states and is best used as structural context.

## 2. Verified Benchmark Map

| Paper | Verified role in this project | What it actually supports | What it does not yet support |
| --- | --- | --- | --- |
| Antonini, Sasieta, Swingle 2023 (`arXiv:2307.14416`) | Primary target construction | Entangled microstates of two holographic CFTs can encode a semiclassical big-bang/big-crunch AdS cosmology in an entanglement wedge | A boundary observable that demonstrates microscopic singularity resolution |
| Manu, Narayan, Paul 2021 (`arXiv:2012.07351`) | Extremal-surface benchmark | Classical extremal surfaces and QES are driven away from the singular region into a semiclassical regime | A proof that probe avoidance equals singularity resolution |
| Frenkel, Hartnoll, Kruthoff, Shi 2020 (`arXiv:2004.01192`) | Geometry benchmark | A deformed CFT state can flow to a Kasner interior, giving an explicit comparison geometry | A resolution mechanism by itself |
| Engelhardt, Hertog, Horowitz 2014 (`arXiv:1404.2309`) | Boundary-diagnostic benchmark | Heavy-operator two-point correlators show horizon-scale signatures of an anisotropic Kasner singularity | Microscopic smoothing or removal of the singularity |
| Narayan, Saini, Yadav 2024 (`arXiv:2404.00761`) | Complexity benchmark | Complexity surfaces bend away from the singularity and become effectively lightlike; entanglement probes show similar IR behavior | An independent, decisive discriminator between avoidance and resolution |
| Sahu, Van Raamsdonk 2025 (`arXiv:2411.14673`) | Nearby structural benchmark | Entangled multi-CFT states can also generate big-bang/big-crunch cosmologies in a related setting | A singularity diagnostic sharp enough to settle the Antonini question |

The pattern across these references is stable. Known semiclassical probes mostly avoid the singular region. Boundary correlators can nevertheless carry singularity-sensitive information. The open problem is therefore narrower than the original draft implied: one needs an Antonini-side boundary observable analogous to the Engelhardt correlator signal, not a generic appeal to entanglement or complexity alone.

## 3. Equation and Approximation Audit

The audit found only one explicit equation stored in the prior GPD state, `S_{dS} = S_{ent}`. That equation was removed because it was not supported by the verified Antonini reference used in this project record. No other derived equation in the workspace depended on it.

The corrected manuscript keeps only benchmark relations whose role is clear:

\[
S_{\mathrm{gen}}[X] = \frac{\mathrm{Area}(X)}{4 G_N} + S_{\mathrm{bulk}}[\Sigma_X].
\]

This is the generalized-entropy relation used in the QES benchmark literature. In natural units with explicit AdS radius `L`, dimensional consistency requires `G_N` to carry dimensions of `L^{d-1}`, so `Area/G_N` is dimensionless and the full right-hand side has entropy units. The relation is therefore dimensionally consistent.

\[
\frac{1}{N^2} \ll 1, \qquad \frac{l_s}{L} \ll 1, \qquad \frac{G_N}{L^{d-1}} \ll 1.
\]

These are the control parameters actually needed in the project record. The audit corrected the state ledger so the semiclassical extremal-surface approximation is controlled by the dimensionless ratio `G_N/L^(d-1)` rather than bare `G_N`.

The limiting-case audit is equally conservative. In the large-`N` and small-`l_s/L` limits, the semiclassical bulk description is expected to improve away from the singular core. Approaching the singularity, the same approximations lose force, which is exactly why probe avoidance cannot be upgraded into proof of microscopic resolution. The current project has no controlled calculation showing that the Antonini cosmology remains semiclassical all the way to the singular region, and it has no verified Antonini-specific boundary diagnostic equivalent to the Engelhardt correlator benchmark.

## 4. Conservative Interpretation

The corrected literature picture supports four claims and no more than four claims.

First, entangled multi-CFT states can encode cosmological spacetimes in holography. Second, in the benchmark Kasner literature, extremal surfaces and complexity surfaces avoid the singular region rather than resolve it. Third, boundary correlators can still register singularity-sensitive structure without implying resolution. Fourth, the Antonini construction has not yet been shown to furnish the missing boundary observable that would separate genuine resolution from generic probe avoidance.

Accordingly, the main conclusion must remain provisional. The Antonini construction is a serious cosmology-from-entanglement framework and a worthwhile singularity benchmark. It is not yet a demonstrated microscopic resolution mechanism. Any stronger claim would require at least one of the following: an Antonini-side boundary correlator with singularity-sensitive behavior, a controlled computation showing that the relevant encoding map stays reliable into the singular regime, or a new benchmark observable whose behavior cannot be reproduced by the already-known avoidance pattern.

## 5. Conclusion

After verifying the cited papers and correcting the stale state entries, the project becomes more coherent and more modest. The benchmark literature is genuinely interesting, but it does not presently justify a resolution claim. The most concrete next scientific step is now clear: compute or identify an observable in the Antonini state family that plays the role that heavy-operator correlators played in `arXiv:1404.2309`, while remaining distinguishable from the already-known avoidance behavior of QES and complexity probes.

## References

1. Stefano Antonini, Martin Sasieta, Brian Swingle, "Cosmology from random entanglement," `arXiv:2307.14416`, JHEP 11 (2023) 188. https://arxiv.org/abs/2307.14416
2. A. Manu, K. Narayan, Partha Paul, "Cosmological singularities, entanglement and quantum extremal surfaces," `arXiv:2012.07351`, JHEP 04 (2021) 200. https://arxiv.org/abs/2012.07351
3. Alexander Frenkel, Sean A. Hartnoll, Jorrit Kruthoff, Zhengyan D. Shi, "Holographic flows from CFT to the Kasner universe," `arXiv:2004.01192`, JHEP 08 (2020) 003. https://arxiv.org/abs/2004.01192
4. Netta Engelhardt, Thomas Hertog, Gary T. Horowitz, "Holographic Signatures of Cosmological Singularities," `arXiv:1404.2309`, Phys. Rev. Lett. 113 (2014) 121602. https://arxiv.org/abs/1404.2309
5. K. Narayan, Hitesh K. Saini, Gopal Yadav, "Cosmological singularities, holographic complexity and entanglement," `arXiv:2404.00761`, JHEP 07 (2024) 125. https://arxiv.org/abs/2404.00761
6. Abhisek Sahu, Mark Van Raamsdonk, "Holographic black hole cosmologies," `arXiv:2411.14673`, JHEP 05 (2025) 233. https://arxiv.org/abs/2411.14673
