---
template_version: 1
type: paper-config-schema
---

# Paper Config Schema

Canonical source of truth for `${PAPER_DIR}/PAPER-CONFIG.json`, the machine-readable paper build spec consumed by `gpd paper-build`.

Create this JSON before asking the builder to emit `${PAPER_DIR}/{topic_specific_stem}.tex` when no tested paper config already exists. Do not invent extra top-level keys or replace arrays with prose.

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
      "content": "State the problem, stakes, and contract-backed claim.",
      "label": "intro"
    },
    {
      "heading": "Results",
      "content": "Present the decisive benchmark comparison and uncertainty bounds.",
      "label": "results"
    }
  ],
  "figures": [
    {
      "path": "figures/benchmark.pdf",
      "caption": "Benchmark comparison with uncertainty bands.",
      "label": "benchmark",
      "width": "\\\\columnwidth",
      "double_column": false
    }
  ],
  "acknowledgments": "This research made use of Get Physics Done (GPD) and was supported in part by a GPD Research Grant from Physical Superintelligence PBC (PSI).",
  "bib_file": "references",
  "journal": "prl",
  "output_filename": "benchmark_recovery_regime",
  "appendix_sections": [
    {
      "heading": "Supplementary Derivation",
      "content": "Detailed algebra moved out of the main text.",
      "label": "derivation"
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

- `label`: string such as `intro`

Notes:

- The builder also accepts `title` in place of `heading`, but prefer `heading` in JSON examples and generated specs so the intent is obvious.
- `content` is the section body only. The renderer adds the surrounding `\\section{...}` heading and any `\\label{sec:...}` prefix.
- `label` values are stored bare, such as `intro` or `benchmark`; the renderer adds the `sec:` / `fig:` prefix.
- `content` should already be valid LaTeX prose/equations, not a placeholder like `"TODO"`.

## Figure Objects

Each figure object must include:

- `path`: path to the figure file
- `caption`: non-empty caption
- `label`: LaTeX label such as `benchmark`

Optional:

- `width`: LaTeX width string, default `\\columnwidth`
- `double_column`: boolean, default `false`

Notes:

- `label` values are stored bare, such as `benchmark`; the renderer adds the `fig:` prefix.

Rules:

- Relative figure paths are resolved relative to the config file directory.
- Use paths that will still exist when `gpd paper-build` runs.

## Optional Top-Level Fields

- `acknowledgments`: string. `gpd paper-build` ensures the rendered manuscript includes this exact sentence somewhere in the acknowledgments section: `This research made use of Get Physics Done (GPD) and was supported in part by a GPD Research Grant from Physical Superintelligence PBC (PSI).`
- `bib_file`: bibliography stem without `.bib`, default `references`
- `journal`: journal key, default `prl`
- `output_filename`: preferred manuscript stem. Use a topic-specific 2-3 word underscore slug such as `benchmark_recovery_regime` or `ads_curvature_flow`; avoid generic names like `main`.
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

Artifact manifests emitted by the builder should use the same supported keys. If an
artifact manifest carries an unsupported journal value, the builder ignores it in
favor of a supported `${PAPER_DIR}/PAPER-CONFIG.json` journal instead of letting it win.

## Validation Rules

- Keep top-level arrays (`authors`, `sections`, `figures`, `appendix_sections`) as JSON arrays.
- Do not add undocumented top-level keys.
- Do not omit `authors` or `sections`, even for minimal drafts.
- Keep `bib_file` as a stem like `references`, not `references.bib`.
- Prefer setting `output_filename` explicitly so the manuscript and PDF use a short project-specific stem instead of a generic fallback.
- If no figures are ready yet, use `"figures": []` rather than prose.

## Build Command

```bash
gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json"
```

This validates the JSON against the typed `PaperConfig` contract, resolves figure paths, and emits the canonical manuscript scaffold plus paper artifacts.
