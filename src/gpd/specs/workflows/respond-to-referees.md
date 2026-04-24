<purpose>
Structure a point-by-point response to referee reports and revise the manuscript accordingly. Handles the full revision pipeline: parsing referee comments, drafting responses, spawning revision agents for manuscript changes, tracking new calculations, and producing the canonical GPD response artifacts, with an optional manuscript-local response letter companion when the journal still needs one. This workflow is project-aware: it may revise the active manuscript from the current GPD project or an explicit manuscript subject, but the canonical GPD-authored response artifacts still live under `GPD/`. Integrates with the GPD research workflow for any new calculations requested by referees.

Called from gpd:respond-to-referees command. Section revisions are performed by gpd-paper-writer agents.
</purpose>

<core_principle>
Responding to referees is not adversarial -- it is collaborative improvement. Every referee comment, even an incorrect one, reveals something about how the paper communicates (or fails to communicate) its results. The goal is to produce a stronger paper, not to win an argument.

**Response principles:**

1. **Address every point.** Never ignore a comment, even if you disagree.
2. **Be specific.** "We have clarified the text" is insufficient. Quote the exact change.
3. **Be respectful.** Even when the referee is wrong, acknowledge their perspective.
4. **Separate response from changes.** The response letter explains; the manuscript shows.
5. **Track everything.** Every change, every new calculation, every decision.
</core_principle>

<process>

<step name="init">
**Initialize context and locate paper:**

```bash
INIT=$(gpd --raw init phase-op --include config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `autonomy`, `research_mode`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`, `derived_manuscript_reference_status`, `derived_manuscript_reference_status_count`, `derived_manuscript_proof_review_status`.

**Read mode settings:**

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default supervised)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after each referee point for user review of the proposed response.
- `autonomy=balanced` (default): Draft the full response and apply routine manuscript changes. Do not force a parse-confirmation pause; pause only if the referee report is ambiguous, the response needs claim-level changes, new calculations, or unresolved referee disagreements. Any spawned agent that needs user input must return `status: checkpoint` and stop; the orchestrator presents the checkpoint and spawns a fresh continuation handoff after the user responds.
- `autonomy=yolo`: Draft response and apply manuscript changes without pausing.

**Normalize command intake into one manuscript subject plus one or more report sources before preflight:**

- Preferred explicit intake: `gpd:respond-to-referees --manuscript path/to/main.tex --report reviews/ref1.md --report reviews/ref2.md`
- Accept the literal `paste` sentinel as an explicit report source.
- Accept the positional shorthand `gpd:respond-to-referees path/to/report.md` or `gpd:respond-to-referees paste` only when the manuscript subject resolves from the current GPD project.
- Treat a bare positional path as a referee-report source only. Do not reinterpret it as the manuscript subject for this workflow.
- Keep all GPD-authored auxiliary outputs under `GPD/` even when the manuscript subject itself is external, and keep manuscript edits on the resolved manuscript subject.
- Project-backed response rounds keep the current global `GPD/` / `GPD/review/` ownership. If centralized preflight resolves an explicit external publication subject with a managed subject-owned publication root at `GPD/publication/{subject_slug}`, keep the same round-artifact family inside that managed root instead of writing sidecars beside `${PAPER_DIR}`.
- Set `PREFLIGHT_ARGUMENTS` to the validator-safe normalized intake string before shelling out. For the explicit `--manuscript ... --report ...` lane, keep the normalized manuscript/report payload in that single variable and do not explode it back into separate validator argv tokens.

Run centralized context preflight before continuing:

```bash
if [ -n "$PREFLIGHT_ARGUMENTS" ]; then
  CONTEXT=$(gpd --raw validate command-context respond-to-referees -- "$PREFLIGHT_ARGUMENTS")
else
  CONTEXT=$(gpd --raw validate command-context respond-to-referees "$ARGUMENTS")
fi
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Run the centralized review preflight before continuing:

```bash
if [ -n "$PREFLIGHT_ARGUMENTS" ]; then
  REVIEW_PREFLIGHT=$(gpd validate review-preflight respond-to-referees --strict -- "$PREFLIGHT_ARGUMENTS")
