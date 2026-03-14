<overview>
Research plans execute automatically when no checkpoint is required. Checkpoints formalize interaction points where human verification, physical judgment, or decisions are needed.

**Core principle:** The assistant automates all computation, derivation, and analysis. Checkpoints are for verification of physical reasoning and decisions about research direction, not manual calculation.

**Golden rules:**

1. **If the assistant can compute it, the assistant computes it** - Never ask user to run integrals, solve ODEs, or evaluate limits by hand
2. **The assistant sets up the verification environment** - Run simulations, generate plots, prepare numerical checks
3. **User only does what requires physical judgment** - "Does this phase diagram look physical?", "Is this the right regime?", "Does this limiting behavior make sense?"
4. **Domain expertise comes from user, computation comes from the assistant** - Ask for physical constraints, then the assistant implements them
   </overview>

<checkpoint_types>

<type name="human-verify">
## checkpoint:human-verify (Most Common - 90%)

**When:** The assistant completed automated calculation/analysis, human confirms physical correctness.

**Use for:**

- Verifying limiting cases match physical intuition
- Checking that plots show expected qualitative behavior
- Confirming symmetry properties are preserved
- Validating order-of-magnitude estimates
- Reviewing whether approximations are justified in a given regime
- Assessing whether a result is physically reasonable

**Structure:**

```xml
<task type="checkpoint:human-verify" gate="blocking">
  <what-derived>[What the assistant computed, derived, or analyzed]</what-derived>
  <how-to-verify>
    [Exact checks to perform - limiting cases, plots, known results to compare against]
  </how-to-verify>
  <resume-signal>[How to continue - "confirmed", "yes", or describe issues]</resume-signal>
</task>
```

**Example: Dispersion Relation (shows key pattern: the assistant derives and checks BEFORE checkpoint)**

```xml
<task type="auto">
  <name>Derive phonon dispersion relation for diatomic chain</name>
  <files>derivations/diatomic_chain.py, notes/dispersion.tex</files>
  <action>Set up equations of motion for alternating masses m1, m2 with spring constant k. Solve eigenvalue problem for omega(q).</action>
  <verify>Two branches obtained (acoustic + optical). omega(q=0) for acoustic branch = 0.</verify>
  <done>Dispersion relation derived with acoustic and optical branches</done>
</task>

<task type="auto">
  <name>Generate dispersion plot and check limiting cases</name>
  <action>Plot omega(q) for both branches. Evaluate: q->0 limit, zone boundary q=pi/a, equal mass limit m1=m2.</action>
  <verify>Acoustic branch linear near q=0, optical branch flat near q=0. Equal mass limit recovers monatomic result with halved Brillouin zone.</verify>
  <done>Dispersion plotted with limiting cases verified numerically</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-derived>Phonon dispersion for diatomic chain - two branches with gap at zone boundary</what-derived>
  <how-to-verify>
    Review the dispersion plot and verify:
    1. Acoustic branch: starts at omega=0, increases monotonically to zone boundary
    2. Optical branch: finite frequency at q=0, decreases to zone boundary
    3. Band gap: gap between branches at q=pi/a equals sqrt(2k/m1) - sqrt(2k/m2) (for m1 > m2)
    4. Equal mass limit: gap closes, recovers monatomic chain with doubled unit cell
  </how-to-verify>
  <resume-signal>Type "confirmed" or describe physical issues</resume-signal>
</task>
```

**Example: Numerical Simulation Result**

```xml
<task type="auto">
  <name>Run Monte Carlo simulation of 2D Ising model</name>
  <files>simulations/ising_mc.py, data/magnetization.csv</files>
  <action>Implement Metropolis algorithm for L=32 lattice. Sweep temperature from T=1.0 to T=4.0 in steps of 0.1. Compute magnetization |m(T)| averaged over 10^4 sweeps after 10^3 thermalization sweeps.</action>
  <verify>Phase transition visible near T_c ~ 2.269. Magnetization drops from ~1 to ~0.</verify>
  <done>Simulation complete, magnetization vs temperature data collected</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-derived>Ising model magnetization curve showing phase transition near T_c = 2.269</what-derived>
  <how-to-verify>
    Examine the magnetization plot and verify:
    - Sharp drop near expected T_c = 2/ln(1+sqrt(2)) ~ 2.269
    - Low-T regime: |m| ~ 1 (ordered phase)
    - High-T regime: |m| ~ 0 (disordered phase)
    - Finite-size rounding is visible but transition location is correct
  </how-to-verify>
  <resume-signal>Type "confirmed" or describe issues with the simulation</resume-signal>
</task>
```

