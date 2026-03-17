# Shared Protocols

Common protocols referenced by multiple GPD agents. Import via `references/shared/shared-protocols.md`.

Agents must NEVER install dependencies silently. Ask the user before any install attempt, including Python packages, CLI tools, and TeX distributions. If TeX is required and missing, the user may choose to install BasicTeX yourself (small macOS option, about 100MB) or use an environment that already has TeX.

## Forbidden Files

**NEVER read or quote contents from these files (even if they exist):**

- `.env`, `.env.*`, `*.env` -- Environment variables with secrets
- `credentials.*`, `secrets.*`, `*secret*`, `*credential*` -- Credential files
- `*.pem`, `*.key`, `*.p12`, `*.pfx`, `*.jks` -- Certificates and private keys
- `id_rsa*`, `id_ed25519*`, `id_dsa*` -- SSH private keys
- `.npmrc`, `*.netrc` -- Package manager auth tokens
- `config/secrets/*`, `.secrets/*`, `secrets/` -- Secret directories
- `*.keystore`, `*.truststore` -- Java keystores
- `serviceAccountKey.json`, `*-credentials.json` -- Cloud service credentials
- Any file in `.gitignore` that appears to contain secrets

**Additional caution for physics projects:**

- Private experimental data under NDA or embargo
- Unpublished results from collaborators not yet cleared for sharing
- Referee reports and editorial correspondence
- Pre-publication manuscripts from other groups shared in confidence

**If you encounter these files:**

- Note their EXISTENCE only: "`.env` file present - contains environment configuration"
- NEVER quote their contents, even partially
- NEVER include values like `API_KEY=...` or `sk-...` in any output

**Why this matters:** Your output gets committed to git. Leaked secrets = security incident. Leaked embargoed data = collaboration violation.

## Convention Tracking Protocol

Physics calculations are invalidated by convention mismatches. Every agent working with equations must track conventions explicitly.

### Required Convention Declarations

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

### Convention Lock

At the start of every task:

1. Read `convention_lock` from STATE.md/state.json
2. Read `conventions` from the plan frontmatter
3. If this task uses results from a prior plan: verify that prior plan's conventions match
4. State explicitly at the top of every derivation file which conventions are in effect

### Before Every Fourier Transform

State the sign convention and where the 2pi lives:

```
% Fourier convention: f(x) = integral dk/(2pi) f(k) e^{+ikx}
% Inverse:            f(k) = integral dx f(x) e^{-ikx}
% (physics convention with 2pi in the dk measure)
```

Different conventions differ by powers of 2pi and signs in the exponent. The three common ones are:

| Convention | Forward (x -> k)               | Inverse (k -> x)               | Where 2pi lives        |
| ---------- | ------------------------------ | ------------------------------ | ---------------------- |
| Physics    | integral dx e^{-ikx}           | integral dk/(2pi) e^{+ikx}     | In dk                  |
| Math       | integral dx e^{-2pi*i*kx}      | integral dk e^{+2pi*i*kx}      | Absorbed into exponent |
| Symmetric  | integral dx/sqrt(2pi) e^{-ikx} | integral dk/sqrt(2pi) e^{+ikx} | Split between both     |

**Always state which row you are using.**

### Before Every Metric Contraction

State the signature convention and verify:

```
% Metric: g = diag(+1, -1, -1, -1)
% Verification: g^{mu nu} g_{nu rho} = delta^mu_rho
% Implication: k^2 = k_mu k^mu = k_0^2 - |k|^2
% On-shell: k^2 = m^2 (positive)
```

If using (-,+,+,+): k^2 = -k_0^2 + |k|^2, and on-shell k^2 = -m^2. The propagator is 1/(k^2 + m^2) not 1/(k^2 - m^2). Getting this wrong flips signs everywhere.

### Before Every Commutator/Anticommutator

State the ordering convention:

- **Canonical commutation:** [x, p] = i\*hbar (or i in natural units). Sign and factor of hbar.
- **Creation/annihilation:** [a, a^dag] = 1 (bosons), {b, b^dag} = 1 (fermions)
- **Field commutators:** [phi(x), pi(y)] = i\*delta(x-y). State equal-time vs covariant.
- **Normal ordering:** : a^dag a : = a^dag a (no constant subtraction). But : a a^dag : = a^dag a (reordered).

