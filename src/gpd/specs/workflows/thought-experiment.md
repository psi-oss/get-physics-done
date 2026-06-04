<purpose>
Run structured Gedanken (thought) experiments around a physical question and
distill them into candidate theoretical postulates and conjectures — the
creative inspiration that precedes a rigorous derivation or proof. Produce
either a phase-scoped `THOUGHT-EXPERIMENTS.md` or a standalone
`GPD/analysis/thought-experiment-{slug}.md` rooted at the current workspace.
</purpose>

<core_principle>
Inspiration and proof are different jobs and must not be confused. This workflow
optimizes for physically motivated breadth: it generates many candidate
postulates from idealized scenarios, then discards the obviously-wrong ones with
the cheapest available physics checks (dimensions, symmetry, conservation,
known limits). Every postulate that survives is still an explicitly unproven
conjecture. The deliverable is a ranked set of conjectures, each paired with the
concrete rigorous step that would confirm or refute it — never a claim that any
postulate is established.
</core_principle>

<references>
Use `references/results/result-lookup-policy.md` for canonical result lookup when
a thought experiment needs to anchor against an existing project result.
Use `{GPD_INSTALL_DIR}/references/analysis/physics-validation-recipes.md` for the
cheap-check catalogs (dimensional consistency, symmetry/conservation arguments,
limiting-case sanity checks) used to filter candidate postulates.
Use `{GPD_INSTALL_DIR}/references/methods/approximation-selection.md` when a
thought experiment turns on the validity regime of an approximation.
</references>

<process>

## 0. Validate Context, Load Workspace State, and Resolve the Target

Run centralized command-context preflight first:

```bash
CONTEXT=$(gpd --raw validate command-context thought-experiment "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  # STOP; surface the error.
fi
```

Parse `project_exists`, `checks`, and `managed_output_root`, then classify one
target:

This workflow is non-interactive: it never opens a prompt or blocks waiting for
input. The subject must come from `$ARGUMENTS`.

| Condition | Action |
| --- | --- |
| Empty input (project or standalone) | stop and print guidance: re-run with an explicit topic (e.g. `gpd:thought-experiment "<question>"`) or a phase number. Do not prompt. |
| Current project + bare phase number | set `TARGET_KIND=phase`, `PHASE_ARG=<number>` |
| Explicit topic text (anywhere) | set `TARGET_KIND=topic`, `TOPIC=<text>` |
| Anything else | stop and print guidance naming what to pass (topic or phase number). Do not prompt. |

Load workspace-bound state and conventions without project reentry:

```bash
INIT=$(gpd --raw init progress --include state,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP; surface the error.
fi
```

Parse conventions, the unit system, active approximations, validity ranges, and
`intermediate_results`. These bound which thought experiments are physically
admissible and which known limits a postulate must respect.

If `TARGET_KIND=phase`, resolve the phase inside the current workspace:

```bash
PHASE_INIT=$(gpd --raw init phase-op --include state,config "${PHASE_ARG}")
if [ $? -ne 0 ]; then
  echo "ERROR: thought-experiment phase resolution failed: $PHASE_INIT"
  # STOP; surface the error.
fi
```

Parse `phase_found`, `phase_dir`, `phase_number`, `phase_name`, and
`phase_slug`; stop if a requested phase is absent. Set target/output variables:

| Target kind | Variables |
| --- | --- |
| phase | `TARGET_LABEL="phase ${phase_number}"`; `OUTPUT_DIR="${phase_dir}"`; `OUTPUT_PATH="${phase_dir}/THOUGHT-EXPERIMENTS.md"` |
| topic | stable ASCII `slug` from the topic; `TARGET_LABEL="${TOPIC}"`; `OUTPUT_DIR="GPD/analysis"`; `OUTPUT_PATH="GPD/analysis/thought-experiment-{slug}.md"` rooted at the current workspace |

Only topic mode creates `GPD/analysis`. Reuse the resolved `TARGET_KIND`, `slug`,
`OUTPUT_DIR`, and `OUTPUT_PATH` variables consistently. The panel writes its
per-lens scratch artifacts under `${OUTPUT_DIR}/thought-experiments-{slug}/`.
Never write standalone/current-workspace thought-experiment artifacts under
`GPD/phases/**`.

## 1. Frame the Question

State the phenomenon under study in one or two sentences, then make the framing
precise:

