---
load_when:
  - "verification gap analysis"
  - "error class coverage"
  - "defense layer audit"
tier: 2
context_cost: medium
---

# Verification Coverage and Gap Analysis

Current runtime-facing overview of how GPD defends against physics errors today.

This file is intentionally evergreen. Dated point-in-time audits belong outside the shipped runtime reference bundle.

## Use This File For

- understanding the current defense layers
- locating the live executable source of truth
- deciding when to load the compact priority summary versus deeper references
- identifying the main categories of gaps that still need human judgment or domain-specific protocols
- understanding which parts of verification are conditional, advisory, or disabled by config

## Current Source of Truth

- `gpd.core.verification_checks` — live machine-readable verification registry
- `gpd-verification` MCP server — machine-facing verification metadata surface
- `../errors/llm-physics-errors.md` — current 104-class error catalog
- `../meta/verifier-profile-checks.md` — domain-specific verifier checklists
- `gpd-executor.md` `<post_step_physics_guards>` — early-intercept guardrails and the 52-type computation mini-checklist

If this file disagrees with the executable registry, the registry wins.

The machine-readable `ERROR_CLASS_COVERAGE` currently maps a focused subset of 20 error classes. `verification-gap-summary.md` extends current prioritization beyond that subset using executor guards, traceability docs, and domain-specific protocols.

## Defense Layers Today

| Layer | Current surface | Role today | Important limit |
|---|---|---|---|
| L0 | Plan-checker 16 dimensions | Catches bad plans before execution starts | Structural only; does not prove results are correct |
| L1 | Convention lock + convention assertions | Prevents convention drift and runtime mismatch | Only catches convention-trackable failures |
| L2 | Executor post-step guards | Catches setup, identity, BC, computation-type, and domain-level mistakes early | Best-effort; still not a substitute for verifier evidence |
| L3 | Pre-commit check | Blocks malformed frontmatter, NaN/Inf markers, and missing/mismatched ASSERT_CONVENTION coverage on changed derivation and phase verification artifacts | Still changed-file structural gating only; not a physics verifier |
| L4 | Inter-wave gates | Phase-class-aware between-wave checks such as convention, dimensional, identity, convergence, plausibility, and LaTeX compile checks | Selected by review cadence and phase class; still not a full verification pass |
| L5 | Live verifier registry | Main within-phase result verification surface | Must still be scoped correctly to the phase and contract; execute-phase skips it entirely when `workflow.verifier` is false |
| L6 | Consistency checker | Cross-phase convention and dependency consistency | Limited to things visible across phase boundaries |
| Human loop | `verify-work` researcher validation | Adds interactive researcher judgment on top of machine checks | Optional; depends on user invocation |

## Live Verifier Model

The current verifier model is:

- **14 universal checks (`5.1`-`5.14`)** covering dimensional analysis, numerical spot-checks, limiting cases, conservation laws, convergence, literature cross-checks, order-of-magnitude, plausibility, Ward identities / sum rules, unitarity, causality, positivity, Kramers-Kronig consistency, and statistical validation.
- **5 contract-aware checks (`5.15`-`5.19`)** covering limit recovery, benchmark reproduction, direct-vs-proxy consistency, fit-family mismatch, and estimator-family mismatch.

In practical terms:

- The universal checks are the reusable physics floor.
- The contract-aware checks are what stop GPD from treating proxies, wrong fit families, or benchmark drift as success.
- Domain-specific anomaly/topology and formulation traps still rely on protocol bundles and verifier profile checklists, not only on a single registry id.

## What Still Requires Extra Care

### 1. Domain-specific traps can outstrip generic checks

Some failure modes are only partially visible to universal checks. Examples include:

- anomaly and topology mistakes
- subtle formulation mismatches in QFT, relativity, and condensed matter
- regime-selection errors where the model family is wrong before the algebra starts

Treat `verifier-profile-checks.md`, protocol bundles, and literature anchors as required, not optional add-ons.

### 2. Early guardrails are intentionally lightweight

Pre-commit checks and inter-wave gates are valuable, but they are smoke detectors:

- they catch malformed artifacts and obvious bad states
- they do **not** replace full within-phase verification
- they should never be cited as publication-grade evidence by themselves

### 3. Cross-phase uncertainty propagation is still incomplete

The `verify-work` workflow includes an explicit cross-phase uncertainty audit, including inherited-quantity checks and catastrophic-cancellation detection. Even so, uncertainty chaining across phases is still not a first-class verification object in the machine-readable core, so this remains a real gap for long research programs.

### 4. Exploratory and quick flows still need explicit skepticism

Exploration may compress optional depth, but it must not waive:

- decisive benchmark or anchor checks
- forbidden-proxy checks
- direct-vs-proxy consistency
- formulation-critical checks required by the phase semantics

Quick workflows remain intentionally narrow and are not publication-grade verification.

In `verify-work`, `autonomy=yolo` may skip optional cross-checks and literature comparison, but it must still preserve contract-critical anchors and decisive benchmarks.

### 5. Verification can be disabled

When `workflow.verifier` is false in config, `execute-phase` skips phase verification entirely. The defense layers above therefore describe the live verification stack when verification is enabled, not an unconditional guarantee that every phase was verified.

### 6. Computational evidence is mandatory

Every `VERIFICATION.md` must still contain at least one executed code block with actual output. Audit summaries and priority lists help decide what to check first; they do not replace the Level 5 external-oracle requirement.

## Recommended Loading Order

1. `../core/verification-quick-reference.md` for the conceptual checklist
2. `verification-gap-summary.md` for current prioritization
3. `../errors/llm-physics-errors.md` or the relevant part file for class-level detail
4. `../meta/verifier-profile-checks.md` plus the relevant domain references for phase-specific depth
5. this file when you need the current coverage architecture rather than a single checklist

## Historical Audits

Historical dated audits are intentionally kept outside the shipped runtime references. They are useful for maintainers, but they should not be treated as the current system description.

## See Also

- `verification-gap-summary.md` — compact current priority list
- `../errors/llm-physics-errors.md` — full 104-class error catalog
- `../errors/llm-errors-traceability.md` — quick traceability index into the error catalog
- `../meta/verification-hierarchy-mapping.md` — current plan-checker / verifier / consistency-checker mapping
- `../core/verification-core.md` — universal verification procedures
- `../../shared/shared-protocols.md` — convention tracking and shared verification protocols
