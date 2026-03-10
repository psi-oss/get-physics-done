# Cross-Project Pattern Library

How the global pattern library works -- a persistent knowledge base of physics error patterns, convention pitfalls, and recurring issues that accumulates across all GPD projects.

<core_principle>
**Projects end, patterns persist.**

A sign error caused by metric signature confusion in one QFT project is the same sign error in every QFT project. A convergence failure from naive lattice discretization in one condensed matter calculation will recur in the next. The cross-project pattern library captures these lessons so they are available before the error is made, not after.

The library lives outside any single project at the resolved global pattern-library root: `GPD_PATTERNS_ROOT` -> `GPD_DATA_DIR/learned-patterns` -> `~/.gpd/learned-patterns`.
</core_principle>

<location>

## Storage Location

```text
~/.gpd/learned-patterns/
  patterns-by-domain/
    qft/
    condensed-matter/
    stat-mech/
    gr/
    amo/
    nuclear/
    classical/
    fluid/
    plasma/
    astro/
    mathematical/
    soft-matter/
    quantum-info/
  index.json
```

**Why the global `.gpd` directory:** This directory persists across all projects and sessions. Project-local `.gpd/INSIGHTS.md` captures project-specific lessons; the global library captures cross-project patterns.

**Each pattern file** follows the `learned-pattern.md` template (see `../../templates/learned-pattern.md`). Filenames use the format `{category}-{short-slug}.md` (e.g., `sign-error-metric-signature.md`, `factor-error-fourier-convention.md`).

</location>

<index_structure>

## Index File (`index.json`)

The index provides fast lookup without reading every pattern file. Agents filter by domain and category to find relevant patterns.

```json
{
  "version": 1,
  "patterns": [
    {
      "id": "qft-sign-error-metric-signature",
      "file": "patterns-by-domain/qft/sign-error-metric-signature-mismatch.md",
      "domain": "qft",
      "category": "sign-error",
      "severity": "critical",
      "confidence": "confirmed",
      "title": "Metric signature sign flip in propagator denominators",
      "first_seen": "2025-09-12",
      "last_seen": "2025-11-03",
      "occurrence_count": 3,
      "tags": ["propagator", "metric", "sign", "momentum-space"]
    }
  ]
}
```

**Index fields:**

| Field              | Purpose                                               |
| ------------------ | ----------------------------------------------------- |
| `id`               | Unique identifier: `{domain}-{category}-{slug}`       |
| `file`             | Relative path from the pattern-library root           |
| `domain`           | Physics domain (matches subdirectory)                 |
| `category`         | Error category from the template                      |
| `severity`         | critical / high / medium / low                        |
| `confidence`       | single_observation / confirmed / systematic           |
| `title`            | Short descriptive title (from pattern file)           |
| `first_seen`       | Date the pattern was first recorded                   |
| `last_seen`        | Date the pattern was most recently observed           |
| `occurrence_count` | Number of times observed across projects              |
| `tags`             | Free-form tags for search (keywords from the pattern) |

</index_structure>

<when_patterns_are_written>

## When Patterns Are Written

Patterns enter the library from three sources. Each writes to both the project-local record and the global library.

### After debugger confirms a root cause

When the debugger (gpd-debugger) resolves a debug session and identifies a root cause:

1. The `Resolution.lessons_learned` field in the debug file captures the project-specific lesson
2. The debugger writes the same lesson to the project's `.gpd/INSIGHTS.md`
3. The debugger checks whether a matching pattern already exists in the global library:
   - **No match:** Create a new pattern file from the `learned-pattern.md` template with confidence `single_observation`. Add entry to `index.json`.
   - **Match found:** Update `last_seen`, increment `occurrence_count`. If confidence was `single_observation` and this is a different project, upgrade to `confirmed`.

### After verifier discovers a systematic error type

When the verifier (gpd-verifier) finds that a particular class of error recurs across multiple phases or plans within a project:

1. Write a pattern file capturing the error class, detection method, and prevention strategy
2. Set confidence based on how many independent instances were found:
   - 1 instance: `single_observation`
   - 2-3 instances within one project: `single_observation` (same project does not count as independent confirmation)
   - Instances across different projects: `confirmed`

### After consistency checker finds a convention violation

When a cross-phase convention violation is detected (e.g., one phase uses East Coast metric while another uses West Coast):

1. Write a pattern file focused on the convention pitfall
2. Include specific detection criteria (what to grep for, what to check in STATE.md)
3. Include prevention guidance (what the planner should specify in PLAN.md)

</when_patterns_are_written>

<when_patterns_are_read>

