---
name: gpd:help
description: Show available GPD commands and usage guide
argument-hint: "[--all | --command <name>]"
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

Check whether the user passed `--command <name>` or `--all`.

- If `$ARGUMENTS` contains `--command <name>`: display the **Single Command Detail Extract** (step 4).
- If `$ARGUMENTS` contains `--all` and does not contain `--command <name>`: display the **Compact Command Index** (step 3).
- If `$ARGUMENTS` is empty or contains neither `--all` nor `--command <name>`: display the **Quick Start Extract** (step 2) only.

## Step 2: Quick Start Extract (Default Output)

Use the loaded workflow help file as the authority. Output ONLY this extract from
that workflow-owned reference and then STOP:

- Start at the workflow-owned `## Quick Start` section.
- Include the workflow-owned `## Quick Start` section.
- Stop before `## Command Index`.
- Append this one wrapper-owned line: `Run \`gpd:help --all\` for the compact command index.`

Do not rewrite, summarize, or invent alternate wording for any extracted section.

## Step 3: Compact Command Index (--all)

Use the loaded workflow help file as the authority. Output ONLY this extract from
that workflow-owned reference and then STOP:

- Start at the workflow-owned `## Quick Start` section.
- Include the workflow-owned `## Quick Start` section.
- Include the workflow-owned `## Command Index` section.
- Stop before `## Detailed Command Reference`.
- Append this one wrapper-owned line: `Run \`gpd:help --command <name>\` for detailed help on one command.`

Do not rewrite, summarize, or invent alternate wording for any extracted section.

## Step 4: Single Command Detail Extract (--command <name>)

Use the loaded workflow help file as the authority.

- Parse the command name from `$ARGUMENTS` after `--command`.
- Accept either a bare command name such as `plan-phase` or a canonical runtime command such as `gpd:plan-phase`.
- If the lookup includes inline flags or arguments such as `gpd:new-project --minimal`, normalize it to the base command block that documents those flags or arguments.
- Normalize the lookup to the matching canonical runtime command inside the workflow-owned `## Detailed Command Reference`.
- Output ONLY the smallest matching detailed command block.
- Include the nearest containing section heading (for example `### Phase Planning`) plus the matching command block.
- Include matching `Flags:`, `Usage:`, and `Result:` lines that belong to that command when present.
- Stop before the next command block begins.
- If no exact command matches, output exactly this one line and STOP: `Unknown command. Run \`gpd:help --all\` for the compact command index.`

Do not rewrite, summarize, or invent alternate wording for any extracted section.
</process>
