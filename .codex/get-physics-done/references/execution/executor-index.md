---
load_when:
  - "which reference to load"
  - "executor needs guidance"
  - "execution scenario"
tier: 1
context_cost: small
---

# Executor Reference Index

Maps execution scenarios to the correct reference file. Load this at execution start, then load the specific reference(s) needed for the current task.

## By Execution Scenario

| Scenario | Load These References |
|---|---|
| **Any derivation** | `references/shared/shared-protocols.md` (conventions), `references/execution/executor-verification-flows.md` (verification) |
| **QFT calculation** | `references/verification/domains/verification-domain-qft.md`, plus `references/protocols/perturbation-theory.md`, `references/protocols/renormalization-group.md`, `references/protocols/supersymmetry.md`, `references/protocols/asymptotic-symmetries.md`, `references/protocols/generalized-symmetries.md`, or `references/protocols/conformal-bootstrap.md` when fixed-point CFT data or crossing constraints are central |
| **Condensed matter** | `references/verification/domains/verification-domain-condmat.md`, `references/execution/executor-subfield-guide.md` §Condensed Matter |
| **Statistical mechanics / simulation** | `references/verification/domains/verification-domain-statmech.md`, `references/protocols/monte-carlo.md` or `references/protocols/molecular-dynamics.md`; add `references/protocols/conformal-bootstrap.md` when the target is critical exponents, universality class data, or the critical-point CFT |
| **General relativity / cosmology** | `references/verification/domains/verification-domain-gr-cosmology.md`, plus `references/protocols/general-relativity.md`, `references/protocols/de-sitter-space.md`, `references/protocols/asymptotic-symmetries.md`, or `references/protocols/cosmological-perturbation-theory.md` depending on regime |
| **Quantum gravity / holography** | `references/subfields/quantum-gravity.md`, plus `references/verification/domains/verification-domain-gr-cosmology.md`, `references/verification/domains/verification-domain-qft.md`, and `references/protocols/holography-ads-cft.md`, `references/protocols/de-sitter-space.md`, or `references/protocols/asymptotic-symmetries.md` depending on asymptotics |
| **String theory / compactification** | `references/subfields/string-theory.md`, plus `references/verification/domains/verification-domain-qft.md`, `references/verification/domains/verification-domain-mathematical-physics.md`, and `references/protocols/supersymmetry.md`, `references/protocols/holography-ads-cft.md`, `references/protocols/de-sitter-space.md`, or `references/protocols/path-integrals.md` depending on regime |
| **AMO physics** | `references/verification/domains/verification-domain-amo.md`, `references/execution/executor-subfield-guide.md` §AMO |
| **Nuclear / particle** | `references/verification/domains/verification-domain-nuclear-particle.md`, `references/protocols/phenomenology.md`, and `references/execution/executor-subfield-guide.md` §Nuclear & Particle Physics |
| **Astrophysics** | `references/verification/domains/verification-domain-astrophysics.md`, `references/execution/executor-subfield-guide.md` §Astrophysics |
| **Mathematical physics** | `references/verification/domains/verification-domain-mathematical-physics.md`, `references/execution/executor-subfield-guide.md` §Mathematical Physics, plus `references/protocols/conformal-bootstrap.md` or `references/protocols/holography-ads-cft.md` for CFT-heavy problems |
| **Algebraic QFT / operator algebras** | `references/subfields/algebraic-qft.md`, `references/verification/domains/verification-domain-algebraic-qft.md`, `references/protocols/algebraic-qft.md`, and `references/execution/executor-subfield-guide.md` §Algebraic Quantum Field Theory |
| **String field theory** | `references/subfields/string-field-theory.md`, `references/verification/domains/verification-domain-string-field-theory.md`, `references/protocols/string-field-theory.md`, and `references/execution/executor-subfield-guide.md` §String Field Theory; add `references/subfields/string-theory.md` when worldsheet, D-brane, or compactification input is part of the setup |
| **Conformal bootstrap / CFT** | `references/verification/domains/verification-domain-mathematical-physics.md`, `references/protocols/conformal-bootstrap.md`, and `references/subfields/qft.md` or `references/subfields/mathematical-physics.md` depending on whether the project is field-theoretic or structural |
| **Numerical computation** | `references/protocols/numerical-computation.md`, `references/protocols/symbolic-to-numerical.md`, `references/verification/core/verification-numerical.md` |
| **Paper writing** | `references/publication/figure-generation-templates.md`, `references/publication/bibtex-standards.md` |
| **Debugging / error recovery** | `references/execution/execute-plan-recovery.md`, `references/execution/executor-deviation-rules.md` |

## By Execution Phase

| Phase | Load These References |
|---|---|
| **Pre-execution setup** | `references/shared/shared-protocols.md` §Convention Lock, `references/execution/executor-subfield-guide.md` (subfield section) |
| **During execution** | `references/execution/executor-verification-flows.md`, `references/execution/executor-task-checkpoints.md` |
| **Deviation from plan** | `references/execution/executor-deviation-rules.md` |
| **Checkpoint / save** | `references/execution/execute-plan-checkpoints.md`, `references/orchestration/checkpoints.md` |
| **Task completion** | `references/execution/executor-completion.md`, `references/execution/execute-plan-validation.md` |
| **Error recovery** | `references/execution/execute-plan-recovery.md` |

## By Error Class Concern

| Concern | Load These References |
|---|---|
| **Convention mismatch suspected** | `references/conventions/conventions-quick-reference.md`, `references/shared/shared-protocols.md` §Convention Tracking |
| **LLM error patterns** | `references/verification/audits/verification-gap-summary.md` (compact), `references/verification/errors/llm-errors-core.md` or relevant part file |
| **Numerical issues** | `references/verification/core/verification-numerical.md`, `references/protocols/numerical-computation.md` |
| **Reproducibility** | `references/protocols/reproducibility.md` |

## Verification Domain Files

| Domain | File |
|---|---|
| QFT / particle / GR | `references/verification/domains/verification-domain-qft.md` |
| Condensed matter | `references/verification/domains/verification-domain-condmat.md` |
| Quantum info | `references/verification/domains/verification-domain-quantum-info.md` |
| AMO | `references/verification/domains/verification-domain-amo.md` |
| Soft matter | `references/verification/domains/verification-domain-soft-matter.md` |
| Fluid / plasma | `references/verification/domains/verification-domain-fluid-plasma.md` |
| Statistical mechanics / cosmology / fluids | `references/verification/domains/verification-domain-statmech.md` |
| General relativity / cosmology | `references/verification/domains/verification-domain-gr-cosmology.md` |
| Quantum gravity / holography | `references/verification/domains/verification-domain-gr-cosmology.md` + `references/verification/domains/verification-domain-qft.md` |
| String theory / compactification | `references/verification/domains/verification-domain-qft.md` + `references/verification/domains/verification-domain-mathematical-physics.md` + `references/verification/domains/verification-domain-gr-cosmology.md` |
| AMO physics | `references/verification/domains/verification-domain-amo.md` |
| Nuclear / particle physics | `references/verification/domains/verification-domain-nuclear-particle.md` |
| Astrophysics | `references/verification/domains/verification-domain-astrophysics.md` |
| Mathematical physics | `references/verification/domains/verification-domain-mathematical-physics.md` |
| Algebraic QFT / operator algebras | `references/verification/domains/verification-domain-algebraic-qft.md` |
| String field theory | `references/verification/domains/verification-domain-string-field-theory.md` |

## Protocol Files

See `references/shared/shared-protocols.md` §Detailed Protocol References for the full protocol index.
