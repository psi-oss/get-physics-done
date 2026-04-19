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
  "autonomy": "balanced",
  "research_mode": "balanced"
}
```

Set via: `gpd config set autonomy balanced` and `gpd config set research_mode balanced`.

Read via: `gpd --raw init` includes both fields in the init JSON output.

---

## Publication Boundary Across Modes

Mode adaptation changes drafting, bibliography, and review behavior. It does not widen publication intake policy.

For the bounded `gpd:write-paper` external-authoring lane:

- accept one explicit intake manifest only
- keep all GPD-authored durable outputs under `GPD/publication/{subject_slug}/...`
- treat `GPD/publication/{subject_slug}/manuscript/` as the only manuscript/build root
- treat `GPD/publication/{subject_slug}/intake/` as intake/provenance state only
- during bounded write-paper authoring, keep the subject-owned publication root at `GPD/publication/{subject_slug}` bounded to manuscript and intake state; later standalone peer-review or response workflows may bind their own round-artifact family there explicitly
- do not mine arbitrary folders or infer claim/evidence bindings from loose notes
- do not widen `gpd:arxiv-submission`, claim full publication-root migration, or claim embedded external staged-review parity; route authored-manuscript review to standalone `gpd:peer-review` when that bounded lane needs review

The same autonomy and research-mode knobs still apply inside that bounded lane, but they cannot relax the manifest requirement or broaden the publication-root contract.

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

| Behavior | Supervised | Balanced | YOLO |
|---|---|---|---|
| **Citation addition** | Propose additions and wait for approval before modifying `.bib`. | Add verified citations automatically. Pause only for uncertain matches, borderline relevance, or citation-scope changes. | Fully automatic; skip verification of canonical references when confidence is already high. |
| **Conflicting sources** | Present both sources and ask the user which to cite. | Recommend based on citation count, recency, and venue fit. Auto-resolve routine metadata conflicts; pause on substantive source disagreements. | Auto-resolve without pausing unless the conflict changes the paper's claim. |
| **Bibliography restructuring** | Never restructure without explicit request. | Auto-clean duplicates and normalize keys when the change is mechanical. Suggest larger restructures before applying them. | Auto-restructure aggressively for speed and consistency. |

---

## Referee Mode Adaptation

The referee's strictness, scope of critique, and recommendation threshold change with research mode.

### By Research Mode

| Behavior | Explore | Balanced | Exploit | Adaptive |
|---|---|---|---|---|
| **Strictness level** | Lenient: focus on fundamental correctness and novel insights. Accept incomplete results if direction is promising. | Standard: full 10-dimension evaluation. Expect complete verification and clear presentation. | Strict: publication-ready standards. Every claim must be verified, every approximation justified with bounds, every figure with error bars. | Lenient in early phases, strict in final phases |
| **Novelty evaluation** | Emphasize: is the approach interesting? Could it lead somewhere new? | Standard: is the result new? How does it compare to prior work? | De-emphasize novelty, emphasize correctness and completeness. The approach is known; the question is whether it's executed correctly. | Evaluate novelty in explore, correctness in exploit |
| **Missing analysis tolerance** | High: accept "future work" for secondary checks. Core result must be dimensionally consistent and have one limiting case or other decisive anchor. | Medium: expect broad universal verification plus the required contract-aware checks. Missing domain-specific depth may be noted, but decisive checks still must be present. | Low: full relevant verifier-registry coverage required. Missing checks are major revisions. | Adapts with phase |
| **Recommendation thresholds** | Accept with minor revisions only if the manuscript is honest about being exploratory. If the physics story or significance is overstated, escalate to major revision. | Standard thresholds from referee rubric plus explicit checks on claim proportionality, physical support, and venue fit. | Accept only with no remaining issues. Any unresolved physics question or overstated claim → major revision or reject. | Strict in final milestone, lenient otherwise |
| **Scope of critique** | Broad: comment on direction, methodology choice, alternative approaches. | Standard: correctness, completeness, presentation. | Narrow: is this specific result correct and well-presented? Don't question methodology choice. | Broad early, narrow late |

**Hard override for manuscript peer review:** when the review scope is a manuscript or a target journal is named, venue standards dominate. `research_mode` may change how much evidence is likely to exist, but it may NOT lower the novelty, significance, claim-evidence, or venue-fit thresholds needed for `accept` or `minor_revision`.

In manuscript review:

- `minor_revision` is forbidden when central claims must be narrowed.
- mathematically consistent but physically weak work is at least `major_revision`, and often `reject` for PRL/Nature-style venues.
- unsupported physical connections or inflated significance claims are publication-relevant blockers, not stylistic issues.

### By Autonomy Mode

| Behavior | Supervised | Balanced | YOLO |
|---|---|---|---|
| **Report delivery** | Full report with line-by-line comments. Present to the user for discussion before any action. | Summary report with prioritized issues. AI can draft follow-up fixes immediately, but the user still sees the report before claim-level changes land. | Report triggers an automatic revision cycle. User sees the final product unless a hard stop fires. |
| **Revision authority** | Referee identifies issues; user decides which to address. | Referee identifies issues; AI addresses technical and presentation fixes automatically, but pauses on claim narrowing, scope shifts, or new calculations that change the paper's story. | Referee + AI iterate until all issues are resolved or a circuit breaker triggers. |
| **Dispute resolution** | User arbitrates any disagreement between referee assessment and research results. | AI resolves routine technical disputes using verification evidence and escalates genuine physics judgment calls. | No routine escalation. AI makes the final call unless a hard contradiction or safety gate appears. |

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

| Behavior | Supervised | Balanced | YOLO |
|---|---|---|---|
| **Section drafting** | Draft one section at a time. Present each section for review before moving on. | Draft a full manuscript pass, self-review it, and present a polished draft. Pause only if the narrative or claims need user judgment. | Complete the paper end-to-end and present it only when it is ready for submission review. |
| **Notation decisions** | Ask the user for notation preferences before writing. | Use project conventions and resolve routine ambiguities by internal consistency or the dominant reference. Pause only when a notation choice changes interpretation. | Make all notation choices without pausing. |
| **Abstract writing** | Draft the abstract and present it for user editing. | Draft the abstract and suggest a few emphasis variants when the framing is ambiguous. | Write and finalize the abstract automatically. |

---

## Mode Interaction Matrix

When autonomy and research modes combine, the publication pipeline exhibits emergent behavior:

| Combination | Pipeline Behavior |
|---|---|
| **Supervised + Explore** | Maximum user involvement in a discovery-oriented project. User guides literature search, approves every citation, and discusses referee feedback interactively. Best for: student mentoring, unfamiliar territory. |
| **Supervised + Exploit** | User closely controls a focused calculation. Every important result is checked by the user before paper writing proceeds. Best for: high-stakes publications, experiment-theory comparisons. |
| **Balanced + Balanced** | **DEFAULT.** Standard research workflow. AI handles routine tasks, drafts the paper, and pauses only on major physics or claim decisions. Best for: most research projects. |
| **Balanced + Explore** | AI-assisted exploration with user oversight on direction changes and novelty claims. Good for: new research directions, literature surveys, methodology comparisons. |
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
| Hallucinated citation detected (title/authors don't match any database) | Hard stop in supervised. Auto-remove with warning in balanced/yolo. | All modes (severity varies) |
| Referee report: "reject" recommendation | Hard stop in all modes. Major issues must be addressed before proceeding. | All modes |
| 3 consecutive verification failures on same result | Hard stop. Systematic problem requiring human judgment. | All modes |
| Cost budget exceeded (>2x estimated) | Pause and notify in supervised/balanced. Continue with warning in yolo. | All modes |

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
3. Propose the transition to the user in supervised mode, apply it automatically in yolo mode, and in balanced mode apply it automatically only when it is a routine optimization rather than a scope change
4. Update config via `gpd config set research_mode exploit`

---

## See Also

- `references/planning/planning-config.md` — Full config schema
- `references/orchestration/model-profiles.md` — Model profile system (orthogonal to modes)
- `references/orchestration/checkpoints.md` — Checkpoint types and frequencies
- `references/orchestration/agent-infrastructure.md` — Agent spawning and context allocation
