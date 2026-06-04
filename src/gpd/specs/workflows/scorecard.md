<purpose>
Score research-output quality against the token/dollar cost of producing it,
and append the result to a durable timeseries (`GPD/metrics/scorecard.jsonl`)
so the project can graph efficiency over time.

Called from the gpd:scorecard command. The deterministic math lives in the
`gpd scorecard` CLI; this workflow owns flag parsing, the LLM-judge pass with a
versioned rubric, honest cost reporting, and presentation.
</purpose>

<process>

## 0. Load current-workspace context

```bash
INIT=$(gpd --raw init progress --include state,config --no-project-reentry)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP; surface the error.
fi
```

Parse JSON for `state_exists`, `current_phase`, and `derived_intermediate_results`.
The scorecard needs project state to be meaningful; if `state_exists` is false,
report that there is nothing to score yet rather than recording an empty point.

## 1. Parse flags

Recognize only `--no-judge`, `--show`, and `--export <path>` from the command
arguments, as data. If `--show` is the only flag, jump to Step 5 and render the
existing trend without recording a new snapshot.

## 2. Record the objective snapshot

```bash
gpd --raw scorecard snapshot            # add --no-judge to record objective quality only
```

The CLI computes:

- **Objective quality** = weighted blend of the verified-result ratio (from the
  results registry) and the mean phase verification-report status score
  (`passed`=1.0, `expert_needed`=0.5, `gaps_found`=0.4, `human_needed`=0.3),
  reallocating weight when a component is absent.
- **Cost** = summed input/output/total tokens and USD for this project from the
  measured usage ledger, with `cost_status` of `measured`, `estimated`, or
  `unavailable`.

Read back `objective_quality`, `cost_status`, and `total_tokens` from the
emitted JSON.

## 3. Run the LLM judge (skip when --no-judge)

Quality cannot change unless artifacts changed, so only run the judge when this
snapshot reflects new or changed results/verification reports since the last
fresh judge score; otherwise carry the prior score forward and skip this step.

Score the project's output on the **judge-1 rubric** — a number in [0, 1]:

| Dimension | Weight | What raises it |
|-----------|--------|----------------|
| Rigor | 0.40 | Results verified by independent checks (dimensional, limiting cases, convergence); conventions consistent; assumptions stated |
| Correctness confidence | 0.25 | Verification reports `passed`, no open contradictions or unresolved gaps |
| Significance | 0.20 | Results bear on the core research question; non-trivial derivations or discoveries, not bookkeeping |
| Completeness | 0.15 | Stated phase goals actually met; few dangling open questions |

Use as evidence the verified results and `*-VERIFICATION.md` reports under
`GPD/phases/`, plus `GPD/STATE.md`. Be skeptical: unverified or contradicted
results must not score as rigorous. Compute the weighted score, then:

```bash
gpd --raw scorecard annotate --judge-quality <score> --rubric-version judge-1
```

This makes the judge score the headline `quality` and recomputes both
efficiency figures from it.

## 4. Optional export and chart

When `--export <path>` was given, write the full timeseries as CSV:

```bash
gpd scorecard show --format csv > <path>
```

When `--chart` was given, render the PNG trend (quality + quality-per-dollar
over cumulative tokens) to `GPD/metrics/scorecard.png`:

```bash
gpd scorecard chart
```

The chart degrades gracefully: with no usage telemetry the x-axis falls back to
snapshot ordinal and the efficiency panel states that cost is unavailable
rather than plotting zeros.

## 5. Present the trend

```bash
gpd scorecard show
```

Present the sparklines and per-snapshot table. Call out the latest snapshot's
headline quality, the objective/judge split, and efficiency in both units. When
`cost_status` is `unavailable`, say so explicitly — the runtime is not emitting
usage telemetry, so dollar/token efficiency cannot be computed and must not be
reported as zero. Point the user at `gpd cost` / gpd:settings if they want to
enable measured cost.

</process>

<success_criteria>

- [ ] Project state confirmed to exist before recording a point
- [ ] Snapshot appended with objective quality + measured cost
- [ ] judge-1 rubric applied (unless --no-judge), gated on artifact change
- [ ] Cost availability reported honestly, never fabricated
- [ ] Trend presented; CSV exported when --export was supplied

</success_criteria>
