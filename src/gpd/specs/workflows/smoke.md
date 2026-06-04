<purpose>
Sniff-test a published quantitative claim with the smallest reproducible computation BEFORE committing to a full GPD project around it. The smoke command runs pre-`new-project`: it confirms that the claim is reproducible at all, the user can implement it, and the toolchain works — then either greenlights `/gpd:new-project` or stops and flags the gap. It deliberately refuses to scaffold a project, write GPD state, or scale the run.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="orient_the_user">
Open with one short sentence:

`This is a smoke test. I will reproduce the smallest possible version of a quantitative claim or assumption, compare numbers, and stop. No project scaffolding, no state, no scaling.`

Detect the invocation mode from `$ARGUMENTS`:

- If `$ARGUMENTS` contains the flag `--from-plan`, enter the `from_plan_intake` step.
- Else if `$ARGUMENTS` contains the flag `--assumption "<text>"`, treat the quoted text as an assumption (not a published claim) and skip to `identify_minimal_setup`.
- Else if `$ARGUMENTS` is non-empty, treat it as the claim text and skip the open question in `gather_the_claim`.
- Else ask for a claim or assumption.

A "claim" is a published quantitative statement with a source (anchor mode). An "assumption" is a local statement that the user or another GPD command is about to commit to without verification (assumption mode). Both route through the same propose-confirm-run-verdict machinery; the only difference is how the verdict is framed.
</step>

<step name="from_plan_intake">
This step is reached when invoked with `--from-plan`.

Search order for the plan file (non-recursive, skip archived/backup folders):

1. `GPD/phases/*/*-PLAN.md` (the canonical location written by `/gpd:plan-phase` — phase folder + planner-emitted filename suffix).
2. `GPD/phases/*/PLAN.md` (older or hand-written form).
3. `./PLAN.md` in the current working directory (pre-project test mode for users not in a full GPD project).
4. If multiple candidates match, list them with their containing phase folder and ask the user which file to read.
5. If no candidates exist, stop and tell the user there is no `PLAN.md` to read from. Do not silently fall back to interactive claim entry — the user invoked `--from-plan` for a reason.

**Tolerant parser for the assumptions section.** Different writers emit different shapes; the parser must accept all of these without requiring `/gpd:plan-phase` or any other GPD command to be modified:

- **Flat form**: An H2 heading whose title contains the word `assumption` or `assumptions` (case-insensitive), followed by bulleted lines starting with `- `, `* `, or `1.`/`2.`/etc. Example heading: `## Assumptions`.
- **Hierarchical form**: An H2 heading containing `assumption(s)` (case-insensitive), with H3 subheadings underneath (e.g. `### Physical Assumptions`, `### Mathematical Framework`, `### Approximation Scheme`). Each H3 may contain bullets, numbered lines, or short prose paragraphs. Example H2: `## My Assumptions for Phase 1: Damped Pendulum`.
- **Embedded form**: A YAML/structured block somewhere in the file with a key like `assumptions:` or `assumption:`. Treat each list item as a bullet.

Extraction algorithm:

1. Scan for the first H2 (`^## `) whose text contains the case-insensitive substring `assumption`. Section extends to the next H2 or end of file.
2. Inside the section, collect candidates:
   - Every line that begins with `- `, `* `, `1. ` / `2. ` / `N. ` (after stripping leading whitespace) is one candidate. Strip the bullet marker, keep the rest.
   - Lines under H3 subheadings are tagged with the H3 title in brackets, e.g. `[Physical] sin(θ) ≈ θ to within 1% at θ₀ = 30°`. This preserves which category the assumption came from.
   - Prose paragraphs that are not bulleted are NOT auto-extracted — too noisy. Instead, list the H3 titles with a "(no bullets — full subsection is prose)" tag, and let the user paste in the specific assumption text manually if they want to smoke it.
