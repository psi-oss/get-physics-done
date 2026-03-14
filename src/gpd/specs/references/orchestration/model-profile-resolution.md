# Model Profile Resolution

Resolve model profile once at the start of orchestration, then resolve each agent's tier and optional runtime-specific model override before spawning Task calls.

Do not scrape `.gpd/config.json` directly in workflows. Runtime selection, defaults, and runtime-specific model overrides are owned by the canonical CLI helpers:

- `gpd resolve-tier`
- `gpd resolve-model`

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

`gpd resolve-model` prints a concrete model name only when project config contains a matching `model_overrides.<runtime>.<tier>` entry for the active runtime. Otherwise it prints nothing so the runtime's own default model is used.

Model override strings are runtime-native and are not normalized by GPD:

- Preserve the exact identifier or alias syntax accepted by the active runtime.
- Keep provider prefixes, slash-delimited ids, bracket suffixes, and other runtime-native punctuation intact.
- If the runtime already uses a non-default provider or model source, keep that provider's exact identifier format.

## Profile Change Guidance

The orchestrator should NOT auto-switch profiles. If the current work suggests a different profile, inform the user and recommend the explicit change:

```
Current profile: review
This phase involves heavy numerical simulation. Consider switching:
  /gpd:set-profile numerical
```

## Usage

1. Resolve once at orchestration start using `gpd resolve-tier` / `gpd resolve-model`
2. Store the resolved tier/model values for the current orchestration step
3. Omit the `model` parameter when `gpd resolve-model` prints nothing
4. If the user wants a different profile, switch it explicitly with `/gpd:set-profile ...`
