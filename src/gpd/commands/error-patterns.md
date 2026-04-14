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

<objective>
Display project error patterns from `GPD/ERROR-PATTERNS.md`, optionally filtered by category, then append relevant cross-project patterns.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/error-patterns.md
@GPD/ERROR-PATTERNS.md
</execution_context>

<context>
Category filter: $ARGUMENTS

Supported categories include `sign`, `factor`, `convention`, `numerical`, `approximation`, `boundary`, `gauge`, and `combinatorial`.
</context>

<process>

```bash
if [ ! -d "GPD" ]; then
  echo "Error: No GPD project found. Run gpd:new-project first."
  exit 1
fi
```

If `GPD/ERROR-PATTERNS.md` is missing, report that no project patterns are recorded yet and suggest `gpd:debug` after a confirmed root cause.

If a category is provided, show only matching project patterns and report `{shown} of {total}`. Otherwise show all project patterns and mention `gpd:error-patterns <category>`.

Append cross-project patterns when available:

```bash
gpd pattern init 2>/dev/null || true
DOMAIN=$(grep -m1 "domain:" GPD/PROJECT.md 2>/dev/null | sed 's/.*: *//' || echo "")
gpd --raw pattern list ${DOMAIN:+--domain "$DOMAIN"} 2>/dev/null
```

</process>
