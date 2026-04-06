---
template_version: 2
purpose: Supplemental bibliography registry template backed by persistent database
total_references: 0
---

# Bibliography Template

Template for `GPD/BIBLIOGRAPHY.md` -- human-readable registry of citations, benchmarks, prior
artifacts, and anchor status across the project.

**Status:** Integrated with the GPD bibliography database (`GPD/references/bibliography-db.json`).
The live bibliographer/paper pipeline uses the bibliography database as the persistent store,
`references/references.bib` for BibTeX output, and this markdown file for human review.

**Purpose:** Human-readable view of the bibliography database. The machine-readable source of truth
is `GPD/references/bibliography-db.json`, which tracks read/cited/relevant status, citation
networks, and verification state. This markdown file is generated from and kept in sync with
that database.

**Relationship to other files:**

- `references/bibliography-db.json` is the persistent bibliography database (JSON, machine-readable)
- `references/references.bib` is the BibTeX file maintained by the gpd-bibliographer agent
- `state.json.project_contract` is the authoritative machine-readable anchor registry
- Phase SUMMARY.md files may reference citations by BibTeX key; the database tracks which are cited
- `CONVENTIONS.md` records which textbook conventions are followed; those textbooks should appear here
- `PARAMETERS.md` may cite data sources; those citations should appear here

---

## File Template

```markdown
# Project Reference and Anchor Ledger

## Anchor Ledger

| BibTeX Key | Type | Title / Artifact | Relevance | Read Status | Cited | Verification | Tags |
|------------|------|------------------|-----------|-------------|-------|--------------|------|
| [key] | [paper/tool/data/website] | [title, DOI/arXiv, or artifact path] | [critical/supporting/background/tangential] | [unread/skimmed/read/studied] | [yes/no] | [verified/pending/suspect/not_found] | [comma-separated tags] |

## Citation Network

| Source Key | Relationship | Target Key | Notes |
|------------|-------------|------------|-------|
| [citing_key] | cites | [cited_key] | [what is cited] |
| [key_a] | related_to | [key_b] | [relationship description] |

## Unresolved / Pending Anchors

- [Missing citation, benchmark, or prior artifact that still needs confirmation]
- [User-requested anchor that has not yet been sourced or verified]

## Reading Queue

Entries that are critical or supporting but have not yet been read:

- [ ] [bib_key]: [title] (relevance: [critical/supporting])

## Verification Status

- Total references: [N]
- Verified by bibliographer: [M]
- Cited in paper draft: [K]
- Read or studied: [R]
- Flagged issues: [list any SUSPECT or NOT FOUND references]

## Notes

- **Database file**: `references/bibliography-db.json` (persistent, machine-readable)
- **BibTeX file**: `references/references.bib` (maintained by bibliographer, generated from database)
- **Relevance tiers**: critical (must surface), supporting (used downstream), background (context only), tangential (noted but not needed)
- **Read status**: unread, skimmed, read, studied
- **Verified**: Checked by gpd-bibliographer against INSPIRE/ADS/Google Scholar
```

<lifecycle>

**Creation:** During project initialization, after PROJECT.md

- Initialize `GPD/references/bibliography-db.json` with `load_bibliography_db(project_root)`
- Pre-populate with key references from the project description and project contract using `add_from_citation_source()`
- Add textbook references matching conventions in CONVENTIONS.md
- Set relevance levels: critical for contract-required, supporting for methods, background for context
- All entries start as `verification: pending`, `read_status: unread`

**Appending:** After each phase that introduces new citations

- Add new entries to the database via `add_from_citation_source()` or `add_entry()`
- Tag entries with `project_phases` to track which phase introduced them
- Set relevance based on role in the project (critical / supporting / background / tangential)
- Record citation links via `add_citation_link()` when papers cite each other
- Record related links via `add_related_link()` for thematically related papers
- Save the database with `save_bibliography_db()`

**Reading:** By gpd-bibliographer agent

- Load database with `load_bibliography_db(project_root)`
- Query unverified entries with `get_unverified_entries()`
- Verify BibTeX keys against INSPIRE-HEP, ADS, arXiv, Google Scholar
- Update verification status with `set_verification()`
- Detect hallucinated citations (keys that don't resolve) and mark as `not_found`
- Export verified entries to `references/references.bib` via `export_citation_sources()`
- Save the database after updates

**Reading:** By gpd-literature-reviewer agent

- Load database to check what has already been surveyed
- Query by tag or relevance to focus the review scope
- Use `get_unread_relevant()` to identify the reading queue
- After review, update `read_status` and add notes
- Build citation network links between surveyed papers

**Reading:** By gpd-paper-writer agent

- Look up citations by BibTeX key with `get_entry()`
- Use `get_cited_entries()` to see what is already cited
- Query by relevance to find critical references that must appear in the paper
- Mark entries as cited with `mark_cited()` as they are referenced in the draft

**Reading:** By gpd-referee agent

- Verify that claimed comparisons with literature have corresponding database entries
- Check that key methods and decisive benchmarks cite their original sources via `get_citation_network()`
- Use `filter_by_status(verification=VerificationStatus.suspect)` to find flagged entries
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
