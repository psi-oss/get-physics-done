<purpose>
Create presentation slides from either a GPD project or the current workspace. The workflow should identify the best source material available, clarify the talk brief, choose an appropriate slide format, and produce concrete deck files under `slides/`.
</purpose>

<process>

<step name="inventory_context">
Inspect the workspace before asking questions.

1. Detect whether this is an initialized GPD project:
   - `.gpd/PROJECT.md`
   - `.gpd/ROADMAP.md`
   - `.gpd/STATE.md`

2. Scan for likely presentation inputs:
   - papers or drafts (`paper/`, `manuscript/`, `draft/`, `*.tex`, `*.pdf`)
   - notes and summaries (`README.md`, `*.md`, phase summaries)
   - figures (`*.png`, `*.pdf`, `*.svg`)
   - code and notebooks (`*.py`, `*.jl`, `*.ipynb`)
   - data tables (`*.csv`, `*.json`, `*.dat`, `*.h5`)
   - existing slide assets (`slides/`, `presentation/`, `deck/`, `*.pptx`, `*.odp`, `*.key`)

3. Build a shortlist of the most relevant source artifacts and read the highest-value ones before questioning:
   - project overview files (`PROJECT.md`, `README.md`, paper abstract/introduction)
   - the most informative figures/tables
   - any existing deck or template files
   - the main result or summary documents if present

4. Determine whether existing slide outputs already exist:
   - generated artifacts under `slides/`
   - an existing deck the user may want to extend
   - a template or branding package that should constrain the output

If neither a project context nor meaningful source material is present, stop and ask the user what the presentation should be based on before drafting anything.
</step>

<step name="establish_brief">
Use `$ARGUMENTS` plus the workspace inventory to infer what is already known, then ask only the missing high-value questions in one compact batch.

Critical questions to resolve:

1. What is the talk for?
   - conference talk, seminar, group meeting, collaborator update, defense, class, pitch, paper presentation, project walkthrough
2. Who is the audience?
   - specialists, broader physicists, students, interdisciplinary collaborators, non-technical stakeholders
3. How long is the talk?
   - exact duration or target slide count
4. What level of technical depth is expected?
   - conceptual, medium technical, derivation-heavy, code/data-heavy
5. What output format should be produced?
   - Beamer / LaTeX
   - editable deck / native slide format
   - markdown-based slides (Marp, reveal-style, or plain markdown)
6. Is there a required template, branding package, or existing deck to extend?
7. If existing slide artifacts were found, should they be refreshed, updated in place, or left untouched?
8. What should be emphasized?
   - paper narrative, derivation, results, figures, reproducibility, live demo, project status
9. Should speaker notes, backup slides, or a references appendix be included?
10. Does the user want a terse deck or a more verbose, self-explanatory one?

Do not ask questions the user already answered. If a format choice is still open, recommend one based on the source material and audience.

> **Platform note:** If `ask_user` is not available, ask the same missing questions inline in one compact batch and wait for the user's freeform response.
</step>

<step name="choose_format">
Choose the deck format/toolchain intentionally.

Default recommendations:

- **Beamer** for equation-heavy physics talks, paper presentations, or when existing LaTeX figures/macros should be reused.
- **Editable native deck** when the audience is broader, the user wants a collaborator-friendly `.pptx`, or a template already exists in slide form.
- **Markdown-based slides** when the user wants a lightweight, git-friendly deck and does not need a heavy template.

Rules:

- If the user supplied a template, follow it unless it is unusable.
- If an editable native deck is requested, only choose it when the current runtime can actually author that deck format reliably. Otherwise, say so plainly and propose Beamer or markdown as the nearest high-fidelity alternative before proceeding.
- For equation-heavy physics talks, default toward Beamer unless the user explicitly prefers another format.
- Do not install TeX, presentation tooling, or new dependencies without explicit user approval.
</step>

<step name="existing_outputs">
Handle existing slide outputs explicitly before writing anything new.

