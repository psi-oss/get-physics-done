<purpose>
Build a robust private research persona candidate without silently changing
machine-local persona storage.

The workflow interviews the user only after explicit consent, ingests named
sources only after exact category/path consent, and emits a candidate
`ResearchPersonaPatch` JSON object for user approval. The approval and storage
mutation path is the local CLI sequence: `gpd research-persona validate`,
`gpd research-persona diff`, explicit approval, and
`gpd research-persona apply-patch`.

No silent memory: do not silently create, infer, or update persona memory from
ordinary chat context, source ingestion, project scans, or prior behavior.
Explicit user approval is required before mutation; do not apply-patch until
approval is given after the candidate patch and diff are reviewed.
</purpose>

<hard_boundaries>
- Never write `${GPD_DATA_DIR:-~/.gpd}/research-persona/profile.json` directly.
- Never run `gpd research-persona apply-patch` on the user's behalf unless the
  user explicitly asks after reviewing the candidate patch.
- Never infer permission to interview, inspect papers, inspect collaborators,
  inspect git history, or scan files from command invocation alone.
- Never read a paper path, BibTeX path, repository root, project file category,
  manual JSON patch, or user statement into persona ingestion until the user has
  approved that exact source category and path or text.
- Never include `never_prompt` facts in prompt-visible summaries.
- Treat collaborator names, unpublished project details, personal workflow
  habits, and sensitive preferences as private unless the user explicitly marks
  them `safe_to_share`.
- Prefer `private_local` for new facts unless the user chooses a narrower or
  broader privacy label.
</hard_boundaries>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before
starting. Use the local research-persona CLI controls as the storage authority:

- `gpd research-persona show --projection local|project-private|prompt|public`
- `gpd research-persona ingest-source SOURCE_JSON|- --output PATCH_JSON`
- `gpd research-persona validate [PROFILE_JSON|-]`
- `gpd research-persona diff PATCH_JSON|-`
- `gpd research-persona apply-patch PATCH_JSON|-`
- `gpd research-persona doppelganger --task "<task>"`
- `gpd research-persona explain-plan PLAN_JSON|- --task "<task>"`
- `gpd research-persona taste-check CANDIDATE_JSON|- --focus "<focus>"`
- `gpd research-persona forget <fact-id>`
- `gpd research-persona export-capsule --role planner|executor|verifier|paper_writer|literature|recovery|explainer|doppelganger|taste`
</required_reading>

<process>

<step name="load_existing_snapshot">
Inspect only the local persona shape and counts first. This read is allowed
because the user explicitly invoked persona building, but keep it local and do
not inject raw private content into later prompts.

```bash
PERSONA_STATUS=$(gpd --raw research-persona show --projection local)
if [ $? -ne 0 ]; then
  echo "$PERSONA_STATUS"
  # Continue with an empty-draft mindset only if the error says the profile is missing.
fi
```

Use this payload to avoid duplicate fact IDs and to know whether the user is
building from scratch or revising an existing profile. Do not copy raw profile
contents into delegated prompts or final prose.
</step>

<step name="consent_gate">
Before asking any interview questions or reading any source, ask for explicit
scope consent and record the source plan.

If `ask_user` is available, present exactly these mutually exclusive choices:

- `Interview only` -- ask focused questions; do not inspect local files.
- `Current project` -- read only approved project categories after listing them.
- `Paper path` -- read one approved paper or manuscript path.
- `BibTeX path` -- read one approved bibliography path.
- `Repository scan` -- inspect one approved repository root with narrow search.
- `Manual JSON patch` -- validate and review one approved patch path.
- `User statement` -- capture a direct user-provided statement as a source.
- `Stop` -- do not collect persona facts.

If `ask_user` is not available, present the same options in plain text and wait
for a freeform response.

If the user chooses `Stop`, end without emitting a patch.

For every source mode, ask one concrete follow-up before reading:

- Interview: confirm the topics to ask about.
- Current project: list exact path categories such as `GPD/STATE.md`,
  `GPD/ROADMAP.md`, `GPD/knowledge/*.md`, `GPD/literature/*.md`, manuscript
  files, package metadata, or selected reference files.
- Paper path: ask for the exact paper path and confirm it back.
- BibTeX path: ask for the exact `.bib` path and confirm it back.
- Repository scan: ask for the exact repository root and scan categories.
- Manual JSON patch: ask for the exact patch path and confirm it is only a
  candidate patch review.
- User statement: ask for the exact statement text and whether to store it as a
  direct source.

Only read categories, paths, or text the user approved in this persona-building
run.
</step>

