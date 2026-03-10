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
| **adaptive** | Start in explore, auto-transition to exploit once a viable approach is validated. The system detects the transition point. | Multi-phase projects where the first phases explore and later phases execute the chosen approach |

## Per-Agent Behavioral Effects

### gpd-phase-researcher

| Mode | Behavior |
|---|---|
| **explore** | Maximum breadth. Survey 5+ candidate approaches. Compare strengths, weaknesses, failure modes of each. Identify non-obvious alternatives from adjacent subfields. Include experimental/computational feasibility analysis. Output: ranked approach comparison table. Budget: 40-60k tokens. |
| **balanced** | Standard research. Survey 2-3 approaches, recommend one with justification. Include regime of validity, key assumptions, validation strategy. Budget: 25-35k tokens. |
| **exploit** | Minimal research. Confirm the chosen methodology is standard, find the key reference (textbook section or review), identify known pitfalls. No alternative survey. Budget: 10-15k tokens. |
| **adaptive** | Starts as explore for first 1-2 phases, transitions to exploit for subsequent phases once approach is locked. |

### gpd-planner

| Mode | Behavior |
|---|---|
| **explore** | Plans include comparison tasks. Multiple derivation pathways planned in parallel (via hypothesis branches or parallel plans within a wave). Each plan variant has its own validation criteria. Include a "decision plan" that compares results and selects the best approach. 5-8 tasks per plan. |
| **balanced** | Standard planning. Single approach, 3-5 tasks per plan with verification at key steps. Follows researcher recommendation. |
| **exploit** | Minimal plans. 2-3 tasks per plan. No exploration tasks, no comparison tasks. Focus on execution efficiency. Larger tasks (up to 90 min) to reduce plan overhead. |
| **adaptive** | First phase uses explore planning; subsequent phases automatically use exploit planning unless verification failure triggers re-exploration. |

### gpd-verifier

| Mode | Behavior |
|---|---|
| **explore** | 7-check floor (5.1, 5.2, 5.3, 5.6, 5.7, 5.8, 5.10). Focus on detecting WRONG APPROACHES early, not polishing correct ones. Key question: "Is this approach viable?" not "Is this result perfect?" Accept approximate results if they demonstrate feasibility. Flag approaches that fail basic sanity checks. |
| **balanced** | Full 15-check verification per profile. Standard confidence requirements. |
| **exploit** | Full 15-check verification but with STRICTER thresholds. Require INDEPENDENTLY CONFIRMED for all key results (even in non-deep-theory profiles). Publication-grade rigor because the approach is assumed correct — errors are in execution, not methodology. |
| **adaptive** | Uses explore verification until approach is validated, then switches to exploit verification. Transition criterion: first phase passes verification with ≥3 INDEPENDENTLY CONFIRMED key results. |

### gpd-bibliographer

| Mode | Behavior |
|---|---|
| **explore** | Broad search. Survey 20+ references across multiple approaches. Include competing methodologies, negative results, and open debates. Build a citation network: who cites whom, which groups agree/disagree. Use INSPIRE-HEP category-aware search across adjacent categories. |
| **balanced** | Standard search. 10-15 key references for the chosen approach. Standard citation verification. |
| **exploit** | Narrow search. 5-10 references: the seminal paper, the best review, the most recent benchmark, and 2-3 methodological references. No breadth — depth on the specific technique being used. |
| **adaptive** | Broad search in first phase, narrow in subsequent phases. |

### gpd-executor

| Mode | Behavior |
|---|---|
| **explore** | Multiple parallel derivation attempts when plan includes variants. Lighter self-critique (focus on feasibility, not polish). Accept "back of envelope" calculations to test approach viability. Larger deviation tolerance before escalating. Document which approaches work and which don't — failure is data. |
| **balanced** | Standard execution. Full self-critique protocol. Deviation rules apply normally. |
| **exploit** | Maximum rigor execution. Extra self-critique checkpoints (every 2 steps, not 3-4). Zero deviation tolerance — any unexpected difficulty escalates immediately. The approach is known to work; execution must be flawless. |
| **adaptive** | Explore execution in early phases, exploit execution in later phases. |

### gpd-plan-checker

