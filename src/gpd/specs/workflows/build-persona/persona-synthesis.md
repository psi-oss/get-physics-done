<purpose>
Create a candidate `ResearchPersonaPatch` from consented interview answers,
approved evidence handles, and source-derived candidate patches.
</purpose>

<process>
1. Delegate candidate synthesis to `gpd-persona-builder` with a scoped write
   path for the patch artifact.
2. Require every proposed fact to include `source_kind`, `sources`,
   `evidence_refs`, `confidence`, and a privacy label.
3. Preserve source kinds emitted by `gpd research-persona ingest-source`:
   `interview`, `user_statement`, `project_scan`, `paper_import`,
   `bibtex_import`, `repo_scan`, and `manual_patch`.
4. Use conservative privacy defaults: `private_local` unless the user chooses
   `project_private`, `session_only`, `safe_to_share`, or `never_prompt`.
5. Keep `never_prompt` material out of prompt-facing summaries and capsules.
6. Keep existing persona context prompt-safe: use role capsules or projections
   only, never raw private profile content.
7. Validate the current stored profile, then run a read-only diff on the
   candidate patch. The diff step parses and validates the patch shape without
   writing persona storage:

```text
gpd research-persona validate
gpd research-persona diff GPD/persona/candidate-patch.json
```

8. If stored-profile validation or candidate-patch diff fails, revise the
   candidate patch when the error is in the candidate, or stop with the schema
   error. Do not apply the patch.
</process>

<downstream_hooks>
The patch may include approved facts for future `doppelganger`, `explainer`,
and `taste` capsules, but this stage does not run those behaviors. After the
user applies the patch, downstream previews must use prompt-safe capsules from
`gpd research-persona export-capsule` or the Phase 5 helpers:
`gpd research-persona doppelganger`, `gpd research-persona explain-plan`, and
`gpd research-persona taste-check`.
</downstream_hooks>
