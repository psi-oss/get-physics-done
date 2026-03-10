# Continuation Format

Standard format for presenting next steps after completing a research command or workflow.

## Core Structure

```
---

## > Next Up

**{identifier}: {name}** -- {one-line description}

`{command to copy-paste}`

<sub>`/clear` first -> fresh context window</sub>

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
4. **`/clear` explanation** -- always include, keeps it concise but explains why
5. **"Also available" not "Other options"** -- sounds more app-like
6. **Visual separators** -- `---` above and below to make it stand out

## Variants

### Execute Next Plan

```
---

## > Next Up

**02-03: Perturbative Corrections** -- Compute one-loop self-energy with RPA screening

`/gpd:execute-phase 2`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- Review plan before executing
- `/gpd:list-phase-assumptions 2` -- check physical assumptions

---
```

### Execute Final Plan in Phase

Add note that this is the last plan and what comes after:

```
---

## > Next Up

**02-03: Perturbative Corrections** -- Compute one-loop self-energy with RPA screening
<sub>Final plan in Phase 2</sub>

`/gpd:execute-phase 2`

<sub>`/clear` first -> fresh context window</sub>

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

`/gpd:plan-phase 2`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:discuss-phase 2` -- gather context first
- `/gpd:research-phase 2` -- investigate unknowns
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

`/gpd:plan-phase 3`

<sub>`/clear` first -> fresh context window</sub>

---

**Also available:**
- `/gpd:discuss-phase 3` -- gather context first
- `/gpd:research-phase 3` -- investigate unknowns
- Review what Phase 2 established

---
```

### Multiple Equal Options

When there's no clear primary action:

```
---

## > Next Up

**Phase 3: Non-perturbative Effects** -- Instanton contributions, resummation, and strong-coupling analysis

**To plan directly:** `/gpd:plan-phase 3`

**To discuss context first:** `/gpd:discuss-phase 3`

**To research unknowns:** `/gpd:research-phase 3`

<sub>`/clear` first -> fresh context window</sub>

---
```

### Milestone Complete

```
---

## Milestone v1.0 Complete

All 4 phases completed

## > Next Up

**Start v1.1** -- questioning -> literature review -> research plan -> roadmap

`/gpd:new-milestone`

<sub>`/clear` first -> fresh context window</sub>

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

```
## To Continue

Run `/clear`, then paste:
/gpd:execute-phase 2
```

User has no idea what 02-03 is about.

### Don't: Missing /clear explanation

```
`/gpd:plan-phase 3`

Run /clear first.
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
/gpd:plan-phase 3
```
````

Fenced blocks inside templates create nesting ambiguity. Use inline backticks instead.