### Automated Convention Enforcement

At the start of each task, agents MUST:

1. **Read `convention_lock`** from STATE.md/state.json and verify all conventions match the project lock
2. **Before every Fourier transform,** verify the sign convention matches the locked convention — state explicitly which row of the Fourier convention table is in use
3. **Before combining expressions from different sources,** run the 5-point checklist:
   - Metric signature matches? (check propagator sign)
   - Fourier convention matches? (check 2π placement)
   - State normalization matches? (check relativistic vs non-relativistic)
   - Coupling convention matches? (check g vs alpha = g^2/(4pi) — a factor of 4pi per vertex)
   - Renormalization scheme matches? (check MS-bar vs on-shell — finite parts differ)

If any check fails, resolve the mismatch BEFORE proceeding. Never combine and "fix later."

### Convention Conflict Detection

Before using any equation from an external source, verify:

1. **Metric signature** -- Does the source use the same signature? A propagator derived with (-,+,+,+) has opposite signs from one derived with (+,-,-,-).
2. **Fourier convention** -- Where does the 2pi live? Factors of 2pi are the #1 source of "factor of 2pi" discrepancies.
3. **Coupling constant definition** -- Is it g, g^2, g^2/(4pi), or alpha=g^2/(4pi)?
4. **Field normalization** -- Canonical vs relativistic normalization of states and fields.
5. **Renormalization scheme** -- MS-bar, on-shell, momentum subtraction? Intermediate quantities are scheme-dependent.

### When Combining Expressions from Different Sources

Before combining two expressions (e.g., a propagator from one derivation with a vertex from another):

1. **Verify unit systems match.** Both in natural units? Both in SI? If mixed: convert explicitly.
2. **Verify metric signatures match.** Both (+,-,-,-)? If not: do not combine. Convert one first.
3. **Verify Fourier conventions match.** Same sign in exponent? Same placement of 2pi? If not: insert the conversion factor.
4. **Verify state normalizations match.** Both relativistic (<p|q> = (2pi)^3 2E delta)? Both non-relativistic (<p|q> = delta)? The cross section formula depends on this.
5. **Verify coupling conventions match.** Both using the same definition of the coupling? g vs g^2/(4pi) vs alpha introduces factors of 4pi at every vertex. If different: convert explicitly.
6. **Verify renormalization schemes match.** Both MS-bar? Both on-shell? Intermediate quantities (counterterms, anomalous dimensions, finite parts) are scheme-dependent. Mixing schemes silently produces wrong finite parts.
7. **Document the verification.** "Propagator from theory.tex uses (+,-,-,-) and physics Fourier convention. Vertex from vertex.tex uses same. Coupling: both use alpha_s = g^2/(4pi) in MS-bar. Compatible --- combining directly."

If any mismatch is found: resolve it BEFORE combining. Never combine and "fix later."

### Convention Propagation Rules

- If Phase 01 established metric (+,-,-,-), ALL subsequent phases MUST use it unless an explicit convention change task is included
- When citing results from sources with different conventions, convert BEFORE using
- Document all convention choices in project CONVENTIONS.md
- When ambiguity is possible, annotate each equation with its convention

### Cross-Phase Error Propagation

When a phase consumes results from a prior phase, uncertainties must be tracked explicitly:

1. **Identify inputs from prior phases.** List every quantity imported from a previous phase with its uncertainty or error estimate.
2. **Propagate uncertainties.** Use standard error propagation (quadrature for independent errors, linear for correlated errors) through every calculation step that uses imported quantities.
3. **Document propagation.** In the phase SUMMARY, include a section listing: (a) imported quantities with their uncertainties, (b) how uncertainties entered the current calculation, (c) the resulting uncertainty on this phase's outputs.
4. **Flag amplification.** If uncertainty is amplified (e.g., exponentiation, division by small numbers, chaotic sensitivity), flag this explicitly as a potential validity concern.
5. **Use `/gpd:error-propagation`** for systematic tracking across multi-phase calculations.

**Why this matters:** Without explicit tracking, error bars on final results are underestimated. A 5% uncertainty in Phase 2 can become 50% by Phase 6 through amplification, but if never tracked, the final result appears precise.

