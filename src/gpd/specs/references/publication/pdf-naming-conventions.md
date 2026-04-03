---
reference_type: output-conventions
description: PDF and TeX output filename derivation rules for the paper build pipeline
used_by: [gpd-paper-writer]
---

# PDF Naming Conventions

How the paper build pipeline derives filenames for emitted `.tex` and `.pdf` artifacts.

## Filename Resolution Order

1. **Explicit override** -- If `PaperConfig.output_filename` is set, use it verbatim as the stem (no extension).
2. **Topic-derived default** -- Otherwise derive a short manuscript stem from `PaperConfig.title`:
   - Normalize to ASCII lowercase.
   - Prefer the first 2-3 salient topic words.
   - Join them with underscores.
   - Truncate to 60 characters.
3. **Fallback** -- If the title is empty or sanitizes to nothing, use `paper_draft`.

## Examples

| Title | output_filename | Resulting stem |
|---|---|---|
| Quantum Entanglement in Black Holes | *(not set)* | `quantum_entanglement_black` |
| *(empty)* | *(not set)* | `paper_draft` |
| *(any)* | `my-paper-v2` | `my-paper-v2` |
| A Very Long Title That Exceeds Sixty Characters When Fully Written Out Here | *(not set)* | first 2-3 salient words, truncated if needed |

## Integration Points

- `gpd.mcp.paper.models.derive_output_filename` -- Pure function implementing the rules above.
- `gpd.mcp.paper.compiler.build_paper` -- Calls `derive_output_filename` to name the primary emitted `.tex` file; the compiler then produces a `.pdf` with a matching stem.
- `ARTIFACT-MANIFEST.json` records the canonical emitted manuscript path so downstream manuscript discovery and review flows resolve the actual topic-specific stem instead of assuming `main.tex`.

## Constraints

- The derived filename must be safe for all major filesystems (no path separators; default slugs only use ASCII letters, digits, and underscores).
- The 60-character limit avoids filesystem path-length issues on Windows.
- When `output_filename` is provided, no sanitization is applied, but it must still be a bare filename stem rather than a path.