<step name="interview">
Ask a compact interview tailored to the requested scope. Do not ask all
questions if the user's answers already resolve the scope.

Cover these dimensions when relevant:

1. Research areas, subfields, and current problems.
2. Expertise level by axis: mathematical, computational, experimental,
   theoretical, applied, literature/navigation, and writing/publication.
3. Preferred explanation style: abstraction level, derivation density, code
   detail, examples, notation strictness, and citation depth.
4. Scientific taste: what the user sees as elegant, suspicious, promising,
   boring, overfit, under-justified, or worth pursuing.
5. Workstyle: cadence, checkpoint preference, tolerance for autonomous action,
   preferred tools, languages, notebooks, symbolic/numeric packages, and
   testing expectations.
6. Papers, collaborators, references, datasets, software, or groups the user
   wants remembered.
7. Privacy defaults: which items are `private_local`, `project_private`,
   `safe_to_share`, `session_only`, or `never_prompt`.

Keep questions grouped. When an answer contains sensitive personal details, ask
whether to store that item at all and which privacy label to use.
</step>

<step name="source_ingestion">
If the user approved a source mode, turn that explicit source into a candidate
patch through the local CLI bridge. Use `gpd research-persona ingest-source`
for source-derived candidate patches; do not bypass it with direct persona
state edits.

Source-mode mapping:

- `interview`: use for structured interview answers.
- `user_statement`: use for a direct statement the user wants captured.
- `project_scan`: use for approved current-project categories only.
- `paper_import`: use for an approved paper or manuscript path.
- `bibtex_import`: use for an approved BibTeX path.
- `repo_scan`: use for an approved repository root and scan category list.
- `manual_patch`: use for an approved candidate JSON patch path.

CLI bridge examples:

The CLI shape is `gpd research-persona ingest-source SOURCE_JSON|- --output
PATCH_JSON`. The source kind belongs inside the JSON payload; do not use
nonexistent source-mode flags on the CLI.

```bash
printf '%s\n' '{"source_kind":"interview","text":"<approved interview summary>"}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
printf '%s\n' '{"source_kind":"user_statement","text":"<approved user statement>"}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
printf '%s\n' '{"source_kind":"project_scan","path":"<approved project root>","metadata":{"scan_categories":"<approved categories>"}}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
printf '%s\n' '{"source_kind":"paper_import","path":"<approved paper path>"}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
printf '%s\n' '{"source_kind":"bibtex_import","path":"<approved bibtex path>"}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
printf '%s\n' '{"source_kind":"repo_scan","path":"<approved repo root>","metadata":{"scan_categories":"<approved categories>"}}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
printf '%s\n' '{"source_kind":"manual_patch","path":"<approved patch path>"}' | gpd research-persona ingest-source - --output /tmp/research-persona-source-patch.json
```

If the source mode is current project or repository scan, perform a narrow
read-only survey of only approved paths before invoking the bridge. Use this
survey to propose candidate facts; never treat it as confirmed ground truth
unless the user confirms it.

Useful read-only checks include:

```bash
find GPD -maxdepth 3 -type f 2>/dev/null | sort | head -80
rg -n --glob '*.md' --glob '*.tex' --glob 'pyproject.toml' --glob 'package.json' --glob 'Cargo.toml' "arXiv|doi|collaborat|author|method|theorem|simulation|experiment|notebook|pytest|ruff|numpy|jax|mathematica|wolfram|latex" . 2>/dev/null | head -120
```

Do not inspect private credential files, environment files, browser caches,
home-directory documents, email, chat exports, or git remotes unless the user
explicitly names those exact sources for this persona-building run.

For paper and BibTeX ingestion, read only the approved path. Do not chase
external links, sibling drafts, citation PDFs, or collaborator files unless the
user approves those exact additional sources.

For manual JSON patch ingestion, treat the input as untrusted. Validate its
schema and privacy labels through the CLI bridge, then route any resulting
candidate through the same review sequence as every other source.
</step>

<step name="draft_patch">
Merge confirmed interview answers, user-approved scan inferences, and any
candidate emitted by `gpd research-persona ingest-source` into a single
candidate `ResearchPersonaPatch` JSON object.

Patch requirements:

- Top-level `schema_version` is `1`.
- Use `source_kind: "interview"` for structured interview answers.
- Use `source_kind: "user_statement"` for direct statements the user asked to
  capture as persona facts.
- Use `source_kind: "project_scan"` for consented local evidence, with
  `confidence: "inferred"` unless the user confirmed the fact.
