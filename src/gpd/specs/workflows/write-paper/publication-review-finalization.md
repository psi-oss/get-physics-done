<purpose>
Own publication review routing, final adjudication handoff, final manuscript
checks, and in-workflow revision/response artifacts.
</purpose>

<stage_boundary>
This compact router eagerly loads only this stage and the review-round contract.
Response authoring, recovery, scoring, reliability diagnostics, panel execution,
schemas, and proof-redteam details stay conditional or inside staged
`gpd:peer-review`; do not inline them here.

Start only after manuscript-root artifacts, fresh bibliography audit,
reproducibility manifest, and claim/proof blockers are clear.
</stage_boundary>

<init>
Load the staged publication-review payload before routing peer review or
evaluating review-round artifacts:

```bash
if [ -n "${ARGUMENTS:-}" ]; then PUBLICATION_REVIEW_INIT=$(gpd --raw init write-paper --stage publication_review -- "$ARGUMENTS"); else PUBLICATION_REVIEW_INIT=$(gpd --raw init write-paper --stage publication_review); fi
if [ $? -ne 0 ]; then echo "ERROR: write-paper publication-review init failed: $PUBLICATION_REVIEW_INIT"; fi
INIT="$PUBLICATION_REVIEW_INIT"
```

Apply `PUBLICATION_REVIEW_INIT.staged_loading.field_access_instruction` before reading `PUBLICATION_REVIEW_INIT`.

```bash
PAPER_DIR=$(echo "$INIT" | gpd json get .publication_bootstrap_root --default "")
PAPER_DIR="${PAPER_DIR:-$(echo "$INIT" | gpd json get .manuscript_root --default "")}"
selected_publication_root=$(echo "$INIT" | gpd json get .selected_publication_root --default GPD)
selected_review_root=$(echo "$INIT" | gpd json get .selected_review_root --default "")
selected_review_root="${selected_review_root:-${selected_publication_root}/review}"
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```
</init>

<reward_hacking_integrity_gate>
Run `{GPD_INSTALL_DIR}/references/shared/reward-hacking-self-check.md` against
the manuscript before `pre_submission_review`. Distinct from
`critique_revision_loop` (polish); this step is content integrity. Always runs,
fail-closed, both lanes. Never skip for a finalized manuscript.

**Procedure.**

1. Resolve lane-aware `${gate_inputs}`:
   - **project-backed:** `${artifact_manifest_path}`, `${bibliography_audit_path}`,
     `state.json` `contract_results`, `GPD/phases/*-SUMMARY.md`,
     `GPD/phases/*-VERIFICATION.md`.
   - **external-authoring:** `${artifact_manifest_path}`,
     `${bibliography_audit_path}`, plus the bound intake manifest and its
     claim/evidence ledger under `GPD/publication/{subject_slug}/intake/`.
     Project-backed artifacts (`state.json`, phase summaries/verifications) are
     **not** required here; their absence must not block the gate. Fail-closed
     still holds: at least one bound evidence source per audited claim.

2. Spawn `gpd-paper-writer` (`readonly=false`) using the canonical runtime
   delegation convention:

   ```python
   task(
     subagent_type="gpd-paper-writer",
     model="{writer_model}",
     readonly=false,
     prompt="Read {GPD_AGENTS_DIR}/gpd-paper-writer.md and {GPD_INSTALL_DIR}/references/shared/reward-hacking-self-check.md. Apply items 1-5 plus S1-S4 to ${manuscript_entrypoint}, using ${gate_inputs}.\n\n<autonomy_mode>{AUTONOMY}</autonomy_mode>\n<research_mode>{RESEARCH_MODE}</research_mode>\n\nWrite ${PAPER_DIR}/INTEGRITY-GATE.json: items.{literal_vs_spirit,cheap_wins,adversarial_self_review,uncertainty_disclosure,revise_or_refuse} each {passed,notes}; scientific_writing_rules.{S1_speculative_pathways,S2_citation_confidence,S3_evidence_kind,S4_confidence_to_language} each {passed,violations}; overall_passed; required_revisions[] of {section,item,suggested_change}. S2/S4 fail-closed: any at_risk_citation or confidence mismatch sets overall_passed=false. suggested_change must be a concrete edit.",
     description="Reward-hacking integrity gate"
   )
   ```

3. Read `${PAPER_DIR}/INTEGRITY-GATE.json`. If `overall_passed: true`, append a
   one-line entry to `${PAPER_DIR}/CRITIQUE-LOG.md` and proceed.

4. If `overall_passed: false`: spawn `gpd-paper-writer` (`readonly=false`) per
   `required_revisions` item using `suggested_change` as the directive --
   scoped, not broadened. Re-run the gate once. If still false:
   - `autonomy=yolo`: do NOT proceed; record failures in `CRITIQUE-LOG.md` and
     `gpd_return.issues`; recommend dropping offending citations/claims or
     weakening prose to match verified evidence.
   - `autonomy=supervised|balanced`: present remaining `required_revisions` with
     location, item, and suggested change; ask whether to (1) keep revising,
     (2) drop/weaken, or (3) accept as a known limitation.

