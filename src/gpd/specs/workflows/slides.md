<purpose>
Create presentation slides from either a GPD project or the current workspace. The workflow should identify the best source material available, clarify the talk brief, choose an appropriate slide format, and produce concrete deck files under `slides/`.
</purpose>

<process>

<step name="inventory_context">
Inspect the workspace before asking questions.

Command identity: this shared workflow is `gpd:slides`. Runtime-visible final blocks may render the active runtime's native command label. Shell/local bridge calls use the bare registry slug `slides`, e.g. `gpd --raw validate command-context slides -- "$ARGUMENTS"`.

1. Detect whether this is an initialized GPD project:
   - `GPD/PROJECT.md`
   - `GPD/ROADMAP.md`
   - `GPD/STATE.md`

2. Scan likely inputs: manuscripts/PDFs, notes, figures, code/notebooks, data tables, and existing decks/templates (`slides/`, `presentation/`, `deck/`, `*.pptx`, `*.odp`, `*.key`).
3. Read the highest-value shortlist before questioning: project overview, paper abstract/introduction, key figures/tables, existing deck/template, and main result/summary docs.
4. Determine whether generated slide outputs, an extendable deck, or a constraining template already exists.

If neither a project context nor meaningful source material is present, stop and ask the user what the presentation should be based on before drafting anything.
</step>

<step name="establish_brief">
Use `$ARGUMENTS` plus the workspace inventory to infer what is already known, then ask only the missing high-value questions in one compact batch.

Resolve only missing high-value fields: talk purpose, audience, duration/slide count, technical depth, output format, template/existing deck handling, emphasis, speaker notes/backup/references, and terse vs self-explanatory style. Do not ask questions the user already answered; if format is open, recommend from source material and audience.

> **Platform note:** If `ask_user` is not available, ask the same missing questions inline in one compact batch and wait for the user's freeform response.
</step>

<step name="choose_format">
Choose the deck format/toolchain intentionally.

Default format choice: Beamer for equation-heavy/paper talks or reusable LaTeX assets; editable native deck only when the runtime can author it reliably or a slide template requires it; markdown when lightweight/git-friendly output fits. Follow usable user templates, default equation-heavy talks to Beamer, and do not install TeX or deck tooling without approval.
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

Output boundary: `slides/` is the only durable write root for this workflow; never write deck artifacts under `exports/`, `GPD/publication/`, `GPD/review/`, manuscript roots, or temp dirs. Slides do not update project state and must not satisfy publication, peer-review, response, arXiv-package, or export gates.
Use context/init-selected project/workspace roots for nested launches; otherwise ask for a source/root. If the workspace is not a git checkout, report explicit outputs and `files_written` evidence instead of git status.

Do not modify `GPD/STATE.md`, `GPD/ROADMAP.md`, `GPD/PROJECT.md`, or any project state files as part of this workflow.

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

If the readable source is too thin for a polished seminar deck--for example, no derivation, figures, theorem/proof structure, or scientific narrative details are present--do not invent missing content. Either ask one compact clarification/source question before drafting, or label the output as a source-bound skeleton in `slides/PRESENTATION-BRIEF.md`, `slides/OUTLINE.md`, the deck title/subtitle or first slide, and final handoff evidence.
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

<step name="publication_framing">
Publication and response gates are target-bound for slides:

| Deck frame | Gate behavior |
|---|---|
| ordinary seminar/paper-talk/group/class/project deck | no publication gate; report `publication_root: not_applicable`, `review_root: not_applicable`, `review_state: not_required`, `response_state: not_required`, `checkpoint: none`, `next_step: none` |
| final/revised/submission/arXiv/referee-response deck | inspect selected review/response roots for the target manuscript |
| incomplete/stale response round | write draft-labeled slides only; report `checkpoint: response_gate`, `publication_root: not_applicable`, and `next_step: gpd:respond-to-referees --manuscript <resolved manuscript> --report <selected_publication_root>/REFEREE-REPORT{round_suffix}.md` |

Use the canonical referee report under `selected_publication_root` for `--report`; default project manuscripts use `GPD/REFEREE-REPORT{round_suffix}.md` or `GPD/REFEREE-REPORT.md`.
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
After Beamer compilation, keep only durable deck outputs: prefer a disposable build dir or runtime-native deletion for exact known aux files under `slides/` (`main.nav`, `main.snm`, `main.toc`, `main.out`, `main.aux`, `main.log`, `main.fls`, `main.fdb_latexmk`). Re-list `slides/` and include only durable artifacts in `files_written`.
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
