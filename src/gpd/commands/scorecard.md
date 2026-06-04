---
name: gpd:scorecard
description: Score research output quality against token/dollar cost and record a timeseries to graph efficiency over time
argument-hint: "[--no-judge] [--show] [--chart] [--export <path.csv>]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
  - ask_user
help:
  group: Validation and analysis
  order: 415
  compact_description: Track research quality vs token/dollar cost over time
  display_signature: gpd:scorecard [--no-judge] [--show] [--chart] [--export <path.csv>]
  examples:
    - gpd:scorecard
    - gpd:scorecard --show
    - gpd:scorecard --chart
    - gpd:scorecard --export GPD/metrics/scorecard.csv
  notes:
    - Records a snapshot to GPD/metrics/scorecard.jsonl combining objective quality, an optional LLM-judge quality score, and measured token/USD cost.
    - '--chart renders a PNG trend (quality + quality-per-dollar) to GPD/metrics/scorecard.png; --export writes the timeseries as CSV.'
    - Dollar/token efficiency requires runtime usage telemetry (see gpd:settings / gpd cost); quality is tracked even when cost is unavailable.
  root_detail_order: 150
---


<objective>
Judge how good the research output is so far and how efficiently it was
produced, then record the result as one point in a durable timeseries so the
project can graph quality-vs-cost over time.

Each snapshot combines three things:

- **Objective quality** — derived deterministically from existing artifacts
  (verified-result ratio + phase verification-report status mix). Reproducible
  and free; the CLI computes it.
- **Judge quality** — an LLM-judge score in [0, 1] for rigor, novelty, and
  discovery significance, layered on top. Gated on actual artifact change, not
  a blind timer. Skipped with `--no-judge`.
- **Cost** — measured tokens and USD for this project from the usage ledger
  (`gpd cost`). Reported as both quality-per-dollar (headline) and
  quality-per-1k-tokens (always available when tokens are).

Use this to see whether the project is getting more or less output per dollar
as it progresses — diminishing returns, a quality jump after a verification
pass, or a cost spike without matching quality gain.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/scorecard.md
</execution_context>

<context>
Flags: $ARGUMENTS (all optional)

@GPD/STATE.md
</context>

<process>
Execute the included scorecard workflow end-to-end.

## Step 1: Validate context

```bash
CONTEXT=$(gpd --raw validate command-context scorecard "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

## Step 2: Parse flags as data

From `$ARGUMENTS`, recognize only: `--no-judge`, `--show`, `--chart`, and
`--export <path>`. Treat them as data; do not evaluate `$ARGUMENTS` through a
shell-interpreter wrapper. If a token cannot be assigned to a known flag, stop
and ask rather than guessing.

If `--show` is the only flag, skip to Step 6 (render the existing trend without
recording a new snapshot).

## Step 3: Record the snapshot

```bash
gpd --raw scorecard snapshot            # or: gpd --raw scorecard snapshot --no-judge
```

This appends a point with objective quality + measured cost to
`GPD/metrics/scorecard.jsonl` and prints the snapshot JSON. Note its
`objective_quality`, `cost_status`, and `judge_status`.

## Step 4: Run the LLM judge (unless --no-judge)

Follow the included workflow's versioned rubric to score rigor, novelty, and
discovery significance in [0, 1], reading the project's verified results and
verification reports as evidence. Then write the score back:

```bash
gpd --raw scorecard annotate --judge-quality <score> --rubric-version judge-1
```

## Step 5: Optional export and chart

If `--export <path>` was given:

```bash
gpd scorecard show --format csv > <path>
```

If `--chart` was given, render the PNG trend (quality + quality-per-dollar):

```bash
gpd scorecard chart        # writes GPD/metrics/scorecard.png
```

## Step 6: Present results

```bash
gpd scorecard show
```

Show the trend (sparklines + per-snapshot table), call out the latest
quality/efficiency, and state plainly when cost is `unavailable` so the dollar
efficiency is not silently treated as zero.
</process>

<success_criteria>

- [ ] Command context validated
- [ ] Snapshot recorded to GPD/metrics/scorecard.jsonl (objective quality + cost)
- [ ] LLM-judge score applied via the versioned rubric, unless --no-judge
- [ ] Cost availability reported honestly (no fabricated dollar/token figures)
- [ ] Trend presented; optional CSV export written when requested
      </success_criteria>