If `slides/` already exists or an existing deck/template was found:

```
Existing slide artifacts detected.

Choose one:
1. Refresh - replace the generated deck artifacts with a new deck for this brief
2. Update - extend or revise the existing deck/template in place
3. Skip - keep existing slide artifacts unchanged
```

If the user already made this choice in their request, do not ask again.

If "Skip": stop after reporting which existing artifacts were found.

If "Update": preserve reusable assets, keep the existing narrative where appropriate, and report exactly which files were revised.

If "Refresh": treat the old artifacts as reference material, but rewrite the target deck files from the new brief.
</step>

<step name="create_structure">
Create the output structure and lock the persistence policy.

Create `slides/` explicitly before writing files.

Do not modify `.gpd/STATE.md`, `.gpd/ROADMAP.md`, `.gpd/PROJECT.md`, or any project state files as part of this workflow.

Do not commit slide artifacts automatically. Leave the generated files in the workspace and report them clearly.

Use these deterministic templates as the starting structure:

- `{GPD_INSTALL_DIR}/templates/slides/presentation-brief.md`
- `{GPD_INSTALL_DIR}/templates/slides/outline.md`
- `{GPD_INSTALL_DIR}/templates/slides/slides.md`
- `{GPD_INSTALL_DIR}/templates/slides/speaker-notes.md`
- `{GPD_INSTALL_DIR}/templates/slides/main.tex`
</step>

<step name="build_structure">
Create a narrative arc before writing the deck source.

At minimum, produce `slides/PRESENTATION-BRIEF.md` with:

- working title
- audience
- duration / target slide count
- chosen format
- primary takeaway
- source artifacts used
- constraints and assumptions

Then produce `slides/OUTLINE.md` with an ordered slide plan.

Use the shortest structure that still serves the goal. Typical flows:

- **Paper talk:** problem -> setup -> method -> main result -> interpretation -> limitations -> outlook
- **Group update:** status -> what changed -> evidence -> blockers -> next steps
- **Technical walkthrough:** motivation -> architecture/model -> key derivation or algorithm -> results -> implementation details -> takeaways

Keep slides sparse. Prefer figures, equations, and claims over paragraphs.
</step>

<step name="materialize_deck">
Write concrete slide artifacts under `slides/`.

Always write:

- `slides/PRESENTATION-BRIEF.md`
- `slides/OUTLINE.md`

Then branch by chosen format:

- **Beamer:** create `slides/main.tex` from the Beamer template and any needed local assets or bibliography files. Reuse existing LaTeX macros or figure paths when they improve fidelity.
- **Editable native deck:** create the requested deck file only when the runtime can author it reliably. If not, pause and get approval before falling back to Beamer or markdown.
- **Markdown-based slides:** create `slides/slides.md`.

If speaker notes are requested, write `slides/SPEAKER-NOTES.md`.

If backup slides or references are requested, include them explicitly in the outline and final deck source.

Never claim to have produced an editable native deck unless the corresponding deck file was actually written.
</step>

<step name="verify_output">
Perform a lightweight QA pass before handoff.

Check:

- audience fit and technical level match the brief
- slide count is reasonable for the duration
- the narrative has a clear beginning, middle, and end
- equations and figures are introduced with a point, not dumped
- filenames and output paths are explicit

If the format supports compilation or rendering and the needed tool is already installed, run it:

- Beamer: `latexmk`, `pdflatex`, `xelatex`, or `lualatex`
- Markdown slides: any already-installed renderer (for example Marp, Quarto, Pandoc, or reveal tooling)

If the tool is missing, do not install it silently; report the limitation instead.
</step>

<step name="report">
Return:

- the chosen format and rationale
- source artifacts used
- whether the workflow refreshed, updated, or skipped existing slide assets
- files created or updated under `slides/`
- unresolved assumptions, if any
- compile/render status
- explicit note that no automatic git commit was made
</step>

</process>
