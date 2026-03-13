# Model Profiles

Model profiles control which model tier each GPD agent uses. This allows balancing quality vs token spend.

## Tier System

GPD uses capability tiers instead of platform-specific model names:

- **tier-1**: Highest capability (strongest reasoning model available on the platform)
- **tier-2**: Balanced capability/cost (standard model)
- **tier-3**: Fast/economical (fastest model)

`gpd resolve-tier` exposes the abstract tier assignment for a given agent.
`gpd resolve-model` resolves that tier to a runtime-specific override only when `.gpd/config.json` defines `model_overrides.<runtime>.<tier>`.
If no override is configured for the active runtime, `gpd resolve-model` returns empty output and the task call should omit `model` so the platform uses its default model.

## Profile Definitions

| Agent                    | `deep-theory` | `numerical` | `exploratory` | `review` | `paper-writing` |
| ------------------------ | ------------- | ----------- | ------------- | -------- | --------------- |
| gpd-planner              | tier-1        | tier-1      | tier-1        | tier-1   | tier-1          |
| gpd-roadmapper           | tier-1        | tier-1      | tier-2        | tier-1   | tier-2          |
| gpd-executor             | tier-1        | tier-2      | tier-2        | tier-2   | tier-1          |
| gpd-phase-researcher     | tier-1        | tier-1      | tier-1        | tier-2   | tier-2          |
| gpd-project-researcher   | tier-1        | tier-2      | tier-1        | tier-2   | tier-3          |
| gpd-research-synthesizer | tier-1        | tier-2      | tier-2        | tier-2   | tier-1          |
| gpd-debugger             | tier-1        | tier-1      | tier-2        | tier-1   | tier-2          |
| gpd-research-mapper      | tier-2        | tier-3      | tier-3        | tier-3   | tier-3          |
| gpd-verifier             | tier-1        | tier-1      | tier-2        | tier-1   | tier-2          |
| gpd-plan-checker         | tier-2        | tier-2      | tier-2        | tier-1   | tier-2          |
| gpd-consistency-checker  | tier-1        | tier-2      | tier-2        | tier-1   | tier-2          |
| gpd-paper-writer         | tier-1        | tier-2      | tier-2        | tier-2   | tier-1          |
| gpd-literature-reviewer  | tier-1        | tier-2      | tier-1        | tier-2   | tier-2          |
| gpd-bibliographer        | tier-2        | tier-3      | tier-3        | tier-2   | tier-1          |
| gpd-explainer            | tier-1        | tier-2      | tier-1        | tier-1   | tier-1          |
| gpd-review-reader        | tier-2        | tier-2      | tier-2        | tier-2   | tier-2          |
| gpd-review-literature    | tier-1        | tier-2      | tier-1        | tier-1   | tier-2          |
| gpd-review-math          | tier-1        | tier-1      | tier-2        | tier-1   | tier-1          |
| gpd-review-physics       | tier-1        | tier-1      | tier-2        | tier-1   | tier-1          |
| gpd-review-significance  | tier-2        | tier-2      | tier-2        | tier-1   | tier-1          |
| gpd-referee              | tier-1        | tier-2      | tier-2        | tier-1   | tier-1          |
| gpd-experiment-designer  | tier-2        | tier-1      | tier-2        | tier-2   | tier-3          |
| gpd-notation-coordinator | tier-2        | tier-3      | tier-3        | tier-2   | tier-2          |

## Profile Philosophy

**deep-theory** - Maximum rigor for formal derivations

- Tier-1 for all reasoning-intensive agents, especially planner, executor, verifier
- Formal proofs, exact solutions, rigorous mathematical arguments
- Use when: deriving new results, proving theorems, establishing bounds, working with axiomatic frameworks
- Trade-off: highest token spend, but errors in formal work are catastrophic

**numerical** - Computational physics focus

- Tier-1 for planning and debugging (architecture of numerical pipelines)
- Tier-1 for verifier (convergence analysis requires strong reasoning)
- Tier-2 for execution (follows well-specified numerical recipes)
- Use when: running simulations, finite element analysis, Monte Carlo methods, numerical integration
- Trade-off: convergence debugging needs quality; routine computation does not

**exploratory** - Creative, broad search across solution space

- Tier-1 for planner and researchers (hypothesis generation needs creativity)
- Tier-2 for execution and verification (testing ideas is cheaper)
- Use when: exploring new phenomena, brainstorming approaches, surveying parameter space, early-stage research
- Trade-off: quantity of ideas over depth of any single one

