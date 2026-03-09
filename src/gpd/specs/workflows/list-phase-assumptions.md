<purpose>
Surface the AI's assumptions about a phase before planning, enabling users to correct misconceptions early. Covers physical, mathematical, and computational assumptions with justification requirements.

Key difference from discuss-phase: This is ANALYSIS of what the AI thinks, not INTAKE of what user knows. No file output - purely conversational to prompt discussion.
</purpose>

<process>

<step name="validate_phase" priority="first">
Phase number: $ARGUMENTS (required)

**If argument missing:**

```
Error: Phase number required.

Usage: $gpd-list-phase-assumptions [phase-number]
Example: $gpd-list-phase-assumptions 3
```

Exit workflow.

**If argument provided:**
Validate phase exists in roadmap:

```bash
cat .planning/ROADMAP.md | grep -i "Phase ${PHASE}"
```

**If phase not found:**

```
Error: Phase ${PHASE} not found in roadmap.

Available phases:
[list phases from roadmap]
```

Exit workflow.

**If phase found:**
Parse phase details from roadmap:

- Phase number
- Phase name
- Phase description/goal
- Any scope details mentioned

Continue to analyze_phase.
</step>

<step name="analyze_phase">
Based on roadmap description and project context, identify assumptions across seven areas:

**1. Physical Assumptions:**
What physical regime, symmetries, and conservation laws does the AI assume apply?

- "I assume the system is in the [regime] because..."
- "I assume [symmetry] is preserved because..."
- "I assume [conservation law] holds because..."
- "I assume [interaction/coupling] can be neglected because..."

**2. Mathematical Framework:**
What mathematical structures, equations, and solution methods does the AI assume?

- "I'd use [equation/formalism] because..."
- "I'd work in [representation/basis] because..."
- "I'd assume [mathematical property] (e.g., analyticity, convergence, completeness) because..."
- "I'd treat [quantity] as [small/large/perturbative] because..."

**3. Approximation Scheme:**
What approximations does the AI plan to make, and what are their regimes of validity?

- "I'd use [approximation] valid when [condition]..."
- "This breaks down when [parameter] ~ [value] because..."
- "The leading correction would be O([expression])..."
- "Alternative approaches for when this fails: [list]"

**4. Computational Approach:**
What numerical methods, algorithms, and tools does the AI assume?

- "I'd use [algorithm/package] because..."
- "I'd discretize using [method] with [resolution/basis size]..."
- "Expected computational cost: [estimate]"
- "Convergence criterion: [specification]"

**5. Scope Boundaries:**
What's included vs excluded in the assistant's interpretation?

- "This phase includes: A, B, C"
- "This phase does NOT include: D, E, F"
- "Boundary ambiguities: G could go either way"

**6. Expected Results:**
What does the assistant expect the answer to look like?

- "I expect [quantity] to scale as [expression] because..."
- "In the [limit], this should reduce to [known result]..."
- "Order of magnitude estimate: [value] based on [reasoning]..."
- "The result should satisfy [constraint/sum rule/Ward identity]..."

**7. Dependencies and Prerequisites:**
What does the assistant assume exists or needs to be in place?

- "This assumes [result/data] from previous phases"
- "External dependencies: [packages, data sets, known results]"
- "This will feed into [downstream phases]"
- "Required input: [specific quantities with expected formats]"

Be honest about uncertainty. Mark assumptions with confidence levels:

- "Fairly confident: ..." (clear from roadmap or well-established physics)
- "Assuming: ..." (reasonable inference, standard approach)
- "Unclear: ..." (could go multiple ways, depends on regime)
- "Risky assumption: ..." (commonly violated, needs explicit verification)
  </step>

<step name="present_assumptions">
Present assumptions in a clear, scannable format:

```
## My Assumptions for Phase ${PHASE}: ${PHASE_NAME}

### Physical Assumptions
[List assumptions about the physics: regime, symmetries, conservation laws, negligible interactions]
For each: state the assumption, why it seems reasonable, and what would change if it's wrong

### Mathematical Framework
[List assumptions about formalism, equations, representations, and mathematical properties]
For each: state why this framework is appropriate and what alternatives exist

### Approximation Scheme
[List planned approximations with stated regimes of validity]
For each: state the controlling parameter, when it breaks down, and the expected error

### Computational Approach
[List assumed algorithms, packages, and numerical parameters]
For each: state why this method suits the problem and what its limitations are

### Scope Boundaries
**In scope:** [what's included]
**Out of scope:** [what's excluded]
**Ambiguous:** [what could go either way]

### Expected Results
**Scaling:** [expected functional forms]
**Limiting cases:** [what known results must be recovered]
**Order of magnitude:** [rough estimates with reasoning]
**Consistency checks:** [sum rules, Ward identities, conservation laws to verify]

### Dependencies
**From prior phases:** [what's needed]
**External:** [packages, data, known results]
**Feeds into:** [what future phases need from this]

---

**What do you think?**

Probe these assumptions critically:
- Which physical assumptions are you least confident about?
- Are the approximation regimes appropriate for your parameter values?
- Do the expected results match your intuition?
- Am I missing any important limiting cases?
```

Wait for user response.
</step>

<step name="gather_feedback">
**If user provides corrections:**

Acknowledge the corrections and probe deeper:

```
Key corrections:
- [correction 1] -- this changes [what it impacts]
- [correction 2] -- this means [revised understanding]

This significantly affects the approach. In particular:
- [Assumption X] is now [revised]
- [Method Y] may need to be replaced by [alternative]
- [Expected result Z] should instead look like [revised expectation]

Does this revised understanding match your picture?
```

**If user identifies risky assumptions:**

```
You've flagged [assumption] as risky. Let me think about what happens if it fails:
- If [assumption] doesn't hold, then [consequence]
- We could hedge by [alternative approach or verification strategy]
- The plan should include a checkpoint to verify this early

Should I note this as a critical validation point?
```

**If user confirms assumptions:**

```
Assumptions validated. Key physics confirmed:
- [most important confirmed assumption]
- [second most important]
```

Continue to offer_next.
</step>

<step name="offer_next">
Present next steps:

```
What's next?
1. Discuss methodology ($gpd-discuss-phase ${PHASE}) - Socratic dialogue to make methodological decisions
2. Plan this phase ($gpd-plan-phase ${PHASE}) - Create detailed research execution plans
3. Re-examine assumptions - I'll analyze again with your corrections
4. Done for now
```

Wait for user selection.

If "Discuss methodology": Note that CONTEXT.md will incorporate any corrections discussed here
If "Plan this phase": Proceed knowing assumptions are understood
If "Re-examine": Return to analyze_phase with updated understanding
</step>

</process>

<success_criteria>

- Phase number validated against roadmap
- Assumptions surfaced across seven areas: physical, mathematical framework, approximation scheme, computational approach, scope, expected results, dependencies
- Each assumption includes justification and consequences if wrong
- Confidence levels marked where appropriate
- Limiting cases and consistency checks identified
- "What do you think?" prompt with specific probing questions presented
- User feedback acknowledged with impact analysis
- Clear next steps offered
  </success_criteria>
