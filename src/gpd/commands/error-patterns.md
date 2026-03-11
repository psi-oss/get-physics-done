---
name: gpd:error-patterns
description: View accumulated physics error patterns for this project
argument-hint: "[category]"
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
Display accumulated physics error patterns from `.gpd/ERROR-PATTERNS.md`. Optionally filter by category.

Error patterns are recorded by the debugger after confirming root causes. They capture project-specific failure modes so that verifiers, planners, and executors can proactively check for recurrence.

Categories:

- `sign` -- Sign errors (metric, integration by parts, Wick rotation)
- `factor` -- Missing factors (2, pi, symmetry factors, normalization)
- `convention` -- Convention mismatches between modules or phases
- `numerical` -- Numerical issues (convergence, precision, stability)
- `approximation` -- Approximation validity breakdowns
- `boundary` -- Boundary condition errors
- `gauge` -- Gauge/frame artifacts
- `combinatorial` -- Symmetry factors, diagram counting
  </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-patterns.md
@.gpd/ERROR-PATTERNS.md
</execution_context>

<process>

**Pre-flight check:**
```bash
if [ ! -d ".gpd" ]; then
  echo "Error: No GPD project found. Run /gpd:new-project first."
  exit 1
fi
```

<step name="check_file">
```bash
test -f .gpd/ERROR-PATTERNS.md && echo "EXISTS" || echo "MISSING"
```

**If MISSING:**

```
No error patterns recorded yet.

Error patterns are captured by /gpd:debug when root causes are confirmed.
They help the verifier and planner proactively check for recurring issues.

---

Start a debugging session with /gpd:debug to begin building the pattern database.
```

Exit.
</step>

<step name="read_patterns">
Read `.gpd/ERROR-PATTERNS.md`.

**If $ARGUMENTS provided (category filter):**

Filter the patterns table to show only rows matching the category. Display:

```
## Error Patterns: {category}

{filtered table rows}

---

Showing {N} of {total} patterns. Run `/gpd:error-patterns` to see all.
```

**If no arguments (show all):**

Display the full contents formatted as:

```
## Project Error Patterns

{full table}

---

{total} patterns recorded. Filter by category: `/gpd:error-patterns sign`
```

</step>

<step name="global_patterns">
**Also show relevant patterns from the global cross-project library.**

```bash
gpd pattern init 2>/dev/null || true
DOMAIN=$(grep -m1 "domain:" .gpd/PROJECT.md 2>/dev/null | sed 's/.*: *//' || echo "")
GLOBAL=$(gpd --raw pattern list ${DOMAIN:+--domain "$DOMAIN"} 2>/dev/null)
```

If global patterns exist (count > 0), append:

```
## Cross-Project Patterns

{pattern list from global library, sorted by severity}

---

Global library: {count} patterns. Search: `gpd pattern search "keyword"`
```

</step>

</process>
