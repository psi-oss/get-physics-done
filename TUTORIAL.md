# GPD in Codex: Simple Tutorial

This file shows the basic way to use GPD inside Codex.

The key thing: in Codex, GPD commands are typed as chat commands like:

```text
$gpd-progress
```

They are not shell commands.

## 1. Start a new project

### Full mode

Type:

```text
$gpd-new-project
```

GPD will then ask questions. Reply in plain English.

Example:

```text
I want to study Newton's laws of motion with simple simulations.
Start with constant force, gravity, and linear drag.
Use basic numerical checks and analytic formulas.
```

### Minimal mode

If you want a faster bootstrap:

```text
$gpd-new-project --minimal
```

Then give one short project description.

Example:

```text
I want to build simple experiments to study Newton's laws of motion.
Phase 1: write the equations for constant force, gravity, and linear drag.
Phase 2: run simple simulations.
Phase 3: compare simulation results with analytic formulas.
```

### Minimal mode from a markdown file

If you already wrote a short plan:

```text
$gpd-new-project --minimal @plan.md
```

### Auto mode

If you have a longer proposal document and want the workflow to run with less back-and-forth:

```text
$gpd-new-project --auto @proposal.md
```

## 2. Check where you are

If you are unsure what to do next, use:

```text
$gpd-progress
```

This is the safest default command in an existing project.

## 3. Discuss a phase before planning

If you want to guide the approach for a phase:

```text
$gpd-discuss-phase 1
```

This is where you clarify things like assumptions, conventions, scope boundaries, and preferred methods.

## 4. Plan a phase

To create the actual plan for the phase:

```text
$gpd-plan-phase 1
```

If you want to skip the discussion step:

```text
$gpd-plan-phase 1
```

If you want a lighter plan:

```text
$gpd-plan-phase 1 --light
```

## 5. Inspect the phase

To see what the phase contains:

```text
$gpd-show-phase 1
```

## 6. Execute the phase

Once the phase is planned:

```text
$gpd-execute-phase 1
```

## 7. Verify the results

After execution:

```text
$gpd-verify-work 1
```

## 8. Typical workflow

For most projects, the normal sequence in Codex is:

```text
$gpd-new-project
$gpd-progress
$gpd-discuss-phase 1
$gpd-plan-phase 1
$gpd-show-phase 1
$gpd-execute-phase 1
$gpd-verify-work 1
$gpd-progress
```

Then continue with the next phase:

```text
$gpd-discuss-phase 2
$gpd-plan-phase 2
$gpd-execute-phase 2
$gpd-verify-work 2
```

## 9. One small worked example

You type:

```text
$gpd-new-project --minimal
```

Then GPD asks for a description, and you reply:

```text
I want to study Newton's laws with simple simulations.
Phase 1: derive equations.
Phase 2: simulate trajectories.
Phase 3: validate against known formulas.
```

Then you continue with:

```text
$gpd-progress
$gpd-discuss-phase 1
$gpd-plan-phase 1
$gpd-execute-phase 1
$gpd-verify-work 1
```

## 10. Quick command meanings

- `$gpd-new-project`: create a new `.gpd/` project
- `$gpd-progress`: show status and next suggested step
- `$gpd-discuss-phase N`: clarify how to approach a phase
- `$gpd-plan-phase N`: create the phase plan
- `$gpd-show-phase N`: inspect phase artifacts
- `$gpd-execute-phase N`: run the phase
- `$gpd-verify-work N`: verify the results
- `$gpd-help --all`: show the larger command reference

## Best rule

If you are lost, type:

```text
$gpd-progress
```
