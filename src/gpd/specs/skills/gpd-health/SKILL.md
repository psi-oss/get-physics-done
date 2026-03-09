---
name: gpd-health
description: Run project health checks and optionally auto-fix issues
argument-hint: "[--fix]"
requires:
  files: [".planning/PROJECT.md"]
allowed-tools:
  - read_file
  - write_file
  - shell
  - glob
  - grep
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for runtimes that do not resolve them natively. -->

<objective>
Run comprehensive project health checks (9 checks) and optionally auto-fix detected issues.

Checks include: state.json validity, STATE.md sync, convention lock integrity, config.json validity, orphaned phase directories, ROADMAP.md consistency, missing plan files, stale artifacts, and git status.

Use `--fix` to automatically repair detected issues.
</objective>

<process>

## Step 1: Parse Arguments

Check `$ARGUMENTS` for `--fix` flag.

## Step 2: Run health check

```bash
if echo "$ARGUMENTS" | grep -q "\-\-fix"; then
  HEALTH=$(gpd health --fix --raw)
else
  HEALTH=$(gpd health --raw)
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
Run `$gpd-health --fix` to auto-repair {fixable_count} issue(s).
```

If all checks pass:

```
All {total} health checks passed.
```

</process>

<success_criteria>

- [ ] Health command executed successfully
- [ ] All 9 checks reported with status
- [ ] Summary presented (pass/warn/fail counts)
- [ ] Auto-fix applied if --fix flag present
- [ ] Clear guidance on how to fix remaining issues
</success_criteria>
</output>