elif [ -n "$ARGUMENTS" ]; then
  REVIEW_PREFLIGHT=$(gpd validate review-preflight respond-to-referees "$ARGUMENTS" --strict)
else
  REVIEW_PREFLIGHT=$(gpd validate review-preflight respond-to-referees --strict)
fi
if [ $? -ne 0 ]; then
  echo "$REVIEW_PREFLIGHT"
  exit 1
fi
```

When the normalized payload begins with `--`, the end-of-options marker is mandatory in both validator calls; otherwise the validator CLI will reinterpret `--manuscript` or `--report` as its own options instead of as subject text.
Use the literal `paste` sentinel when collecting inline report text. Do not pass the raw pasted referee report body as `$ARGUMENTS` to the strict preflight command.
Do not pass the raw pasted referee report body as `PREFLIGHT_ARGUMENTS` either; only the literal `paste` sentinel is validator-safe.

If review preflight exits nonzero because of missing project state, missing manuscript, missing referee report source when provided as a path, degraded review integrity, or missing required conventions, STOP and show the blocking issues before drafting responses.
In explicit external-manuscript mode, `project_state` and `conventions` are advisory only. The hard intake blockers remain the resolved manuscript subject, the report-source set, and review-integrity failures.
Apply the shared publication bootstrap preflight exactly:

@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md

Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true; otherwise the contract is visible but blocked, and the response should surface the blocker instead of relying on it.
If `derived_manuscript_reference_status` is present, use it as a quick manuscript-local summary of what is already cited, what is still pending, and what probably needs a bibliography refresh; keep `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` and the other manuscript-root publication artifacts authoritative for strict response and packaging decisions.
If `derived_manuscript_proof_review_status` is present, use it as the first-pass manuscript-local summary of proof-review freshness for theorem-bearing revisions; keep passed proof-redteam artifacts and the manuscript-root publication artifacts authoritative for strict response and packaging decisions.

**Locate paper directory:**

Bind `PAPER_DIR` to the manuscript root resolved either from explicit `--manuscript` intake or by the shared preflight and manuscript-root contract above, keep every manuscript-local path rooted there, and do not re-derive a second manuscript root later in this workflow. Set `MANUSCRIPT_BASENAME` from the resolved manuscript entrypoint for later rebuild and smoke-check steps.

**If no paper found:**

```
No paper directory found. Searched the canonical manuscript roots `paper/`, `manuscript/`, and `draft/` via the manuscript resolver

Run gpd:write-paper first to generate a manuscript from research results.
```

Exit.

Treat every resolved manuscript file path as rooted under `${PAPER_DIR}`, including nested section files such as `${PAPER_DIR}/{section}.tex` and any optional manuscript-local response-letter companion such as `${PAPER_DIR}/response-letter.tex` when the journal requires one.

**Convention verification** — referee responses must use the same conventions as the paper:

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — resolve before drafting referee responses"
  echo "$CONV_CHECK"
fi
```

If the check fails, resolve convention mismatches before proceeding. New calculations or derivations in the response must use the same conventions as the published manuscript.

**Check for existing referee response file:**

```bash
if [ -d GPD/review ]; then
  find GPD/review -maxdepth 1 -type f -name 'REFEREE_RESPONSE*.md' -print
fi
if [ -d GPD ]; then
  find GPD -maxdepth 1 -type f -name 'AUTHOR-RESPONSE*.md' -print
fi
```

If found, load as continuation context (user may be resuming an interrupted session). Do not infer `round_suffix` from these listings; the shared handoff below remains authoritative for latest-round detection and sibling-artifact pairing.

**Check for staged peer-review decision artifacts:**

```bash
if [ -d GPD/review ]; then
  find GPD/review -maxdepth 1 -type f -name 'REVIEW-LEDGER*.json' -print
  find GPD/review -maxdepth 1 -type f -name 'REFEREE-DECISION*.json' -print
fi
```

If matching round-specific files exist, load them as structured context, but keep the shared handoff below as the canonical source for active-round selection and paired response-artifact discovery.
Read `@{GPD_INSTALL_DIR}/references/publication/peer-review-reliability.md` here for the canonical failure-recovery, round-suffix, and latest-round artifact conventions that keep this workflow fail-closed.
Apply the shared publication response-writer handoff exactly:

