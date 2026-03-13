---
name: gpd:list-phase-assumptions
description: Surface the AI's assumptions about a phase approach before planning
argument-hint: "[phase]"
context_mode: project-required
allowed-tools:
  - file_read
  - shell
  - search_files
  - find_files
---

<!-- Tool names and @ includes are platform-specific. The installer translates paths for your runtime. -->
<!-- Allowed-tools are runtime-specific. Other platforms may use different tool interfaces. -->

<objective>
Analyze a phase and present the AI's assumptions about the physics, methodology, computational approach, scope boundaries, anchors, risk areas, and dependencies.

Purpose: Help users see what the AI thinks BEFORE planning begins -- enabling course correction early when assumptions are wrong.
Output: Conversational output only (no file creation) -- ends with "What do you think?" prompt

**Assumption categories for physics research:**

1. **Physical assumptions** -- approximations taken for granted

   - Weak/strong coupling regime
   - Low/high energy limit
   - Thermodynamic limit or finite-size
   - Equilibrium vs non-equilibrium
   - Adiabatic or sudden approximation
   - Mean-field validity
   - Symmetry assumptions (isotropy, homogeneity, translational invariance)
   - Neglected interactions or degrees of freedom

2. **Mathematical assumptions** -- properties assumed about the formalism

   - Convergence of series expansions or perturbative corrections
   - Analyticity of relevant functions
   - Completeness of basis sets
   - Existence and uniqueness of solutions
   - Validity of saddle-point / stationary-phase approximations
   - Commutativity of limits (e.g., thermodynamic limit vs zero-temperature limit)

3. **Computational assumptions** -- believed-sufficient numerics

   - Grid resolution or mesh density sufficient
   - Time step small enough for stability and accuracy
   - Convergence criteria adequate
   - Finite-size effects under control
   - Random sampling sufficient (Monte Carlo statistics)
   - Floating-point precision adequate

4. **Methodological assumptions** -- approach and ordering

   - Which method is the right tool for the problem
   - What order to tackle sub-problems
   - What can be reused from prior phases vs computed fresh
   - What constitutes "good enough" agreement with benchmarks

5. **Scope assumptions** -- what is in and out
   - Which effects are included vs explicitly neglected
   - What parameter ranges are targeted
   - What level of rigor is expected (estimate, calculation, proof)
   - What deliverables the phase produces
6. **Anchor assumptions** -- what trusted references, baselines, prior outputs, or benchmarks the AI assumes constrain the phase
7. **Skeptical assumptions** -- what looks weakest, what could falsify the current framing early, and what might be false progress
     </objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/list-phase-assumptions.md
</execution_context>

<context>
Phase number: $ARGUMENTS (required)

**Load project state first:**
@.gpd/STATE.md

**Load roadmap:**
@.gpd/ROADMAP.md
</context>

<process>
1. Validate phase number argument (error if missing or invalid)
2. Check if phase exists in roadmap
3. Follow list-phase-assumptions.md workflow:
   - Analyze roadmap description
   - Surface assumptions about: physical model, mathematical formalism, computational approach, methodology ordering, scope boundaries, anchors, and skeptical failure modes
   - For each assumption, state WHY the AI assumes it (what in the phase description or physics domain suggests it)
   - Flag assumptions that are most likely to be wrong or most consequential if wrong
   - Present assumptions clearly, grouped by category
   - Prompt "What do you think?"
4. Gather feedback and offer next steps
</process>

<success_criteria>

- Phase validated against roadmap
- Assumptions surfaced across all five categories (physical, mathematical, computational, methodological, scope)
- Each assumption includes rationale and consequence-if-wrong
- High-risk assumptions flagged explicitly
- User prompted for feedback
- User knows next steps (discuss context, plan phase, or correct assumptions)
  </success_criteria>
