<purpose>
Structure a point-by-point response to referee reports and revise the manuscript accordingly. Handles the full revision pipeline: parsing referee comments, drafting responses, spawning revision agents for manuscript changes, tracking new calculations, and producing a response letter. Integrates with the GPD research workflow for any new calculations requested by referees.

Called from $gpd-respond-to-referees command. Section revisions are performed by gpd-paper-writer agents.
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

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`.

**Read mode settings:**

```bash
AUTONOMY=$(gpd config get autonomy --raw 2>/dev/null || echo "guided")
```

**Mode-aware behavior:**
- `autonomy=supervised`: Pause after each referee point for user review of proposed response.
- `autonomy=guided` (default): Pause only for major revision requests requiring new calculations or significant changes.
- `autonomy=autonomous`: Draft complete response document, present for review at end.
- `autonomy=yolo`: Draft response and apply manuscript changes without pausing.

**If `project_exists` is false:**

```
ERROR: No project found.

Responding to referees requires a project with a completed manuscript.
Run $gpd-new-project first.
```

Exit.

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

Run $gpd-write-paper first to generate a manuscript from research results.
```

Exit.

**Convention verification** — referee responses must use the same conventions as the paper:

```bash
CONV_CHECK=$(gpd convention check --raw 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — resolve before drafting referee responses"
  echo "$CONV_CHECK"
fi
```

If the check fails, resolve convention mismatches before proceeding. New calculations or derivations in the response must use the same conventions as the published manuscript.

**Check for existing referee response file:**

```bash
ls .gpd/paper/REFEREE_RESPONSE*.md 2>/dev/null
```

If found, load as continuation context (user may be resuming an interrupted session).
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

Confirm parsing is correct, or paste corrections.
```

</step>

<step name="create_response_file">
**Create the structured referee response document:**

Read the template:

```bash
cat {GPD_INSTALL_DIR}/templates/paper/referee-response.md
```

Create `.gpd/paper/REFEREE_RESPONSE.md` using the template structure, populated with:

- Paper metadata (journal, manuscript ID, dates)
- Decision summary from editor
- Each referee comment with full quote, category, priority
- Empty response and changes-made fields (to be filled in subsequent steps)
- Progress tracking table

For second-round responses, create `REFEREE_RESPONSE_R2.md` instead.

```bash
mkdir -p .gpd/paper
```

Commit the initial response file:

```bash
PRE_CHECK=$(gpd pre-commit-check --files .gpd/paper/REFEREE_RESPONSE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: create referee response structure" \
  --files .gpd/paper/REFEREE_RESPONSE.md
```

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

Present triage:

```
### Triage Summary

| Group | Count | Action |
|-------|-------|--------|
| A: Response-only | {N} | Draft responses (no manuscript change) |
| B: Manuscript revision | {N} | Spawn paper-writer agents for section edits |
| C: New calculations | {N} | Create research phases via $gpd-add-phase |

Group C items require research work before the response can be completed.
Address these first? (Y/n)
```

</step>

<step name="handle_new_calculations">
**For Group C items (new calculations requested by referees):**

If no Group C items: skip to draft_responses.

For each new calculation:

1. Create an entry in the "New Calculations Summary" table in REFEREE_RESPONSE.md
2. Suggest a research phase to execute the calculation:

```
### New Calculations Needed

| ID | Requested By | Description | Suggested Phase |
|----|-------------|-------------|-----------------|
| NC-1 | Referee 1, Comment 3 | Extend to next-to-leading order | $gpd-insert-phase {N}.1 |
| NC-2 | Referee 2, Comment 5 | Compare with Monte Carlo results | $gpd-add-phase |

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

The user should run `$gpd-plan-phase` and `$gpd-execute-phase` for each new phase, then return to `$gpd-respond-to-referees` to continue.

</step>

<step name="draft_responses">
**Draft responses for all Group A and Group B items:**

Resolve writer model:

```bash
WRITER_MODEL=$(gpd resolve-model gpd-paper-writer --raw)
```

**For Group A (response-only) items:**

Draft each response directly in REFEREE_RESPONSE.md. For each comment:

- Quote the referee's exact words
- Write the assessment (is the referee correct, partially correct, or mistaken?)
- Draft a respectful, specific response
- Note "No manuscript change needed" in the changes section
- Set status to "Response drafted"

**For Group B (manuscript revision) items:**

Group revision items by affected section to minimize agent spawns. For each affected section, spawn a paper-writer agent:

> See `{GPD_INSTALL_DIR}/references/known-bugs.md` for workarounds to known platform bugs affecting subagent spawning.

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `Task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
Task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\n" + revision_prompt,
  subagent_type="gpd-paper-writer",
  model="{writer_model}",
  description="Revise: {section_name}"
)
```

Each revision agent receives:

- The specific referee comments affecting this section (with full quotes)
- The current section text (read from paper/{section}.tex)
- The planned response strategy for each comment
- Instruction to make minimal, targeted changes (do NOT rewrite the section)
- Instruction to mark changed text with `% REVISED: Referee X, Comment Y` LaTeX comments for tracking

**If a revision agent fails to spawn or returns an error:** Note the failure for that section. Continue with other sections. After all agents complete, report which sections failed and offer: 1) Retry failed sections, 2) Apply revisions manually in the main context, 3) Skip failed sections and proceed. Do not block the entire referee response on a single section failure.

After each agent returns, update REFEREE_RESPONSE.md:
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

Read the completed REFEREE_RESPONSE.md (all comments should have status "Response drafted" or "Final").

**If any Group C items are still pending:** Warn the user before generating:

```
{N} new calculations are still pending. The response letter will note these as
"work in progress." Complete them with $gpd-execute-phase before resubmission.
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
PRE_CHECK=$(gpd pre-commit-check --files .gpd/paper/REFEREE_RESPONSE.md paper/response-letter.tex ${PAPER_DIR}/*.tex ${PAPER_DIR}/references.bib 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: referee response and manuscript revisions" \
  --files .gpd/paper/REFEREE_RESPONSE.md paper/response-letter.tex ${PAPER_DIR}/*.tex ${PAPER_DIR}/references.bib
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

- Response tracking: .gpd/paper/REFEREE_RESPONSE.md
- Response letter: paper/response-letter.tex
- Revised manuscript: {paper_dir}/*.tex

---

## Next Steps

{If all complete:}
1. Review response letter: `cat paper/response-letter.tex`
2. Build revised manuscript: `cd paper && make`
3. `$gpd-arxiv-submission` — repackage for resubmission
4. Submit revised manuscript + response letter to journal

{If new calculations pending:}
1. Execute pending calculations:
   $gpd-plan-phase {N}
   $gpd-execute-phase {N}
2. Return here to incorporate results:
   $gpd-respond-to-referees (will detect existing REFEREE_RESPONSE.md)

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
- [ ] REFEREE_RESPONSE.md created with complete point-by-point structure
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
