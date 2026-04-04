---
template_version: 1
type: artifact-manifest-schema
---

# Artifact Manifest Schema

Canonical source of truth for `${PAPER_DIR}/ARTIFACT-MANIFEST.json`, the machine-readable manifest emitted by `gpd paper-build`.

This file records the concrete manuscript artifacts the builder actually produced. Treat it as the canonical review/build handoff for the current manuscript root. Do not invent extra keys, prose summaries, or unsupported journal labels.

---

## File Template

```json
{
  "version": 1,
  "paper_title": "Benchmark Recovery in a Controlled Regime",
  "journal": "jhep",
  "created_at": "2026-04-04T12:00:00+00:00",
  "artifacts": [
    {
      "artifact_id": "tex-paper",
      "category": "tex",
      "path": "benchmark_recovery_regime.tex",
      "sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "produced_by": "build_paper:render_tex",
      "sources": [],
      "metadata": {
        "journal": "jhep",
        "section_count": 6,
        "appendix_count": 1,
        "figure_count": 3
      }
    },
    {
      "artifact_id": "audit-bibliography",
      "category": "audit",
      "path": "BIBLIOGRAPHY-AUDIT.json",
      "sha256": "abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789",
      "produced_by": "build_paper:write_bibliography_audit",
      "sources": [],
      "metadata": {
        "total_sources": 18,
        "resolved_sources": 18,
        "partial_sources": 0,
        "unverified_sources": 0,
        "failed_sources": 0
      }
    },
    {
      "artifact_id": "figure-fig:benchmark",
      "category": "figure",
      "path": "figures/benchmark.pdf",
      "sha256": "fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210",
      "produced_by": "build_paper:prepare_figures",
      "sources": [
        {
          "path": "plots/benchmark.py",
          "role": "source-figure"
        }
      ],
      "metadata": {
        "label": "fig:benchmark",
        "caption_length": 92,
        "double_column": false
      }
    }
  ]
}
```

## Top-Level Fields

- `version`: literal integer `1`
- `paper_title`: non-empty string
- `journal`: supported builder journal key from `${PAPER_DIR}/PAPER-CONFIG.json`
- `created_at`: ISO 8601 timestamp string
- `artifacts`: array of artifact records

## Artifact Records

Each `artifacts[]` entry must include:

- `artifact_id`: stable identifier such as `tex-paper`, `bib-references`, `audit-bibliography`, or `pdf-topic_stem`
- `category`: one of `tex`, `bib`, `figure`, `pdf`, `audit`
- `path`: artifact path string
- `sha256`: 64-character lowercase hex digest
- `produced_by`: non-empty producer label such as `build_paper:render_tex`

Optional:

- `sources`: array of source references
- `metadata`: object whose values are only strings, integers, floats, or booleans

## Source References

Each `sources[]` entry may include:

- `path`: original upstream artifact path
- `role`: short role label such as `source-figure`, `compiled-from`, or `bibliography`

## Path Rules

- For artifacts inside the manuscript root, keep `path` relative to `${PAPER_DIR}`.
- Preserve an explicit external path only when the artifact actually lives outside `${PAPER_DIR}`.
- Keep `sources[].path` aligned with the original upstream input path instead of rewriting it into prose.

## Journal Rules

The manifest `journal` must stay aligned with the supported builder key in `${PAPER_DIR}/PAPER-CONFIG.json`. The builder currently supports:

- `prl`
- `apj`
- `mnras`
- `nature`
- `jhep`
- `jfm`

Do not write unsupported scoring-only journal labels such as `prd`, `prb`, `prc`, or `nature_physics` into `${PAPER_DIR}/ARTIFACT-MANIFEST.json`.

## Validation Rules

- Keep `artifacts` as a JSON array, even when only one artifact exists.
- Do not add undocumented top-level keys.
- Keep every `sha256` exact; approximate hashes do not satisfy the manifest contract.
- Keep `metadata` machine-readable. Do not replace structured fields with prose blocks.
- If the manuscript entrypoint changes, regenerate this file through `gpd paper-build` rather than editing only one path by hand.

