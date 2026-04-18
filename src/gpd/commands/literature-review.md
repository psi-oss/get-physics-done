---
name: gpd:literature-review
description: Structured literature review for a physics research topic with citation network analysis and open question identification
argument-hint: "[topic or research question]"
context_mode: project-aware
command-policy:
  schema_version: 1
  subject_policy:
    subject_kind: literature_topic
    resolution_mode: literature_topic
    explicit_input_kinds:
      - topic or research question
    allow_interactive_without_subject: true
  supporting_context_policy:
    project_context_mode: project-aware
    project_reentry_mode: disallowed
    optional_file_patterns:
      - GPD/STATE.md
      - GPD/ROADMAP.md
      - GPD/literature/*.md
  output_policy:
    output_mode: managed
    managed_root_kind: gpd_managed_durable
    default_output_subtree: GPD/literature
allowed-tools:
  - file_read
  - file_write
  - shell
  - search_files
  - find_files
  - task
  - web_search
  - web_fetch
  - ask_user
---
<objective>
Run the literature-review workflow as a thin wrapper around the staged review pipeline for an explicit topic or research question. Produce `GPD/literature/{slug}-REVIEW.md` and the matching `GPD/literature/{slug}-CITATION-SOURCES.json` sidecar under `GPD/literature/` rooted at the current workspace. In project-backed mode that is the resolved project root's `GPD/literature/`; in standalone mode it is `./GPD/literature/` in the invoking workspace.

**Why subagent:** Literature searches burn context fast. Fresh context keeps the survey lean and gives the dedicated reviewer handoff room to synthesize cleanly.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/literature-review.md
</execution_context>

<context>
Topic: $ARGUMENTS (project context can narrow the framing, but it does not replace the review topic)
</context>

<process>
```bash
CONTEXT=$(gpd --raw validate command-context literature-review "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Follow `@{GPD_INSTALL_DIR}/workflows/literature-review.md` exactly. The workflow owns staged loading, scope fixing, artifact gating, and citation verification.
If the invocation is empty in project-backed mode, ask one focused question to set the review topic before handing off. Standalone empty invocations should already have failed preflight.
</process>
