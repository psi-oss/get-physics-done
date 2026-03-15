<purpose>
Conduct a standalone skeptical peer review of a manuscript and supporting artifacts through a staged six-agent panel. The goal is to prevent single-pass, overly charitable reviews of manuscripts that are mathematically coherent but physically weak, novelty-light, or scientifically unconvincing.
</purpose>

<core_principle>
Peer review should be staged, evidence-aware, and fail-closed on unsupported scientific significance. The panel must separate:

1. What the paper claims
2. Whether the literature supports those claims
3. Whether the mathematics is sound
4. Whether the physics is actually supported by the mathematics
5. Whether the result is interesting enough for the claimed venue
6. Whether the paper should be accepted, revised, or rejected

Each stage runs in a fresh subagent context and writes a compact artifact. The final referee decides only after reading those artifacts.
</core_principle>

<process>

<step name="init">
**Initialize context and locate the review target:**

```bash
INIT=$(gpd init phase-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `project_exists`, `state_exists`, `commit_docs`, `project_contract`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`.
Treat `project_contract` and `active_reference_context` as authoritative contract-backed evidence context for later review stages. Stage 1 stays manuscript-first, but later adjudication must not ignore the approved contract or active anchor ledger.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context peer-review "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

**Resolve manuscript target:**

1. If `$ARGUMENTS` names a directory, use it as the candidate paper directory.
2. If `$ARGUMENTS` names a `.tex` or `.md` file, use that file and its parent directory as the review root.
3. Otherwise search, in order:
   - `paper/main.tex`
   - `manuscript/main.tex`
   - `draft/main.tex`

**If no manuscript found:**

```
No manuscript found. Searched: paper/, manuscript/, draft/

Run /gpd:write-paper first, or provide a manuscript path to /gpd:peer-review.
```

Exit.

**Convention verification:**

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — the review panel may flag convention drift."
  echo "$CONV_CHECK"
fi
```

</step>

<step name="load_specialized_review_context">
Use `protocol_bundle_context` from init JSON as additive review guidance.

- If `selected_protocol_bundle_ids` is non-empty, treat the bundle summary as a quick map of which decisive artifacts, benchmark anchors, estimator caveats, or specialized comparisons the manuscript should make visible.
- Use bundle guidance to sharpen skepticism about missing evidence; do **not** use it to invent claims, waive missing comparisons, or overrule the manuscript, `project_contract`, `.gpd/comparisons/*-COMPARISON.md`, `.gpd/paper/FIGURE_TRACKER.md`, or phase summary / verification evidence (`.gpd/phases/*/SUMMARY.md`, `.gpd/phases/*/*-SUMMARY.md`, `.gpd/phases/*/*VERIFICATION.md`).
- Judge the paper by reader-visible claims and surfaced evidence first. Review-support artifacts are scaffolding, not substitutes for contract-backed evidence.
- If no bundle is selected, run the same review pipeline against the manuscript and contract-backed artifacts without any specialized overlay.
</step>

<step name="preflight">
**Run the executable review preflight checks before spawning the review panel:**

```bash
gpd validate review-preflight peer-review --strict
```

If preflight exits nonzero because of missing project state, missing manuscript, degraded review integrity, or missing review-grade paper artifacts, STOP and show the blocking issues.

In strict peer-review mode, `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and a reproducibility manifest are required inputs. Peer review is expected to fail closed when those review-support artifacts are absent or not review-ready.
Passing preflight still does not establish scientific support. Complete manifests and audits cannot rescue missing decisive comparisons, overclaimed conclusions, or absent contract-backed evidence.
</step>

<step name="artifact_discovery">
**Load the supporting artifact set for the review:**

Load the following files:

- The resolved manuscript main file and all nearby `*.tex` section files
- `.gpd/STATE.md`
- `.gpd/ROADMAP.md`
- All summary artifacts matching `.gpd/phases/*/SUMMARY.md` or `.gpd/phases/*/*-SUMMARY.md`
- All `.gpd/phases/*/*VERIFICATION.md` files
- `.gpd/comparisons/*-COMPARISON.md` if present
- `.gpd/paper/FIGURE_TRACKER.md` if present
- `paper/ARTIFACT-MANIFEST.json` if present
- `paper/BIBLIOGRAPHY-AUDIT.json` if present
- `paper/reproducibility-manifest.json` if present
- `paper/PAPER-CONFIG.json` if present
- `paper/references.bib` or `references/references.bib` if present

Infer the target journal from `PAPER-CONFIG.json` when available; otherwise use `unspecified`.

If bundle context is present, compare its decisive-artifact and reference expectations against the actual comparison artifacts and figure tracker. Missing bundle-suggested coverage is a warning unless the manuscript has narrowed the claim honestly; missing contract-backed decisive evidence remains a blocker.

