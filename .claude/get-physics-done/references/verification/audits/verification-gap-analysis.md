---
load_when:
  - "verification gap analysis"
  - "error class coverage"
  - "defense layer audit"
tier: 2
context_cost: large
---
# Physics Verification Protocol Gap Analysis

Systematic analysis of which LLM physics error classes are caught by which defense layers, identifying gaps with no coverage or single-layer coverage. The full catalog now covers **101 error classes**: core (#1-51) with full coverage matrix, extended broad coverage (#52-71) for 10 underrepresented domains, deep domain classes (#72-81) for numerical relativity, quantum chemistry, plasma physics, fluid dynamics, and biophysics, and specialized classes (#82-101) covering nuclear physics, astrophysics, AMO, condensed matter, mathematical physics, nonlinear dynamics, optics, and cosmology.

Last audited: 2026-02-23 (deep audit, cross-referenced against actual workflow/agent implementations)

## Defense Layers

| Layer | Name | Timing | What It Checks | Reliability Notes |
|---|---|---|---|---|
| L0 | **Plan-checker 16D** | Pre-execution | Plan design quality: prerequisites, approximation validity, validation strategy, anomaly awareness | Only runs for execute-phase; user can skip |
| L1 | **Convention Lock** | Pre-execution | Conventions in `state.json convention_lock` match plan frontmatter and prior phases | Requires lock to be populated; empty lock = no check |
| L2 | **ASSERT_CONVENTION** | During execution | Inline `% ASSERT_CONVENTION:` declarations match project lock; missing assertions flagged | Only covers convention-trackable errors (metric, Fourier, units, coupling, renorm) |
| L2b | **Executor self-critique + post-step guards** | During execution | Self-critique: sign, factor, convention, dimension checks every 3-4 steps. **Post-step guards:** IDENTITY_CLAIM tagging (#11), BOUNDARY_CONDITION declarations (#13), EXPANSION_ORDER tracking (#16), 12-type computation mini-checklist. Guard failures → deviation rules 3/4/5. | Best-effort — LLM may skip under context pressure. Guards are lightweight (~50 tokens) so more resilient than full self-critique. |
| L3 | **Pre-commit check** | At commit time | ASSERT_CONVENTION vs lock validation, NaN detection in state.json, SUMMARY/PLAN frontmatter completeness | Now used in 37/59 workflows (bug #23 fixed). Advisory (`|| true`), not blocking |
| L4 | **Inter-wave gates** | Between waves | Convention consistency + dimensional spot-check on wave SUMMARY.md equations | **Only runs between waves within execute-phase**; does NOT run limiting cases, symmetry, or conservation checks |
| L5 | **Verifier 15-check** | Post-execution | Full verification: 5.1-5.15 (dimensional, spot-check, limiting cases, cross-check, symmetry, conservation, math consistency, convergence, literature, plausibility, statistics, thermodynamic, spectral, anomalies/topology) | **Profile-dependent**: exploratory runs 7-check floor (5.1,5.2,5.3,5.6,5.7,5.8,5.10); quick mode runs 5.1/5.3/5.10; Tier 4 (5.13-5.15) skipped under context pressure but promoted if computation type requires them |
| L5b | **Researcher validation** | Post-execution | Interactive verify-work with computational evidence; researcher confirms/denies each check | Only runs when user invokes `/gpd:verify-work`; human-dependent |
| L6 | **Cross-phase consistency** | Post-phase | Convention drift, provides/requires chains, sign/factor spot-checks, approximation validity | Only checks quantities crossing phase boundaries; within-phase errors invisible |

---

## Coverage Matrix

Legend: `++` = primary detection, `+` = partial detection, `(+)` = theoretical/conditional detection (may not run), `.` = no coverage

| # | Error Class | L0 | L1 | L2 | L2b | L3 | L4 | L5 | L5b | L6 | Reliable Layers | Risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Wrong CG coefficients | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 2 | N-particle symmetrization | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 3 | Green's function confusion | . | . | . | . | . | . | ++ | (+) | (+) | **1** (L5 only; L6 only for cross-phase) | MEDIUM |
| 4 | Wrong group theory (non-SU(2)) | . | . | . | . | . | . | ++ | (+) | (+) | **1** | MEDIUM |
| 5 | Incorrect asymptotic expansions | . | . | . | . | . | . | ++ | (+) | (+) | **1** (L4 was overstated — it only does dimensional) | MEDIUM |
| 6 | Delta function mishandling | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L4 was overstated) | MEDIUM |
| 7 | Wrong phase conventions | (+) | ++ | ++ | + | (+) | + | + | (+) | ++ | 4 (L1+L2+L4+L6) | LOW |
| 8 | Intensive/extensive confusion | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L4 was overstated — dim check doesn't catch this) | MEDIUM |
| 9 | Incorrect thermal field theory | . | . | . | . | . | . | ++ | (+) | (+) | **1** (L5 5.13/5.14 required; skipped in exploratory/quick) | **HIGH** |
| 10 | Wrong tensor decompositions (GR) | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L4 was overstated) | MEDIUM |
| 11 | **Hallucinated identities** | . | . | . | . | . | . | (+) | (+) | . | **0-1 (weak)** | **CRITICAL** |
| 12 | Incorrect Grassmann signs | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 13 | **Boundary condition hallucination** | (+) | . | . | . | . | . | (+) | (+) | . | **0-1 (weak)** | **CRITICAL** |
| 14 | Operator ordering errors | . | . | . | (+) | . | . | ++ | (+) | (+) | **1** (L2 only covers convention-locked ordering) | MEDIUM |
| 15 | Dimensional analysis failures | . | . | + | ++ | (+) | ++ | ++ | (+) | (+) | 4 (L2+L2b+L4+L5) | LOW |
| 16 | Series truncation errors | (+) | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 17 | Correlation/response confusion | . | . | . | . | . | . | ++ | (+) | (+) | **1** (L5 5.14 required; skipped in exploratory/quick) | MEDIUM |
| 18 | Integration constant omission | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 19 | Wrong DOF counting | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 20 | Classical/quantum conflation | . | . | . | . | . | . | ++ | (+) | (+) | **1** | MEDIUM |
| 21 | Branch cut errors | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 22 | HS sign errors | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 23 | Diagram topology miscounting | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 24 | Variational bound violations | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 25 | Partition fn vs generating fn | . | . | . | (+) | . | . | ++ | (+) | (+) | **1** (L4 was overstated) | MEDIUM |
| 26 | Coherent state normalization | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 27 | First/second quantization | . | . | . | (+) | . | . | ++ | (+) | (+) | **1** (L4 was overstated) | MEDIUM |
| 28 | Angular momentum j>1 | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 29 | Wrong Boltzmann factor | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L4 was overstated — dim check only catches exp argument) | MEDIUM |
| 30 | Missing path ordering (non-Abelian) | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 31 | Wrong ensemble | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 32 | Numerical linear algebra errors | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 33 | Natural unit restoration errors | . | + | + | ++ | (+) | ++ | ++ | (+) | (+) | 5 (L1+L2+L2b+L4+L5) | LOW |
| 34 | Regularization scheme mixing | . | ++ | ++ | + | (+) | + | ++ | (+) | ++ | 4 (L1+L2+L5+L6) | LOW |
| 35 | Incorrect Fierz identity | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 36 | Effective potential sign errors | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 37 | Metric signature inconsistency | . | ++ | ++ | ++ | (+) | ++ | ++ | (+) | ++ | 5 (L1+L2+L2b+L5+L6) | LOW |
| 38 | Covariant vs partial derivative | . | . | (+) | (+) | . | . | ++ | (+) | (+) | **1** (L2 only if derivative convention in lock) | MEDIUM |
| 39 | Wick contraction miscounting | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 40 | Scaling dimension errors (CFT/RG) | . | . | . | . | . | . | ++ | (+) | . | **1** (L4 was overstated) | MEDIUM |
| 41 | Index (anti)symmetrization factors | . | . | . | (+) | . | . | ++ | (+) | (+) | **1** | MEDIUM |
| 42 | Noether current / anomaly errors | (+) | . | . | . | . | . | ++ | (+) | . | **1** (L4 was overstated; L0 only checks awareness) | MEDIUM |
| 43 | Legendre transform errors | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L4 was overstated) | MEDIUM |
| 44 | Spin-statistics violations | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 45 | Topological term mishandling | . | . | (+) | . | . | . | ++ | (+) | . | **1** (L2 only if topological convention in lock) | MEDIUM |
| 46 | Adiabatic vs sudden confusion | . | . | . | . | . | . | ++ | (+) | . | **1** (L4 was overstated) | MEDIUM |
| 47 | Incorrect complex conjugation | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 48 | Hellmann-Feynman misapplication | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 49 | Incorrect replica trick | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 50 | Wrong zero mode treatment | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 51 | Wrong HS channel selection | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |

