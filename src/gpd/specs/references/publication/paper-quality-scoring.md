# Paper Quality Scoring System

Quantitative readiness score (0-100) for physics manuscripts. Used by `/gpd:write-paper` to determine if the paper is ready for submission packaging. Each category is scored independently; the total is a weighted sum.

This is **not** the final referee-decision policy. A manuscript can score well on packaging/readiness and still deserve `major_revision` or `reject` if its novelty, significance, venue fit, or claim-evidence proportionality are weak. Those publication-judgment gates belong to the staged peer-review policy and `validate referee-decision`.

## Scoring Categories

### 1. Equations (20 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| All displayed equations have `\label{}` | 4 | Use `search_files` for unlabeled `\begin{equation}` |
| All symbols defined at first use | 4 | Read each equation, check preceding text |
| Dimensional consistency verified | 6 | Dimensional analysis trace in VERIFICATION.md |
| All limiting cases checked and documented | 6 | Count verified limits vs total key results |

**Scoring:** Full points if ALL checks pass. Half points if >80% pass. Zero if <50%.

### 2. Figures (15 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| Decisive figures/tables labeled with units | 3 | Read `.gpd/paper/FIGURE_TRACKER.md` `figure_registry` and verify `has_units: true` for decisive artifacts |
| Decisive figures/tables carry uncertainty bands or error bars | 4 | Use the tracker `has_uncertainty` field for decisive artifacts |
| Decisive figures/tables referenced in text and role is clear | 4 | Use the tracker `referenced_in_text` field and verify the `role` is not `other` |
| Captions are self-contained (understandable without reading text) | 3 | Read each caption in isolation |
| Colorblind-safe palette used | 1 | Check against viridis/Wong palette |

### 3. Citations (10 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| All `\cite{}` keys resolve in .bib file | 3 | Compile check — no undefined citations |
| No `MISSING:` placeholder citations remain | 3 | Use `search_files` for `MISSING:` in .tex files |
| Key prior work cited (not just self-citations) | 2 | Check introduction references breadth |
| No hallucinated citations (bibliographer verified) | 2 | `BIBLIOGRAPHY-AUDIT.json` clean or passing status |

### 4. Conventions (15 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| Convention lock complete (all relevant fields set) | 5 | `gpd convention check` returns complete: true |
| ASSERT_CONVENTION in all derivation files | 5 | Search derivation files for `ASSERT_CONVENTION:` and compare against the convention lock; `gpd pre-commit-check` does not currently validate these assertions |
| Notation consistent across all sections | 5 | Same symbol = same meaning throughout |

### 5. Verification (20 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| VERIFICATION.md exists with status: passed | 5 | File exists and frontmatter status = passed |
| All contract-defined targets verified (score = N/N) | 5 | Aggregate phase `SUMMARY.md` / `VERIFICATION.md` `contract_results` by contract ID |
| Key results have INDEPENDENTLY CONFIRMED confidence | 5 | Count independently confirmed vs total |
| No UNRELIABLE confidence ratings on any result | 5 | Use `search_files` on VERIFICATION.md for "UNRELIABLE" |

### 6. Completeness (10 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| Abstract written LAST (matches actual results) | 2 | Abstract mentions key numerical values from results |
| All sections present for target journal | 3 | Compare section structure against journal template |
| No TODO/FIXME/PENDING placeholders remain | 3 | Use `search_files` in .tex files for placeholders |
| Supplemental material cross-referenced | 2 | Check SM section numbers match main text pointers |

### 7. Results Presentation (10 points)

| Check | Points | How to verify |
|-------|--------|---------------|
| Key numerical results include uncertainties | 4 | Every number in results section has ± or error bar |
| Decisive outputs have explicit comparison verdicts and anchors | 3 | `comparison_verdicts` exist for decisive results and cite the right anchors; decisive figures should link back to `.gpd/comparisons/*-COMPARISON.md` when relevant |
| Physical interpretation provided (not just math) | 3 | Discussion section explains meaning of results |

## Total Score Interpretation

| Score | Status | Action |
|-------|--------|--------|
| **90-100** | Publication ready | Submit to target journal |
| **80-89** | Nearly ready | Fix specific deficiencies, then submit |
| **70-79** | Needs work | Address all items scoring 0; re-score after fixes |
| **60-69** | Significant gaps | Multiple categories need attention; plan revision phase |
| **<60** | Not ready | Major work remaining; return to research/verification phases |

