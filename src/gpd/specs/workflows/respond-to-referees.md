<purpose>
Structure a point-by-point response to referee reports and revise the manuscript accordingly. Handles the full revision pipeline: parsing referee comments, drafting responses, spawning revision agents for manuscript changes, tracking new calculations, and producing a response letter. Integrates with the GPD research workflow for any new calculations requested by referees.

Called from /gpd:respond-to-referees command. Section revisions are performed by gpd-paper-writer agents.
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
INIT=$(gpd init phase-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `project_contract`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`.

**Read mode settings:**

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after each referee point for user review of the proposed response.
- `autonomy=balanced` (default): Draft the full response and apply routine manuscript changes. Pause only for claim-level changes, new calculations, or unresolved referee disagreements.
- `autonomy=yolo`: Draft response and apply manuscript changes without pausing.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context respond-to-referees "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Run the centralized review preflight before continuing:

```bash
if [ -n "$ARGUMENTS" ]; then
  REVIEW_PREFLIGHT=$(gpd validate review-preflight respond-to-referees "$ARGUMENTS" --strict)
else
  REVIEW_PREFLIGHT=$(gpd validate review-preflight respond-to-referees --strict)
fi
if [ $? -ne 0 ]; then
  echo "$REVIEW_PREFLIGHT"
  exit 1
fi
```

If review preflight exits nonzero because of missing project state, missing manuscript or referee-report source, degraded review integrity, or missing required conventions, STOP and show the blocking issues before drafting responses.

**Locate paper directory:**

```bash
for DIR in paper manuscript draft; do
  if [ -f "${DIR}/main.tex" ]; then
    PAPER_DIR="$DIR"
    break
  fi
done
```

**If no paper found:**

```
No paper directory found. Searched: paper/, manuscript/, draft/

Run /gpd:write-paper first to generate a manuscript from research results.
```

Exit.

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
ls .gpd/paper/REFEREE_RESPONSE*.md 2>/dev/null
ls .gpd/AUTHOR-RESPONSE*.md 2>/dev/null
```

If found, load as continuation context (user may be resuming an interrupted session).

**Check for staged peer-review decision artifacts:**

```bash
ls .gpd/review/REVIEW-LEDGER*.json 2>/dev/null
ls .gpd/review/REFEREE-DECISION*.json 2>/dev/null
```

If matching round-specific files exist, load them as structured context. Use `REFEREE-REPORT*.md` as the canonical issue-ID source, and use `REVIEW-LEDGER*.json` / `REFEREE-DECISION*.json` to identify blocking issues, unsupported-claim findings, recommendation floors, and the referee's stated rationale.

Set `round_suffix` to match the peer-review artifact convention:

- `""` for the initial response round
- `"-R2"` for the second round
- `"-R3"` for the third round

Use that exact suffix for both `.gpd/AUTHOR-RESPONSE{round_suffix}.md` and `.gpd/paper/REFEREE_RESPONSE{round_suffix}.md`.
</step>

<step name="load_specialized_revision_context">
Use `protocol_bundle_context` from init JSON as additive revision guidance.

- If `selected_protocol_bundle_ids` is non-empty, keep the bundle's decisive artifact expectations, benchmark anchors, estimator caveats, and reference prompts visible while triaging referee requests.
- Use bundle guidance to distinguish "missing decisive evidence we already owed" from "new side quest the referee is asking for."
- Do **not** let bundle guidance justify broader claims, waive review-ledger blockers, or replace the manuscript's actual evidence trail in `.gpd/comparisons/*-COMPARISON.md`, `.gpd/paper/FIGURE_TRACKER.md`, phase `SUMMARY.md`, or `VERIFICATION.md`.
- Keep revisions tied to claims the manuscript still intends to make. Review ledgers and bundle hints help prioritize, but they do not force new side analyses once honest claim narrowing resolves the concern.
</step>

<step name="parse_referee_reports">
**Obtain referee reports from the user:**

Ask the user to provide referee reports via one of:

1. **Paste directly** -- user pastes report text into the conversation
2. **File path** -- user provides a path to the report file(s)
3. **Existing file** -- check `.gpd/paper/referee-report-*.md` or `paper/referee-reports/`

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

Do not invent new `REF-*` identifiers from the JSON artifacts. Instead, use them to prioritize and calibrate the responses to the issues already surfaced in `REFEREE-REPORT*.md`.

Present the parsed structure for user confirmation:

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

Read the template:

```bash
cat {GPD_INSTALL_DIR}/templates/paper/referee-response.md
```

Create both response artifacts for the current round:

- `.gpd/AUTHOR-RESPONSE{round_suffix}.md` — structured internal tracker keyed by `REF-*` issues, change locations, and staged review outcomes
- `.gpd/paper/REFEREE_RESPONSE{round_suffix}.md` — journal-facing response letter built from the template

Populate `.gpd/paper/REFEREE_RESPONSE{round_suffix}.md` with:

- Paper metadata (journal, manuscript ID, dates)
- Decision summary from editor
- Decision summary from `REFEREE-DECISION*.json` when available
- Each referee comment with full quote, category, priority
- Explicit list of blocking items from `REVIEW-LEDGER*.json` when available
- Empty response and changes-made fields (to be filled in subsequent steps)
- Progress tracking table

Populate `.gpd/AUTHOR-RESPONSE{round_suffix}.md` with:

- One section per `REF-*` issue
- Classification (`fixed`, `rebutted`, `acknowledged`, `needs-calculation`)
- Exact manuscript change locations or planned follow-up work
- Any blocking / recommendation-floor context imported from `REVIEW-LEDGER*.json` or `REFEREE-DECISION*.json`

For later rounds, use the round-specific variants (for example `REFEREE_RESPONSE-R2.md` and `AUTHOR-RESPONSE-R2.md`).

```bash
mkdir -p .gpd/paper
```

Commit the initial response file:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/paper/REFEREE_RESPONSE{round_suffix}.md .gpd/AUTHOR-RESPONSE{round_suffix}.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: create referee response structure" \
  --files .gpd/paper/REFEREE_RESPONSE{round_suffix}.md .gpd/AUTHOR-RESPONSE{round_suffix}.md
```

Keep the two files synchronized for the rest of the workflow: draft issue-by-issue substance in `.gpd/AUTHOR-RESPONSE{round_suffix}.md`, and mirror the journal-facing prose into `.gpd/paper/REFEREE_RESPONSE{round_suffix}.md`.

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
| C: New calculations | {N} | Create research phases via /gpd:add-phase |

Group C items require research work before the response can be completed.
Address these first? (Y/n)
```

</step>

<step name="handle_new_calculations">
**For Group C items (new calculations requested by referees):**

If no Group C items: skip to draft_responses.

For each new calculation:

1. Create matching entries in the "New Calculations Summary" sections of `REFEREE_RESPONSE.md` and `AUTHOR-RESPONSE.md`
2. Suggest a research phase to execute the calculation:

```
### New Calculations Needed

| ID | Requested By | Description | Suggested Phase |
|----|-------------|-------------|-----------------|
| NC-1 | Referee 1, Comment 3 | Extend to next-to-leading order | /gpd:insert-phase {N}.1 |
| NC-2 | Referee 2, Comment 5 | Compare with Monte Carlo results | /gpd:add-phase |

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

The user should run `/gpd:plan-phase` and `/gpd:execute-phase` for each new phase, then return to `/gpd:respond-to-referees` to continue.

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

Draft each response in `AUTHOR-RESPONSE.md`, then mirror the polished journal-facing wording into `REFEREE_RESPONSE.md`. For each comment:

- Quote the referee's exact words
- Write the assessment (is the referee correct, partially correct, or mistaken?)
- Draft a respectful, specific response
- Note "No manuscript change needed" in the changes section
- Set status to "Response drafted"

**For Group B (manuscript revision) items:**

Group revision items by affected section to minimize agent spawns. For each affected section, spawn a paper-writer agent:
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\n" + revision_prompt,
  subagent_type="gpd-paper-writer",
  model="{writer_model}",
  readonly=false,
  description="Revise: {section_name}"
)
```

Each revision agent receives:

- The specific referee comments affecting this section (with full quotes)
- The current section text (read from paper/{section}.tex)
- The planned response strategy for each comment
- Relevant `.gpd/comparisons/*-COMPARISON.md` files and `FIGURE_TRACKER.md` entries for decisive claims mentioned in the section
- `protocol_bundle_context` and `selected_protocol_bundle_ids` as additive specialized guidance only; they help preserve benchmark anchors, decisive artifacts, and estimator caveats during revision, but do not create new claims or replace the review ledger
- Instruction to make minimal, targeted changes (do NOT rewrite the section)
- Instruction to mark changed text with `% REVISED: Referee X, Comment Y` LaTeX comments for tracking

**If a revision agent fails to spawn or returns an error:** Note the failure for that section. Continue with other sections. After all agents complete, report which sections failed and offer: 1) Retry failed sections, 2) Apply revisions manually in the main context, 3) Skip failed sections and proceed. Do not block the entire referee response on a single section failure.