@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md

Use that shared handoff for `round_suffix`, sibling-artifact discovery, and the canonical response-artifact pair for the active round. `GPD/REFEREE-REPORT{round_suffix}.md` remains the canonical issue-ID source, and `REVIEW-LEDGER*.json` / `REFEREE-DECISION*.json` still identify blocking issues, unsupported-claim findings, recommendation floors, and the referee's stated rationale. Keep `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, and `active_reference_context` visible together when drafting the response letter; treat the contract as approved scope only when `project_contract_gate.authoritative` is true.
</step>

<step name="load_specialized_revision_context">
Use `protocol_bundle_context` from init JSON as additive revision guidance.

- If `selected_protocol_bundle_ids` is non-empty, keep the bundle's decisive artifact expectations, benchmark anchors, estimator caveats, and reference prompts visible while triaging referee requests.
- Use bundle guidance to distinguish "missing decisive evidence we already owed" from "new side quest the referee is asking for."
- Do **not** let bundle guidance justify broader claims, waive review-ledger blockers, or replace the manuscript's actual evidence trail in `GPD/comparisons/*-COMPARISON.md`, `${PAPER_DIR}/FIGURE_TRACKER.md`, phase summary artifacts, or `VERIFICATION.md`.
- Keep revisions tied to claims the manuscript still intends to make. Review ledgers and bundle hints help prioritize, but they do not force new side analyses once honest claim narrowing resolves the concern.
- Use `derived_manuscript_reference_status` as the first-pass triage signal for citation and bibliography changes, but do not let it override the manuscript-root audit or publication-manifest checks.
</step>

<step name="parse_referee_reports">
**Obtain referee reports from the user:**

Ask the user to provide referee reports via one of:

1. **Explicit report paths** -- one or more `--report PATH` inputs or equivalent wrapper-provided file paths
2. **Paste directly** -- user pastes report text into the conversation
3. **Existing file** -- use canonical `GPD/REFEREE-REPORT{round_suffix}.md` only
4. **Positional shorthand** -- one positional report path only when the manuscript subject resolves from the current GPD project

If the active report source is external to the canonical round artifact set, import or normalize it into `GPD/REFEREE-REPORT{round_suffix}.md` before parsing comments. Use that canonical Markdown file as the durable issue-ID source for the rest of the workflow. Do not keep manuscript-local or external `AUTHOR-RESPONSE*` / `REFEREE_RESPONSE*` sidecars beside the source report.

**Parse each referee's comments into structured items:**

For each comment, extract:

- **Referee number** (1, 2, 3, ...)
- **Comment number** (sequential within referee)
- **Full text** of the comment
- **Category:** Physics concern | Clarity | Missing reference | Technical error | Presentation | Additional calculation requested
- **Priority:** Must address (could lead to rejection) | Should address (editor expects it) | Optional (nice to have)
- **Affected section(s):** Which manuscript section(s) the comment targets

**Also parse editor comments** (if present) as a separate section -- editor guidance often indicates which referee points are critical vs. optional.

**If staged peer-review artifacts exist, extract additional decision context:**

- Final recommendation from `REFEREE-DECISION*.json`
- Blocking issues and unresolved issue IDs from `REVIEW-LEDGER*.json`
- Any finding that the paper's claim scope outruns the evidence, that physical interpretation is unsupported, or that venue fit/significance is inadequate

Do not invent new `REF-*` identifiers from the JSON artifacts. Instead, use them to prioritize and calibrate the responses to the issues already surfaced in the canonical `GPD/REFEREE-REPORT{round_suffix}.md`.

Present the parsed structure. Ask for explicit user confirmation only in supervised mode or when the report source is ambiguous; balanced mode should treat the parse as working context and continue unless ambiguity or missing source requires a checkpoint:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > REFEREE REPORTS PARSED
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Editor decision:** {Major revision / Minor revision / Reject and resubmit}

| Referee | Comments | Must Address | New Calc Needed |
|---------|----------|-------------|-----------------|
| Referee 1 | {N} | {M} | {K} |
| Referee 2 | {N} | {M} | {K} |