3. If no candidates are found, report the H2 title that was matched, list the H3 subsection titles seen, and ask the user to either paste the assumption text or invoke `/gpd:smoke --assumption "<text>"` directly.

Presenting to the user:

1. Show the source file path.
2. Show the matched H2 heading.
3. Number each candidate. Include the `[Category]` tag if it came from an H3 subsection.
4. Ask which to smoke. Accept exactly one number per invocation. Do not chain.
5. Bind the selected text as the assumption (drop the `[Category]` prefix for the assumption_text itself, but keep it in the verdict source attribution) and route into `identify_minimal_setup` in assumption mode. Carry the source file path through to the final verdict.

Never edit `PLAN.md` from this step. Smoke is read-only against the plan; rewriting the plan after a verdict is the user's call (or a future explicit command).
</step>

<step name="gather_the_claim">
A smoke test requires a quantitative anchor — a published number you can either match or not. Refuse to proceed without one. Acceptable forms:

- Numerical value with units and a source (e.g. "Onsager 1944: 2D Ising Tc/J ≈ 2.269").
- Analytic identity that produces a number for chosen parameters (e.g. "small-angle pendulum period T = 2π√(L/g) for L=1m, g=9.81 m/s² gives T ≈ 2.007 s").
- Reported result from a paper with a figure or table value (e.g. "Lorenz 1963 Fig. 2: trajectory exhibits two-lobe attractor for σ=10, β=8/3, ρ=28").

Reject vague or qualitative claims ("AI improves productivity", "the system is unstable"). Ask the user to sharpen them into a number + tolerance, or stop.

Capture as a structured claim:

- `claim_value`: the number to hit (with units).
- `claim_source`: paper / equation / table reference.
- `claim_parameters`: any input parameters required to make the claim concrete (lattice size, temperature range, L, g, σ, etc.).
</step>

<step name="identify_minimal_setup">
Propose the *smallest* configuration that could plausibly reproduce the claim. Be aggressive about smallness — the point is fast feedback, not publication-quality.

For stochastic / many-body problems: smallest lattice or particle count that still shows the phenomenon (e.g. 16×16 or 20×20 Ising, not 100×100).

For ODE / PDE: shortest integration time, coarsest tolerable step (e.g. one period of oscillation, not 1000 periods).

For ML / data: smallest sample that exercises the pipeline (e.g. 1000 examples, not the full dataset).

State the proposal explicitly with these fields and ask the user to confirm or modify:

- `setup`: one-paragraph description of the method (e.g. "Metropolis Monte Carlo, single-spin flips, periodic BCs").
- `minimal_parameters`: concrete values (lattice size, sweep count, dt, etc.).
- `expected_runtime`: a rough number ("under 60 seconds on this laptop").
- `success_criterion`: numerical threshold for PASS. Default to ±10% for finite-size / stochastic methods, ±1% for deterministic, but state the chosen tolerance and let the user override.

Do not start writing code until the user confirms the proposal or modifies it.
</step>

<step name="scaffold_and_run">
After confirmation:

1. Create a scratch script in the current working directory. Use a clearly-named file like `smoke_<short_label>.py`. Do NOT create a `GPD/` folder, do NOT write any GPD state, and do NOT touch git. This is pre-project.
2. Keep the script self-contained: standard library + numpy/scipy/matplotlib only. No project imports, no external configs.
3. Print the measured value(s) clearly at the end. If a comparison is unambiguous (single scalar), also print the ratio measured/claim and the absolute residual.
4. Run the script with `python` (or `python3`). Capture stdout. If it takes longer than the stated `expected_runtime` × 3, kill it and report the timeout.

If the script errors before producing a number, do not silently retry. Report the error and stop — the smoke has revealed an implementation gap, which is itself useful information.
</step>

<step name="compare_and_verdict">
Compare measured value to `claim_value`:

