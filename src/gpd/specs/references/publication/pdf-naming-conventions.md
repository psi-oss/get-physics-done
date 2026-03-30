---
reference_type: output-conventions
description: PDF and TeX output filename derivation rules for the paper build pipeline
used_by: [gpd-paper-writer]
---

# PDF Naming Conventions

How the paper build pipeline derives filenames for emitted `.tex` and `.pdf` artifacts.

## Filename Resolution Order

1. **Explicit override** -- If `PaperConfig.output_filename` is set, use it verbatim as the stem (no extension).
2. **Title-based slug** -- Sanitize `PaperConfig.title`:
   - Lowercase the title.
   - Replace spaces with hyphens.
   - Strip characters that are not alphanumeric or hyphens.
   - Collapse consecutive hyphens.
   - Truncate to 60 characters.
3. **Fallback** -- If the title is empty or sanitizes to nothing, use `main`.

## Examples

| Title | output_filename | Resulting stem |
|---|---|---|
| Quantum Entanglement in Black Holes | *(not set)* | `quantum-entanglement-in-black-holes` |
| *(empty)* | *(not set)* | `main` |
| *(any)* | `my-paper-v2` | `my-paper-v2` |
| A Very Long Title That Exceeds Sixty Characters When Fully Written Out Here | *(not set)* | truncated to first 60 characters of slug |

## Integration Points

- `gpd.mcp.paper.models.derive_output_filename` -- Pure function implementing the rules above.
- `gpd.mcp.paper.compiler.build_paper` -- Calls `derive_output_filename` to name the primary emitted `.tex` file; the compiler then produces a `.pdf` with a matching stem.
- `gpd.mcp.paper.compiler.build_paper` also writes compatibility copies at `main.tex` and `main.pdf` when the derived stem is not `main`, so downstream manuscript discovery and review flows continue to work.

## Constraints

- The derived filename must be safe for all major filesystems (no special characters beyond hyphens).
- The 60-character limit avoids filesystem path-length issues on Windows.
- When `output_filename` is provided, no sanitization is applied, but it must still be a bare filename stem rather than a path.