### Critical Points (Must Address)

1.{N}: {brief summary} — {affected section}
2.{N}: {brief summary} — {affected section}
...

### Decision Context (if available)

- Recommendation floor: {major_revision / reject / etc.}
- Blocking issues from review ledger: {count}
- Central claims needing narrowed scope or stronger support: {summary}

Confirm parsing is correct, or paste corrections.
```

</step>

<step name="create_response_file">
**Create the structured referee response document:**

Read the canonical templates and the shared publication response-writer handoff:

```bash
cat {GPD_INSTALL_DIR}/templates/paper/author-response.md
cat {GPD_INSTALL_DIR}/templates/paper/referee-response.md
```

@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md

Create both response artifacts for the current round:

- `GPD/AUTHOR-RESPONSE{round_suffix}.md` — structured internal tracker keyed by `REF-*` issues, change locations, staged review outcomes, and new-calculation status
- `GPD/review/REFEREE_RESPONSE{round_suffix}.md` — journal-facing response letter built from the template

Those two GPD-owned response artifacts stay canonical even when the manuscript subject is explicit or external. Do not write `AUTHOR-RESPONSE*` or `REFEREE_RESPONSE*` beside `${PAPER_DIR}` or beside the imported report source.
If centralized preflight has already resolved a subject-owned publication root at `GPD/publication/{subject_slug}` for an explicit external publication subject, place the canonical response pair under that managed root and keep the same round suffix / sibling relationships there. Do not duplicate the pair into both the subject-owned root and the global project root in one run.

Populate `GPD/review/REFEREE_RESPONSE{round_suffix}.md` with paper metadata, decision summaries, mirrored per-comment classification/status fields from the canonical response templates, blocking items from `REVIEW-LEDGER*.json` when available, and the progress tracking table. Leave response and changes-made fields empty until the later draft/revision step fills them.

Before writing `GPD/AUTHOR-RESPONSE{round_suffix}.md`, load the canonical template at `@{GPD_INSTALL_DIR}/templates/paper/author-response.md` and keep the internal tracker aligned with it.

Populate `GPD/AUTHOR-RESPONSE{round_suffix}.md` with one section per `REF-*` issue, classification (`fixed`, `rebutted`, `acknowledged`, `needs-calculation`), exact manuscript change locations or planned follow-up work, `New calculations required` and `Source phase for new work` when needed, and any blocking / recommendation-floor context imported from `REVIEW-LEDGER*.json` or `REFEREE-DECISION*.json`. Use `**Evidence:**` blocks for rebuttals and `**Plan:**` blocks for acknowledged or `needs-calculation` responses when needed.

Apply the shared publication response-writer handoff exactly for the response-artifact pair:

@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md

Use the current `round_suffix` and the canonical sibling-artifact pair from that handoff rather than restating local round tables or alternate filenames.

Commit the initial response file:

```bash
PRE_CHECK=$(gpd pre-commit-check --files GPD/review/REFEREE_RESPONSE{round_suffix}.md GPD/AUTHOR-RESPONSE{round_suffix}.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: create referee response structure" \
  --files GPD/review/REFEREE_RESPONSE{round_suffix}.md GPD/AUTHOR-RESPONSE{round_suffix}.md
```

Keep the two files synchronized for the rest of the workflow: draft issue-by-issue substance in `GPD/AUTHOR-RESPONSE{round_suffix}.md`, and mirror the journal-facing prose into `GPD/review/REFEREE_RESPONSE{round_suffix}.md`.

Treat `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md` as the response success gate. If either artifact is missing after the writer returns, the response is not complete. The shared publication response-artifact contract remains authoritative for freshness and fail-closed completion.

</step>

<step name="triage_comments">
**Triage comments into actionable categories:**

Sort all comments into three groups:

**Group A -- Text-only responses (no manuscript change needed):**
- Referee misunderstandings that can be clarified in the response letter
- Comments where the current manuscript already addresses the concern
- Requests for clarification that are best handled in the response letter

**Group B -- Manuscript revisions (existing content needs editing):**
- Clarity improvements, additional explanation, notation fixes
- Missing references to add
- Figure improvements, caption changes
- Reorganization of existing material

**Group C -- New calculations required:**
- Additional derivations requested by referee
- New comparisons with published results
- Extended parameter ranges or new limiting cases
- Additional numerical checks or convergence tests

**Mandatory override from staged peer-review artifacts:**

If `REVIEW-LEDGER*.json` or `REFEREE-DECISION*.json` marks an issue as blocking, unsupported, or central to the recommendation floor, classify it as Must Address even if the prose report sounds mild. If the decision artifacts say the paper's claims outrun the evidence, do not triage that as response-only; it requires either manuscript revision, claim narrowing, or new evidence.
Treat referee requests beyond the manuscript's honest scope as optional unless they expose a real support gap for a claim you still want to keep.

Present triage:

```
### Triage Summary

| Group | Count | Action |
|-------|-------|--------|
| A: Response-only | {N} | Draft responses (no manuscript change) |
| B: Manuscript revision | {N} | Spawn paper-writer agents for section edits |
| C: New calculations | {N} | Create research phases via gpd:add-phase |

Group C items require research work before the response can be completed.
Address Group-C new-calculation items first? [Y/n/e]  (Enter = Y; e opens freeform to re-triage)
```

</step>

<step name="handle_new_calculations">
**For Group C items (new calculations requested by referees):**

If no Group C items: skip to draft_responses.

For each new calculation:

1. Create matching entries in the "New Calculations Summary" sections of `GPD/review/REFEREE_RESPONSE{round_suffix}.md` and `GPD/AUTHOR-RESPONSE{round_suffix}.md`
2. Suggest a research phase to execute the calculation:

```
### New Calculations Needed

| ID | Requested By | Description | Suggested Phase |
|----|-------------|-------------|-----------------|
| NC-1 | Referee 1, Comment 3 | Extend to next-to-leading order | gpd:insert-phase {N}.1 |
| NC-2 | Referee 2, Comment 5 | Compare with Monte Carlo results | gpd:add-phase |

Create these phases now? The referee response will be incomplete until
new calculations are done.

Options:
1. Create phases now — then execute them before continuing response
2. Skip for now — draft responses for Groups A and B first, return to C later
3. Mark as "beyond scope" — explain in response why calculation is not feasible
```

If user chooses option 1:

```bash
# For each new calculation, create a phase
gpd phase add "Referee revision: {description}"
```

The user should run `gpd:plan-phase` and `gpd:execute-phase` for each new phase, then return to `gpd:respond-to-referees` to continue.

If the staged decision artifacts indicate that the main problem is overclaiming rather than missing computation, prefer narrowing the claim set or venue framing before creating new research phases.
If selected protocol bundles already identify a decisive comparison, benchmark anchor, or estimator caveat that the manuscript failed to surface, prefer fulfilling that existing obligation or narrowing the claim before creating broader new-computation work.
Do not create new phases solely to satisfy a speculative side quest once narrowing the manuscript claim would fully resolve the issue.

</step>

<step name="draft_responses">
**Draft responses for all Group A and Group B items:**

Resolve writer model:

```bash
WRITER_MODEL=$(gpd resolve-model gpd-paper-writer)
```

**For Group A (response-only) items:**

Draft each response in `GPD/AUTHOR-RESPONSE{round_suffix}.md`, then mirror the polished journal-facing wording into `GPD/review/REFEREE_RESPONSE{round_suffix}.md`. For each comment:

- Quote the referee's exact words
- Write the assessment (is the referee correct, partially correct, or mistaken?)
- Draft a respectful, specific response
- Note "No manuscript change needed" in the changes section
- Set status to "Response drafted"

**For Group B (manuscript revision) items:**

Group revision items by affected section to minimize agent spawns. For each affected section, spawn a paper-writer agent:
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

Apply the shared publication round and response contracts exactly for the response-artifact pair. The workflow-specific addition for each section handoff is that the same fresh child return must also name the revised section file.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\nRead the canonical <author_response> protocol at {GPD_INSTALL_DIR}/templates/paper/author-response.md, the canonical referee response template at {GPD_INSTALL_DIR}/templates/paper/referee-response.md, and the shared publication response-writer handoff at {GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md. You own both the manuscript edits and the response-tracker updates for this section. Make the manuscript changes first, then update the response trackers for the same comments. If you need user input, return `status: checkpoint` and stop; do not wait inside this run. Return only after the fresh `gpd_return.files_written` set names the revised section file plus `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`; stale pre-existing edits do not count.\n\n<autonomy_mode>{AUTONOMY}</autonomy_mode>\n<research_mode>{RESEARCH_MODE}</research_mode>\n" + revision_prompt,
  subagent_type="gpd-paper-writer",
  model="{writer_model}",
  readonly=false,
  description="Revise: {section_name}"
)
```

Each revision agent receives:

- The specific referee comments affecting this section (with full quotes)
- The current section text (read from the resolved section file within the manuscript tree rooted at `${PAPER_DIR}`, allowing nested subdirectories)
- The planned response strategy for each comment
- Explicit ownership of both the manuscript edits and the response-tracker updates for this section; the paper-writer must not treat the handoff as complete until both are written
- Relevant `GPD/comparisons/*-COMPARISON.md` files and `FIGURE_TRACKER.md` entries for decisive claims mentioned in the section
- `protocol_bundle_context` and `selected_protocol_bundle_ids` as additive specialized guidance only; they help preserve benchmark anchors, decisive artifacts, and estimator caveats during revision, but do not create new claims or replace the review ledger
- Instruction to make minimal, targeted changes (do NOT rewrite the section)
- Instruction to mark changed text with `% REVISED: Referee X, Comment Y` LaTeX comments for tracking

**If a revision agent fails to spawn or returns an error:** Note the failure for that section. Continue with other sections. After all agents complete, report which sections failed and offer: 1) Retry failed sections, 2) Apply revisions manually in the main context, 3) Skip failed sections and proceed. Do not block the entire referee response on a single section failure.