**review** (default) - Validation-heavy, cross-checking emphasis

- Tier-1 for verifier, plan-checker, consistency-checker, and debugger
- Tier-2 for execution and research (follows verification protocols)
- Use when: checking known results, peer-review preparation, validating calculations, reproducing literature
- Trade-off: strong verification at the cost of slower generation

**paper-writing** - Narrative and presentation focus

- Tier-1 for planner, executor, and synthesizer (narrative coherence matters)
- Tier-2 for verification (checking claims, not generating them)
- Tier-3 for project-level research (quick literature lookups)
- Use when: writing papers, preparing talks, creating figures, structuring arguments
- Trade-off: presentation quality over computational depth

## Behavioral Effects

Profiles affect agent behavior, not just model selection. When a profile is active, agents adjust their depth, focus, and workflow -- not merely which model tier they run on. This means choosing a profile shapes the entire research experience: how thoroughly errors are investigated, how many plan dimensions are checked, and what kind of output agents prioritize.

### gpd-debugger

| Profile         | Behavioral Change                                                                                                                                                        |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **deep-theory** | Full investigation. Uses all 9 debugging techniques. Requires formal proof of root cause. Tests fix against 3+ independent checks.                                       |
| **numerical**   | Focuses on numerical diagnostics (convergence, precision, algorithm issues). Binary search through parameter space. Richardson extrapolation for error characterization. |
| **exploratory** | Quick triage only. Identifies whether the error is fundamental (stop) or fixable (patch and continue). Max 2 investigation rounds before escalating.                     |
| **review**      | Exhaustive documentation. Every hypothesis tested is recorded. Creates detailed error timeline. Focuses on whether the error could affect other phases.                  |

### gpd-plan-checker

| Profile         | Behavioral Change                                                                                                                                                                                 |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory** | All 16 verification dimensions checked at maximum rigor. Requires explicit justification for every approximation. Flags any task without a validation step.                                       |
| **numerical**   | Emphasizes dimensions 5 (computational feasibility), 7 (numerical stability), 8 (error budgets), 9 (dependencies), 16 (environment validation). Requires convergence testing plan for every numerical task. |
| **exploratory** | Reduces to 9 core dimensions: Dim 1 (Research Question Coverage), 2 (Task Completeness), 4 (Approximation Validity), 5 (Computational Feasibility), 8 (Result Wiring), 9 (Dependency Correctness), 10 (Scope Sanity), 11 (Deliverable Derivation), 16 (Environment Validation). Skips: Dim 3, 6, 7, 12, 13, 14, 15. |
| **review**      | All 16 dimensions plus additional checks: does the plan reference specific literature results for comparison? Are all claims testable?                                                            |
| **paper-writing** | All 16 dimensions with emphasis on Dim 12 (Publication Readiness), Dim 8 (Result Wiring), Dim 11 (Deliverable Derivation). Verify plans map to paper sections, figures, and tables. Check notation consistency tasks exist. |

### gpd-verifier

| Profile           | Behavioral Change                                                                                                                                                                                                                                                                                    |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Maximum verification depth. Runs the full universal verifier registry plus any required contract-aware checks. Requires INDEPENDENTLY CONFIRMED confidence for every key derivation result, re-derives limiting cases, and traces conventions through the whole calculation.                        |
| **numerical**     | Computation-focused verification. Still runs required contract-aware checks, but emphasizes convergence, numerical spot-checks, benchmark reproduction, and error budgets. De-emphasizes analytical re-derivation unless it is validating numerics.                                                |
| **exploratory**   | Lightweight universal-check floor plus all required contract-aware checks. Exploration may reduce depth, but it does NOT waive decisive-anchor, forbidden-proxy, or direct-vs-proxy checks. The goal is to catch gross errors early without pretending proxy-only success is enough.             |
| **review**        | Cross-validation focused. Runs the full registry plus extra literature and approximation-bound scrutiny. Compares every material numerical result against literature or benchmark anchors and flags any result that cannot be cross-validated.                                                       |
| **paper-writing** | Publication-readiness verification. Runs the full registry plus manuscript-facing checks: figures match data, equations match derivation files, notation is consistent, decisive artifacts have explicit verdicts, and references exist.                                                          |

### gpd-planner

