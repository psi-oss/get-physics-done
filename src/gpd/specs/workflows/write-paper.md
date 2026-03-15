<purpose>
Structure and write a physics paper from completed research results. Handles the full pipeline from outline through polished draft: section planning, equation presentation, figure integration, narrative flow, and internal consistency verification.

Called from /gpd:write-paper command. Sections are drafted by gpd-paper-writer agents.
</purpose>

<core_principle>
A physics paper has a narrative arc. It is not a report of everything that was done -- it is a carefully constructed argument that poses a question, develops the tools to answer it, presents the answer with evidence, and explains why the answer matters. Every equation, figure, and paragraph must advance this argument. Anything that doesn't is cut or moved to an appendix.

**The narrative arc:**

1. **Motivation** -- Why should the reader care about this problem?
2. **Setup** -- What are the ingredients (model, formalism, parameters)?
3. **Development** -- How do we get from setup to result?
4. **Result** -- What is the answer, with evidence?
5. **Significance** -- What does the answer mean for the field?
   </core_principle>

<journal_formats>

### Physical Review Letters (PRL)

- **Length:** 4 pages (3750 words including references)
- **Style:** Impact-focused. The first paragraph must hook the reader. No leisurely introduction.
- **Equations:** Only the essential ones. Derivations go to Supplemental Material.
- **Figures:** Maximum 4 (including insets). Each must be publication quality.
- **References:** ~30-40 citations maximum.

### Physical Review (PRD/PRB/PRA/PRE)

- **Length:** Full-length (8-15 pages typical)
- **Style:** Detailed and complete. Sufficient for a reader to reproduce the work.
- **Equations:** Include all essential steps. Move lengthy algebra to appendices.
- **Figures:** As many as needed. Must be referenced in text.
- **References:** Comprehensive.

### Reviews of Modern Physics (RMP)

- **Length:** 30-80+ pages
- **Style:** Pedagogical review. Should be accessible to non-specialists in the subfield.
- **Equations:** Include derivations of key results. Pedagogical clarity over brevity.
- **References:** Exhaustive.

### arXiv Preprint

- **Length:** Flexible
- **Style:** Vary from PRL-like to full detail
- **Priority:** Establishing priority and getting community feedback
  </journal_formats>

<process>

<step name="init" priority="first">
**Load project context and resolve models:**

```bash
INIT=$(gpd init phase-op)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `project_contract`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`.

**Load mode settings:**

```bash
AUTONOMY=$(gpd --raw config get autonomy 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
RESEARCH_MODE=$(gpd --raw config get research_mode 2>/dev/null | gpd json get .value --default balanced 2>/dev/null || echo "balanced")
```

Mode effects on the write-paper pipeline:
- **Explore mode**: Paper structured as a comparison/survey; broader literature review; more figures; comprehensive related-work section
- **Exploit mode**: Paper structured as a focused result; streamlined introduction; minimal related-work; optimized for tight prose
- **Supervised autonomy**: Checkpoints after the outline, after each section draft, and before referee review.
- **Balanced autonomy**: Auto-generate the outline from the research digest, draft all sections, and pause only for claim-level decisions, major structural changes, or referee conflicts.
- **YOLO autonomy**: Draft all sections, run referee, and present the final result with only hard-stop interruptions.

For detailed mode adaptation specifications (bibliographer search breadth, referee strictness, paper-writer style by mode), see `{GPD_INSTALL_DIR}/references/publication/publication-pipeline-modes.md`.

Run centralized context preflight before continuing:

```bash
CONTEXT=$(gpd --raw validate command-context write-paper "$ARGUMENTS")
if [ $? -ne 0 ]; then
  echo "$CONTEXT"
  exit 1
fi
```

Run the centralized review preflight before continuing:

```bash
gpd validate review-preflight write-paper --strict
```

If review preflight exits nonzero because of missing project state, missing roadmap, missing manuscript, degraded review integrity, missing research artifacts, or non-review-ready reproducibility coverage, STOP and show the blocking issues before drafting.

**Locate paper directory (if resuming):**

```bash
for DIR in paper manuscript draft; do
  if [ -f "${DIR}/main.tex" ]; then
    PAPER_DIR="$DIR"
    break
  fi
done
```

If `PAPER_DIR` is set, the workflow is resuming or revising an existing paper. Otherwise, a new `paper/` directory will be created in `generate_files`.

**Check pdflatex availability:**

```bash
command -v pdflatex >/dev/null 2>&1 && PDFLATEX_AVAILABLE=true || PDFLATEX_AVAILABLE=false
```

If `PDFLATEX_AVAILABLE` is false, display a warning:

```
⚠ pdflatex not found. LaTeX compilation checks will be skipped.
  Install TeX Live or MacTeX for compilation verification during drafting.
  The paper .tex files will still be generated correctly.
```

The workflow continues without compilation checks — .tex file generation does not require pdflatex.

**Convention verification** — papers must use consistent conventions throughout:

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — review before writing paper"
  echo "$CONV_CHECK"
