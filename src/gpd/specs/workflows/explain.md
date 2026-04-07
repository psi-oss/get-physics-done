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
- If structured citation-source fields are present in init payloads, treat them as the preferred paper catalog for follow-up links and reference IDs.
- If the concept maps to a canonical stored result and the `result_id` is already known, prefer `gpd result show "{result_id}"` for the direct stored result view before dependency tracing. Use `gpd result deps "{result_id}"` when you need the upstream derivation chain, and `gpd result downstream "{result_id}"` when you need the reverse impact tree.
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
5. If structured citation-source metadata is available, prefer it over prose-only reference reconstruction when selecting papers to mention or link.
6. If a canonical `result_id` is already known, use `gpd result show "{result_id}"` before `gpd result deps "{result_id}"` when the explanation needs the direct stored result view. Use `gpd result downstream "{result_id}"` when the explanation needs to show what depends on the result.

**Important:** Do not default to a generic textbook exposition. The explanation must answer why this matters in the user's current workflow or requested standalone task.
</step>

<step name="gather_project_context">
If project context exists, gather the minimum useful context packet before spawning the explainer.

```bash
INIT=$(gpd --raw init progress --include project,state,roadmap,config)
```

Use the init payload to extract:

- Project title / milestone
- Current phase and next phase
- Whether work is paused or currently executing
- Research mode, autonomy mode, and model profile
- Any structured citation-source catalog fields such as `citation_source_files`, `citation_source_count`, and `derived_citation_sources`
- Any manuscript-local reference status surfaced as `derived_manuscript_reference_status` when the explanation is about the active paper or manuscript
- Any canonical result metadata you can recover through `gpd result search` when the concept maps to a derived equation, result, or quantity already stored in `intermediate_results`
- When a canonical `result_id` is already known, use `gpd result show "{result_id}"` before `gpd result deps "{result_id}"` so the explainer can ground the explanation on the stored result directly
- When the explanation needs reverse impact context, use `gpd result downstream "{result_id}"` to separate direct dependents from transitive dependents
- Any upstream dependency context you can recover through `gpd result deps "{result_id}"` once a canonical result has been identified and the explanation needs to show where it comes from

Search the local workspace for relevant mentions of the requested concept:

```bash
rg -n -i --fixed-strings -- "{concept}" GPD paper manuscript docs src 2>/dev/null | head -60
```

Also check for nearby high-value context when present:

- `GPD/research-map/*.md`
- Current phase `PLAN.md`, `SUMMARY.md`, `RESEARCH.md`, `VERIFICATION.md`
- `paper/`, `manuscript/`, or `draft/`
- Existing `GPD/literature/*REVIEW.md`
- Existing `GPD/literature/*-CITATION-SOURCES.json`
- Existing manuscript-local `BIBLIOGRAPHY-AUDIT.json` when available
- Existing canonical result entries surfaced by `gpd result search --text "{concept}"` or `gpd result search --equation "{concept}"`
- The recorded dependency chain from `gpd result deps "{result_id}"` when a canonical stored result is central to the explanation

If no project context exists, gather only the user request plus any relevant local files in the current working directory.

Create the output directory:

```bash
mkdir -p GPD/explanations
```
</step>

<step name="spawn_explainer">
Resolve the explainer model:

```bash
EXPLAINER_MODEL=$(gpd resolve-model gpd-explainer)
```

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

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
7. If structured citation-source metadata is available, use it to keep the literature guide tied to stable `reference_id` entries and openable URLs.
8. If a canonical `result_id` is already known, use `gpd result show "{result_id}"` before `gpd result deps "{result_id}"` when the direct stored result view is relevant. Use `gpd result downstream "{result_id}"` when the explanation needs the reverse dependency tree.
9. Include a literature guide with papers the user can open directly. Prefer arXiv abstract links when available; otherwise use DOI or INSPIRE links.
10. Never fabricate citations. If a reference is uncertain, mark it clearly as unverified instead of guessing.
11. Close with common confusions, failure modes, and the next questions the user should ask.
</requirements>

<output>
Write to: GPD/explanations/{slug}-EXPLAIN.md

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

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, perform the audit in the main context.

```
task(
  subagent_type="gpd-bibliographer",
  model="{biblio_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-bibliographer.md for your role and instructions.

Audit the citations in `GPD/explanations/{slug}-EXPLAIN.md`.

For every paper or book in the Literature Guide:
1. Verify that the reference is real and relevant
2. Check title, authors, year, journal/arXiv metadata, and openable URL
3. Flag hallucinated, inaccurate, or weakly supported references
4. Write the audit to `GPD/explanations/{slug}-CITATION-AUDIT.md`

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
**Report:** GPD/explanations/{slug}-EXPLAIN.md
**Project anchor:** {current phase / manuscript / standalone}
**Citation verification:** {all verified | issues found in GPD/explanations/{slug}-CITATION-AUDIT.md | unverified}

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