| Profile           | Behavioral Change                                                                                                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Adds derivation checkpoint every 2 steps (not 3-4). Requires INDEPENDENTLY_CONFIRMED for all key results. Every 2 derivation steps, inserts a verification task that independently re-derives or cross-checks the result. |
| **numerical**     | Adds convergence testing task for every numerical computation. Requires error budget task per plan tracking how numerical errors propagate through the calculation chain.                                                 |
| **exploratory**   | Uses the smallest viable task structure, but still keeps decisive contract checks, anchor references, and forbidden proxies visible. Allows larger tasks only when first-result and pre-fanout gates remain intact.                                                                              |
| **review**        | Adds cross-reference task comparing every result to at least one published source with full bibliographic reference. Requires 2+ independent verification methods for every result.                                       |
| **paper-writing** | Adds notation consistency task per plan checking all symbols are defined, equations in text match derivation files, and figures match data. Adds reference verification task. Prioritizes readability and logical flow.   |

### gpd-executor

| Profile           | Behavioral Change                                                                                                                                                                                                         |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Maximum rigor. Inserts verification checkpoint after every derivation step. Requires all intermediate results to be dimensionally checked. Refuses to proceed past a step with unresolved sign ambiguity or index mismatch. |
| **numerical**     | Convergence-first execution. Every numerical computation includes grid/basis/timestep refinement test before result is accepted. Automatically runs Richardson extrapolation. Fast iteration on code, slow acceptance of results. |
| **exploratory**   | Speed over depth, but not at the cost of decisive checks. Larger tasks are allowed only when required first-result, anchor, and pre-fanout gates still run. Approximate answers may guide exploration, but they do not satisfy contract-backed success criteria on their own.                |
| **review**        | Reproduction-focused. Every step cross-references the specific literature source it implements. Documents deviations from published methods. Adds provenance annotation to every computed quantity.                        |
| **paper-writing** | Narrative execution. Organizes computation output for direct inclusion in manuscript. Generates clean intermediate expressions suitable for equations in text. Prioritizes readable variable names and well-commented derivation files. |

### gpd-phase-researcher

| Profile           | Behavioral Change                                                                                                                                                                                    |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Deep literature dive. Reads primary sources (not just reviews). Traces the provenance of key equations back to original derivations. Identifies all assumptions behind each method, including implicit ones. |
| **numerical**     | Implementation-focused research. Prioritizes finding working code, validated algorithms, and published benchmarks. Evaluates numerical stability and convergence properties of each candidate method. |
| **exploratory**   | Breadth-first survey. Scans across subfields for analogous techniques. Prioritizes finding 5+ candidate approaches over fully understanding any single one. Reports a ranked shortlist with trade-offs. |
| **review**        | Verification-oriented research. For each method found, identifies what independent checks exist (sum rules, limiting cases, conservation laws). Prioritizes methods with built-in validation pathways. |
| **paper-writing** | Context-gathering research. Focuses on how the planned work relates to prior literature. Identifies the key references that must be cited. Maps the narrative gap the paper will fill.                 |

### gpd-project-researcher

| Profile           | Behavioral Change                                                                                                                                                                           |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Thorough domain survey. Maps the full theoretical landscape around the problem: known exact results, rigorous bounds, open conjectures. Identifies which results are proven vs widely believed. |
| **numerical**     | Computational landscape survey. Catalogs existing codes, published benchmarks, available datasets. Identifies state-of-the-art numerical methods and their limitations for the problem class. |
| **exploratory**   | Maximum breadth. Surveys adjacent fields for cross-pollination opportunities. Identifies unconventional approaches (e.g., machine learning for physics, information-theoretic methods). Casts a wide net. |
| **review**        | Gap-identification focus. Maps what is established vs contested vs unknown. Identifies specific claims in the literature that lack independent verification. Flags reproducibility concerns. |
| **paper-writing** | Lightweight survey. Quick identification of the 10-15 most relevant references. Focuses on positioning the project within the existing literature rather than exhaustive coverage.            |

### gpd-research-synthesizer

| Profile           | Behavioral Change                                                                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Maximum detail in synthesis. Preserves all mathematical subtleties, convention choices, and proof structures. Synthesis document is a complete technical reference, not a summary.                   |
| **numerical**     | Results-focused synthesis. Emphasizes numerical values, convergence data, error budgets. Organizes by computed quantity rather than by research phase. Tables and figures over prose.                |
| **exploratory**   | High-level synthesis. Distills findings into key insights and open questions. Drops technical detail in favor of conceptual clarity. Highlights the most promising directions for further work.      |
| **review**        | Verification-chain synthesis. Organizes results by what has been verified, how it was verified, and what remains unverified. Maps the chain of logical dependencies between results.                |
| **paper-writing** | Narrative synthesis. Organizes findings into a story arc suitable for a paper. Identifies the main result, supporting results, and context. Drafts section-level outlines alongside the synthesis. |