## When Patterns Are Read

Different agents read patterns at different points in the workflow.

### Planner reads before creating plans

During the `consult_learned_patterns` step of plan creation:

1. Read `index.json`
2. Filter by domain tags matching the current project's domain (from `.gpd/PROJECT.md`)
3. Sort by: severity (critical first), then confidence (systematic > confirmed > single_observation), then occurrence_count (descending)
4. Read the top 5 most relevant pattern files
5. Incorporate prevention guidance into plan structure:
   - Add explicit convention checks to task descriptions
   - Include known pitfall warnings in `@context` sections
   - Add specific key_links to `must_haves` that would catch the pattern

### Executor reads before starting work

Before executing a plan's tasks:

1. Read `index.json`, filter by current domain
2. Read patterns with severity `critical` or `high`
3. Keep these patterns in working memory as "watch for" items during derivation and computation
4. When a step matches a known pattern's trigger conditions, apply the prevention method before proceeding

### Verifier reads to prioritize checks

When setting up verification:

1. Read `index.json`, filter by current domain
2. Read all patterns with category matching the current verification scope
3. Add pattern-specific checks to the verification checklist:
   - If a sign-error pattern exists for this domain, add explicit sign checks at the specific locations described in the pattern
   - If a factor-error pattern exists, add numerical spot-checks at the specific values described in the pattern
   - If a convergence-issue pattern exists, add convergence tests with the specific parameter ranges described in the pattern

</when_patterns_are_read>

<pattern_lifecycle>

## Pattern Lifecycle

Patterns evolve through a confidence progression and can eventually be archived.

### Confidence levels

| Level                | Meaning                                           | Threshold                                                |
| -------------------- | ------------------------------------------------- | -------------------------------------------------------- |
| `single_observation` | Seen once in one project                          | Initial recording                                        |
| `confirmed`          | Seen independently in multiple projects           | Same pattern recorded from a different project           |
| `systematic`         | Pervasive pattern with well-understood root cause | 5+ occurrences across 3+ projects, root cause documented |

### Progression rules

- **New pattern:** Always starts at `single_observation`
- **Same project, different phase:** Increment `occurrence_count` but do NOT upgrade confidence (same project is not independent confirmation)
- **Different project, same pattern:** Upgrade `single_observation` to `confirmed`. Increment `occurrence_count`.
- **5+ occurrences across 3+ projects:** Upgrade `confirmed` to `systematic`
- **Confidence never decreases.** A pattern confirmed across projects remains confirmed even if not seen in the current project.

### Archival

- Patterns not observed for 10+ consecutive projects are archived, NOT deleted
- Archived patterns move to `patterns-by-domain/{domain}/archived/`
- Archived patterns are excluded from the default `index.json` query but remain searchable
- Rationale: physics pitfalls do not expire. A convention error that has not been seen recently may simply mean recent projects avoided that subfield. It will recur when the subfield is revisited.

</pattern_lifecycle>

<agent_integration>

## Integration with Agents

> **Status:** Agent definitions reference the global pattern library. gpd-planner reads top 5 patterns by severity during `consult_learned_patterns`. gpd-verifier checks domain-matching patterns during verification setup. gpd-executor reads critical/high patterns before starting work. gpd-debugger reads existing patterns before investigating and writes/updates patterns after confirming root causes. Agents also use project-local `.gpd/INSIGHTS.md` and `.gpd/ERROR-PATTERNS.md` for within-project pattern learning.

Each agent integrates with the pattern library at specific points in its workflow.

### Common pattern: reading the index

```
1. Read `<pattern-library-root>/index.json`
2. Parse the patterns array
3. Filter: pattern.domain matches current project domain (from PROJECT.md)
4. Sort by severity (critical first), then confidence, then occurrence_count
5. Select top N patterns (5 for planner, all critical/high for executor, all matching for verifier)
6. Read selected pattern files
7. Extract actionable guidance for the current workflow step
```

### Agent-specific integration points

| Agent        | When                            | What it reads                  | What it does with patterns                                   |
| ------------ | ------------------------------- | ------------------------------ | ------------------------------------------------------------ |
| gpd-planner  | `consult_learned_patterns` step | Top 5 by relevance             | Adds prevention steps to plans, key_links to must_haves      |
| gpd-executor | Before starting task execution  | All critical/high for domain   | Watches for trigger conditions during derivation             |
| gpd-verifier | During verification setup       | All patterns matching domain   | Adds pattern-specific checks to verification report          |
| gpd-debugger | After confirming root cause     | Existing patterns for matching | Writes new pattern or updates existing one                   |

