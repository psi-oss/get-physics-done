# Research Summary: Witten Index of Orbifold Daughters of N=4 SYM

**Synthesized:** 2026-03-13
**Sources:** 4 parallel literature scouts (Prior Work, Methods, Computational, Pitfalls)

## Executive Summary

Computing the Witten index Tr(-1)^F for Z_k orbifold daughter theories of N=4 SYM via the CKKU lattice construction is genuinely novel — no 4d lattice Witten index computation exists in the literature. The target theory (Z_3 orbifold of SU(6) → SU(2)^3 quiver with bi-fundamental matter) has never been simulated on the lattice. Each component has solid precedent, but the synthesis is new.

The CKKU/Catterall A_4* twisted lattice formulation is the only viable 4D lattice SUSY approach with exact supersymmetry (one nilpotent Q). It has ~20 years of development, validated code, and published results for parent SU(2)–SU(4) N=4 SYM. The Pfaffian sign problem is empirically mild for the parent theory but **completely uncharacterized for the orbifold daughter** — this is the single greatest risk.

## Key Findings

### Known Results
- **CKKU construction** (Cohen-Kaplan-Katz-Unsal, 2003): Mature lattice formulation preserving one exact supercharge Q via topological twist on A_4* lattice. Validated numerically for SU(2)–SU(4) parent N=4 SYM.
- **Orbifold equivalence** (Kovtun-Unsal-Yaffe, 2003): Parent/daughter neutral-sector equivalence proven at large N. At N=2, corrections are O(1/N^2) ≈ 25%.
- **Witten index on lattice**: Computed successfully in d=1 (SUSY QM) and d=2 (SYM). No 4d computation exists — this project is novel.
- **Z_3 daughter theory**: N=1 SU(2)^3 circular quiver with bi-fundamental chiral multiplets and cubic superpotential. Well-defined in continuum, unstudied on lattice.
- **SUSY Ward identities**: Verified for parent theory; violations scale as O(a^2) toward continuum limit.

### Standard Methods
- **RHMC** (Rational Hybrid Monte Carlo): Workhorse for configuration generation. Handles Pfaffian via rational approximation to |Pf(M)|^{1/2}. Cost: O(V × N_c^3) per trajectory.
- **Pfaffian computation**: Exact via Parlett-Reid tridiagonalization (Wimmer algorithm), O(n^3). Feasible for L ≤ 4 (matrix dim ~50K). Infeasible for L ≥ 8.
- **Witten index extraction**: Partition function ratio Z_PBC/Z_APBC via boundary condition twist. Best approach: direct Pfaffian ratio on small lattices (L=2,4).
- **Code base**: Catterall-Schaich MILC-based C code. Public but requires author contact. Major modifications needed for quiver gauge group structure (estimated 3–6 person-months).

### Watch Out For
1. **Pfaffian sign problem** (CRITICAL): Unknown for daughter theory. Must measure <cos(α)> on small lattices before any production. If severe → pivot observable.
2. **Flat direction instability** (CRITICAL): Scalar runaway along moduli space. Requires soft SUSY-breaking mass μ^2 with μ→0 extrapolation.
3. **Orbifold equivalence breakdown at N=2** (CRITICAL): Z_3 symmetry may break spontaneously. Must monitor Z_3 order parameter. Treat daughter as independent theory.
4. **Incorrect boundary conditions** (CRITICAL): Witten index requires periodic fermion BCs (not standard anti-periodic). Easy to get wrong when adapting thermal code.
5. **Breaking exact Q** (CRITICAL): Every action modification must preserve Q-exactness. Orbifold projection must commute with Q.
6. **Non-commuting limits**: μ→0, a→0, V→∞ order matters. Must extrapolate carefully.
7. **No existing orbifold daughter code**: All development from scratch on parent code. The code itself is a research contribution.

## Resource Estimates

| Calculation | Volume | Configs | Cost | Memory |
|---|---|---|---|---|
| Parent SU(2) validation | 4^4 | 5,000 | 1–2 CPU-days | 1 GB |
| Daughter SU(2)^3 (bosonic + Pf) | 2^4 | 10,000 | 1–3 CPU-days | 0.5 GB |
| Daughter SU(2)^3 (bosonic + Pf) | 4^4 | 5,000 | 2–4 CPU-weeks | 4 GB |
| Exact Pfaffian per config | 2^4 | — | seconds | 0.1 GB |
| Exact Pfaffian per config | 4^4 | — | minutes | 4 GB |
| Exact Pfaffian per config | 6^4 | — | hours | 100 GB |

**Critical constraint:** Exact Pfaffian infeasible for L ≥ 8. Focus Witten index on L=2,4.

## Suggested Phase Structure

1. **Setup & Parent Validation**: Obtain Catterall code, reproduce SU(2) N=4 SYM results (Ward identities, Pfaffian phase), validate infrastructure
2. **Orbifold Implementation**: Implement Z_3 projection (gauge group decomposition, bi-fundamental matter, quiver Dirac operator). Verify Q-exactness preserved. Test on free-field limit.
3. **Sign Problem Feasibility**: Measure Pfaffian phase for daughter theory on 2^4. GO/NO-GO gate.
4. **Witten Index Computation**: Implement periodic fermion BCs. Compute Tr(-1)^F via exact Pfaffian ratio on L=2,4. Verify β-independence, μ-independence.
5. **Systematic Analysis**: Volume dependence, continuum extrapolation, Ward identity convergence, orbifold equivalence cross-check.
6. **Publication**: Write paper with plots, error budget, results.

## Open Questions

- Pfaffian phase severity for orbifold daughter (empirical — Phase 3 go/no-go)
- Proper lattice definition of (-1)^F in the CKKU Pfaffian formulation for 4d
- Whether μ^2 deformation affects Witten index discontinuously at μ=0
- Optimal lattice volumes for topological quantity (L=2 may suffice)
- Theoretical prediction for daughter Witten index (needed for validation)
- Ward identity exact values for SU(2)^3 quiver (must derive analytically)

## Key References

| Reference | arXiv | Role |
|---|---|---|
| Cohen-Kaplan-Katz-Unsal (2003) | hep-lat/0302017 | CKKU construction |
| Catterall (2005) | hep-lat/0503036 | Twisted lattice N=4 SYM |
| Catterall-Kaplan-Unsal (2009) | 0903.4881 | Exact lattice SUSY review |
| Catterall-Schaich (2015) | 1505.03135 | N=4 SYM benchmarks, Pfaffian phase |
| Kovtun-Unsal-Yaffe (2003) | hep-th/0311098 | Orbifold equivalence |
| Witten (1982) | Nucl.Phys.B202:253 | Witten index definition |
| Kanamori-Suzuki (2009) | 0811.2851 | Lattice Witten index (2d) |
| Wimmer (2012) | 1102.3440 | Efficient Pfaffian algorithm |
| Schaich (2022) | 2201.03097 | Lattice N=4 SYM status |

## Confidence Assessment

| Area | Confidence |
|---|---|
| Lattice formulation (CKKU/Catterall) | HIGH |
| RHMC algorithm for parent theory | HIGH |
| Orbifold equivalence theory | HIGH |
| Code modification path | MEDIUM |
| Witten index extraction method | MEDIUM |
| Pfaffian phase for daughter | LOW (unknown) |
| Resource estimates | MEDIUM |