## Automated Scoring Protocol

When invoked during `/gpd:write-paper` (step: quality_assessment), prefer the artifact-driven path:

```bash
gpd --raw validate paper-quality --from-project .
```

This path derives the machine-readable `PaperQualityInput` from the manuscript, bibliography audit, figure tracker, comparison artifacts, and contract-backed summary / verification ledgers before scoring it.

If you need to provide a manual JSON instead, use `@{GPD_INSTALL_DIR}/templates/paper/paper-quality-input-schema.md` as the schema source of truth.

The artifact-driven path is intentionally conservative: it can infer many figure, citation, verification, completeness, and comparison checks, but equation and convention evidence may still need explicit manual review. Do not paper over missing evidence by inventing perfect scores.

## Integration Points

- **`/gpd:write-paper`**: Runs quality scoring after all sections drafted, before generating submission package
- **`/gpd:arxiv-submission`**: Requires score ≥ 80 to proceed (override with `--force`)
- **`/gpd:respond-to-referees`**: Re-scores after revision to track improvement
- **VERIFICATION.md**: Quality score recorded in paper section of verification report

## Confidence-to-Score Mapping

Results with different verification confidence levels contribute differently to the score:

| Verification Confidence | Contribution to Score |
|------------------------|----------------------|
| INDEPENDENTLY CONFIRMED | Full points |
| STRUCTURALLY PRESENT | 60% of points |
| UNABLE TO VERIFY | 20% of points |
| UNRELIABLE | 0 points (and flags a blocker) |

## Journal-Specific Score Adjustments

Different journals emphasize different quality dimensions. Apply these multipliers to the base score:

### PRL (Broad Significance Required)

- Results Presentation: **1.5x** (key result must be immediately compelling)
- Completeness: **1.3x** (every word counts in 4 pages)
- Conventions: **0.7x** (less emphasis — short paper, fewer equations)
- **Extra check (+5 points):** Does the abstract convey significance to non-specialists?
- **Minimum for submission:** 85

### PRD/PRB/PRC (Thorough Technical Paper)

- Equations: **1.2x** (full derivation expected — more equations to check)
- Verification: **1.3x** (complete error analysis required)
- Figures: **1.0x** (standard)
- **Extra check (+5 points):** Are convergence studies shown with at least 3 data points?
- **Minimum for submission:** 75

### JHEP (Theoretical Rigor)

- Equations: **1.4x** (every derivation step must be shown or referenced)
- Conventions: **1.5x** (metric, gamma matrices, dim-reg scheme MUST be stated in Section 2)
- Citations: **1.2x** (complete reference to related calculations expected)
- **Extra check (+5 points):** Are all Feynman diagrams listed at the relevant loop order?
- **Minimum for submission:** 80

### Nature Physics (Accessibility + Impact)

- Results Presentation: **1.5x** (physical interpretation is paramount)
- Completeness: **1.3x** (Methods section must be self-contained)
- Equations: **0.5x** (fewer equations; clarity over rigor)
- **Extra check (+5 points):** Can a physicist outside the subfield understand the abstract?
- **Minimum for submission:** 90

### ApJ (Observational Connection)

- Results Presentation: **1.3x** (comparison with observational data critical)
- Citations: **1.2x** (software citations REQUIRED)
- Figures: **1.3x** (data visualization is central to astro papers)
- **Extra check (+3 points):** Is a `\software{}` statement present?
- **Minimum for submission:** 75

## Scoring Summary Report Template

Present to the researcher after scoring:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PAPER QUALITY SCORE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Title:** {paper title}
**Target:** {journal}
**Score:** {total}/100 → {status}

| Category | Score | Max | Status |
|----------|-------|-----|--------|
| Equations | {X} | 20 | {pass/fix} |
| Figures | {X} | 15 | {pass/fix} |
| Citations | {X} | 10 | {pass/fix} |
| Conventions | {X} | 15 | {pass/fix} |
| Verification | {X} | 20 | {pass/fix} |
| Completeness | {X} | 10 | {pass/fix} |
| Results | {X} | 10 | {pass/fix} |

### Items to Fix (Priority Order)

{For each category scoring < max:}
1. **{category}** ({current}/{max}): {specific items to fix}

### Journal Adjustment

{If journal-specific multipliers applied:}
Adjusted score for {journal}: {adjusted}/100
Minimum for submission: {min}
{READY / NOT READY}

───────────────────────────────────────────────────────
```