Create the review artifact directory if needed:

```bash
mkdir -p .gpd/review
```
</step>

<step name="round_detection">
**Detect whether this is an initial review or a revision round:**

Check for prior reports and author responses:

```bash
ls .gpd/REFEREE-REPORT*.md 2>/dev/null
ls .gpd/AUTHOR-RESPONSE*.md 2>/dev/null
```

Set:

- `ROUND=1`, `ROUND_SUFFIX=""` for the first review
- `ROUND=2`, `ROUND_SUFFIX="-R2"` if `.gpd/REFEREE-REPORT.md` and `.gpd/AUTHOR-RESPONSE.md` exist
- `ROUND=3`, `ROUND_SUFFIX="-R3"` if `.gpd/REFEREE-REPORT-R2.md` and `.gpd/AUTHOR-RESPONSE-R2.md` exist

Stage artifacts for revision rounds should use the same suffix:

- `.gpd/review/CLAIMS{ROUND_SUFFIX}.json`
- `.gpd/review/STAGE-reader{ROUND_SUFFIX}.json`
- `.gpd/review/STAGE-literature{ROUND_SUFFIX}.json`
- `.gpd/review/STAGE-math{ROUND_SUFFIX}.json`
- `.gpd/review/STAGE-physics{ROUND_SUFFIX}.json`
- `.gpd/review/STAGE-interestingness{ROUND_SUFFIX}.json`
- `.gpd/review/REVIEW-LEDGER{ROUND_SUFFIX}.json`
- `.gpd/review/REFEREE-DECISION{ROUND_SUFFIX}.json`

Use the same `-R2` / `-R3` suffix convention for downstream response artifacts:

- `.gpd/AUTHOR-RESPONSE{ROUND_SUFFIX}.md`
- `.gpd/paper/REFEREE_RESPONSE{ROUND_SUFFIX}.md`

</step>

<step name="stage_1_read">
**Stage 1 — Read the whole manuscript once.**

Resolve reader model:

```bash
READ_MODEL=$(gpd resolve-model gpd-review-reader)
```

> **Runtime delegation:** Spawn a fresh subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-review-reader",
  model="{read_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-reader.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `ClaimIndex` / `StageReviewReport` artifact contract exactly.

Operate in manuscript-reader stage mode. This stage must start nearly fresh and remain manuscript-first.

Target journal: {target_journal}
Round: {round}
Output paths:
- `.gpd/review/CLAIMS{round_suffix}.json`
- `.gpd/review/STAGE-reader{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files

Focus on:
1. Read the whole manuscript end-to-end before consulting project-internal summaries.
2. Extract every central claim into a compact claim index with claim ids and claim types.
3. Flag where abstract/introduction/conclusion overclaim the physics.
4. Do NOT use `STATE.md`, `ROADMAP.md`, or phase summaries as a source of truth for the manuscript's validity.

Return STAGE 1 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 1: manuscript read"
)
```

If Stage 1 fails, STOP. Later stages depend on its claim map.
</step>

<step name="stage_2_and_3">
**Stages 2 and 3 — Run literature and mathematics in parallel when possible.**

Resolve models:

```bash
LITERATURE_MODEL=$(gpd resolve-model gpd-review-literature)
MATH_MODEL=$(gpd resolve-model gpd-review-math)
```

Stage 2 prompt:

