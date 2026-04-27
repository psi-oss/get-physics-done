---
name: gpd:health
description: Run project health checks and optionally auto-fix issues
argument-hint: "[--fix]"
context_mode: projectless
allowed-tools:
  - file_read
  - ask_user
  - shell
  - find_files
  - search_files
---


<objective>
Run comprehensive project health checks. Default to read-only inspection.

Checks include: environment, project structure, knowledge inventory, storage-path policy, state validity, compaction, roadmap consistency, orphaned phase directories, convention lock integrity, plan frontmatter, latest return envelope, config.json validity, checkpoint tags, and git status.

Use `--fix` only after explicit confirmation from the researcher, because it can modify project files.
</objective>

<process>

## Step 1: Parse Arguments

Check `$ARGUMENTS` for `--fix` flag.

Default mode is read-only. If `--fix` is absent, do not mutate files and run only `gpd --raw health`.

If `--fix` is present, stop before running the command and ask for explicit confirmation that auto-repair may modify project files. Do not run `gpd --raw health --fix` unless the researcher confirms.

## Step 2: Run health check

Let the raw CLI inspect project files conditionally from the current workspace.

```bash
if echo "$ARGUMENTS" | grep -q "\-\-fix"; then
  # Only after explicit confirmation in Step 1.
  HEALTH=$(gpd --raw health --fix)
else
  HEALTH=$(gpd --raw health)
fi

if [ $? -ne 0 ]; then
  echo "ERROR: health check failed: $HEALTH"
  exit 1
fi
```

## Step 3: Parse and present

Parse JSON output containing:
- `overall`: top-level `CheckStatus` for the full report
- `summary`: `HealthSummary` with `ok`, `warn`, `fail`, and `total`
- `checks`: Array of `HealthCheck` objects with `status`, `label`, `details`, `issues`, and `warnings`
- `fixes_applied`: top-level list of auto-applied fix descriptions

## Step 4: Display

```
## Project Health

| Check | Status | Details |
|-------|--------|---------|
| {name} | {pass/warn/fail} | {message} |
| ... | ... | ... |

---

**Overall:** {overall}
**{ok}/{total} ok** | {warn} warnings | {fail} failures
[If --fix was used:] | {fixed} auto-fixed
```

If there are failures and `--fix` was not used:

```
Run `gpd:health --fix` only when you want auto-repair, then confirm the mutation prompt. Report any applied fixes from `fixes_applied`.
```

If all checks pass:

```
All {total} health checks passed.
```

</process>

<success_criteria>

- [ ] Health command executed successfully
- [ ] All checks reported with status
- [ ] Summary presented (pass/warn/fail counts)
- [ ] Auto-fix applied only if --fix flag present and the researcher explicitly confirmed mutation
- [ ] Clear guidance on how to fix remaining issues
      </success_criteria>
