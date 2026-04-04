---
template_version: 1
type: bibliography-audit-schema
---

# Bibliography Audit Schema

Canonical source of truth for `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, the machine-readable bibliography audit emitted by `gpd paper-build`.

This audit is the strict-review artifact for bibliography integrity. It summarizes whether each citation was provided, enriched, left incomplete, or failed verification. Do not replace these structured statuses with prose.

---

## File Template

```json
{
  "generated_at": "2026-04-04T12:00:00+00:00",
  "total_sources": 3,
  "resolved_sources": 2,
  "partial_sources": 1,
  "unverified_sources": 0,
  "failed_sources": 0,
  "entries": [
    {
      "key": "bench2026",
      "source_type": "paper",
      "reference_id": "ref-benchmark",
      "title": "Benchmark Recovery in a Controlled Regime",
      "resolution_status": "provided",
      "verification_status": "partial",
      "verification_sources": [],
      "canonical_identifiers": [
        "doi:10.1000/benchmark",
        "arxiv:2604.01234"
      ],
      "missing_core_fields": [],
      "enriched_fields": [],
      "warnings": [
        "Canonical identifiers were provided by the caller but not externally verified"
      ],
      "errors": []
    },
    {
      "key": "legacy2021",
      "source_type": "paper",
      "reference_id": "ref-legacy",
      "title": "Legacy Result",
      "resolution_status": "enriched",
      "verification_status": "verified",
      "verification_sources": ["arXiv"],
      "canonical_identifiers": ["arxiv:2101.01234"],
      "missing_core_fields": [],
      "enriched_fields": ["title", "authors", "year"],
      "warnings": [],
      "errors": []
    }
  ]
}
```

## Top-Level Fields

- `generated_at`: ISO 8601 timestamp string
- `total_sources`: total number of audit entries
- `resolved_sources`: count of entries whose `resolution_status` is `provided` or `enriched`
- `partial_sources`: count of entries whose `verification_status` is `partial`
- `unverified_sources`: count of entries whose `verification_status` is `unverified`
- `failed_sources`: count of entries whose `resolution_status` is `failed`
- `entries`: array of citation audit records

## Citation Audit Records

Each `entries[]` item must include:

- `key`: emitted BibTeX key
- `source_type`: one of `paper`, `tool`, `data`, `website`
- `title`: citation title string
- `resolution_status`: one of `provided`, `enriched`, `incomplete`, `failed`
- `verification_status`: one of `verified`, `partial`, `unverified`
- `verification_sources`: array of external verification sources such as `arXiv`
- `canonical_identifiers`: array of normalized identifiers such as `doi:...`, `arxiv:...`, or `url:...`
- `missing_core_fields`: array of missing core field names
- `enriched_fields`: array of fields filled during enrichment
- `warnings`: array of non-fatal audit warnings
- `errors`: array of fatal enrichment or resolution errors

Optional:

- `reference_id`: project contract or citation-source reference id

## Status Semantics

- `provided`: the caller already supplied the necessary core citation fields
- `enriched`: missing core fields were recovered from enrichment and now pass the minimum citation requirements
- `incomplete`: core fields are still missing
- `failed`: enrichment or resolution failed outright

- `verified`: an external source confirmed the citation metadata
- `partial`: the citation is usable but not fully externally verified
- `unverified`: no external verification happened

## Validation Rules

- Keep `entries` as a JSON array, even for a one-citation bibliography.
- Do not add undocumented top-level keys or per-entry keys.
- Keep the summary counters consistent with the per-entry statuses above.
- Preserve warnings and errors as arrays of strings; do not collapse them into one paragraph.
- Regenerate this file with `gpd paper-build` after bibliography changes instead of editing counts manually.

