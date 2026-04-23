---
name: gpd:discuss-phase
description: Gather phase context through adaptive questioning before planning
argument-hint: "<phase> [--auto|--compact]"
context_mode: project-required
allowed-tools:
  - file_read
  - file_write
  - shell
  - find_files
  - search_files
  - ask_user
---


<objective>
Extract research decisions that downstream agents need -- researcher and planner will use CONTEXT.md to know what to investigate, which anchors and prior outputs must stay visible, and what choices are locked.

**How it works:**

1. Analyze the phase to identify gray areas (physics assumptions, method choices, scope boundaries, etc.)
2. Present gray areas -- user selects which to discuss
3. Deep-dive each selected area until satisfied
4. Create CONTEXT.md with decisions, carry-forward inputs, and skeptical review items that guide research and planning

**`--auto` mode:** Compress the discussion to 2-3 critical gray areas, 1 question each, then auto-proceed to planning. For researchers who want fast iteration with sensible defaults.

**`--compact` mode:** Present a single-screen form instead of the Socratic multi-round dialogue. The form shows:

1. The phase goal as read from the ROADMAP.
2. The 4-6 controllable policy knobs (see workflow spec) with current defaults pre-filled.
3. A free-text "intent" field for anything not captured by the knobs.

Then render a one-screen summary of the resulting `{phase}-CONTEXT.md` and ask for a single confirm. Use `--compact` when you already know what you want and don't need the agent to lead you through gray-area discovery. `--auto` stays hands-off; `--compact` is hands-on but single-turn.

**Output:** `{phase}-CONTEXT.md` -- decisions clear enough that downstream agents can act without asking the user again
</objective>

<execution_context>
@{GPD_INSTALL_DIR}/workflows/discuss-phase.md
@{GPD_INSTALL_DIR}/templates/context.md
</execution_context>

<context>
Phase number: $ARGUMENTS (required)

**Load project state:**
@GPD/STATE.md

**Load roadmap:**
@GPD/ROADMAP.md
</context>

<process>
1. Validate phase number and detect `--auto` / `--compact` flag (error if phase missing or not in roadmap; flags are mutually exclusive)
2. Check if CONTEXT.md exists (offer update/view/skip if yes; in `--auto` mode: reuse existing, skip to planning; in `--compact` mode: pre-fill the form from the existing CONTEXT.md)
3. **Analyze phase** -- Identify domain and generate phase-specific gray areas (skipped in `--compact` mode)
4. **Present gray areas** -- Multi-select: which to discuss? (NO skip option; `--auto`: auto-select top 2-3; `--compact`: skipped entirely in favor of the knobs form)
5. **Deep-dive each area** -- 4 questions per area, then offer more/next (`--auto`: 1 question per area; `--compact`: skipped)
6. **Compact form** (only in `--compact` mode): present phase goal + knobs + intent field; accept one batched answer
7. **Write CONTEXT.md** -- Sections match areas discussed (in `--compact` mode: sections reflect the knob values plus intent)
8. Offer next steps (`--auto` / `--compact`: auto-suggest `gpd:plan-phase` and proceed if user confirms)

**CRITICAL: Scope guardrail**

- Phase boundary from ROADMAP.md is FIXED
- Discussion clarifies HOW to approach the physics, not WHETHER to expand the scope
- If user suggests new calculations or investigations beyond the phase: "That belongs in its own phase. I'll note it for later."
- Capture deferred ideas -- don't lose them, don't act on them

**Domain-aware gray areas:**
Gray areas depend on what physics is being done. Analyze the phase goal:

- Something being DERIVED -> formalism choice, gauge/frame, conventions, regularization scheme
- Something being COMPUTED -> algorithm, discretization, convergence criteria, error tolerance
- Something being SIMULATED -> initial conditions, boundary conditions, ensemble size, equilibration
- Something being ANALYZED -> statistical methods, fitting procedures, error propagation, systematics
- Something being WRITTEN -> narrative structure, level of detail, target audience, notation conventions
- Something being COMPARED -> which benchmarks, what metrics, how to quantify agreement

Generate 3-4 **phase-specific** gray areas, not generic categories.

**Probing depth:**

- Ask 4 questions per area before checking
- "More questions about [area], or move to next?"
- If more -> ask 4 more, check again
- After all areas -> "Ready to create context?"

**Do NOT ask about (the agent handles these):**

- Code implementation details
- File organization
- LaTeX formatting specifics
- Performance optimization
- Scope expansion
  </process>

<success_criteria>

- Gray areas identified through intelligent analysis of the physics
- User chose which areas to discuss
- Each selected area explored until satisfied
- Scope creep redirected to deferred ideas
- CONTEXT.md captures decisions, not vague aspirations
- User knows next steps
  </success_criteria>
