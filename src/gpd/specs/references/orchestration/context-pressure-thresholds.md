# Context Pressure Thresholds

Standardized context pressure monitoring thresholds for all GPD agents. This file covers per-agent threshold calibration. For workflow-level context budgeting (how to segment plans, when to /clear, token cost estimates), see `references/orchestration/context-budget.md`.

**Default thresholds** (from `references/orchestration/agent-infrastructure.md`):

| Level | Threshold | Action |
|---|---|---|
| GREEN | < 40% | Proceed normally |
| YELLOW | 40-60% | Prioritize remaining work, skip optional depth |
| ORANGE | 60-75% | Complete current unit of work only, write checkpoint, prepare handoff |
| RED | > 75% | STOP immediately, write checkpoint with progress so far, return with CHECKPOINT status |

## Per-Agent Thresholds

Agents override defaults based on their context consumption patterns. Agents that read many files or produce large outputs need lower thresholds.

| Agent | GREEN | YELLOW | ORANGE | RED | Unit of Work | Rationale |
|---|---|---|---|---|---|---|
| **Shared default** | < 40% | 40-60% | 60-75% | > 75% | -- | Baseline for agents without special needs |
| gpd-consistency-checker | < 30% | 30-45% | 45-60% | > 60% | phase pair | Reads many cross-phase artifacts; needs headroom for compliance matrix |
| gpd-debugger | < 30% | 30-50% | 50-65% | > 65% | investigation technique | Must hold hypothesis context, evidence history, and eliminated alternatives simultaneously |
| gpd-literature-reviewer | < 35% | 35-50% | 50-60% | > 60% | review area | Each paper reviewed ~2-3%; many papers needed for thorough review |
| gpd-phase-researcher | < 35% | 35-50% | 50-65% | > 65% | research area | web_search results ~2-4% each; synthesize after 8-10 searches |
| gpd-project-researcher | < 35% | 35-50% | 50-65% | > 65% | research area | Same as phase-researcher; limit to 10-15 searches before synthesizing |
| gpd-planner | < 35% | 35-50% | 50-65% | > 65% | plan file | Large plan output (~5-8% per plan); keep plans concise |
| gpd-plan-checker | < 35% | 35-50% | 50-65% | > 65% | plan check | Each verification dimension ~2-3%; exploratory (8 dims) vs comprehensive (15 dims) |
| gpd-executor | < 40% | 40-55% | 55-70% | > 70% | task | Tracks both input and output; forced checkpoint at 50% regardless of task status |
| gpd-review-reader | < 35% | 35-50% | 50-65% | > 65% | manuscript section | Full-manuscript reading stage; summarize claims early rather than hoarding text |
| gpd-review-literature | < 35% | 35-50% | 50-60% | > 60% | claim cluster | Literature search results accumulate quickly; synthesize overlap after each claim cluster |
| gpd-review-math | < 35% | 35-50% | 50-60% | > 60% | equation cluster | Keep only the 3-5 claim-central equations live; externalize side calculations immediately |
| gpd-review-physics | < 35% | 35-50% | 50-60% | > 60% | physical claim cluster | Focus on regime-of-validity and claim-support tables rather than full derivation history |
| gpd-review-significance | < 35% | 35-50% | 50-60% | > 60% | venue-fit dimension | Compare contribution vs venue bar explicitly; avoid retaining unnecessary derivation detail |
| gpd-referee | < 40% | 40-50% | 50-65% | > 65% | evaluation dimension | Start with 5 critical dimensions, expand if budget allows |
| gpd-bibliographer | < 40% | 40-55% | 55-70% | > 70% | reference verification | Each reference verified ~1-2%; batch verifications |
| gpd-experiment-designer | < 40% | 40-55% | 55-70% | > 70% | design section | Standard consumption pattern |
| gpd-research-synthesizer | < 40% | 40-60% | 60-70% | > 70% | synthesis section | Loading 4-5 researcher outputs consumes ~20-30% before synthesis |
| gpd-paper-writer | < 40% | 40-55% | 55-65% | > 65% | paper section | Each section ~5-10%; focus on assigned sections only |
| gpd-roadmapper | < 40% | 40-60% | 60-75% | > 75% | phase design | Standard consumption; for 8+ phases use concise descriptions |
| gpd-research-mapper | < 40% | 40-60% | 60-75% | > 75% | focus area document | Each focus area ~5-8%; limit exploration depth |
| gpd-notation-coordinator | < 45% | 45-60% | 60-75% | > 75% | convention category | Produces shorter outputs; process one category at a time |
| gpd-verifier | -- | -- | -- | ~75% | verification check | Single trigger only; no graduated levels |

## Threshold Clusters

Three clusters based on how aggressively agents must manage context:

**Conservative (GREEN < 30-35%):** Agents that read many cross-phase files or must maintain extensive internal state.
- consistency-checker, debugger, literature-reviewer, phase-researcher, project-researcher, planner, plan-checker

**Standard (GREEN < 40%):** Agents with typical read/write patterns.
- executor, referee, bibliographer, experiment-designer, research-synthesizer, paper-writer, roadmapper, research-mapper

**Lenient (GREEN 40-45%):** Agents that produce short outputs or work with focused inputs.
- notation-coordinator

## Estimation Heuristics

| Activity | Estimated Cost | Notes |
|---|---|---|
| File read | ~2-5% | Larger files cost more |
| web_search result | ~2-4% | Search results vary in length |
| Substantial output block | ~1-3% | Derivations, analyses, code |
| Plan file produced | ~5-8% | Complex plans with task breakdowns |
| Paper section drafted | ~5-10% | Equations and text combined |
| Focus area document | ~5-8% | Structured analysis documents |
| Reference verified via search | ~1-2% | Short verification cycles |

**Running estimate formula:** `(files_read x 3%) + (output_blocks x 2%)`

**Recall test:** If you cannot recall conventions from the start of the session, you are likely past ORANGE.

## Behaviors at Each Level

### GREEN
- Proceed normally with full depth and thoroughness

### YELLOW
- Prioritize remaining work items by importance
- Skip optional elaboration and depth
- Compress verbose output

### ORANGE
- Complete ONLY the current unit of work (see table)
- Write checkpoint with all progress
- Include `context_pressure: high` in output envelope
- Prepare handoff notes for continuation agent

### RED
- **STOP immediately** -- do not start new work
- Write checkpoint with everything completed so far
- Return with `status: checkpoint` so orchestrator spawns continuation
- Include clear next-action instructions for the continuation agent
