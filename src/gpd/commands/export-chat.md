---
name: gpd:export-chat
description: Export chat logs to shareable files for bug reports, feature requests, and workflow examples
argument-hint: "[--format markdown|json] [--session <id>] [--output <path>]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Export chat and session logs into shareable files. Collects observability session
events and execution trace events from the project, sanitizes sensitive data, and
writes them to Markdown or JSON files suitable for:

- **Bug reports** -- attach sanitized logs showing what happened before an error
- **Feature requests** -- include workflow examples demonstrating current behavior
- **Sharing workflows** -- show collaborators how a research session progressed
- **Debugging** -- capture full event history for systematic analysis

**Formats:**

- `markdown`: Human-readable log with timestamps, commands, and event summaries
- `json`: Machine-readable structured export for programmatic analysis

Sensitive data (API keys, home directory paths) is redacted by default.
</objective>

<context>
Format: $ARGUMENTS (optional -- if not provided, defaults to markdown)

@GPD/STATE.md
</context>

<process>

## Step 1: List Available Sessions

```bash
gpd export-chat sessions
```

Show the user available sessions with their IDs, timestamps, and event counts.

## Step 2: Determine Export Options

Parse from $ARGUMENTS:

| Argument | Effect |
|----------|--------|
| `--format markdown` | Markdown output (default) |
| `--format json` | JSON output |
| `--session <id>` | Export specific session |
| `--output <path>` | Custom output path |
| `--no-traces` | Exclude trace events |
| `--no-sanitize` | Keep sensitive data (for self-debugging only) |
| `--last <N>` | Limit to last N events |
| `--phase <num>` | Filter traces by phase |

If no arguments, export all sessions as sanitized markdown.

## Step 3: Run Export

```bash
gpd export-chat run --format markdown
```

## Step 4: Report

Display the output file path and a summary of what was exported.

</process>

<success_criteria>

- [ ] Sessions listed or export format determined
- [ ] Events collected from observability and/or trace logs
- [ ] Sensitive data sanitized (unless --no-sanitize)
- [ ] File written to exports/ or custom path
- [ ] File location reported to user
</success_criteria>
