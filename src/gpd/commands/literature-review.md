---
name: gpd:literature-review
description: Structured literature review for a physics research topic with citation network analysis and open question identification
argument-hint: "[topic or research question]"
context_mode: project-aware
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
Run the literature-review workflow as a thin wrapper around the staged review pipeline. Produce `GPD/literature/{slug}-REVIEW.md` and the matching `GPD/literature/{slug}-CITATION-SOURCES.json` sidecar.

**Why subagent:** Literature searches burn context fast. Fresh context keeps the survey lean and gives the dedicated reviewer handoff room to synthesize cleanly.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/literature-review.md
</execution_context>

<context>
Topic: $ARGUMENTS
</context>

<process>
Read the workflow referenced in `<execution_context>` with `file_read` first.

```bash
CONTEXT=$(gpd --raw validate command-context literature-review "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```
</process>
