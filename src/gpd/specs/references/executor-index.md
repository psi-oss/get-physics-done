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
| **Any derivation** | `shared-protocols.md` (conventions), `executor-verification-flows.md` (verification) |
| **QFT calculation** | `verification-domain-qft.md`, `protocols/perturbation-theory.md` or `protocols/renormalization-group.md` |
| **Condensed matter** | `verification-domain-condmat.md`, `executor-subfield-guide.md` §Condensed Matter |
| **Statistical mechanics / simulation** | `verification-domain-statmech.md`, `protocols/monte-carlo.md` or `protocols/molecular-dynamics.md` |
| **General relativity / cosmology** | `verification-domain-gr-cosmology.md`, plus `protocols/general-relativity.md`, `protocols/de-sitter-space.md`, or `protocols/cosmological-perturbation-theory.md` depending on regime |
| **AMO physics** | `verification-domain-amo.md`, `executor-subfield-guide.md` §AMO |
| **Nuclear / particle** | `verification-domain-nuclear-particle.md`, `executor-subfield-guide.md` §Nuclear |
| **Astrophysics** | `verification-domain-astrophysics.md`, `executor-subfield-guide.md` §Astrophysics |
| **Mathematical physics** | `verification-domain-mathematical-physics.md`, `executor-subfield-guide.md` §Mathematical Physics |
| **Numerical computation** | `protocols/numerical-computation.md`, `protocols/symbolic-to-numerical.md`, `verification-numerical.md` |
| **Paper writing** | `figure-generation-templates.md`, `bibtex-standards.md` |
| **Debugging / error recovery** | `execute-plan-recovery.md`, `executor-deviation-rules.md` |

## By Execution Phase

| Phase | Load These References |
|---|---|
| **Pre-execution setup** | `shared-protocols.md` §Convention Lock, `executor-subfield-guide.md` (subfield section) |
| **During execution** | `executor-verification-flows.md`, `executor-task-checkpoints.md` |
| **Deviation from plan** | `executor-deviation-rules.md` |
| **Checkpoint / save** | `execute-plan-checkpoints.md`, `checkpoints.md` |
| **Task completion** | `executor-completion.md`, `execute-plan-validation.md` |
| **Error recovery** | `execute-plan-recovery.md` |

## By Error Class Concern

| Concern | Load These References |
|---|---|
| **Convention mismatch suspected** | `conventions-quick-reference.md`, `shared-protocols.md` §Convention Tracking |
| **LLM error patterns** | `verification-gap-summary.md` (compact), `llm-errors-core.md` or relevant part file |
| **Numerical issues** | `verification-numerical.md`, `protocols/numerical-computation.md` |
| **Reproducibility** | `reproducibility.md` |

## Verification Domain Files

| Domain | File |
|---|---|
| QFT / particle / GR | `verification-domain-qft.md` |
| Condensed matter / QI / AMO | `verification-domain-condmat.md` |
| Statistical mechanics / cosmology / fluids | `verification-domain-statmech.md` |
| General relativity / cosmology | `verification-domain-gr-cosmology.md` |
| AMO physics | `verification-domain-amo.md` |
| Nuclear / particle physics | `verification-domain-nuclear-particle.md` |
| Astrophysics | `verification-domain-astrophysics.md` |
| Mathematical physics | `verification-domain-mathematical-physics.md` |

## Protocol Files

See `shared-protocols.md` §Detailed Protocol References for the full protocol index (41 protocols across 4 categories).
