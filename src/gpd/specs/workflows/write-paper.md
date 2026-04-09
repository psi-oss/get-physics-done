<purpose>
Structure and write a physics paper from completed research results. Handles the full pipeline from outline through polished draft: section planning, equation presentation, figure integration, narrative flow, and internal consistency verification.

Called from gpd:write-paper command. Sections are drafted by gpd-paper-writer agents.
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

### Builder-Supported Manuscript Scaffolds

The manuscript builder and emitted `${PAPER_DIR}/ARTIFACT-MANIFEST.json` currently support only these `PAPER-CONFIG.json` journal keys:

- `prl` — short, impact-focused letter; only the essential equations stay in the main text
- `apj` — astrophysics manuscript with data/software citation expectations
- `mnras` — astronomy manuscript using the shared generic scoring profile for now
- `nature` — broad-impact scaffold with accessibility emphasis
- `jhep` — theory-first scaffold with stronger derivation and convention expectations
- `jfm` — fluids manuscript using the shared generic scoring profile for now

These are the only valid `journal` values in `PAPER-CONFIG.json` and `${PAPER_DIR}/ARTIFACT-MANIFEST.json`.

### Manual Paper-Quality Profiles

Manual `PaperQualityInput` JSON can use additional scoring-only profiles such as `prd`, `prb`, `prc`, or `nature_physics`, but those are not supported `PAPER-CONFIG.json` builder keys yet.

When `gpd --raw validate paper-quality --from-project .` runs, the journal is resolved only from supported builder keys surfaced by `${PAPER_DIR}/ARTIFACT-MANIFEST.json` or `${PAPER_DIR}/PAPER-CONFIG.json`. Unsupported values fall back to the `generic` scoring profile rather than being inferred.
</journal_formats>

<process>

<step name="init" priority="first">
**Load project context and resolve models:**

```bash
INIT=$(gpd --raw init phase-op --include config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `commit_docs`, `state_exists`, `project_exists`, `autonomy`, `research_mode`, `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, `selected_protocol_bundle_ids`, `protocol_bundle_context`, `active_reference_context`, `derived_manuscript_reference_status`, `derived_manuscript_reference_status_count`, `derived_manuscript_proof_review_status`.

**Load mode settings:**

```bash
AUTONOMY=$(echo "$INIT" | gpd json get .autonomy --default balanced)
RESEARCH_MODE=$(echo "$INIT" | gpd json get .research_mode --default balanced)
```

Mode effects on the write-paper pipeline:
- **Explore mode**: Paper structured as a comparison/survey; broader literature review; more figures; comprehensive related-work section
- **Exploit mode**: Paper structured as a focused result; streamlined introduction; minimal related-work; optimized for tight prose
- **Supervised autonomy**: Checkpoints after the outline, after each section draft, and before referee review.
- **Balanced autonomy**: Auto-generate the outline from the research digest, draft all sections, and continue automatically unless the outline, a draft section, or referee feedback exposes a genuine ambiguity, missing evidence path, claim-level decision, or major structural change. Do not force a routine outline-approval pause in balanced mode.
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

If review preflight exits nonzero because of missing project state, missing roadmap, degraded review integrity, missing research artifacts, or non-review-ready reproducibility coverage, STOP and show the blocking issues before drafting.
Apply the shared publication bootstrap preflight exactly:

@{GPD_INSTALL_DIR}/references/publication/publication-bootstrap-preflight.md

Keep the current `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, and `active_reference_context` visible throughout the staged review; the contract is authoritative only when `project_contract_gate.authoritative` is true.
If `derived_manuscript_proof_review_status` is present, use it as the first-pass manuscript-local summary of proof-review freshness for theorem-bearing results; keep passed proof-redteam artifacts authoritative for strict drafting decisions.
If the manuscript depends on any theorem-style or `proof_obligation` result, treat passed proof-redteam artifacts from the source phases as mandatory review inputs. Missing or open proof audits are CRITICAL blockers, not polish issues.

**Resolve paper directory (if resuming):**

If strict preflight or init already resolved an active manuscript under `paper/`, `manuscript/`, or `draft/`, keep that manuscript root as `PAPER_DIR`.
Strict review for that resume path uses `${PAPER_DIR}/ARTIFACT-MANIFEST.json`; do not satisfy that gate with legacy publication artifacts from a different manuscript directory.
When strict preflight resolves a manuscript root, bind it explicitly as `PAPER_DIR="$DIR"` where `$DIR` is that resolved manuscript directory, and treat `${PAPER_DIR}/{topic_specific_stem}.tex` as the canonical emitted manuscript path recorded by `${PAPER_DIR}/ARTIFACT-MANIFEST.json`.

If a manuscript root was resolved, the workflow is resuming or revising that manuscript directory. Keep every strict-review dependency rooted there.
If no manuscript root was resolved, set `PAPER_DIR="paper"` and bootstrap a fresh scaffold there.

**Check optional local LaTeX compiler availability for smoke tests (cross-platform):**

```bash
# Check standard PATH first, then platform-specific locations
if command -v pdflatex >/dev/null 2>&1; then
  PDFLATEX_AVAILABLE=true
