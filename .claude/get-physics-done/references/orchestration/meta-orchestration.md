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
- `references/orchestration/agent-delegation.md` — Task() call pattern, runtime alternatives
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
  IF exploit: bibliographer only (phase-researcher optional)
  POST:    consistency-checker (convention import from literature)

formulation:
  ALWAYS:  phase-researcher → planner → plan-checker → executor
  IF explore: + theory-mapper (map alternative formulations)
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
  ALWAYS:  verifier (full 15-check), consistency-checker
  IF explore: + phase-researcher (find additional cross-checks)
  IF exploit: verifier only (publication-grade rigor)

writing:
  ALWAYS:  paper-writer, bibliographer, notation-coordinator
  OPTIONAL: referee (pre-submission review)
  POST:    consistency-checker (notation consistency)
```

### Mode-Adjusted Agent Selection

| Setting | Effect on Agent Selection |
|---|---|
| `research_mode: explore` | Add phase-researcher and theory-mapper to formulation phases. Bibliographer uses broad search (20+ refs). Planner creates parallel plans. Verifier uses 7-check floor (feasibility, not perfection). |
| `research_mode: exploit` | Skip phase-researcher for well-known methods. Bibliographer uses narrow search (5-10 refs). Planner creates single focused plan. Verifier uses full 15-check with strict thresholds. |
| `research_mode: adaptive` | Start with explore selection for phases 1-3, auto-switch to exploit after first verification pass with >= 3 INDEPENDENTLY CONFIRMED results. |
| `autonomy: supervised` | All agents produce detailed explanations. Orchestrator pauses for user review at every phase boundary. |
| `autonomy: guided` | Standard depth. Orchestrator pauses at major decision points (approach selection, method choice). |
| `autonomy: autonomous` | Agents self-validate more thoroughly. No pauses between phases. Explicit assumption documentation at each step. |
| `autonomy: yolo` | Maximum speed. Skip optional agents (theory-mapper, experiment-designer). Reduce verification to 7-check floor. Still maintain physics correctness. |

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

3. **Verification exceeds 50% verifier budget:** Reduce to the 7-check floor. Flag skipped checks in VERIFICATION.md for follow-up in a separate verifier invocation.

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

For `research_mode: adaptive`, the orchestrator needs to detect when to switch from explore to exploit.

### Transition Criteria

The explore-to-exploit transition fires when ALL of the following are met:

1. **Approach validated:** At least one derivation or numerical phase has passed verification with >= 3 INDEPENDENTLY CONFIRMED key results
2. **Conventions locked:** The convention_lock in state.json has >= 5 entries and no unresolved convention conflicts
3. **No fundamental objections:** The consistency-checker has not flagged any cross-phase inconsistencies in the last 2 phases
4. **Method converging:** For numerical work, the target observable shows monotonic improvement with resolution/iteration. For analytical work, the perturbation series shows decreasing corrections

### Transition Mechanics

```
After each phase completion:
  1. CHECK transition criteria
  2. IF all met:
     - Set internal flag: explore_phase_complete = true
     - Log transition: "Adaptive mode: switching from explore to exploit at phase N"
     - From next phase onward:
       - Planner uses exploit-mode planning (single focused plan)
       - Researcher uses exploit-mode search (narrow)
       - Verifier uses exploit-mode thresholds (strict)
  3. IF criteria not met but phase > 4:
     - Consider partial transition: lock the approach but keep explore-level verification
     - Log: "Adaptive mode: partial transition — approach locked but verification remains exploratory"
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
| Verifier returns incomplete (< 7 checks) | Re-invoke with remaining checks. Budget a fresh context. |
| Researcher returns "insufficient literature" | Try: (a) broader search terms, (b) adjacent subfield, (c) WebSearch with different query. |
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
