---
load_when:
  - "paper writer journal calibration"
  - "paper writer venue guidance"
  - "paper writer latex scaffold"
  - "paper writer figure sizing"
type: paper-writer-cookbook
tier: 2
context_cost: medium
---

# Paper Writer Cookbook

Use this pack only when the venue or manuscript structure needs concrete examples. The base paper-writer prompt keeps only the hard contract, evidence gate, acknowledgment text, and return envelope.

## Venue Calibration

- `prl`: lead with the result, keep the main story compact, and move derivation bulk to supplemental material.
- `jhep`: state conventions early, show the full calculation path, and keep renormalization / scheme choices explicit.
- `nature`: prioritize accessibility and implication-first narrative; technical details move to Methods or supplement.
- style-only venues such as PRD/PRC/PRB/PRA/Nature Physics should influence tone and section depth, not the builder journal key.

## LaTeX Scaffold Hints

- APS-style journals: `revtex4-2` with the supported journal option.
- JHEP: `article` + `jheppub`.
- Nature-style manuscripts: standard `article` plus conservative package use and clean figure handling.
- Builder-backed artifacts remain authoritative for the emitted `.tex` path and supported journal key.

## Figure Sizing

- PRL single column: about `3.375 in`; double column: about `7.0 in`.
- JHEP single-column figures can usually fill the text width.
- Nature-style figures should be simpler, more visual, and readable by non-specialists.
- For exact file-format and sizing constraints, prefer vector output for LaTeX (`pdf`, `eps`) and avoid `tiff` for arXiv packaging.

## Story Architecture Reminders

- State one central claim.
- Pick the 3-5 results that actually carry that claim.
- Move long derivations and exhaustive tables out of the main text when they do not advance the story.
- Keep the strongest defensible claim aligned with the evidence already present in summaries, verification artifacts, and comparison verdicts.
