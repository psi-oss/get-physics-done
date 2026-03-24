---
template_version: 1
purpose: Supplemental post-read evidence authority ledger
total_entries: 0
---

# Evidence Authority Ledger Template

Template for `.gpd/EVIDENCE-AUTHORITY.md` -- optional machine-readable source-weight ledger for projects that need an explicit post-read assessment of how much authority each source should carry.

**Status:** Not wired into the current GPD contract flow. Use this only if a project needs a durable authority surface between bibliography anchors and contract / comparison results.

**Purpose:** Distinguish plan-time anchor presence from post-read source authority. Use this ledger to record whether a source is promotive, bounded, context-only, negative, mixed, or unresolved for a specific claim, deliverable, or benchmark after review.

**Relationship to other files:**

- `BIBLIOGRAPHY.md` tracks what references and anchors exist; this file tracks how much downstream weight each source should carry after review
- `state.json.project_contract.references[*]` and `PLAN.md#/contract.references[]` define anchor role and must-surface expectations
- Phase `RESEARCH.md`, `SUMMARY.md`, and `VERIFICATION.md` artifacts hold the narrative analysis and decisive contract outcomes
- `paper/internal-comparison.md` records cross-method or benchmark verdicts, not per-source authority classes
- If a project needs richer per-source prose than the compact authority summary here, keep that narrative in the phase artifacts and use this file as the machine-readable ledger

---

## File Template

```markdown
---
template_version: 1
total_entries: 0
authority_entries:
  - id: auth-ref-main
    reference_id: ref-main
    authority_class: promotive|bounded|context_only|negative|mixed|unresolved
    applies_to: [claim-main]
    not_for: [claim-side]
    scope_limits:
      - "[regime, assumption, or observable boundary]"
    carry_forward_to: [planning, verification, writing]
    evidence_path: .gpd/phases/XX-name/XX-SUMMARY.md
    summary: "[what this source actually supports and how strongly]"
---

# Evidence Authority Ledger

## Summary

- Total authority entries: [N]
- Promotive entries: [A]
- Bounded entries: [B]
- Context-only entries: [C]
- Negative entries: [D]
- Mixed / unresolved entries: [E]

## Authority Ledger

| ID | Reference ID | Authority Class | Applies To | Not For | Scope Limits | Carry Forward To | Evidence Path |
|----|--------------|-----------------|------------|---------|--------------|------------------|---------------|
| auth-ref-main | ref-main | promotive | claim-main | claim-side | [regime] | planning, verification | .gpd/phases/XX-name/XX-SUMMARY.md |

## Class Definitions

- **promotive**: Source can positively support a downstream claim or benchmark interpretation
- **bounded**: Source supports the downstream use only inside explicit regime, method, or observable limits
- **context_only**: Source is worth carrying for framing or definitions, but should not carry decisive weight
- **negative**: Source is disconfirming, blocking, or directly undermines a proposed use
- **mixed**: Source supports one downstream use but cuts against another, so a single class is insufficient
- **unresolved**: Review exists, but authority is still not settled enough to classify

## Notes

- Use `not_for` to make non-support visible instead of leaving it implicit
- Use `scope_limits` whenever a source is valid only under clear restrictions
- Keep `summary` short and concrete; the phase artifact at `evidence_path` should hold the longer explanation
```

<lifecycle>

**Creation:** After bibliography or reference review becomes material

- Initialize when the project begins carrying literature, benchmarks, datasets, or prior artifacts that need more than “present / cited”
- Pre-populate only for sources that have actually been reviewed
- Leave uncertain cases as `unresolved`, not silently omitted

**Appending:** After each literature or benchmark review pass

- Add or update one authority entry per reviewed source / use pairing
- Record exactly which claim, deliverable, or benchmark the source applies to
- Capture the evidence path where the supporting or disconfirming reasoning is written down

**Reading:** By planner / executor agents

- Use the ledger to decide which sources can actually carry downstream weight
- Avoid promoting context-only or bounded evidence as though it were fully promotive

**Reading:** By paper-writer and referee agents

- Check whether claims are leaning on promotive or merely contextual evidence
- Use `negative` and `mixed` entries to surface rebuttal risk before drafting conclusions

</lifecycle>

<guidelines>

**What belongs in EVIDENCE-AUTHORITY.md:**

- Reviewed sources that need an explicit authority class after reading
- Scope limits that materially bound how a source can be used downstream
- Non-support or disconfirming relationships that should remain visible
- Pointers to the phase artifact where the detailed reasoning lives

**What does NOT belong here:**

- Full bibliographic metadata (that belongs in `BIBLIOGRAPHY.md` or `references/references.bib`)
- Detailed literature summaries (those belong in phase `RESEARCH.md` artifacts)
- Contract pass/fail results (those belong in `contract_results` / `comparison_verdicts`)
- Project-specific ontology or domain-specific evidence semantics

**When filling this template:**

- Classify only after actual review; do not predeclare authority from titles alone
- Prefer `bounded` over `promotive` whenever regime limits matter
- Prefer `mixed` or `unresolved` over forced certainty
- Keep the authority class attached to an explicit downstream use via `applies_to`
- Use `not_for` to make invalid downstream uses legible

**Why evidence-authority tracking matters:**

- Prevents anchor presence from being mistaken for downstream support
- Makes scope limits and non-support machine-visible
- Helps rebuttal, milestone, and review surfaces stay honest about what sources really carry weight
- Supports literature-heavy projects without forcing domain-specific scoring logic into core contracts

</guidelines>