- PASS: measured within `success_criterion` of the claim.
- FAIL: measured outside the tolerance band, or wrong sign, or wrong order of magnitude.
- INCONCLUSIVE: ran successfully but result is too noisy to decide (e.g. error bars overlap both pass and fail regions). Treat INCONCLUSIVE as not-yet-PASS.

Show the user a three-line verdict block. In anchor mode:

```
Claim:    <claim_value> (<claim_source>)
Measured: <measured_value> (±<uncertainty if known>)
Verdict:  PASS | FAIL | INCONCLUSIVE  (tolerance ±<X>)
```

In assumption mode (from `--assumption` or `--from-plan`):

```
Assumption: <text> (from <source file path or 'user input'>)
Measured:   <measured_value> (±<uncertainty if known>)
Verdict:    PASS | FAIL | INCONCLUSIVE  (tolerance ±<X>)
```

Do not editorialize past those three lines. The numbers are the verdict.
</step>

<step name="gate_next_step">
Strict routing based on the verdict and invocation mode.

**Anchor mode** (claim is a published quantitative statement):

- **PASS** → "The claim reproduces at minimal scale. You can now scaffold a full project with `/gpd:new-project` and plan the real study (finite-size scaling, parameter sweeps, novel extensions). The smoke script remains in this folder as the seed implementation."
- **FAIL** → "The claim did not reproduce. Do not start a project around it yet. Likely causes: implementation bug in the smoke script, wrong parameters, or the claim itself is mis-stated. Investigate before scaffolding."
- **INCONCLUSIVE** → "Result is too noisy to decide. Suggest one tightening: <e.g. 4× more sweeps, finer dt, larger lattice>. Re-run `/gpd:smoke` with the tightened parameters before starting a project."

**Assumption mode** (statement came from `--assumption` or `--from-plan`):

- **PASS** → "The assumption holds at the tested parameters. Safe to keep in `<source file path>`. The smoke script remains as the verification record. If this came from `--from-plan`, the assumption can stay committed; you may proceed with `/gpd:plan-phase` or `/gpd:execute-phase` as planned."
- **FAIL** → "The assumption does not hold at the tested parameters. Do NOT proceed with `/gpd:execute-phase` on this plan. Recommended next actions: (1) revise the assumption in `<source file path>` (e.g., narrow the range it claims to cover, replace the method); (2) re-smoke with the revised assumption; (3) only then continue. Do not silently overwrite the plan from this command — the user decides what to revise."
- **INCONCLUSIVE** → "Result is too noisy to decide. Tighten the smoke (more samples, finer dt, etc.) and re-run. Until then, treat the assumption as unverified."

Do not route into `/gpd:new-project`, `/gpd:plan-phase`, `/gpd:execute-phase`, or any other workflow automatically. State the recommended next command and stop. Smoke is a gate, not a launcher.
</step>

<step name="guardrails">
- Smoke is pre-project. Never create `GPD/`, `state.json`, `PROJECT.md`, or any GPD scaffolding from this command.
- Smoke is single-claim. Do not chain into a second smoke or a parameter sweep in the same invocation.
- Smoke is honest about scope. A PASS at 16×16 Ising does not mean the full critical-exponent study will work — only that the foundational pipeline is sound. Say so.
- Never fabricate the measured value. If the run failed or was killed, the verdict is missing, not PASS.
- If the user proposes a claim without a published source ("I think the answer is ~5"), accept it but label the verdict as a self-consistency check, not a reproduction.
</step>

</process>

<success_criteria>
- [ ] The claim is captured as a structured quantitative anchor with units and a source
- [ ] The minimal setup is the smallest variant that could plausibly reproduce the claim
- [ ] The user confirms the proposal before any code is written
- [ ] The script runs in the working directory without creating GPD scaffolding
- [ ] The verdict is a three-line PASS/FAIL/INCONCLUSIVE block grounded in the measured number
- [ ] No automatic routing into `/gpd:new-project`; the user must invoke it explicitly
</success_criteria>
