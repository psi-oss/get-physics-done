# Extending The Restricted QFC Beyond Braneworlds: Corrected Note

## Abstract

This note replaces the workspace's earlier overcompressed summary with a source-checked version. The benchmark result remains arXiv:2212.03881, which argues for restricted quantum focusing and proves it in a brane-world semiclassical gravity setting subject to a technical assumption. The `Theta -> 0` paper arXiv:2310.14396 does not supply a general non-braneworld proof of rQFC; rather, it derives the improved quantum null energy condition (INEC) and sketches a possible field-theory proof route. The strongest direct non-braneworld evidence instead comes from arXiv:2510.13961, which proves rQFC in a class of JT-gravity-plus-QFT toy models and derives, in a broad class of `d>2` states, a stronger consequence forbidding QNEC saturation faster than `O(A)` as the transverse area shrinks.

## Verified Bibliography

The citation audit was done against arXiv and INSPIRE.

1. Arvin Shahbazi-Moghaddam, *Restricted Quantum Focusing*, [arXiv:2212.03881](https://arxiv.org/abs/2212.03881), also listed by INSPIRE and published as Phys. Rev. D 109 (2024) 066023.
2. Ido Ben-Dayan, *The Quantum Focusing Conjecture and the Improved Energy Condition*, [arXiv:2310.14396](https://arxiv.org/abs/2310.14396), also listed by INSPIRE and published as JHEP 02 (2024) 132.
3. Victor Franken, Sami Kaya, François Rondeau, Arvin Shahbazi-Moghaddam, Patrick Tran, *Tests of restricted Quantum Focusing and a new CFT bound*, [arXiv:2510.13961](https://arxiv.org/abs/2510.13961), mapped by INSPIRE to literature record 3070444.

No arXiv identifier in the workspace points to an unrelated paper.

## Corrected Literature Claims

The benchmark statement from arXiv:2212.03881 is unchanged in substance. Restricted quantum focusing is established there only in a brane-world semiclassical gravity setting with higher-dimensional Einstein-dual control and under a technical assumption. Any extension program that forgets those hypotheses is misreading the benchmark.

The correction concerns arXiv:2310.14396. What the paper directly gives is the limiting-case statement

```text
T_{kk} >= hbar/(2*pi*A) (S''_{out} - (1/2) theta S'_{out})
```

in the `Theta -> 0` regime, together with a sketch of a field-theory proof strategy. That is important evidence about which structure may survive beyond the holographic benchmark, but it is not by itself a general non-braneworld proof of rQFC.

The strongest direct non-braneworld evidence comes from arXiv:2510.13961. In `d=2`, the paper proves rQFC in a class of JT-gravity-plus-QFT toy models. In `d>2`, it derives a stronger consequence than ordinary QNEC saturation: in a broad class of states, rQFC forbids saturation faster than `O(A)` as the transverse area shrinks to zero.

## Equation Audit

The one explicit equation carried by the workspace is the INEC formula above. Its dimensions are consistent if the affine parameter `lambda` has dimension of length, `S_out` is dimensionless, `theta ~ L^-1`, `S''_{out} ~ L^-2`, and the local transverse area element satisfies `A ~ L^(d-2)`. The right-hand side then scales as `hbar * L^-d`, matching the dimension of the null-null stress component `T_{kk}`.

Its limiting behavior is also correct. Setting `theta -> 0` reduces the right-hand side to

```text
T_{kk} >= hbar/(2*pi*A) S''_{out},
```

which is precisely the intended restricted-limit form quoted in the paper. No additional equation in the workspace required correction.

## Present Verdict

The literature supports a cautious extension program, not a general theorem. The benchmark braneworld proof is real. The `Theta -> 0` paper provides a sharp limiting-case constraint and a field-theory direction. The JT/d>2 paper provides the strongest direct non-braneworld tests now in hand. What is still missing is a credible replacement for the benchmark proof's higher-dimensional Einstein-dual control in a genuinely general non-braneworld argument.
