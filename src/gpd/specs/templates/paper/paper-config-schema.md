---
template_version: 1
type: paper-config-schema
---

# Paper Config Schema

Canonical source of truth for `paper/PAPER-CONFIG.json`, the machine-readable paper build spec consumed by `gpd paper-build`.

Create this JSON before asking the builder to emit `paper/main.tex` when no tested paper config already exists. Do not invent extra top-level keys or replace arrays with prose.

---

## File Template

```json
{
  "title": "Benchmark Recovery in a Controlled Regime",
  "authors": [
    {
      "name": "A. Researcher",
      "email": "researcher@example.edu",
      "affiliation": "Department of Physics, Example University"
    }
  ],
  "abstract": "One paragraph stating the question, method, decisive result, and why it matters.",
  "sections": [
    {
      "heading": "Introduction",
      "content": "\\\\section{Introduction}\\nState the problem, stakes, and contract-backed claim.",
      "label": "sec:intro"
    },
    {
      "heading": "Results",
      "content": "\\\\section{Results}\\nPresent the decisive benchmark comparison and uncertainty bounds.",
      "label": "sec:results"
    }
  ],
  "figures": [
    {
      "path": "figures/benchmark.pdf",
      "caption": "Benchmark comparison with uncertainty bands.",
      "label": "fig:benchmark",
      "width": "\\\\columnwidth",
      "double_column": false
    }
  ],
  "acknowledgments": "Funding, collaborators, and compute support.",
  "bib_file": "references",
  "journal": "prl",
  "appendix_sections": [
    {
      "heading": "Supplementary Derivation",
      "content": "\\\\section{Supplementary Derivation}\\nDetailed algebra moved out of the main text.",
      "label": "app:derivation"
    }
  ],
  "attribution_footer": "Generated with Get Physics Done"
}
```

## Required Fields

- `title`: non-empty string
- `authors`: array of objects with `name`; `email` and `affiliation` are optional strings
- `abstract`: non-empty string
- `sections`: array of section objects

## Section Objects

Each section object must include:

- `heading`: non-empty section title
- `content`: LaTeX-ready section body string

Optional:

- `label`: string such as `sec:intro`

Notes:

- The builder also accepts `title` in place of `heading`, but prefer `heading` in JSON examples and generated specs so the intent is obvious.
- `content` should already be valid LaTeX prose/equations, not a placeholder like `"TODO"`.

## Figure Objects

Each figure object must include:

- `path`: path to the figure file
- `caption`: non-empty caption
- `label`: LaTeX label such as `fig:benchmark`

Optional:

- `width`: LaTeX width string, default `\\columnwidth`
- `double_column`: boolean, default `false`

Rules:

- Relative figure paths are resolved relative to the config file directory.
- Use paths that will still exist when `gpd paper-build` runs.

## Optional Top-Level Fields

- `acknowledgments`: string
- `bib_file`: bibliography stem without `.bib`, default `references`
- `journal`: journal key, default `prl`
- `appendix_sections`: array of section objects
- `attribution_footer`: string footer appended by the builder

## Supported `journal` Values

The paper builder currently supports:

- `prl`
- `apj`
- `mnras`
- `nature`
- `jhep`
- `jfm`

Choose one supported key exactly. Do not use freeform journal names here.

## Validation Rules

- Keep top-level arrays (`authors`, `sections`, `figures`, `appendix_sections`) as JSON arrays.
- Do not add undocumented top-level keys.
- Do not omit `authors` or `sections`, even for minimal drafts.
- Keep `bib_file` as a stem like `references`, not `references.bib`.
- If no figures are ready yet, use `"figures": []` rather than prose.

## Build Command

```bash
gpd paper-build paper/PAPER-CONFIG.json
```

This validates the JSON against the typed `PaperConfig` contract, resolves figure paths, and emits the canonical manuscript scaffold plus paper artifacts.