### Extended Error Classes (#52-81) Coverage

| # | Error Class | L0 | L1 | L2 | L2b | L3 | L4 | L5 | L5b | L6 | Reliable Layers | Risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 52 | NR constraint violation | . | . | . | ++ | . | . | ++ | (+) | . | **2** (L2b+L5) | **HIGH** |
| 53 | Wrong stellar structure eqn | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 54 | Basis set superposition (BSSE) | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 55 | Wrong XC functional regime | (+) | . | . | . | . | . | ++ | (+) | . | **1** (L0 checks computational feasibility) | MEDIUM |
| 56 | Plasma instability criteria | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 57 | Reynolds number regime | ✓ | . | . | (+) | . | . | ++ | (+) | . | **1** (L0 checks regime, L5 verifies) | MEDIUM |
| 58 | Entanglement vs thermo entropy | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 59 | Wrong quantum gate count | . | . | . | (+) | . | . | ++ | (+) | . | **1** | LOW |
| 60 | Coarse-graining artifacts | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 61 | Gauge-fixing artifact confusion | . | . | . | . | . | . | ++ | (+) | (+) | **1** | MEDIUM |
| 62 | Missing finite-size effects | . | . | . | . | . | . | ++ | (+) | (+) | **1** (L6 catches cross-phase size inconsistency) | MEDIUM |
| 63 | GW template mismatch | . | . | . | . | . | . | ++ | (+) | . | **1** | **HIGH** |
| 64 | Optical depth confusion | ✓ | . | . | ++ | . | . | ++ | (+) | . | **3** (L0 dim+L2b dim+L5) | LOW |
| 65 | Wrong dispersion relation | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 66 | Semiclassical beyond validity | (+) | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 67 | Adiabatic elimination errors | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 68 | Wrong Kramers-Kronig | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 69 | Molecular symmetry misID | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 70 | Wrong Landau levels | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 71 | Missing Berry phase | . | . | . | . | . | . | ++ | (+) | . | **1** | **HIGH** |
| 72 | NR gauge mode leakage | . | . | . | ++ | . | . | ++ | (+) | . | **2** (L2b monitor+L5) | **HIGH** |
| 73 | CFL condition violation | . | . | . | ++ | . | . | ++ | (+) | . | **2** (L2b check+L5) | MEDIUM |
| 74 | DFT+U double counting | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 75 | Broken spin symmetry | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 76 | Debye length resolution | . | . | . | ++ | . | . | ++ | (+) | . | **2** (L2b grid check+L5) | **HIGH** |
| 77 | Kinetic vs fluid mismatch | (+) | . | . | . | . | . | ++ | (+) | . | **1** (L0 checks regime) | **HIGH** |
| 78 | Numerical diffusion | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |
| 79 | Turbulence model extrap | (+) | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 80 | Implicit solvent artifacts | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 81 | Force field transferability | . | . | . | (+) | . | . | ++ | (+) | . | **1** | MEDIUM |

