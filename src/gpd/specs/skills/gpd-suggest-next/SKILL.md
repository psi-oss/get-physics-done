---
name: gpd-suggest-next
description: Suggest the most impactful next action based on current project state
argument-hint: ""
requires:
  files: [".planning/PROJECT.md"]
allowed-tools:
  - read_file
  - shell
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<objective>
Analyze current project state and suggest the most impactful next action. Uses gpd suggest-next to scan phases, plans, verification status, blockers, and todos to produce a prioritized action list.

This is the fastest way to answer "what should I do next?" without reading through progress reports.
</objective>

<process>

## Step 1: Run suggest-next

```bash
SUGGESTIONS=$(gpd suggest-next --raw)
if [ $? -ne 0 ]; then
  echo "ERROR: suggest-next failed: $SUGGESTIONS"
  echo ""
  echo "Try $gpd-progress for manual project status."
  exit 1
fi
```

## Step 2: Parse and present

Parse the JSON output. It contains:
- `suggestions`: Array of `{priority, action, command, reason}` sorted by priority (1=highest)
- `context`: Object with `current_phase`, `status`, `progress_percent`, `paused_at`, `active_blockers`
- `suggestion_count`: Total number of suggestions

## Step 3: Display

```
## What's Next

[For each suggestion, ordered by priority:]

**{priority}. {command}**
   {reason}

---

Context: Phase {current_phase} | {progress_percent}% complete | {status}
```

If there's only one suggestion, present it as the clear next step:

```
## >> Next Up

**{command}**
{reason}

<sub>`/clear` first -> fresh context window</sub>
```

If there are blockers, highlight them before suggestions:

```
## !! {active_blockers} Blocker(s)

Resolve before continuing:
- {blocker description}

---
```

</process>

<success_criteria>

- [ ] suggest-next command executed successfully
- [ ] Suggestions presented in priority order
- [ ] Context shown (phase, progress, status)
- [ ] Blockers highlighted if present
- [ ] User has a clear next action
</success_criteria>
</output>
