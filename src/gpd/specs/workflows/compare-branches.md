<purpose>
Compare research results across hypothesis branches side-by-side. Builds a structured comparison table from STATE.md and SUMMARY files across all hypothesis/* branches, assessing key results, verification status, approximation validity, and context usage. Offers to merge the winning branch back to the parent and clean up.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="discover_branches">
**List all hypothesis branches:**

```bash
git branch --list 'hypothesis/*' --format='%(refname:short)'
```

**If no hypothesis branches found:**

```
ERROR: No hypothesis branches found.

Create hypothesis branches with /gpd:branch-hypothesis <description>
```

Exit.

**If exactly 1 hypothesis branch found:**

Single-branch mode: compare the one hypothesis branch against its parent branch as baseline. This allows evaluating a hypothesis without requiring a second alternative. Proceed to extract_branch_data with the hypothesis branch and its parent.

Record the current branch:

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
```

</step>

<step name="extract_branch_data">
**For each hypothesis branch, extract research state:**

```bash
git show {branch}:.gpd/STATE.md 2>/dev/null
git show {branch}:.gpd/hypotheses/{slug}/HYPOTHESIS.md 2>/dev/null
```

**If STATE.md is missing on a branch:** Mark the branch as "no state data" in the comparison table. This branch has no completed work to compare.

**If HYPOTHESIS.md is missing:** The branch was created manually without `/gpd:branch-hypothesis`. Use the branch name as the description and mark hypothesis metadata as "N/A".

For each branch, collect:

1. **Hypothesis description** -- from HYPOTHESIS.md `## Description`
2. **Status** -- from HYPOTHESIS.md `## Metadata` -> Status field
3. **Current phase** -- from STATE.md `## Current Position`
4. **Key results** -- scan for SUMMARY.md files in the branch:

```bash
git ls-tree -r --name-only {branch} -- .gpd/phases/ | grep SUMMARY.md
```

For each SUMMARY.md found:

```bash
git show {branch}:{summary_path} 2>/dev/null
```

Extract via `summary-extract --field one_liner --field key_results --field equations`: `one_liner` (body bold text or frontmatter), `key_results` (body section), `equations` (body section "Equations Derived").

5. **Verification status** -- scan for VERIFICATION.md files:

```bash
git ls-tree -r --name-only {branch} -- .gpd/phases/ | grep VERIFICATION.md
```

Extract `status` (passed/gaps_found/human_needed) from each.

6. **Commit count** -- number of commits unique to this branch:

```bash
git rev-list --count {branch} --not $(git merge-base {branch} {parent_branch})
```

</step>

<step name="include_parent">
**Also extract data from the parent branch** (usually `main` or the primary research branch):

Determine parent from the first hypothesis branch's HYPOTHESIS.md `## Metadata` -> `Parent branch` field. If HYPOTHESIS.md is missing on that branch, fall back to `main`.

Extract the same data (STATE.md, SUMMARYs, VERIFICATIONs) from the parent branch so it can be included in the comparison as the baseline.

**If no branch has any SUMMARY.md files:**

```
No completed plans found on any branch. Nothing to compare yet.

Complete at least one plan on each branch before comparing:
  /gpd:execute-phase <phase-number>
```

Exit.
</step>

<step name="build_comparison">
**Build the comparison table:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > BRANCH COMPARISON
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

## Overview

| Branch | Description | Phase | Plans Done | Verified |
|--------|-------------|-------|------------|----------|
| {parent} (baseline) | Original approach | {N} | {X}/{Y} | {status} |
| hypothesis/{slug-1} | {description} | {N} | {X}/{Y} | {status} |
| hypothesis/{slug-2} | {description} | {N} | {X}/{Y} | {status} |

## Key Results Comparison

### {Result Category} (e.g., "Energy Spectrum", "Transport Coefficients")

| Quantity | {parent} | hypothesis/{slug-1} | hypothesis/{slug-2} |
|----------|----------|---------------------|---------------------|
| {quantity-1} | {value} | {value} | {value} |
| {quantity-2} | {value} | {value} | {value} |

### Equations

| Branch | Key Equations |
|--------|---------------|
| {parent} | {eq list} |
| hypothesis/{slug-1} | {eq list} |
| hypothesis/{slug-2} | {eq list} |

## Verification Summary

| Branch | Checks Passed | Warnings | Failures | Overall |
|--------|---------------|----------|----------|---------|
| {parent} | {N} | {N} | {N} | {status symbol} |
| hypothesis/{slug-1} | {N} | {N} | {N} | {status symbol} |
| hypothesis/{slug-2} | {N} | {N} | {N} | {status symbol} |
```

</step>

<step name="numerical_comparison">
**Computational comparison of numerical results across branches:**

When branches produce numerical results (extracted from `key_results` in SUMMARY.md frontmatter), compute quantitative differences:

**1. Extract numerical values from each branch:**

For each branch, scan all SUMMARY.md `key_results` entries for values with numbers (e.g., `E_0 = -1.234 +/- 0.005`, `T_c/J = 2.269`):

Prefer parsing the `git show` output directly in memory. The branch SUMMARY content is already available from `git show`, so do not write it to `.gpd/tmp/` just to run a path-based extractor.

If the structure is ambiguous, re-run `git show {branch}:{summary_path} 2>/dev/null` and inspect the frontmatter plus the `## Key Results` and `## Equations Derived` sections directly. Keep branch-summary extraction in memory/stdout only; do not use `.gpd/tmp/`, `/tmp`, or another temp root for this step.

Parse each entry for: quantity name, numerical value, uncertainty (if present), units.

**2. Match quantities across branches:**

Identify quantities that appear in two or more branches (by matching quantity names or equation labels). Build a matched-pairs table.

**3. Compute relative differences:**

For each matched quantity pair between branches A and B:

```
relative_diff = |value_A - value_B| / max(|value_A|, |value_B|)
```

If both values have uncertainties (sigma_A, sigma_B):

```
combined_sigma = sqrt(sigma_A^2 + sigma_B^2)
tension = |value_A - value_B| / combined_sigma
```

**4. Flag statistically significant disagreements:**

| Threshold | Interpretation | Display |
|-----------|---------------|---------|
| tension < 1 sigma | Consistent | (no flag) |
| 1 sigma <= tension < 2 sigma | Mild tension | (!) |
| 2 sigma <= tension < 3 sigma | Significant tension | (!!) |
| tension >= 3 sigma | Strong disagreement | (!!!) |

For values without uncertainties, use relative difference thresholds:
- < 1%: consistent
- 1-5%: mild difference (!)
- 5-10%: notable difference (!!)
- > 10%: large difference (!!!)

**5. Present numerical comparison table:**

```
## Numerical Comparison

| Quantity | {parent} | hypothesis/{slug} | Rel. Diff | Tension | Flag |
|----------|----------|-------------------|-----------|---------|------|
| E_0      | -1.234(5) | -1.237(4) | 0.24% | 0.47σ | — |
| T_c/J    | 2.269(3) | 2.315(8) | 2.0% | 5.4σ | !!! |

{If any flags:}
### Significant Disagreements

**T_c/J:** 5.4σ tension between branches. The hypothesis branch predicts a higher
critical temperature. This {agrees with / contradicts} the hypothesis expectation
that {reference HYPOTHESIS.md expected outcome}.
```

**6. If no numerical results found in any branch:** Skip this step silently (branches may contain purely analytical results).

</step>

<step name="assessment">
**Build qualitative assessment:**

```
## Assessment

{For each branch: 2-3 sentences on strengths/weaknesses relative to others.
Consider: accuracy, approximation validity, computational cost, generalizability, verification completeness.
If numerical comparison was performed, reference significant agreements and disagreements.}

**Recommendation:** {Which branch appears most promising, with reasoning.
If inconclusive, say so and suggest what additional work would distinguish them.}
```

</step>

<step name="offer_merge">
**Offer to merge the winning branch:**

```
───────────────────────────────────────────────────────────────

## Actions

1. **Merge a branch** -- merge hypothesis results back to parent
2. **Delete a branch** -- clean up an abandoned hypothesis
3. **Continue working** -- return to current branch
4. **Export comparison** -- write this comparison to .gpd/BRANCH-COMPARISON.md

Which action? (1/2/3/4)

───────────────────────────────────────────────────────────────
```

**If merge selected:**

1. Ask which branch to merge
2. Confirm the merge target (parent branch)
3. Switch to parent branch:

```bash
git checkout {parent_branch}
```

4. Merge the hypothesis branch:

```bash
git merge hypothesis/{slug} --no-ff -m "merge: incorporate hypothesis/{slug} results"
```

5. If merge conflicts:

```
╔══════════════════════════════════════════════════════════════╗
║  CHECKPOINT: Decision Required                               ║
╚══════════════════════════════════════════════════════════════╝

Merge conflicts detected in:
{list of conflicted files}

──────────────────────────────────────────────────────────────
→ Resolve conflicts manually, then type "done"
──────────────────────────────────────────────────────────────
```

6. After successful merge, offer to delete the merged branch:

```bash
git branch -d hypothesis/{slug}
```

**If delete selected:**

1. Ask which branch to delete
2. Confirm deletion (warn about data loss if unmerged)
3. Execute: `git branch -D hypothesis/{slug}` (if confirmed)

**If export selected:**

Write the comparison output to `.gpd/BRANCH-COMPARISON.md`.

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/BRANCH-COMPARISON.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: export branch comparison" --files .gpd/BRANCH-COMPARISON.md
```

</step>

<step name="restore_branch">
**Return to original branch:**

```bash
git checkout {CURRENT_BRANCH}
```

Present completion:

```
───────────────────────────────────────────────────────────────

**Also available:**
- `/gpd:branch-hypothesis <desc>` -- create another hypothesis branch
- `/gpd:progress` -- check overall research progress
- List branches: `git branch --list 'hypothesis/*'`

───────────────────────────────────────────────────────────────
```

</step>

</process>

<anti_patterns>

- Don't compare branches with no completed plans -- there's nothing to compare
- Don't auto-merge without user confirmation
- Don't delete branches without checking if they have unmerged results
- Don't leave the user on a different branch than where they started
- Don't force-push or rebase hypothesis branches
- Don't compare only commit counts -- focus on physics results and verification status
  </anti_patterns>

<success_criteria>
Branch comparison is complete when:

- [ ] All hypothesis branches discovered and listed
- [ ] Parent branch identified and included as baseline
- [ ] STATE.md and SUMMARY data extracted from each branch
- [ ] Verification status collected from each branch
- [ ] Structured comparison table presented
- [ ] Numerical comparison computed for shared quantities (if both branches have numerical results)
- [ ] Statistically significant disagreements flagged with tension values
- [ ] Assessment with recommendation provided
- [ ] Action offered (merge/delete/continue/export)
- [ ] User returned to original branch

</success_criteria>
