# Get Physics Done (GPD)

[![CI](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml/badge.svg)](https://github.com/physicalsuperintelligence/get-physics-done/actions/workflows/test.yml)

An autonomous physics research system. Describe a problem in plain English, and GPD handles the rest — formalization, literature context, derivations, numerical verification, and paper writing.

## Install

```bash
npx github:physicalsuperintelligence/get-physics-done
```

Prompts you to select your coding agent (Claude Code, OpenCode, Gemini CLI, or Codex) and installs GPD.

## Use

In your coding agent, run:

```
/gpd:new-project
```

GPD will ask you about your physics problem, then automatically:

1. **Formulate** — Asks targeted questions to pin down scope, assumptions, and notation
2. **Plan** — Creates a phased research roadmap with requirements and success criteria
3. **Execute** — Spawns specialist agents to derive equations, write code, run simulations
4. **Verify** — Checks dimensional consistency, limiting cases, energy conservation, numerical stability

Each phase produces real artifacts: `.tex` derivations, `.py` verification scripts, `.pdf` figures.

## Commands

| Command | What it does |
|---------|-------------|
| `/gpd:new-project` | Start a new research project |
| `/gpd:plan-phase N` | Plan phase N (research + task breakdown) |
| `/gpd:execute-phase N` | Execute all plans in phase N |
| `/gpd:verify-work` | Run verification checks |
| `/gpd:progress` | Check where you are and what's next |
| `/gpd:discuss-phase N` | Gather context before planning |
| `/gpd:quick` | Fast mode for simple tasks |

## Example

```
> /gpd:new-project
> Derive the equations of motion for a double pendulum using Lagrangian mechanics

GPD will:
- Ask 3-5 clarifying questions (scope, notation, verification targets)
- Create PROJECT.md, REQUIREMENTS.md, ROADMAP.md
- Plan 3 phases: kinematics → Euler-Lagrange EOMs → numerical verification
- Execute each phase with SymPy verification (22+ automated checks)
- Produce LaTeX derivations and Python validation scripts
```

## Requirements

- Python 3.11+
- One of: Claude Code, OpenCode, Gemini CLI, or Codex
- API key for your LLM provider (Anthropic, OpenAI, or Google)