After each agent returns, verify the promised artifacts before trusting the handoff text:
- Re-apply the shared publication response-artifact contract first; for this workflow, the same fresh child return must also name the revised section file for the affected section.
- Check the fresh child `gpd_return.files_written` first; the section is complete only when it names the revised section file plus both response artifacts.
- Re-read the targeted resolved section file under `${PAPER_DIR}` and confirm the expected revision markers or substantive edits landed.
- Re-open `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md` and confirm the affected comment block now contains the updated assessment / changes-made text.
- If the section file changed but the response trackers did not, or vice versa, treat that section as failed and route it through the retry/manual options above instead of silently proceeding.
- If the agent claimed success but the files did not change, treat that section as failed and route it through the retry/manual options above instead of silently proceeding.

Only after those checks pass, update both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`:
- Fill in "Changes made" with specific locations (section, page, equation)
- Set status to "Response drafted"

</step>

<step name="revision_loop">
**Bounded revision verification (max 3 iterations):**

After all Group B revisions are applied, verify the revised manuscript compiles and is internally consistent:

```bash
cd "${PAPER_DIR}"
pdflatex -interaction=nonstopmode "${MANUSCRIPT_BASENAME}" 2>&1 | tail -20
bibtex "${MANUSCRIPT_BASENAME%.*}" 2>&1 | tail -10
pdflatex -interaction=nonstopmode "${MANUSCRIPT_BASENAME}" 2>&1 | tail -5
```

**If compilation errors:** Fix and retry (does not count as iteration).

**Consistency check (counts as iteration):**

1. Verify notation consistency in revised sections
2. Check that new equations are numbered and referenced correctly
3. Verify new citations exist in .bib file — for any NEW citations added during revision, verify metadata accuracy (author, year, journal) via `gpd pattern search` or web search. Referee-suggested references are usually real but may have wrong metadata.
4. Check cross-references to new or renumbered equations/figures
5. Resolve any `MISSING:` citation markers left by the paper-writer (see write-paper workflow for the resolution protocol)
6. Re-check any decisive `comparison_verdicts` or benchmark anchors touched by the revision. If protocol bundles are selected, use them only as an additive reminder of which decisive comparisons or estimator caveats must remain visible after revision.
7. If the revision touched bibliography files or citation commands, refresh `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` before generating the response letter or proceeding to final review. Use `derived_manuscript_reference_status` as the quick read on what likely changed, but the manuscript-root bibliography audit remains authoritative for the round. Stale bibliography audits are not acceptable in a referee-response round. Confirm the refreshed JSON artifact exists before treating the round as complete.
8. If a spawned paper-writer returns `status: checkpoint`, stop after recording the checkpoint. Present it to the user and spawn a fresh continuation handoff after the user responds. Do not ask the child agent to wait inside the same run.

**If inconsistencies found and iteration < 3:**

Spawn targeted paper-writer agents to fix specific inconsistencies. Increment iteration count.

**If iteration >= 3:**

```
Revision loop reached maximum iterations (3).