| Mode | Behavior |
|---|---|
| **explore** | Reduced to 9 core dimensions. Focuses on: research question coverage (Dim 1), computational feasibility (Dim 5), dependency correctness (Dim 9), scope sanity (Dim 10). Accepts plans with multiple parallel variants. Does NOT require literature comparison tasks. |
| **balanced** | Full 16 dimensions per profile. Standard checks. |
| **exploit** | Full 16 dimensions with EXTRA strictness on: error budgets (Dim 8), validation strategy (Dim 6), boundary conditions (Dim 14), publication readiness (Dim 12). Requires every result to have an independent verification task. |
| **adaptive** | 9 dimensions for explore phases, 16 for exploit phases. |

### gpd-consistency-checker

| Mode | Behavior |
|---|---|
| **explore** | Lightweight. Convention compliance + provides/requires chains only. Does not flag minor notation inconsistencies between experimental branches (they're expected to differ). Focus on detecting convention DRIFT that would make branches incomparable. |
| **balanced** | Full semantic verification. All convention checks, sign/factor spot-checks, approximation validity. |
| **exploit** | Maximum consistency. Numerical value matching across phases (not just symbolic). Verify that every computed quantity propagated between phases matches to stated precision. Flag any result used without independent verification. |
| **adaptive** | Lightweight for explore phases, maximum for exploit phases. |

### gpd-referee

| Mode | Behavior |
|---|---|
| **explore** | Constructive review. Focus on methodology viability, not publication polish. Key questions: "Is the approach sound?" "Are the assumptions justified?" "Would this survive a referee?" Lenient on presentation, strict on physics fundamentals. |
| **balanced** | Standard peer review. Balanced novelty/correctness/significance assessment. |
| **exploit** | Publication-grade review. Apply the standards of the target journal. Check every claim against evidence. Verify reproducibility. Evaluate whether the paper meets the acceptance criteria of PRL/PRD/JHEP/etc. |
| **adaptive** | Constructive in explore phases, publication-grade in exploit phases. |

### gpd-literature-reviewer

| Mode | Behavior |
|---|---|
| **explore** | Maximum breadth. Survey 30+ papers across multiple approaches and adjacent subfields. Build citation network with competing methodologies. Include negative results and open debates. Identify non-obvious connections to other fields. Budget: 50-70k tokens. |
| **balanced** | Standard review. 15-25 papers focused on the chosen approach. Standard citation network. Include seminal works, key reviews, and recent developments. Budget: 30-45k tokens. |
| **exploit** | Focused review. 8-12 papers: seminal paper, best review, most recent results, key methodological references. No breadth — depth on the specific technique. Budget: 15-25k tokens. |
| **adaptive** | Broad review in first invocation, narrow in subsequent invocations once approach is locked. |

### gpd-experiment-designer

| Mode | Behavior |
|---|---|
| **explore** | Exploratory design. Broader parameter ranges, coarser grids, more validation points. Include regions where multiple methods should be compared. Budget 30% for adaptive refinement. Prioritize coverage over precision. |
| **balanced** | Standard design. Physics-informed grids, standard convergence studies (3-4 values per parameter), production-grade statistical analysis plan. |
| **exploit** | Precision design. Tight parameter ranges around known interesting regions. Maximum convergence depth (5+ values per parameter). Highest statistical standards. Every simulation point serves the final result. |
| **adaptive** | Exploratory design for first phases, precision design once the interesting parameter regime is identified. |

### gpd-research-synthesizer

| Mode | Behavior |
|---|---|
| **explore** | Multi-approach synthesis. Present all viable methods with tradeoffs without picking a winner. Cross-validation matrix includes ALL pairwise comparisons. Flag complementary approaches for parallel investigation. |
| **balanced** | Standard synthesis. Recommend a single approach based on evidence weight. Present alternatives briefly. Standard cross-validation matrix. |
| **exploit** | Focused synthesis. Distill the single recommended approach with maximum implementation detail. Skip alternative comparison — extract every actionable detail for the executor. |
| **adaptive** | Multi-approach synthesis in explore phases, focused synthesis once approach is locked. |

### gpd-roadmapper

| Mode | Behavior |
|---|---|
| **explore** | Branching roadmap. Plan parallel investigation of 2-3 approaches with comparison phases. Include decision phases that compare branch results. Larger total phase count (8-15). |
| **balanced** | Standard roadmap. Linear phase sequence with verification checkpoints. Single approach. 5-10 phases. |
| **exploit** | Minimal roadmap. Shortest path from problem to result. 3-6 phases. No exploratory or comparison phases. Pure execution. |
| **adaptive** | Branching roadmap for first milestone (explore), linear for subsequent milestones (exploit). |

### gpd-theory-mapper

| Mode | Behavior |
|---|---|
| **explore** | Broad mapping. Include adjacent frameworks, alternative formalisms, cross-subfield connections. Equation catalog includes variants from different approaches. Flag framework choice as open question. |
| **balanced** | Standard mapping. Primary theoretical framework with key equations, conventions, and open questions. |
| **exploit** | Focused mapping. Only the specific formalism being used. Skip alternatives. Focus on computational status (implemented vs needs derivation). |
| **adaptive** | Broad mapping initially, focused in subsequent invocations. |

## Transition Detection (Adaptive Mode)

The adaptive mode automatically transitions from explore to exploit based on these signals:

### Transition Criteria (ALL must be met)

1. **Approach validated**: At least one phase has passed verification with ≥3 key results at INDEPENDENTLY CONFIRMED confidence
2. **Methodology locked**: The researcher and planner agree on a single approach (no active hypothesis branches with competing methods)
3. **Conventions established**: Convention lock has ≥5 conventions set (metric, Fourier, units, coupling, renormalization at minimum)
4. **No open methodology questions**: All blocker-type open questions resolved (minor questions OK)

### Transition Signals (Indicators, not hard requirements)

- Researcher output shifts from "survey" to "focused" language
- Planner creates sequential (not branching) plans
- Hypothesis branches are merged or abandoned
- Literature search narrows to specific technique references

### Transition Mechanism

When the orchestrator detects transition criteria are met:

1. Log the transition: `gpd state add-decision --phase N --summary "Research mode transition: explore → exploit" --rationale "Approach validated in phase N: [approach description]"`
2. Update config: `gpd config-set research_mode exploit`
3. Announce to user: "Research mode transitioning to exploit. The [approach] methodology validated in Phase N will be executed with maximum rigor for remaining phases."

The user can override at any time: `/gpd:settings` or `gpd config-set research_mode explore`

## Interaction with Model Profiles

Research mode and model profile are ORTHOGONAL:

| | explore | balanced | exploit |
|---|---|---|---|
| **deep-theory** | Explore multiple derivation pathways, full rigor on each | Standard deep-theory | Execute ONE derivation with absolute rigor |
| **numerical** | Try multiple numerical methods, compare convergence | Standard numerical | Run ONE validated numerical method at maximum resolution |
| **exploratory** | Maximum breadth, minimum depth per approach | Standard exploratory | Quick execution of known method |
| **review** | Survey multiple analyses of the same problem | Standard review | Focused reproduction of specific results |
| **paper-writing** | Draft multiple paper structures, compare | Standard writing | Execute ONE paper structure efficiently |

## Config Schema Addition

```json
{
  "research_mode": "balanced",
  "adaptive_transition": {
    "auto_detect": true,
    "min_confirmed_results": 3,
    "min_conventions_locked": 5
  }
}
```

## Command Interface

```bash
# Set research mode
gpd config-set research_mode explore
gpd config-set research_mode balanced
gpd config-set research_mode exploit
gpd config-set research_mode adaptive

# Check current mode
gpd config-get research_mode --raw

# In adaptive mode, check transition status
gpd state-snapshot  # includes research_mode and transition readiness
```

## See Also

- `../planning/planning-config.md` — Full config schema documentation
- `references/orchestration/model-profiles.md` — Profile definitions (orthogonal to research mode)
- `../../workflows/branch-hypothesis.md` — Hypothesis branching (used in explore mode)
- `../../workflows/compare-branches.md` — Branch comparison (used in explore mode)
- `references/orchestration/agent-infrastructure.md` — Context pressure management (affected by research mode)
