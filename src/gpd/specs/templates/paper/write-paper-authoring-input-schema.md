---
template_version: 1
type: write-paper-authoring-input-schema
---

# Write-Paper Authoring Input Schema

Canonical source of truth for the bounded external-authoring intake accepted by `gpd:write-paper --intake path/to/write-paper-authoring-input.json`.

Use this manifest only for the explicit external-authoring lane. It is closed-schema and fail-closed: do not add undocumented top-level keys, and do not replace claim-to-evidence bindings with loose prose.

---

## File Template

```json
{
  "schema_version": 1,
  "title": "Curvature Flow Bounds from Controlled Benchmarks",
  "authors": [
    {
      "name": "A. Researcher",
      "email": "researcher@example.edu",
      "affiliation": "Department of Physics, Example University"
    }
  ],
  "target_journal": "prl",
  "subject_slug": "curvature-flow-bounds",
  "central_claim": "The controlled benchmark regime supports a stable curvature-flow bound with quantified uncertainty.",
  "claims": [
    {
      "id": "CLM-main",
      "statement": "The benchmarked curvature-flow bound remains stable across the resolved parameter range.",
      "evidence": {
        "source_note_ids": ["NOTE-main"],
        "result_ids": ["RES-main"],
        "figure_ids": ["FIG-main"],
        "citation_source_ids": ["cite-benchmark"]
      }
    }
  ],
  "source_notes": [
    {
      "id": "NOTE-main",
      "path": "notes/main-result.md",
      "summary": "Summarizes the benchmark setup, numerical regime, and the final fitted bound."
    }
  ],
  "results": [
    {
      "id": "RES-main",
      "summary": "Main benchmark comparison showing the stable bound and uncertainty band.",
      "source_note_ids": ["NOTE-main"]
    }
  ],
  "figures": [
    {
      "id": "FIG-main",
      "path": "figures/benchmark-comparison.pdf",
      "caption": "Benchmark comparison supporting the main bound.",
      "source_note_ids": ["NOTE-main"]
    }
  ],
  "citation_sources": [
    {
      "source_type": "paper",
      "reference_id": "cite-benchmark",
      "title": "Benchmark Recovery in a Controlled Regime",
      "authors": ["A. Author", "B. Author"],
      "year": "2024",
      "arxiv_id": "2401.12345"
    }
  ],
  "notation_note": "Use c = ħ = 1 and keep the manuscript notation aligned with the source notes."
}
```

## Required Top-Level Fields

- `schema_version`: must be the integer `1`
- `title`: non-empty string
- `authors`: non-empty array of `Author` objects
- `target_journal`: one of `prl`, `apj`, `mnras`, `nature`, `jhep`, or `jfm`
- `central_claim`: non-empty string
- `claims`: non-empty array of claim objects
- `source_notes`: non-empty array of source-note objects
- `citation_sources`: non-empty array of citation-source objects

Optional:

- `subject_slug`: lowercase kebab-case slug for `GPD/publication/{subject_slug}/...`
- `results`: array of result objects
- `figures`: array of figure objects
- `notation_note`: free-text notation or convention note

## Claim Objects

Each claim object must include:

- `id`: `CLM-*`
- `statement`: non-empty string
- `evidence`: object with at least one explicit binding list

The `evidence` object may include:

- `source_note_ids`: `NOTE-*` ids
- `result_ids`: `RES-*` ids
- `figure_ids`: `FIG-*` ids
- `citation_source_ids`: `citation_sources[].reference_id` values

Rules:

- At least one evidence list must be non-empty.
- Every referenced id must exist in the same manifest.
- Duplicate ids are invalid.

## Source Note Objects

Each source note object must include:

- `id`: `NOTE-*`
- `path`: non-empty path or locator string
- `summary`: non-empty summary of what the note contains

## Result Objects

Each result object must include:

- `id`: `RES-*`
- `summary`: non-empty result summary
- `source_note_ids`: non-empty array of `NOTE-*` ids

## Figure Objects

Each figure object must include:

- `id`: `FIG-*`
- `path`: non-empty figure path
- `caption`: non-empty caption
- `source_note_ids`: non-empty array of `NOTE-*` ids

## Citation Sources

`citation_sources` reuses the canonical `CitationSource` surface. Each entry must still include:

- `reference_id`: non-empty string
- `title`: non-empty string
- `source_type`: one of `paper`, `tool`, `data`, or `website`

`claims[].evidence.citation_source_ids` must reference these `reference_id` values exactly.

## Validation Rules

- Keep the top-level object closed. Unknown keys are invalid.
- Do not omit `claims`, `source_notes`, or `citation_sources`.
- Do not rely on loose filenames, prose summaries, or implicit provenance in place of explicit evidence bindings.
- If `subject_slug` is omitted, the runtime derives it from `title`; if present, it must already be lowercase kebab-case.
- This intake manifest is not `PAPER-CONFIG.json`. It is the authoring contract that authorizes the bounded external lane before manuscript scaffolding exists.