- Use `source_kind: "paper_import"` for approved paper or manuscript paths.
- Use `source_kind: "bibtex_import"` for approved bibliography paths.
- Use `source_kind: "repo_scan"` for approved repository scans.
- Use `source_kind: "manual_patch"` for approved candidate patch review.
- Prefer stable fact IDs such as `interest.quantum-field-theory`,
  `expertise.math.derivations`, `workstyle.tests.pytest`, or
  `taste.prefers-mechanistic-explanations`.
- Use `add_fact`, `replace_fact`, `add_axis`, `replace_axis`, `add_list_item`,
  `remove_list_item`, or pointer operations supported by the research-persona
  patch schema.
- Include `sources`, `privacy`, `confidence`, and `updated_at` on every fact.
- Use `safe_to_share` only when the user explicitly chooses it.
- Use `never_prompt` for facts that may be retained locally for audit or
  duplicate suppression but must never enter prompt capsules.
- Keep collaborator and unpublished-project facts `private_local` or
  `project_private` unless the user explicitly chooses otherwise.

For scientific-taste facts, capture preferences as reviewable hypotheses, not
identity claims. Example categories include:

- `taste.values_elegant_minimal_models`
- `taste.suspicious_of_unchecked_numerics`
- `taste.prefers_first_principles_derivations`
- `taste.likes_cross_regime_consistency_checks`

For Researcher Doppelganger support, include only user-approved style and taste
facts that help a future role critique plans in the user's voice. Do not invent
personal opinions.

For Expertise-Aware Explanations support, include explanation-depth facts and
axes that help future explainers choose prerequisite level, math density, code
examples, and citation depth.
</step>

<step name="validate_candidate">
Write the candidate patch to the response as a fenced JSON block or, if a local
temporary file is needed for review, use `/tmp` and keep it outside persona
storage. Then validate the current stored profile as a preflight and run a
read-only diff on the candidate patch before presenting it as ready:

```bash
gpd --raw research-persona validate
gpd --raw research-persona diff /tmp/research-persona-candidate-patch.json
```

If stored-profile validation or candidate-patch diff fails, fix the patch when
the error is in the candidate, or report the schema error and stop without
suggesting application.
</step>

<step name="present_for_approval">
Present:

1. A short summary of what the patch would add, replace, or remove.
2. The complete candidate `ResearchPersonaPatch` JSON.
3. The approval commands:

```bash
gpd research-persona validate
gpd research-persona diff /tmp/research-persona-candidate-patch.json
# wait for explicit user approval
gpd research-persona apply-patch /tmp/research-persona-candidate-patch.json
```

If no temporary file was written, tell the user they can pass the candidate
patch JSON through stdin for the patch-specific steps:

```bash
gpd research-persona validate
gpd research-persona diff -
# wait for explicit user approval
gpd research-persona apply-patch -
```

Make clear that `apply-patch` is the mutation step and must be user-approved.
Offer `gpd research-persona forget <fact-id>` for later deletion.
</step>

<step name="capsule_check_optional">
After the user approves and applies the patch, or if the user asks how an
already-applied persona affects future behavior, explain that projected capsules
are role-specific and privacy-filtered. The relevant local checks are:

```bash
gpd research-persona export-capsule --role planner
gpd research-persona export-capsule --role explainer
gpd research-persona export-capsule --role doppelganger
gpd research-persona export-capsule --role taste
gpd research-persona doppelganger --task "<current research decision>"
gpd research-persona explain-plan PLAN_JSON|- --task "<explanation target>"
gpd research-persona taste-check CANDIDATE_JSON|- --focus "<direction set>"
```

Do not run these against newly proposed facts until the user applies the patch.
These helpers are advisory previews over prompt-safe stored capsules; do not
read raw persona storage or pass raw private profile content to specialist
agents.
</step>

</process>

<success_criteria>
- [ ] Existing persona inspected only through local CLI projection
- [ ] Explicit consent collected before interview or source reads
- [ ] Source category and exact path/text approved before ingestion
- [ ] Source-derived candidates produced through `gpd research-persona ingest-source`
- [ ] Scans restricted to user-approved local path categories
- [ ] Candidate facts have source kind, confidence, privacy, and stable IDs
- [ ] Stored profile validates and candidate patch diffs through the local CLI
- [ ] Final answer includes the full candidate patch and validate -> diff -> explicit approval -> apply-patch route
- [ ] Post-apply guidance uses prompt-safe capsules or advisory helpers only
- [ ] No direct write to research-persona storage occurred
</success_criteria>
