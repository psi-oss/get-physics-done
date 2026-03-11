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
   - existing slide assets (`slides/`, `presentation/`, `*.pptx`)

3. Build a shortlist of the most relevant source artifacts.

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
7. What should be emphasized?
   - paper narrative, derivation, results, figures, reproducibility, live demo, project status
8. Should speaker notes, backup slides, or a references appendix be included?
9. Does the user want a terse deck or a more verbose, self-explanatory one?

Do not ask questions the user already answered. If a format choice is still open, recommend one based on the source material and audience.
</step>

<step name="choose_format">
Choose the deck format/toolchain intentionally.

Default recommendations:

- **Beamer** for equation-heavy physics talks, paper presentations, or when existing LaTeX figures/macros should be reused.
- **Editable native deck** when the audience is broader, the user wants a collaborator-friendly `.pptx`, or a template already exists in slide form.
- **Markdown-based slides** when the user wants a lightweight, git-friendly deck and does not need a heavy template.

Rules:

- If the user supplied a template, follow it unless it is unusable.
- If the requested format cannot be produced reliably in the current runtime, say so plainly and propose the nearest high-fidelity alternative before proceeding.
- Do not install TeX, presentation tooling, or new dependencies without explicit user approval.
</step>

<step name="build_structure">
Create a narrative arc before writing slides.

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

- **Beamer:** create `slides/main.tex` and any needed local assets or bibliography files.
- **Editable native deck:** create the requested deck file when the runtime can author it reliably; otherwise fall back only after explaining the limitation and getting user approval.
- **Markdown-based slides:** create `slides/slides.md`.

If speaker notes are requested, write `slides/SPEAKER-NOTES.md`.

If backup slides or references are requested, include them explicitly in the outline and final deck source.
</step>

<step name="verify_output">
Perform a lightweight QA pass before handoff.

Check:

- audience fit and technical level match the brief
- slide count is reasonable for the duration
- the narrative has a clear beginning, middle, and end
- equations and figures are introduced with a point, not dumped
- filenames and output paths are explicit

If the format supports compilation or rendering and the needed tool is already installed, run it. If the tool is missing, do not install it silently; report the limitation instead.
</step>

<step name="report">
Return:

- the chosen format and rationale
- source artifacts used
- files created or updated under `slides/`
- unresolved assumptions, if any
- compile/render status
</step>

</process>
