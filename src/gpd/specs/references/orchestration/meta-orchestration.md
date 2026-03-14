---
load_when:
  - "orchestration"
  - "agent selection"
  - "which agent to use"
  - "context budget"
  - "feedback loop"
  - "verification failure routing"
  - "meta-orchestration"
tier: 2
context_cost: medium
---

# Meta-Orchestration Intelligence

How GPD selects agents, allocates context budgets, and routes verification failures. This document covers orchestration STRATEGY, not mechanics (for mechanics, see `references/orchestration/agent-delegation.md` and `references/orchestration/agent-infrastructure.md`).

**Related files:**
- `references/orchestration/agent-delegation.md` — task() call pattern, runtime alternatives
- `references/orchestration/agent-infrastructure.md` — data boundary, tool failure, context pressure
- `references/orchestration/context-budget.md` — per-workflow budget targets
- `references/orchestration/context-pressure-thresholds.md` — GREEN/YELLOW/ORANGE/RED thresholds
- `../research/research-modes.md` — explore/balanced/exploit/adaptive behavioral effects

---

## 1. Agent Selection Matrix

Which agents to invoke for each phase type. The orchestrator (execute-phase workflow) selects agents based on the phase's primary activity and the current `research_mode` and `autonomy` settings.

### Phase Type Classification

| Phase Type | Primary Activity | Example Phases |
|---|---|---|
| **literature** | Survey prior work, identify approaches | "Literature and Setup", "Problem Setup" |
| **formulation** | Define equations, write Lagrangians, set up models | "Governing Equations", "Model Construction", "Lagrangian and Feynman Rules" |
| **derivation** | Analytical calculation, proofs, symbolic work | "Loop Integrals", "Stability Analysis", "Solution Construction" |
| **numerical** | Simulation, numerical computation, data analysis | "Numerical Simulation", "Circuit and Simulation" |
| **validation** | Check results, compare with known cases | "Limiting Cases and Validation", "Comparison with Experiment" |
| **writing** | Draft manuscript sections | "Paper Writing" |

### Agent Selection by Phase Type

```
Phase Type → Agent Selection (in order of invocation)
─────────────────────────────────────────────────────

literature:
  ALWAYS:  phase-researcher, bibliographer
  IF explore: + project-researcher (broader context)
  IF exploit: bibliographer only when current contract, anchors, and prior research already cover the method family
  POST:    consistency-checker (convention import from literature)

formulation:
  ALWAYS:  phase-researcher → planner → plan-checker → executor
  IF explore: + research-mapper (map alternative formulations)
  POST:    verifier (dimensional + limiting cases), consistency-checker

derivation:
  ALWAYS:  planner → plan-checker → executor → verifier
  IF explore: planner generates parallel derivation plans
  IF exploit: planner generates single focused plan
  POST:    consistency-checker (cross-phase sign/factor check)

numerical:
  ALWAYS:  planner → plan-checker → executor → verifier
  EXTRAS:  debugger (if convergence fails), experiment-designer (parameter sweep design)
  POST:    verifier (convergence + statistics checks), consistency-checker

validation:
  ALWAYS:  verifier (full contract-aware checklist), consistency-checker
  IF explore: + phase-researcher (find additional cross-checks)
  IF exploit: verifier only after the decisive comparison path is already well established

writing:
  ALWAYS:  paper-writer, bibliographer, notation-coordinator
  OPTIONAL: referee (pre-submission review)
  POST:    consistency-checker (notation consistency)
```

### Mode-Adjusted Agent Selection

| Setting | Effect on Agent Selection |
|---|---|
| `research_mode: explore` | Add phase-researcher and research-mapper to formulation phases. Bibliographer uses broad search (20+ refs). Planner creates parallel plans. Verification can stage breadth over multiple passes, but contract-critical checks stay mandatory. |
| `research_mode: exploit` | Skip phase-researcher only when the current contract, anchors, and prior outputs already make the method family obvious. Bibliographer uses narrow search (5-10 refs). Planner creates single focused plan. Verification stays full-strength on contract-critical checks and decisive comparisons. |
| `research_mode: adaptive` | Start broad, then narrow only after prior decisive evidence or an explicit approach lock shows the method family is stable. Do not switch purely because the phase number increased, a wave completed, or a proxy comparison passed. |
| `autonomy: babysit` | All agents produce detailed explanations. Orchestrator pauses for user review at every major phase transition, every required bounded gate, and each key decision, but not after every algebraic micro-step. |
| `autonomy: balanced` | Standard depth. Orchestrator auto-runs routine work and pauses at major decision points, ambiguities, blocker states, or whenever decisive evidence is still missing and the next work would assume it. |
| `autonomy: yolo` | Maximum speed. Skip only optional breadth agents when the contract is already well scoped. Keep the same contract-critical verification bar; autonomy changes pause cadence, not decisiveness, and it never auto-continues past an uncleared first-result, skeptical, or pre-fanout gate. |

---

## 2. Context Budget Allocation by Phase Type