### Machine-Readable Convention Assertions

Every derivation file, computation script, and notebook must include a parseable assertion line declaring which conventions are in effect. This enables automated verification by the consistency checker and verifier agent.

**Syntax:**

```
% ASSERT_CONVENTION: key=value, key=value, ...
```

For LaTeX files, use `%` comment prefix. For Python, use `#`. For Markdown, use an HTML comment `<!-- ASSERT_CONVENTION: ... -->`.

**Required keys** (must match convention_lock key names from `gpd convention list`):

| Key | Values | Example |
|---|---|---|
| `natural_units` | `natural`, `SI`, `CGS`, `lattice` | `natural_units=natural` |
| `metric_signature` | `mostly-plus`, `mostly-minus`, `euclidean` | `metric_signature=mostly-plus` |
| `fourier_convention` | `physics`, `math`, `symmetric` | `fourier_convention=physics` |
| `coupling_convention` | `g`, `g^2/(4pi)`, `alpha=g^2/(4pi)`, or explicit | `coupling_convention=alpha=g^2/(4pi)` |
| `renormalization_scheme` | `MSbar`, `on-shell`, `MOM`, `lattice` | `renormalization_scheme=MSbar` |
| `state_normalization` | `relativistic`, `non-relativistic` | `state_normalization=relativistic` |
| `gauge_choice` | `Feynman`, `Lorenz`, `Coulomb`, `axial`, `light-cone` | `gauge_choice=Feynman` |
| `time_ordering` | `normal`, `time`, `Weyl` | `time_ordering=time` |

**IMPORTANT:** Keys should use the canonical convention_lock field names from state.json (use `gpd --raw convention list` to see them). Short aliases are also accepted by the `ASSERT_CONVENTION` parser used by convention validation, the verifier, and the consistency checker: `metric` → `metric_signature`, `fourier` → `fourier_convention`, `units` → `natural_units`, `coupling` → `coupling_convention`, `renorm` → `renormalization_scheme`, `gauge` → `gauge_choice`. Canonical names are preferred for clarity.

**IMPORTANT:** Values must NOT contain commas (the parser splits on commas to separate key=value pairs). Prefer the canonical values shown by `gpd --raw convention list`: `mostly-minus` and `mostly-plus`, not the comma forms `(+,-,-,-)` or `(-,+,+,+)`. The parser also normalizes underscore aliases like `mostly_minus`, but the canonical lock values are hyphenated.

**Examples:**

```latex
% ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-plus, fourier_convention=physics, coupling_convention=alpha=g^2/(4pi), renormalization_scheme=MSbar, gauge_choice=Feynman
```

```python
# ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-plus, coupling_convention=alpha=g^2/(4pi), renormalization_scheme=MSbar
```

```markdown
<!-- ASSERT_CONVENTION: natural_units=natural, metric_signature=mostly-minus, fourier_convention=physics -->
```

**Important:** Values must exactly match what is stored in `state.json convention_lock`. Read them via `gpd convention list` rather than guessing. `ASSERT_CONVENTION` validation normalizes accepted key aliases and then compares the declared values against the lock.

**Verification protocol:**

1. The executor writes an `ASSERT_CONVENTION` line at the top of every derivation file it creates or modifies
2. The verifier scans for `ASSERT_CONVENTION` lines in all phase artifacts and compares each declared value against the project convention lock in `state.json`
3. A mismatch between an assertion and the lock is a **blocker** — it means the file was written under different conventions than the project standard
4. A missing assertion in a file that contains equations is a **warning** — conventions should be declared explicitly

## Source Hierarchy

**MANDATORY: Authoritative sources BEFORE general search**

### Tier 1: Standard References (Always check first)

**Textbooks by subfield:**

