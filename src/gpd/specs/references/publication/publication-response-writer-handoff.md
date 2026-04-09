---
load_when:
  - "publication response drafting"
  - "publication response handoff"
  - "author response"
  - "referee response"
type: publication-response-writer-handoff
tier: 2
context_cost: low
---

# Publication Response Writer Handoff

Canonical workflow-facing handoff and completion reference for spawned response-writing work.

Use this pack when a workflow or agent spawns `gpd-paper-writer` to draft a response artifact pair or revise manuscript text in response to a referee report.

## Canonical Sources

- `@{GPD_INSTALL_DIR}/templates/paper/author-response.md`
- `@{GPD_INSTALL_DIR}/templates/paper/referee-response.md`
- `@{GPD_INSTALL_DIR}/references/publication/publication-response-artifacts.md`

## Rules

- A spawned response writer is one-shot. If user input is needed, it returns `status: checkpoint` and stops.
- The orchestrator resumes with a fresh continuation handoff. It does not wait inside the same run.
- `status: completed` is provisional until the expected response files exist on disk and are named in fresh typed `gpd_return.files_written`.
- Successful response-round completion requires both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`.
- Do not treat prose-only status messages or stale preexisting files as proof of completion.
- Keep the hard gate visible at the spawn site, but do not duplicate the full response prose there when this reference is loaded.
