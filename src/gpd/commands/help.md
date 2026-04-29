---
name: gpd:help
description: Show available GPD commands and usage guide
argument-hint: "[--all | --command <name>]"
context_mode: global
---


<objective>
Display GPD help by delegating to the workflow-owned help surface.

Return only reference content. Do not add project-specific analysis, git status,
next-step suggestions, or commentary beyond the requested reference extract.
</objective>

Shared wrapper rule for every extract below: the loaded workflow help file is the authority. Return the requested section without rewriting, summarizing, or inventing alternate wording.

Use the workflow-owned stable markers as the extraction boundaries:

- `<!-- gpd-help:quick-start:start -->` / `<!-- gpd-help:quick-start:end -->`
- `<!-- gpd-help:command-index:start -->` / `<!-- gpd-help:command-index:end -->`
- `<!-- gpd-help:detailed-command-reference:start -->` / `<!-- gpd-help:detailed-command-reference:end -->`

Return marker contents only; never print the HTML marker comments themselves. Visible headings inside marker ranges are output labels only.

Runtime command-surface note: `<current-help-command>` below means the concrete command spelling that invoked this help wrapper. Replace it before output; never print the placeholder or adapter-specific examples.

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

Output ONLY this extract from the workflow-owned reference and then STOP:

- Extract from `<!-- gpd-help:quick-start:start -->` through `<!-- gpd-help:quick-start:end -->`.
- Exclude the marker comment lines themselves.
- Do not output adapter-specific examples; replace `<current-help-command>` before output.
- Append this one wrapper-owned line: `Run <current-help-command> --all for the compact command index.`

## Step 3: Compact Command Index (--all)

Output ONLY this extract from the workflow-owned reference and then STOP:

- Extract from `<!-- gpd-help:quick-start:start -->` through `<!-- gpd-help:command-index:end -->`.
- Exclude the marker comment lines themselves.
- Do not output adapter-specific examples; replace `<current-help-command>` before output.
- Append this one wrapper-owned line: `Run <current-help-command> --command <name> for detailed help on one command.`

## Step 4: Single Command Detail Extract (--command <name>)

- Parse the command name from `$ARGUMENTS` after `--command`.
- Accept either a bare command name such as `plan-phase`, a canonical runtime command such as `gpd:plan-phase`, or the current runtime's native command label.
- If the lookup includes inline flags or arguments such as `gpd:new-project --minimal` or `new-project --minimal`, parse the inline arguments separately and normalize the lookup to the base command block that documents those flags or arguments.
- Normalize the lookup to the matching canonical runtime command inside the workflow-owned detailed-command marker range (`<!-- gpd-help:detailed-command-reference:start -->` / `<!-- gpd-help:detailed-command-reference:end -->`), whose visible heading is `## Detailed Command Reference`.
- Output ONLY the smallest matching detailed command block.
- Include the nearest containing section heading (for example `### Phase Planning`) plus the matching command block.
- Include matching `Flags:`, `Usage:`, and `Result:` lines that belong to that command when present.
- Stop before the next command block begins.
- If no command matches after normalization, output this one line and STOP after replacing `<current-help-command>`: `Unknown command. Run <current-help-command> --all for the compact command index.`
</process>
