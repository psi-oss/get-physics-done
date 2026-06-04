<purpose>
Convert explicitly approved persona sources into candidate patch artifacts
through the local research-persona CLI bridge.
</purpose>

<hard_boundaries>
- No silent memory: do not infer consent from command invocation, prior chat, or
  project presence.
- Do not read any source until the user has approved the exact source category
  and path or statement text for this run.
- Do not mutate persona storage in this stage.
- Do not place raw private persona profile content in prompts, child handoffs,
  summaries, or capsules.
- Keep `never_prompt` material out of prompt-visible summaries.
</hard_boundaries>

<source_modes>
Supported modes:

- `interview` for structured interview answers.
- `user_statement` for a direct user-provided statement.
- `project_scan` for approved current-project categories.
- `paper_import` for an approved paper or manuscript path.
- `bibtex_import` for an approved BibTeX path.
- `repo_scan` for an approved repository root and scan categories.
- `manual_patch` for an approved candidate JSON patch path.
</source_modes>

<process>
1. Re-state the approved source mode and exact path, category list, or statement
   before reading anything.
2. For current-project and repository scans, perform only narrow read-only
   searches inside approved categories. Do not inspect credential files,
   environment files, browser caches, home-directory documents, email, chat
   exports, or git remotes unless the user names that exact source.
3. For paper and BibTeX ingestion, read only the approved file path. Do not
   chase links, citation PDFs, sibling drafts, collaborator notes, or external
   downloads unless separately approved.
4. For manual JSON patch ingestion, treat the input as untrusted candidate data.
   Validate schema, source kinds, privacy labels, and confidence labels before
   merging it with any other candidate.
5. Invoke the CLI bridge to transform the source into a candidate patch:

The implemented CLI shape is:

```text
gpd research-persona ingest-source SOURCE_JSON|- --output PATCH_JSON
```

Place `source_kind` and all approved source handles in the JSON payload. Do not
use source-mode flags on the CLI.

```text
printf '%s\n' '{"source_kind":"interview","text":"<approved-summary>"}' | gpd research-persona ingest-source - --output <candidate-patch>
printf '%s\n' '{"source_kind":"user_statement","text":"<approved-statement>"}' | gpd research-persona ingest-source - --output <candidate-patch>
printf '%s\n' '{"source_kind":"project_scan","path":"<approved-project-root>","metadata":{"scan_categories":"<approved-categories>"}}' | gpd research-persona ingest-source - --output <candidate-patch>
printf '%s\n' '{"source_kind":"paper_import","path":"<approved-paper-path>"}' | gpd research-persona ingest-source - --output <candidate-patch>
printf '%s\n' '{"source_kind":"bibtex_import","path":"<approved-bibtex-path>"}' | gpd research-persona ingest-source - --output <candidate-patch>
printf '%s\n' '{"source_kind":"repo_scan","path":"<approved-repo-root>","metadata":{"scan_categories":"<approved-categories>"}}' | gpd research-persona ingest-source - --output <candidate-patch>
printf '%s\n' '{"source_kind":"manual_patch","path":"<approved-patch-path>"}' | gpd research-persona ingest-source - --output <candidate-patch>
```

6. Preserve the source-derived patch as a candidate artifact only. The next
   stages may merge, validate, and diff it, but durable profile mutation remains
   gated by explicit approval and `gpd research-persona apply-patch`.
</process>

<candidate_requirements>
- Every fact or axis derived from a source must carry `source_kind`, `sources`,
  `evidence_refs`, `confidence`, and a privacy label.
- Default new facts to `private_local` unless the user selected
  `project_private`, `session_only`, `safe_to_share`, or `never_prompt`.
- Use `confidence: "inferred"` for scan-derived facts until the user confirms
  them; use `confidence: "confirmed"` only for direct user statements or
  explicitly confirmed scan inferences.
- Scientific-taste entries should be reviewable hypotheses, not identity
  claims.
</candidate_requirements>

<handoff>
Return only source handles, candidate patch paths, privacy notes, confidence
notes, and schema warnings. Do not hand off raw private profile contents.
</handoff>