</type>

<type name="decision">
## checkpoint:decision (9%)

**When:** Human must make choice that affects research direction.

**Use for:**

- Choosing between physical models or approximation schemes
- Selecting which regime to investigate first
- Deciding on boundary conditions or gauge choices
- Prioritizing which observable to compute
- Choosing between analytical and numerical approaches

**Structure:**

```xml
<task type="checkpoint:decision" gate="blocking">
  <decision>[What's being decided]</decision>
  <context>[Why this decision matters for the research]</context>
  <options>
    <option id="option-a">
      <name>[Option name]</name>
      <pros>[Benefits]</pros>
      <cons>[Tradeoffs]</cons>
    </option>
    <option id="option-b">
      <name>[Option name]</name>
      <pros>[Benefits]</pros>
      <cons>[Tradeoffs]</cons>
    </option>
  </options>
  <resume-signal>[How to indicate choice]</resume-signal>
</task>
```

**Example: Approximation Scheme Selection**

```xml
<task type="checkpoint:decision" gate="blocking">
  <decision>Select approximation for electron self-energy</decision>
  <context>
    Need to compute quasiparticle lifetime in the interacting electron gas.
    Three approaches with different tradeoffs between accuracy and tractability.
  </context>
  <options>
    <option id="rpa">
      <name>Random Phase Approximation (RPA)</name>
      <pros>Captures long-range screening, exact in high-density limit, well-understood</pros>
      <cons>Misses short-range correlations, breaks down at low density</cons>
    </option>
    <option id="gw">
      <name>GW Approximation</name>
      <pros>Systematic improvement over RPA, good for quasiparticle properties, widely benchmarked</pros>
      <cons>Computationally heavier, vertex corrections missing, self-consistency issues</cons>
    </option>
    <option id="tmatrix">
      <name>T-matrix Approximation</name>
      <pros>Captures pairing fluctuations, better at low density, includes ladder diagrams</pros>
      <cons>Less standard, misses screening, harder to benchmark</cons>
    </option>
  </options>
  <resume-signal>Select: rpa, gw, or tmatrix</resume-signal>
</task>
```

**Example: Regime Selection**

```xml
<task type="checkpoint:decision" gate="blocking">
  <decision>Select parameter regime for initial investigation</decision>
  <context>
    The model has three regimes with qualitatively different physics.
    Each requires different analytical techniques. Start with one, extend later.
  </context>
  <options>
    <option id="weak-coupling">
      <name>Weak coupling (g << 1)</name>
      <pros>Perturbation theory applicable, systematic expansion, can benchmark against known results</pros>
      <cons>Interesting non-perturbative physics missed, may not capture phase transition</cons>
    </option>
    <option id="strong-coupling">
      <name>Strong coupling (g >> 1)</name>
      <pros>Novel physics, strong-coupling expansion possible, dual description may simplify</pros>
      <cons>Less controlled, harder to validate, fewer known benchmarks</cons>
    </option>
    <option id="critical">
      <name>Critical regime (g ~ g_c)</name>
      <pros>Universal behavior, RG techniques applicable, experimentally relevant</pros>
      <cons>Most technically challenging, requires careful treatment of fluctuations</cons>
    </option>
  </options>
  <resume-signal>Select: weak-coupling, strong-coupling, or critical</resume-signal>
</task>
```

</type>

<type name="human-action">
## checkpoint:human-action (1% - Rare)

**When:** Action has no programmatic equivalent and requires human-only interaction, OR the assistant hit a resource gate during computation.

**Use ONLY for:**

- **Authentication gates** - The assistant tried API/CLI but needs credentials for HPC cluster or licensed software
- Accessing proprietary experimental data behind institutional login
- Running licensed software (e.g., VASP, Gaussian) that requires a local license
- Manual instrument configuration for experimental data collection
- Accessing paywalled journal articles for comparison

**Do NOT use for pre-planned manual work:**

- Running simulations (use Python, Julia, or appropriate CLI)
- Plotting results (use matplotlib, gnuplot, etc.)
- LaTeX compilation (use pdflatex/latexmk)
- Data analysis (use pandas, numpy, scipy)

**Structure:**