Remaining issues ({N}):
{list of unresolved inconsistencies}

Options:
1. Proceed anyway (note issues in response letter)
2. Manually fix the remaining issues
```

</step>

<step name="generate_response_letter">
**Finalize the canonical response artifacts and generate an optional manuscript-local response letter companion:**

Apply the shared publication response-writer handoff exactly before treating the response-artifact pair as complete:

@{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md

Read the completed `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md` (all comments should have status "Response drafted" or "Final"). Treat those files as complete only if the expected mirrored artifacts exist on disk and the orchestrator has aggregated every section handoff: the revised section file exists, both response artifacts exist, and the fresh child `gpd_return.files_written` for that section names all required outputs. Do not rely on stale pre-existing edits or prose completion alone.
Those two Markdown artifacts under `GPD/` are the canonical required outputs for this workflow. `${PAPER_DIR}/response-letter.tex` or `${PAPER_DIR}/response-letter.md` is optional and should be generated only when the journal or user asked for a manuscript-local submission companion. If the manuscript subject is an explicit external artifact, keep auxiliary response outputs under `GPD/` and do not write sidecars beside that external manuscript unless the main integration later exposes a subject-local export hook.
If centralized preflight resolved a subject-owned publication root at `GPD/publication/{subject_slug}` for that explicit external subject, apply the same rule there: keep the canonical response pair under that managed root, not beside the manuscript, and do not infer a full publication-tree relocation from this bounded continuation path.

**If any Group C items are still pending:** Warn the user before generating:

```
{N} new calculations are still pending. The response letter will note these as
"work in progress." Complete them with gpd:execute-phase before resubmission.
```

If a manuscript-local response letter companion is required for a project-backed manuscript, write `${PAPER_DIR}/response-letter.tex` (or `.md` depending on journal requirements):

```latex
\documentclass[12pt]{article}
\usepackage[margin=1in]{geometry}