| Subfield              | Standard References                                            |
| --------------------- | -------------------------------------------------------------- |
| Quantum Field Theory  | Peskin & Schroeder; Weinberg (vols 1-3); Schwartz; Zinn-Justin |
| Quantum Mechanics     | Sakurai & Napolitano; Griffiths; Cohen-Tannoudji               |
| Statistical Mechanics | Pathria & Beale; Kardar (vols 1-2); Huang                      |
| Condensed Matter      | Altland & Simons; Chaikin & Lubensky; Ashcroft & Mermin        |
| General Relativity    | Carroll; Wald; Misner, Thorne, Wheeler                         |
| Electrodynamics       | Jackson; Griffiths; Zangwill                                   |
| Many-Body Theory      | Fetter & Walecka; Abrikosov, Gorkov, Dzyaloshinskii; Mahan     |
| Mathematical Methods  | Arfken, Weber & Harris; Bender & Orszag; Morse & Feshbach      |
| Particle Physics      | Halzen & Martin; Griffiths; PDG Review                         |
| Nuclear Physics       | Ring & Schuck; Bertulani; Krane                                |
| Astrophysics          | Weinberg (Cosmology); Shapiro & Teukolsky; Rybicki & Lightman  |

**Databases:**

- Particle Data Group (PDG) -- particle properties, coupling constants, masses
- NIST -- physical constants, atomic spectra, thermodynamic data
- DLMF (Digital Library of Mathematical Functions) -- special functions, identities
- OEIS -- integer sequences (useful for combinatorial physics)

### Tier 2: Review Articles

Search in:

- Reviews of Modern Physics (RMP)
- Physics Reports
- Annual Review of Condensed Matter Physics / Nuclear and Particle Science
- Reports on Progress in Physics
- Living Reviews in Relativity

Query pattern: `"[topic]" review` on arXiv or Google Scholar, sort by citations.

### Tier 3: Primary Literature

- arXiv (preprints and published versions)
- Physical Review (A/B/C/D/E/Letters)
- Journal of High Energy Physics (JHEP)
- Nuclear Physics B
- Journal of Statistical Mechanics (JSTAT)
- New Journal of Physics
- Nature Physics, Science (for high-impact results)

### Tier 4: Community Resources

- web_search for code repositories (GitHub, GitLab)
- Stack Exchange (Physics, MathOverflow) for conceptual clarifications
- Conference proceedings for very recent results
- Thesis repositories for detailed expositions

**Priority order:** Textbooks/Reviews > Peer-Reviewed Papers > Cited arXiv Preprints > Official Tool Docs > Verified web_search > Unverified Sources

### Confidence Levels

| Level | Sources | Use |
|---|---|---|
| HIGH | Published reviews, textbooks, PDG/NIST values, multiple peer-reviewed papers agree | State as established result |
| MEDIUM | Recent arXiv preprints by established groups, single peer-reviewed source, computational benchmarks | State with attribution |
| LOW | Single arXiv preprint, blog post, unverified computation, training data only | Flag as needing validation |

## Physics Verification

For the complete verification hierarchy and check procedures, see `references/verification/core/verification-core.md` (universal checks) and the domain-specific verification files (13 domains — see table below). For a compact checklist, see `references/verification/core/verification-quick-reference.md`. For HIGH-risk error class priorities, see `references/verification/audits/verification-gap-summary.md`.

For LLM-specific physics error patterns and detection strategies, see `references/verification/errors/llm-physics-errors.md`. For a lightweight traceability matrix, see `references/verification/errors/llm-errors-traceability.md`.

For convention declarations, see `../conventions/conventions-quick-reference.md` (compact) or the Convention Tracking Protocol section above (full).

**Quick reference** — verification priority order:
1. Dimensional analysis (catches ~40% of errors)
2. Known limiting cases
3. Conservation laws and symmetries
4. Numerical spot-checks
5. Literature comparison

## Detailed Protocol References

Each protocol below provides step-by-step procedures for a specific computational method or mathematical technique. Import the relevant protocol when working in that domain.

### Core Derivation Protocols

