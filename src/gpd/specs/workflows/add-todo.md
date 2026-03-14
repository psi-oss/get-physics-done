<purpose>
Capture an idea, task, or issue that surfaces during a GPD session as a structured todo for later work. Enables "thought -> capture -> continue" flow without losing context. Typical physics research todos include: a subtlety to check, a reference to look up, an alternative approach to explore, a numerical test to run, or a derivation step to verify.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="init_context">
Load todo context:

```bash
INIT=$(gpd init todos)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Extract from init JSON: `commit_docs`, `date`, `timestamp`, `todo_count`, `todos`, `pending_dir`, `todos_dir_exists`, `project_exists`.

**Note:** `add-todo` works even without a project (creates `.gpd/todos/` standalone). No project_exists gate needed — todos can be created independently.

Ensure directories exist:

```bash
mkdir -p .gpd/todos/pending .gpd/todos/done
```

Note existing areas from the todos array for consistency in infer_area step.
</step>

<step name="extract_content">
**With arguments:** Use as the title/focus.
- `/gpd:add-todo Check unitarity of S-matrix at two loops` -> title = "Check unitarity of S-matrix at two loops"

**Without arguments:** Analyze recent conversation to extract:

- The specific problem, idea, or task discussed
- Relevant file paths or notebook sections mentioned
- Technical details (equations, parameter values, limits, constraints)

Formulate:

- `title`: 3-10 word descriptive title (action verb preferred)
- `problem`: What's wrong or why this is needed
- `solution`: Approach hints or "TBD" if just an idea
- `files`: Relevant paths with line numbers from conversation
  </step>

<step name="infer_area">
Infer area from file paths and content:

| Path pattern / content                 | Area            |
| -------------------------------------- | --------------- |
| `derivations/*`, `analytical/*`        | `analytical`    |
| `numerics/*`, `simulations/*`, `src/*` | `numerical`     |
| `references/*`, `bibliography/*`       | `literature`    |
| `data/*`, `results/*`, `plots/*`       | `data-analysis` |
| `tests/*`, `validation/*`              | `validation`    |
| `notebooks/*`                          | `notebooks`     |
| `.gpd/*`                          | `planning`      |
| `scripts/*`, `tools/*`                 | `tooling`       |
| Equation/formalism discussion          | `formalism`     |
| Symmetry/consistency checks            | `consistency`   |
| No files or unclear                    | `general`       |

Use existing area from step 2 if similar match exists.
</step>

<step name="check_duplicates">
```bash
# Search for key words from title in existing todos
grep -l -i "[key words from title]" .gpd/todos/pending/*.md 2>/dev/null
```

If potential duplicate found:

1. Read the existing todo
2. Compare scope

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

If overlapping, use ask_user:

- header: "Duplicate?"
- question: "Similar todo exists: [title]. What would you like to do?"
- options:
  - "Skip" -- keep existing todo
  - "Replace" -- update existing with new context
  - "Add anyway" -- create as separate todo
    </step>

<step name="create_file">
Use values from init context: `timestamp` and `date` are already available.

Generate slug for the title:

```bash
slug=$(gpd --raw slug "$title")
todo_file=".gpd/todos/pending/${date}-${slug}.md"
```

Write to `${todo_file}`:

```markdown
---
created: [timestamp]
title: [title]
area: [area]
files:
  - [file:lines]
---

## Problem

[problem description - enough context for a future AI session to understand weeks later]

## Solution

[approach hints or "TBD"]
```

</step>

<step name="update_state">
If `.gpd/STATE.md` exists:

1. Use `todo_count` from init context (or re-run `init todos` if count changed)
2. Update "### Pending Todos" under "## Accumulated Context"

</step>

<step name="git_commit">
Commit the todo and any updated state:

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${todo_file}" .gpd/STATE.md 2>&1) || true
echo "$PRE_CHECK"

gpd commit "docs: capture todo - ${title}" --files "${todo_file}" .gpd/STATE.md
```

Tool respects `commit_docs` config and gitignore automatically.

Confirm: "Committed: docs: capture todo - ${title}"
</step>

<step name="confirm">
```
Todo saved: ${todo_file}

[title]
Area: [area]
Files: [count] referenced

---

Would you like to:

1. Continue with current work
2. Add another todo
3. View all todos (/gpd:check-todos)

```
</step>

</process>

<success_criteria>
- [ ] Directory structure exists
- [ ] Todo file created with valid frontmatter
- [ ] Problem section has enough context for a future AI session
- [ ] No duplicates (checked and resolved)
- [ ] Area consistent with existing todos
- [ ] STATE.md updated if exists
- [ ] Todo and state committed to git
</success_criteria>
