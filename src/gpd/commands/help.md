---
name: gpd:help
description: Show available GPD commands and usage guide
argument-hint: "[--all | --command <name>]"
context_mode: global
help:
  group: Starter commands
  order: 10
  compact_description: Show the quick start or command index
  display_signature: gpd:help
---


<objective>
Display GPD help by delegating to the renderer-backed local CLI help bridge.
Return only help content.
</objective>

Shared wrapper rule: use the bridge first; fallback extracts preserve workflow marker text without rewriting or invented wording.
Bridge command rule: local CLI raw help -> JSON -> renderer-backed markdown/fields.
Use the workflow-owned help surface as the marker fallback.

- `@{GPD_INSTALL_DIR}/workflows/help.md` - Fallback marker source path.
- `@{GPD_INSTALL_DIR}/references/help/detailed-command-reference.md` - Fallback detail.

Use the workflow-owned stable markers as the extraction boundaries for fallback mode:

- `<!-- gpd-help:default:start -->` / `<!-- gpd-help:default:end -->`
- `<!-- gpd-help:quick-start:start -->` / `<!-- gpd-help:quick-start:end -->`
- `<!-- gpd-help:command-index:start -->` / `<!-- gpd-help:command-index:end -->`
- `<!-- gpd-help:detailed-command-reference:start -->` / `<!-- gpd-help:detailed-command-reference:end -->`

Research Persona fallback inventory:

<!-- gpd-help:research-persona-builder-command-index:start -->
### Tangents, memory, and exports

- `gpd:build-persona [focus|--from-current-project|--interview-only]` - Draft a private research-persona patch for explicit review
<!-- gpd-help:research-persona-builder-command-index:end -->

<!-- gpd-help:research-persona-builder-detailed-command-reference:start -->
### Tangents, memory, and exports

**`gpd:build-persona [focus|--from-current-project|--interview-only]`**
Build a private research persona patch from explicit interview and consented local evidence.
Usage: `gpd:build-persona --interview-only`; `gpd:build-persona --from-current-project "math/code balance and citation style"`
Notes: Candidate patch only; apply separately with `gpd research-persona apply-patch`. Interview, source ingestion, local scans, paper/BibTeX imports, repo scans, manual patches, and statements require explicit user consent. Prompt capsules must use privacy projection and must not expose `private_local`, `project_private`, or `never_prompt` facts. The same substrate powers Researcher Doppelganger, Expertise-Aware Explanations, and Scientific Taste Model previews without raw profile access.
<!-- gpd-help:research-persona-builder-detailed-command-reference:end -->

Return marker contents only; never print the HTML marker comments themselves. Visible headings inside marker ranges are output labels only.

Runtime command-surface note: refer to the command that invoked this wrapper as "this help command"; do not print adapter-specific examples.

Anchors:
Project-aware technical-analysis lane: `GPD/analysis/`; `gpd:dimensional-analysis results/01-SUMMARY.md`; `gpd:limiting-cases results/01-SUMMARY.md`; `gpd:numerical-convergence results/mesh-study.csv`. `gpd:graph` and `gpd:error-propagation` are separate commands and are not part of this relaxed current-workspace lane.
Publication boundary: one bounded external-authoring lane driven by an explicit intake manifest only; use `gpd:write-paper --intake intake/write-paper-authoring-input.json`. Outputs live under `GPD/publication/{subject_slug}/...`; `GPD/publication/{subject_slug}/manuscript` is the only manuscript/build root; `GPD/publication/{subject_slug}/intake/` keeps intake/provenance state only. It does not mine arbitrary folders or infer claim/evidence bindings from loose notes. `gpd:peer-review` remains the standalone follow-on command. Project-backed review/response/package outputs stay on the `GPD/` and `GPD/review/` paths. `gpd:respond-to-referees` stays tied to the resolved manuscript root; `gpd:arxiv-submission` packages only a GPD-owned manuscript root or `.tex` entrypoint. Not a full publication-root migration.

<process>

## Step 1: Parse Arguments

If `$ARGUMENTS` contains `--command <name>`, use step 4. Otherwise use step 3
for `--all` or step 2 for the default quick start.

## Step 2: Quick Start Extract (Default Output)

```bash
gpd --raw help
```

Parse JSON field `quick_start.markdown`; output ONLY that markdown. Append this one wrapper-owned line:
`Run this help command with --all for the compact command index.`

Workflow-owned reference fallback:

Extract from `<!-- gpd-help:default:start -->` through `<!-- gpd-help:default:end -->`.
Exclude the marker comment lines themselves. Append this one wrapper-owned line:
`Run this help command with --all for the compact command index.`

Then STOP.

## Step 3: Compact Command Index (--all)

```bash
gpd --raw help --all
```

Parse JSON fields `quick_start.markdown`, `command_index_markdown`, and
`detailed_help_follow_up`; output quick start then index; replace the follow-up with:
`Run this help command with --command <name> for detailed help on one command.`

Workflow-owned reference fallback:

Extract from `<!-- gpd-help:quick-start:start -->` through `<!-- gpd-help:command-index:end -->`.
Exclude the marker comment lines themselves. Append this one wrapper-owned line:
`Run this help command with --command <name> for detailed help on one command.`

Then STOP.

## Step 4: Single Command Detail Extract (--command <name>)

Parse the command name after `--command`. Accept a bare command name or
canonical runtime command, plus the current runtime's native command label. If lookup
includes inline flags or arguments such as `gpd:new-project --minimal`, split
them and normalize to the base command block.

```bash
gpd --raw help --command <name>
```

Pass through the normalized name. If the bridge returns `ok: false` with
`error: "unknown_command"`, output exactly:
`Unknown command. Run this help command with --all for the compact command index.`
If it returns `detail_markdown`, output that renderer-owned markdown without
rewriting it; otherwise render a compact detail block from `canonical_command`,
`description`, `argument_hint`, `context_mode`, `project_reentry_capable`,
`requires`, and `allowed_tools`, including command-context preflight fields.

Workflow-owned reference fallback:

Prefer the generated detail reference file. Normalize to the matching canonical
command inside `<!-- gpd-help:detailed-command-reference:start -->` /
`<!-- gpd-help:detailed-command-reference:end -->`, whose visible heading is `## Detailed Command Reference`.
If unavailable, use the root workflow marker
slice. Output ONLY the smallest matching detailed command block, include the
nearest containing section heading plus matching `Flags:`, `Usage:`, and
`Result:` lines, and stop before the next command block. If no command matches,
output exactly: `Unknown command. Run this help command with --all for the compact command index.`
</process>