```xml
<task type="checkpoint:human-action" gate="blocking">
  <action>[What human must do - the assistant already did everything automatable]</action>
  <instructions>
    [What the assistant already automated]
    [The ONE thing requiring human action]
  </instructions>
  <verification>[What the assistant can check afterward]</verification>
  <resume-signal>[How to continue]</resume-signal>
</task>
```

**Example: HPC Job Submission**

```xml
<task type="auto">
  <name>Prepare DFT input files for cluster</name>
  <action>Generate Quantum ESPRESSO input files for the 20 k-point configurations. Create SLURM submission script with appropriate resource requests.</action>
  <verify>All .in files parse correctly with pw.x --check. SLURM script has valid syntax.</verify>
  <done>Input files and submission script ready in cluster_jobs/</done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <action>Submit jobs to HPC cluster (requires institutional credentials)</action>
  <instructions>
    I prepared all input files and the SLURM script in cluster_jobs/.
    Upload to your cluster and submit: sbatch run_all.sh
    Return the job IDs when submitted.
  </instructions>
  <verification>Job output files present and parseable</verification>
  <resume-signal>Paste job IDs or "submitted" when done</resume-signal>
</task>
```

**Example: Authentication Gate (Dynamic Checkpoint)**

```xml
<task type="auto">
  <name>Fetch experimental data from materials database</name>
  <files>data/experimental/</files>
  <action>Query Materials Project API for band structures of target compounds</action>
  <verify>JSON responses contain band structure data</verify>
</task>

<!-- If API returns "Error: Invalid API key", the assistant creates checkpoint on the fly -->

<task type="checkpoint:human-action" gate="blocking">
  <action>Provide Materials Project API key so I can fetch experimental data</action>
  <instructions>
    I tried to query the Materials Project API but need authentication.
    Get your API key from: https://materialsproject.org/api
    Paste the key here.
  </instructions>
  <verification>I'll query with the key and verify data retrieval</verification>
  <resume-signal>Paste your API key</resume-signal>
</task>

<!-- After authentication, the assistant retries the query -->

<task type="auto">
  <name>Retry Materials Project data fetch</name>
  <action>Query API with provided key for band structures</action>
  <verify>Band structure data retrieved for all target compounds</verify>
</task>
```

**Key distinction:** Auth gates are created dynamically when the assistant encounters auth errors. NOT pre-planned -- the assistant automates first, asks for credentials only when blocked.
</type>
</checkpoint_types>

<execution_protocol>

## Required Checkpoint Payload

Every authored or auto-inserted checkpoint must return a bounded execution payload, not only prose. The payload must include:

- `checkpoint_id`
- `checkpoint_type`
- `checkpoint_reason` (`explicit`, `first_result`, `segment_boundary`, `pre_fanout`, `context_pressure`, or `manual`)
- `awaiting` (what the user or orchestrator must provide)
- `verification_prework_done`
- `resume_contract` (what must be true before continuation)
- `success_path`
- `issue_path`
- `execution_segment` with current cursor, completed tasks, current task, and resume preconditions

When the stop is a first-result, skeptical, or pre-fanout review, the `execution_segment` must also carry the live gate fields that keep resume/status surfaces honest: `first_result_gate_pending`, `pre_fanout_review_pending`, `pre_fanout_review_cleared` when applicable, `skeptical_requestioning_required`, and `downstream_locked`.

This keeps authored checkpoints and auto-inserted Stage 5 checkpoints on the same continuation path.

Clear transitions are reason-scoped. Clearing `first_result` must not erase `pre_fanout` or skeptical fields, and `fanout unlock` must not clear a live pre-fanout review on its own. A pre-fanout stop is only retired after the matching review clear and fanout unlock have both been observed.

When the assistant encounters `type="checkpoint:*"`:

1. **Stop immediately** - do not proceed to next task
2. **Display checkpoint clearly** using the format below
3. **Wait for user response** - do not hallucinate completion
4. **Verify if possible** - check equations, run numerical tests, whatever is specified
5. **Resume execution** - continue to next task only after confirmation

**For checkpoint:human-verify:**

