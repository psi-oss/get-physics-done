---
load_when:
  - "publication mode"
  - "autonomy mode"
  - "research mode"
  - "explore exploit"
  - "paper writing mode"
  - "referee strictness"
  - "bibliographer search"
tier: 2
context_cost: medium
---
# Publication Pipeline Mode Adaptation

How the bibliographer, referee, and paper-writer agents adapt their behavior based on the project's **autonomy mode** (`config.autonomy`) and **research mode** (`config.research_mode`). These modes are orthogonal — any autonomy mode can combine with any research mode.

**Load when:** Starting a paper-writing phase, configuring project modes, or calibrating publication pipeline behavior.

**Related files:**
- `references/planning/planning-config.md` — Config schema including `autonomy` and `research_mode` fields
- `references/orchestration/model-profiles.md` — Model profile system (deep-theory/numerical/exploratory/review/paper-writing)
- `references/orchestration/agent-infrastructure.md` — Agent spawning and orchestration

---

## Mode Configuration

```json
{
  "autonomy": "guided",
  "research_mode": "balanced"
}
```

Set via: `gpd config-set autonomy guided` and `gpd config-set research_mode balanced`.

Read via: `gpd init` includes both fields in the init JSON output.

---

## Bibliographer Mode Adaptation

The bibliographer's search breadth, verification depth, and citation completeness expectations change with research mode.

### By Research Mode

| Behavior | Explore | Balanced | Exploit | Adaptive |
|---|---|---|---|---|
| **Search breadth** | Wide: 3+ databases, 50+ results per query, follow citation networks 2 hops deep | Standard: 2 databases, 20 results, 1-hop citations | Narrow: known references only, verify existing .bib, add only directly cited works | Starts wide, narrows after approach selection |
| **Database priority** | INSPIRE + ADS + arXiv + Google Scholar | INSPIRE + arXiv | Project .bib + INSPIRE for verification | Adapts based on hit rate |
| **Hallucination check depth** | Verify ALL citations: title, authors, year, journal, DOI | Verify new citations; spot-check existing | Verify only newly added; trust project .bib | Full verify in explore, spot-check in exploit |
| **Missing citation warnings** | Aggressive: flag any equation without attribution, flag any claim without reference | Standard: flag key results without attribution | Minimal: only flag direct quotations without citation | Matches current phase mode |
| **Related work discovery** | Active: suggest 5-10 related papers per phase, build citation network graph | Standard: suggest 2-3 related papers when relevant | Passive: only when explicitly requested | Active in explore, passive in exploit |
| **arXiv monitoring** | Check daily listings in relevant categories | Check weekly | Disabled | Enabled during explore phases |

### By Autonomy Mode

| Behavior | Supervised | Guided | Autonomous | YOLO |
|---|---|---|---|---|
| **Citation addition** | Propose additions, wait for user approval before modifying .bib | Add verified citations automatically, checkpoint on uncertain matches | Fully automatic: add, verify, format without checkpoints | Fully automatic, skip verification of well-known references |
| **Conflicting sources** | Present both sources and ask user which to cite | Present conflict and recommend based on citation count + recency | Auto-resolve: cite the more cited/recent source, note the conflict in comments | Auto-resolve without noting |
| **Bibliography restructuring** | Never restructure without explicit request | Suggest restructuring when .bib exceeds 100 entries | Auto-restructure: group by topic, remove duplicates, standardize keys | Auto-restructure aggressively |

---

## Referee Mode Adaptation

The referee's strictness, scope of critique, and recommendation threshold change with research mode.

### By Research Mode

| Behavior | Explore | Balanced | Exploit | Adaptive |
|---|---|---|---|---|
| **Strictness level** | Lenient: focus on fundamental correctness and novel insights. Accept incomplete results if direction is promising. | Standard: full 10-dimension evaluation. Expect complete verification and clear presentation. | Strict: publication-ready standards. Every claim must be verified, every approximation justified with bounds, every figure with error bars. | Lenient in early phases, strict in final phases |
| **Novelty evaluation** | Emphasize: is the approach interesting? Could it lead somewhere new? | Standard: is the result new? How does it compare to prior work? | De-emphasize novelty, emphasize correctness and completeness. The approach is known; the question is whether it's executed correctly. | Evaluate novelty in explore, correctness in exploit |
| **Missing analysis tolerance** | High: accept "future work" for secondary checks. Core result must be dimensionally consistent and have one limiting case. | Medium: expect 7-check verification floor. Missing Tier 4 checks noted but not blocking. | Low: all 15 verification checks required. Missing checks are major revisions. | Adapts with phase |
| **Recommendation thresholds** | Accept with minor revisions only if the manuscript is honest about being exploratory. If the physics story or significance is overstated, escalate to major revision. | Standard thresholds from referee rubric plus explicit checks on claim proportionality, physical support, and venue fit. | Accept only with no remaining issues. Any unresolved physics question or overstated claim → major revision or reject. | Strict in final milestone, lenient otherwise |
| **Scope of critique** | Broad: comment on direction, methodology choice, alternative approaches. | Standard: correctness, completeness, presentation. | Narrow: is this specific result correct and well-presented? Don't question methodology choice. | Broad early, narrow late |

