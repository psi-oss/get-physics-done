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
Export GPD observability session logs and execution traces to files for external review, sharing, debugging, or archival.

Reads session event streams from `GPD/observability/sessions/` and trace logs from `GPD/traces/`, applies optional filters, and writes the results to `GPD/exports/logs/` (or a custom directory).

The local-only CLI passthrough filters `--command`, `--phase`, and `--category` are forwarded to the underlying export command; they only narrow what gets exported.

**Formats:**

- `jsonl` (default): Raw JSONL — one JSON object per line, suitable for machine consumption or log-processing pipelines
- `json`: Pretty-printed JSON arrays, suitable for inspection or import into analysis tools
- `markdown`: Human-readable report with session table and event timeline

**Filters:**

- `--session <id>`: Export only a specific session
- `--last N`: Export only the N most recent sessions
- `--command <label>`: Export only sessions for a given command
- `--phase <phase>`: Export only events from the matching phase
- `--category <name>`: Export only events from the matching category
- `--no-traces`: Exclude execution traces (only export observability events)
- `--output-dir <path>`: Write files to a custom directory instead of `GPD/exports/logs/`
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/export-logs.md
</execution_context>

<context>
Format and filters: $ARGUMENTS (all optional)
Local-only CLI passthrough filters: `--command`, `--phase`, and `--category`

@GPD/STATE.md
</context>

<process>
Execute the export-logs workflow from @{GPD_INSTALL_DIR}/workflows/export-logs.md end-to-end.

## Step 1: Validate project

Confirm a GPD project exists and observability data is present.

## Step 2: Parse arguments

Extract format, filters, and output directory from $ARGUMENTS.

## Step 3: Run export

```bash
gpd --raw observe export $ARGUMENTS
```

## Step 4: Report results

Display the export summary: files written, event counts, and output location.
</process>

<success_criteria>

- [ ] Project existence validated
- [ ] Observability sessions discovered and read
- [ ] Filters applied correctly (session, command, phase, last N)
- [ ] Output files written in requested format
- [ ] Traces included unless --no-traces specified
- [ ] File locations and counts reported to user
      </success_criteria>
