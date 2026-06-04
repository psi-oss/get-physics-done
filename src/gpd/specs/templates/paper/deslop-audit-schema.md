<purpose>
Schema for the deslopification audit trail. One record per applied edit, by line.
Written by `gpd-discipline-editor` to `${PAPER_DIR}/DESLOP-AUDIT.jsonl` (machine) and
rendered to `${PAPER_DIR}/DESLOP-AUDIT.md` (human table). The audit is a first-class
deliverable: an applied edit with no record here is a defect; fail closed.
</purpose>

<jsonl_record>
Each line of `DESLOP-AUDIT.jsonl` is one edit:

```json
{
  "edit_id": "DSE-0042",
  "location": {"file": "main.tex", "line_start": 281, "line_end": 286},
  "original": "Disposition tag. Per PFAFFIAN-APPLICABILITY.md §7.3, the disposition is (b) CONDITIONAL HOLDS...",
  "new": "The decidability result is conditional on Conjecture CPA. Existing Pfaffian and cellular-decomposition results provide the framework, but the mirror-octic constants have not yet been computed.",
  "tell_addressed": "agent_scaffolding_leakage",
  "rationale": "Removes internal project-provenance language while preserving the public conditional status.",
  "meaning_preserving": "yes",
  "protected_spans_changed": false,
  "claim_ledger_changed": false
}
```

Fields:
- `edit_id`; stable `DSE-NNNN`.
- `location`; file + 1-based line range in the pre-edit manuscript.
- `original` / `new`; verbatim text before and after.
- `tell_addressed`; controlled vocabulary: `agent_scaffolding_leakage`, `process_jargon`,
  `proof_routing_nouns`, `catalogue_proof`, `auditor_voice`, `over_conditional_repetition`,
  `notation_before_motivation`, `tricolon_or_list_cascade`, `not_x_but_y`, `colon_drop`,
  `hedging_cluster`, `mic_drop_ending`, `stock_vocabulary`, `em_dash_overuse`,
  `stray_bold`, `reflexive_list`, `low_burstiness`, `typo`.
- `rationale`; one line, why this is slop and why the rewrite is faithful.
- `meaning_preserving`; must be `"yes"`; an edit that cannot assert this is a FLAG, not an edit.
- `protected_spans_changed` / `claim_ledger_changed`; must both be `false`.
</jsonl_record>

<md_table>
`DESLOP-AUDIT.md` renders the same records as a reviewer-facing table, grouped by section:

```markdown
| location | original → new | tell addressed | rationale | meaning-preserving |
|----------|----------------|----------------|-----------|--------------------|
| main.tex:281-286 | internal commit/file provenance → public conditional statement | agent-scaffolding leakage | Removes private process evidence; preserves CPA conditionality. | yes |
```

A human must be able to `diff` the manuscript and confirm, edit by edit, that nothing
semantic changed. Header carries totals: `edits=N`, `protected_spans_changed=0`,
`claim_ledger_changed=0`.
</md_table>