\begin{document}

\noindent Dear Editor,

\medskip

We thank the referees for their careful reading of our manuscript and their
constructive comments. We have revised the manuscript to address all points
raised. Below we provide point-by-point responses.

\bigskip

{For each referee:}

\section*{Response to Referee {N}}

{For each comment:}

\subsection*{Comment {N}.{M}}

\textit{``{referee comment text}''}

\medskip

{Response text}

{If changes made:}
\textbf{Changes:} {description of changes with section/equation references}

{End for each comment}
{End for each referee}

\section*{Summary of Changes}

\subsection*{Major changes}
\begin{enumerate}
{numbered list of significant changes}
\end{enumerate}

\subsection*{Minor changes}
\begin{enumerate}
{numbered list of minor changes}
\end{enumerate}

\bigskip
\noindent Sincerely,\\
{Authors}

\end{document}
```

</step>

<step name="commit_and_present">
**Commit all revision artifacts:**

```bash
COMMIT_FILES=(GPD/review/REFEREE_RESPONSE{round_suffix}.md GPD/AUTHOR-RESPONSE{round_suffix}.md)
if [ -f "${PAPER_DIR}/response-letter.tex" ]; then
  COMMIT_FILES+=("${PAPER_DIR}/response-letter.tex")
elif [ -f "${PAPER_DIR}/response-letter.md" ]; then
  COMMIT_FILES+=("${PAPER_DIR}/response-letter.md")
fi
while IFS= read -r FILE; do
  COMMIT_FILES+=("$FILE")
done < <(find "${PAPER_DIR}" -type f -name '*.tex' -print)
while IFS= read -r FILE; do
  COMMIT_FILES+=("$FILE")