- the system and its degrees of freedom;
- the quantity of interest and what "explaining" it would mean;
- the governing regime (energies, scales, couplings) and which conventions and
  active project approximations apply;
- what is already known or assumed (anchor to project results or stored results
  via the result-lookup policy when relevant);
- the boundary of ignorance — the specific gap a postulate would fill.

A good thought experiment targets that boundary, not settled physics.

## 2. Generate Thought Experiments — Multi-Lens Panel

Generate breadth by fanning out a panel of independent `gpd-thought-experimenter`
agents, one per generative lens, rather than free-associating in a single
context. Each lens explores a different way the question can crack open, and the
agents are blind to each other so the set stays genuinely diverse.

Lenses (spawn one agent each): `idealized-limits`, `symmetry-invariance`,
`conservation-bookkeeping`, `analogy-correspondence`, `adversarial-paradox`.

Create the per-run lens directory and resolve the agent model once:

```bash
LENS_DIR="${OUTPUT_DIR}/thought-experiments-{slug}"   # phase: ${phase_dir}/thought-experiments-{slug}; topic: GPD/analysis/thought-experiments-{slug}
mkdir -p "${LENS_DIR}"
TE_MODEL=$(gpd resolve-model gpd-thought-experimenter)
```

@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

Spawn the lenses **in parallel**, each writing a disjoint scoped file so no two
agents share a writable target. Repeat this block once per lens, substituting
`{lens}` and keeping every other field identical:

```
task(
  subagent_type="gpd-thought-experimenter",
  model="{te_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-thought-experimenter.md for your role and instructions.

Assigned lens: {lens}
Framed question: {framed_question}
Conventions and unit system: {conventions_summary}
Active project approximations and validity ranges: {approximations_summary}
Known anchors (project or stored results to respect): {known_anchors}

Apply ONLY your assigned lens. Generate 2–4 thought experiments, distill them into
falsifiable candidate postulates, and self-check each with cheap physics checks
(dimensions, symmetry, conservation, known limits, order of magnitude).

Write to: ${LENS_DIR}/lens-{lens}.md

<spawn_contract>
write_scope:
  mode: scoped_write
  allowed_paths:
    - ${LENS_DIR}/lens-{lens}.md
expected_artifacts:
  - one lens artifact at the path above
shared_state_policy: return_only
</spawn_contract>

Return a status envelope summarizing your lens, postulate counts, and your single
strongest surviving conjecture. Present nothing as established.",
  description="Thought-experiment lens {lens}"
)
```

If the runtime cannot spawn subagents, fall back to executing each lens
sequentially in the main context using the same lens instructions and the same
`${LENS_DIR}/lens-{lens}.md` write targets.

## 3. Synthesize and Extract Candidate Postulates

Read every produced `${LENS_DIR}/lens-*.md` artifact. Merge their candidate
postulates into one list, deduplicating near-identical conjectures that several
lenses surfaced (a postulate corroborated by independent lenses is stronger —
note the corroboration rather than dropping it silently). Confirm each surviving
conjecture is crisp and falsifiable, with a parameter dependence or inequality
where possible; sharpen any that the agents left vague. Record each postulate's
originating lens(es) for provenance.

## 4. Cross-Lens Plausibility Filter (cheap checks only)

The panel agents self-checked within their lens; you now re-check the merged set
as a whole, so a postulate that looked fine in isolation but conflicts with
another lens's result is caught. This is sanity-filtering, not proof. Apply the
cheapest physics checks:

- **dimensions** — is the statement dimensionally consistent?
- **symmetry / invariance** — does it respect the system's required symmetries
  and the conventions loaded in Step 0?
- **conservation** — does it violate energy/charge/information conservation?
- **known limits** — does it reduce to an accepted result in a regime where the
  answer is known? (Reuse limiting-case reasoning from the analysis recipes.)
- **order of magnitude** — does any implied estimate land in a sane range?

Classify each postulate as `survives`, `tension` (a check is suggestive but
inconclusive), or `refuted` (a cheap check kills it). Record the exact failing
check for refuted candidates — a fast refutation is a real result worth keeping.

## 5. Rank and Propose the Rigorous Next Step

For each surviving postulate, assess promise (explanatory reach × falsifiability
÷ effort to test) and pair it with the concrete rigorous follow-up that would
settle it:

