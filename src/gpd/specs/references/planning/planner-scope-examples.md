## Scope Estimation: Depth Calibration and Profile Adjustments

### Dynamic Difficulty Escalation

When prior phase history is available, apply these automatic depth escalation rules:

| Condition                                                       | Escalation Suggestion                                                                           | Reasoning                                                                                                               |
| --------------------------------------------------------------- | ----------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- |
| Previous phase required gap closure (gap_closure plans exist)   | Suggest upgrading depth: quick -> standard, or standard -> comprehensive                        | Gap closure indicates the original depth underestimated complexity; the next phase likely needs more thorough treatment |
| Previous phase consumed >60% context on any single plan         | Suggest splitting equivalent tasks in this phase into smaller plans                             | Context pressure signals tasks were too large; splitting preserves rigor in the quality-critical 0-50% context range    |
| ERROR-PATTERNS.md has >3 entries for the current physics domain | Increase verification tasks: add 1 extra verification task per plan beyond the standard minimum | Repeated errors in a domain indicate systematic difficulty; more verification catches issues earlier                    |

**Escalation protocol:**

1. Evaluate all three conditions against project history (from `read_project_history` and `consult_learned_patterns` steps)
2. If any condition triggers, prepare an escalation suggestion with:
   - Which condition(s) triggered
   - The specific evidence (e.g., "Phase 03 Plan 02 consumed 68% context", "4 sign error entries for QFT domain")
   - The recommended depth change
   - Impact on plan count and task distribution
3. **Present the escalation suggestion to the orchestrator with reasoning -- do NOT auto-apply**
4. If the orchestrator approves, apply the escalation; if rejected, proceed with the original depth

**Example escalation message:**

```markdown
### Depth Escalation Suggested

**Triggers:**

- Phase 03 required gap closure (03-04-PLAN.md, 03-05-PLAN.md were gap_closure plans)
- ERROR-PATTERNS.md has 4 entries for "perturbative QFT" domain

**Recommendation:** Upgrade from `standard` (3-5 plans) to `comprehensive` (5-10 plans)

- Split derivation tasks more aggressively (1 derivation per plan instead of 2)
- Add dedicated sign-check plan for each major calculation
- Add dedicated convergence validation plan

**Impact:** Estimated 7 plans instead of 4, +2 verification-only plans

Approve escalation? (Orchestrator decides)
```

### Profile-Aware Planning Adjustments

When the project profile is known (from PROJECT.md or orchestrator context), apply profile-specific planning adjustments to depth calibration:

| Profile       | Planning adjustment                                                                                    |
| ------------- | ------------------------------------------------------------------------------------------------------ |
| deep-theory   | Add derivation checkpoint every 2 steps (not 3-4). Require INDEPENDENTLY_CONFIRMED for all key results |
| numerical     | Add convergence testing task for every numerical computation. Require error budget task                |
| exploratory   | Compress optional detail, keep decisive anchor and acceptance-test coverage explicit, and allow somewhat larger tasks when that speeds first-result learning without hiding risk |
| review        | Add cross-reference task comparing every result to literature. Require 2+ independent checks           |
| paper-writing | Add notation consistency task per plan. Verify equations match derivation files                        |

**Profile adjustment details:**

**deep-theory:** Theoretical derivations where correctness is paramount. Every 2 derivation steps, insert a verification task that independently re-derives or cross-checks the result. All key results (equations that downstream tasks depend on) must carry an `INDEPENDENTLY_CONFIRMED` tag in their verification, meaning they were verified by a method different from the original derivation (e.g., derive via path integral AND operator formalism, or verify symbolically AND numerically).

**numerical:** Computationally intensive work where numerical accuracy is the primary concern. Every task that produces a numerical result must have a paired convergence testing sub-task (grid refinement, time step halving, or statistical bootstrap). Additionally, include one `error_budget` task per plan that tracks how numerical errors propagate through the calculation chain and verifies the final uncertainty is within acceptable bounds.

**exploratory:** Early-stage investigation where breadth matters more than exhaustive polish. Keep decisive claims, anchors, forbidden proxies, and disconfirming paths explicit, but allow lighter prose, fewer optional cross-checks, and tasks up to 90 minutes (instead of 60) to reduce plan fragmentation. Accept 3-4 tasks per plan when the plan still surfaces what would quickly falsify the current framing. The goal is rapid coverage with honest skepticism, not exhaustive proof.

**review:** Systematic validation of existing results against literature. Every plan must include a cross-reference task that compares each derived or computed result to at least one published source (with full bibliographic reference and equation numbers). Require a minimum of 2 independent verification methods for every result (e.g., analytical + numerical, or two different analytical approaches).

**paper-writing:** Publication preparation where notation consistency and presentation matter. Every plan must include a notation consistency task that checks all symbols are defined, equations in the paper text match derivation files, and figures match data. Add a task to verify references exist and are correctly cited. Prioritize readability and logical flow of argument.

**If profile is not specified:** Use standard depth calibration with no profile adjustments.