fi
```

If conventions are locked, all equations in the paper must follow them. Convention mismatches between research phases and the paper are a common source of sign errors and missing factors.

</step>

<step name="load_specialized_publication_context">
Use `protocol_bundle_context` from init JSON as additive specialized-publication guidance.

- If `selected_protocol_bundle_ids` is non-empty, keep the bundle's decisive artifact guidance, estimator caveats, and reference prompts visible while choosing main-text figures, appendices, and related-work framing.
- Use bundle guidance to check whether the manuscript surfaces the right decisive comparisons, benchmark anchors, and estimator limitations for this project.
- Do **not** let bundle guidance invent new claims, replace `project_contract`, or override `contract_results`, `comparison_verdicts`, `.gpd/comparisons/*-COMPARISON.md`, `.gpd/paper/FIGURE_TRACKER.md`, or `active_reference_context`. Those remain authoritative.
- If no bundle is selected, rely on shared publication guidance plus the contract-backed comparison artifacts already present in the project.

</step>

<step name="load_research_digest">

Check for research digests generated during milestone completion. These digests are the primary structured handoff from the research phase and should drive paper organization.

**Step 1 -- Locate digest files:**

```bash
ls .gpd/milestones/*/RESEARCH-DIGEST.md 2>/dev/null
```

**If digest(s) found:**

Read all available digests:

```bash
cat .gpd/milestones/*/RESEARCH-DIGEST.md
```

**Step 2 -- Map digest sections to paper structure:**

The research digest provides a direct scaffolding for paper organization:

- **Narrative Arc** -> Paper's logical flow. The narrative arc paragraph describes the research story from first question to final result. Use this as the backbone for the Introduction's argument and the overall section ordering. If the narrative naturally follows "we asked X, developed method Y, found Z," the paper sections should mirror that progression.

- **Key Results table** -> Results section content. Each row in the key results table is a candidate for inclusion in the Results section. The equations/values, validity ranges, and confidence levels determine what gets presented as primary results vs. supporting evidence vs. appendix material.

- **Methods Employed** -> Methods section. The phase-ordered methods list defines the tools developed or applied. Methods introduced early that underpin later results are the core of the Methods section. Methods used only in one phase may be relegated to a subsection or appendix.

- **Convention Evolution** -> Notation consistency. The final active conventions from the convention timeline define the notation for the entire paper. Any superseded conventions must NOT appear in the manuscript. Build the paper's symbol table from the "Active" entries only.

- **Figures and Data Registry** -> Figure planning. Figures marked "Paper-ready? Yes" are immediate candidates for the paper. Others may need regeneration. Use the registry to plan the figure sequence and identify gaps that need new figures.

- **Open Questions** -> Discussion / Future Work. These feed directly into the Discussion section's "outlook" paragraphs or a dedicated Future Work subsection.

- **Dependency Graph** -> Derivation ordering. The provides/requires graph shows which results depend on which. This determines the logical ordering of the Methods and Results sections -- a result that requires another result must come after it.

- **Mapping to Original Objectives** -> Introduction framing. The requirements mapping shows which research goals were achieved. This helps frame the Introduction's promise ("In this paper, we...") and the Conclusions' delivery ("We have shown...").

**Step 3 -- Identify digest gaps:**

If the digest is incomplete or missing sections, note which paper sections will need to be built from raw phase data instead:

```bash
# Fall back to raw sources if digest is insufficient
cat .gpd/phases/*-*/*-SUMMARY.md
cat .gpd/state.json
```

**If NO digest found:**

Display a clear warning explaining why and offering alternatives:

```
⚠ No RESEARCH-DIGEST.md found in .gpd/milestones/.

Research digests are generated during /gpd:complete-milestone. Without a digest,
the paper will be built from raw phase data (SUMMARY.md files, STATE.md, state.json).
This works but produces a less structured starting point — the digest provides
a curated narrative arc, convention timeline, and figure registry.

Options:
  1. Continue anyway — build paper from raw phase data (proceed below)
  2. Run /gpd:complete-milestone first — generates the digest, then return here
  3. Use --from-phases to explicitly select which phases to include:
     /gpd:write-paper --from-phases 1,2,3,5
```

**If `--from-phases` flag is present:** Read SUMMARY.md and research artifacts only from the specified phase directories. Skip milestone digest lookup entirely. This is useful for writing papers that cover a subset of phases or when milestones haven't been completed yet.

```bash
# Example: --from-phases 1,3,5
for PHASE_NUM in $(echo "$FROM_PHASES" | tr ',' ' '); do
  PHASE_DIR=$(ls -d .gpd/phases/*/ | grep "^.gpd/phases/0*${PHASE_NUM}-")
  cat "$PHASE_DIR"/*-SUMMARY.md 2>/dev/null
done
```

Proceed to establish_scope and catalog_artifacts, which will gather research context from raw phase data, SUMMARY.md files, and state.json directly.

</step>

<step name="establish_scope">
From command context, determine:
- Target journal and formatting requirements
- Paper type (new result, new method, comparison, review)
- The ONE key result (if it can't be stated in one sentence, the paper isn't focused enough)
- Target audience (specialists, broader physics, interdisciplinary)
- Available research artifacts (derivations, data, figures)

If a research digest was loaded, the key result is typically the highest-confidence entry in the Key Results table. The narrative arc paragraph often contains the one-sentence key result in condensed form.

The key result drives everything. Every section exists to support, contextualize, or explain this result.
</step>

<step name="catalog_artifacts">
Gather all research outputs that could contribute to the paper:

1. **Derivations** -- LaTeX, Python scripts, Mathematica notebooks

   - Which results are ready for publication?
   - Which need polishing or additional steps?

2. **Numerical results** -- Data files, convergence tests, benchmarks

   - Which results are converged and reliable?
   - What error bars / uncertainties are established?

3. **Figures** -- Existing plots, phase diagrams, schematics

   - Which are publication quality?
   - Which need to be generated or improved?

4. **Literature context** -- From `.gpd/literature/*-REVIEW.md` or phase `RESEARCH.md`

   - What is the relevant prior work to cite?
   - How does our result compare with published values?

5. **Verification results** -- From VERIFICATION.md
   - Which limiting cases were checked?
   - What is the confidence level of each result?

6. **Internal comparisons and decisive evidence** -- From `.gpd/comparisons/*-COMPARISON.md`, `FIGURE_TRACKER.md`, and bundle context

   - Which comparisons carry decisive `comparison_verdicts` for the paper's core claims?
   - Which decisive comparisons are actually needed for the claims the manuscript intends to make, and which checks are merely supportive?
   - Which figures or tables are benchmark-anchored versus only supportive?
   - If protocol bundles are selected, do their decisive-artifact expectations match what the manuscript plans to surface?

Map each artifact to the section where it will appear.
</step>

<step name="paper_readiness_audit">
## Paper-Readiness Audit

Before committing to an outline, verify the research is publication-ready. This pre-flight gate catches gaps that would block or undermine the paper.

Run checks across all contributing phases (from digest, `--from-phases`, or all completed phases):

```bash
# Identify contributing phases
if [ -n "$FROM_PHASES" ]; then
  PHASE_DIRS=$(for n in $(echo "$FROM_PHASES" | tr ',' ' '); do ls -d .gpd/phases/0*${n}-* 2>/dev/null; done)
else
  PHASE_DIRS=$(ls -d .gpd/phases/*/ 2>/dev/null)