After each agent returns, verify the promised artifacts before trusting the handoff text:
- Re-read the targeted `paper/{section}.tex` file and confirm the expected revision markers or substantive edits landed.
- Re-open `AUTHOR-RESPONSE.md` and `REFEREE_RESPONSE.md` and confirm the affected comment block now contains the updated assessment / changes-made text.
- If the agent claimed success but the files did not change, treat that section as failed and route it through the retry/manual options above instead of silently proceeding.

Only after those checks pass, update both `AUTHOR-RESPONSE.md` and `REFEREE_RESPONSE.md`:
- Fill in "Changes made" with specific locations (section, page, equation)
- Set status to "Response drafted"

</step>

<step name="revision_loop">
**Bounded revision verification (max 3 iterations):**

After all Group B revisions are applied, verify the revised manuscript compiles and is internally consistent:

```bash
cd "${PAPER_DIR}"
pdflatex -interaction=nonstopmode main.tex 2>&1 | tail -20
bibtex main 2>&1 | tail -10
pdflatex -interaction=nonstopmode main.tex 2>&1 | tail -5
```

**If compilation errors:** Fix and retry (does not count as iteration).

**Consistency check (counts as iteration):**

1. Verify notation consistency in revised sections
2. Check that new equations are numbered and referenced correctly
3. Verify new citations exist in .bib file — for any NEW citations added during revision, verify metadata accuracy (author, year, journal) via `gpd pattern search` or web search. Referee-suggested references are usually real but may have wrong metadata.
4. Check cross-references to new or renumbered equations/figures
5. Resolve any `MISSING:` citation markers left by the paper-writer (see write-paper workflow for the resolution protocol)
6. Re-check any decisive `comparison_verdicts` or benchmark anchors touched by the revision. If protocol bundles are selected, use them only as an additive reminder of which decisive comparisons or estimator caveats must remain visible after revision.

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
**Generate the response letter to the editor:**

