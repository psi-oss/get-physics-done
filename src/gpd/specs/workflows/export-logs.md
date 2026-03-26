<purpose>
Export GPD observability session logs and execution traces to files. Reads session event streams from `GPD/observability/sessions/` and trace logs from `GPD/traces/`, applies optional filters, and writes results to `GPD/exports/logs/` or a custom directory. Supports JSONL (raw), JSON (pretty-printed), and markdown (human-readable report) formats.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="validate_project">
**Validate GPD project and observability data:**

```bash
gpd validate command-context gpd:export-logs $ARGUMENTS
```

Check that `GPD/observability/sessions/` exists and contains at least one `.jsonl` file:

```bash
ls GPD/observability/sessions/*.jsonl 2>/dev/null | head -5
```

**If no sessions found:**

```
╔══════════════════════════════════════════════════════════════╗
║  ERROR                                                       ║
╚══════════════════════════════════════════════════════════════╝

No observability sessions found in GPD/observability/sessions/.

Session logs are recorded automatically during GPD command execution.
Run any GPD command first, then retry /gpd:export-logs.
```

Exit.
</step>

<step name="parse_arguments">
**Parse export arguments from $ARGUMENTS:**

| Argument | Default | Meaning |
|----------|---------|---------|
| `--format jsonl\|json\|markdown` | `jsonl` | Output format |
| `--session <id>` | (none) | Export only this session |
| `--last N` | (none) | Export the N most recent sessions |
| `--command <label>` | (none) | Filter sessions by command label |
| `--no-traces` | false | Exclude execution traces |
| `--output-dir <path>` | `GPD/exports/logs/` | Custom output directory |

If no arguments provided, use defaults (all sessions, JSONL format, include traces, default output dir).

**If format is not recognized:**

```
╔══════════════════════════════════════════════════════════════╗
║  ERROR                                                       ║
╚══════════════════════════════════════════════════════════════╝

Unsupported format: {format}. Use: jsonl, json, or markdown.
```

Exit.
</step>

<step name="run_export">
**Execute the export via CLI:**

Build the CLI invocation from parsed arguments:

```bash
EXPORT_ARGS=""
if [ -n "$FORMAT" ]; then EXPORT_ARGS="$EXPORT_ARGS --format $FORMAT"; fi
if [ -n "$SESSION" ]; then EXPORT_ARGS="$EXPORT_ARGS --session $SESSION"; fi
if [ -n "$LAST" ]; then EXPORT_ARGS="$EXPORT_ARGS --last $LAST"; fi
if [ -n "$COMMAND" ]; then EXPORT_ARGS="$EXPORT_ARGS --command $COMMAND"; fi
if [ -n "$OUTPUT_DIR" ]; then EXPORT_ARGS="$EXPORT_ARGS --output-dir $OUTPUT_DIR"; fi
if [ "$NO_TRACES" = "true" ]; then EXPORT_ARGS="$EXPORT_ARGS --no-traces"; fi

RESULT=$(gpd --raw observe export $EXPORT_ARGS)

if [ $? -ne 0 ]; then
  echo "ERROR: export failed: $RESULT"
  exit 1
fi
```

Parse the JSON result for `exported`, `output_dir`, `sessions_exported`, `events_exported`, `traces_exported`, and `files_written`.
</step>

<step name="present_results">
**Display the export summary:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > LOG EXPORT COMPLETE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

**Format:** {format}
**Output:** {output_dir}

| Metric | Count |
|--------|-------|
| Sessions exported | {sessions_exported} |
| Events exported | {events_exported} |
| Traces exported | {traces_exported} |

**Files written:**

{For each file in files_written:}
- `{file_path}`

───────────────────────────────────────────────────────────────

**Also available:**
- `/gpd:export-logs --format markdown` — human-readable report
- `/gpd:export-logs --last 5` — export only recent sessions
- `gpd observe show` — inspect events interactively
- `gpd observe sessions` — list available sessions

───────────────────────────────────────────────────────────────
```

**If no events found (after filtering):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > LOG EXPORT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

No events matched the specified filters.

Try broadening filters or run `gpd observe sessions` to see available sessions.
```

</step>

</process>

<anti_patterns>

- Don't export without checking that observability data exists first
- Don't silently overwrite previous exports — timestamped filenames prevent collisions
- Don't include the `.active-trace` marker file in trace exports
- Don't fail on malformed JSONL lines — skip them gracefully
- Don't export binary or non-JSONL files from the observability tree
</anti_patterns>

<success_criteria>
Export is complete when:

- [ ] GPD project validated and observability data found
- [ ] Arguments parsed and format validated
- [ ] Session logs read and filtered
- [ ] Traces included (unless --no-traces)
- [ ] Files written to output directory with timestamped names
- [ ] Summary displayed with file paths and counts

</success_criteria>
