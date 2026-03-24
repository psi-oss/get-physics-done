---
load_when:
  - "research mode"
  - "explore exploit"
  - "research strategy"
  - "adaptive research"
tier: 1
context_cost: medium
---

# Research Modes: Explore/Exploit Tunability

GPD adapts its research strategy along an explore↔exploit spectrum. The research mode controls how broadly the system searches for approaches vs how deeply it executes a known methodology.

## Mode Definitions

| Mode | Philosophy | When to Use |
|---|---|---|
| **explore** | Search the solution space. Cast a wide net. Multiple hypotheses, broad literature, diverse approaches. Prefer breadth over depth. | New problem domain, uncertain methodology, multiple viable approaches, early-stage research, literature survey |
| **balanced** (default) | Standard research flow. Plan one approach based on researcher recommendation, execute, verify, iterate if needed. | Most physics research — known domain, moderately established methodology, single focused investigation |
| **exploit** | Execute efficiently. Known methodology, tight scope, fast convergence. Minimize overhead, maximize execution speed. | Established calculation technique, reproduction of known results, parameter sweep of a validated method, writing up completed work |
| **adaptive** | Start broad enough to compare viable approaches, then narrow only after prior decisive evidence or an explicit approach lock shows the method family is stable. | Multi-phase projects where methodology should stay evidence-driven instead of phase-count-driven |

## Per-Agent Behavioral Effects

### gpd-phase-researcher

| Mode | Behavior |
|---|---|
| **explore** | Maximum breadth. Survey 5+ candidate approaches. Compare strengths, weaknesses, failure modes of each. Identify non-obvious alternatives from adjacent subfields. Include experimental/computational feasibility analysis. Output: ranked approach comparison table. Budget: 40-60k tokens. |
| **balanced** | Standard research. Survey 2-3 approaches, recommend one with justification. Include regime of validity, key assumptions, validation strategy. Budget: 25-35k tokens. |
| **exploit** | Minimal research. Confirm the chosen methodology is standard, find the key reference (textbook section or review), identify known pitfalls. No alternative survey. Budget: 10-15k tokens. |
| **adaptive** | Begin with explore-style comparison while the method family is still open. Narrow to exploit-depth only after prior decisive evidence or an explicit approach lock stabilizes the approach. |

### gpd-planner

| Mode | Behavior |
|---|---|
| **explore** | Plans include comparison tasks. Multiple derivation pathways planned in parallel (via hypothesis branches or parallel plans within a wave). Each plan variant has its own validation criteria. Include a "decision plan" that compares results and selects the best approach. 5-8 tasks per plan. |
| **balanced** | Standard planning. Single approach, 3-5 tasks per plan with verification at key steps. Follows researcher recommendation. |
| **exploit** | Minimal plans. 2-3 tasks per plan. No exploration tasks, no comparison tasks. Focus on execution efficiency. Larger tasks (up to 90 min) to reduce plan overhead. |
| **adaptive** | Keep explore-style comparison tasks until prior decisive evidence or an explicit approach lock makes one method family dominant; only then collapse to exploit-style focused plans. |

### gpd-verifier

| Mode | Behavior |
|---|---|
| **explore** | Fast, contract-aware viability testing. Focus on detecting WRONG APPROACHES early, not polishing correct ones. Key question: "Is this approach viable?" not "Is this result perfect?" Compress optional depth, but still run the contract gate and every applicable decisive-anchor, forbidden-proxy, benchmark-reproduction, direct-vs-proxy, and formulation-critical check. Flag approaches that fail basic sanity checks. |
| **balanced** | Full relevant universal verification plus every required contract-aware check. Standard confidence requirements. |
| **exploit** | Full relevant universal verification plus every required contract-aware check, with STRICTER thresholds. Require INDEPENDENTLY CONFIRMED for all key results (even in non-deep-theory profiles). Publication-grade rigor because the approach is assumed correct — errors are in execution, not methodology. |
| **adaptive** | Keep the same contract-critical floor at all times. Use explore-style skepticism until prior decisive evidence or an explicit approach lock exists, then narrow only optional breadth and apply exploit-style strictness to the locked method. |

### gpd-bibliographer

| Mode | Behavior |
|---|---|
| **explore** | Broad search. Survey 20+ references across multiple approaches. Include competing methodologies, negative results, and open debates. Build a citation network: who cites whom, which groups agree/disagree. Use INSPIRE-HEP category-aware search across adjacent categories. |
| **balanced** | Standard search. 10-15 key references for the chosen approach. Standard citation verification. |
| **exploit** | Narrow search. 5-10 references: the seminal paper, the best review, the most recent benchmark, and 2-3 methodological references. No breadth — depth on the specific technique being used. |
| **adaptive** | Keep broad search until decisive evidence or an explicit approach lock stabilizes the method family; then narrow to exploit-style maintenance search. |