Read the completed `AUTHOR-RESPONSE.md` and `REFEREE_RESPONSE.md` (all comments should have status "Response drafted" or "Final").

**If any Group C items are still pending:** Warn the user before generating:

```
{N} new calculations are still pending. The response letter will note these as
"work in progress." Complete them with /gpd:execute-phase before resubmission.
```

Write `paper/response-letter.tex` (or `.md` depending on journal requirements):

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
PRE_CHECK=$(gpd pre-commit-check --files .gpd/paper/REFEREE_RESPONSE.md .gpd/AUTHOR-RESPONSE.md paper/response-letter.tex ${PAPER_DIR}/*.tex ${PAPER_DIR}/references.bib 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: referee response and manuscript revisions" \
  --files .gpd/paper/REFEREE_RESPONSE.md .gpd/AUTHOR-RESPONSE.md paper/response-letter.tex ${PAPER_DIR}/*.tex ${PAPER_DIR}/references.bib
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
| Response letter | {Done / Draft} |
| Compilation check | {Pass / Fail} |

### Files

- Structured response tracking: .gpd/AUTHOR-RESPONSE.md
- Journal-facing response letter source: .gpd/paper/REFEREE_RESPONSE.md
- Response letter: paper/response-letter.tex
- Revised manuscript: {paper_dir}/*.tex

---

## Next Steps

{If all complete:}
1. Review response letter: `cat paper/response-letter.tex`
2. Build revised manuscript: `cd paper && make`
3. `/gpd:arxiv-submission` — repackage for resubmission
4. `/gpd:peer-review` — optional re-review before final packaging if the revision was substantial
5. Submit revised manuscript + response letter to journal

{If new calculations pending:}
1. Execute pending calculations:
   /gpd:plan-phase {N}
   /gpd:execute-phase {N}
2. Return here to incorporate results:
   /gpd:respond-to-referees (will detect existing REFEREE_RESPONSE.md / AUTHOR-RESPONSE.md)

Recommend `/gpd:peer-review` as the standalone re-review command once the revised manuscript compiles cleanly. This keeps revision rounds aligned with the referee agent's `REFEREE-REPORT-R{N}.md` protocol.

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
- Don't generate the response letter before all Group A and B items are drafted
</anti_patterns>

<success_criteria>

- [ ] Referee reports parsed and structured
- [ ] All comments categorized (physics concern, clarity, etc.) and prioritized
- [ ] REFEREE_RESPONSE.md and AUTHOR-RESPONSE.md created with complete point-by-point structure
- [ ] Comments triaged into Groups A (response-only), B (revision), C (new calculation)
- [ ] Group C items routed to research phases (if any)
- [ ] All Group A responses drafted
- [ ] All Group B revisions applied via paper-writer agents
- [ ] Revised manuscript compiles without errors
- [ ] Internal consistency verified after revisions (max 3 iterations)
- [ ] Response letter generated with all responses and change summary
- [ ] All artifacts committed
- [ ] User informed of next steps (resubmission or pending calculations)
</success_criteria>