| Protocol | File | When to Use |
|---|---|---|
| Derivation Discipline | `references/protocols/derivation-discipline.md` | Every derivation — sign tracking, convention annotation, checkpointing |
| Integral Evaluation | `references/protocols/integral-evaluation.md` | Any integral — convergence, contour, regularization |
| Perturbation Theory | `references/protocols/perturbation-theory.md` | Any perturbative expansion — combinatorics, Ward identities, divergences |
| Renormalization Group | `references/protocols/renormalization-group.md` | RG flows, beta functions, fixed points, critical exponents |
| Path Integrals | `references/protocols/path-integrals.md` | Path integral evaluation — measure, saddle points, anomalies |
| Effective Field Theory | `references/protocols/effective-field-theory.md` | EFT construction — power counting, matching, running |
| Electrodynamics | `references/protocols/electrodynamics.md` | EM calculations — unit systems, Maxwell equations, radiation, Lienard-Wiechert, duality |
| Analytic Continuation | `references/protocols/analytic-continuation.md` | Wick rotation, Matsubara sums, numerical continuation, dispersion relations |
| Order of Limits | `references/protocols/order-of-limits.md` | Any calculation with multiple limits — non-commuting limit detection |
| Classical Mechanics | `references/protocols/classical-mechanics.md` | Lagrangian/Newtonian mechanics — constraints, conserved quantities, oscillations |
| Hamiltonian Mechanics | `references/protocols/hamiltonian-mechanics.md` | Canonical transformations, Poisson brackets, Hamilton-Jacobi, action-angle variables |
| Scattering Theory | `references/protocols/scattering-theory.md` | Cross sections, phase shifts, S-matrix, partial waves, optical theorem |
| Phenomenology | `references/protocols/phenomenology.md` | Likelihoods, global fits, EFT validity, recasting, correlated uncertainties, public reinterpretation |
| Supersymmetry | `references/protocols/supersymmetry.md` | SUSY algebra, BPS bounds, localization, Seiberg-Witten/duality, soft breaking, supergravity caveats |
| String Field Theory | `references/protocols/string-field-theory.md` | BRST string fields, star product, BV, `A_infinity` / `L_infinity`, tachyon condensation |
| Cosmological Perturbation Theory | `references/protocols/cosmological-perturbation-theory.md` | Inflation, scalar/tensor perturbations, gauge choices, power spectra |
| de Sitter Space | `references/protocols/de-sitter-space.md` | Positive cosmological constant, cosmological horizons, dS/CFT, static patch holography |
| Thukdam Protocol | `references/protocols/thukdam-protocol.md` | Post-mortem phase coherence, reverse projection theory, Clear Light state decoding |
| Holography / AdS-CFT | `references/protocols/holography-ads-cft.md` | AdS/CFT dictionary, holographic renormalization, entanglement entropy |
| Quantum Error Correction | `references/protocols/quantum-error-correction.md` | Stabilizer codes, surface codes, fault tolerance, threshold theorems |
| Resummation | `references/protocols/resummation.md` | Borel summation, Pade approximants, conformal mapping, optimized perturbation theory |

### Computational Method Protocols

