# Model Profile Resolution

Resolve model profile once at the start of orchestration, then use it for all Task spawns.

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

Look up the agent in the table for the resolved profile. Pass the model parameter to Task calls:

```
task(
  prompt="...",
  subagent_type="gpd-planner",
  model="{resolved_model}"  # e.g., "tier-1" resolved to platform model for deep-theory profile
)
```

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
3. Look up each agent's tier from the table when spawning
4. Pass model parameter to each Task call (on single-model platforms, tier resolves to null — use default model)