Never silently waive: a staged panel on a manuscript that failed the gate
yields untrustworthy recommendations. This gate runs independently of
`critique_revision_loop` skip conditions (e.g., `research_mode=exploit` +
`autonomy=supervised`).
</reward_hacking_integrity_gate>

<deslopification_gate>
Run the deslopification gate AFTER the reward-hacking integrity gate and BEFORE
`pre_submission_review`. The integrity gate secures claim/evidence integrity; this
gate makes the manuscript read like expert work WITHOUT hiding the remaining issues.
Peer review must see the cleaned manuscript plus `DESLOP-FLAGS.md`, never the raw
agent scaffolding. Authority:
`{GPD_INSTALL_DIR}/references/publication/deslopification-gate.md`. Always runs on a
finalized manuscript; fail-closed on release blockers; never edits a protected span.

1. Spawn `gpd-discipline-editor` (`readonly=false`) via the canonical delegation
   convention:

   ```python
   task(
     subagent_type="gpd-discipline-editor",
     model="{writer_model}",
     readonly=false,
     prompt="Read {GPD_AGENTS_DIR}/gpd-discipline-editor.md and {GPD_INSTALL_DIR}/references/publication/deslopification-gate.md. Run the four-pass deslopification gate on ${manuscript_entrypoint} in --mode apply. Freeze all protected spans and the claim/notation/citation ledgers first; route each paragraph KEEP/EDIT/FLAG; apply only invariant-passing style edits; FLAG (never fix) everything substantive. Write ${PAPER_DIR}/DESLOP-AUDIT.jsonl, ${PAPER_DIR}/DESLOP-AUDIT.md, ${PAPER_DIR}/DESLOP-FLAGS.md, ${PAPER_DIR}/DESLOP-SUMMARY.json and the edited manuscript.\n\n<autonomy_mode>{AUTONOMY}</autonomy_mode>\n<research_mode>{RESEARCH_MODE}</research_mode>",
     description="Deslopification gate"
   )
   ```

2. Read `${PAPER_DIR}/DESLOP-SUMMARY.json`. If `gate_status` is `clean` or
   `edited_with_flags` and `release_blocker_count == 0`, append a one-line entry to
   `${PAPER_DIR}/CRITIQUE-LOG.md` (`edits=N, flags=M`) and proceed to
   `pre_submission_review` with the cleaned manuscript.

3. If `release_blocker_count > 0` (`gate_status: blocked`): do NOT proceed to peer
   review.
   - `autonomy=yolo`: record blockers in `CRITIQUE-LOG.md` and `gpd_return.issues`;
     recommend the author actions in `DESLOP-FLAGS.md` (resolve placeholder citations,
     scaffolding leakage, notation order).
   - `autonomy=supervised|balanced`: present the `DESLOP-FLAGS.md` blockers (location,
     why, recommended action) and ask whether to (1) resolve now via the delegated
     owner, (2) accept as a known limitation, or (3) hold the manuscript. Re-run this
     gate after resolution.

Never silently waive: peer review on a manuscript still leaking agent scaffolding or
carrying placeholder citations yields untrustworthy recommendations. Style edits here
never alter a protected span; `DESLOP-AUDIT.md` is the by-line proof.
</deslopification_gate>

<pre_submission_review>
Branch by write-paper lane before finalizing.

**Project-backed lane:** route to staged `gpd:peer-review` for the resolved
`${PAPER_DIR}/{topic_specific_stem}.tex` target recorded in
`ARTIFACT-MANIFEST.json`. Use the peer-review stage manifest for panel
execution, final adjudication, review-ledger/referee-decision schemas, and any
proof-redteam gate. Do not inline those authorities here.
Load `proactive_critique_loop` when budget allows; log run/skip/failure.

After peer review, this stage may read review-round artifacts. Load the conditional `response_pair_authoring` authorities only when drafting the pair.

Use `gpd-referee` only through the peer-review final-adjudication authority. Keep
the project-contract gate fields, reference handles/statuses, citation-source
context, and protocol load manifests visible. Read a specific reference or
protocol file only for a concrete finding, response issue, or route.

Read `${selected_review_root}/REFEREE-DECISION{round_suffix}.json` and
`${selected_review_root}/REVIEW-LEDGER{round_suffix}.json` first when they
exist, then read `${selected_publication_root}/REFEREE-REPORT{round_suffix}.md`
and assess the findings.

**External-authoring lane:** do **not** run the embedded staged panel here.
Embedded `write-paper` review parity for the bounded external-authoring lane is deferred until the managed publication lineage is unified end to end.