**Hard override for manuscript peer review:** when the review scope is a manuscript or a target journal is named, venue standards dominate. `research_mode` may change how much evidence is likely to exist, but it may NOT lower the novelty, significance, claim-evidence, or venue-fit thresholds needed for `accept` or `minor_revision`.

In manuscript review:

- `minor_revision` is forbidden when central claims must be narrowed.
- mathematically consistent but physically weak work is at least `major_revision`, and often `reject` for PRL/Nature-style venues.
- unsupported physical connections or inflated significance claims are publication-relevant blockers, not stylistic issues.

### By Autonomy Mode

| Behavior | Supervised | Guided | Autonomous | YOLO |
|---|---|---|---|---|
| **Report delivery** | Full report with line-by-line comments. Present to user for discussion before any action. | Summary report with prioritized issues. User reviews before executor acts on feedback. | Report goes directly to paper-writer for revision. User sees revised version. | Report triggers automatic revision cycle. User sees final product only. |
| **Revision authority** | Referee identifies issues; user decides which to address. | Referee identifies issues; AI addresses critical/major automatically, presents minor for user decision. | Referee identifies issues; AI addresses all, including scope adjustments within bounds. | Referee + AI iterate until all issues resolved or circuit breaker triggers. |
| **Dispute resolution** | User arbitrates any disagreement between referee assessment and research results. | AI attempts resolution for technical issues; escalates physics judgment calls to user. | AI resolves all disputes using verification evidence. Escalates only genuine contradictions. | No escalation — AI makes final call on all disputes. |

---

## Paper-Writer Mode Adaptation

The paper-writer's style, detail level, and structural choices change with research mode.

### By Research Mode

| Behavior | Explore | Balanced | Exploit | Adaptive |
|---|---|---|---|---|
| **Paper structure** | Letter/rapid communication format. 4-6 pages. Focus on key result and implications. Extended methods in supplemental. | Standard article. Full introduction, methods, results, discussion. 8-15 pages. | Comprehensive article or review-style. Full derivation details, extensive appendices, complete error analysis. 15-30 pages. | Letter for preliminary results, full article for final |
| **Derivation detail** | Sketch key steps, cite derivation files for details. "As shown in the supplementary material..." | Show important intermediate steps. Full derivation for novel results, sketch for standard ones. | Show all steps for novel results. Reproduce standard results if the application is non-trivial. Include all intermediate algebra. | Sketchy early, detailed final |
| **Figure strategy** | 2-4 key figures. Schematic diagrams welcome. Qualitative plots acceptable. | 5-8 figures. All with proper axes, labels, error bars where applicable. Mix of schematic and quantitative. | 8-15 figures. Every numerical result plotted. Convergence evidence shown. Comparison with literature in every relevant figure. | Grows with project maturity |
| **Literature integration** | Cite 10-20 key references. Focus on framing the problem and claiming novelty. | Cite 30-50 references. Thorough related work section. Discuss agreements and discrepancies with prior results. | Cite 50-100+ references. Comprehensive literature comparison. Discuss every relevant prior result and explain any disagreement. | Expands from explore to exploit |
| **Error discussion** | Brief: "systematic uncertainties are estimated to be O(10%)" | Standard: explicit error budget with statistical and systematic components | Comprehensive: full error propagation, sensitivity analysis, comparison of multiple methods, discussion of limitations | Grows with phase |

### By Autonomy Mode

