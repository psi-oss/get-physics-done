---
template_version: 1
type: artifact-manifest-schema
---

# Artifact Manifest Schema

Canonical source for `${PAPER_DIR}/ARTIFACT-MANIFEST.json`, the machine-readable manifest emitted by `gpd paper-build`.

Record only artifacts the builder produced. Use this as the review/build handoff for the current manuscript root. Do not invent keys, prose summaries, or unsupported journal labels.

---

## File Template

```json
{
  "version": 1,
  "paper_title": "Benchmark Recovery in a Controlled Regime",
  "journal": "jhep",
  "created_at": "2026-04-04T12:00:00+00:00",
  "manuscript_sha256": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "manuscript_mtime_ns": 1775304000000000000,
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
      "artifact_id": "figure-benchmark",
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
        "label": "benchmark",
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
- `created_at`: ISO 8601 timestamp
- `manuscript_sha256`: active manuscript SHA-256
- `manuscript_mtime_ns`: active manuscript mtime ns
- `artifacts`: array of artifact records

## Artifact Records

Required:

- `artifact_id`: stable identifier such as `tex-paper`, `bib-references`, `audit-bibliography`, or `pdf-topic_stem`
- `category`: one of `tex`, `bib`, `figure`, `pdf`, `audit`
- `path`: artifact path string
- `sha256`: 64-character lowercase hex digest
- `produced_by`: producer label such as `build_paper:render_tex`

Optional:

- `sources`: array of source references
- `metadata`: object whose values are only strings, integers, floats, or booleans

## Source References

Each `sources[]` entry may include:

- `path`: upstream artifact path
- `role`: short label such as `source-figure`, `compiled-from`, or `bibliography`

## Path Rules

- For artifacts inside the manuscript root, keep `path` relative to `${PAPER_DIR}`.
- Preserve external paths only when the artifact lives outside `${PAPER_DIR}`.
- Keep `sources[].path` aligned with the original upstream input path instead of rewriting it into prose.

## Journal Rules

The manifest `journal` must match a supported builder key in `${PAPER_DIR}/PAPER-CONFIG.json`: `prl`, `apj`, `mnras`, `nature`, `jhep`, or `jfm`.

Do not write unsupported scoring-only journal labels such as `prd`, `prb`, `prc`, or `nature_physics` into `${PAPER_DIR}/ARTIFACT-MANIFEST.json`.

## Validation Rules

- Keep `artifacts` as a JSON array.
- Do not add undocumented top-level keys.
- Keep every `sha256` exact.
- If `manuscript_sha256` differs from the active manuscript digest, the manifest is stale and cannot drive manuscript resolution or publication preflight.
- Treat `manuscript_mtime_ns` as diagnostic; regenerate with `gpd paper-build` after manuscript edits.
- Keep `metadata` structured; regenerate this file instead of hand-editing one path.
