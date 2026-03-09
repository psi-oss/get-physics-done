---
name: gpd-map-theory
description: Map existing research project — theoretical framework, computations, conventions, and open questions
argument-hint: "[optional: specific area to map, e.g., 'hamiltonian' or 'numerics' or 'perturbation-theory']"
allowed-tools:
  - read_file
  - shell
  - glob
  - grep
  - write_file
---

<!-- Tool names in allowed-tools use canonical GPD names. Adapters translate per runtime. -->
<!-- @ includes are expanded at install time for non-Claude runtimes. -->

<objective>
Map an existing physics research project using parallel gpd-theory-mapper agents.

Each mapper agent explores a focus area and **writes documents directly** to `.planning/research-map/`. The orchestrator only receives confirmations, keeping context usage minimal.

Maps the **theoretical architecture** of the research: formalism, computational implementations, conventions, validation status, and open questions.

Output: .planning/research-map/ folder with 7 structured documents about the research project state.
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/map-theory.md
</execution_context>

<context>
Focus area: $ARGUMENTS (optional - if provided, tells agents to focus on specific subsystem, theory sector, or computational domain)

**Load project state if exists:**
Check for .planning/STATE.md - loads context if project already initialized

**This command can run:**

- Before $gpd-new-project (existing research with prior work) - creates research map first
- After $gpd-new-project (fresh research direction) - updates research map as work evolves
- Anytime to refresh understanding of the research landscape
  </context>

<when_to_use>
**Use map-theory for:**

- Existing research projects before initialization (understand prior derivations, computations, and data)
- Refreshing the research map after significant theoretical or computational progress
- Onboarding to an unfamiliar research project or collaboration
- Before major theoretical pivots (understand current state of all components)
- When STATE.md references outdated research context

**Skip map-theory for:**

- Brand new research directions with no prior work (nothing to map)
- Trivial calculations (<5 files)
  </when_to_use>

<process>
1. Check if .planning/research-map/ already exists (offer to refresh or skip)
2. Create .planning/research-map/ directory structure
3. Spawn 4 parallel gpd-theory-mapper agents:
   - Agent 1: theory focus -> writes FORMALISM.md, REFERENCES.md
     - FORMALISM.md: Lagrangians/Hamiltonians, symmetries, gauge groups, field content, key equations, approximation schemes
     - REFERENCES.md: Papers cited, textbooks used, key results relied upon, open questions from literature
   - Agent 2: computation focus -> writes ARCHITECTURE.md, STRUCTURE.md
     - ARCHITECTURE.md: Computational pipeline, solver choices, algorithm design, parallelization strategy
     - STRUCTURE.md: File/directory layout, data flow, input/output formats, dependency graph
   - Agent 3: methodology focus -> writes CONVENTIONS.md, VALIDATION.md
     - CONVENTIONS.md: Notation, sign conventions, metric signature, unit system, index placement, Fourier transform conventions
     - VALIDATION.md: Known limits checked, analytic benchmarks, convergence tests, consistency checks performed
   - Agent 4: status focus -> writes CONCERNS.md
     - CONCERNS.md: Known issues, unresolved divergences, numerical instabilities, theoretical gaps, TODO items
4. Wait for agents to complete, collect confirmations (NOT document contents)
5. Verify all 7 documents exist with line counts
6. Commit research map
7. Offer next steps (typically: $gpd-new-project or $gpd-plan-phase)
</process>

<success_criteria>

- [ ] .planning/research-map/ directory created
- [ ] All 7 research map documents written by mapper agents
- [ ] Documents follow template structure
- [ ] Parallel agents completed without errors
- [ ] User knows next steps
      </success_criteria>