```
+================================================+
|  CHECKPOINT: Verification Required             |
+================================================+

Progress: 5/8 tasks complete
Task: Phonon dispersion relation

Derived: Diatomic chain dispersion with acoustic and optical branches

How to verify:
  1. Acoustic branch: omega -> 0 as q -> 0 (Goldstone mode)
  2. Optical branch: finite gap at q = 0, value = sqrt(2k(1/m1 + 1/m2))
  3. Band gap at zone boundary consistent with mass ratio
  4. Equal mass limit recovers monatomic chain

-------------------------------------------------
> YOUR ACTION: Type "confirmed" or explain issues
-------------------------------------------------
```

**For checkpoint:decision:**

```
+================================================+
|  CHECKPOINT: Decision Required                 |
+================================================+

Progress: 2/6 tasks complete
Task: Select approximation scheme

Decision: Which approximation for the self-energy?

Context: Need quasiparticle lifetime. Three approaches with different validity ranges.

Options:
  1. rpa - Random Phase Approximation
     Pros: Exact in high-density limit, captures screening
     Cons: Misses short-range correlations

  2. gw - GW Approximation
     Pros: Systematic, good for quasiparticles
     Cons: Heavier computation, missing vertex corrections

  3. tmatrix - T-matrix Approximation
     Pros: Captures pairing, better at low density
     Cons: Less standard, misses screening

-------------------------------------------------
> YOUR ACTION: Select rpa, gw, or tmatrix
-------------------------------------------------
```

**For checkpoint:human-action:**

```
+================================================+
|  CHECKPOINT: Action Required                   |
+================================================+

Progress: 3/8 tasks complete
Task: Fetch experimental band structures

Attempted: Materials Project API query
Error: Invalid API key

What you need to do:
  1. Go to: https://materialsproject.org/api
  2. Copy your API key
  3. Paste it here

I'll verify: API returns band structure data for target compounds

-------------------------------------------------
> YOUR ACTION: Paste your API key
-------------------------------------------------
```

</execution_protocol>

<authentication_gates>

**Auth gate = the assistant tried API/CLI, got auth error.** Not a failure -- a gate requiring human input to unblock.

**Pattern:** The assistant tries automation -> auth error -> creates checkpoint:human-action -> user authenticates -> the assistant retries -> continues

**Gate protocol:**

1. Recognize it's not a failure - missing auth for research databases/HPC is expected
2. Stop current task - don't retry repeatedly
3. Create checkpoint:human-action dynamically
4. Provide exact authentication steps
5. Verify authentication works
6. Retry the original task
7. Continue normally

**Key distinction:**

- Pre-planned checkpoint: "I need you to run this simulation" (wrong - the assistant should automate)
- Auth gate: "I tried to query the database but need credentials" (correct - unblocks automation)

</authentication_gates>

<automation_reference>

**The rule:** If it can be computed programmatically, the assistant computes it. Never ask the researcher to perform automatable work.

## Research Tool Reference

| Tool               | CLI/API              | Key Operations                                   | Auth Gate       |
| ------------------ | -------------------- | ------------------------------------------------ | --------------- |
| Python/NumPy/SciPy | `python`             | Numerical computation, ODE solving, optimization | N/A             |
| Mathematica        | `wolframscript`      | Symbolic computation, exact solutions            | License check   |
| LaTeX              | `pdflatex`/`latexmk` | Document compilation, equation rendering         | N/A             |
| Jupyter            | `jupyter`            | Interactive notebooks, inline plots              | N/A             |
| matplotlib         | Python library       | Plotting, visualization                          | N/A             |
| Materials Project  | REST API             | Crystal structures, band data                    | API key         |
| OEIS               | REST API             | Integer sequence lookup                          | N/A             |
| arXiv              | REST API             | Paper search, abstract retrieval                 | N/A             |
| Git                | `git`                | Version control for research                     | N/A             |
| GitHub             | `gh`                 | Repository management, collaboration             | `gh auth login` |

## Data Analysis Automation

**Data files:** Use Python (pandas, numpy) to read, process, and analyze. Never ask human to manipulate data manually.

**Plotting:**

| Library    | Use Case                  | Example                           |
| ---------- | ------------------------- | --------------------------------- |
| matplotlib | Publication-quality plots | Phase diagrams, dispersion curves |
| seaborn    | Statistical visualization | Correlation plots, distributions  |
| plotly     | Interactive exploration   | 3D surfaces, parameter sweeps     |

**Symbolic computation pattern:**

