---
name: gpd:smoke
description: Sniff-test a published claim or an unverified assumption with the smallest reproducible computation
argument-hint: "[claim text] | --assumption \"<text>\" | --from-plan"
context_mode: projectless
allowed-tools:
  - file_read
  - file_write
  - shell
  - ask_user
help:
  group: Validation and analysis
  order: 290
  compact_description: Pre-commit sniff-test for a quantitative claim or an assumption from PLAN.md
  display_signature: gpd:smoke [claim | --assumption "<text>" | --from-plan]
---


<objective>
Reproduce the smallest viable version of a published quantitative claim, or
verify an in-project assumption against its plan, before committing to a
heavier workflow. Smoke is a pre-commit gate: it captures the claim as a
number with a source, proposes the smallest configuration that could plausibly
reproduce it, runs a self-contained scratch script in the working directory,
compares the measured value to the claim, and emits a PASS / FAIL /
INCONCLUSIVE verdict. It does not create a `GPD/` folder, write GPD state, or
hand off into another workflow automatically. The user decides whether the
PASS verdict justifies running `gpd:new-project`, `gpd:plan-phase`, or
`gpd:execute-phase` next.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/smoke.md
</execution_context>

<inline_guidance>

- `gpd:smoke` is a sniff-test primitive with two roles:
  - Pre-project anchor: reproduce a published number before scaffolding with `gpd:new-project`.
  - In-project assumption gate: verify an assumption (from `--assumption` or `--from-plan`) before committing to `gpd:plan-phase` or `gpd:execute-phase`.
- It is NOT `gpd:verify-work` (post-result consistency checks), `gpd:limiting-cases` (analytic-limit audits inside a project), or `gpd:numerical-convergence` (grid-refinement studies). Those run after a result exists; smoke runs before commitment.
- A PASS verdict means "this specific quantitative claim or assumption holds at the tested parameters" — not "the full study will work." Be honest about scope.
- A FAIL verdict means do not commit to the next workflow until the gap is understood.
- Smoke is read-only against `PLAN.md`. It never rewrites the plan.
- Use the working directory for the scratch script. Do not create `GPD/` or any GPD state files from this command.

</inline_guidance>

<process>
Follow the included smoke workflow end-to-end.

Refuse to write code or run anything until the user has confirmed the proposed
minimal setup. The point of smoke is fast feedback with the user in the loop
on the first cycle.

Do not auto-route into `gpd:new-project`, `gpd:plan-phase`, or
`gpd:execute-phase` on PASS. State the recommendation, but require the user to
invoke it explicitly.

If the user provides a claim that is qualitative or lacks a quantitative
anchor, ask once for sharpening; if they cannot or will not provide one, stop
and explain that smoke needs a number to compare against.
</process>
