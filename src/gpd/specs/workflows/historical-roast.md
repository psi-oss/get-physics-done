<purpose>
Run a source-backed, in-character historical roast of one manuscript or artifact
through one historical physicist or a comma-separated panel of physicists.
</purpose>

<boundary>
This workflow is intentionally lightweight. It is not `gpd:peer-review`, does
not write `REFEREE-DECISION.json`, and must not claim to be a formal journal
referee verdict. It writes auxiliary roast artifacts under
`GPD/historical-roast/` in the current workspace.

The user asked for a playful hackathon command, so lively historical voice is
welcome. Keep the physics critique real. Do not invent sources, direct quotes,
private beliefs, or facts about the named person.
</boundary>

<argument_contract>
The command uses one roaster-spec argument:

```text
gpd:historical-roast "Emmy Noether" paper/main.tex
gpd:historical-roast "Noether, Feynman, Dirac" draft/main.md
```

Do not support separate `--reviewer` or `--panel` flags. If either flag appears,
stop and give the corrected form:

```text
gpd:historical-roast "Noether, Feynman, Dirac" path/to/target
```

Parsing rules:

1. Treat the roaster spec as the named physicist span.
2. If a later argument span clearly looks like a target path, artifact file, or
   manuscript directory, treat that span as the roast target and everything
   before it as the roaster spec.
3. Target-like spans include existing paths, `paper`, `manuscript`, `draft`,
   `GPD/publication/*/manuscript`, or files ending in `.tex`, `.md`, `.txt`,
   `.pdf`, `.docx`, `.csv`, `.tsv`, `.xlsx`, or `.xlsm`.
4. If there is no target-like span, treat all arguments as the roaster spec and
   resolve the target from the current project manuscript family.
5. Split roaster spec on commas, trim whitespace, drop empty entries, and keep
   order. One name is single-reviewer mode. Two or more names is panel mode.
6. If the roaster spec is empty, ask for one historical physicist or a
   comma-separated panel.
</argument_contract>

<target_resolution>
Prefer an explicit target when provided. If no explicit target is provided,
look for the current project manuscript in this order:

1. manifest/config-resolved manuscript if obvious from `paper/`,
   `manuscript/`, or `draft/`
2. `paper/*.tex`, then `manuscript/*.tex`, then `draft/*.tex`
3. `paper/*.md`, then `manuscript/*.md`, then `draft/*.md`
4. `GPD/publication/*/manuscript/*.tex` or `.md`

Use shell and file search only for target discovery. Do not widen into arbitrary
workspace files. If no target resolves, ask for a specific target path.

For binary or tabular targets, prefer the artifact-text validator to extract a
reviewable text surface. Keep extracted target text under the run directory.
</target_resolution>

<artifact_layout>
Create a run directory:

```text
GPD/historical-roast/{reviewer-slug-or-panel-slug}/
```

If that directory already exists, append a date or numeric suffix rather than
overwriting prior work.

Write one dossier per reviewer:

```text
GPD/historical-roast/{run-slug}/{reviewer-slug}-DOSSIER.md
```

Write the final roast:

```text
GPD/historical-roast/{run-slug}/HISTORICAL-ROAST.md
```
</artifact_layout>

<source_dossier_protocol>
Before writing any in-character roast, gather source context for every named
physicist. Use `web_search` and, when useful, `web_fetch`.

For each reviewer, collect 2-4 reputable sources. Prefer:

- Nobel Prize, university, museum, archive, encyclopedia, or professional
  society pages
- the physicist's original papers, lectures, letters, or books when accessible
- reliable secondary sources about their scientific style and historical role

Wikipedia can help orientation but should not be the only source for a dossier.

Each dossier must include:

- source list with links
- documented research areas
- style signals: public writing/lecture habits, recurring phrases, or known
  intellectual temperament
- review lens: what this person would be unusually likely to notice
- caution line: what the workflow must not infer from the sources

Keep the dossier compact. The goal is enough source-backed flavor for a useful
review, not a biography.
</source_dossier_protocol>

<review_voice>
Write the review so it feels like the named reviewer is in the room. This can
be casual, sharp, funny, severe, playful, or dry when the sources support that
kind of voice. Do not copy long passages from sources. Do not fabricate direct
quotes. Do not claim certainty about what the historical person "would" think.

Use formulations like:

- "In a Noetherian mood, the first question is..."
- "A Feynman-flavored objection:"
- "Dirac would probably want the clutter removed until only the invariant
  statement remains."

Allowed: vivid stylistic emulation based on public persona and documented work.
Forbidden: fake quotations, biographical trivia as evidence, or letting the bit
replace physics criticism.
</review_voice>

<review_structure>
For a single reviewer, write `HISTORICAL-ROAST.md` with:

1. `# Historical Roast`
2. target path and roaster name
3. one-paragraph source-backed voice note
4. in-character roast
5. top objections
6. best praise
7. suggested fixes
8. short "where the bit stops" note naming the source limits

For panel mode, write:

1. `# Historical Roast Panel`
2. target path and ordered reviewer list
3. one short source-backed voice note per reviewer
4. one in-character section per reviewer
5. panel disagreement: where the reviewers would likely talk past each other
6. consensus action items
7. funniest or sharpest useful one-liner from each reviewer, clearly marked as
   generated style, not a quotation
8. short "where the bit stops" note naming the source limits

Every critique must tie back to the target artifact. A stylish complaint that
does not identify a concrete claim, equation, assumption, figure, paragraph, or
missing comparison is decoration; cut it or make it actionable.
</review_structure>

<completion>
In the final response, report:

- run directory
- dossier files
- final roast file
- the top 3-5 action items from the historical roast

Keep the final response short and make clear this is an auxiliary historical
roast, not the formal `peer-review` decision.
</completion>
