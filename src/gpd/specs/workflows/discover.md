<purpose>
Execute discovery at the appropriate depth level for a physics research phase.
Produces RESEARCH.md (for Level 2-3) that informs PLAN.md creation.

Can be invoked before plan-phase for deeper literature/method investigation, or run automatically during plan-phase's research step. Accepts a depth parameter.

This workflow discovers the physics landscape: what is known, what is open, what tools exist, what methods are standard, what data is available, what approximations are valid.

NOTE: For comprehensive literature survey ("what do experts know about this"), use /gpd:research-phase instead, which produces a full-depth RESEARCH.md. This workflow produces a quick-depth RESEARCH.md (depth: quick) suitable for method selection and landscape scanning.
</purpose>

<depth_levels>
**This workflow supports three depth levels:**

| Level | Name         | Time      | Output                                      | When                                                                         |
| ----- | ------------ | --------- | ------------------------------------------- | ---------------------------------------------------------------------------- |
| 1     | Quick Verify | 2-5 min   | No file, proceed with verified knowledge    | Confirming a formula, checking a known result, verifying a convention        |
| 2     | Standard     | 15-30 min | RESEARCH.md                                | Choosing between methods, exploring a new regime, setting up a calculation   |
| 3     | Deep Dive    | 1+ hour   | Detailed RESEARCH.md with validation gates | Novel problems, ambiguous literature, competing claims, foundational choices |

**Depth is determined by the caller (plan-phase.md or the user) before routing here.**
</depth_levels>

<source_hierarchy>
**MANDATORY: Authoritative sources BEFORE general search**

Physics results can be subtle and sign conventions vary across references. Always verify.

1. **Standard references FIRST** - Textbooks, review articles, established databases (PDG, NIST, OEIS)
2. **Primary literature** - Original papers where results were derived
3. **Preprint servers** - arXiv for recent developments
4. **web_search LAST** - For community discussions, code repositories, and numerical benchmarks only

See {GPD_INSTALL_DIR}/templates/research.md for the RESEARCH.md template structure (use `depth: quick` for discovery-level output).
</source_hierarchy>

<process>

<step name="load_context" priority="first">
**Load project context and conventions:**