Different phase types have different context consumption patterns. The orchestrator should monitor these and segment work accordingly.

### Budget Targets by Phase Type

| Phase Type | Orchestrator Budget | Agent Budget (each) | Total per Phase | Notes |
|---|---|---|---|---|
| **literature** | 15% | researcher: 40%, bibliographer: 30% | ~85% max | Heavy file reads. Segment if > 10 papers. |
| **formulation** | 20% | researcher: 25%, planner: 15%, executor: 30% | ~90% max | Moderate. Usually fits in one pass. |
| **derivation** | 15% | planner: 10%, executor: 50%, verifier: 20% | ~95% max | Executor is context-heavy. Segment derivation into sub-steps if > 5 intermediate results. |
| **numerical** | 10% | planner: 10%, executor: 40%, debugger: 20%, verifier: 15% | ~95% max | Executor consumes less context than derivation (code is compact). Budget debugger for iteration. |
| **validation** | 10% | verifier: 50%, consistency-checker: 25% | ~85% max | Verifier does heavy cross-referencing. |
| **writing** | 10% | paper-writer: 50%, bibliographer: 15%, referee: 15% | ~90% max | Paper-writer is context-heavy (reads all prior phases). |

### Budget Adaptation Rules

1. **Derivation exceeds 50% executor budget:** Split the plan into sub-plans. The executor should write intermediate results to a file, clear context, and continue from the checkpoint.

2. **Literature exceeds 60% researcher budget:** The researcher should write a structured literature summary to a file and return. A second researcher invocation can process remaining papers.

3. **Verification exceeds 50% verifier budget:** Split verifier work into multiple passes. Keep the contract-critical, anchor, and decisive-comparison checks in the current pass and queue optional depth for follow-up.

4. **Numerical debugging exceeds 20% debugger budget:** Write a debugging report with hypotheses and return. The orchestrator should re-invoke the debugger with fresh context and the report.

---

## 3. Verification Failure Routing

When verification fails, the failure type determines which agent to re-invoke and with what modified prompt. This is the "smart feedback loop" that closes the gap between detection and correction.

### Failure Classification and Routing

| Verification Failure | Detected By | Route To | Modified Prompt |
|---|---|---|---|
| **Dimensional inconsistency** (5.1) | verifier | executor | "Re-derive equation X. The verifier found dimensional inconsistency: [details]. Track dimensions explicitly at every step." |
| **Limiting case failure** (5.3) | verifier | executor | "Result fails in the [limit] limit. Expected: [known result]. Got: [our result]. Re-derive starting from equation Y with the limit applied before other approximations." |
| **Symmetry violation** (5.5) | verifier | executor | "Result violates [symmetry]. Check: [specific violation]. Trace the symmetry through every step of the derivation to find where it is broken." |
| **Conservation law violation** (5.6) | verifier | executor | "Conservation of [quantity] is violated. Current value: [X], expected: [Y]. Check the equations of motion and verify that the symmetry generating this conservation law is preserved." |
| **Math error** (5.8) | verifier | executor | "Step N contains a mathematical error: [details]. Re-derive from step N-1 with CAS verification of each algebraic step." |
| **Convergence failure** (5.9) | verifier | debugger | "Numerical result did not converge. Current behavior: [description]. Diagnose: (a) grid resolution, (b) iteration count, (c) algorithm stability, (d) parameter regime." |
| **Literature disagreement** (5.10) | verifier | phase-researcher + executor | "Our result disagrees with [reference]: we get [X], they report [Y]. Investigate: (a) convention difference, (b) different approximation, (c) their error, (d) our error." |
| **Convention drift** | consistency-checker | notation-coordinator | "Convention drift detected between phase M and phase N: [details]. Trace the convention through all intermediate steps and identify where the change occurred." |
| **Cross-phase inconsistency** | consistency-checker | executor | "Phase N result is inconsistent with Phase M output: [details]. The Phase M output was: [value]. Re-derive Phase N result using the Phase M output explicitly." |
| **Statistical inadequacy** (5.12) | verifier | executor | "Statistical error analysis is inadequate: [details]. Re-run with: (a) longer equilibration, (b) more samples, (c) proper autocorrelation analysis, (d) block averaging." |

### Routing Protocol

```
On verification failure:
  1. CLASSIFY: Which check failed? (5.1-5.15 or consistency)
  2. EXTRACT: What specifically was wrong? (equation number, step, value, expected vs actual)
  3. DIAGNOSE: Is this a derivation error, numerical error, convention error, or conceptual error?
  4. ROUTE: Select target agent from table above
  5. CONSTRUCT: Build modified prompt with:
     - Specific failure description
     - Expected correct behavior
     - Relevant files to re-read
     - Instruction to verify the fix against the original failure
  6. INVOKE: Re-invoke the target agent with modified prompt
  7. RE-VERIFY: After fix, re-run the failed verification check (not full suite)
```

### Escalation Rules

