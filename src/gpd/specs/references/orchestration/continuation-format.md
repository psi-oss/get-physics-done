# Continuation Format

Standard format for presenting next steps after completing a research command or workflow.
This format is a presentation layer only: the displayed next step is derived from canonical continuation and recovery state, and it does not establish project authority by itself.

## Core Structure

```
---

## > Next Up

**{identifier}: {name}** -- {one-line description}

`{command to copy-paste}`

<sub>Start a fresh context window, then run `{next command}`</sub>

---

**Also available:**
- `{alternative option 1}` -- description
- `{alternative option 2}` -- description

---
```

## Format Rules

1. **Always show what it is** -- name + description, never just a command path
2. **Pull context from source** -- ROADMAP.md for phases, PLAN.md `<objective>` for plans
3. **Command in inline code** -- backticks, easy to copy-paste, renders as clickable link
4. **Fresh context explanation** -- always include it, and pair it with the next command instead of leaving it as a dead-end. If project rediscovery is still required, say so explicitly and point to `gpd resume` or `gpd resume --recent` before reopening the runtime; do not treat the fresh context reset as project recovery.
5. **"Also available" not "Other options"** -- sounds more app-like
6. **Visual separators** -- `---` above and below to make it stand out
7. **Derived, not authoritative** -- the message is a projection of the current recovery decision, not a competing source of truth

## Stop And Checkpoint Rules

Every user-visible completion, checkpoint, blocked return, failed return, retry gate, or stop that expects later action must end with this block. Do not end on labels such as "ready", "continue", "retry", "review", or "stop here" unless the same final section gives the exact command or artifact action.

Use this routing unless a workflow has a more specific command:

- Resumable handoff/checkpoint persisted: primary `gpd:resume-work`; include `gpd:suggest-next`
- Same workflow should be retried after user edits input: show the exact original command, e.g. `gpd:new-project --minimal @file.md`
- Phase lacks context: primary `gpd:discuss-phase N`; alternative `gpd:plan-phase N`
- Phase has context but no plan: primary `gpd:plan-phase N`; include `gpd:research-phase N` when discovery is needed
- Phase has plans to execute: primary `gpd:execute-phase N`
- Verification gaps exist: primary `gpd:plan-phase N --gaps`; after gap plans exist, `gpd:execute-phase N --gaps-only`; confirm with `gpd:verify-work N`
- Convention issue blocks progress: primary `gpd:validate-conventions`; include `gpd:resume-work` after repair
- No clear primary route: primary `gpd:suggest-next`

## Variants

### Execute Next Plan

```
---

## > Next Up

**02-03: Perturbative Corrections** -- Compute one-loop self-energy with RPA screening

`gpd:execute-phase 2`

<sub>Start a fresh context window, then run `gpd:execute-phase 2`</sub>

---

**Also available:**
- Review plan before executing
- `gpd:list-phase-assumptions 2` -- check physical assumptions

---
```

### Execute Final Plan in Phase

Add note that this is the last plan and what comes after:

```
---

## > Next Up

**02-03: Perturbative Corrections** -- Compute one-loop self-energy with RPA screening
<sub>Final plan in Phase 2</sub>

`gpd:execute-phase 2`

<sub>Start a fresh context window, then run `gpd:execute-phase 2`</sub>

---

**After this completes:**
- Phase 2 -> Phase 3 transition
- Next: **Phase 3: Non-perturbative Effects** -- Instanton contributions and resummation

---
```

### Plan a Phase

```
---

## > Next Up

**Phase 2: Linear Response** -- Compute susceptibilities and response functions

`gpd:plan-phase 2`

<sub>Start a fresh context window, then run `gpd:plan-phase 2`</sub>

---

**Also available:**
- `gpd:discuss-phase 2` -- gather context first
- `gpd:research-phase 2` -- investigate unknowns
- Review roadmap

---
```

### Phase Complete, Ready for Next

Show completion status before next action:

```
---

## Phase 2 Complete

3/3 plans executed

## > Next Up

**Phase 3: Non-perturbative Effects** -- Instanton contributions, resummation, and strong-coupling analysis

`gpd:plan-phase 3`

<sub>Start a fresh context window, then run `gpd:plan-phase 3`</sub>

---

**Also available:**
- `gpd:discuss-phase 3` -- gather context first
- `gpd:research-phase 3` -- investigate unknowns
- Review what Phase 2 established

---
```

### Multiple Equal Options

When there's no clear primary action:

```
---

## > Next Up

**Phase 3: Non-perturbative Effects** -- Instanton contributions, resummation, and strong-coupling analysis

**To plan directly:** `gpd:plan-phase 3`

**To discuss context first:** `gpd:discuss-phase 3`

**To research unknowns:** `gpd:research-phase 3`

<sub>Start a fresh context window, then run the chosen command below</sub>

---
```

### Milestone Complete

```
---

## Milestone v1.0 Complete

All 4 phases completed

## > Next Up

**Start v1.1** -- questioning -> literature review -> research plan -> roadmap

`gpd:new-milestone`

<sub>Start a fresh context window, then run `gpd:new-milestone`</sub>

---
```

## Pulling Context

### For phases (from ROADMAP.md):

```markdown
### Phase 2: Linear Response

**Goal:** Compute susceptibilities and response functions in RPA
```

Extract: `**Phase 2: Linear Response** -- Compute susceptibilities and response functions in RPA`

### For plans (from ROADMAP.md):

```markdown
Plans:

- [ ] 02-03: Compute perturbative corrections to self-energy
```

Or from PLAN.md `<objective>`:

```xml
<objective>
Compute one-loop self-energy with RPA-screened interaction.

Purpose: Obtain quasiparticle lifetime and effective mass renormalization.
</objective>
```

Extract: `**02-03: Perturbative Corrections** -- Compute one-loop self-energy with RPA screening`

## Anti-Patterns

### Don't: Command-only (no context)

```text
## To Continue

Start a fresh context window, then run the concrete next command:
gpd:execute-phase 2
```

User has no idea what 02-03 is about.

### Don't: Missing fresh-context explanation

```text
`gpd:plan-phase 3`

Start a fresh context window, then run the command.
```

Doesn't explain why. User might skip it.

### Don't: "Other options" language

```
Other options:
- Review roadmap
```

Sounds like an afterthought. Use "Also available:" instead.

### Don't: Fenced code blocks for commands

````
```
gpd:plan-phase 3
```
````

Fenced blocks inside templates create nesting ambiguity. Use inline backticks instead.