### Writing a new pattern

```
1. Identify the root cause and error class
2. Determine domain and category from the template's allowed values
3. Check index.json for existing pattern with same domain + category + similar description
4. If no match:
   a. Create pattern file from learned-pattern.md template
   b. Save to patterns-by-domain/{domain}/{category}-{slug}.md
   c. Add entry to index.json with confidence: single_observation
5. If match found:
   a. Update last_seen date
   b. Increment occurrence_count
   c. If different project and confidence is single_observation: upgrade to confirmed
   d. Add any new details (additional examples, refined detection methods) to pattern file
   e. Update index.json entry
```

</agent_integration>

<relationship_to_project_insights>

## Relationship to Project-Local INSIGHTS.md

The global pattern library and project-local `.gpd/INSIGHTS.md` serve complementary roles:

| Aspect     | INSIGHTS.md                           | Global Pattern Library                            |
| ---------- | ------------------------------------- | ------------------------------------------------- |
| Scope      | Single project                        | All projects                                      |
| Location   | `.gpd/INSIGHTS.md`               | `~/.gpd/learned-patterns/` |
| Content    | Project-specific findings and lessons | Generalized error patterns and prevention methods |
| Lifetime   | Lives with the project                | Persists indefinitely                             |
| Written by | Debugger, executor                    | Debugger, verifier                                |
| Read by    | All agents working on the project     | All agents working on any project                 |

**Flow:** A project-specific insight in INSIGHTS.md that recurs across projects graduates to a global pattern. The global pattern is more general (stripped of project-specific details) and includes detection and prevention guidance.

</relationship_to_project_insights>

<bootstrapping>

## Bootstrapping the Library

When the pattern library does not yet exist (first GPD session on a machine):

1. Agents that attempt to read `index.json` and find it missing should create the directory structure:
   ```
   mkdir -p ~/.gpd/learned-patterns/patterns-by-domain/{qft,condensed-matter,stat-mech,gr,amo,nuclear,classical,fluid,plasma,astro,mathematical,soft-matter,quantum-info}
   ```
2. Create an empty `index.json`:
   ```json
   {
     "version": 1,
     "patterns": []
   }
   ```
3. Continue with normal operation -- the library will populate organically as projects are completed and errors are resolved.

Agents should handle the empty-library case gracefully: no patterns found means no additional checks to add, not an error condition.

</bootstrapping>

<bootstrap_patterns>

## Bootstrap Patterns

Seed patterns derived from common LLM physics error classes (see `references/verification/errors/llm-physics-errors.md`). These provide immediate value even before the automated library infrastructure is in place.

### Pattern 1: Sign Error in Fourier Convention Switch

**Domain:** qft, condensed-matter
**Category:** sign-error
**Severity:** critical

**Description:** When combining expressions derived with different Fourier conventions (physics: e^{-ikx} vs math: e^{+2πikx} vs symmetric), sign errors appear in interference terms, propagators, and response functions. The error often cancels in squared quantities (cross sections) but persists in interference terms and phase-sensitive observables.

**Detection:** Check the sign of the imaginary part of response functions (Im[χ] should have definite sign from causality). Verify retarded/advanced structure is preserved. Test with known Fourier pairs (Gaussian, Lorentzian).

**Prevention:** Lock Fourier convention at project start. Before combining any two expressions, verify they use the same convention. Insert explicit conversion factors when they don't.

### Pattern 2: Missing Factor of 2π in Density of States

**Domain:** condensed-matter, stat-mech, qft
**Category:** factor-error
**Severity:** high

**Description:** The density of states g(E) picks up factors of 2π from the Fourier convention and the definition of momentum integration measure. Common error: using ∫dk instead of ∫dk/(2π)^d, or vice versa. This produces density of states off by (2π)^d, which propagates to thermodynamic quantities, transport coefficients, and scattering rates.

**Detection:** Check dimensional analysis of g(E). Verify the free-particle DOS reproduces known results: g(E) = m/(πℏ²) per spin in 2D, g(E) = m√(2mE)/(π²ℏ³) per spin in 3D. Compare integrated DOS with electron count.

**Prevention:** Always write the momentum integration measure explicitly with its (2π)^d factor. Verify against free-particle DOS before computing interacting DOS.

### Pattern 3: Wrong Branch Cut in Analytic Continuation

**Domain:** qft, condensed-matter
**Category:** conceptual-error
**Severity:** critical

**Description:** When analytically continuing from Matsubara frequencies (iωₙ) to real frequencies (ω + iη), choosing the wrong Riemann sheet flips the sign of Im[G], turning a retarded propagator into an advanced one. This produces negative spectral functions (unphysical) and acausal response.

