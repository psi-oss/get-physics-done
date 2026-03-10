<purpose>
Conduct a standalone skeptical peer review of a manuscript and supporting artifacts. This wraps the `gpd-referee` agent with review-grade preflight gates and summary routing, so peer review is a first-class publication workflow rather than only a substep of `write-paper`.
</purpose>

<core_principle>
Peer review should be reproducible, evidence-aware, and artifact-aware. A manuscript is reviewed in the context of its figures, citations, verification evidence, and supporting research outputs. The goal is not to produce a vague opinion, but a structured referee report that can drive the next action.
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

Parse JSON for: `project_exists`, `state_exists`, `commit_docs`.

**If `project_exists` is false:**

```
ERROR: No project found.

Peer review requires a GPD project with a manuscript or completed research artifacts.
Run /gpd:new-project first.
```

Exit.

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
CONV_CHECK=$(gpd convention check --raw 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — the referee may flag convention drift."
  echo "$CONV_CHECK"
fi
```

</step>

<step name="preflight">
**Run the executable review preflight checks before spawning the referee:**

```bash
gpd validate review-preflight peer-review --strict
```

If preflight exits nonzero because of missing project state, missing manuscript, degraded review integrity, or missing review-grade paper artifacts, STOP and show the blocking issues.

In strict peer-review mode, `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and a reproducibility manifest are required inputs. Peer review is expected to fail closed when those review-support artifacts are absent or not review-ready.
</step>

<step name="artifact_discovery">
**Load the supporting artifact set for the review:**

Load the following files:

- The resolved manuscript main file and all nearby `*.tex` section files
- `.gpd/STATE.md`
- `.gpd/ROADMAP.md`
- All `.gpd/phases/*/SUMMARY.md` files
- All `.gpd/phases/*/*VERIFICATION.md` files
- `paper/ARTIFACT-MANIFEST.json` if present
- `paper/BIBLIOGRAPHY-AUDIT.json` if present
- `paper/reproducibility-manifest.json` if present
- `paper/PAPER-CONFIG.json` if present
- `paper/references.bib` or `references/references.bib` if present

Infer the target journal from `PAPER-CONFIG.json` when available; otherwise use `unspecified`.
</step>

<step name="spawn_referee">
Resolve referee model:

```bash
REFEREE_MODEL=$(gpd resolve-model gpd-referee --raw)
```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolved to `null`, omit it. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-referee",
  model="{referee_model}",
  prompt="First, read {GPD_AGENTS_DIR}/gpd-referee.md for your role and instructions.

Conduct a skeptical peer review of the resolved manuscript and its supporting research artifacts.

Scope: Manuscript review
Target journal: {target_journal}

Files to read:
- Resolved manuscript main file and all nearby section .tex files
- `paper/ARTIFACT-MANIFEST.json` if present
- `paper/BIBLIOGRAPHY-AUDIT.json` if present
- `paper/reproducibility-manifest.json` if present
- `paper/PAPER-CONFIG.json` if present
- `paper/references.bib` or `references/references.bib` if present
- `.gpd/STATE.md`
- `.gpd/ROADMAP.md`
- `.gpd/phases/*/SUMMARY.md`
- `.gpd/phases/*/*VERIFICATION.md`

Evaluate across all 10 dimensions with emphasis on:
1. Correctness -- dimensional analysis, limiting cases, sign conventions, approximation validity
2. Completeness -- all promised results delivered, uncertainties and error analysis present
3. Literature context -- citations, prior work, novelty positioning
4. Reproducibility -- artifact manifest, bibliography audit, reproducibility coverage, stated computational details
5. Publishability -- whether the manuscript is ready, needs revision, or should be rejected

Write `.gpd/REFEREE-REPORT.md` (or the next revision-round report if prior author responses exist).
Also write `.gpd/CONSISTENCY-REPORT.md` when applicable.

Return REVIEW COMPLETE with recommendation, confidence, and issue counts.",
  description="Peer review manuscript"
)
```

**If the referee agent fails to spawn or returns an error:** STOP and report the failure. Do not silently skip peer review, because this command exists specifically to produce the referee assessment.
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
**Report:** {path}
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
- [ ] gpd-referee executed successfully
- [ ] Latest referee report located and summarized
- [ ] Outcome routed to the correct next action
</success_criteria>