### gpd-literature-reviewer

| Profile           | Behavioral Change                                                                                                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Full citation depth. Traces citation networks back to seminal papers. Reads and summarizes key derivations from primary sources. Identifies where different groups disagree and why.                        |
| **numerical**     | Benchmark-focused review. Prioritizes papers that provide numerical benchmarks, validation data, or code. Catalogs published values with uncertainties for comparison. Identifies reproducibility status.   |
| **exploratory**   | Broad survey. Covers more papers at lower depth. Focuses on identifying the landscape of approaches rather than deeply understanding any single one. Produces a categorized bibliography.                   |
| **review**        | Critical review. Evaluates the strength of evidence for each claim in the literature. Identifies papers with weak methodology, unchecked assumptions, or results that have not been independently reproduced. |
| **paper-writing** | Citation-completeness review. Ensures all relevant prior work is identified for proper attribution. Focuses on what must be cited vs what is useful context. Identifies the key 5-10 references to discuss in detail. |

### gpd-bibliographer

| Profile           | Behavioral Change                                                                                                                                                                      |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Maximum verification. Cross-checks every citation against INSPIRE-HEP and ADS. Verifies that equations attributed to a reference actually appear in that reference. Flags misattributions. |
| **numerical**     | Standard verification. Resolves citation keys, verifies DOIs exist, checks journal references are correctly formatted. Moderate depth — focuses on getting references right, not exhaustive. |
| **exploratory**   | Lightweight mode. Resolves citation keys and checks basic formatting. Does not deeply verify that cited results match the reference content. Quick turnaround over thoroughness.         |
| **review**        | Audit-grade verification. Checks every citation for correctness, verifies page numbers and volume numbers, flags retracted papers. Warns about any reference that cannot be verified.   |
| **paper-writing** | Publication-ready verification. Full formatting check against target journal style (APS, JHEP, etc.). Ensures BibTeX entries are complete. Adds missing fields (DOI, eprint, pages). Alphabetizes and deduplicates. |

### gpd-explainer

| Profile           | Behavioral Change                                                                                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Formal-first explanations. Expands derivational steps, states assumptions precisely, and connects the concept to exact results, controlled limits, and canonical primary sources.                         |
| **numerical**     | Workflow-first explanations. Emphasizes how the concept affects implementation choices, convergence behavior, diagnostics, and which equations matter in code or simulation practice.                      |
| **exploratory**   | Breadth-first explanations. Prioritizes intuition, method landscape, and when different interpretations of the concept matter, while still grounding the answer in a compact reading path.                  |
| **review**        | Audit-style explanations. Distinguishes established facts, project assumptions, and contested interpretations explicitly. Extra attention to notation drift, caveats, and citation reliability.             |
| **paper-writing** | Reader-facing explanations. Optimizes for clean structure, narrative flow, and references the user can open immediately. Useful when turning a concept into manuscript-ready exposition or background text. |

### gpd-referee

| Profile           | Behavioral Change                                                                                                                                                                                             |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Maximally strict. Demands rigorous proof for every claim. Flags hand-waving arguments, unjustified approximations, and implicit assumptions. Applies the standard of a mathematical physics journal.          |
| **numerical**     | Convergence-focused review. Demands convergence data for every numerical result. Requires error bars and uncertainty quantification. Checks whether numerical methods are appropriate for the problem.         |
| **exploratory**   | Constructive review. Focuses on whether the exploration covered sufficient ground and identified the most promising directions. Lenient on individual result rigor; strict on coverage and intellectual honesty. |
| **review**        | Standard peer review. Balanced assessment of novelty, correctness, and significance. Checks reproducibility of key results. Evaluates whether conclusions are supported by the evidence presented.            |
| **paper-writing** | Publication-readiness review. Evaluates clarity, logical flow, figure quality, and notation consistency alongside physics content. Applies the standards of the target journal.                                |

### gpd-paper-writer