```bash
INIT=$(gpd init phase-op --include state,config "${PHASE_ARG:-}")
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `phase_found`, `phase_dir`, `phase_number`, `phase_name`, `phase_slug`, `state_exists`.

- Extract `convention_lock` for unit system and sign conventions (so discovered formulas can be matched to project conventions)
- Extract active approximations (so discovery can focus on the relevant regime)
- If no project context exists (standalone usage), proceed with user-specified topic

**If `phase_found` is false and a phase was specified:** Error — phase not found.
**If no phase specified:** Discovery is standalone; output goes to `.gpd/analysis/`. Ensure the directory exists: `mkdir -p .gpd/analysis`.
</step>

<step name="determine_depth">
**Parse depth from `$ARGUMENTS`:**

Extract `--depth` flag if present: `--depth quick`, `--depth medium`, `--depth deep`.

Map to internal depth levels:
- `--depth quick` or `depth=verify` -> Level 1 (Quick Verification)
- `--depth medium` or `depth=standard` -> Level 2 (Standard Discovery)
- `--depth deep` or `depth=deep` -> Level 3 (Deep Dive)
- No `--depth` flag -> Default to Level 2 (Standard Discovery)

When called from `plan-phase.md`, the depth is passed as a parameter directly (not via `$ARGUMENTS`).

Route to appropriate level workflow below.
</step>

<step name="level_1_quick_verify">
**Level 1: Quick Verification (2-5 minutes)**

For: Confirming a formula, checking a convention, verifying a known result is still current.

**Process:**

1. Identify the specific claim to verify:

   - A formula or expression
   - A numerical value or constant
   - A convention (sign, normalization, metric signature)
   - A known result or theorem

2. Check against standard references:

   - Textbook formulas (Peskin & Schroeder, Weinberg, Sakurai, Landau & Lifshitz, etc.)
   - Review articles (Rev. Mod. Phys., Physics Reports, etc.)
   - Standard databases (PDG for particle data, NIST for constants, DLMF for special functions)

3. Verify:

   - Result matches expectations
   - Conventions are consistent with our framework
   - No recent corrections or errata

4. **If verified:** Return to plan-phase.md with confirmation. No RESEARCH.md needed.

5. **If concerns found:** Escalate to Level 2.

**Output:** Verbal confirmation to proceed, or escalation to Level 2.
</step>

<step name="level_2_standard">
**Level 2: Standard Discovery (15-30 minutes)**

For: Choosing between methods, exploring a new parameter regime, setting up a new type of calculation.

**Process:**

1. **Identify what to discover:**

   - What methods or approaches exist for this calculation?
   - What are the key comparison criteria (accuracy, cost, regime of validity)?
   - What is our specific physical setup?

2. **Search standard references for each approach:**

   ```
   For each method/technique:
   - Check textbook treatments
   - Find original papers where method was developed
   - Look for review articles comparing approaches
   ```

3. **Check primary literature** for recent developments and applications to similar systems.

4. **Search arXiv and journals** for comparisons:

   - "[method A] vs [method B] [physical system]"
   - "[method] limitations [regime]"
   - "[method] benchmark [observable]"

5. **Cross-verify:** Any claim from a single source -> confirm with independent source. Watch for sign conventions and normalization differences between references.

6. **Create RESEARCH.md** using {GPD_INSTALL_DIR}/templates/research.md structure:

   - Summary with recommendation
   - Key findings per method/approach
   - Explicit formulas with convention choices stated
   - Regime of validity for each approach
   - Confidence level (should be MEDIUM-HIGH for Level 2)

7. Return to plan-phase.md.

**Output:** `${phase_dir}/RESEARCH.md`
</step>

<step name="level_3_deep_dive">
**Level 3: Deep Dive (1+ hour)**

For: Novel problems, ambiguous or contradictory literature, foundational choices that affect the entire calculation, high-risk methodological decisions.

**Process:**

1. **Scope the discovery** using {GPD_INSTALL_DIR}/templates/research.md:

   - Define clear scope (which physical question, which regime, which observable)
   - Define include/exclude boundaries
   - List specific questions to answer

2. **Exhaustive literature search:**

   - All relevant textbooks and monographs
   - Key review articles in the subfield
   - Original papers where methods were developed
   - Recent papers applying methods to similar systems
   - Competing approaches and their proponents

3. **Mathematical framework analysis:**

   - Write down the starting Lagrangian/Hamiltonian/action explicitly
   - Identify all symmetries and conservation laws
   - Map out the approximation hierarchy
   - Check consistency of conventions across all sources
   - Identify subtleties (anomalies, gauge fixing, regularization scheme dependence)

4. **Numerical landscape survey:**

   - What codes exist for this type of calculation?
   - What benchmarks are available?
   - What are known numerical pitfalls (convergence, sign problems, critical slowing down)?
   - What computational resources are needed?

5. **Cross-verify ALL findings:**

   - Every result -> verify with independent derivation or source
   - Mark what is established vs conjectured vs controversial
   - Flag contradictions between references (with specific citations)
   - Note where conventions differ and choose ours explicitly

6. **Create comprehensive RESEARCH.md:**

   - Full structure from {GPD_INSTALL_DIR}/templates/research.md
   - Quality report with source attribution
   - Confidence by finding
   - If LOW confidence on any critical finding -> add validation checkpoints (e.g., "reproduce Table 3 of [ref] before proceeding")

7. **Confidence gate:** If overall confidence is LOW, present options before proceeding.

8. Return to plan-phase.md.

**Output:** `${phase_dir}/RESEARCH.md` (comprehensive)
</step>

<step name="identify_unknowns">
**For Level 2-3:** Define what we need to learn.

Ask: What do we need to know before we can plan this phase?

- Which method is most appropriate for this regime?
- What are the known results we should reproduce as benchmarks?
- What are the dominant corrections we might be neglecting?
- Are there subtleties in the mathematical framework (gauge fixing, regularization, etc.)?
- What numerical methods and codes are available?
- What experimental or simulation data exists for comparison?
  </step>

<step name="create_discovery_scope">
Use {GPD_INSTALL_DIR}/templates/research.md.

Include:

- Clear discovery objective (what physical question drives this)
- Scoped include/exclude lists
- Source preferences (textbooks, reviews, arXiv, specific journals)
- Output structure for RESEARCH.md
  </step>

<step name="execute_discovery">
Run the discovery:
- Check standard references first (textbooks, reviews)
- Search primary literature (original papers)
- Use arXiv for recent developments
- Use web search for code repositories and benchmarks
- Structure findings per template
- Note all conventions explicitly
</step>

<step name="create_discovery_output">
Ensure output directory exists and write RESEARCH.md:

**Phase-scoped:** `${phase_dir}/RESEARCH.md`
**Standalone (no phase):**

```bash
mkdir -p .gpd/analysis
```

Write to `.gpd/analysis/discovery-{slug}.md` (where `{slug}` is derived from the discovery topic).

Contents of RESEARCH.md:
- Summary with recommendation
- Key findings with sources (specific references, not vague citations)
- Explicit formulas with conventions stated
- Regime of validity for each approach
- Metadata (confidence, dependencies, open questions, assumptions)
</step>

<step name="confidence_gate">
After creating RESEARCH.md, check confidence level.

> **Platform note:** If `ask_user` is not available, present these options in plain text and wait for the user's freeform response.

If confidence is LOW:
Use ask_user:

- header: "Low Confidence"
- question: "Discovery confidence is LOW: [reason]. How would you like to proceed?"
- options:
  - "Dig deeper" - Do more literature search before planning
  - "Proceed anyway" - Accept uncertainty, plan with caveats and validation checkpoints
  - "Pause" - I need to think about this / consult with collaborators

If confidence is MEDIUM:
Inline: "Discovery complete (medium confidence). [brief reason]. Proceed to planning?"

If confidence is HIGH:
Proceed directly, just note: "Discovery complete (high confidence)."
</step>

<step name="open_questions_gate">
If RESEARCH.md has open_questions:

Present them inline:
"Open questions from discovery:

- [Question 1: e.g., Sign convention for the vertex function in dimensional regularization]
- [Question 2: e.g., Whether the series converges in the regime g > 1]

These may affect the derivation. Acknowledge and proceed? (yes / address first)"

If "address first": Gather user input on questions, update discovery.
</step>

<step name="offer_next">
```
Discovery complete: ${phase_dir}/RESEARCH.md
Recommendation: [one-liner]
Confidence: [level]

What's next?

1. Discuss phase context (/gpd:discuss-phase [current-phase])
2. Create phase plan (/gpd:plan-phase [current-phase])
3. Refine discovery (dig deeper)
4. Review discovery

```

NOTE: RESEARCH.md is NOT committed separately. It will be committed with phase completion.
</step>

</process>

<success_criteria>
**Level 1 (Quick Verify):**
- Standard reference consulted for formula/result/convention
- Current state verified or concerns escalated
- Verbal confirmation to proceed (no files)

**Level 2 (Standard):**
- Standard references consulted for all approaches
- Claims cross-verified against independent sources
- Conventions explicitly stated
- RESEARCH.md created with recommendation
- Confidence level MEDIUM or higher
- Ready to inform PLAN.md creation

**Level 3 (Deep Dive):**
- Discovery scope defined
- Literature exhaustively surveyed (textbooks, reviews, primary papers, arXiv)
- All claims verified against independent sources
- Conventions reconciled across references
- RESEARCH.md created with comprehensive analysis
- Quality report with source attribution
- If LOW confidence findings -> validation checkpoints defined (reproduce known result X before proceeding)
- Confidence gate passed
- Ready to inform PLAN.md creation
</success_criteria>
