---
template_version: 1
---

# Discovery Template

Template for `.gpd/phases/XX-name/DISCOVERY.md` - pre-planning discovery of physics landscape, methods, and known results.

**Purpose:** Document what was discovered about a physics problem before planning begins. Answers: what methods exist, what is known, what tools are available, what approximations are valid, and what the recommended approach is.

**Relationship to research.md:** This template produces DISCOVERY.md (pre-planning exploration). The research.md template produces RESEARCH.md (comprehensive literature survey). Discovery is lighter and more action-oriented; research is deeper and more exhaustive. For comprehensive literature surveys, use /gpd:research-phase instead.

---

## Discovery Depth Levels

| Level | Name         | Time      | Output                                   | When                                                                       |
| ----- | ------------ | --------- | ---------------------------------------- | -------------------------------------------------------------------------- |
| 1     | Quick Verify | 2-5 min   | No file (verbal confirmation to proceed) | Confirming a formula, checking a known result, verifying a convention       |
| 2     | Standard     | 15-30 min | DISCOVERY.md                             | Choosing between methods, exploring a new regime, setting up a calculation  |
| 3     | Deep Dive    | 1+ hour   | Detailed DISCOVERY.md with gates          | Novel problems, ambiguous literature, competing claims, foundational choices |

**Default to Level 2** unless the user or plan-phase specifies otherwise.

---

## File Template

````markdown
---
phase: XX-name
depth: verify|standard|deep
confidence: HIGH|MEDIUM|LOW
discovered: YYYY-MM-DD
domain: [primary physics subfield]
recommendation: "[one-liner: recommended approach]"
open_questions:
  - "[unresolved question 1]"
  - "[unresolved question 2]"
conventions_noted:
  - "[convention choice with rationale]"
---

# Phase [X]: [Name] - Discovery

**Discovered:** [date]
**Depth:** [verify|standard|deep]
**Confidence:** [HIGH/MEDIUM/LOW]
**Domain:** [physics subfield / problem domain]

## Summary and Recommendation

[2-3 paragraph summary of what was discovered]

- What physical question drives this discovery
- What the standard approach is and why
- Key findings that inform planning

**Recommendation:** [one-liner actionable guidance for the planner]

## Methods Landscape

### Available Approaches

| Method   | When to Use                   | Limitations            | Key Reference    | Regime of Validity  |
| -------- | ----------------------------- | ---------------------- | ---------------- | ------------------- |
| [method] | [conditions where it applies] | [where it breaks down] | [paper/textbook] | [parameter regime]  |
| [method] | [conditions where it applies] | [where it breaks down] | [paper/textbook] | [parameter regime]  |

### Recommended Method

**Method:** [chosen approach]
**Why:** [rationale - accuracy, computational cost, regime match]
**Alternatives if this fails:** [fallback options]

### Computational Tools

| Tool/Package | Purpose            | Why Standard         |
| ------------ | ------------------ | -------------------- |
| [name]       | [what it computes] | [why experts use it] |

## Known Results and Benchmarks

### Results to Reproduce (Validation Targets)

| Result | Value/Expression   | Conditions           | Source  |
| ------ | ------------------ | -------------------- | ------- |
| [what] | [value or formula] | [regime/assumptions] | [paper] |

### Limiting Cases

| Limit                | Expected Behavior    | Expression         | Source      |
| -------------------- | -------------------- | ------------------ | ----------- |
| [parameter -> value] | [what should happen] | [formula if known] | [reference] |

## Convention Choices

| Quantity   | Literature Convention(s)  | Our Choice      | Reason              |
| ---------- | ------------------------- | --------------- | ------------------- |
| [quantity] | [varies: A uses X, B uses Y] | [chosen symbol] | [consistency with project] |

**Key notational hazards:** [Where different papers use the same symbol for different things]

## Pitfalls and Warnings

### [Pitfall 1]

**What goes wrong:** [description]
**How to avoid:** [prevention strategy]
**Warning signs:** [how to detect early]

### [Pitfall 2]

**What goes wrong:** [description]
**How to avoid:** [prevention strategy]
**Warning signs:** [how to detect early]

## Open Questions

Things that couldn't be fully resolved during discovery:

1. **[Question]**
   - What we know: [partial info]
   - What's unclear: [the gap]
   - Impact on planning: [how to handle]

## What Was NOT Found

[Explicitly document gaps to prevent re-searching dead ends]

- [Question investigated but not answered, with sources checked]
- [Method searched for but not found in literature]

## Sources

### Primary (HIGH confidence)

- [Textbook/major review] - [what was checked]

### Secondary (MEDIUM confidence)

- [Recent paper, cross-checked] - [finding]

### Tertiary (LOW - needs validation during execution)

- [Single-source claim] - [finding, marked for validation]

---

_Phase: XX-name_
_Discovery completed: [date]_
_Ready for planning: [yes/no]_
````

---

## Depth-Specific Guidance

### Level 1: Quick Verify (no file output)

Confirm a specific claim against standard references:
- Check textbook formulas, review articles, standard databases (PDG, NIST, DLMF)
- Verify conventions are consistent with project framework
- If verified: proceed. If concerns: escalate to Level 2.

### Level 2: Standard (default)

All sections at moderate depth:
- Methods Landscape: 2-4 approaches compared
- Known Results: Key benchmarks and limiting cases
- Convention Choices: Reconcile notation across 2-3 references
- Sources: At least one primary and one secondary per major finding

### Level 3: Deep Dive

All sections with full analysis:
- Methods Landscape: Exhaustive survey including alternatives considered and rejected
- Known Results: Complete benchmark catalog with numerical values
- Convention Choices: Full reconciliation across all referenced papers
- Pitfalls: Comprehensive catalog with worked failure examples
- Sources: Complete citation chain for every claim
- **Validation gates:** If any finding has LOW confidence, define a checkpoint (e.g., "reproduce Table 3 of [ref] before proceeding")

---

## Integration with Planning

- DISCOVERY.md lives in phase directory: `.gpd/phases/XX-name/DISCOVERY.md`
- Loaded by plan-phase as context when creating PLAN.md
- Recommendation informs approach selection
- Known results provide verification benchmarks for the plan
- Convention choices prevent notation mismatches during execution
- Pitfalls inform deviation rules and verification criteria
- Open questions may spawn additional discovery or affect plan structure

## Confidence Gate

After creating DISCOVERY.md:
- **HIGH confidence:** Proceed directly to planning
- **MEDIUM confidence:** Note caveats, proceed with validation checkpoints in plan
- **LOW confidence:** Present options to user before proceeding (dig deeper / proceed anyway / pause)