| Profile           | Behavioral Change                                                                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **deep-theory**   | Precision writing. Every equation is derived in full, no steps skipped. Mathematical notation is formally precise. Proofs are included in the main text rather than appendices. Prioritizes rigor over readability. |
| **numerical**     | Data-driven writing. Emphasizes tables, figures, and convergence plots. Computational methodology section is detailed. Results section organized by computed quantity. Includes supplemental data descriptions. |
| **exploratory**   | Rapid drafting. Produces a complete first draft quickly, accepting rough prose that can be polished later. Prioritizes getting the structure and key results on paper over perfect wording.               |
| **review**        | Standard quality writing. Balanced depth and readability. Clear methodology, well-organized results, measured conclusions. Follows conventions of the target journal.                                    |
| **paper-writing** | Maximum narrative quality. Careful attention to logical flow, transitions between sections, and the story arc of the paper. Multiple revision passes on prose. Reader-focused: every paragraph earns its place. |

### gpd-consistency-checker

| Profile           | Behavioral Change                                                                                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **deep-theory**   | Full consistency audit. Checks all conventions (metric, Fourier, normalization) across every phase. Substitutes test values into every equation to verify numerical agreement between phases. Zero tolerance for ambiguity. |
| **numerical**     | Numerical consistency focus. Verifies that numerical values computed in one phase are used correctly in subsequent phases. Checks unit conversions, parameter passing, and data format consistency. Validates that convergence criteria are consistent. |
| **exploratory**   | Lightweight consistency check. Verifies that conventions are declared and not contradictory. Checks that key parameters have consistent values across phases. Flags potential issues without deep investigation. |
| **review**        | Cross-reference consistency. Verifies every result cited from a prior phase matches the actual output of that phase. Checks provides/consumes chains. Identifies any result that is used but never validated. |
| **paper-writing** | Notation consistency. Verifies that all symbols in the paper are defined, used consistently, and match the computation files. Checks that equations in the text match derivation outputs. Flags notation drift. |

### Choosing a Profile

When selecting a profile, consider not just the token cost tradeoff (shown in the tier tables above) but also these behavioral differences. For example:

- A **deep-theory** project gets the most exhaustive debugging and plan checking, appropriate for formal derivations where a single sign error invalidates everything.
- A **numerical** project gets debugging tuned toward convergence and precision issues, and plan checking that prioritizes computational feasibility.
- An **exploratory** project trades depth for speed at every stage -- quick triage debugging and streamlined plan checks -- so you can iterate faster across many hypotheses.
- A **review** project maximizes documentation and cross-referencing, making it ideal for reproducing literature results or preparing work for peer review.

## Resolution Logic

Orchestrators resolve tier and optional concrete model before spawning:

```
1. Read .gpd/config.json
2. Get model_profile (default: "review")
3. Look up agent in table above
4. Resolve tier via `gpd resolve-tier`
5. Resolve runtime override via `gpd resolve-model`
6. Omit `model` when `gpd resolve-model` returns empty
```

## Switching Profiles

Runtime: `/gpd:set-profile <profile>`

Per-project default: Set in `.gpd/config.json`:

```json
{
  "model_profile": "review"
}
```

## Design Rationale

**Why tier-1 for gpd-planner across all profiles?**
Planning involves decomposing a physics problem into sub-problems, choosing approximation schemes, and designing the research strategy. This is where model quality has the highest impact regardless of the type of work.

**Why tier-1 for gpd-executor in deep-theory?**
Formal derivations require the executor to carry out multi-step mathematical reasoning. Unlike software execution where the plan contains most of the thinking, theoretical physics execution IS the thinking.

**Why tier-1 for gpd-verifier in numerical and review?**
Verification in physics requires checking dimensional consistency, limiting cases, conservation laws, and convergence behavior. These are reasoning-intensive tasks where tier-3 or even tier-2 may miss subtle errors (e.g., a sign error in a commutator, an off-by-one in an index contraction).

**Why tier-1 for gpd-research-synthesizer in paper-writing?**
Synthesizing research into a coherent narrative requires understanding which results are important, how they connect, and what story they tell. This is high-level reasoning about physics, not just summarization.

**Why tier-3 for gpd-research-mapper?**
Read-only exploration of project artifacts (simulation configs, data files, existing notebooks). No heavy physics derivation required, just structured output from file contents.

**Why tier-1 for gpd-paper-writer in deep-theory and paper-writing?**
Writing physics papers requires understanding the narrative arc, choosing which intermediate steps to include, and presenting results clearly. In deep-theory mode, mathematical exposition must be precise. In paper-writing mode, narrative quality is paramount.

**Why tier-1 for gpd-literature-reviewer in exploratory?**
Exploratory literature reviews require creative search strategies, recognizing connections between subfields, and assessing the reliability of competing claims. This is reasoning-intensive work.
