---
name: gpd:export-logs
description: Export session logs and traces to files for external review or archival
argument-hint: "[--format jsonl|json|markdown] [--session <id>] [--last N] [--command <label>] [--phase <phase>] [--category <name>] [--no-traces] [--output-dir <path>]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
---


<objective>
Export GPD observability session logs and execution traces for review, sharing, debugging, or archival.

The local-only CLI passthrough filters `--command`, `--phase`, and `--category` narrow the underlying export only. Supported options are `--format jsonl|json|markdown`, `--session <id>`, `--last N`, `--command <label>`, `--phase <phase>`, `--category <name>`, `--no-traces`, and `--output-dir <path>`.

The raw export validates the requested format before creating directories, refuses missing session logs, and labels filtered empty exports with `empty_export: true`.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/export-logs.md
</execution_context>

<context>
Format and filters: $ARGUMENTS (all optional)

@GPD/STATE.md
</context>

<process>
Execute the included export-logs workflow end-to-end.

## Step 1: Validate context

Run the raw prefixless command-context preflight before export:

```bash
CONTEXT=$(gpd --raw validate command-context export-logs "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

## Step 2: Parse arguments as data

Extract format, filters, and output directory from `$ARGUMENTS` as data only. Do not evaluate it, run it through a shell-interpreter wrapper, or concatenate it into a shell command.

Use only the recognized flags listed above. Preserve spaces inside values such as output paths or command/category labels. If a value cannot be unambiguously assigned to a known flag, stop and ask for the exact format, filter, or output path instead of guessing.

## Step 3: Run export

Invoke `gpd --raw observe export` once. Pass only requested recognized options, with each value as its own quoted argv value:

`--format "$FORMAT"`, `--session "$SESSION"`, `--last "$LAST"`, `--command "$COMMAND"`, `--phase "$PHASE"`, `--category "$CATEGORY"`, `--output-dir "$OUTPUT_DIR"`, `--no-traces`.

Never pass raw `$ARGUMENTS` to `observe export`, never build `EXPORT_ARGS`, and never run the export through a shell-interpreter wrapper. For example, a spaced path must be passed as one quoted `--output-dir` value.

## Step 4: Report results

Display files written, event counts, and output location. If `empty_export: true`, state that the requested filters matched no sessions, events, or traces.
</process>

<success_criteria>

- [ ] Command-context preflight passed
- [ ] Filters applied correctly (session, command, phase, last N)
- [ ] Output files written in requested format
- [ ] Empty filtered exports explicitly labeled when no content matched
- [ ] Traces included unless --no-traces specified
- [ ] File locations and counts reported to user
      </success_criteria>