- a derivation target → `gpd:derive-equation`;
- a parallel alternative worth isolating → `gpd:branch-hypothesis`;
- a body of work that needs planning → `gpd:plan-phase`;
- a focused numerical or limiting check → `gpd:limiting-cases` /
  `gpd:numerical-convergence`.

Rank survivors so the highest-promise, lowest-cost conjecture is the suggested
next action.

## 6. Generate Report

Write `${OUTPUT_PATH}` with:

- target and output path;
- the framed question and its boundary of ignorance;
- the thought experiments (setup, idealization, reasoning, conclusion);
- the candidate postulates table with filter status (`survives` / `tension` /
  `refuted`) and the failing check for refuted entries;
- the ranked surviving conjectures, each with its proposed rigorous next step;
- an explicit caveat that all postulates are unproven conjectures.

Use a postulates table such as:

```markdown
## Candidate Postulates for {Question}

| # | Postulate (conjecture) | Lens(es) | Cheap checks | Status | Next step |
|---|------------------------|----------|--------------|--------|-----------|
```

The synthesized report is the durable artifact. The per-lens scratch files under
`${OUTPUT_DIR}/thought-experiments-{slug}/` are provenance; reference them but do
not duplicate their full contents into `${OUTPUT_PATH}`.

If `TARGET_KIND=phase`, `${OUTPUT_PATH}` is `${phase_dir}/THOUGHT-EXPERIMENTS.md`.
If `TARGET_KIND=topic`, `${OUTPUT_PATH}` is
`GPD/analysis/thought-experiment-{slug}.md` rooted at the current workspace.

## 7. Present Results, then Offer to Act

Summarize the framed question, the count of postulates generated / surviving /
refuted, the lenses that contributed, and the single highest-promise conjecture.
Always present postulates as inspiration, never as results.

Then offer to act on the top-ranked survivor (ask once, act only on explicit
confirmation — never auto-fire a side effect):

- if the next step is a derivation, offer to launch `gpd:derive-equation` for it;
- if it is a parallel alternative worth isolating, offer to open a
  `gpd:branch-hypothesis` branch with the conjecture as the hypothesis;
- otherwise offer to capture it with `gpd:add-todo` so it is not lost.

If the user declines, stop after reporting the artifact path and the suggested
commands — leave the choice with them. Do not chain into a derivation or branch
without confirmation, and do not treat acting on the conjecture as confirming it.

## 8. Finalize Persistence Honestly

Do not run an unconditional standalone docs commit for this workflow.

- If `TARGET_KIND=phase`, `state_exists` is true, and `commit_docs` is enabled,
  you may include `${OUTPUT_PATH}` in the phase's normal documentation commit
  path after reviewing the diff.
- If the run is standalone/current-workspace topic mode, skip the commit step
  entirely and report `${OUTPUT_PATH}` back to the user.
- Do not mutate `STATE.md` or `state.json` from standalone/current-workspace
  topic mode.

Optional phase-backed commit flow:

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: thought experiments and candidate postulates — ${phase_slug}" \
  --files "${OUTPUT_PATH}"
```

Only run the commit block when the report is phase-backed and the project is
already in its normal docs-commit path.

</process>

<output>
`${OUTPUT_PATH}` written with framed question, thought experiments, filtered
candidate postulates, and ranked surviving conjectures with rigorous next steps.
</output>

<success_criteria>
- [ ] Target classified through command-context preflight.
- [ ] Workspace state and conventions loaded with
  `gpd --raw init progress --include state,config --no-project-reentry`.
- [ ] `TARGET_KIND`, `slug`, and `OUTPUT_PATH` reused consistently.
- [ ] Question framed with an explicit boundary of ignorance.
- [ ] A `gpd-thought-experimenter` panel fanned out one agent per lens (or the
  sequential fallback ran), each writing a disjoint scoped lens artifact.
- [ ] Lens artifacts synthesized into one deduplicated, provenance-tagged set of
  falsifiable candidate postulates.
- [ ] Each postulate filtered by cheap checks and classified survives/tension/refuted.
- [ ] Surviving postulates ranked and paired with a rigorous next step.
- [ ] Report generated at `${OUTPUT_PATH}` with an unproven-conjecture caveat.
- [ ] Top survivor offered as an action (`gpd:derive-equation` /
  `gpd:branch-hypothesis` / `gpd:add-todo`), acted on only with confirmation.
- [ ] Standalone/current-workspace outputs stay under `GPD/analysis/` and skip
  state mutation and commits.
</success_criteria>
</output>
