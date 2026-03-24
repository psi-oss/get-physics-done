---
template_version: 1
purpose: Per-source evidence boundary note for recording what a source directly supports, indirectly suggests, and does not support
---

# Research Evidence Note Template

Template for `.gpd/evidence/EV-001.md` -- a focused note for one source and one claim, question, or comparison boundary.

**Purpose:** Capture the boundary between "this reference exists" and "this source should carry weight for this specific point." Use one note when a source needs more careful treatment than a bibliography entry or citation list can provide.

**Relationship to other files:**

- `BIBLIOGRAPHY.md` is the optional registry of sources and anchors; an evidence note is the per-source review artifact when one source needs explicit support boundaries
- `state.json.project_contract.references[]` records plan-time reference roles and must-surface anchors; an evidence note records the post-read interpretation of a specific source
- `contract-results-schema.md` records whether contract claims, references, and comparisons passed or failed; an evidence note explains what the source actually supports before those verdicts are written
- Phase `RESEARCH.md` and `SUMMARY.md` files may cite source takeaways; an evidence note is the durable support-boundary record behind those takeaways
- `DECISIONS.md` may reference evidence note IDs when a research choice depends on a particular source boundary

---

## File Template

```markdown
---
evidence_note_id: EV-001
source_id: [reference-id, bibtex-key, benchmark-id, artifact-id, or n/a]
source_type: paper | benchmark | dataset | prior_artifact | experiment | review | spec | internal_note
claim_under_review: "[short claim, question, or comparison target]"
status: draft | reviewed | superseded
updated: YYYY-MM-DD
downstream_artifacts:
  - [artifact path]
---

# Evidence Note: [short source / claim label]

## Source

- Source ID: [reference-id or n/a]
- Source Type: [paper / benchmark / dataset / prior_artifact / ...]
- Citation / Path: [BibTeX key, DOI, arXiv ID, URL, or repo path]
- Reviewer: [agent or user]
- Review Date: [YYYY-MM-DD]

## Claim Under Review

- [the exact claim, question, or comparison target being evaluated]

## Direct Support

- [what the source directly establishes]
- [only include claims that the source itself supports clearly]

## Indirect Signals

- [what the source weakly suggests, hints at, or partially informs]
- [keep these distinct from direct support]

## Does Not Support

- [what the source does not establish]
- [things that would overstate the source if carried forward]

## Caveats And Boundary Conditions

- [scope limits, assumptions, model regime, missing checks, benchmark caveats]
- [anything a downstream artifact must not silently flatten away]

## Downstream Uses

- [artifact path] — [how this note should constrain or support it]

## Open Questions

- [what still needs another source, benchmark, or calculation]
```

<lifecycle>

**Creation:** When a source needs more than a citation or bibliography entry

- Create one note per source / claim boundary, not one giant literature dump
- Start from a concrete question, claim, or comparison target
- Link the note to the closest downstream artifact that will rely on it

**Appending / Updating:** After rereads, new comparisons, or reviewer feedback

- Tighten the `Direct Support`, `Indirect Signals`, and `Does Not Support` sections when the interpretation sharpens
- Update caveats when new assumptions, benchmark tensions, or regime limits become clear
- Mark `status: superseded` if a better note replaces this one

**Reading:** By planning, execution, verification, and writing agents

- Use evidence notes to avoid flattening a nuanced source into a simple yes/no citation
- Check `Does Not Support` and `Caveats And Boundary Conditions` before carrying a claim forward
- Use the note ID in downstream artifacts when a decision or rebuttal depends on this exact source boundary

</lifecycle>

<guidelines>

**What belongs in an evidence note:**

- One source and one concrete claim, question, or comparison target
- The exact boundary between direct support, indirect signal, and non-support
- Caveats that downstream artifacts must preserve
- Pointers to the artifacts that rely on this interpretation

**What does NOT belong here:**

- Full BibTeX entries or citation registry management
- A general literature review covering many unrelated sources at once
- Final contract pass/fail verdicts by themselves
- Authority class labels for the whole source corpus

**When filling this template:**

- Quote the claim under review as narrowly as possible
- Prefer explicit non-support over vague hedging
- Keep direct support separate from suggestive but incomplete evidence
- Link only the downstream artifacts that actually depend on this interpretation
- If the source is too broad for one note, split it into multiple source / claim notes

**Why this artifact matters:**

- Prevents a real source from being overclaimed downstream
- Preserves caveats and scope limits that often get lost in summaries
- Makes reviewer rebuttals and milestone audits easier because the evidence boundary is already written down
- Creates a durable bridge between source presence and claim authority without changing the contract schema itself

</guidelines>