### gpd-executor

| Mode | Behavior |
|---|---|
| **explore** | Multiple parallel derivation attempts when plan includes variants. Lighter self-critique (focus on feasibility, not polish). Accept "back of envelope" calculations to test approach viability. Larger deviation tolerance before escalating. Document which approaches work and which don't — failure is data. |
| **balanced** | Standard execution. Full self-critique protocol. Deviation rules apply normally. |
| **exploit** | Maximum rigor execution. Extra self-critique checkpoints (every 2 steps, not 3-4). Zero deviation tolerance — any unexpected difficulty escalates immediately. The approach is known to work; execution must be flawless. |
| **adaptive** | Execute in explore style while the approach is still being falsified. Once a decisive benchmark or anchor confirms the method family, switch to exploit-style rigor for follow-on work. |

### gpd-plan-checker

| Mode | Behavior |
|---|---|
| **explore** | Reduced to 9 core dimensions. Focuses on: research question coverage (Dim 1), computational feasibility (Dim 5), dependency correctness (Dim 9), scope sanity (Dim 10). Accepts plans with multiple parallel variants. Does NOT require literature comparison tasks. |
| **balanced** | Full 16 dimensions per profile. Standard checks. |
| **exploit** | Full 16 dimensions with EXTRA strictness on: error budgets (Dim 8), validation strategy (Dim 6), boundary conditions (Dim 14), publication readiness (Dim 12). Requires every result to have an independent verification task. |
| **adaptive** | Use explore-style tolerance for parallel variants until the approach is locked; then apply the full exploit-style dimension set to the focused plan. |

### gpd-consistency-checker