done < <(find "${PAPER_DIR}" -type f -name '*.bib' -print)

PRE_CHECK=$(gpd pre-commit-check --files "${COMMIT_FILES[@]}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: referee response and manuscript revisions" \
  --files "${COMMIT_FILES[@]}"
```

**Present completion summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > REFEREE RESPONSE COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

### Progress

| Item | Status |
|------|--------|
| Referee 1 responses | {N}/{M} addressed |
| Referee 2 responses | {N}/{M} addressed |
| New calculations | {N}/{M} complete |
| Manuscript revised | {Done / Partial} |
| Canonical response artifacts | {Done / Partial} |
| Optional manuscript-local response letter | {Not requested / Draft / Done} |
| Compilation check | {Pass / Fail} |

### Files

- Structured response tracking: GPD/AUTHOR-RESPONSE{round_suffix}.md
- Journal-facing response letter source: GPD/review/REFEREE_RESPONSE{round_suffix}.md
- Optional manuscript-local response letter: `${PAPER_DIR}/response-letter.tex` or `${PAPER_DIR}/response-letter.md` when present
- Revised manuscript: {paper_dir}/*.tex

---

## Next Steps

{If all complete:}
1. Review canonical response artifacts: `cat GPD/review/REFEREE_RESPONSE{round_suffix}.md` and `cat GPD/AUTHOR-RESPONSE{round_suffix}.md`
2. If a manuscript-local response letter was requested, review it: `cat ${PAPER_DIR}/response-letter.tex` (or `.md`)
3. Build revised manuscript: `cd ${PAPER_DIR} && make`
4. If this round changed manuscript content, figures, citations, or reproducibility evidence, run `gpd:peer-review` next. A manuscript-changing referee-response round is not submission-ready until a fresh staged review clears the revised manuscript.
5. Run `gpd:arxiv-submission` only after that fresh staged review clears the revised manuscript.
6. Submit the revised manuscript and whatever response-letter form the journal actually requires

{If new calculations pending:}
1. Execute pending calculations:
   gpd:plan-phase {N}
   gpd:execute-phase {N}
2. Return here to incorporate results:
   gpd:respond-to-referees (will detect existing `GPD/review/REFEREE_RESPONSE{round_suffix}.md` / `GPD/AUTHOR-RESPONSE{round_suffix}.md`)

Recommend `gpd:peer-review` as the standalone re-review command once the revised manuscript compiles cleanly. For any round that changed the manuscript itself, that re-review is mandatory before `gpd:arxiv-submission`. This keeps revision rounds aligned with the referee agent's `REFEREE-REPORT-R{N}.md` protocol.

---
```

</step>

</process>

<anti_patterns>

- Don't ignore any referee comment, even trivial ones -- every point gets a response
- Don't be defensive or dismissive in responses (even when the referee is wrong)
- Don't make changes beyond what the referee requests (scope creep introduces new issues)
- Don't rewrite entire sections when a targeted edit suffices
- Don't skip the compilation check after revisions
- Don't submit without completing all "must address" items
- Don't generate the optional manuscript-local response letter companion before all Group A and B items are drafted
</anti_patterns>

<success_criteria>

- [ ] Referee reports parsed and structured
- [ ] All comments categorized (physics concern, clarity, etc.) and prioritized
- [ ] `GPD/review/REFEREE_RESPONSE{round_suffix}.md` and `GPD/AUTHOR-RESPONSE{round_suffix}.md` created with complete point-by-point structure
- [ ] Comments triaged into Groups A (response-only), B (revision), C (new calculation)
- [ ] Group C items routed to research phases (if any)
- [ ] All Group A responses drafted
- [ ] All Group B revisions applied via paper-writer agents
- [ ] Revised manuscript compiles without errors
- [ ] Internal consistency verified after revisions (max 3 iterations)
- [ ] Canonical response artifacts under `GPD/` finalized, with an optional manuscript-local response letter generated only when requested
- [ ] All artifacts committed
- [ ] Manuscript-changing rounds route back through `gpd:peer-review` before `gpd:arxiv-submission`
- [ ] User informed of next steps (resubmission or pending calculations)
</success_criteria>