| Protocol | File | When to Use |
|---|---|---|
| Monte Carlo Methods | `references/protocols/monte-carlo.md` | MC simulations — thermalization, autocorrelation, error estimation, sign problem |
| Variational Methods | `references/protocols/variational-methods.md` | Variational calculations — ansatz design, optimization, VMC, coupled cluster |
| Density Functional Theory | `references/protocols/density-functional-theory.md` | DFT calculations — functional selection, convergence, band gaps, vdW |
| Lattice Gauge Theory | `references/protocols/lattice-gauge-theory.md` | Lattice QCD/QFT — fermion discretization, topology, continuum extrapolation |
| Tensor Networks | `references/protocols/tensor-networks.md` | MPS/DMRG/PEPS — bond dimension convergence, entanglement, time evolution |
| Symmetry Analysis | `references/protocols/symmetry-analysis.md` | Symmetry identification, representations, selection rules, SSB, anomalies |
| Asymptotic Symmetries | `references/protocols/asymptotic-symmetries.md` | Bondi gauge, null infinity, large gauge transformations, BMS charges, soft/memory checks |
| Generalized Symmetries | `references/protocols/generalized-symmetries.md` | Higher-form symmetries, center symmetry, higher-group structure, non-invertible defects, anomaly checks |
| Non-Equilibrium Transport | `references/protocols/non-equilibrium-transport.md` | Kubo formulas, Keldysh formalism, Boltzmann equation, Mori-Zwanzig |
| Finite-Temperature Field Theory | `references/protocols/finite-temperature-field-theory.md` | Matsubara frequencies, Schwinger-Keldysh, HTL resummation, IR problems |
| Conformal Bootstrap | `references/protocols/conformal-bootstrap.md` | Crossing symmetry, OPE, unitarity bounds, SDPB, extremal functionals |
| Numerical Relativity | `references/protocols/numerical-relativity.md` | 3+1 decomposition, BSSN, gauge conditions, constraint monitoring, GW extraction |
| Exact Diagonalization | `references/protocols/exact-diagonalization.md` | Lanczos, Hilbert space truncation, symmetry sectors, spectral functions |
| Many-Body Perturbation Theory | `references/protocols/many-body-perturbation-theory.md` | GW approximation, Bethe-Salpeter, quasiparticle self-energy, vertex corrections |
| Molecular Dynamics | `references/protocols/molecular-dynamics.md` | MD simulations, force fields, thermostats, barostats, integration schemes |
| Machine Learning for Physics | `references/protocols/machine-learning-physics.md` | Neural network potentials, physics-informed ML, generative models, symmetry equivariance |
| Stochastic Processes | `references/protocols/stochastic-processes.md` | Langevin equation, Fokker-Planck, master equations, stochastic calculus |
| Kinetic Theory | `references/protocols/kinetic-theory.md` | Boltzmann equation, collision integrals, Chapman-Enskog, transport coefficients |
| Bethe Ansatz | `references/protocols/bethe-ansatz.md` | Coordinate/algebraic/thermodynamic Bethe ansatz, integrable models, spin chains |
| Random Matrix Theory | `references/protocols/random-matrix-theory.md` | GOE/GUE/GSE ensembles, level spacing, Tracy-Widom, quantum chaos diagnostics |

### Mathematical Method Protocols

| Protocol | File | When to Use |
|---|---|---|
| Algebraic QFT | `references/protocols/algebraic-qft.md` | Haag-Kastler nets, modular theory, DHR sectors, factor types, split and duality properties |
| Group Theory | `references/protocols/group-theory.md` | Representations, Clebsch-Gordan coefficients, character tables, selection rules |
| Topological Methods | `references/protocols/topological-methods.md` | Berry phase, Chern numbers, topological invariants, edge states, bulk-boundary |
| Green's Functions | `references/protocols/green-functions.md` | Retarded/advanced/Matsubara propagators, spectral functions, Dyson equation, analytic continuation |
| WKB & Semiclassical | `references/protocols/wkb-semiclassical.md` | WKB approximation, Bohr-Sommerfeld, tunneling, connection formulas, semiclassical limit |
| Large-N Expansion | `references/protocols/large-n-expansion.md` | 1/N expansion, 't Hooft limit, saddle-point, planar diagrams, matrix models |

### Domain-Specific Verification

| Domain | File | What It Covers |
|---|---|---|
| QFT / Particle / GR | `references/verification/domains/verification-domain-qft.md` | Ward identities, unitarity, crossing symmetry, gauge invariance |
| Condensed Matter | `references/verification/domains/verification-domain-condmat.md` | f-sum rule, Luttinger theorem, Kramers-Kronig, Goldstone modes |
| Statistical Mechanics / Cosmology | `references/verification/domains/verification-domain-statmech.md` | Detailed balance, thermodynamic limit, finite-size scaling, critical exponents |
| Fluid Dynamics / Plasma Physics | `references/verification/domains/verification-domain-fluid-plasma.md` | MHD equilibrium, Alfven waves, reconnection, turbulence spectra, conservation laws, CFL, div(B) |
| General Relativity / Cosmology | `references/verification/domains/verification-domain-gr-cosmology.md` | Coordinate invariance, ADM consistency, energy conditions, Friedmann equations |
| AMO Physics | `references/verification/domains/verification-domain-amo.md` | RWA validity, selection rules, dipole approximation, AC Stark shifts |
| Nuclear / Particle Physics | `references/verification/domains/verification-domain-nuclear-particle.md` | Magic numbers, shell model, parton sum rules, CKM unitarity |
| Astrophysics | `references/verification/domains/verification-domain-astrophysics.md` | Eddington luminosity, stellar structure, Jeans mass, opacity |
| Mathematical Physics | `references/verification/domains/verification-domain-mathematical-physics.md` | Analyticity, spectral theory, asymptotics, distribution theory |
| Algebraic QFT | `references/verification/domains/verification-domain-algebraic-qft.md` | Haag-Kastler nets, modular theory, type `I/II/III`, DHR sectors, split and duality checks |
| String Field Theory | `references/verification/domains/verification-domain-string-field-theory.md` | BRST nilpotency, ghost/picture counting, BPZ cyclicity, truncation convergence |
| Quantum Information | `references/verification/domains/verification-domain-quantum-info.md` | CPTP maps, entanglement measures, information bounds, channel capacity |
| Soft Matter / Biophysics | `references/verification/domains/verification-domain-soft-matter.md` | Equilibration, scaling laws, force fields, finite-size analysis |