| Condition | Action |
|---|---|
| Same check fails twice | Escalate: invoke phase-researcher to investigate alternative approaches |
| Three different checks fail | Escalate: re-run full verification. The result may have a fundamental error |
| Convention drift recurs after fix | Escalate: invoke notation-coordinator for global convention audit |
| Numerical convergence fails after debugging | Escalate: reconsider the numerical method (invoke planner for alternative approach) |
| Literature disagreement unresolved | Escalate: invoke bibliographer to find additional references; consider that both results may be correct in different regimes |

### Maximum Iteration Limits

| Failure Type | Max Re-invocations | After Max |
|---|---|---|
| Math/derivation error | 2 | Flag as UNRESOLVED, document in VERIFICATION.md, continue |
| Convergence failure | 3 | Reduce scope or change numerical method |
| Convention drift | 2 | Lock conventions globally and re-derive from scratch |
| Literature disagreement | 2 | Document as open question, present both results |

---

## 4. Adaptive Transition Detection

For `research_mode: adaptive`, the orchestrator needs to detect when to narrow from explore-style behavior toward exploit-style behavior.

The decision is evidence-driven, not phase-count-driven. Reaching a later phase, finishing one wave, or seeing one internal proxy pass is not enough on its own.

### Transition Criteria

The explore-to-exploit transition fires when ALL of the following are met:

1. **Approach locked by evidence:** At least one prior phase has recorded decisive comparison or contract-result evidence that makes the current method family trustworthy for follow-on work. Proxy-only or sanity-only passes do NOT satisfy this.
2. **Conventions locked:** The convention_lock in state.json has >= 5 entries and no unresolved convention conflicts
3. **No fundamental objections:** The consistency-checker has not flagged any cross-phase inconsistencies in the last 2 phases
4. **Method converging:** For numerical work, the target observable shows monotonic improvement with resolution/iteration. For analytical work, the planned approximation path still has a credible validation story and no unresolved anchor failures

For criterion 1, prefer explicit evidence such as:

- a decisive `comparison_verdicts` entry that passes for the method family now being reused
- a `contract_results` acceptance test or claim result that the user would recognize as decisive for this method choice
- an explicit `approach_lock` / `approach_locked` marker tied to the same evidence

### Transition Mechanics

```
After each phase completion or any explicit decisive-evidence update:
  1. CHECK transition criteria
  2. IF all met:
     - Keep `research_mode=adaptive`; record that the approach is now locked by evidence
     - Log transition: "Adaptive mode: narrowing toward exploit behavior at phase N"
     - From next phase onward:
       - Planner uses exploit-mode planning (single focused plan)
       - Researcher uses exploit-mode search (narrow)
     - Verifier keeps the same contract-critical checks and narrows only optional breadth
  3. IF criteria not met but there is partial evidence:
     - Consider partial transition: lock the approach locally but keep broader research or verifier depth wherever decisive evidence is still missing
     - Log: "Adaptive mode: partial transition — approach locked but broader skepticism remains active"
```

### Reverse Transition (Exploit to Explore)

Triggered by:
- Verification failure that cannot be resolved in 2 iterations
- Consistency-checker flags a fundamental inconsistency
- Literature review reveals the chosen approach has a known limitation in the current regime

```
On reverse transition:
  1. Log: "Adaptive mode: reverting to explore at phase N due to [reason]"
  2. Invoke phase-researcher to survey alternative approaches
  3. Invoke planner to create comparison plans
  4. Resume explore-mode operation
```

---

## 5. Agent Performance Heuristics

Guidance for the orchestrator on how to handle agent-specific patterns.

### When to Re-invoke vs Skip

| Situation | Action |
|---|---|
| Executor returns CHECKPOINT (context full) | Re-invoke with checkpoint file. This is normal for long derivations. |
| Verifier returns incomplete contract-aware coverage | Re-invoke with remaining checks. Budget a fresh context. |
| Researcher returns "insufficient literature" | Try: (a) broader search terms, (b) adjacent subfield, (c) web_search with different query. |
| Planner produces > 8 tasks in one plan | Split: plans with > 8 tasks risk executor context overflow. Split into 2 plans at a natural boundary. |
| Debugger returns "unknown failure mode" | Escalate to phase-researcher for alternative method. The current approach may be fundamentally unsuitable. |
| Bibliographer returns < 3 references | For explore mode: re-invoke with broader search. For exploit: acceptable if the references are the canonical ones. |
| Paper-writer output fails referee review | Re-invoke paper-writer with specific referee feedback. Do not re-invoke referee — that creates circular loops. |

### Agent Spawn Order Optimization

For standard derivation phases, this order minimizes wasted context:

```
1. planner         (10% context, produces PLAN.md)
2. plan-checker    (5% context, validates plan, fast)
3. executor        (50% context, does the work)
4. verifier        (20% context, validates results)
5. consistency-checker (10% context, cross-phase check)
```

If the executor must be re-invoked after verification failure, the total exceeds 100% of a single context window. This is expected — each agent runs in its own fresh context. The orchestrator's context only holds the coordination logic and summary results.
