---
template_version: 1
purpose: Supplemental bibliography registry template
total_references: 0
---

# Bibliography Template

Template for `.gpd/BIBLIOGRAPHY.md` -- optional bibliography registry for projects that want a
human-readable citation ledger in addition to the live BibTeX files.

**Status:** Not wired into the current GPD bibliography flow. The live bibliographer/paper pipeline
uses `references/references.bib`, `references/references-verified.log`, and
`references/references-pending.md`.

**Purpose:** Use this only if you explicitly want a parallel markdown registry of citations across
the project. It is no longer treated as the canonical source of truth for paper generation.

**Relationship to other files:**

- `references/references.bib` is the BibTeX file maintained by the gpd-bibliographer agent
- Phase SUMMARY.md files may reference citations by BibTeX key; this file is optional supplemental tracking
- `CONVENTIONS.md` records which textbook conventions are followed; those textbooks should appear here
- `PARAMETERS.md` may cite data sources; those citations should appear here

---

## File Template

```markdown
# Project Bibliography

## Primary References (foundations of this work)

| BibTeX Key | Authors | Year | Title | DOI/arXiv | Source Phase | Provides | Verified |
|-----------|---------|------|-------|-----------|-------------|----------|----------|
| [key] | [authors] | [year] | [title] | [doi] | Phase [N] | benchmark/method/comparison | [yes/no] |

## Methods References (techniques and algorithms used)

| BibTeX Key | Authors | Year | Title | DOI/arXiv | Source Phase | Method | Verified |
|-----------|---------|------|-------|-----------|-------------|--------|----------|
| [key] | [authors] | [year] | [title] | [doi] | Phase [N] | [method name] | [yes/no] |

## Comparison Benchmarks (data we compare against)

| BibTeX Key | Authors | Year | Title | DOI/arXiv | Source Phase | Quantity | Agreement | Verified |
|-----------|---------|------|-------|-----------|-------------|----------|-----------|----------|
| [key] | [authors] | [year] | [title] | [doi] | Phase [N] | [what] | [yes/no/partial] | [yes/no] |

## Background Reading (context and review articles)

| BibTeX Key | Authors | Year | Title | DOI/arXiv | Source Phase | Topic | Verified |
|-----------|---------|------|-------|-----------|-------------|-------|----------|
| [key] | [authors] | [year] | [title] | [doi] | Phase [N] | [topic] | [yes/no] |

## Verification Status

- Total references: [N]
- Verified by bibliographer: [M]
- Cited in paper draft: [K]
- Flagged issues: [list any SUSPECT or NOT FOUND references]

## Notes

- **Confidence tiers**: Primary (directly supports results), Secondary (provides context), Tertiary (general background)
- **Verified**: Checked by gpd-bibliographer against INSPIRE/ADS/Google Scholar
- **BibTeX file**: `references/references.bib` (maintained by bibliographer)
```

<lifecycle>

**Creation:** During project initialization, after PROJECT.md

- Pre-populate with key references from the project description
- Add textbook references matching conventions in CONVENTIONS.md
- Initialize all as unverified

**Appending:** After each phase that introduces new citations

- Extract citations from phase RESEARCH.md and SUMMARY.md
- Categorize into Primary, Methods, Comparison, or Background
- Record which phase introduced each reference
- Trigger bibliographer verification if available

**Reading:** By gpd-bibliographer agent

- Verify BibTeX keys against INSPIRE-HEP, ADS, arXiv, Google Scholar
- Detect hallucinated citations (keys that don't resolve)
- Warn about missing citations when equations from papers are used without attribution
- Maintain `references/references.bib` in correct journal format

**Reading:** By gpd-paper-writer agent

- Look up citations by BibTeX key for inline references
- Use the categorization to build the paper's reference section
- Check that all cited results have verified references

**Reading:** By gpd-referee agent

- Verify that claimed comparisons with literature have corresponding entries
- Check that key methods cite their original sources
- Flag any result that uses a technique without citing the methods reference

</lifecycle>

<guidelines>

**What belongs in BIBLIOGRAPHY.md:**

- Every reference cited in any phase artifact
- Textbooks and review articles that establish conventions
- Papers providing benchmark data for comparison
- Original sources for methods and algorithms used

**What does NOT belong here:**

- Full BibTeX entries (those go in `references/references.bib`)
- Detailed summaries of papers (those go in phase RESEARCH.md)
- Literature review analysis (that goes in literature review artifacts)

**When filling this template:**

- Use consistent BibTeX key format: `AuthorYYYY` for single author, `AuthorCoauthorYYYY` for two, `AuthorEtAlYYYY` for three or more
- Record DOI when available, arXiv ID as fallback, URL as last resort
- Mark the "Provides" column specifically: what does this reference give us? (e.g., "QCD beta function to 5-loop", "lattice spacing determination", "experimental cross section data")
- For comparison benchmarks, record whether agreement was found
- Keep entries sorted by BibTeX key within each section

**Why bibliography tracking matters:**

- Prevents hallucinated citations (a known LLM failure mode)
- Enables automatic BibTeX generation for paper drafts
- Tracks provenance: which results depend on which references
- Supports reproducibility: exact references for every method and comparison
- Catches missing attributions before peer review

**Verification workflow:**

The gpd-bibliographer agent checks each entry:
1. Resolve BibTeX key against INSPIRE-HEP (for HEP papers), ADS (for astrophysics), or Google Scholar
2. Verify that title, authors, and year match
3. Flag entries that cannot be resolved as SUSPECT
4. Generate proper BibTeX and add to `references/references.bib`

</guidelines>
