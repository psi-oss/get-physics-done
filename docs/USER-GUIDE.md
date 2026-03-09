# GPD User Guide

GPD (Get Physics Done) is an autonomous physics research system that runs inside your AI agent. You describe a problem, GPD asks clarifying questions, then handles formalization, derivation, numerical verification, and paper writing.

This guide is for physicists using GPD day-to-day. For architecture and internals, see [ARCHITECTURE.md](../ARCHITECTURE.md).

---

## Quick Start

### 1. Install GPD

```bash
pip install get-physics-done
```

Or with uv:

```bash
uv pip install get-physics-done
```

### 2. Set up your AI agent

```bash
gpd install
```

This auto-detects your runtime (Claude Code, OpenCode, Gemini CLI, or Codex) and installs all GPD commands and agents. If you use multiple runtimes, run `gpd install` in each.

### 3. Start your first project

In your AI agent, run:

```
/gpd:new-project
```

GPD will ask 3-5 questions to pin down your problem's scope, assumptions, notation, and verification targets. Answer them, and GPD creates your project structure.

---

## The GPD Workflow

A typical GPD project follows four stages:

### 1. New Project (`/gpd:new-project`)

GPD asks targeted questions about your physics problem:
- What exactly are you solving?
- What coordinate system and notation?
- What approximations are acceptable?
- How will you verify the result?

It then creates:
- `PROJECT.md` -- problem statement, scope, assumptions
- `REQUIREMENTS.md` -- success criteria, verification targets
- `ROADMAP.md` -- phased research plan
- `STATE.md` -- live project state (GPD updates this automatically)

### 2. Plan a Phase (`/gpd:plan-phase N`)

Before executing, GPD plans phase N in detail:
- Breaks the phase into concrete tasks
- Identifies dependencies between tasks
- Sets milestones and verification checkpoints
- Estimates effort

Use `/gpd:discuss-phase N` first if you want to explore the phase interactively before committing to a plan.

### 3. Execute a Phase (`/gpd:execute-phase N`)

GPD spawns specialist agents to carry out the plan:
- Derivation agents write LaTeX equations step by step
- Verification agents check dimensional consistency, limiting cases, conservation laws
- Numerical agents write and run Python validation scripts
- Each task produces artifacts (`.tex`, `.py`, figures)

You can watch progress and intervene at any point.

### 4. Verify Work (`/gpd:verify-work`)

Runs the full verification suite:
- Dimensional analysis on all equations
- Limiting case checks (does it reduce correctly?)
- Symmetry verification
- Conservation law checks
- Numerical stability tests
- Sign convention consistency
- Index consistency (tensors, summations)

---

## How Questions Work

GPD frequently asks questions rather than guessing. When it asks:

1. **Answer directly.** GPD parses your response and continues.
2. **Say "skip"** to use GPD's default assumption.
3. **Say "I don't know"** and GPD will research the answer or flag it as an open question.

Questions appear at natural decision points: before choosing a coordinate system, when an approximation could go multiple ways, or when a derivation has branching paths.

---

## Key Commands

| Command | Description |
|---------|-------------|
| `/gpd:new-project` | Start a new research project from scratch |
| `/gpd:plan-phase N` | Plan phase N with task breakdown |
| `/gpd:execute-phase N` | Execute all tasks in phase N |
| `/gpd:verify-work` | Run verification checks on current work |
| `/gpd:progress` | Show current status and next steps |
| `/gpd:discuss-phase N` | Interactively explore phase N before planning |
| `/gpd:quick` | Fast mode for simple, single-step tasks |
| `/gpd:derive-equation` | Derive a specific equation step by step |
| `/gpd:dimensional-analysis` | Check dimensional consistency |
| `/gpd:error-propagation` | Propagate uncertainties through expressions |
| `/gpd:compare-branches` | Compare alternative solution approaches |
| `/gpd:branch-hypothesis` | Fork the project to test a hypothesis |
| `/gpd:audit-milestone` | Review milestone completion and quality |
| `/gpd:check-todos` | List outstanding tasks and blockers |
| `/gpd:decisions` | Review and record research decisions |
| `/gpd:discover` | Find available GPD capabilities |
| `/gpd:estimate-cost` | Estimate computational cost of a plan |
| `/gpd:error-patterns` | Check for known error patterns in your work |

Run `/gpd:discover` inside your agent to see the full list of available commands.

---

## Working with Conventions and Notation

GPD enforces notation consistency across your entire project. When you start a project, it locks conventions for up to 17 physics fields:

- Coordinate system (Cartesian, spherical, cylindrical, ...)
- Metric signature (+--- or -+++)
- Index placement (up/down) and summation convention
- Unit system (SI, CGS, natural, ...)
- Sign conventions (potential energy, Fourier transform, ...)

Once locked, GPD flags any deviation. To change a convention mid-project, use an explicit decision record rather than silently switching -- GPD will help you propagate the change through existing work.

---

## Tips for Better Results

**Be specific about your problem.** "Derive the equations of motion for a double pendulum" works. "Do some classical mechanics" does not.

**Use standard notation.** GPD understands standard physics notation. If you use non-standard symbols, define them upfront.

**Set verification targets.** Tell GPD what a correct answer looks like: "In the limit of small angles, this should reduce to two uncoupled harmonic oscillators."

**Verify numerically.** GPD can generate Python scripts that check your analytical results against numerical integration. Use this -- it catches sign errors, missing factors of 2, and other common mistakes.

**Work in phases.** Break large problems into phases. GPD handles this naturally, but explicit phasing gives you more control and better checkpoints.

**Review intermediate results.** GPD produces artifacts at each step. Read the `.tex` derivations and `.py` scripts -- they're the actual work product, not just logs.

---

## Troubleshooting

### GPD commands not appearing in my agent

Run `gpd install` again. If you recently updated GPD (`pip install --upgrade get-physics-done`), reinstall to pick up new commands.

### "GPD state not found" or missing STATE.md

You're not in a GPD project directory. Either `cd` into your project or run `/gpd:new-project` to create one.

### Verification checks failing unexpectedly

Check that your conventions are set correctly (`/gpd:progress` shows current conventions). A common cause is mismatched sign conventions between derivation steps.

### Agent seems stuck or looping

Use `/gpd:progress` to see where GPD is in the workflow. If a phase is stuck, try `/gpd:debug` to get diagnostic information.

### Slow performance

GPD makes multiple LLM calls per phase. For faster iteration on simple tasks, use `/gpd:quick` instead of the full project workflow.

### Want to change a decision made earlier

Use `/gpd:decisions` to review past decisions, then explicitly override. GPD will propagate the change and re-verify affected work.