elif [ "$(uname -s 2>/dev/null)" = "MINGW"* ] || [ -n "$WINDIR" ]; then
  # Windows: check common MiKTeX and TeX Live install paths
  for DIR in \
    "$LOCALAPPDATA/Programs/MiKTeX/miktex/bin/x64" \
    "$PROGRAMFILES/MiKTeX/miktex/bin/x64" \
    "$PROGRAMFILES/texlive"/*/bin/windows \
    "$PROGRAMFILES/texlive"/*/bin/win64 \
    "C:/texlive"/*/bin/windows \
    "C:/texlive"/*/bin/win64; do
    if [ -f "$DIR/pdflatex.exe" ]; then
      export PATH="$DIR:$PATH"
      PDFLATEX_AVAILABLE=true
      break
    fi
  done
  [ -z "$PDFLATEX_AVAILABLE" ] && PDFLATEX_AVAILABLE=false
else
  PDFLATEX_AVAILABLE=false
fi
```

If `PDFLATEX_AVAILABLE` is false, display a warning:

```
⚠ pdflatex not found. Local compilation smoke checks will be skipped.
  The paper .tex files will still be generated correctly.

  To enable local smoke checks, install a LaTeX distribution:
    - Windows:     MiKTeX (https://miktex.org/download) or TeX Live
    - macOS:       brew install --cask mactex
    - Linux:       sudo apt install texlive-latex-base  (Debian/Ubuntu)
```

The workflow continues without local compilation smoke checks — .tex file generation does not require pdflatex, and `gpd paper-build` remains the canonical manuscript scaffold contract.

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
- Treat `project_contract` as authoritative only when `project_contract_gate.authoritative` is true; otherwise the contract is visible but blocked, and drafting must pause for contract repair.
- Do **not** let bundle guidance invent new claims, replace `project_contract`, or override `contract_results`, `comparison_verdicts`, `GPD/comparisons/*-COMPARISON.md`, `${PAPER_DIR}/FIGURE_TRACKER.md`, or `active_reference_context`. Those remain authoritative.
- If no bundle is selected, rely on shared publication guidance plus the contract-backed comparison artifacts already present in the project.

</step>

<step name="load_research_digest">

Check for research digests generated during milestone completion. These digests are the primary structured handoff from the research phase and should drive paper organization.

**Step 1 -- Locate digest files:**

```bash
ls GPD/milestones/*/RESEARCH-DIGEST.md 2>/dev/null
```

**If digest(s) found:**

Read all available digests:

```bash
cat GPD/milestones/*/RESEARCH-DIGEST.md
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

If the digest is incomplete or missing sections, note which paper sections will need to be built from raw phase data instead. Prefer the structured init payload first for the canonical state slices already exposed there:

- `derived_convention_lock` and `derived_convention_lock_count`
- `derived_intermediate_results` and `derived_intermediate_result_count`
- `derived_approximations` and `derived_approximation_count`

Use raw phase files only for details that are not already surfaced through init.

```bash
# Fall back to raw sources if digest is insufficient
cat GPD/phases/*/*SUMMARY.md
cat GPD/state.json
```

**If NO digest found:**

Display a clear warning explaining why and offering alternatives:

```
⚠ No RESEARCH-DIGEST.md found in GPD/milestones/.

Research digests are generated during gpd:complete-milestone. Without a digest,
the paper will be built from raw phase data when needed, but the structured init payload should be used first for conventions, results, and approximations.
This works but produces a less structured starting point — the digest provides
a curated narrative arc, convention timeline, and figure registry.

Options:
  1. Continue anyway — build paper from raw phase data (proceed below)
  2. Run gpd:complete-milestone first — generates the digest, then return here
  3. Use --from-phases to explicitly select which phases to include:
     gpd:write-paper --from-phases 1,2,3,5
```

**If `--from-phases` flag is present:** Read summary artifacts (`SUMMARY.md` and `*-SUMMARY.md`) and research artifacts only from the specified phase directories. Skip milestone digest lookup entirely. This is useful for writing papers that cover a subset of phases or when milestones haven't been completed yet.

```bash
# Example: --from-phases 1,3,5
for PHASE_NUM in $(echo "$FROM_PHASES" | tr ',' ' '); do
  PHASE_DIR=$(ls -d GPD/phases/*/ | grep "^GPD/phases/0*${PHASE_NUM}-")
  cat "$PHASE_DIR"/*SUMMARY.md 2>/dev/null
done
```

Proceed to establish_scope and catalog_artifacts, which will gather research context from the init payload first, then summary artifacts, and only the remaining raw phase files directly.

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

4. **Literature context** -- From `GPD/literature/*-REVIEW.md` or phase `RESEARCH.md`

   - What is the relevant prior work to cite?
   - How does our result compare with published values?

5. **Verification results** -- From VERIFICATION.md
   - Which limiting cases were checked?
   - What is the confidence level of each result?

6. **Internal comparisons and decisive evidence** -- From `GPD/comparisons/*-COMPARISON.md`, `${PAPER_DIR}/FIGURE_TRACKER.md`, and bundle context

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
  PHASE_DIRS=$(for n in $(echo "$FROM_PHASES" | tr ',' ' '); do ls -d GPD/phases/0*${n}-* 2>/dev/null; done)
else
  PHASE_DIRS=$(ls -d GPD/phases/*/ 2>/dev/null)
fi
```

### Check 1: summary-artifact completeness

Every contributing phase must have a summary artifact (`SUMMARY.md` or `*-SUMMARY.md`) that tells the paper what user-visible result it contributes. For contract-backed phases, `contract_results` and any decisive `comparison_verdicts` are the readiness anchors; generic `verification_status` / `confidence` tags are optional hints, not gates.

For each phase directory:

1. Verify a summary artifact exists
2. If the phase is contract-backed and supports a paper claim, check for `plan_contract_ref` and `contract_results`
3. If a contract-backed target depends on a decisive comparison, check for the corresponding `comparison_verdicts` entry and an evidence path the manuscript can surface
4. Confirm the summary or verification artifacts identify where the substantive evidence lives

**Missing summary artifact** → CRITICAL gap (phase results not summarized).
**Contract-backed phase missing `contract_results` for a paper-relevant target** → CRITICAL gap.
**Decisive comparison required by the contract but no verdict/evidence path is surfaced** → CRITICAL gap.
**Missing generic `verification_status` / `confidence` tags alone are not blockers.**

### Check 2: Convention consistency

Read the convention declarations from each phase's summary artifact or derivation files and compare:

1. Metric signature — must be identical across all phases
2. Fourier convention — must be identical across all phases
3. Unit system — must be identical (or conversions documented)

Also check `derived_convention_lock` from the init payload first. If a convention lock exists, verify all phases comply. Fall back to `STATE.md` or `state.json` only if the structured field is unavailable.

**Convention mismatch between phases** → CRITICAL gap (combining results with different conventions produces wrong answers).

### Check 3: Numerical value stability

For each key result listed in the research digest (or `derived_intermediate_results` from the init payload):

1. Locate the value in its source phase summary artifact
2. Compare with any cross-references in other phases
3. Flag values that appear in multiple places with different magnitudes

**Values differ by more than stated uncertainty** → CRITICAL gap.
**Values lack uncertainty estimates** → WARNING.

### Check 4: Figure readiness

Check whether planned figures have source data and generation scripts:

```bash
# Check durable figure roots, not internal phase scratch paths
find artifacts/phases figures "${PAPER_DIR}/figures" -maxdepth 3 \( -type f -o -type d \) 2>/dev/null
ls "${PAPER_DIR}/FIGURE_TRACKER.md" 2>/dev/null
```

Default bootstrap example:

```bash
find artifacts/phases figures "${PAPER_DIR}/figures" -maxdepth 3
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
ls "${PAPER_DIR}/references.bib" 2>/dev/null
ls GPD/literature/*-REVIEW.md 2>/dev/null
```

1. Does a project bibliography exist (`references/references.bib` or `${PAPER_DIR}/references.bib`)?
2. Does at least one `GPD/literature/*-REVIEW.md` or phase `RESEARCH.md` exist?
3. Are key prior works identified (the research digest's "Prior Work" or literature review)?
4. If `GPD/literature/*-CITATION-SOURCES.json` exists for the current topic, treat it as the citation-source handoff from literature-review and pass it through `gpd paper-build --citation-sources` instead of reconstructing the list manually.
5. If `derived_manuscript_reference_status` is present in the init/context payload, use it as the manuscript-local status summary for the active manuscript instead of reconstructing read/verified/cited state from prose or source ordering.
6. `gpd paper-build` is the authoritative step that regenerates `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` and the derived `reference_id -> bibtex_key` bridge for the active manuscript root. Rerun it whenever the bibliography or citation set changes before strict review. The JSON audit is the review contract artifact; `${PAPER_DIR}/CITATION-AUDIT.md` is only the human-readable report.
   For the default bootstrap path, this means: rerun `paper-build` so `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` reflects the current bibliography before strict review.

**No bibliography file, no literature review, and no citation-source sidecar** → WARNING (citations will need to be built from scratch).

### Check 6: Decisive comparison continuity

Check that the manuscript can surface the decisive evidence, not just supporting narrative:

1. Read `GPD/comparisons/*-COMPARISON.md` and note every decisive `comparison_verdicts` entry
2. Read `${PAPER_DIR}/FIGURE_TRACKER.md` and confirm those decisive claims have a planned figure, table, or explicit textual comparison path
3. If `selected_protocol_bundle_ids` is non-empty, use `protocol_bundle_context` only as an additive expectation map for which anchors, estimator caveats, or benchmark comparisons should stay visible in the paper
4. Only require the manuscript to surface decisive comparisons for claims it actually makes. Honest narrowing is acceptable; silent omission is not.

**Decisive comparison missing for a central claim** → CRITICAL gap.
**Bundle guidance suggests a decisive comparison that is absent, but the manuscript narrows the claim honestly** → WARNING, not blocker.

### Check 7: Proof-obligation coverage

Check whether any contributing phase or manuscript section makes theorem-style claims.

Treat a manuscript claim as proof-bearing when:

1. the supporting phase contract includes `proof_obligation`
2. the manuscript uses theorem-style language (`theorem`, `lemma`, `corollary`, `proposition`, `claim`, `proof`, `we prove`, `show that`)
3. the draft strengthens a formal result beyond the audited scope of a source derivation

For each such claim:

1. locate the source `*-PROOF-REDTEAM.md` artifact in the contributing phase, or the manuscript-round `GPD/review/PROOF-REDTEAM{round_suffix}.md` artifact when it already exists
2. confirm the audit reports `status: passed`
3. confirm the audit closed parameter, hypothesis, quantifier/domain, and conclusion-clause coverage
4. confirm the manuscript wording does not overstate what the passed audit actually established

**Missing proof-redteam artifact for a theorem-style claim** → CRITICAL gap.
**Proof-redteam artifact present but `status != passed`** → CRITICAL gap.
**Manuscript strengthens the claim beyond the audited theorem statement** → CRITICAL gap.

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
		  Proof obligations          {P/F}     {details}

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

If `autonomy=supervised`, present the outline for approval before proceeding. If `autonomy=balanced`, treat the outline as a working draft and continue automatically unless it exposes a genuine ambiguity, missing evidence path, or scope-changing decision that needs user judgment. If `autonomy=yolo`, continue automatically after the artifact checks.
</step>

<step name="generate_files">
Create the paper directory structure under `${PAPER_DIR}/`:

```
${PAPER_DIR}/
+-- {topic_specific_stem}.tex   # Master document with \input commands
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

The manuscript entrypoint should:

- Use the target journal's document class
- Define all custom macros in a preamble block (see `{GPD_INSTALL_DIR}/templates/latex-preamble.md` for standard packages, project-specific macros, equation labeling conventions, and SymPy-to-LaTeX integration)
- \input each section file
- Handle bibliography correctly for the journal

If the project has a `GPD/analysis/LATEX_PREAMBLE.md`, use its macros to ensure notation consistency with the research phases.

If a machine-readable paper spec is available, prefer the canonical builder:

```bash
mkdir -p "${PAPER_DIR}"
gpd paper-build "${PAPER_DIR}/PAPER-CONFIG.json" --output-dir "${PAPER_DIR}"
```

This emits `${PAPER_DIR}/{topic_specific_stem}.tex`, writes the manuscript-root artifact manifest, and keeps the manuscript scaffold aligned with the tested `gpd.mcp.paper` package. `gpd paper-build` defines the build truth for the manuscript; local compiler runs are only smoke checks. If no JSON spec exists yet, create `${PAPER_DIR}/PAPER-CONFIG.json` first using `{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md` as the schema source of truth, set `output_filename` to a short topic-specific 2-3 word underscore stem, and then run `gpd paper-build` before proceeding. The compilation checks in `draft_sections` require the emitted manuscript `.tex` file to exist.

After `gpd paper-build` runs, treat the `.tex` artifact recorded in `${PAPER_DIR}/ARTIFACT-MANIFEST.json` as the canonical manuscript entrypoint and refer to its basename as `MANUSCRIPT_BASENAME` in later smoke checks.

When authoring `${PAPER_DIR}/PAPER-CONFIG.json`:

- use the exact top-level fields from `{GPD_INSTALL_DIR}/templates/paper/paper-config-schema.md`
- keep `authors`, `sections`, `figures`, and `appendix_sections` as JSON arrays
- keep any custom funding/collaborator text in `acknowledgments`; `gpd paper-build` appends this exact sentence automatically if it is missing: `This research made use of Get Physics Done (GPD) and was supported in part by a GPD Research Grant from Physical Superintelligence PBC (PSI).`
- keep `journal` to a supported builder key like `prl`, `apj`, `mnras`, `nature`, `jhep`, or `jfm`
- do not invent extra keys just because a journal asks for extra prose; put that prose in the section content instead

Canonical schema for `${PAPER_DIR}/ARTIFACT-MANIFEST.json`:
@{GPD_INSTALL_DIR}/templates/paper/artifact-manifest-schema.md

Canonical schema for `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`:
@{GPD_INSTALL_DIR}/templates/paper/bibliography-audit-schema.md

Treat both emitted JSON artifacts as strict review inputs. If they need to be recreated or repaired, match those schema surfaces exactly instead of inventing keys from prose memory.

**Supplemental material:** If the paper requires supplemental material (common for PRL and other letter-format journals), use `{GPD_INSTALL_DIR}/templates/paper/supplemental-material.md` for the standard structure (extended derivations, computational details, additional figures, data tables, code availability).

**Experimental comparison:** If the paper compares theoretical predictions with experimental or observational data, use `{GPD_INSTALL_DIR}/templates/paper/experimental-comparison.md` for the systematic comparison structure (data source metadata, unit conversion checklist, pull analysis, chi-squared statistics, discrepancy classification with root cause hierarchy).
</step>

<step name="generate_figures">
## Figure Generation

Ensure the paper directory structure exists before writing any files:

```bash
mkdir -p "${PAPER_DIR}/figures"
```

Before drafting sections, generate all planned figures:

1. Before reading or updating `${PAPER_DIR}/FIGURE_TRACKER.md`, load `@{GPD_INSTALL_DIR}/templates/paper/figure-tracker.md` and treat its `figure_registry` frontmatter as the schema source of truth. Keep the registry machine-readable for paper-quality scoring; do not invent ad hoc keys or collapse it into prose.
2. Read `${PAPER_DIR}/FIGURE_TRACKER.md` for figure specifications
3. For each figure with status != "Final":
   a. Locate source data (from phase directories)
   b. Generate matplotlib script with publication styling:
      - Use shared style: `plt.style.use('${PAPER_DIR}/paper.mplstyle')` if exists, otherwise use sensible defaults
      - Font size 10pt, axes labels with units, legend
      - Error bars where applicable, colorblind-safe colors
   c. Execute script, save to `${PAPER_DIR}/figures/`
   d. Update `${PAPER_DIR}/FIGURE_TRACKER.md` status
4. Verify all figures referenced in outline exist as files

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

**Optional local compilation smoke check after each wave (if a compiler is available):**

Skip this check if `PDFLATEX_AVAILABLE` is false (set in init step). `gpd paper-build` remains the source of build truth either way.

After each drafting wave completes, verify the document compiles:

```bash
cd "${PAPER_DIR}"
pdflatex -interaction=nonstopmode "${MANUSCRIPT_BASENAME}" 2>&1 | tail -20
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
if [ -f "${PAPER_DIR}/results.tex" ] && [ -f "${PAPER_DIR}/methods.tex" ]; then
  echo "Wave 1 outputs exist -- skipping to Wave 2"
else
  # Spawn Wave 1 agents
fi
```

Apply this pattern to each wave: check for the expected .tex output files before spawning writer agents.
Check if the expected .tex file was written to `${PAPER_DIR}/` before treating a section handoff as complete.
If the file exists, proceed to the next section.

**For each section, spawn a writer agent:**
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\n<autonomy_mode>{AUTONOMY}</autonomy_mode>\n<research_mode>{RESEARCH_MODE}</research_mode>\n" + section_prompt,
  subagent_type="gpd-paper-writer",
  model="{writer_model}",
  readonly=false,
  description="Draft: {section_name}"
)
```

**If a writer agent fails to spawn or returns an error:** Check the writer's typed `gpd_return.status` first. If the writer returned `status: completed`, verify that `gpd_return.files_written` names the expected `.tex` file and that the file exists on disk. If the writer returned `status: checkpoint`, treat it as an incomplete handoff and continue only by spawning a fresh continuation run after the orchestrator/user review. If the writer returned `status: blocked` or `status: failed`, treat the section as incomplete. Do not accept a preexisting `.tex` file as a substitute for a successful spawn; a spawn error always leaves the section incomplete until a fresh typed return names the artifact and the file exists on disk.

Treat the emitted `.tex` file as the success artifact gate for each section.
Route on the writer's typed return envelope. A writer response that does not report `status: completed`, does not list the emitted path in `files_written`, or does not leave the expected file on disk is not a completed section, even if the agent returned success text.

**Each writer agent receives:**

- Paper context (title, journal, key result, audience)
- Section brief (purpose, content, equations, figures, citations)
- Narrative continuity (how preceding section ends, what following section needs)
- Research artifacts (file paths to read for content)
- Active decisive-comparison artifacts (`GPD/comparisons/*-COMPARISON.md`) and relevant `FIGURE_TRACKER.md` entries for any contract-critical figure or table
- Passed proof-redteam artifacts (`*-PROOF-REDTEAM.md`, `GPD/review/PROOF-REDTEAM{round_suffix}.md`) for any theorem-style claim surfaced in the section
- `protocol_bundle_context` and `selected_protocol_bundle_ids` as additive specialized guidance only; they help decide which decisive anchors, estimator caveats, and benchmark comparisons must stay visible, but they do not replace the contract-backed evidence ledger
- Writing principles (see command file)

Writer agents must not strengthen, generalize, or rhetorically smooth theorem-style claims beyond what the proof-redteam artifacts actually passed. If the section brief implies a stronger theorem than the available audit supports, STOP and route the claim back for proof review instead of writing around the gap.

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
grep -rn "RESULT PENDING" "${PAPER_DIR}"/*.tex
```

For each `% [RESULT PENDING: phase N, task M -- description]`:

1. Read the referenced phase's summary artifact for the completed result
2. If the result is available: replace `\text{[PENDING]}` with the actual value and remove the `% [RESULT PENDING: ...]` comment
3. If the result is still unavailable: flag as a blocker — the paper cannot be finalized with pending placeholders

**GATE: All RESULT PENDING markers must be resolved before proceeding to verify_references.**

```bash
PENDING_COUNT=$(grep -rcE "RESULT PENDING|\\\\text\{\\[PENDING\\]\}" "${PAPER_DIR}"/*.tex 2>/dev/null || echo 0)
```

If `PENDING_COUNT > 0`:

```
ERROR: ${PENDING_COUNT} unresolved RESULT PENDING marker(s) found.
A paper with placeholder values is not submission-ready.

Unresolved markers:
$(grep -rn "RESULT PENDING" "${PAPER_DIR}"/*.tex 2>/dev/null)

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
ls GPD/NOTATION_GLOSSARY.md 2>/dev/null
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
@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

> If subagent spawning is unavailable, execute these steps sequentially in the main context.

```
task(
  subagent_type="gpd-bibliographer",
  model="{biblio_model}",
  readonly=false,
  prompt="First, read {GPD_AGENTS_DIR}/gpd-bibliographer.md for your role and instructions.\n\n<autonomy_mode>{AUTONOMY}</autonomy_mode>\n<research_mode>{RESEARCH_MODE}</research_mode>

Verify all references in the paper and audit citation completeness.

Mode: Audit bibliography + Audit manuscript

Paper directory: ${PAPER_DIR}/
Bibliography: `references/references.bib` (preferred) or `${PAPER_DIR}/references.bib` if the manuscript keeps a local copy
Citation sources: `GPD/literature/*-CITATION-SOURCES.json` when literature-review has already assembled a machine-readable citation list for the current topic
Manuscript tree: all `.tex` files under `${PAPER_DIR}` recursively, rooted at the manifest-resolved manuscript directory
Target journal: {target_journal}

Tasks:
1. Verify every entry in the active bibliography file against authoritative databases (INSPIRE, ADS, arXiv)
2. Check all \cite{} keys in .tex files resolve to bibliography entries
3. Detect orphaned bibliography entries (not cited in any .tex file)
4. Scan for uncited named results, theorems, or methods that should have citations
5. Verify BibTeX formatting matches {target_journal} requirements
6. Check arXiv preprints for published versions (update stale preprint-only entries)
7. Preserve `GPD/literature/*-CITATION-SOURCES.json` as the source artifact that seeded the bibliography; do not treat it as a competing registry

Write audit report to ${PAPER_DIR}/CITATION-AUDIT.md

Return a typed `gpd_return` envelope. Use `status: completed` when the bibliography task finished, even if the human-readable heading is `## CITATION ISSUES FOUND`; use `status: checkpoint` only when researcher input is required to continue. A completed return must list `references/references.bib` and `GPD/references-status.json` in `gpd_return.files_written`, and both files must exist on disk before the bibliography pass is accepted."
)
```

**If the bibliographer agent fails to spawn or returns an error:** Do not mark bibliography verification complete. Offer: 1) Retry the bibliographer, 2) Run the audit in the main context, 3) Stop and leave citation status unverified. Do not proceed to strict review, reproducibility-manifest generation, or final review until `${PAPER_DIR}/CITATION-AUDIT.md` and the refreshed `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` exist.

Treat `${PAPER_DIR}/CITATION-AUDIT.md`, the refreshed `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`, and the bibliographer's typed `gpd_return` envelope as the bibliography success gate; all three must be present, and the typed return must name the bibliography outputs, before the pass is accepted.
If the typed return is missing, blocked, or does not name the bibliography outputs, keep the bibliography pass incomplete even if older audit files are still on disk.

**If the bibliographer completed with issues recorded in the audit report or `GPD/references-status.json`:**

- Read the audit report and `GPD/references-status.json`
- If `derived_manuscript_reference_status` is present, use it as the first-pass manuscript-local citation-status summary instead of reconstructing citation state manually from `.tex` or `.bib` files.
- If a citation-source sidecar exists, keep it aligned with the bibliography output so `gpd paper-build --citation-sources` can continue to consume the same stable reference IDs and regenerate the authoritative bibliography audit in lockstep
- Prefer the `reference_id -> bibtex_key` mapping surfaced by `gpd paper-build` over reconstructing manuscript keys manually from prose or source ordering
- Replace resolved `MISSING:` markers: for each entry in `resolved_markers`, find-and-replace `\cite{MISSING:X}` → `\cite{resolved_key}` in all .tex files and remove the associated `% MISSING CITATION:` comment
- Fix hallucinated entries (remove from .bib, update \cite commands)
- Apply metadata corrections to .bib entries
- Add missing citations identified by the bibliographer
- Re-run the audit if substantial changes were made
- Re-run `gpd paper-build` after bibliography changes so `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` and the derived reference bridge are regenerated before entering strict review or `pre_submission_review`.
- Confirm `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` exists after the refresh before proceeding to reproducibility or strict review.

**If the bibliographer completed cleanly with no remaining citation issues:**

- Corrections already applied to .bib by bibliographer
- Re-run `gpd paper-build` so `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` reflects the current bibliography state and the derived reference bridge stays current for downstream strict review.
- If `derived_manuscript_reference_status` is present, use it to confirm which manuscript-local references still need attention, but let the refreshed manuscript-root build artifacts decide the final state.
- If the bibliography was seeded from `GPD/literature/*-CITATION-SOURCES.json`, keep that handoff artifact visible for reruns of `gpd paper-build --citation-sources`.
- Review the changes summary, proceed to final review
  </step>

<step name="reproducibility_manifest">
Before strict review, create or refresh the reproducibility manifest the publication review contract expects.

Use the canonical schema:

- `{GPD_INSTALL_DIR}/templates/paper/reproducibility-manifest.md`

Canonical schema for `${PAPER_DIR}/reproducibility-manifest.json`:
@{GPD_INSTALL_DIR}/templates/paper/reproducibility-manifest.md

Create or update:

- `${PAPER_DIR}/reproducibility-manifest.json`

Minimum required inputs:

- `${PAPER_DIR}/ARTIFACT-MANIFEST.json`
- `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` produced by the latest `gpd paper-build`
- `${PAPER_DIR}/FIGURE_TRACKER.md`
- contract-backed summary-artifact / `VERIFICATION.md` evidence for decisive claims, figures, and comparisons

`gpd paper-build` must have regenerated `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json` for the current bibliography before building the reproducibility manifest. Stale bibliography audits are not acceptable review inputs.

Validate it before entering strict review:

```bash
gpd --raw validate reproducibility-manifest "${PAPER_DIR}/reproducibility-manifest.json" --strict
```

For the default bootstrap path, the validation command is:

```bash
gpd --raw validate reproducibility-manifest "${PAPER_DIR}/reproducibility-manifest.json" --strict
```

If validation fails, stop and fix the manifest now. Do not enter `pre_submission_review` with a missing or non-review-ready reproducibility manifest, because strict review preflight will block on it.
</step>

<step name="pre_submission_review">
Before finalizing, run the same staged peer-review panel used by `gpd:peer-review`. Do not fall back to a single generalist referee pass here, because that is precisely the failure mode this workflow is meant to avoid.

For theorem-style or `proof_obligation` claims, this stage also carries the mandatory auxiliary proof-redteam gate from `peer-review.md`. Missing or open proof-redteam artifacts are fail-closed blockers even if the rest of the manuscript review looks clean.

**Standalone entrypoint:** `gpd:peer-review` is the first-class command for re-running this stage outside the write-paper pipeline. This embedded step must stay behaviorally aligned with that command and use the same six-agent panel:

1. `gpd-review-reader`
2. `gpd-review-literature`
3. `gpd-review-math`
4. `gpd-review-physics`
5. `gpd-review-significance`
6. `gpd-referee` as final adjudicator

Apply the shared publication round contract exactly:

@{GPD_INSTALL_DIR}/references/publication/publication-review-round-artifacts.md

Then follow `@{GPD_INSTALL_DIR}/workflows/peer-review.md` exactly, using the resolved `${PAPER_DIR}/{topic_specific_stem}.tex` target recorded in `ARTIFACT-MANIFEST.json` as the review target. Keep the current `project_contract`, `project_contract_gate`, `project_contract_load_info`, `project_contract_validation`, and `active_reference_context` visible throughout that staged review; the contract remains authoritative only when `project_contract_gate.authoritative` is true.

**If the staged panel fails:** Do not silently waive the review. Note the failure and recommend running `gpd:peer-review` directly after resolving the blocking issue.

**After final adjudication:**

Read `GPD/review/REFEREE-DECISION{round_suffix}.json` and `GPD/review/REVIEW-LEDGER{round_suffix}.json` first when they exist, then read `GPD/REFEREE-REPORT{round_suffix}.md` and assess the findings:

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

Score the paper across 7 dimensions (equations, figures, citations, conventions, verification, completeness, results presentation) for a total out of 100. Apply journal-specific multipliers for the resolved journal profile, noting that the artifact-driven path only honors supported builder journals surfaced by `${PAPER_DIR}/ARTIFACT-MANIFEST.json` or `${PAPER_DIR}/PAPER-CONFIG.json`.

```bash
QUALITY=$(gpd --raw validate paper-quality --from-project . 2>/dev/null)
```

The score should be artifact-driven, not manually estimated. Use:
- `${PAPER_DIR}/ARTIFACT-MANIFEST.json`
- `${PAPER_DIR}/BIBLIOGRAPHY-AUDIT.json`
- `${PAPER_DIR}/FIGURE_TRACKER.md` frontmatter `figure_registry`
- `GPD/comparisons/*-COMPARISON.md`
- phase summary-artifact / `VERIFICATION.md` `contract_results` and `comparison_verdicts`

Treat paper-support artifacts as scaffolding, not as proof that a claim is established. Missing decisive comparison evidence still blocks a strong submission recommendation even if manifests and audits are complete.

Present the quality score report. If score < journal minimum, list specific items to fix before submission. If score >= minimum but no submission-clearing staged review exists yet, recommend `gpd:peer-review`. Recommend `gpd:arxiv-submission` only when the latest staged review already clears submission packaging.

Present summary to user with build instructions, quality score, and next steps.
</step>

<step name="paper_revision">
## Revision Mode (Handling Referee Reports)

**Note:** For a dedicated referee response workflow, use `gpd:respond-to-referees`. This step handles revision when invoked from within the write-paper pipeline.

When revising a paper in response to referee reports:

1. **Parse the referee report:** Extract each numbered point as a structured item with:
   - Referee number and point number
   - Category: major concern, minor concern, question, suggestion
   - Affected section(s) of the manuscript

2. **Spawn section revision agents first:** For each major concern requiring manuscript changes, spawn a paper-writer agent with:
   - The specific referee point
   - The current section text
   - The planned response
   - Any new calculations or results needed

   Treat the manuscript edit as the source of truth for any `fixed` classification. A point is not `fixed` until the corresponding section file changes have landed on disk.

3. **Produce paired response artifacts after the edits land:** Spawn a paper-writer agent to produce the structured author response and response letter that the gpd-referee expects for multi-round review:

   @{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md

   > If subagent spawning is unavailable, execute these steps sequentially in the main context.

   ```
   task(
     subagent_type="gpd-paper-writer",
     model="{writer_model}",
     readonly=false,
     prompt="First, read {GPD_AGENTS_DIR}/gpd-paper-writer.md for your role and instructions.\n\nRead the canonical <author_response> protocol at {GPD_INSTALL_DIR}/templates/paper/author-response.md, the canonical referee response template at {GPD_INSTALL_DIR}/templates/paper/referee-response.md, and the shared publication response-writer handoff at {GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md. Produce both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`.\n\n<autonomy_mode>{AUTONOMY}</autonomy_mode>\n<research_mode>{RESEARCH_MODE}</research_mode>\n" +
       "Referee report: GPD/REFEREE-REPORT{round_suffix}.md\n" +
       "Review ledger (if present): GPD/review/REVIEW-LEDGER{round_suffix}.json\n" +
       "Decision artifact (if present): GPD/review/REFEREE-DECISION{round_suffix}.json\n" +
       "Manuscript tree: all .tex files under ${PAPER_DIR} recursively, rooted at the manifest-resolved manuscript directory, after the section revision agents have landed their edits\n" +
       "Round: {N}\n\n" +
       "For each REF-xxx issue, classify as fixed/rebutted/acknowledged/needs-calculation only after the corresponding manuscript edits exist on disk. Use fixed only for issues whose section changes are already present; otherwise use acknowledged or needs-calculation.\n" +
       "If an issue needs new work, keep `New calculations required` and `Source phase for new work` explicit in the author-response tracker.\n" +
       "Write to GPD/AUTHOR-RESPONSE{round_suffix}.md and GPD/review/REFEREE_RESPONSE{round_suffix}.md",
     description="Author response: round {N}"
   )
   ```

   Apply the shared publication response-writer handoff exactly:

   @{GPD_INSTALL_DIR}/references/publication/publication-response-writer-handoff.md

   **If the response-handoff agent fails to spawn or returns an error:** Check the agent's typed `gpd_return.status` first. If it returned `status: completed`, verify that `gpd_return.files_written` names both `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`, and verify both files exist on disk. If it returned `status: checkpoint`, treat that as a fresh continuation handoff rather than completion. If it returned `status: blocked` or `status: failed`, treat the response as incomplete. Do not accept preexisting response files as a substitute for a successful spawn; the round remains incomplete until a fresh typed return names both outputs and both files exist on disk.
   Treat `GPD/AUTHOR-RESPONSE{round_suffix}.md`, `GPD/review/REFEREE_RESPONSE{round_suffix}.md`, and the writer's typed `gpd_return` envelope as the response success gate. If the shared gate is not satisfied, offer: 1) Retry the agent, 2) Draft the response artifacts in the main context using the referee report and revised manuscript, 3) Skip structured response and proceed directly to calculation tracking.

   See the canonical `templates/paper/author-response.md` and `templates/paper/referee-response.md` contracts plus the shared publication response-writer handoff for the full response-tracker format.

4. **Track new calculations:** If referee requests require new derivations or simulations, create tasks in `${PAPER_DIR}/REVISION_TASKS.md` and route to appropriate phases.

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
- [ ] Local compilation smoke check run when available (skipped otherwise)
- [ ] Research digest checked and loaded (if available from milestone completion)
- [ ] Paper scope established (journal, type, key result, audience)
- [ ] Research artifacts cataloged and mapped to sections
- [ ] Paper-readiness audit passed (0 critical gaps, or user approved proceeding with gaps)
- [ ] Detailed outline created; approval captured only when autonomy requires it
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
- [ ] Paper directory created with buildable LaTeX scaffold via `gpd paper-build`
- [ ] Abstract accurately reflects paper content
- [ ] Word/page count within journal limits
</success_criteria>

<community_contribution>

After a paper draft is finalized and passes peer review, display:

```
────────────────────────────────────────────────────────
📄 Share your work with the GPD community

When the paper is posted to arXiv or otherwise public,
consider opening a pull request to add it to the
README.md "Papers Using GPD" list:

  https://github.com/psi-oss/get-physics-done#papers-using-gpd

What to include:
  • A short summary of the problem and approach
  • The GPD commands/workflow you used
  • Key results or figures (optional)

This helps other researchers discover real GPD papers and
learn from concrete workflows.
────────────────────────────────────────────────────────
```

This prompt is informational only. Do not block the paper workflow on it.

</community_contribution>
