---
template_version: 1
purpose: Supplemental bibliography registry template
total_references: 0
---

# Bibliography Template

Template for `.gpd/BIBLIOGRAPHY.md` -- optional reference and anchor ledger for projects that want a
human-readable registry alongside the live BibTeX files and the structured project contract.

**Status:** Not wired into the current GPD bibliography flow. The live bibliographer/paper pipeline
uses `references/references.bib`, `references/references-verified.log`, and
`references/references-pending.md`.

**Purpose:** Use this only if you explicitly want a parallel markdown registry of citations,
benchmarks, prior artifacts, and anchor status across the project. It is not the canonical source
of truth for paper generation or scoping; it mirrors those systems for human review.

**Relationship to other files:**

- `references/references.bib` is the BibTeX file maintained by the gpd-bibliographer agent
- `state.json.project_contract` is the authoritative machine-readable anchor registry
- Phase SUMMARY.md files may reference citations by BibTeX key; this file is optional supplemental tracking
- `CONVENTIONS.md` records which textbook conventions are followed; those textbooks should appear here
- `PARAMETERS.md` may cite data sources; those citations should appear here

---

## File Template

```markdown
# Project Reference and Anchor Ledger

## Anchor Ledger

| Anchor ID | Type | BibTeX Key | Title / Artifact | What It Supports | Carry Forward To | Source Surface | Verification |
|-----------|------|------------|------------------|------------------|------------------|----------------|--------------|
| [anchor-id] | [paper/dataset/prior_artifact/spec/user_anchor] | [key or n/a] | [title, DOI/arXiv, or artifact path] | [claim, observable, deliverable, or benchmark] | [planning/execution/verification/writing] | [PROJECT/CONTEXT/RESEARCH/SUMMARY] | [verified/pending/suspect] |

## Unresolved / Pending Anchors

- [Missing citation, benchmark, or prior artifact that still needs confirmation]
- [User-requested anchor that has not yet been sourced or verified]

## Verification Status

- Total references: [N]
- Verified by bibliographer: [M]
- Cited in paper draft: [K]
- Flagged issues: [list any SUSPECT or NOT FOUND references]

## Notes

- **Confidence tiers**: Contract-critical (must surface), supporting (used downstream), background (context only)
- **Verified**: Checked by gpd-bibliographer against INSPIRE/ADS/Google Scholar
- **BibTeX file**: `references/references.bib` (maintained by bibliographer)
```

<lifecycle>

**Creation:** During project initialization, after PROJECT.md

- Pre-populate with key references and prior artifacts from the project description and project contract
- Add textbook references matching conventions in CONVENTIONS.md
- Initialize all as unverified

**Appending:** After each phase that introduces new citations

- Extract citations and anchor references from phase RESEARCH.md, SUMMARY.md, and CONTEXT.md
- Record which phase or project surface introduced each reference or artifact
- Note whether the item must surface during planning, execution, verification, or writing
- Trigger bibliographer verification if available

**Reading:** By gpd-bibliographer agent

- Verify BibTeX keys against INSPIRE-HEP, ADS, arXiv, Google Scholar
- Detect hallucinated citations (keys that don't resolve)
- Warn about missing citations when equations from papers are used without attribution
- Maintain `references/references.bib` in correct journal format

**Reading:** By gpd-paper-writer agent

- Look up citations by BibTeX key for inline references
- Use the anchor ledger to see which references are contract-critical versus background
- Check that all cited results have verified references

**Reading:** By gpd-referee agent

- Verify that claimed comparisons with literature have corresponding entries
- Check that key methods and decisive benchmarks cite their original sources
- Flag any result that uses a technique without citing the methods reference

</lifecycle>

<guidelines>

**What belongs in BIBLIOGRAPHY.md:**

- Every reference cited in any phase artifact
- Textbooks and review articles that establish conventions
- Papers providing benchmark data for comparison
- Original sources for methods and algorithms used
- Prior artifacts or internal baselines that later phases must keep visible

**What does NOT belong here:**

- Full BibTeX entries (those go in `references/references.bib`)
- Detailed summaries of papers (those go in phase RESEARCH.md)
- Literature review analysis (that goes in literature review artifacts)

**When filling this template:**

- Use consistent BibTeX key format: `AuthorYYYY` for single author, `AuthorCoauthorYYYY` for two, `AuthorEtAlYYYY` for three or more
- Record DOI when available, arXiv ID as fallback, URL as last resort
- Record specifically what the anchor gives us and what downstream phase must keep using it
- For benchmark anchors, record whether agreement was found
- Keep entries sorted by Anchor ID or BibTeX key

**Why bibliography tracking matters:**

- Prevents hallucinated citations (a known LLM failure mode)
- Enables automatic BibTeX generation for paper drafts
- Tracks provenance: which results depend on which references
- Tracks which prior artifacts and benchmarks are mandatory rather than optional
- Supports reproducibility: exact references for every method and comparison
- Catches missing attributions before peer review

**Verification workflow:**

The gpd-bibliographer agent checks each entry:
1. Resolve BibTeX key against INSPIRE-HEP (for HEP papers), ADS (for astrophysics), or Google Scholar
2. Verify that title, authors, and year match
3. Flag entries that cannot be resolved as SUSPECT
4. Generate proper BibTeX and add to `references/references.bib`

</guidelines>
