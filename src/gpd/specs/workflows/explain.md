<workflow_goal>
Explain a requested physics concept rigorously and in context. The command must work both inside an initialized GPD project and from a standalone question.
</workflow_goal>

<step name="validate_context">
Run centralized command-context preflight first.

```bash
CONTEXT=$(gpd --raw validate command-context explain "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Parse the returned JSON.

- If `project_exists=true`, operate in project-context mode.
- If `project_exists=false`, require an explicit concept/topic from `$ARGUMENTS` and operate in standalone mode.
- If the request is empty or too vague to explain meaningfully, ask one clarifying question.
</step>

<step name="scope_request">
Determine what kind of explanation is needed.

1. Extract the core concept, method, notation, result, or paper title from `$ARGUMENTS`.
2. Infer the likely explanation goal:
   - Conceptual grounding for the active phase
   - Formal clarification of notation/equations
   - Method comparison before or during execution
   - Paper/context briefing
3. Choose the right depth:
   - Brief operational clarification if the request is narrow and local
   - Full conceptual + formal explanation if the request is broader or foundational
4. Generate a slug for the output file from the concept.

**Important:** Do not default to a generic textbook exposition. The explanation must answer why this matters in the user's current workflow or requested standalone task.
</step>

<step name="gather_project_context">
If project context exists, gather the minimum useful context packet before spawning the explainer.

```bash
INIT=$(gpd init progress --include project,state,roadmap,config)
```

Use the init payload to extract:

- Project title / milestone
- Current phase and next phase
- Whether work is paused or currently executing
- Research mode, autonomy mode, and model profile

Search the local workspace for relevant mentions of the requested concept:

```bash
rg -n -i --fixed-strings -- "{concept}" .gpd paper manuscript docs src 2>/dev/null | head -60
```

Also check for nearby high-value context when present:

- `.gpd/research-map/*.md`
- Current phase `PLAN.md`, `SUMMARY.md`, `RESEARCH.md`, `VERIFICATION.md`
- `paper/`, `manuscript/`, or `.gpd/paper/`
- Existing `.gpd/literature/*REVIEW.md`

If no project context exists, gather only the user request plus any relevant local files in the current working directory.

Create the output directory:

```bash
mkdir -p .gpd/explanations
```
</step>

<step name="spawn_explainer">
Resolve the explainer model:

```bash
EXPLAINER_MODEL=$(gpd resolve-model gpd-explainer)
```

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```markdown
<objective>
Explain the following concept rigorously and in context: {concept}
</objective>

<mode>
{project-context or standalone}
</mode>

<available_context>
- User request: {raw request}
- Project summary / roadmap / state excerpts when available
- Current phase, manuscript, or active process context when available
- Relevant local files and `rg` hits mentioning the concept
- Local conventions and notation artifacts when available
</available_context>

<requirements>
1. Start with the short answer in one paragraph.
2. Explain why this concept matters in the current project or requested task.
3. Build a prerequisite ladder so the explanation is scoped correctly.
4. Give the rigorous core: definition, physical meaning, assumptions, limits, and equations/derivation where needed.
5. Connect the concept to this project's files, conventions, current phase, or manuscript claims when available.
6. Distinguish established literature facts from project-specific assumptions or interpretations.
7. Include a literature guide with papers the user can open directly. Prefer arXiv abstract links when available; otherwise use DOI or INSPIRE links.
8. Never fabricate citations. If a reference is uncertain, mark it clearly as unverified instead of guessing.
9. Close with common confusions, failure modes, and the next questions the user should ask.
</requirements>

<output>
Write to: .gpd/explanations/{slug}-EXPLAIN.md

Structure:

- Frontmatter (`concept`, `date`, `mode`, `project_context`, `citation_status`)
- Executive Summary
- Why This Matters Here
- Prerequisites and Dependencies
- Core Explanation
- Formal Structure / Equations
- Project-Specific Connection
- Common Confusions and Failure Modes
- Literature Guide
  - Foundational papers
  - Practical/working references
  - Current frontier
- Suggested Follow-up Questions
</output>
```

```
task(
  prompt=filled_prompt,
  subagent_type="gpd-explainer",
  model="{explainer_model}",
  readonly=false,
  description="Explain {slug}"
)
```
</step>

<step name="verify_citations">
After the explanation is written, run the bibliographer on the produced explanation file.

Resolve bibliographer model:

```bash
BIBLIO_MODEL=$(gpd resolve-model gpd-bibliographer)
```

> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, perform the audit in the main context.

```
task(
  subagent_type="gpd-bibliographer",
  model="{biblio_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-bibliographer.md for your role and instructions.

Audit the citations in `.gpd/explanations/{slug}-EXPLAIN.md`.

For every paper or book in the Literature Guide:
1. Verify that the reference is real and relevant
2. Check title, authors, year, journal/arXiv metadata, and openable URL
3. Flag hallucinated, inaccurate, or weakly supported references
4. Write the audit to `.gpd/explanations/{slug}-CITATION-AUDIT.md`

Return `BIBLIOGRAPHY UPDATED` if all references are verified or corrected.
Return `CITATION ISSUES FOUND` if any references remain uncertain or invalid."
)
```

If `CITATION ISSUES FOUND`:

- Read the audit report
- Correct metadata in the explanation file where the fix is straightforward
- Remove or explicitly flag unresolved references
- Preserve the explanation, but never leave fabricated citations unmarked

If the bibliographer step fails entirely:

- Keep the explanation
- Set citation status to unverified in the final report
- Tell the user which file still needs manual checking
</step>

<step name="return_results">
Return to the orchestrator with:

- Explanation summary (3-6 lines)
- Report path
- Project anchor (current phase / manuscript / standalone)
- Citation verification status
- Best papers to open next

Format:

```markdown
## EXPLANATION COMPLETE

**Concept:** {concept}
**Report:** .gpd/explanations/{slug}-EXPLAIN.md
**Project anchor:** {current phase / manuscript / standalone}
**Citation verification:** {all verified | issues found in .gpd/explanations/{slug}-CITATION-AUDIT.md | unverified}

**Key takeaways:**

1. {takeaway}
2. {takeaway}
3. {takeaway}

**Papers to open next:**

1. {paper title} — {url}
2. {paper title} — {url}
3. {paper title} — {url}
```

If the concept remains ambiguous or critical context is missing:

```markdown
## CHECKPOINT REACHED

**Type:** clarification
**Need:** {what disambiguation is required}
**Why it matters:** {how the explanation would change}
```
</step>