fi
```

### Check 1: SUMMARY.md completeness

Every contributing phase must have a SUMMARY.md that tells the paper what user-visible result it contributes. For contract-backed phases, `contract_results` and any decisive `comparison_verdicts` are the readiness anchors; generic `verification_status` / `confidence` tags are optional hints, not gates.

For each phase directory:

1. Verify SUMMARY.md exists
2. If the phase is contract-backed and supports a paper claim, check for `plan_contract_ref` and `contract_results`
3. If a contract-backed target depends on a decisive comparison, check for the corresponding `comparison_verdicts` entry and an evidence path the manuscript can surface
4. Confirm the summary or verification artifacts identify where the substantive evidence lives

**Missing SUMMARY.md** → CRITICAL gap (phase results not summarized).
**Contract-backed phase missing `contract_results` for a paper-relevant target** → CRITICAL gap.
**Decisive comparison required by the contract but no verdict/evidence path is surfaced** → CRITICAL gap.
**Missing generic `verification_status` / `confidence` tags alone are not blockers.**

### Check 2: Convention consistency

Read the convention declarations from each phase's SUMMARY.md or derivation files and compare:

1. Metric signature — must be identical across all phases
2. Fourier convention — must be identical across all phases
3. Unit system — must be identical (or conversions documented)

Also check `convention_lock` in STATE.md or state.json. If a convention lock exists, verify all phases comply.

**Convention mismatch between phases** → CRITICAL gap (combining results with different conventions produces wrong answers).

### Check 3: Numerical value stability

For each key result listed in the research digest (or `intermediate_results` in state.json):

1. Locate the value in its source phase SUMMARY.md
2. Compare with any cross-references in other phases
3. Flag values that appear in multiple places with different magnitudes

**Values differ by more than stated uncertainty** → CRITICAL gap.
**Values lack uncertainty estimates** → WARNING.

### Check 4: Figure readiness

Check whether planned figures have source data and generation scripts:

```bash
# Check durable figure roots, not internal phase scratch paths
find artifacts/phases figures paper/figures -maxdepth 3 \( -type f -o -type d \) 2>/dev/null
ls .gpd/paper/FIGURE_TRACKER.md 2>/dev/null
```

For each figure referenced in the research digest or artifact catalog:

1. Does the source data file exist?
2. Does a generation script exist (`.py`, `.m`, `.nb`)?
3. Has the script been run (output file exists)?

**Source data missing** → CRITICAL gap.
**Script missing but data exists** → WARNING (script can be written during `generate_figures`).
**Script exists but not run** → INFO (will be run during `generate_figures`).

### Check 5: Citation readiness

Check for bibliography infrastructure:

```bash
ls references/references.bib 2>/dev/null
ls paper/references.bib 2>/dev/null
ls .gpd/literature/*-REVIEW.md 2>/dev/null
```

1. Does a project bibliography exist (`references/references.bib` or `paper/references.bib`)?
2. Does at least one `.gpd/literature/*-REVIEW.md` or phase `RESEARCH.md` exist?
3. Are key prior works identified (the research digest's "Prior Work" or literature review)?

**No bibliography file and no literature review** → WARNING (citations will need to be built from scratch).

### Check 6: Decisive comparison continuity

Check that the manuscript can surface the decisive evidence, not just supporting narrative:

1. Read `.gpd/comparisons/*-COMPARISON.md` and note every decisive `comparison_verdicts` entry
2. Read `.gpd/paper/FIGURE_TRACKER.md` and confirm those decisive claims have a planned figure, table, or explicit textual comparison path
3. If `selected_protocol_bundle_ids` is non-empty, use `protocol_bundle_context` only as an additive expectation map for which anchors, estimator caveats, or benchmark comparisons should stay visible in the paper
4. Only require the manuscript to surface decisive comparisons for claims it actually makes. Honest narrowing is acceptable; silent omission is not.

**Decisive comparison missing for a central claim** → CRITICAL gap.
**Bundle guidance suggests a decisive comparison that is absent, but the manuscript narrows the claim honestly** → WARNING, not blocker.

### Audit Report

Present results as a readiness report:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 GPD > PAPER-READINESS AUDIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Phases audited: {N}

	  Check                     Status    Issues
	  ─────────────────────────────────────────────
	  SUMMARY completeness      {P/F}     {details}
	  Convention consistency     {P/F}     {details}
	  Numerical stability        {P/F}     {details}
	  Figure readiness           {P/F}     {details}
	  Citation readiness         {P/F}     {details}
	  Decisive comparisons       {P/F}     {details}

  CRITICAL gaps: {count}
  Warnings:      {count}
```

### Gate Decision

- **0 CRITICAL gaps:** Proceed to `create_outline`.
- **1+ CRITICAL gaps:** Present the gaps and offer options:

```
Paper-readiness audit found {N} critical gap(s):

{numbered list of critical gaps with phase and description}

Options:
  1. Fix gaps first — return to research phases to address critical issues
  2. Proceed anyway — acknowledge gaps as known limitations in the paper
  3. Exclude problematic phases — re-scope paper with --from-phases to skip incomplete phases
```

Wait for user decision before proceeding. Do NOT silently continue past critical gaps.

</step>

<step name="create_outline">
Generate a detailed outline tailored to the journal format.

For each section:

- **Purpose:** What this section accomplishes in the narrative
- **Key content:** Bullet list of main points (3-7 per section)
- **Equations:** Specific equations to include (by reference to derivation files)
- **Figures:** Specific figures to include (by file path)
- **Citations:** Key references to cite
- **Length estimate:** In paragraphs or words
- **Dependencies:** What must be established before this section

The outline must satisfy:

1. A reader of only the Introduction understands what was done and why
2. A reader of only the Results gets the key finding with evidence
3. A reader of Abstract + Conclusions gets the full story in miniature
4. The Discussion adds value beyond repeating Results (interpretation, implications, connections)

Present outline for approval before proceeding.
</step>

<step name="generate_files">
Create the paper directory structure:

```
paper/
+-- main.tex              # Master document with \input commands
+-- abstract.tex
+-- introduction.tex
+-- model.tex             # or setup.tex
+-- methods.tex           # or derivation.tex
+-- results.tex
+-- discussion.tex
+-- conclusions.tex
+-- appendix_A.tex        # if needed
+-- appendix_B.tex        # if needed
+-- references.bib        # BibTeX entries
+-- figures/              # All figure files
+-- Makefile              # Build: pdflatex + bibtex
```

The main.tex should:

- Use the target journal's document class
- Define all custom macros in a preamble block (see `{GPD_INSTALL_DIR}/templates/latex-preamble.md` for standard packages, project-specific macros, equation labeling conventions, and SymPy-to-LaTeX integration)
- \input each section file
- Handle bibliography correctly for the journal

If the project has a `.gpd/analysis/LATEX_PREAMBLE.md`, use its macros to ensure notation consistency with the research phases.

If a machine-readable paper spec is available, prefer the canonical builder:

```bash
gpd paper-build paper/PAPER-CONFIG.json
```

This emits `paper/main.tex`, writes the artifact manifest, and keeps the manuscript scaffold aligned with the tested `gpd.mcp.paper` package. If no JSON spec exists yet, create `paper/PAPER-CONFIG.json` first using `{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md` as the schema source of truth, and then run `gpd paper-build` before proceeding. The compilation checks in `draft_sections` require `main.tex` to exist.

When authoring `paper/PAPER-CONFIG.json`:

- use the exact top-level fields from `{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md`
- keep `authors`, `sections`, `figures`, and `appendix_sections` as JSON arrays
- keep `journal` to a supported builder key like `prl`, `apj`, `mnras`, `nature`, `jhep`, or `jfm`
- do not invent extra keys just because a journal asks for extra prose; put that prose in the section content instead

**Supplemental material:** If the paper requires supplemental material (common for PRL and other letter-format journals), use `{GPD_INSTALL_DIR}/templates/paper/supplemental-material.md` for the standard structure (extended derivations, computational details, additional figures, data tables, code availability).

**Experimental comparison:** If the paper compares theoretical predictions with experimental or observational data, use `{GPD_INSTALL_DIR}/templates/paper/experimental-comparison.md` for the systematic comparison structure (data source metadata, unit conversion checklist, pull analysis, chi-squared statistics, discrepancy classification with root cause hierarchy).
</step>

<step name="generate_figures">
## Figure Generation

Ensure the paper directory structure exists before writing any files:

```bash
mkdir -p paper/figures
```

Before drafting sections, generate all planned figures:

1. Read `.gpd/paper/FIGURE_TRACKER.md` for figure specifications
2. For each figure with status != "Final":
   a. Locate source data (from phase directories)
   b. Generate matplotlib script with publication styling:
      - Use shared style: `plt.style.use('paper/paper.mplstyle')` if exists, otherwise use sensible defaults
      - Font size 10pt, axes labels with units, legend
      - Error bars where applicable, colorblind-safe colors
   c. Execute script, save to `paper/figures/`
   d. Update FIGURE_TRACKER.md status
3. Verify all figures referenced in outline exist as files

**If figure data is missing:** Flag as blocker, suggest which phase needs re-execution.
</step>

<step name="draft_sections">
Resolve paper-writer model:

```bash
WRITER_MODEL=$(gpd resolve-model gpd-paper-writer)
```

Spawn gpd-paper-writer agents for section drafting.

**Section drafting order (with parallelization):**

<!-- Results and Methods have no dependency on each other -- spawn in parallel.
     Introduction depends on Results (for framing). Discussion depends on both.
     Conclusions and Abstract are sequential. Appendices can parallel with Abstract. -->

1. **Wave 1 (parallel):** Results + Methods -- no dependency between them
2. **Wave 2:** Introduction -- depends on Results for framing the narrative
3. **Wave 3:** Discussion -- depends on Results + Methods for interpretation
4. **Wave 4:** Conclusions -- summarizes all preceding sections
5. **Wave 5:** Abstract -- distill everything into 150-300 words (write LAST)
6. **Wave 6:** Appendices -- technical details moved from main text

**LaTeX compilation check after each wave (if pdflatex available):**

Skip this check if `PDFLATEX_AVAILABLE` is false (set in init step).

After each drafting wave completes, verify the document compiles:

```bash
cd paper/
pdflatex -interaction=nonstopmode main.tex 2>&1 | tail -20
```

**If compilation errors:**
1. Parse the log for the first error: `grep -A 3 "^!" main.log | head -10`
2. Feed the error back to the paper-writer for the affected section
3. Common LLM LaTeX errors: unmatched braces, undefined commands, incorrect environment nesting
4. Fix and re-compile before proceeding to the next wave

**If compilation succeeds:** Proceed to next wave. Run bibtex after the bibliography wave.

This prevents error accumulation across waves.

**Per-wave checkpointing and failure recovery:**

Before spawning each wave, check if the target .tex files already exist on disk. If they do, skip that wave and move to the next. On re-invocation, the workflow detects already-written sections and resumes from the first incomplete wave.

```bash
# Example: check Wave 1 outputs before spawning
if [ -f "paper/results.tex" ] && [ -f "paper/methods.tex" ]; then
  echo "Wave 1 outputs exist -- skipping to Wave 2"
else
  # Spawn Wave 1 agents
fi
```

Apply this pattern to each wave: check for the expected .tex output files before spawning writer agents.

**For each section, spawn a writer agent:**
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\n" + section_prompt,
  subagent_type="gpd-paper-writer",
  model="{writer_model}",
  readonly=false,
  description="Draft: {section_name}"
)
```

**If a writer agent fails to spawn or returns an error:** Check if the expected .tex file was written to `paper/` (agents write files first). If the file exists, proceed to the next section. If not, offer: 1) Retry the failed section, 2) Draft the section in the main context using the section brief, 3) Skip the section and continue with remaining waves. Do not block the entire paper on a single section failure — other sections can still be drafted in parallel.

**Each writer agent receives:**

- Paper context (title, journal, key result, audience)
- Section brief (purpose, content, equations, figures, citations)
- Narrative continuity (how preceding section ends, what following section needs)
- Research artifacts (file paths to read for content)
- Active decisive-comparison artifacts (`.gpd/comparisons/*-COMPARISON.md`) and relevant `FIGURE_TRACKER.md` entries for any contract-critical figure or table
- `protocol_bundle_context` and `selected_protocol_bundle_ids` as additive specialized guidance only; they help decide which decisive anchors, estimator caveats, and benchmark comparisons must stay visible, but they do not replace the contract-backed evidence ledger
- Writing principles (see command file)

**What makes good physics writing:**

- **Opening sentence of each section** hooks the reader. Not "In this section we..." but a statement that advances the physics.
- **Transitions between sections** are smooth. The end of Sec. III naturally leads to the beginning of Sec. IV.
- **Equations are introduced in words** before they appear. "The partition function is..." not "We have: Z = ..."
- **Results are interpreted immediately.** Don't present a table of numbers and then explain it three paragraphs later.
- **Figures are discussed in the text.** "As shown in Fig. 3, the order parameter vanishes..." not "See Fig. 3."
- **Technical jargon is defined.** Even for specialists, define non-standard terms and abbreviations at first use.
  </step>

<step name="equation_presentation">
Equations in a published paper must be:

1. **Numbered if referenced** (Eq. (1), (2), ...). Unnumbered if not referenced.
2. **Defined completely** -- Every symbol defined at first appearance
3. **Dimensionally consistent** -- Author has verified dimensions
4. **Typeset correctly** -- LaTeX best practices:

   - `\left( \right)` for auto-sizing delimiters
   - `\mathrm{d}` for differential d (upright, not italic)
   - `\text{...}` for words within equations
   - `\boldsymbol{}` for vector/tensor quantities (or `\vec{}` if journal prefers)
   - Consistent use of `\cdot` vs `\times` for products

5. **Contextualized** -- Each equation has text before (setup) and after (interpretation)

**Bad:** "From the Lagrangian we get" [equation] "which we use below."
**Good:** "Varying the action with respect to phi yields the equation of motion" [equation] "This is a nonlinear Klein-Gordon equation, with the potential V'(phi) acting as an effective mass that depends on the field value."
</step>

<step name="figure_preparation">
Each figure must:

1. **Make exactly one point.** If a figure makes two points, split it into two panels.
2. **Be self-contained.** The caption should allow understanding without reading the text.
3. **Have labeled axes with units.** Always.
4. **Include error bars** where uncertainties exist. If no error bars, state why.
5. **Use consistent notation.** Same symbols in figures as in text.
6. **Be readable in grayscale** (many readers print in black and white).
7. **Use vector formats** (PDF, EPS) for line plots, raster (PNG, 300+ dpi) only for images/heatmaps.

**Caption format:**

```latex
\begin{figure}
  \includegraphics[width=\columnwidth]{figures/fig_energy.pdf}
  \caption{Ground-state energy $E_0$ as a function of coupling $g$ for $N = 100$ sites.
  Solid line: exact diagonalization. Dashed line: mean-field theory.
  Error bars are smaller than symbol size for all data points.
  Inset: relative difference between ED and MFT, showing $O(1/N)$ corrections.}
  \label{fig:energy}
\end{figure}
```

</step>

<step name="consistency_check">
After all sections are drafted, verify internal consistency:

**Notation audit:**

- Build a symbol table: every symbol -> definition -> first appearance
- Check that the same symbol is never used for two different quantities
- Check that the same quantity is never denoted by two different symbols
- Verify Greek vs Latin index conventions are consistent

**Cross-reference audit:**

- Every \ref{} has a corresponding \label{}
- Every \cite{} has a corresponding bibliography entry
- Every equation referenced in text exists
- Every figure referenced in text exists
- Section numbers match actual section ordering

**Placeholder resolution:**

Scan all .tex files for `RESULT PENDING` markers left by the paper-writer:

```bash
grep -rn "RESULT PENDING" paper/*.tex
```

For each `% [RESULT PENDING: phase N, task M -- description]`:

1. Read the referenced phase's SUMMARY.md for the completed result
2. If the result is available: replace `\text{[PENDING]}` with the actual value and remove the `% [RESULT PENDING: ...]` comment
3. If the result is still unavailable: flag as a blocker — the paper cannot be finalized with pending placeholders

**GATE: All RESULT PENDING markers must be resolved before proceeding to verify_references.**

```bash
PENDING_COUNT=$(grep -rcE "RESULT PENDING|\\\\text\{\\[PENDING\\]\}" paper/*.tex 2>/dev/null || echo 0)
```

If `PENDING_COUNT > 0`:

```
ERROR: ${PENDING_COUNT} unresolved RESULT PENDING marker(s) found.
A paper with placeholder values is not submission-ready.

Unresolved markers:
$(grep -rn "RESULT PENDING" paper/*.tex 2>/dev/null)

Options:
  1. Resolve markers from phase SUMMARYs (attempt auto-fill)
  2. Return to research phases to complete missing results
  3. List all pending markers for manual resolution

HALTING — do NOT proceed to verify_references until all markers are resolved.
```

Do NOT proceed to the `verify_references` step. This is a hard gate.

**Physics consistency:**

- Results in Abstract match results in Results section (same values, same error bars)
- Conclusions don't claim more than the Results support
- Approximations stated in Methods are consistent with those used in Results
- Units are consistent throughout (no mixing natural and SI without conversion)
- Conventions stated in Setup are used consistently everywhere

**Narrative flow:**

- Introduction poses the question that Results answers
- Methods section develops exactly the tools needed for Results (no more, no less)
- Discussion interprets Results, doesn't repeat them
- Conclusions don't introduce new results
- Each section ends in a way that motivates the next section
  </step>

<step name="notation_audit">
## Notation Consistency Audit

After all sections are drafted, run a systematic notation check:

**Check for notation glossary:**

```bash
ls .gpd/NOTATION_GLOSSARY.md 2>/dev/null
```

If NOTATION_GLOSSARY.md does not exist, skip step 2 below and note in the report that no glossary was available for cross-referencing. The consistency checks (steps 1, 3, 4) still run — they compare the paper against itself.

1. **Extract symbols:** Scan all .tex files for math-mode content. List every unique symbol.
2. **Cross-reference against NOTATION_GLOSSARY.md** (if exists): For each symbol:
   - Defined in glossary? -> OK
   - Not defined? -> Flag as "undefined symbol"
   - Multiple definitions? -> Flag as "notation conflict"
3. **Check consistency:**
   - Same quantity denoted by different symbols in different sections?
   - Same symbol used for different quantities?
   - Inconsistent formatting (H vs \hat{H} vs \mathcal{H})?
4. **Report:** List all violations. Feed to paper-writer for correction.
</step>

<step name="verify_references">
Spawn the bibliographer agent to verify all references before final review. This ensures no hallucinated citations reach the manuscript and that all BibTeX entries are accurate and properly formatted for the target journal.

Resolve bibliographer model:

```bash
BIBLIO_MODEL=$(gpd resolve-model gpd-bibliographer)
```
> **Runtime delegation:** Spawn a subagent for the task below. Adapt the `task()` call to your runtime's agent spawning mechanism. If `model` resolves to `null` or an empty string, omit it so the runtime uses its default model. Always pass `readonly=false` for file-producing agents. If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-bibliographer",
  model="{biblio_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-bibliographer.md for your role and instructions.

Verify all references in the paper and audit citation completeness.

Mode: Audit bibliography + Audit manuscript

Paper directory: paper/
Bibliography: `references/references.bib` (preferred) or `paper/references.bib` if the manuscript keeps a local copy
Manuscript files: paper/*.tex
Target journal: {target_journal}

Tasks:
1. Verify every entry in the active bibliography file against authoritative databases (INSPIRE, ADS, arXiv)
2. Check all \cite{} keys in .tex files resolve to bibliography entries
3. Detect orphaned bibliography entries (not cited in any .tex file)
4. Scan for uncited named results, theorems, or methods that should have citations
5. Verify BibTeX formatting matches {target_journal} requirements
6. Check arXiv preprints for published versions (update stale preprint-only entries)

Write audit report to paper/CITATION-AUDIT.md

Return BIBLIOGRAPHY UPDATED or CITATION ISSUES FOUND."
)
```

**If the bibliographer agent fails to spawn or returns an error:** Proceed without bibliography verification — note in the paper status that citations are unverified. The user should run `/gpd:literature-review` to verify citations after the paper is written.

**If CITATION ISSUES FOUND:**

- Read the audit report and `.gpd/references-status.json`
- Replace resolved `MISSING:` markers: for each entry in `resolved_markers`, find-and-replace `\cite{MISSING:X}` → `\cite{resolved_key}` in all .tex files and remove the associated `% MISSING CITATION:` comment
- Fix hallucinated entries (remove from .bib, update \cite commands)
- Apply metadata corrections to .bib entries
- Add missing citations identified by the bibliographer
- Re-run the audit if substantial changes were made

**If BIBLIOGRAPHY UPDATED:**

- Corrections already applied to .bib by bibliographer
- Review the changes summary, proceed to final review
  </step>

<step name="reproducibility_manifest">
Before strict review, create or refresh the reproducibility manifest the publication review contract expects.

Use the canonical schema:

- `{GPD_INSTALL_DIR}/templates/paper/reproducibility-manifest.md`

Create or update:

- `paper/reproducibility-manifest.json`

Minimum required inputs:

- `paper/ARTIFACT-MANIFEST.json`
- `paper/BIBLIOGRAPHY-AUDIT.json`
- `.gpd/paper/FIGURE_TRACKER.md`
- contract-backed `SUMMARY.md` / `VERIFICATION.md` evidence for decisive claims, figures, and comparisons

Validate it before entering strict review:

```bash
gpd --raw validate reproducibility-manifest paper/reproducibility-manifest.json --strict
```

If validation fails, stop and fix the manifest now. Do not enter `pre_submission_review` with a missing or non-review-ready reproducibility manifest, because strict review preflight will block on it.
</step>

<step name="pre_submission_review">
Before finalizing, run the same staged peer-review panel used by `/gpd:peer-review`. Do not fall back to a single generalist referee pass here, because that is precisely the failure mode this workflow is meant to avoid.

**Standalone entrypoint:** `/gpd:peer-review` is the first-class command for re-running this stage outside the write-paper pipeline. This embedded step must stay behaviorally aligned with that command and use the same six-agent panel:

1. `gpd-review-reader`
2. `gpd-review-literature`
3. `gpd-review-math`
4. `gpd-review-physics`
5. `gpd-review-significance`
6. `gpd-referee` as final adjudicator

For the detailed staging, artifact naming, round handling, `CLAIMS.json` / `STAGE-*.json` outputs, `REVIEW-LEDGER.json`, `REFEREE-DECISION.json`, and recommendation guardrails, follow `@{GPD_INSTALL_DIR}/workflows/peer-review.md` exactly, using `paper/main.tex` as the resolved target and the current draft's bibliography and audit artifacts. Keep the current `project_contract` and `active_reference_context` visible throughout that staged review; they remain authoritative when judging whether the manuscript has surfaced decisive evidence honestly.

**If the staged panel fails:** Do not silently waive the review. Note the failure and recommend running `/gpd:peer-review` directly after resolving the blocking issue.

**After final adjudication:**

Read `.gpd/review/REFEREE-DECISION.json` and `.gpd/review/REVIEW-LEDGER.json` first when they exist, then read `.gpd/REFEREE-REPORT.md` and assess the findings:

- **If recommendation is `accept` or `minor_revision` with 0 major issues:** Proceed to `final_review`. Note minor issues for the user.
- **If recommendation is `major_revision` or `reject`:** Present the major issues to the user before proceeding. For each major issue, show the location, description, and suggested fix. Ask the user whether to:
  1. Address the issues now (spawn paper-writer agents to revise affected sections)
  2. Proceed to `final_review` anyway (accept the issues as known limitations)
  3. Stop and return to research phases to fix underlying problems
</step>

<step name="final_review">
Before declaring the draft complete:

1. **Read the Abstract alone.** Does it tell the full story in miniature?
2. **Read Introduction + Conclusions only.** Is the paper's contribution clear?
3. **Check every equation** has been proofread for typos (missing exponents, swapped indices, etc.)
4. **Check every figure** is referenced and discussed in the text.
5. **Check word count / page count** against journal requirements.
6. **Check reference formatting** matches journal style.

**7. Run paper quality scoring** (see `{GPD_INSTALL_DIR}/references/publication/paper-quality-scoring.md`):

Score the paper across 7 dimensions (equations, figures, citations, conventions, verification, completeness, results presentation) for a total out of 100. Apply journal-specific multipliers for the target journal.

```bash
QUALITY=$(gpd --raw validate paper-quality --from-project . 2>/dev/null)
```

The score should be artifact-driven, not manually estimated. Use:
- `paper/ARTIFACT-MANIFEST.json`
- `paper/BIBLIOGRAPHY-AUDIT.json`
- `.gpd/paper/FIGURE_TRACKER.md` frontmatter `figure_registry`
- `.gpd/comparisons/*-COMPARISON.md`
- phase `SUMMARY.md` / `VERIFICATION.md` `contract_results` and `comparison_verdicts`

Treat paper-support artifacts as scaffolding, not as proof that a claim is established. Missing decisive comparison evidence still blocks a strong submission recommendation even if manifests and audits are complete.

Present the quality score report. If score < journal minimum, list specific items to fix before submission. If score >= minimum, recommend proceeding to `/gpd:arxiv-submission`.

Present summary to user with build instructions, quality score, and next steps.
</step>

<step name="paper_revision">
## Revision Mode (Handling Referee Reports)

**Note:** For a dedicated referee response workflow, use `/gpd:respond-to-referees`. This step handles revision when invoked from within the write-paper pipeline.

When revising a paper in response to referee reports:

1. **Parse the referee report:** Extract each numbered point as a structured item with:
   - Referee number and point number
   - Category: major concern, minor concern, question, suggestion
   - Affected section(s) of the manuscript

2. **Produce AUTHOR-RESPONSE.md:** Spawn a paper-writer agent to produce the structured author response that the gpd-referee expects for multi-round review:

   ```
   task(
     subagent_type="gpd-paper-writer",
     model="{writer_model}",
     readonly=false,
     prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\nRead your <author_response> protocol. Produce an AUTHOR-RESPONSE file.\n\n" +
       "Referee report: .gpd/REFEREE-REPORT{-RN}.md\n" +
       "Review ledger (if present): .gpd/review/REVIEW-LEDGER{-RN}.json\n" +
       "Decision artifact (if present): .gpd/review/REFEREE-DECISION{-RN}.json\n" +
       "Manuscript: paper/*.tex\n" +
       "Round: {N}\n\n" +
       "For each REF-xxx issue, classify as fixed/rebutted/acknowledged. Use the JSON artifacts to identify blocking issues and decision-floor reasons, but keep REF-xxx IDs from the report.\n" +
       "Write to .gpd/AUTHOR-RESPONSE{-RN}.md",
     description="Author response: round {N}"
   )
   ```

   **If the author-response agent fails to spawn or returns an error:** Check if `.gpd/AUTHOR-RESPONSE{-RN}.md` was written (agents write files first). If it exists, proceed to section revision. If not, offer: 1) Retry the agent, 2) Draft the author response in the main context using the referee report and manuscript, 3) Skip structured response and proceed directly to section revisions.

   The AUTHOR-RESPONSE.md uses REF-xxx issue IDs matching the referee report, with classifications (fixed/rebutted/acknowledged) and specific change locations. When present, `REVIEW-LEDGER{-RN}.json` and `REFEREE-DECISION{-RN}.json` provide the blocking-issue and recommendation-floor context that the response must resolve. See the gpd-paper-writer's `<author_response>` section for the full format.

   Also create `paper/REFEREE_RESPONSE.md` (the human-readable response letter) using the `templates/paper/referee-response.md` template for the actual journal submission cover letter.

3. **Spawn section revision agents:** For each major concern requiring manuscript changes, spawn a paper-writer agent with:
   - The specific referee point
   - The current section text
   - The planned response
   - Any new calculations or results needed

4. **Track new calculations:** If referee requests require new derivations or simulations, create tasks in `.gpd/paper/REVISION_TASKS.md` and route to appropriate phases.

5. **Verify consistency:** After all revisions, re-run the consistency_check and notation_audit steps to ensure revisions don't introduce new inconsistencies.

### Bounded Revision Loop (Max 3 Iterations)

After section revision agents complete, run the pre_submission_review step again to check if the revisions resolved the issues. Track iteration count.

**Iteration flow:**

1. **Iteration 1:** Revise sections based on referee/reviewer feedback -> re-run pre_submission_review
2. **If issues remain and iteration < 3:** Feed remaining issues back to paper-writer agents for targeted fixes -> re-run pre_submission_review -> increment iteration
3. **If iteration >= 3:** Stop looping. Present remaining issues to user:

```
Paper revision loop reached maximum iterations (3).

**Remaining issues ({N}):**
{list of unresolved issues from latest pre_submission_review}

Options:
1. Proceed to final_review anyway (accept known issues)
2. Manually edit the affected sections
3. Return to research phases to address underlying problems
```

**Each iteration should be targeted** -- only revise sections flagged by the reviewer, not the entire paper. This prevents introducing new issues while fixing old ones.
</step>

</process>

<success_criteria>

- [ ] Project context loaded via init (commit_docs, state_exists)
- [ ] pdflatex availability checked (compilation tests skipped if unavailable)
- [ ] Research digest checked and loaded (if available from milestone completion)
- [ ] Paper scope established (journal, type, key result, audience)
- [ ] Research artifacts cataloged and mapped to sections
- [ ] Paper-readiness audit passed (0 critical gaps, or user approved proceeding with gaps)
- [ ] Detailed outline created and approved
- [ ] All sections drafted in correct order (Results first, Abstract last)
- [ ] Every equation numbered, labeled, defined, and contextualized
- [ ] Every figure captioned, labeled, and discussed in text
- [ ] Every citation present in bibliography
- [ ] All citations verified via gpd-bibliographer (no hallucinated references)
- [ ] BibTeX formatting matches target journal requirements
- [ ] Pre-submission mock peer review completed via gpd-referee
- [ ] Major referee issues addressed or acknowledged before finalization
- [ ] Internal consistency verified (notation, cross-references, conventions)
- [ ] Notation audit includes NOTATION_GLOSSARY.md cross-reference (if glossary exists)
- [ ] Narrative arc flows from motivation through result to significance
- [ ] Paper directory created with buildable LaTeX (if pdflatex available)
- [ ] Abstract accurately reflects paper content
- [ ] Word/page count within journal limits
</success_criteria>
