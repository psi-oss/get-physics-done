---
load_when:
  - "publication response artifacts"
  - "referee response"
  - "review round suffix"
type: publication-response-artifacts
tier: 2
context_cost: low
---

# Publication Response Artifacts

Canonical paired response-artifact and one-shot child-return contract for referee-response work.

## Canonical Pair

- `GPD/AUTHOR-RESPONSE{round_suffix}.md` is the canonical internal tracker.
- `GPD/review/REFEREE_RESPONSE{round_suffix}.md` is the journal-facing sibling and must mirror the same `REF-*` issue IDs, classifications, statuses, and new-calculation tracking, including source-phase linkage when present.
- An optional manuscript-local response-letter companion such as `response-letter.tex` is additive only. It does not replace the canonical GPD response pair.
- Treat the two files as one success gate: do not mark the round complete when only one of them is current.
- Project-backed response rounds use the exact global paths above.
- For an explicit external publication subject, the same paired response artifacts may instead bind under the subject-owned publication root `GPD/publication/{subject_slug}` while preserving the same filenames, issue IDs, and round-suffix alignment.
- That bounded subject-owned continuation path does not imply a full relocation of manuscript drafts, manuscript-root manifests, or every publication artifact into the subject-owned tree.

## Delegation Rule

- If a spawned writer needs user input, it returns `status: checkpoint` and stops. The orchestrator resumes with a fresh continuation; it does not wait inside the same run.
- A reported `status: completed` is provisional until the response pair exists on disk and those same fresh paths appear in typed `gpd_return.files_written`.

## Completion Gate

- Successful response-round completion requires both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`.
- Do not accept stale preexisting files, prose-only status messages, or a single mirrored letter as proof of completion.
- When decision artifacts exist, keep blocking issue IDs and their statuses synchronized across the paired response files.
