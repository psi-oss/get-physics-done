---
name: gpd:health
description: Run project health checks and optionally auto-fix issues
argument-hint: "[--fix]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Run comprehensive project health checks and optionally auto-fix detected issues.

Checks include: environment, project structure, storage-path policy, state validity, compaction, roadmap consistency, orphaned phase directories, convention lock integrity, plan frontmatter, latest return envelope, config.json validity, checkpoint tags, and git status.

Use `--fix` to automatically repair detected issues.
</objective>

<context>
@.gpd/STATE.md
@.gpd/state.json
@.gpd/config.json
</context>

<process>

## Step 1: Parse Arguments

Check `$ARGUMENTS` for `--fix` flag.

## Step 2: Run health check

```bash
if echo "$ARGUMENTS" | grep -q "\-\-fix"; then
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
- `checks`: Array of `{name, status, message, fixed}` where status is "pass", "warn", or "fail"
- `summary`: Object with `total`, `passed`, `warnings`, `failures`, `fixed`

## Step 4: Display

```
## Project Health

| Check | Status | Details |
|-------|--------|---------|
| {name} | {pass/warn/fail} | {message} |
| ... | ... | ... |

---

**{passed}/{total} passed** | {warnings} warnings | {failures} failures
[If --fix was used:] | {fixed} auto-fixed
```

If there are failures and `--fix` was not used:

```
Run `/gpd:health --fix` to auto-repair {fixable_count} issue(s).
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
- [ ] Auto-fix applied if --fix flag present
- [ ] Clear guidance on how to fix remaining issues
      </success_criteria>
