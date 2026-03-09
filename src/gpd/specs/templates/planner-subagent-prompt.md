---
template_version: 1
---

# Planner Subagent Prompt Template

Template for spawning gpd-planner agent. The agent contains all physics planning expertise - this template provides planning context only.

---

## Template

```markdown
<planning_context>

**Phase:** {phase_number}
**Mode:** {standard | gap_closure}

**Project State:**
@.planning/STATE.md

**Research Plan:**
@.planning/ROADMAP.md

**Requirements (if exists):**
@.planning/REQUIREMENTS.md

**Phase Context (if exists):**
@.planning/phases/{phase_dir}/{phase}-CONTEXT.md

**Research (if exists):**
@.planning/phases/{phase_dir}/{phase}-RESEARCH.md

**Gap Closure (if --gaps mode):**
@.planning/phases/{phase_dir}/{phase}-VERIFICATION.md
@.planning/phases/{phase_dir}/{phase}-VALIDATION.md

</planning_context>

<physics_context>

**Notation conventions:**
@.planning/NOTATION_GLOSSARY.md

**Known results to build on:**
[Key equations, values, or validated results from prior phases]

**Physical constraints:**
[Symmetries, conservation laws, dimensional requirements, known limits]

**Available computational tools:**
[Simulators, symbolic algebra, numerical libraries, HPC resources]

</physics_context>

<downstream_consumer>
Output consumed by $gpd-execute-phase
Plans must be executable prompts with:

- Frontmatter (wave, depends_on, files_modified, autonomous)
- Tasks in XML format
- Validation criteria (limiting cases, cross-checks, dimensional analysis)
- must_haves for goal-backward verification
  </downstream_consumer>

<planning_strategy>
Physics research planning follows a specific logic:

1. **Derivation strategy:** What is the sequence of analytical steps?

   - Starting equations and assumptions
   - Key manipulations (integration by parts, Wick rotation, saddle-point, etc.)
   - Expected intermediate results at each stage
   - Final target expression

2. **Computational approach:** What needs to be computed numerically?

   - Algorithm selection and justification
   - Convergence criteria
   - Parameter ranges and resolution
   - Estimated computational cost

3. **Validation sequence:** How do we know the result is correct?

   - Limiting cases with known analytical results
   - Independent numerical methods for cross-checking
   - Symmetry and conservation law checks
   - Comparison with literature values
   - Dimensional analysis at each intermediate step

4. **Dependency ordering:** What must come before what?
   - Analytical results needed before numerical implementation
   - Validation of approximations before building on them
   - Base cases before generalizations
     </planning_strategy>

<quality_gate>
Before returning PLANNING COMPLETE:

- [ ] PLAN.md files created in phase directory
- [ ] Each plan has valid frontmatter
- [ ] Tasks are specific and actionable (not "derive the result" but "apply Schrieffer-Wolff to block-diagonalize H")
- [ ] Dependencies correctly identified (which equations/results from prior phases are needed)
- [ ] Waves assigned for parallel execution (independent derivations can run in parallel)
- [ ] must_haves derived from phase goal (specific equations, validated numerical values, or proven relationships)
- [ ] Validation tasks included (not optional - every computation must have a cross-check)
- [ ] Approximation validity explicitly stated (when does this break down?)
- [ ] Notation consistent with project conventions
      </quality_gate>
```

---

## Placeholders

| Placeholder                 | Source                 | Example                     |
| --------------------------- | ---------------------- | --------------------------- |
| `{phase_number}`            | From roadmap/arguments | `5` or `2.1`                |
| `{phase_dir}`               | Phase directory name   | `05-transport-coefficients` |
| `{phase}`                   | Phase prefix           | `05`                        |
| `{standard \| gap_closure}` | Mode flag              | `standard`                  |

---

## Usage

**From $gpd-plan-phase (standard mode):**

```python
Task(
  prompt=filled_template,
  subagent_type="gpd-planner",
  description="Plan Phase {phase}"
  # model parameter from profile tier — omit on single-model platforms
)
```

**From $gpd-plan-phase --gaps (gap closure mode):**

```python
Task(
  prompt=filled_template,  # with mode: gap_closure
  subagent_type="gpd-planner",
  description="Plan gaps for Phase {phase}"
  # model parameter from profile tier — omit on single-model platforms
)
```

## <!-- Task() subagent_type and model parameters are runtime-specific. The installer adapts these to the target platform's delegation mechanism. -->

## Continuation

For checkpoints, spawn fresh agent with:

```markdown
<objective>
Continue planning for Phase {phase_number}: {phase_name}
</objective>

<prior_state>
Phase directory: @.planning/phases/{phase_dir}/
Existing plans: @.planning/phases/{phase_dir}/\*-PLAN.md
</prior_state>

<checkpoint_response>
**Type:** {checkpoint_type}
**Response:** {user_response}
</checkpoint_response>

<physics_context>
Notation: @.planning/NOTATION_GLOSSARY.md
Available results: [summary of validated results from prior phases]
</physics_context>

<mode>
Continue: {standard | gap_closure}
</mode>
```

---

<failure_protocol>

## When Planning Stalls

If you cannot produce a valid plan after 2 attempts, report structured failure:

```markdown
**Status:** Cannot proceed
**Reason:** [Specific reason — e.g., "phase goal requires lattice QCD but no HPC access specified", "conflicting requirements between REQ-03 and REQ-07"]
**Blocked by:** [What would unblock — e.g., "user decision on approximation scheme", "RESEARCH.md for this phase not yet available"]
**Suggested alternative:** [Scope reduction or different approach — e.g., "split phase into two: analytical first, numerical second"]
**Partial progress:** [Tasks identified, dependencies mapped, partial plan structure]
```

1. **Document the obstacle** — what prevents plan creation (missing context, conflicting requirements, unclear scope)
2. **State what you have** — partial plan structure, tasks identified so far, dependencies mapped
3. **Identify the gap** — what specific information or decision is needed to unblock
4. **Return PLANNING BLOCKED** with the structured failure block above

Do NOT produce a low-quality plan to avoid blocking. A clear "I need X to proceed" is more valuable than a vague plan.

</failure_protocol>

**Note:** Planning methodology, derivation strategy, validation sequencing, computational approach selection, dependency analysis, wave assignment, and goal-backward derivation are baked into the gpd-planner agent. This template only passes context.
