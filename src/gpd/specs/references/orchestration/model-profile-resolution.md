# Model Profile Resolution

Resolve model profile once at the start of orchestration, then resolve each agent's tier and optional runtime-specific model override before spawning Task calls.

## Resolution Pattern

```bash
MODEL_PROFILE=$(cat .gpd/config.json 2>/dev/null | grep -o '"model_profile"[[:space:]]*:[[:space:]]*"[^"]*"' | grep -o '"[^"]*"$' | tr -d '"' || echo "review")
```

Default: `review` if not set or config missing.

## Valid Profiles

- `deep-theory` - Maximum rigor, formal proofs, exact solutions
- `numerical` - Computational focus, convergence analysis, simulation pipelines
- `exploratory` - Creative, broad search, hypothesis generation
- `review` - Validation-heavy, cross-checking (default)
- `paper-writing` - Narrative, presentation, coherent argumentation

## Lookup Table

references/orchestration/model-profiles.md

Look up the agent in the table for the resolved profile. Use `gpd resolve-tier` when you need the abstract tier for debugging, and `gpd resolve-model` when you need the concrete runtime override:

```
TIER=$(gpd resolve-tier gpd-planner)
MODEL=$(gpd resolve-model gpd-planner)

task(
  prompt="...",
  subagent_type="gpd-planner",
  model="{MODEL}"  # Omit if MODEL is empty
)
```

`gpd resolve-model` prints a concrete model name only when `.gpd/config.json` contains a matching `model_overrides.<runtime>.<tier>` entry for the active runtime. Otherwise it prints nothing so the runtime's own default model is used.

## Profile Selection Heuristic

When the user does not explicitly set a profile, the orchestrator may infer the appropriate profile from the research context:

| Context Signal                                    | Suggested Profile |
| ------------------------------------------------- | ----------------- |
| "derive", "prove", "exact solution", "theorem"    | `deep-theory`     |
| "simulate", "convergence", "discretize", "mesh"   | `numerical`       |
| "explore", "survey", "brainstorm", "what if"      | `exploratory`     |
| "check", "verify", "reproduce", "validate"        | `review`          |
| "write up", "draft", "manuscript", "presentation" | `paper-writing`   |

The orchestrator should NOT auto-switch profiles. If signals suggest a different profile, inform the user:

```
Current profile: review
This phase involves heavy numerical simulation. Consider switching:
  /gpd:set-profile numerical
```

## Usage

1. Resolve once at orchestration start
2. Store the profile value
3. Look up each agent's tier from the table when spawning, or call `gpd resolve-tier`
4. Call `gpd resolve-model` for the active runtime and omit the `model` parameter when it returns empty