Instead, verify the bounded manuscript-root handoff under `${PAPER_DIR}`:
`{topic_specific_stem}.tex`, `PAPER-CONFIG.json`, `ARTIFACT-MANIFEST.json`,
`BIBLIOGRAPHY-AUDIT.json`, `reproducibility-manifest.json`, and
`FIGURE_TRACKER.md` when figures are tracked.
Required handoff paths include `${PAPER_DIR}/PAPER-CONFIG.json`, `${PAPER_DIR}/ARTIFACT-MANIFEST.json`, `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, and `${PAPER_DIR}/reproducibility-manifest.json`.

If any required manuscript-root artifact is missing, stop and fix it now.
Otherwise, route the user to standalone `gpd:peer-review` against the resolved
manuscript root or entrypoint. Do not claim full pre-submission review parity
here, and do not recommend `gpd:arxiv-submission` directly from this lane.
</pre_submission_review>

<final_review>
Before declaring the draft complete, run only decisive checks unless the user
explicitly requested polish: artifact manifest, bibliography audit,
reproducibility manifest, target-bound review state, abstract/story consistency,
introduction/conclusion contribution, equations/figures, page count, and
reference formatting.

Paper quality scoring is advisory and artifact-driven. Load
`advisory_paper_quality_scoring` only when decisive. Use
`${PAPER_DIR}/ARTIFACT-MANIFEST.json`, `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`,
`${PAPER_DIR}/FIGURE_TRACKER.md`, `GPD/comparisons/*-COMPARISON.md`, and
phase summary/verification `contract_results` / `comparison_verdicts`.
Treat paper-support artifacts as scaffolding, not as proof that a claim is established.
Missing decisive comparisons still block strong submission recommendations.
Recommend `gpd:arxiv-submission` only when project-backed staged review already
clears packaging.

Run paper-quality scoring from project artifacts when it is still decisive:

```bash
gpd validate paper-quality --from-project .
```

Skip paper-quality scoring if `review_gate` is decisive or finalization budget is
at risk. Skipping does not weaken bibliography freshness or peer-review
requirements.
</final_review>

<paper_revision>
For dedicated response work, use `gpd:respond-to-referees`. This in-workflow
revision loop applies only after project-backed embedded review; the bounded
external-authoring lane exits earlier and resumes through standalone
`gpd:peer-review` or `gpd:respond-to-referees` once artifacts exist.

When revising a paper in response to referee reports:

1. Parse each referee point into a structured item with category and affected
   manuscript section(s).
2. Spawn targeted section revision agents for manuscript changes; a point is not
   `fixed` until the corresponding section file changes have landed on disk.
3. Load `response_pair_authoring` authorities only after manuscript edits land,
   then produce paired response artifacts through `gpd-paper-writer`.

Pass `<autonomy_mode>{AUTONOMY}</autonomy_mode>`,
`<research_mode>{RESEARCH_MODE}</research_mode>`, selected roots, round,
referee report, optional ledger/decision paths, manifest-resolved manuscript
tree, and the concrete author/referee response paths. For each `REF-xxx` issue,
classify it only after the corresponding manuscript edits exist on disk.

Response-pair completion is delegated to
`publication-response-writer-handoff.md` plus `stage-recovery-gate.md` under the
`response_pair_authoring` condition. Keep the callsite identifier
`id: "write_paper_response_pair"` when applying that delegated gate, with
`${selected_publication_root}/AUTHOR-RESPONSE{round_suffix}.md` and
`${selected_review_root}/REFEREE_RESPONSE{round_suffix}.md` as the expected
outputs. Both response paths must pass handoff artifact validation, round
binding, manuscript binding, allowed-root checks, and freshness checks before
this stage treats the response pair as complete.

Response-pair child gate:

```yaml
child_gate:
  id: "write_paper_response_pair"
  role: "gpd-paper-writer"
  return_profile: "paper_writer"
  required_status: "completed"
  expected_artifacts:
    - "${selected_publication_root}/AUTHOR-RESPONSE{round_suffix}.md"
    - "${selected_review_root}/REFEREE_RESPONSE{round_suffix}.md"
  allowed_roots:
    - "${selected_publication_root}"
    - "${selected_review_root}"
  freshness_marker: "after $RESPONSE_HANDOFF_STARTED_AT"
  validators:
    - "gpd validate handoff-artifacts for both response paths"
    - "publication-response-writer-handoff.md frontmatter, round, and manuscript binding"
  applicator: "none"
  failure_route: "stage-recovery-gate -> retry response writer | stop incomplete"
```

Response-pair completion requires this callsite tuple to pass for both paths.

Track new calculations in `${PAPER_DIR}/REVISION_TASKS.md`. After targeted
revisions, rerun consistency/reference checks and then this publication-review
stage. Stop after three bounded iterations and surface remaining issues.
</paper_revision>

<success_criteria>
- [ ] Project-backed lane: staged peer-review round completed, including final
      adjudication and proof-redteam artifacts when required.
- [ ] External-authoring lane: manuscript-root artifacts exist under
      `GPD/publication/{subject_slug}/manuscript`, and the workflow routed to
      standalone `gpd:peer-review`.
- [ ] Major staged-review issues were addressed or explicitly acknowledged.
- [ ] The bounded external-authoring lane did not widen into generic folder
      mining or direct `gpd:arxiv-submission` claims.
</success_criteria>

<community_contribution>
After a finalized draft passes peer review, mention that public papers can be
added to the README.md "Papers Using GPD" list at
https://github.com/psi-oss/get-physics-done#papers-using-gpd with a short
problem/approach summary, workflow used, and optional key result or figure. This
prompt is informational only; do not block the paper workflow on it.
</community_contribution>
