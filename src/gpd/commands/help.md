---
name: gpd:help
description: Show available GPD commands and usage guide
argument-hint: "[--all]"
context_mode: global
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Display GPD help by delegating to the workflow-owned help surface.

Output ONLY reference content. Do NOT add project-specific analysis, git status,
next-step suggestions, or commentary beyond the requested reference extract.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/help.md
</execution_context>

<process>

## Step 1: Parse Arguments

Check if the user passed `--all` as an argument.

- If `$ARGUMENTS` contains `--all`: display the **Full Command Reference** (step 3).
- If `$ARGUMENTS` is empty or does not contain `--all`: display the **Quick Start Extract** (step 2) only.

## Step 2: Quick Start Extract (Default Output)

Use the loaded workflow help file as the authority. Output ONLY this extract from
that workflow-owned reference and then STOP:

- Start at the workflow-owned `## Quick Start` section.
- Include the workflow-owned `## Quick Start` section.
- Stop before `## Core Workflow`.
- Append this one wrapper-owned line: `Run \`gpd:help --all\` for the full command reference.`

Do not rewrite, summarize, or invent alternate wording for any extracted section.

## Step 3: Full Command Reference (--all)

Output the complete `<reference>` block from the loaded workflow help file verbatim.
Do not add, remove, or rewrite any part of that workflow-owned reference.
</process>