### Numerical and Translation Protocols

| Protocol | File | When to Use |
|---|---|---|
| Numerical Computation | `references/protocols/numerical-computation.md` | Numerical stability, convergence testing, error propagation |
| Symbolic to Numerical | `references/protocols/symbolic-to-numerical.md` | Converting analytic results to numerical code |

### LLM-Specific Error Guards

| Reference | File | When to Use |
|---|---|---|
| LLM Physics Error Catalog | `references/verification/errors/llm-physics-errors.md` | Index to 104 systematic error classes across 4 part files with detection strategies |
| Verification Gap Summary | `references/verification/audits/verification-gap-summary.md` | HIGH-risk error classes for routine verification prioritization (compact summary) |

The LLM Physics Error Catalog documents error patterns specific to language model outputs (wrong CG coefficients, hallucinated identities, Grassmann sign errors, etc.) and should be consulted as a checklist when verifying LLM-produced calculations. The catalog is split into 4 files for context efficiency: `references/verification/errors/llm-errors-core.md` (#1-25), `references/verification/errors/llm-errors-field-theory.md` (#26-51), `references/verification/errors/llm-errors-extended.md` (#52-81, #102-104), `references/verification/errors/llm-errors-deep.md` (#82-101).

## Research Agent Shared Protocol

Shared by gpd-project-researcher and gpd-phase-researcher. Full protocol in `references/research/researcher-shared.md`.

### Core Principles

1. **Training Data = Hypothesis.** The assistant's training is stale. Verify before asserting. Prefer current sources. Flag uncertainty.
2. **The Literature as Ground Truth.** Search before deriving. Know the classic papers. Respect no-go theorems. Track the state of the art.
3. **Honest Reporting.** "I could not find X" is valuable. LOW confidence is valuable. Contradictions between sources are valuable.
4. **Investigation, Not Confirmation.** Survey the landscape of approaches. Let evidence drive recommendations, not initial preferences.
5. **Physics-Specific Integrity.** Respect dimensionality, symmetries, limiting cases, and conservation laws in all recommended methods.

### Research Methodology

Both researcher agents follow the same methodology, differing only in scope (project-level vs phase-level):

| Aspect | gpd-project-researcher | gpd-phase-researcher |
|--------|----------------------|---------------------|
| Scope | Entire project domain | Single phase domain |
| Trigger | /gpd:new-project | /gpd:plan-phase or /gpd:research-phase |
| Output | .gpd/research/ (5 files) | ${phase_dir}/{phase}-RESEARCH.md |
| Consumer | gpd-roadmapper | gpd-planner |
| Commits | No (orchestrator commits) | No (orchestrator commits) |

### Shared Verification Protocol

Before submitting research output, both researchers verify:

- All research domains investigated (foundations, methods, landscape, pitfalls)
- Conventions identified and documented
- Regime of validity identified for every recommended method
- Key equations cited with sources (arXiv IDs or DOIs)
- Alternative approaches documented
- Computational feasibility assessed
- Validation strategies identified
- Confidence levels assigned honestly
- No-go theorems checked

### Tool Strategy and Confidence Levels

See `references/research/researcher-shared.md` for:
- Tool priority (arXiv > web_fetch > web_search > project search)
- arXiv search strategy
- Textbook and reference strategy
- Computational tool documentation approach
- Reference database usage (PDG, NIST, DLMF)
- Confidence level definitions (HIGH/MEDIUM/LOW)
- Cross-verification protocol
- Research pitfalls catalog