**Detection:** Check spectral function positivity: A(k,ω) = -(1/π)Im[G^R(k,ω)] ≥ 0. Check causality: G^R(t<0) = 0. Verify KK consistency.

**Prevention:** Always continue iωₙ → ω + iη (positive infinitesimal η) for retarded functions. Verify by checking that poles of G^R lie in the lower half-plane.

### Pattern 4: Metric Signature Mismatch in Propagator

**Domain:** qft
**Category:** sign-error
**Severity:** critical

**Description:** Mixing (+,−,−,−) and (−,+,+,+) metric conventions in the same calculation. The propagator is 1/(k² − m²) with (+,−,−,−) but 1/(−k² − m²) = −1/(k² + m²) with (−,+,+,+), where k² means different things in each convention. Combining a vertex from one convention with a propagator from another produces wrong signs in every diagram.

**Detection:** Check: what does k² = m² mean? With (+,−,−,−): k₀² − |k|² = m² (positive). With (−,+,+,+): −k₀² + |k|² = m² → k₀² = |k|² − m² (wrong for massive particles at rest). If on-shell condition looks wrong, suspect a signature mismatch.

**Prevention:** State metric signature at the top of every derivation file. When importing from external sources, check their signature convention first.

### Pattern 5: Missing 1/N! for Identical Particles

**Domain:** stat-mech, qft
**Category:** factor-error
**Severity:** high

**Description:** The classical partition function for N identical particles requires a factor of 1/N! (Gibbs factor) to avoid overcounting. LLMs frequently omit this, producing an extensive entropy that depends on the total particle number rather than the density — the Gibbs paradox. In quantum field theory, the same error manifests as wrong symmetry factors in Feynman diagrams.

**Detection:** Check that entropy is extensive (S doubles when system doubles). Check that mixing entropy vanishes for identical gases. Verify Feynman diagram symmetry factors against automated tools.

**Prevention:** Always include 1/(N! h^{3N}) in classical partition functions. For Feynman diagrams, compute symmetry factors from the automorphism group, don't guess.

### Pattern 6: Confusing Coupling Constant Conventions

**Domain:** qft
**Category:** factor-error
**Severity:** high

**Description:** Different sources define the coupling constant differently: g, g², g²/(4π), α = g²/(4π). A "one-loop correction of order g²" in one source is "order α" in another and "order g⁴/(16π²)" in a third. Combining results from different sources without converting produces wrong numerical coefficients.

**Detection:** Check: what is the tree-level amplitude in terms of the coupling? If Coulomb scattering is ∝ e², then e² = 4πα in Heaviside-Lorentz natural units. Verify that α ≈ 1/137 in all systems.

**Prevention:** Convert all couplings to a single convention (typically α = g²/(4π)) before combining results. State the convention explicitly.

### Pattern 7: Dimensional Mismatch When Restoring ℏ and c

**Domain:** all
**Category:** dimensional-error
**Severity:** high

**Description:** When converting from natural units to SI, each quantity needs specific powers of ℏ and c restored based on its mass dimension. Common error: restoring ℏ but not c, or restoring the wrong power of c.

**Detection:** Check that the final expression has correct SI dimensions. Evaluate numerically in both unit systems and compare.

**Prevention:** Use the systematic procedure: identify mass dimension in natural units, then restore [energy] = [M][c²], [length] = [ℏ]/([M][c]), [time] = [ℏ]/([M][c²]). See error class 33 in `references/verification/errors/llm-physics-errors.md` for worked examples.

### Pattern 8: Wrong Sign in Wick Rotation

**Domain:** qft
**Category:** sign-error
**Severity:** critical

**Description:** Wick rotation t → −iτ (or k₀ → ik₄) must be performed carefully to avoid crossing poles in the complex plane. The direction of rotation (clockwise vs counterclockwise) depends on the pole structure, which depends on the metric signature. Getting this wrong flips the sign of the Euclidean action, turning a convergent path integral into a divergent one.

**Detection:** Check that the Euclidean action S_E is bounded below (for bosonic theories). Verify that the Euclidean propagator 1/(k_E² + m²) is positive. Check that the rotation direction avoids the poles of the Minkowski propagator.

**Prevention:** With (+,−,−,−) signature, poles are at k₀ = ±(|k|² + m² − iε)^{1/2}. Rotate k₀ → ik₄ counterclockwise. Verify: the Minkowski propagator i/(k² − m² + iε) becomes −1/(k_E² + m²) after rotation, with the correct sign.

</bootstrap_patterns>