| Mode | Behavior |
|---|---|
| **explore** | Lightweight. Convention compliance + provides/requires chains only. Does not flag minor notation inconsistencies between experimental branches (they're expected to differ). Focus on detecting convention DRIFT that would make branches incomparable. |
| **balanced** | Full semantic verification. All convention checks, sign/factor spot-checks, approximation validity. |
| **exploit** | Maximum consistency. Numerical value matching across phases (not just symbolic). Verify that every computed quantity propagated between phases matches to stated precision. Flag any result used without independent verification. |
| **adaptive** | Start lightweight while branches are still being compared, then escalate to exploit-style strictness once one path becomes authoritative. |

### gpd-referee

| Mode | Behavior |
|---|---|
| **explore** | Constructive review. Focus on methodology viability, not publication polish. Key questions: "Is the approach sound?" "Are the assumptions justified?" "Would this survive a referee?" Lenient on presentation, strict on physics fundamentals. |
| **balanced** | Standard peer review. Balanced novelty/correctness/significance assessment. |
| **exploit** | Publication-grade review. Apply the standards of the target journal. Check every claim against evidence. Verify reproducibility. Evaluate whether the paper meets the acceptance criteria of PRL/PRD/JHEP/etc. |
| **adaptive** | Stay constructive while method choice is still open, then shift to exploit-style publication scrutiny after the approach is locked. |

### gpd-literature-reviewer

| Mode | Behavior |
|---|---|
| **explore** | Maximum breadth. Survey 30+ papers across multiple approaches and adjacent subfields. Build citation network with competing methodologies. Include negative results and open debates. Identify non-obvious connections to other fields. Budget: 50-70k tokens. |
| **balanced** | Standard review. 15-25 papers focused on the chosen approach. Standard citation network. Include seminal works, key reviews, and recent developments. Budget: 30-45k tokens. |
| **exploit** | Focused review. 8-12 papers: seminal paper, best review, most recent results, key methodological references. No breadth — depth on the specific technique. Budget: 15-25k tokens. |
| **adaptive** | Stay broad until the method family is locked by decisive evidence, then narrow to exploit-style review. |

### gpd-experiment-designer

| Mode | Behavior |
|---|---|
| **explore** | Exploratory design. Broader parameter ranges, coarser grids, more validation points. Include regions where multiple methods should be compared. Budget 30% for adaptive refinement. Prioritize coverage over precision. |
| **balanced** | Standard design. Physics-informed grids, standard convergence studies (3-4 values per parameter), production-grade statistical analysis plan. |
| **exploit** | Precision design. Tight parameter ranges around known interesting regions. Maximum convergence depth (5+ values per parameter). Highest statistical standards. Every simulation point serves the final result. |
| **adaptive** | Start exploratory while key regimes or observables are still uncertain, then tighten to exploit-style precision after the decisive regime is identified. |

### gpd-research-synthesizer

| Mode | Behavior |
|---|---|
| **explore** | Multi-approach synthesis. Present all viable methods with tradeoffs without picking a winner. Cross-validation matrix includes ALL pairwise comparisons. Flag complementary approaches for parallel investigation. |
| **balanced** | Standard synthesis. Recommend a single approach based on evidence weight. Present alternatives briefly. Standard cross-validation matrix. |
| **exploit** | Focused synthesis. Distill the single recommended approach with maximum implementation detail. Skip alternative comparison — extract every actionable detail for the executor. |
| **adaptive** | Stay multi-approach until decisive evidence or an explicit approach lock exists, then focus synthesis on the locked method. |

### gpd-roadmapper

| Mode | Behavior |
|---|---|
| **explore** | Branching roadmap. Plan parallel investigation of 2-3 approaches with comparison phases. Include decision phases that compare branch results. Larger total phase count (8-15). |
| **balanced** | Standard roadmap. Linear phase sequence with verification checkpoints. Single approach. 5-10 phases. |
| **exploit** | Minimal roadmap. Shortest path from problem to result. 3-6 phases. No exploratory or comparison phases. Pure execution. |
| **adaptive** | Keep branching only while approach choice remains open; collapse to a lean exploit-style roadmap once the method family is locked. |

### gpd-research-mapper

| Mode | Behavior |
|---|---|
| **explore** | Broad mapping. Include adjacent frameworks, alternative formalisms, cross-subfield connections. Equation catalog includes variants from different approaches. Flag framework choice as open question. |
| **balanced** | Standard mapping. Primary theoretical framework with key equations, conventions, and open questions. |
| **exploit** | Focused mapping. Only the specific formalism being used. Skip alternatives. Focus on computational status (implemented vs needs derivation). |
| **adaptive** | Map alternatives while framework choice remains open; narrow once decisive evidence or an explicit approach lock stabilizes the formalism. |

## Transition Detection (Adaptive Mode)

Adaptive mode narrows from explore-style to exploit-style only when project evidence supports it:

### Transition Criteria (ALL must be met)

1. **Approach locked by evidence**: Prior decisive comparisons, anchor checks, or benchmark results make the current method family trustworthy for follow-on work
2. **Methodology locked**: The planner/researcher outputs no longer show live competing method families for the same claim
3. **Conventions established enough to compare work**: Core conventions are locked and there are no unresolved convention conflicts that would blur comparison results
4. **No fundamental objections remain active**: Anchor failures, blocker-level methodology questions, or cross-phase contradictions are not still open

### Transition Signals (Indicators, not hard requirements)

- Researcher output shifts from "survey" to "focused" language
- Planner stops producing comparison plans
- Hypothesis branches are merged, abandoned, or downgraded to minor alternatives
- Literature search narrows to maintenance references for the chosen technique

### Transition Mechanism

When the orchestrator detects transition criteria are met:

1. Log the transition: `gpd state add-decision --phase N --summary "Adaptive mode narrowed toward exploit behavior" --rationale "Approach lock established in phase N: [approach description]"`
2. Keep `research_mode` set to `adaptive`; adaptive is the persisted policy, while the current narrow/broad posture is inferred from project evidence rather than stored as a second config flag
3. Announce to user: "Adaptive mode is narrowing around the validated [approach] methodology while keeping contract-critical checks active."

The user can override at any time: `/gpd:settings` or `gpd config set research_mode explore`

## Interaction with Model Profiles

Research mode and model profile are ORTHOGONAL:

| | explore | balanced | exploit |
|---|---|---|---|
| **deep-theory** | Explore multiple derivation pathways, full rigor on each | Standard deep-theory | Execute ONE derivation with absolute rigor |
| **numerical** | Try multiple numerical methods, compare convergence | Standard numerical | Run ONE validated numerical method at maximum resolution |
| **exploratory** | Maximum breadth, minimum depth per approach | Standard exploratory | Quick execution of known method |
| **review** | Survey multiple analyses of the same problem | Standard review | Focused reproduction of specific results |
| **paper-writing** | Draft multiple paper structures, compare | Standard writing | Execute ONE paper structure efficiently |

## Config Schema

`research_mode` is the only persisted adaptive-mode knob in `GPD/config.json`. There is no separate `adaptive_transition` block; transition readiness is inferred from project state, anchors, and verification outcomes.

## Command Interface

```bash
# Set research mode
gpd config set research_mode explore
gpd config set research_mode balanced
gpd config set research_mode exploit
gpd config set research_mode adaptive

# Check current mode
gpd --raw config get research_mode

# In adaptive mode, inspect current project state and prior decisive evidence
gpd state snapshot
```

## See Also

- `../planning/planning-config.md` — Full config schema documentation
- `references/orchestration/model-profiles.md` — Profile definitions (orthogonal to research mode)
- `../../workflows/branch-hypothesis.md` — Hypothesis branching (used in explore mode)
- `../../workflows/compare-branches.md` — Branch comparison (used in explore mode)
- `references/orchestration/agent-infrastructure.md` — Context pressure management (affected by research mode)