| Behavior | Supervised | Guided | Autonomous | YOLO |
|---|---|---|---|---|
| **Section drafting** | Draft one section at a time. Present to user for review before next section. | Draft a full first draft. Present for review. Iterate on feedback. | Draft, self-review (via referee agent), revise, present polished draft. | Complete paper autonomously. Present only when ready for submission. |
| **Notation decisions** | Ask user for notation preferences before writing. | Use project conventions. Flag any notation choices not covered by convention lock. | Make notation choices following conventions. Resolve ambiguities by consistency with the most-cited reference. | Make all notation choices. |
| **Abstract writing** | Draft abstract, present for user editing. Abstract is the most user-visible text. | Draft abstract and suggest 2-3 alternatives with different emphasis. | Write abstract optimized for search visibility and citation. | Write and finalize abstract. |

---

## Mode Interaction Matrix

When autonomy and research modes combine, the publication pipeline exhibits emergent behavior:

| Combination | Pipeline Behavior |
|---|---|
| **Supervised + Explore** | Maximum user involvement in a discovery-oriented project. User guides literature search, approves every citation, discusses referee feedback interactively. Best for: student mentoring, unfamiliar territory. |
| **Supervised + Exploit** | User closely controls a focused calculation. Every result checked by user before paper. Best for: high-stakes publications, experimental theory comparisons. |
| **Guided + Balanced** | **DEFAULT.** Standard research workflow. AI handles routine tasks, user makes physics decisions. Best for: most research projects. |
| **Guided + Explore** | AI-assisted exploration with user oversight on direction. Good for: new research directions, literature surveys, methodology comparisons. |
| **Autonomous + Exploit** | Maximum efficiency for well-defined calculations. AI drives the full pipeline from derivation to paper draft. User reviews at milestone boundaries. Best for: production calculations (lattice QCD, DFT parameter sweeps). |
| **Autonomous + Explore** | AI-driven research exploration. Multiple hypothesis branches pursued in parallel. Risk of scope creep — circuit breakers essential. Best for: preliminary studies, parameter space scans. |
| **YOLO + Exploit** | Fastest possible execution. Full automation from calculation to submission-ready paper. Circuit breakers on verification failures only. Best for: well-tested calculations with established methodology. |
| **YOLO + Explore** | **DANGER ZONE.** Maximum autonomy in uncharted territory. High risk of pursuing dead ends without user correction. Recommended only for low-stakes exploratory work. |

---

## Circuit Breakers Across Modes

Regardless of autonomy mode, these conditions ALWAYS trigger a hard stop and user notification:

| Trigger | Action | Applies In |
|---|---|---|
| Verification check 5.1 (dimensional analysis) fails | Hard stop. Derivation has fundamental error. | All modes |
| Variational bound violated (E_trial < E_exact) | Hard stop. Calculation is wrong. | All modes |
| Convention lock mismatch detected | Hard stop. Convention drift will corrupt all downstream results. | All modes |
| Hallucinated citation detected (title/authors don't match any database) | Hard stop in supervised/guided. Auto-remove in autonomous/YOLO. | All modes (severity varies) |
| Referee report: "reject" recommendation | Hard stop in all modes. Major issues must be addressed before proceeding. | All modes |
| 3 consecutive verification failures on same result | Hard stop. Systematic problem requiring human judgment. | All modes |
| Cost budget exceeded (>2x estimated) | Pause and notify in supervised/guided. Continue with warning in autonomous/YOLO. | All modes |

---

## Implementation Notes

**For agent prompt authors:** Each publication pipeline agent should read `config.autonomy` and `config.research_mode` from the init JSON and adapt behavior according to this document. The adaptation is behavioral (prompt interpretation), not code-level — no new commands are needed.

**For workflow authors:** The write-paper, literature-review, and audit-milestone workflows should pass the mode settings to spawned agents in the Task prompt. Example:

```
Current modes: autonomy={autonomy}, research_mode={research_mode}
Adapt your search breadth, strictness, and checkpoint frequency accordingly.
See references/publication/publication-pipeline-modes.md for mode specifications.
```

**For the orchestrator:** Mode transitions (explore → exploit) should be triggered by the `suggest-next` command or by the planner when a viable approach is validated. The orchestrator should:
1. Read current mode from config
2. Check if transition conditions are met (approach validated, convergence achieved, etc.)
3. Propose transition to user (guided mode) or execute it (autonomous mode)
4. Update config via `config-set research_mode exploit`

---

## See Also

- `references/planning/planning-config.md` — Full config schema
- `references/orchestration/model-profiles.md` — Model profile system (orthogonal to modes)
- `references/orchestration/checkpoints.md` — Checkpoint types and frequencies
- `references/orchestration/agent-infrastructure.md` — Agent spawning and context allocation
