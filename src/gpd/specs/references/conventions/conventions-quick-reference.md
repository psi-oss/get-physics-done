---
load_when:
  - "convention mismatch"
  - "Fourier convention"
  - "metric signature"
  - "combining expressions"
  - "unit conversion"
tier: 1
context_cost: small
---

# Conventions Quick Reference

Extracted from `../shared/shared-protocols.md` for lightweight loading. The most common source of LLM physics errors is convention mismatch between expressions from different sources.

**Full protocol:** See `../shared/shared-protocols.md` for the complete convention tracking protocol, machine-readable assertions, and conflict detection procedures.

## Required Convention Declarations

Every phase, plan, or derivation must declare:

| Convention | Options | Default |
|---|---|---|
| Unit system | natural (hbar=c=1), SI, CGS, lattice | natural |
| Metric signature | (+,-,-,-), (-,+,+,+), Euclidean (+,+,+,+) | (+,-,-,-) |
| Fourier convention | physics (exp(-iwt)), math (exp(+iwt)), QFT (exp(-ipx)) | physics |
| Index convention | Einstein summation, explicit sums | Einstein |
| State normalization | relativistic, non-relativistic | context-dependent |
| Spinor convention | Dirac, Weyl, Majorana | context-dependent |
| Gauge choice | Coulomb, Lorenz, axial, Feynman, light-cone | context-dependent |
| Commutator ordering | normal ordering, time ordering, Weyl ordering | context-dependent |
| Coupling convention | g, g^2, g^2/(4pi), alpha=g^2/(4pi) | context-dependent |
| Renormalization scheme | MS-bar, on-shell, momentum subtraction, lattice | context-dependent |
| Levi-Civita sign | epsilon^{0123} = +1, epsilon^{0123} = -1 | +1 |
| Generator normalization | Tr(T^a T^b) = delta^{ab}/2, Tr(T^a T^b) = delta^{ab} | delta^{ab}/2 |
| Covariant derivative sign | D = d - igA, D = d + igA | context-dependent |
| Gamma matrix convention | Dirac, Weyl (chiral), Majorana | context-dependent |
| Creation/annihilation order | normal, anti-normal, Weyl (symmetric) | normal |

## Fourier Convention Table

| Convention | Forward (x -> k) | Inverse (k -> x) | Where 2pi lives |
|---|---|---|---|
| Physics | integral dx e^{-ikx} | integral dk/(2pi) e^{+ikx} | In dk |
| Math | integral dx e^{-2pi\*i\*kx} | integral dk e^{+2pi\*i\*kx} | Absorbed into exponent |
| Symmetric | integral dx/sqrt(2pi) e^{-ikx} | integral dk/sqrt(2pi) e^{+ikx} | Split between both |

**Always state which row you are using.**

## Metric Signature Table

| Signature | ds^2 | k^2 on-shell | Propagator denominator |
|---|---|---|---|
| (+,-,-,-) | dt^2 - dx^2 - dy^2 - dz^2 | k^2 = m^2 (positive) | k^2 - m^2 |
| (-,+,+,+) | -dt^2 + dx^2 + dy^2 + dz^2 | k^2 = -m^2 (negative) | k^2 + m^2 |
| Euclidean | dt_E^2 + dx^2 + dy^2 + dz^2 | k_E^2 = -m^2 (after Wick) | k_E^2 + m^2 |

## 5-Point Checklist Before Combining Expressions

Run this checklist **every time** you combine expressions from different sources, derivations, or papers:

- [ ] **1. Metric signature matches?** Check propagator sign: k^2 - m^2 vs k^2 + m^2
- [ ] **2. Fourier convention matches?** Check 2pi placement and exponent sign
- [ ] **3. State normalization matches?** Relativistic <p|q> = (2pi)^3 2E delta vs non-relativistic <p|q> = delta
- [ ] **4. Coupling convention matches?** g vs alpha = g^2/(4pi) -- a factor of 4pi per vertex
- [ ] **5. Renormalization scheme matches?** MS-bar vs on-shell -- finite parts differ
- [ ] **6. Levi-Civita sign matches?** epsilon^{0123} = +1 (Peskin) vs -1 (Weinberg) -- flips dual tensors
- [ ] **7. Covariant derivative sign matches?** D = d - igA vs D = d + igA -- flips vertex rule sign
- [ ] **8. Generator normalization matches?** Tr(T^a T^b) = delta/2 vs delta -- factor of 2 per color trace

**If any check fails:** Resolve the mismatch BEFORE proceeding. Never combine and "fix later."

## Convention Lock Protocol

At the start of every task:

1. Read `convention_lock` from `state.json`
2. Read `conventions` from the plan frontmatter
3. If using results from a prior plan: verify conventions match
4. State explicitly at the top of every derivation file which conventions are in effect

## Machine-Readable Convention Assertion

Every derivation file must include:

```
% ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-plus, fourier_convention=physics
```

For Python use `#`, for Markdown use `<!-- ASSERT_CONVENTION: ... -->`.
Prefer the canonical hyphenated metric values reported by `gpd --raw convention list` (`mostly-plus`, `mostly-minus`); underscore aliases are normalized but are not the canonical lock spelling.

## Commutator Conventions

- **Canonical:** [x, p] = i*hbar (or i in natural units)
- **Creation/annihilation:** [a, a^dag] = 1 (bosons), {b, b^dag} = 1 (fermions)
- **Field commutators:** [phi(x), pi(y)] = i*delta(x-y) -- state equal-time vs covariant
- **Normal ordering:** :a^dag a: = a^dag a, but :a a^dag: = a^dag a (reordered)

## Convention Propagation Rules

- If Phase 01 established metric (+,-,-,-), ALL subsequent phases MUST use it
- When citing results from sources with different conventions, convert BEFORE using
- Document all convention choices in project CONVENTIONS.md
- When ambiguity is possible, annotate each equation with its convention
