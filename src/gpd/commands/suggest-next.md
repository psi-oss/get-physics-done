---
name: gpd:suggest-next
description: Suggest the most impactful next action based on current project state
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Analyze current project state and suggest the most impactful next action. Uses `gpd --raw suggest` to scan phases, plans, verification status, blockers, and todos to produce a prioritized action list.

This is the fastest way to answer "what should I do next?" without reading through progress reports.
</objective>

<context>
@.gpd/STATE.md
@.gpd/ROADMAP.md
</context>

<process>

## Step 1: Run the suggest CLI

```bash
SUGGESTIONS=$(gpd --raw suggest)
if [ $? -ne 0 ]; then
  echo "ERROR: suggest-next failed: $SUGGESTIONS"
  echo ""
  echo "Try /gpd:progress for manual project status."
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