```xml
<!-- WRONG: Asking user to evaluate an integral -->
<task type="checkpoint:human-action">
  <action>Evaluate the Matsubara sum</action>
  <instructions>Compute sum_n 1/(i*omega_n - epsilon_k) using contour integration</instructions>
</task>

<!-- RIGHT: The assistant computes, user verifies physics -->
<task type="auto">
  <name>Evaluate Matsubara frequency sum</name>
  <action>Use contour integration to evaluate sum_n 1/(i*omega_n - epsilon_k). Verify against known Fermi function result.</action>
  <verify>Result equals n_F(epsilon_k) = 1/(exp(beta*epsilon_k) + 1)</verify>
</task>
```

## Simulation Automation

| Framework        | Start Command                 | Typical Output     | Default |
| ---------------- | ----------------------------- | ------------------ | ------- |
| Python script    | `python simulate.py`          | Data files, plots  | N/A     |
| Jupyter notebook | `jupyter nbconvert --execute` | Executed notebook  | N/A     |
| MCP server       | `uv run mcp-server`           | Simulation results | N/A     |
| Quantum ESPRESSO | `pw.x < input.in`             | SCF output         | N/A     |

## CLI Installation Handling

| Tool         | Auto-install?      | Command                              |
| ------------ | ------------------ | ------------------------------------ |
| pip packages | Ask user first     | `pip install numpy scipy matplotlib` |
| uv packages  | Ask user first     | `uv add package-name`                |
| LaTeX        | No - ask user      | Platform-dependent (texlive, mactex) |
| Mathematica  | No - licensed      | User must have license               |
| HPC tools    | No - institutional | User must have access                |

**Protocol:** Try tool -> "not found" -> ask the user before any install attempt -> if approved, install and retry -> if not approved, checkpoint with the missing-tool guidance.

## Pre-Checkpoint Computation Failures