**Extended catalog summary (#52-81):** Of 30 error classes, **24 have single-layer coverage** (L5 only), **5 have 2-layer coverage** (#52, #72, #73, #76 via L2b computation-type mini-checklists; #64 via dimensional analysis), and **1 has 3-layer coverage** (#64 optical depth via L0+L2b+L5 dimensional checks). Six classes are rated **HIGH** risk: #52 (NR constraints), #63 (GW templates), #71 (Berry phase), #72 (gauge leakage), #76 (Debye resolution), #77 (kinetic/fluid mismatch) — these produce plausible-looking results that can mislead published analysis.

### Deep Domain Error Classes (#82-101) Coverage

| # | Error Class | L0 | L1 | L2 | L2b | L3 | L4 | L5 | L5b | L6 | Reliable Layers | Risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 82 | Wrong nuclear magic numbers | (+) | . | . | . | . | . | ++ | (+) | . | **1** (L0 only checks regime; L5 5.10 literature is primary) | MEDIUM |
| 83 | Eddington luminosity errors | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b general numerics dim check is partial) | MEDIUM |
| 84 | Wrong Friedmann equation usage | (+) | . | . | (+) | . | . | ++ | (+) | (+) | **1** (L2b cosmological perturbation type #25 partial; L6 cross-phase w(a) consistency) | MEDIUM |
| 85 | Wrong multiphoton selection rules | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 86 | BCS gap equation errors | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b many-body type #5 has partial coverage) | MEDIUM |
| 87 | Wrong reconnection topology | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b kinetic type #41 partial for plasma) | **HIGH** |
| 88 | Wrong decoherence channel | . | . | . | ++ | . | . | ++ | (+) | . | **2** (L2b open-quantum type #44 checks Lindblad form + trace + CP; L5) | MEDIUM |
| 89 | Holonomic vs non-holonomic | . | . | . | ++ | . | . | ++ | (+) | . | **2** (L2b constrained dynamics type #49 checks DOF count; L5) | MEDIUM |
| 90 | Hyperscaling / critical exponents | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b RG type #10 checks unitarity bounds — partial) | MEDIUM |
| 91 | Wrong conformal mapping | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 92 | Wrong Lyapunov exponent | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b bifurcation type #50 + symplectic #45 partial for Hamiltonian constraint) | MEDIUM |
| 93 | Fresnel vs Fraunhofer confusion | (+) | . | . | (+) | . | . | ++ | (+) | . | **1** (L0 regime check; L2b EM type #46 checks numerical dispersion) | MEDIUM |
| 94 | Wrong Maxwell construction | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b stat mech type #5 checks S>=0, C_V>=0 — partial) | MEDIUM |
| 95 | Wrong Brillouin zone | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b DFT type #17 checks k-point convergence — partial) | MEDIUM |
| 96 | Wrong nuclear binding energy | . | . | . | . | . | . | ++ | (+) | . | **1** | MEDIUM |
| 97 | Wrong Penrose diagram | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b NR type #26 checks constraints — partial for topology) | MEDIUM |
| 98 | Wrong entanglement measure | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b quantum circuit type #33 checks entropy bounds — partial) | MEDIUM |
| 99 | Wrong magnetic mirror ratio | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b kinetic type #41 checks positivity — partial) | MEDIUM |
| 100 | Jeans instability criterion | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b cosmological type #25 partial) | MEDIUM |
| 101 | Kramers degeneracy misapplication | . | . | . | (+) | . | . | ++ | (+) | . | **1** (L2b exact-diag type #15 checks degeneracy vs symmetry — partial) | MEDIUM |

**Deep domain catalog summary (#82-101):** Of 20 new error classes, **17 have single-layer coverage** (L5 only), **2 have 2-layer coverage** (#88 via L2b open-quantum mini-checklist; #89 via L2b constrained-dynamics mini-checklist), and **1 is rated HIGH risk** (#87 wrong reconnection topology — Sweet-Parker vs Petschek produces 5 orders of magnitude error in timescale). 14 of the 20 classes have partial (+) L2b coverage through existing computation-type mini-checklists, but these are not counted as reliable layers. The remaining 3 (#82 nuclear magic numbers, #85 multiphoton selection rules, #96 nuclear binding energy) have no L2b coverage at all — they belong to nuclear and AMO physics domains not yet covered by computation-type mini-checklists.

---

## Summary Statistics (Corrected 2026-02-23)

**Previous analysis overstated coverage.** The original gap analysis counted L4 (inter-wave gates) as partial coverage for 12+ error classes. Actual L4 implementation only does convention consistency check + dimensional spot-check — it does NOT perform limiting case, symmetry, conservation, or sign checks. L3 (pre-commit) was also overcounted — originally only 2 of 35+ workflows (bug #23, now fixed: 37/59 workflows). The statistics below reflect the corrected L4 assessment; L3 coverage has improved but L4 inflation remains the primary distortion.

| Reliable Coverage | Count | Error Classes |
|---|---|---|
| **0-1 layers (CRITICAL)** | **0** | (Previously #11, #13 — now covered by post-step physics guards at L2b) |
| **1 layer only (L5)** | **82** | Original: #1-6, 8-10, 12, 14, 17-32, 35-36, 38-51. Extended (24): #53-55, 58-63, 65-71, 74-75, 78-81. Deep (17): #82-87, 90-101 |
| 2 layers (L2b + L5) | 10 | Original: #11 (IDENTITY_CLAIM), #13 (BOUNDARY_CONDITION), #16 (EXPANSION_ORDER). Extended: #52, #72, #73, #76 (L2b computation-type mini-checklists + L5 verifier). Deep: #88 (L2b open-quantum #44), #89 (L2b constrained dynamics #49) |
| 3 layers (L0 + L2b + L5) | 2 | #57 (Reynolds regime: L0 plan-checker + L2b + L5), #64 (optical depth: L0 dimensional + L2b + L5) |
| 4+ layers | 6 | #7, #15, #33, #34, #37 (convention-trackable + dimensional). #77 (kinetic/fluid: L0 regime check + L2b + L5 + domain checklist) |
| L2b partial (mini-checklist) | ~49 | Error classes with computation-type mini-checklist coverage (2-3 line checks, best-effort). Expanded from ~35 with 52 computation types. Not counted as reliable layer but provides defense-in-depth. |

**Updated key finding (101 error classes):** **82 of 101 error classes (81%) have only single reliable layer (the verifier, L5).** This ratio is remarkably consistent across all three catalog expansions (original 51: ~80%, extended 81: ~80%, full 101: 81%). The 20 newest classes (#82-101) follow the same pattern: most are caught only by L5 domain-specific checks, with 2 benefiting from L2b computation-type mini-checklists (#88, #89). One new class is rated HIGH risk (#87 reconnection topology). Seven total HIGH risk classes: #52, #63, #71, #72, #76, #77, #87. Zero CRITICAL (0-1 layer) classes remain. The overstated coverage came from:

1. **L4 inflation:** L4 only checks convention consistency and dimensional spot-checks. It was credited with partial detection of #5, 6, 8, 10, 25, 27, 29, 40, 42, 43, 46 — none of which are caught by convention or dimensional checking alone.
2. **L3 coverage (improved):** Pre-commit check was only in 2 of 35+ workflows (bug #23, now fixed: 37/59 workflows). L3 remains advisory (`|| true`) and catches only convention/NaN/frontmatter issues, not physics errors.
3. **L6 overcounting:** Cross-phase consistency only catches errors visible at phase boundaries. Errors localized within a single derivation are invisible to L6.
4. **L5 profile risk:** In exploratory profile, 7-check floor runs (5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.10). Error classes requiring 5.9, 5.11-5.15 (convergence, plausibility, statistics, thermodynamic, spectral, anomalies) have **zero** reliable coverage in exploratory mode.

**L5 tier-dependent coverage breakdown:**

| L5 Checks Run | Profile | Error Classes With Coverage | Error Classes With NO Coverage |
|---|---|---|---|
| 5.1-5.15 (all 15) | deep-theory, review | All 101 | None |
| 5.1-5.15 (all 15) | numerical, paper-writing | All 101 | None |
| 5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.10 (7-check floor) | exploratory | ~68 | **~33 error classes lose their ONLY defense** (core requiring 5.9-5.15 + extended + deep #87,90,92) |
| 5.1, 5.3, 5.10 | quick | ~20 | **~81 error classes lose their ONLY defense** |

**Combined 101-class summary:** 82 single-layer (L5 only), 10 two-layer (L2b+L5), 2 three-layer, 6 four+-layer, 1 three-layer via convention+dimensional. Seven HIGH-risk classes (#52,#63,#71,#72,#76,#77,#87) produce plausible-looking results.

---

## Most Dangerous Error Classes (corrected coverage)

The catalog identifies 7 error classes that produce **plausible-looking results** — the most dangerous category because they pass cursory review:

| # | Error Class | Reliable Coverage | Detection Difficulty |
|---|---|---|---|
| **3** | Green's function confusion | **1 layer** (L5 only; L5 5.14 required) | Retarded vs time-ordered look similar; error only matters at finite T |
| **5** | Incorrect asymptotic expansions | **1 layer** (L5 only) | Leading term correct; subleading coefficients wrong |
| **9** | Thermal field theory errors | **1 layer** (L5 only; L5 5.13/5.14 required) | KMS violation is subtle; Matsubara sums give finite but wrong results |
| **11** | Hallucinated identities | **0-1 layer (CRITICAL)** | Looks authoritative; close to real identity |
| **17** | Correlation/response confusion | **1 layer** (L5 only; L5 5.14 required) | At T=0 they agree; diverges only at finite T |
| **21** | Branch cut errors | **1 layer** (L5 only) | Wrong Riemann sheet gives finite spectral function |
| **42** | Missing anomalies | **1 layer** (L5 only; L5 5.15 required) | Classical conservation holds; quantum anomaly is additional |

**All 7 core classes have only single-layer reliable coverage (L5).** Three of them (#3, #9, #17) require L5 Tier 4 checks (5.13/5.14) which are skipped in exploratory/quick mode, meaning they have **zero** coverage in those profiles. #42 requires 5.15 (anomalies/topology), also Tier 4.

**Extended and deep catalog HIGH-risk classes (also produce plausible-looking results):**

| # | Error Class | Reliable Coverage | Detection Difficulty |
|---|---|---|---|
| **52** | NR constraint violation | **2 layers** (L2b+L5) | Free-evolution amplifies violations; initial data looks fine |
| **63** | GW template mismatch | **1 layer** (L5 only) | Wrong PN order gives finite waveform; phase error accumulates over 10^4 cycles |
| **71** | Missing Berry phase | **1 layer** (L5 only) | Adiabatic evolution looks correct; geometric phase is invisible without explicit calculation |
| **72** | NR gauge mode leakage | **2 layers** (L2b+L5) | Gauge oscillations look like physical GW at single extraction radius |
| **76** | Debye length resolution | **2 layers** (L2b+L5) | Numerical heating mimics physical heating; simulation runs without crash |
| **77** | Kinetic vs fluid mismatch | **1 layer** (L5 only) | MHD gives finite reconnection rate; just 10^5× slower than kinetic reality |
| **87** | Wrong reconnection topology | **1 layer** (L5 only) | Sweet-Parker gives finite rate (~10^{-7} v_A); correct plasmoid-mediated rate is ~0.01 v_A — 5 orders of magnitude discrepancy, but both produce smooth reconnection flows |

---

## Critical Gaps

### Gap 1: Hallucinated Identities (#11) — HIGH RISK

**Problem:** LLMs generate plausible-looking but false mathematical identities. The only defense is Layer 5 check 5.2 (numerical spot-check) or 5.10 (literature comparison). These are Tier 1/3 checks, but the error is uniquely dangerous because it looks correct to cursory review.

**Why single-layer is insufficient:** This error class is flagged in the catalog as one of the most dangerous — producing "plausible-looking results." The verifier's numerical spot-check may not catch identities that are approximately true for common parameter values but fail at edge cases.

**Proposed fix:** Add a **"suspicious identity" flag** to the executor protocol. When any derivation introduces a non-trivial identity (integral evaluation, summation formula, special function relation), the executor must:
1. Tag it: `% IDENTITY_CLAIM: [identity] SOURCE=[textbook|derived|training_data]`
2. If SOURCE=training_data (i.e., recalled from memory, not derived): flag for mandatory numerical verification at 5+ test points
3. The inter-wave gate (Layer 4) should scan for `IDENTITY_CLAIM` tags and verify any tagged as training_data

### Gap 2: Boundary Condition Hallucination (#13) — HIGH RISK

**Problem:** LLMs apply wrong BCs or silently assume periodic/infinite domain. The only defense is Layer 5 check 5.3 (limiting cases) or 5.2 (substitution check). But the verifier must know the correct BCs to check — if the wrong BCs are stated confidently, the verifier may accept them.

**Why single-layer is insufficient:** The error originates in problem setup, not computation. The verifier checks that the solution satisfies stated BCs, but cannot detect that the wrong BCs were stated.

**Proposed fix:** Add a **boundary condition declaration** to the plan-checker and executor:
1. Plan-checker Dim 6 (Validation Strategy) should require explicit BC enumeration: "What BCs does this problem have? List each boundary and the condition imposed."
2. Executor must state BCs at the top of each derivation: `% BOUNDARY_CONDITIONS: [list]`
3. The verifier adds a check: count BCs vs ODE/PDE order. n-th order ODE needs exactly n conditions.

### Gap 3: Series Truncation Errors (#16) — MEDIUM RISK

**Problem:** Mixing orders — keeping some O(g^3) terms while dropping others. Only caught by Layer 5 (checks 5.3 limiting cases, 5.8 math consistency, 5.10 literature). No early detection.

**Proposed fix:** Add an **order-tracking annotation** to the derivation discipline protocol:
1. Every perturbative expansion must declare its target order: `% EXPANSION_ORDER: O(g^N)` or `% EXPANSION_ORDER: O(epsilon^N)`
2. Each term must be tagged with its order
3. Inter-wave gate (Layer 4) can verify: are all terms at the declared order present? Are higher-order terms excluded?

### Gap 4: Integration Constant Omission (#18) — MEDIUM RISK

**Problem:** Forgetting constants when solving ODEs, producing incomplete general solutions. Only Layer 5 catches this.

**Proposed fix:** Add to derivation discipline protocol: when solving any ODE of order n, explicitly state "General solution has n arbitrary constants: {C_1, ..., C_n}." Executor must verify the count before applying BCs.

### Gap 5: 82 Error Classes with Only Layer 5 Coverage (101-class total)

Across the full 101-class catalog, **82 error classes** have only L5 as their reliable defense. The original core had 38 single-layer classes, extended (#52-81) added 24 more, and deep (#82-101) added 17 more. Only 2 of the 50 extended/deep classes gained a second reliable layer (#88 and #89 via L2b computation-type mini-checklists).

All are purely computational errors that no convention or structural check can catch early. They require domain-specific mathematical verification.

**Proposed fix: Executor self-check protocol**

Add a lightweight self-verification step to the executor Agent (execute-plan Pattern A/B/C):

After each major derivation step, the executor runs a mini-checklist tuned to the error classes relevant to that computation type:

See the executor agent's **30-type Computation-Type Mini-Checklist** in `gpd-executor.md` (`<post_step_physics_guards>` section) for the full table. The checklist covers:

- **Algebraic:** Angular momentum/CG, Grassmann/fermionic, operator algebra, group theory (types 1-2, 8)
- **Diagrammatic:** Feynman diagrams, perturbative expansions, scattering (types 3, 11, 19)
- **Variational/extremization:** Ritz method, DFT, Hellmann-Feynman (types 4, 17)
- **Thermodynamic:** Many-body/stat mech, finite-T field theory, Boltzmann transport (types 5, 24, 30)
- **Non-perturbative:** Path integrals, instantons, lattice gauge, topology (types 6, 12, 14)
- **Spectral:** Green's functions, analytic continuation, response functions (types 7, 23)
- **Numerical:** General numerics, exact diag, tensor networks, ODE/PDE, Monte Carlo, ML (types 9, 13, 15-16, 21, 29)
- **Field theory:** Effective potential/RG, conformal bootstrap, holography (types 10, 27-28)
- **Gravity/cosmology:** Cosmological perturbations, numerical relativity (types 25-26)
- **Classical/semiclassical:** WKB, molecular dynamics, Fourier analysis (types 18, 20, 22)

Each entry maps to specific error classes from the 101-class catalog and provides 2-3 concrete post-step checks. This is a lightweight L2b defense (~500 tokens/step) that catches errors before the verifier runs.

---

## Structural Findings (2026-02-23 Audit)

### Finding 1: L4 Coverage Overstated — Inter-Wave Gates Are Narrower Than Documented

**Evidence:** execute-phase.md step 8 (lines 302-370) implements inter-wave gates with exactly two checks:
1. `convention check --raw` — verifies convention lock hasn't drifted
2. Dimensional spot-check — scans SUMMARY.md equations for dimensional consistency

The original gap analysis credited L4 with partial (`+`) coverage for error classes #5, 6, 8, 10, 25, 27, 29, 40, 42, 43, 46. None of these are caught by convention or dimensional checking alone:
- #5 (asymptotic expansions) — requires evaluating the expansion, not just checking dimensions
- #8 (intensive/extensive) — dimensional analysis can't distinguish E from E/N when both have energy dimensions
- #42 (anomalies) — anomaly detection requires computing the triangle diagram coefficient, not checking conventions

### Finding 2: L3 Was Effectively Absent for Most Workflows (NOW FIXED)

**Evidence (original):** Bug #23: `pre-commit-check` was called in only 2 workflows.
**Current status (bug #23 fixed):** `pre-commit-check` is now used in 37 of 59 workflows. The remaining 22 workflows are read-only or delegate commits to sub-workflows. The check is still advisory (`|| true`), not blocking.

### Finding 3: Two Defense Layers Were Missing From the Model

**L0 (Plan-checker):** The plan-checker's 16 dimensions include validation strategy (Dim 6), approximation validity (Dim 4), and anomaly/topological awareness (Dim 7). This provides pre-execution structural checking for #13 (BC hallucination via Dim 6), #16 (series truncation via Dim 6 order counting), and #42 (anomalies via Dim 7). However, plan-checker is inherently weak for computational errors — it checks plan DESIGN, not result CORRECTNESS.

**L2b (Executor self-critique + post-step physics guards):** The executor runs mandatory self-critique checkpoints after every 3-4 derivation steps: sign check, factor check, convention check, dimension check, cancellation detection. Additionally, **post-step physics guards** provide targeted detection for the highest-risk error classes: IDENTITY_CLAIM tagging (#11 — requires 3+ test-point verification for training_data identities), BOUNDARY_CONDITION declarations (#13 — verifies BC count matches ODE/PDE order), EXPANSION_ORDER tracking (#16 — enumerates all terms at declared order), and a 12-type computation mini-checklist covering ~20 additional error classes. Guard failures map to deviation rules (3/4/5) for structured recovery. L2b is best-effort — the LLM may skip general self-critique under context pressure — but the targeted guards are lightweight (~50 tokens each) and more resilient.

### Finding 4: Exploratory Profile Creates a Verification Void

In exploratory profile, the verifier runs the 7-check floor (5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.10). This is improved from the original 4-check set but still means **~33 of 101 error classes lose their only defense**. Error classes requiring:
- 5.9 (convergence): all numerical classes
- 5.11 (plausibility): positivity, causality, magnitude checks
- 5.12 (statistics): MC errors, error propagation
- 5.13 (thermodynamic): #8, 9, 29, 31
- 5.14 (spectral): #3, 9, 17, 21
- 5.15 (anomalies): #42, 45

...are all unprotected in exploratory mode. Deep classes #87 (reconnection, needs 5.11), #90 (critical exponents, needs 5.9/5.11), #92 (Lyapunov, needs 5.9) also lose coverage.

### Finding 5: derive-equation.md Had No Convention Verification (NOW FIXED)

The `derive-equation.md` workflow was user-facing with no convention defense layers. **Bug #26 (now fixed):** derive-equation.md now has convention loading via `gpd init` + `convention check --raw` (pre-step), 5-point checklist with hard STOP on mismatch (Step 1b), ASSERT_CONVENTION template (Step 1b + Step 5), and cross-phase consistency check (Step 3e). Standalone derivations now have L1 + L2 coverage.

---

## Tier 4 Skip Risk

Under context pressure, the verifier may skip Tier 4 checks (5.13-5.15):
- **5.13 Thermodynamic Consistency** — catches #8 (intensive/extensive), #9 (thermal FT), #29 (Boltzmann factor), #31 (ensemble)
- **5.14 Spectral** — catches #3 (Green's fn), #9 (thermal FT), #17 (correlation/response), #21 (branch cuts)
- **5.15 Anomalies/Topology** — catches #42 (Noether/anomaly), #45 (topological terms)

**Risk:** 10 error classes lose their primary detection mechanism when Tier 4 is skipped.

**Proposed fix:** The verifier's Tier 4 skip logic should check if the current phase involves any of these computation types. If yes, the relevant Tier 4 check is promoted to Tier 2 for that phase:
- Phase involves thermodynamics → promote 5.13
- Phase involves Green's functions or transport → promote 5.14
- Phase involves gauge theory or topology → promote 5.15

This can be implemented via the plan frontmatter: the planner tags the computation type, and the verifier uses it to adjust tier priorities.

---

## Layer 3 (Pre-commit check) — Current State and Enhancement Opportunities

The pre-commit check already performs:
- **NaN detection** in state.json (prevents state corruption)
- **ASSERT_CONVENTION validation** — scans staged `.md` and `.tex` files for convention assertion lines and verifies them against the project lock in state.json (catches #7, #15, #33, #34, #37)
- **Frontmatter completeness** — verifies SUMMARY and PLAN files have required fields

It does NOT perform physics-content checks beyond convention assertions. Enhancement opportunities:
1. **Scan for `IDENTITY_CLAIM` tags** (from Gap 1 fix) — verify tagged identities have been numerically checked
2. **Scan for `BOUNDARY_CONDITIONS`** (from Gap 2 fix) — verify BC count matches ODE/PDE order
3. **Scan for `EXPANSION_ORDER`** (from Gap 3 fix) — verify order-tracking annotations are present in perturbative derivations

Cost: ~500-1k additional tokens per commit. These are syntactic/structural checks (not physics verification), keeping the pre-commit check fast.

---

## Layer 4 (Inter-wave gates) Enhancement

Currently inter-wave gates check only convention consistency and dimensional analysis. This could be extended:

**Proposed additions:**
1. **Limiting case spot-check**: Pick ONE known limit from the just-completed wave's results and verify it. Cost: ~500 tokens.
2. **Sign consistency check**: For results with physical sign constraints (energies, probabilities, spectral functions), verify the sign is correct. Cost: ~200 tokens.
3. **Order counting check**: For perturbative results, verify all terms at the declared order are present. Cost: ~300 tokens.

Total overhead per gate: ~1k additional tokens (from ~2-5k to ~3-6k). Catches error classes #16, #24, #36 early.

---

## Cross-Phase Consistency (Layer 6) Enhancement

The consistency checker currently checks convention drift and provides/requires chains. It could additionally check:

1. **Approximation validity propagation**: When Phase N establishes a result valid for g < g_max, verify that Phase N+k doesn't use it at g > g_max. Currently checks "approximation validity ranges" but the implementation is vague.
2. **Numerical value consistency**: When Phase N computes a physical quantity (mass, coupling, etc.) and Phase M uses it, verify the numerical values match (not just that the symbol is defined).
3. **Error class regression**: If Phase N's verifier found and fixed a specific error class, check that Phase N+k doesn't reintroduce the same error pattern.

---

## Proposed Implementation Priority (Revised 2026-02-23)

| Priority | Fix | Error Classes Addressed | Cost | Layers Affected |
|---|---|---|---|---|
| ~~P0~~ | ~~Expand pre-commit-check to all commit-producing workflows~~ — **DONE** (bug #23 fixed, 37/59 workflows). | Convention-related: #7, 15, 33, 34, 37 | 0 (workflow edits only) | L3 |
| **P0** | **Exploratory profile minimum check floor** — IMPLEMENTED: exploratory now runs 7-check floor (5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.10). Reduces gap from 36→~16 unprotected error classes. | ~16 classes that lose coverage in exploratory mode | 0 (verifier logic change) | L5 |
| **P0** | Executor self-check protocol (computation-type mini-checklist) | All 38 single-reliable-layer classes | ~500 tokens/step | New: L2b strengthening |
| **P1** | IDENTITY_CLAIM tagging for hallucinated identities | #11 | ~200 tokens/identity | L4 (inter-wave gate) |
| **P1** | BC declaration in plan-checker + executor | #13 | ~100 tokens/derivation | L0 (plan-checker Dim 6) + L5 |
| ~~P1~~ | ~~Add convention check to derive-equation.md~~ — **DONE** (bug #26 fixed). Pre-step loads convention lock, Step 1b has 5-point checklist + ASSERT_CONVENTION, Step 3e has cross-phase consistency. | #7, 15, 33, 34, 37 for standalone derivations | ~200 tokens | L1 + L2 for standalone path |
| **P2** | Tier 4 promotion based on computation type | #3, 8, 9, 17, 21, 29, 31, 42, 45 | 0 (logic change) | L5 (verifier) |
| **P2** | Order-tracking annotation for perturbative expansions | #16 | ~100 tokens/expansion | L2 + L4 |
| **P2** | **Inter-wave gate enhancements: add limiting case spot-check + sign check** — L4 is currently convention+dimensional only | #16, 24, 36 + partial coverage for 10+ classes | ~1k tokens/gate | L4 |
| **P3** | Pre-commit physics smoke tests (identity scan, BC count, order tracking) | Convention errors + #11, 13, 16 | ~1-2k tokens/commit | L3 |
| **P3** | Consistency checker numerical value matching | Cross-phase factor errors | ~500 tokens/check | L6 |

---

## Extended Error Classes (#52-101) — Defense Layer Mapping

Error catalog expanded from 51 to 101 classes. Classes #52-81 added in Wave 11 (numerical relativity, astrophysics, quantum chemistry, plasma, fluids, biophysics, quantum information). Classes #82-101 added subsequently (nuclear physics, AMO, condensed matter, mathematical physics, nonlinear dynamics, optics, cosmology).

| # | Error Class | Primary L5 Check | Protocol Coverage |
|---|---|---|---|
| 52 | Constraint violation (NR) | 5.8 math, 5.9 conv | general-relativity |
| 53 | Wrong stellar structure | 5.3 limits, 5.10 lit | general-relativity |
| 54 | BSSE (quantum chem) | 5.10 literature | — (gap) |
| 55 | Wrong XC functional | 5.10 literature | quantum-many-body |
| 56 | Plasma instability criterion | 5.1 dim, 5.3 limits | fluid-dynamics-mhd |
| 57 | Reynolds regime confusion | 5.11 plausibility | fluid-dynamics-mhd |
| 58 | Entanglement vs thermo S | 5.1 dim, 5.3 limits | — |
| 59 | Quantum circuit depth | 5.2 spot-check | open-quantum-systems |
| 60 | Coarse-graining artifacts | 5.10 literature | — (gap) |
| 61 | Gauge-fixing artifacts | 5.6 symmetry, L1 lock | — |
| 62 | Missing finite-size effects | 5.9 conv, 5.12 stats | statistical-inference |
| 63 | GW template mismatch | 5.10 lit, 5.2 spot | statistical-inference |
| 64 | Optical depth confusion | 5.1 dimensional | — |
| 65 | Wrong dispersion in media | 5.3 limits, 5.1 dim | — |
| 66 | Semiclassical beyond validity | 5.3 limits, 5.11 plaus | — |
| 67 | Adiabatic elimination errors | 5.3 limits, 5.8 math | open-quantum-systems |
| 68 | Incorrect Kramers-Kronig | 5.14 spectral, 5.8 | quantum-many-body |
| 69 | Molecular symmetry misID | 5.6 symmetry | — (gap) |
| 70 | Wrong Landau levels | 5.3 limits, 5.10 lit | — |
| 71 | Ignoring Berry phase | 5.6 sym, 5.15 topo | — |
| 72 | Gauge mode leakage (NR) | 5.9 convergence | general-relativity |
| 73 | CFL condition violation | 5.9 convergence | fluid-dynamics-mhd |
| 74 | DFT+U double counting | 5.10 lit, 5.3 limits | quantum-many-body |
| 75 | Broken spin symmetry | 5.8 math, 5.2 spot | — |
| 76 | Debye length resolution | 5.9 convergence | fluid-dynamics-mhd |
| 77 | Kinetic vs fluid mismatch | 5.11 plausibility | fluid-dynamics-mhd |
| 78 | Numerical diffusion | 5.9 convergence | fluid-dynamics-mhd |
| 79 | Turbulence model extrapolation | 5.10 lit, 5.11 plaus | fluid-dynamics-mhd |
| 80 | Implicit solvent artifacts | 5.10 literature | — (gap) |
| 81 | Force field transferability | 5.10 lit, 5.1 dim | — (gap) |
| 82 | Wrong nuclear magic numbers | 5.10 lit, 5.3 limits | — (gap) |
| 83 | Eddington luminosity errors | 5.1 dim, 5.10 lit | — (gap) |
| 84 | Wrong Friedmann equation | 5.3 limits, 5.10 lit | cosmological-perturbation (partial) |
| 85 | Wrong multiphoton selection rules | 5.6 symmetry, 5.10 lit | — (gap) |
| 86 | BCS gap equation errors | 5.10 lit, 5.3 limits | quantum-many-body (partial) |
| 87 | Wrong reconnection topology | 5.10 lit, 5.11 plaus | fluid-dynamics-mhd (partial) |
| 88 | Wrong decoherence channel | 5.10 lit, 5.8 math | open-quantum-systems |
| 89 | Holonomic vs non-holonomic | 5.8 math | constrained-dynamics |
| 90 | Hyperscaling / critical exponents | 5.3 limits, 5.10 lit | — |
| 91 | Wrong conformal mapping | 5.2 spot-check, 5.8 math | — (gap) |
| 92 | Wrong Lyapunov exponent | 5.8 math, 5.9 conv | dynamical-systems (partial) |
| 93 | Fresnel vs Fraunhofer confusion | 5.1 dim, 5.3 limits | electromagnetic (partial) |
| 94 | Wrong Maxwell construction | 5.3 limits, 5.10 lit | — |
| 95 | Wrong Brillouin zone | 5.6 symmetry, 5.10 lit | electronic-structure (partial) |
| 96 | Wrong nuclear binding energy | 5.1 dim, 5.10 lit | — (gap) |
| 97 | Wrong Penrose diagram | 5.10 lit, 5.3 limits | general-relativity (partial) |
| 98 | Wrong entanglement measure | 5.8 math | open-quantum-systems (partial) |
| 99 | Wrong magnetic mirror ratio | 5.1 dim, 5.3 limits | fluid-dynamics-mhd (partial) |
| 100 | Jeans instability criterion | 5.1 dim, 5.3 limits, 5.10 lit | — (gap) |
| 101 | Kramers degeneracy misapplication | 5.6 symmetry, 5.10 lit | electronic-structure (partial) |

**Updated statistics (101 classes):** All 50 extended/deep classes have at least L5 coverage. 25/50 have dedicated protocol coverage. 10 gaps remain (#54 BSSE, #60 coarse-graining, #69 molecular symmetry, #80 implicit solvent, #81 force fields, #82 nuclear magic numbers, #83 Eddington luminosity, #85 multiphoton selection rules, #91 conformal mapping, #96 nuclear binding energy, #100 Jeans instability) — need nuclear physics, AMO, astrophysics, and mathematical physics protocols. The existing protocols (fluid-dynamics-mhd, quantum-many-body, general-relativity, open-quantum-systems, statistical-inference, constrained-dynamics, dynamical-systems, electromagnetic, electronic-structure, cosmological-perturbation) collectively cover 25 extended/deep error classes with domain-specific detection guidance.

## See Also

- `../errors/llm-physics-errors.md` — Full 101-error-class catalog with detection strategies
- `../meta/verification-hierarchy-mapping.md` — Agent scope boundaries and check mappings
- `../core/verification-core.md` — Universal verification checks
- `../../shared/shared-protocols.md` — Convention Tracking Protocol and ASSERT_CONVENTION syntax
- `references/orchestration/agent-infrastructure.md` — Convention Loading Protocol
