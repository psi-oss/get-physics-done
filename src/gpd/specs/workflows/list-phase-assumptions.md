<purpose>
Surface the AI's assumptions about a phase before planning, enabling users to correct misconceptions early. Covers physical, mathematical, computational, anchor, and skeptical assumptions with justification requirements.

Key difference from discuss-phase: This is ANALYSIS of what the AI thinks, not INTAKE of what user knows. No file output - purely conversational to prompt discussion.
</purpose>

<process>

<step name="validate_phase" priority="first">
Phase number: $ARGUMENTS (required)

**If argument missing:**

```
Error: Phase number required.

Usage: /gpd:list-phase-assumptions [phase-number]
Example: /gpd:list-phase-assumptions 3
```

Exit workflow.

**If argument provided:**
Validate phase exists in roadmap:

```bash
cat .gpd/ROADMAP.md | grep -i "Phase ${PHASE}"
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
Based on roadmap description and project context, identify assumptions across eight areas:

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

**6. Anchor Inputs:**
What trusted references, prior outputs, baselines, or benchmarks does the AI assume constrain the phase?

- "I assume [paper/result/baseline] is the anchor because..."
- "I assume [prior internal output] must be carried forward because..."
- "Anchor uncertainty: [what reference or baseline is weakest or least explicit]..."

**7. Expected Results:**
What does the assistant expect the answer to look like?

- "I expect [quantity] to scale as [expression] because..."
- "In the [limit], this should reduce to [known result]..."
- "Order of magnitude estimate: [value] based on [reasoning]..."
- "The result should satisfy [constraint/sum rule/Ward identity]..."

**8. Dependencies and Prerequisites:**
What does the assistant assume exists or needs to be in place?

- "This assumes [result/data] from previous phases"
- "External dependencies: [packages, data sets, known results]"
- "This will feed into [downstream phases]"
- "Required input: [specific quantities with expected formats]"

**9. User Guidance I Am Treating As Binding:**
What explicit user requests does the assistant think must survive into planning and execution?

- "I think the user cares most about [observable / figure / artifact] because..."
- "I think [reference / prior output / baseline] must stay visible because..."
- "I think we should stop or re-scope if [condition] because..."
- "I may be over-generalizing [user request] into [weaker proxy]..."

Also name:

- the **weakest anchor or assumption**
- the **earliest disconfirming check**
- the **kind of false progress** that would look encouraging but should not count as success

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

### Anchor Inputs
[List assumed references, baselines, prior outputs, and benchmark anchors]
For each: state why it matters and how confident you are that it should constrain the phase

### Expected Results
**Scaling:** [expected functional forms]
**Limiting cases:** [what known results must be recovered]
**Order of magnitude:** [rough estimates with reasoning]
**Consistency checks:** [sum rules, Ward identities, conservation laws to verify]

### Skeptical Review
**Weakest anchor / assumption:** [what feels least grounded]
**Fast falsifier:** [what would most quickly prove the framing wrong]
**False progress:** [what might look promising but would not count as success]

### Dependencies
**From prior phases:** [what's needed]
**External:** [packages, data, known results]
**Feeds into:** [what future phases need from this]

### User Guidance I Am Treating As Binding
[List the observables, deliverables, prior outputs, required references, and stop conditions I believe the user explicitly cares about]
For each: state why I think it is binding and where I might be paraphrasing too loosely

---

**What do you think?**

Probe these assumptions critically:
- Which physical assumptions are you least confident about?
- Are the approximation regimes appropriate for your parameter values?
- Do the expected results match your intuition?
- Am I missing any important limiting cases?
- Which anchor or prior output feels weakest?
- What should we check early so a wrong framing does not survive too long?
- What result would look like progress here but should not count as success?
- Which of your explicit requests am I at risk of generalizing away or weakening?
- Did I miss any required reference, prior output, decisive observable, or stop condition?
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
1. Discuss methodology (/gpd:discuss-phase ${PHASE}) - Socratic dialogue to make methodological decisions
2. Plan this phase (/gpd:plan-phase ${PHASE}) - Create detailed research execution plans
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
- Assumptions surfaced across nine areas: physical, mathematical framework, approximation scheme, computational approach, scope, anchor inputs, expected results, dependencies, user-binding guidance
- Each assumption includes justification and consequences if wrong
- Confidence levels marked where appropriate
- Limiting cases and consistency checks identified
- "What do you think?" prompt with specific probing questions presented
- User feedback acknowledged with impact analysis
- Clear next steps offered
  </success_criteria>
