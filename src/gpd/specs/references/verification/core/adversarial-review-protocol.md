---
load_when:
  - "parallel review"
  - "adversarial review"
  - "divergence detection"
  - "cross-agent verification"
  - "review reliability"
tier: 2
context_cost: medium
---

# Adversarial Review Protocol — Cross-Agent Verification for Physics Manuscripts

This protocol defines how parallel adversarial review operates to catch errors that single-pass or single-agent reviews systematically miss. It is designed to address the fundamental problem of LLM self-consistency bias in physics manuscript review.

## The Problem: Self-Consistency Bias

A single AI agent reviewing a manuscript tends to produce internally consistent assessments that may nonetheless be wrong. This happens because:

1. **Narrative coherence trap:** A well-written manuscript creates a compelling narrative. A single reviewer following that narrative will evaluate claims within the manuscript's own logical frame, missing external contradictions.
2. **Derivation-path dependence:** When a reviewer checks a derivation by following the same path the author used, any systematic error in the path is invisible. The check confirms the derivation is self-consistent, not that it is correct.
3. **Shared blind spots:** Sequential review stages within a single pipeline share implicit context. If Stage 1 misidentifies the paper's main claim, all subsequent stages evaluate the wrong thing without noticing.
4. **Charitable interpretation default:** LLMs default to interpreting ambiguous statements charitably. In review, this means physically questionable claims get the benefit of the doubt unless an adversarial pressure exists.

## Protocol Architecture

### Parallel Execution Model

```
                    +-----------------------+
                    |  Manuscript + Artifacts|
                    +-----------+-----------+
                                |
                    +-----------+-----------+
                    |                       |
          +---------v--------+    +---------v--------+
          | PRIMARY PANEL    |    | PARALLEL REVIEWER |
          | (6-stage review) |    | (independent)     |
          +--------+---------+    +---------+---------+
                   |                        |
                   v                        v
          Stage artifacts           Independent checks
          (STAGE-*.json)           (PARALLEL-REVIEW.json)
                   |                        |
                   +----------+-------------+
                              |
                    +---------v---------+
                    | DIVERGENCE ANALYSIS|
                    | (cross-comparison) |
                    +---------+---------+
                              |
                    +---------v---------+
                    | REFEREE            |
                    | (reconciliation)   |
                    +-------------------+
```

The parallel reviewer runs concurrently with Stages 1-5 of the primary panel. It reads only the manuscript and its direct support files — it does not read primary panel artifacts until the divergence analysis phase.

### Information Barriers

To prevent the parallel reviewer from converging on the same conclusions as the primary panel through shared context:

1. **No shared transcripts:** The parallel reviewer does not see the primary panel's prompts or responses.
2. **No intermediate artifacts:** The parallel reviewer does not read `STAGE-*.json` files until Phase 2 (divergence analysis).
3. **Different analytical strategy:** The parallel reviewer uses alternative derivation paths, not the manuscript's own path.
4. **Independent claim extraction:** The parallel reviewer identifies claims independently before comparing with the primary panel's `CLAIMS.json`.

### Verification Strategies

The parallel reviewer must use at least three of these independent verification strategies for each central claim:

#### 1. Alternative Derivation Path
Re-derive the key result through a different method than the manuscript uses. If the manuscript uses path-integral methods, try operator methods. If it uses perturbation theory, check a known exact limit.

#### 2. Numerical Spot-Check
Evaluate the key equations numerically at specific parameter values and compare with known results, limiting cases, or independent numerical computation.

#### 3. Dimensional and Scaling Analysis
Verify that the result has correct dimensions and scaling behavior in all relevant limits (weak coupling, strong coupling, large-N, continuum limit, etc.).

#### 4. Assumption Boundary Probing
Take each major assumption to its boundary of validity. Does the result degrade gracefully or catastrophically? Does the manuscript honestly scope its validity regime?

#### 5. Counter-Narrative Construction
Construct the strongest possible argument against the paper's main claim. This forces the reviewer to engage with potential failure modes rather than confirming the manuscript's story.

#### 6. Error Catalog Cross-Reference
Systematically check for the most common LLM physics error classes (see `references/verification/errors/llm-errors-core.md`) that are relevant to the manuscript's subfield.

## Divergence Classification

When the parallel reviewer's findings diverge from the primary panel's findings, classify each divergence:

### Material Divergences (must be reconciled before final recommendation)

- **Support status disagreement:** Panel says "supported," parallel says "unsupported" or "partially_supported" for a central claim.
- **Recommendation ceiling gap >= 2 levels:** Panel ceiling is "accept" but parallel ceiling is "major_revision" or "reject."
- **Missed error class:** Parallel reviewer identifies a cataloged LLM error class that the panel did not catch.
- **Assumption validity disagreement:** Panel accepts a regime of validity that the parallel reviewer's stress test shows is narrower than claimed.

### Minor Divergences (documented but not blocking)

- **Severity disagreement within one level:** Panel says "major," parallel says "minor" for the same finding.
- **Recommendation ceiling gap == 1 level:** Panel ceiling is "minor_revision" but parallel ceiling is "major_revision."
- **Additional minor findings:** Parallel reviewer found minor issues the panel missed, but none affect the central claim.

## Reconciliation Protocol

When material divergences exist, the referee (Stage 6) must:

1. **Read both the primary panel artifacts and the divergence report** before issuing a final recommendation.
2. **For each material divergence**, determine which position is better supported:
   - If the parallel reviewer provides specific evidence (numerical check, alternative derivation, etc.) and the panel does not, favor the parallel reviewer's position.
   - If both provide evidence, the referee must evaluate the evidence quality and explain the resolution.
   - If neither provides strong evidence, the divergence should be flagged as an unresolved concern requiring author response.
3. **Document the reconciliation** in the `REFEREE-DECISION{round_suffix}.json` under a `parallel_review_reconciliation` field.
4. **Adjust the recommendation** if reconciliation changes the severity of any blocking finding.

## When to Use Parallel Review

Parallel review adds cost (an additional agent pass) and is not needed for every manuscript. Use it when:

- **High-stakes submission:** The target venue is a top journal (PRL, JHEP, Nature Physics) where missed errors are costly.
- **Novel methodology:** The manuscript uses a novel approach that the primary panel may not have deep expertise to verify.
- **Self-generated work:** The manuscript was written or significantly aided by GPD itself, creating a self-review risk.
- **Prior review disagreement:** A previous review round had significant disagreement between stages, suggesting the manuscript is at the boundary of acceptability.
- **User request:** The user explicitly requests adversarial review for additional confidence.

## Quality Metrics

A parallel review pass is considered effective if:

1. It identifies at least one finding that the primary panel did not, regardless of severity.
2. The divergence report contains at least one material divergence, OR the agreement summary provides specific evidence for convergence (not just "we agree").
3. The counter-narrative is substantive — it engages with the actual physics, not generic objections.
4. The recommendation ceiling is justified by specific independent checks, not inherited from the primary panel.

A parallel review pass has failed if:

1. It simply restates the primary panel's findings in different words.
2. The "independent" checks follow the same derivation path as the manuscript.
3. The counter-narrative is a generic objection that could apply to any paper in the subfield.
4. It agrees with the primary panel on everything without providing independent evidence for that agreement.