| Failure                     | Response                                                                  |
| --------------------------- | ------------------------------------------------------------------ |
| Numerical instability       | Check parameters, add regularization, retry (don't proceed to checkpoint) |
| Convergence failure         | Adjust tolerance or initial conditions, retry                             |
| Missing dependency          | Ask user before install; if approved, install via pip/uv and retry        |
| Derivation error            | Fix the algebra first (bug, not checkpoint issue)                         |
| Auth error                  | Create auth gate checkpoint                                               |
| Timeout on long computation | Optimize algorithm or reduce problem size, then retry                     |

**Never present a checkpoint with broken results.** If the simulation diverged, don't ask user to "verify the phase transition." Fix the computation first.

```xml
<!-- WRONG: Checkpoint with broken computation -->
<task type="checkpoint:human-verify">
  <what-derived>Energy spectrum (simulation diverged at t=50)</what-derived>
  <how-to-verify>Check if spectrum looks physical...</how-to-verify>
</task>

<!-- RIGHT: Fix first, then checkpoint -->
<task type="auto">
  <name>Fix numerical instability in time evolution</name>
  <action>Reduce time step from dt=0.1 to dt=0.01, add energy conservation check</action>
  <verify>Energy conserved to 10^-6 over full simulation time</verify>
</task>

<task type="checkpoint:human-verify">
  <what-derived>Energy spectrum - converged simulation with energy conservation to 10^-6</what-derived>
  <how-to-verify>Verify spectrum shows expected level spacing statistics...</how-to-verify>
</task>
```

## Automatable Quick Reference

| Action                                  | Automatable?              | Assistant does it? |
| --------------------------------------- | ------------------------- | ------------------ |
| Solve differential equation numerically | Yes (scipy)               | YES                |
| Evaluate integral symbolically          | Yes (sympy/wolframscript) | YES                |
| Generate publication plot               | Yes (matplotlib)          | YES                |
| Run Monte Carlo simulation              | Yes (Python)              | YES                |
| Compile LaTeX document                  | Yes (pdflatex)            | YES                |
| Fit data to model                       | Yes (scipy.optimize)      | YES                |
| Search literature on arXiv              | Yes (API)                 | YES                |
| Query materials database                | Yes (API + auth)          | YES                |
| Submit to HPC cluster                   | No (credentials)          | NO                 |
| Verify plot looks physically reasonable | No (judgment)             | NO                 |
| Decide which regime to study            | No (research direction)   | NO                 |
| Assess if approximation is justified    | No (physical judgment)    | NO                 |

</automation_reference>

<writing_guidelines>

**DO:**

- Automate all computation before checkpoint
- Be specific: "Check that conductivity diverges as 1/omega at low frequency" not "check the result"
- Number verification steps
- State expected physical outcomes: "You should see a linear dispersion at small q"
- Provide context: why this checkpoint matters for the physics

**DON'T:**

- Ask human to do computation the assistant can automate
- Assume knowledge: "Check the usual limits"
- Skip steps: "Verify the result" (too vague)
- Mix multiple unrelated verifications in one checkpoint

**Placement:**

- **After computation completes** - not before the assistant does the derivation
- **After key physical results obtained** - before building further theory on them
- **Before dependent calculations** - decisions before choosing approximation scheme
- **At physical interpretation points** - after obtaining numbers that need physical judgment

**Bad placement:** Before computation | Too frequent | Too late (dependent results already used the answer)
</writing_guidelines>

<examples>

### Example 1: Numerical Computation (No Checkpoint Needed)

```xml
<task type="auto">
  <name>Compute ground state energy of harmonic oscillator via variational method</name>
  <files>calculations/variational_ho.py</files>
  <action>
    1. Use Gaussian trial wavefunction psi = exp(-alpha*x^2)
    2. Compute <H> = <T> + <V> analytically as function of alpha
    3. Minimize over alpha
    4. Compare with exact E_0 = hbar*omega/2
  </action>
  <verify>
    - Optimal alpha = m*omega/(2*hbar)
    - Variational energy equals exact ground state energy (Gaussian is exact for HO)
    - Numerical value matches to machine precision
  </verify>
  <done>Variational ground state energy computed, matches exact result</done>
</task>

<!-- NO CHECKPOINT NEEDED - the assistant computed everything and verified programmatically against known result -->
```

### Example 2: Full Derivation Flow (Single checkpoint at end)

```xml
<task type="auto">
  <name>Derive Lindhard function for free electron gas</name>
  <files>derivations/lindhard.py, notes/lindhard.tex</files>
  <action>Compute chi_0(q, omega) by evaluating the polarization bubble diagram</action>
  <verify>Imaginary part gives correct particle-hole continuum boundaries</verify>
</task>

<task type="auto">
  <name>Evaluate static limit and long-wavelength limit</name>
  <files>derivations/lindhard_limits.py</files>
  <action>Take omega->0 for static screening, q->0 for plasmon pole</action>
  <verify>Static limit gives Thomas-Fermi screening, q->0 gives plasma frequency</verify>
</task>

<task type="auto">
  <name>Generate Lindhard function plots</name>
  <files>plots/lindhard_real_imag.py</files>
  <action>Plot Re[chi] and Im[chi] as functions of omega for several q values. Mark particle-hole continuum boundaries.</action>
  <verify>Plots generated without errors, axes labeled, boundaries marked</verify>
  <done>Lindhard function plotted for multiple q values</done>
</task>

<!-- ONE checkpoint at end verifies the complete physics -->
<task type="checkpoint:human-verify" gate="blocking">
  <what-derived>Complete Lindhard function analysis - analytical expression + limiting cases + plots</what-derived>
  <how-to-verify>
    1. Static limit: chi_0(q, 0) should recover Thomas-Fermi result at small q
    2. Plasmon pole: Re[chi_0(q->0, omega)] should diverge at omega = omega_p
    3. Particle-hole continuum: Im[chi_0] nonzero only inside the continuum
    4. Sum rule: integral of Im[chi_0]*omega over omega gives correct f-sum rule
    5. Plots: qualitative shape matches Mahan Fig. 5.1 or similar reference
  </how-to-verify>
  <resume-signal>Type "confirmed" or describe issues</resume-signal>
</task>
```

</examples>

<anti_patterns>

### BAD: Asking user to compute

```xml
<task type="checkpoint:human-action" gate="blocking">
  <action>Evaluate the Gaussian integral</action>
  <instructions>Compute integral of exp(-alpha*x^2) dx from -inf to +inf</instructions>
</task>
```

**Why bad:** The assistant can evaluate this integral. User should only judge physical content, not do computation.

### GOOD: The assistant computes, user verifies physics

```xml
<task type="auto">
  <name>Evaluate partition function integral</name>
  <action>Compute Z = integral exp(-beta*H) d^N q d^N p using Gaussian integration</action>
  <verify>Result gives correct ideal gas free energy F = -NkT*ln(V/lambda^3)</verify>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <what-derived>Partition function for interacting gas in mean-field approximation</what-derived>
  <how-to-verify>
    Verify that the free energy:
    1. Reduces to ideal gas in the non-interacting limit
    2. Has correct extensive scaling (proportional to N)
    3. Gives positive entropy at all temperatures
  </how-to-verify>
</task>
```

### BAD: Asking human to run simulation / GOOD: The assistant automates

```xml
<!-- BAD: Asking user to run code -->
<task type="checkpoint:human-action" gate="blocking">
  <action>Run the Monte Carlo simulation</action>
  <instructions>Execute: python ising_mc.py --L 32 --T_min 1.0 --T_max 4.0</instructions>
</task>

<!-- GOOD: The assistant runs, user verifies physics -->
<task type="auto">
  <name>Run Ising model simulation</name>
  <action>Execute python ising_mc.py with specified parameters. Collect data.</action>
  <verify>Output files exist, magnetization data has expected temperature range</verify>
</task>

<task type="checkpoint:human-verify">
  <what-derived>Ising model magnetization curve</what-derived>
  <how-to-verify>Phase transition visible near T_c = 2.269, correct ordered/disordered phases</how-to-verify>
  <resume-signal>Type "confirmed"</resume-signal>
</task>
```

### BAD: Too many checkpoints / GOOD: Single checkpoint

```xml
<!-- BAD: Checkpoint after every step -->
<task type="auto">Derive equations of motion</task>
<task type="checkpoint:human-verify">Check equations</task>
<task type="auto">Solve for normal modes</task>
<task type="checkpoint:human-verify">Check modes</task>
<task type="auto">Plot dispersion</task>
<task type="checkpoint:human-verify">Check plot</task>

<!-- GOOD: One checkpoint at end -->
<task type="auto">Derive equations of motion</task>
<task type="auto">Solve for normal modes</task>
<task type="auto">Plot dispersion and check limits</task>

<task type="checkpoint:human-verify">
  <what-derived>Complete normal mode analysis (equations + solutions + dispersion plot)</what-derived>
  <how-to-verify>Verify dispersion, check limiting cases, confirm mode counting</how-to-verify>
  <resume-signal>Type "confirmed"</resume-signal>
</task>
```

### BAD: Vague verification / GOOD: Specific physical checks

```xml
<!-- BAD -->
<task type="checkpoint:human-verify">
  <what-derived>Self-energy calculation</what-derived>
  <how-to-verify>Check it looks right</how-to-verify>
</task>

<!-- GOOD -->
<task type="checkpoint:human-verify">
  <what-derived>Electron self-energy in GW approximation at k_F</what-derived>
  <how-to-verify>
    Verify the self-energy:
    1. Im[Sigma] = 0 at the Fermi surface (quasiparticle is stable at E_F)
    2. Im[Sigma] ~ (E - E_F)^2 near E_F (Fermi liquid behavior)
    3. Re[Sigma] has correct sign (negative for electron gas)
    4. Spectral weight Z = 1/(1 - dRe[Sigma]/dE) is between 0 and 1
  </how-to-verify>
  <resume-signal>Type "confirmed" or describe physical issues</resume-signal>
</task>
```

### BAD: Asking user to manipulate data

```xml
<task type="checkpoint:human-action">
  <action>Extract peak positions from spectrum</action>
  <instructions>Open spectrum.csv and find the frequencies where peaks occur</instructions>
</task>
```

**Why bad:** The assistant can find peaks programmatically with scipy.signal.find_peaks.

</anti_patterns>

<summary>

Checkpoints formalize human-in-the-loop points for physical judgment and research decisions, not manual computation.

**The golden rule:** If the assistant CAN compute it, the assistant MUST compute it.

**Checkpoint priority:**

1. **checkpoint:human-verify** (90%) - The assistant computed everything, human confirms physical correctness and reasonableness
2. **checkpoint:decision** (9%) - Human makes research direction choices (approximations, regimes, models)
3. **checkpoint:human-action** (1%) - Truly unavoidable manual steps with no programmatic path (HPC credentials, licensed software)

**When NOT to use checkpoints:**

- Things the assistant can verify numerically (limiting cases, conservation laws, known results)
- Data manipulation (the assistant can read and process data)
- Algebraic correctness (symbolic computation tools handle this)
- Anything computable via Python/sympy/scipy/CLI

**See also:** `references/execution/execute-plan-checkpoints.md` — how checkpoints integrate into the plan execution workflow.
</summary>
