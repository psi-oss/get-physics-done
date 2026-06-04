<purpose>
Authority for the deslopification gate: a meaning-preserving, line-audited
"expertization" pass that makes an AI-written math/physics manuscript read like
expert work while freezing all scientific content and surfacing; never burying;
every rigor, notation, citation, or physics concern. Owned by
`gpd-discipline-editor`; invoked standalone via `gpd:deslop-paper` and as the
deslopification gate inside `write-paper` publication-review finalization.
</purpose>

<principle>
Never ask the model to "make the paper better." Ask it to propose audited,
semantics-preserving transformations under frozen mathematical invariants. A style
pass over plausible-but-wrong work is more dangerous than no pass, because it
removes the tells that warn a reviewer. So: freeze the science, edit only the
surface, flag everything substantive.
</principle>

<pass_A_freeze_meaning>
Before any edit, build `${PAPER_DIR}/DESLOP-LEDGER.json`:

```json
{
  "protected_spans": ["display_math","inline_math","theorem_statements","hypotheses",
    "labels","refs","cite_keys","bibitems","numbers","units","asymptotic_exponents",
    "theorem/conjecture/open-problem status"],
  "claim_ledger":    [{"claim_id":"CLM-001","location":"main.tex:123-130","type":"theorem",
    "statement_hash":"...","conditionality":"conditional on Conjecture CPA","evidence_refs":["..."]}],
  "notation_ledger": [{"symbol":"R_3","first_use":"...","first_definition":"...",
    "status":"defined_before_use|used_before_defined|overloaded|one_use"}],
  "citation_ledger": [{"key":"BGS-T","location":"...",
    "status":"verified|unresolved|internal|placeholder|suspect"}]
}
```

Anything in the protected ledger is immutable unless an edit is purely typographic and
byte-equivalent after whitespace normalization. This prevents the dangerous case where a
style pass silently changes a theorem, condition, exponent, citation, or normalization.
</pass_A_freeze_meaning>

<pass_B_route>
Route every paragraph to exactly one of:

| Route | Meaning |
|-------|---------|
| KEEP  | Prose is acceptable, or changing it is risky. |
| EDIT  | Style-only edit; all protected ledgers remain invariant. |
| FLAG  | Rigor, notation, citation, physics, evidence, metadata, or theorem-status issue. |

The same issue is never both EDIT and FLAG. If a sentence says "a standard argument shows"
and the argument is not supplied, you may not replace it with a plausible derivation; FLAG it.
</pass_B_route>

<pass_C_invariant_check>
An edit is admissible only if ALL hold:

```json
{"math_spans_identical":true,"citations_identical":true,"labels_refs_identical":true,
 "numbers_units_identical":true,"theorem_status_identical":true,"limitations_preserved":true,
 "claim_ledger_changed":false,"new_claims_added":true_is_forbidden}
```

This still permits high-value transformations: shortening overlong sentences; removing
process/scaffolding jargon and internal-file/commit provenance; moving internal provenance to
a flag; replacing a reflexive list with one specific sentence; delaying nonstandard vocabulary
until after a motivating sentence. None may touch a protected span.
</pass_C_invariant_check>

<pass_D_emit>
Write four artifacts to `${PAPER_DIR}` (see the audit and flags schema templates):
`DESLOP-AUDIT.jsonl` (one record per edit, by line), `DESLOP-AUDIT.md` (human table),
`DESLOP-FLAGS.md` (substantive issues), `DESLOP-SUMMARY.json` (gate status + counts).
`apply` mode also writes the edited `.tex`; `audit` mode leaves the manuscript untouched.
The audit is not optional: an edit with no by-line record is a defect; fail closed.
</pass_D_emit>

<math_physics_tell_catalogue>
Beyond the generic AI accent (see the project slop-evidence requirements), flag/edit these
field-specific tells. The most dangerous is the first; it can camouflage a rigor gap.

| Tell | Why it reads off | Route |
|------|------------------|-------|
| Agent-scaffolding leakage: `.md`/commit/`state.json`/"Phase"/"Pitfall"/"verbatim from …" | Advertises the assembly process; cites internal files as scholarly authority | EDIT to public statement + FLAG if it hides a real dependency |
| Internal provenance as evidence in bibliography ("submission-time check", "anchor", "working-title used here") | Drafting notes published as references | FLAG (blocker; never fabricate the citation) |
| Proof-routing nouns (branch, exit, packet, wrapper, route, terminal sink, ledger, carrier, scaffold) dominating exposition | Makes the proof sound like a workflow engine | EDIT toward "we now prove …"; keep genuine definitions |
| Catalogue proofs; a long list replaces *why* a step is true | Reader sees an inventory, not a reason | EDIT to a compressed dichotomy + FLAG to cross-reference the lemmas |
| Auditor voice ("this completes the chain", "NOT SELECTED", "coverage statement", "no further branch is invoked") | Satisfying a checklist, not explaining | EDIT or move to a dependency appendix |
| Over-conditional flag repetition (the same "conditional on …" string repeated verbatim) | Mechanical | EDIT to state the conditionality once, clearly; never weaken it |
| Physics pseudo-effectivity: `O(poly(...))` with open "explicit constants" | Big-O claim with no computable inputs | FLAG |
| Mathematical overpackaging; every bookkeeping step gets a named Definition/Proposition | Naming for flourish | FLAG (author decides) |
| Notation/concept dumped before motivation | Framework dump, not a guided proof | EDIT to motivation→example→definition order; FLAG missing example/non-example |
</math_physics_tell_catalogue>

<concept_intro_gate>
For every nonstandard term/symbol, the notation ledger records `{object, kind, first_use,
first_definition, motivation_before_definition, example_present, nonexample_or_boundary_case_present,
used_in_theorem_or_proof, one_use_only, status}`. Fail-closed checks (flag, do not auto-fix):

```
CONCEPT_INTRO_GATE:
  require first_definition <= first_technical_use
  require motivation before definition unless locally standard
  require example or boundary case for new named machinery
  require symbol-collision check against universal conventions (∇, ∂, ℏ, ...)
  flag one-use symbols
```

Only safe presentation rewrites are auto-edited (e.g., replacing "endpoint" with the symbol it
already equals in-source). Do not over-gloss standard vocabulary.
</concept_intro_gate>

<fix_hierarchy>
Order of what a working mathematician/physicist cares about; fix/flag in this order; prose taste is LAST:
1. Correctness & epistemic status; theorem vs conjecture vs conditional vs heuristic vs computation; assumptions visible; proof gaps surfaced.
2. Evidence & citations; real, relevant, verified, public; internal files removed from the scholarly argument.
3. Definitions & notation; abstract, theorem statement, and first proof page readable without chasing private jargon.
4. Local proof readability; each hard step says what is used, not merely "standard"/"clearly"/"by closure".
5. Physics sanity; units, dimensions, signs, 2π, ℏ, c, normalization, limiting cases, parameter regimes.
6. Prose taste; sentence rhythm, paragraph burstiness, fewer reflexive lists, fewer stock pivots, no AI accent.
</fix_hierarchy>

<gate_status>
```json
{"gate_status":"clean | edited_with_flags | blocked","edit_count":0,"flag_count":0,
 "release_blocker_count":0,"compile_status":"passed | failed | not_run","semantic_invariants_passed":true}
```
`ci` mode sets `blocked` if any release blocker remains: public-facing scaffolding leakage,
placeholder/submission-time-check citations, missing/incomplete audit coverage, or unresolved
notation/concept-order flags.
</gate_status>