```
task(
  subagent_type="gpd-review-literature",
  model="{literature_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-literature.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in literature-context stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Selected protocol bundles: {selected_protocol_bundle_ids}
Additive specialized guidance:
{protocol_bundle_context}
Output path: `.gpd/review/STAGE-literature{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `.gpd/review/CLAIMS{round_suffix}.json`
- `.gpd/review/STAGE-reader{round_suffix}.json`
- `.gpd/comparisons/*-COMPARISON.md` if present
- `.gpd/paper/FIGURE_TRACKER.md` if present
- `paper/BIBLIOGRAPHY-AUDIT.json` if present
- `paper/references.bib` or `references/references.bib` if present

Use targeted web search when novelty, significance, or prior-work positioning is uncertain. Treat novelty-heavy claims as requiring external comparison, not trust. Use bundle reference prompts only as additive hints about which prior-work or benchmark framing should be visible; do not infer novelty or correctness from bundle presence alone.
Return STAGE 2 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 2: literature context"
)
```

Stage 3 prompt:

```
task(
  subagent_type="gpd-review-math",
  model="{math_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-math.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in mathematical-soundness stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Output path: `.gpd/review/STAGE-math{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `.gpd/review/CLAIMS{round_suffix}.json`
- `.gpd/review/STAGE-reader{round_suffix}.json`
- Summary artifacts matching `.gpd/phases/*/SUMMARY.md` or `.gpd/phases/*/*-SUMMARY.md`
- `.gpd/phases/*/*VERIFICATION.md`
- `paper/ARTIFACT-MANIFEST.json` if present
- `paper/reproducibility-manifest.json` if present

Focus on key equations, limits, internal consistency, and approximation validity.
Return STAGE 3 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 3: mathematical soundness"
)
```

If the runtime supports parallel subagent execution, run Stage 2 and Stage 3 in parallel. Otherwise run Stage 2 first, then Stage 3.

If either stage fails, STOP and report the failure.
</step>

<step name="stage_4_physics">
**Stage 4 — Check physical soundness after the mathematical pass.**

Resolve physics model:

```bash
PHYSICS_MODEL=$(gpd resolve-model gpd-review-physics)
```

```
task(
  subagent_type="gpd-review-physics",
  model="{physics_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-physics.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in physical-soundness stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Selected protocol bundles: {selected_protocol_bundle_ids}
Additive specialized guidance:
{protocol_bundle_context}
Output path: `.gpd/review/STAGE-physics{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `.gpd/review/CLAIMS{round_suffix}.json`
- `.gpd/review/STAGE-reader{round_suffix}.json`
- `.gpd/review/STAGE-math{round_suffix}.json`
- `.gpd/review/STAGE-literature{round_suffix}.json`
- Summary artifacts matching `.gpd/phases/*/SUMMARY.md` or `.gpd/phases/*/*-SUMMARY.md`
- `.gpd/phases/*/*VERIFICATION.md`
- `.gpd/comparisons/*-COMPARISON.md` if present
- `.gpd/paper/FIGURE_TRACKER.md` if present

Focus on:
1. Regime of validity
2. Whether the physical interpretation is actually supported
3. Unsupported or unfounded connections between formal manipulations and physics
4. Whether decisive comparison artifacts, benchmark anchors, and estimator caveats expected by the specialized workflow are actually visible in the manuscript or honestly scoped down

Treat bundle guidance as additive skepticism only. It may highlight missing decisive comparisons or estimator caveats, but it must not replace contract-backed evidence or create new manuscript obligations out of thin air.

Return STAGE 4 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 4: physical soundness"
)
```

If Stage 4 fails, STOP and report the failure.
</step>

<step name="stage_5_significance">
**Stage 5 — Judge interestingness and venue fit after the technical stages.**

Resolve significance model:

```bash
SIGNIFICANCE_MODEL=$(gpd resolve-model gpd-review-significance)
```

```
task(
  subagent_type="gpd-review-significance",
  model="{significance_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-review-significance.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md and use its `StageReviewReport` artifact contract exactly.

Operate in interestingness-and-venue-fit stage mode with a fresh context.

Target journal: {target_journal}
Round: {round}
Output path: `.gpd/review/STAGE-interestingness{round_suffix}.json`

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `.gpd/review/CLAIMS{round_suffix}.json`
- `.gpd/review/STAGE-reader{round_suffix}.json`
- `.gpd/review/STAGE-literature{round_suffix}.json`
- `.gpd/review/STAGE-physics{round_suffix}.json`
- `paper/PAPER-CONFIG.json` if present

You must explicitly decide whether the paper is:
1. Scientifically interesting enough for the venue
2. Merely technically competent
3. Overclaimed relative to its actual contribution

Return STAGE 5 COMPLETE with assessment, blocker count, and major concern count.",
  description="Peer review stage 5: significance and venue fit"
)
```

If Stage 5 fails, STOP and report the failure.
</step>

<step name="final_adjudication">
**Stage 6 — Final adjudication by `gpd-referee`.**

Resolve referee model:

```bash
REFEREE_MODEL=$(gpd resolve-model gpd-referee)
```

```
task(
  subagent_type="gpd-referee",
  model="{referee_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-referee.md for your role and instructions.
Then read {GPD_INSTALL_DIR}/references/publication/peer-review-panel.md, {GPD_INSTALL_DIR}/templates/paper/review-ledger-schema.md, and {GPD_INSTALL_DIR}/templates/paper/referee-decision-schema.md before you write any adjudication artifacts.

Act as the final adjudicating referee for the staged peer-review panel.

Target journal: {target_journal}
Round: {round}
Selected protocol bundles: {selected_protocol_bundle_ids}
Additive specialized guidance:
{protocol_bundle_context}
Project Contract:
{project_contract}
Active References:
{active_reference_context}

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `.gpd/review/CLAIMS{round_suffix}.json`
- `.gpd/review/STAGE-reader{round_suffix}.json`
- `.gpd/review/STAGE-literature{round_suffix}.json`
- `.gpd/review/STAGE-math{round_suffix}.json`
- `.gpd/review/STAGE-physics{round_suffix}.json`
- `.gpd/review/STAGE-interestingness{round_suffix}.json`
- `.gpd/comparisons/*-COMPARISON.md` if present
- `.gpd/paper/FIGURE_TRACKER.md` if present
- `paper/ARTIFACT-MANIFEST.json` if present
- `paper/BIBLIOGRAPHY-AUDIT.json` if present
- `paper/reproducibility-manifest.json` if present
- `.gpd/STATE.md`
- `.gpd/ROADMAP.md`
- Summary artifacts matching `.gpd/phases/*/SUMMARY.md` or `.gpd/phases/*/*-SUMMARY.md`
- `.gpd/phases/*/*VERIFICATION.md`

If this is a revision round, also read the latest `REFEREE-REPORT*.md` and matching `AUTHOR-RESPONSE*.md`.

Recommendation guardrails:
1. Do not issue minor revision if novelty, physical support, or significance remain materially doubtful.
2. A mathematically coherent but physically weak or scientifically mediocre paper can require major revision or rejection.
3. Evaluate venue fit explicitly using the panel artifacts and spot-check the manuscript where the artifacts are under-evidenced.
4. Treat protocol bundle guidance as additive context only. It can increase concern when decisive comparisons or benchmark anchors are missing, but it cannot rescue missing evidence or override the manuscript's actual artifact trail.
5. Write `.gpd/review/REVIEW-LEDGER{round_suffix}.json` and `.gpd/review/REFEREE-DECISION{round_suffix}.json`.
6. Run `gpd validate review-ledger .gpd/review/REVIEW-LEDGER{round_suffix}.json`.
7. Run `gpd validate referee-decision .gpd/review/REFEREE-DECISION{round_suffix}.json --strict --ledger .gpd/review/REVIEW-LEDGER{round_suffix}.json` before trusting a recommendation better than `major_revision`.

Write `.gpd/REFEREE-REPORT{round_suffix}.md` and the matching `.gpd/REFEREE-REPORT{round_suffix}.tex`.
Also write `.gpd/CONSISTENCY-REPORT.md` when applicable.

Return REVIEW COMPLETE with recommendation, confidence, issue counts, and whether prior major concerns are resolved.",
  description="Peer review stage 6: final adjudication"
)
```

If the referee agent fails to spawn or returns an error, STOP and report the failure. Do not silently skip final adjudication.
</step>

<step name="optional_pdf_compile">
**Optional PDF compile of the LaTeX referee report:**

If TeX is installed and the runtime allows it, compile the latest referee-report `.tex` file to a matching `.pdf`.

If TeX is missing, do not block the review:

```
Referee review artifacts were written, but a TeX toolchain is not available.
Continue now with `.gpd/REFEREE-REPORT.md` + `.gpd/REFEREE-REPORT.tex` only.
If you want the polished PDF artifact as well, Authorize the agent to install TeX now or compile the `.tex` later in an environment that already has TeX.
```
</step>

<step name="summarize_report">
**Read the latest referee report and summarize the decision:**

1. Identify the most recent referee report among:
   - `.gpd/REFEREE-REPORT.md`
   - `.gpd/REFEREE-REPORT-R2.md`
   - `.gpd/REFEREE-REPORT-R3.md`
2. Extract:
   - recommendation
   - confidence
   - major issue count
   - minor issue count
   - top actionable items

Present:

```markdown
## Peer Review Summary

**Recommendation:** {recommendation}
**Confidence:** {confidence}
**Major issues:** {N}
**Minor issues:** {M}
**Stage artifacts:** `.gpd/review/`
**Report:** {path}
**LaTeX report:** {path or "not written"}
**Consistency report:** {path or "not written"}
```
</step>

<step name="route_next_action">
**Route the outcome based on the recommendation:**

- `accept`: recommend `/gpd:arxiv-submission`
- `minor_revision`: recommend targeted manuscript edits or `/gpd:respond-to-referees`
- `major_revision`: recommend `/gpd:respond-to-referees` and highlight the blocking findings
- `reject`: present the highest-severity issues and recommend returning to research or restructuring the manuscript before another review

If this was a revision round, state the round number and whether the referee considers previous issues resolved, partially resolved, or unresolved.
</step>

</process>

<success_criteria>
- [ ] Project context initialized
- [ ] Manuscript target resolved
- [ ] Review preflight run in strict mode
- [ ] Supporting artifacts loaded when present
- [ ] Claim index written
- [ ] Stage 1 reader artifact written
- [ ] Stage 2 literature-context artifact written
- [ ] Stage 3 mathematical-soundness artifact written
- [ ] Stage 4 physical-soundness artifact written
- [ ] Stage 5 interestingness artifact written
- [ ] Review ledger and referee decision JSON written
- [ ] Final adjudicating gpd-referee executed successfully
- [ ] Latest referee report located and summarized
- [ ] Outcome routed to the correct next action
</success_criteria>
