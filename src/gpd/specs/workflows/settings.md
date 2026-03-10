<purpose>
Interactive configuration of GPD workflow agents (research, plan_check, verifier), research profile selection, and physics-specific settings via multi-question prompt. Updates .gpd/config.json with user preferences including unit systems, conventions, precision, and preferred computational tools.
</purpose>

<required_reading>
Read all files referenced by the invoking prompt's execution_context before starting.
</required_reading>

<process>

<step name="ensure_and_load_config">
Ensure config exists and load current state:

```bash
gpd config ensure-section
INIT=$(gpd init progress --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Creates `.gpd/config.json` with defaults if missing and loads current config values.
</step>

<step name="read_current">
```bash
cat .gpd/config.json
```

Parse current values (default to `true` / first option if not present):

- `autonomy` -- human-in-the-loop level: `"supervised"`, `"guided"` (default), `"autonomous"`, `"yolo"`
- `research_mode` -- research strategy: `"explore"`, `"balanced"` (default), `"exploit"`, `"adaptive"`
- `workflow.research` -- spawn researcher during plan-phase
- `workflow.plan_checker` -- spawn plan checker during plan-phase
- `workflow.verifier` -- spawn verifier during execute-phase
- `workflow.verify_between_waves` -- inter-wave verification gates (default: `"auto"`)
- `parallelization` -- execute wave plans in parallel (default: `true`)
- `model_profile` -- which research mode profile (default: `review`)
- `git.branching_strategy` -- branching approach (default: `"none"`)
- `physics.unit_system` -- unit convention (default: `"natural"`)
- `physics.metric_signature` -- spacetime metric (default: `"mostly_minus"`)
- `physics.default_precision` -- numerical precision (default: `"double"`)
- `physics.preferred_tools` -- computational tools (default: `["python", "numpy", "scipy"]`)
- `physics.fourier_convention` -- Fourier transform sign (default: `"physics"`)
  </step>

<step name="present_settings">

> **Platform note:** If `AskUserQuestion` is not available, present these options in plain text and wait for the user's freeform response.

Use AskUserQuestion with current values pre-selected:

```
AskUserQuestion([
  {
    question: "How much autonomy should the AI have?",
    header: "Autonomy",
    multiSelect: false,
    options: [
      { label: "Supervised", description: "Checkpoint after every task. You approve each step." },
      { label: "Guided (Recommended)", description: "AI executes routine tasks, checkpoints on physics decisions" },
      { label: "Autonomous", description: "AI drives the research loop. You review at phase boundaries." },
      { label: "YOLO", description: "Maximum speed. AI makes all decisions. Only hard stops on failures." }
    ]
  },
  {
    question: "Research strategy?",
    header: "Research Mode",
    multiSelect: false,
    options: [
      { label: "Explore", description: "Broad literature search, multiple hypothesis branches, compare approaches" },
      { label: "Balanced (Recommended)", description: "Standard: plan one approach, execute, verify, iterate" },
      { label: "Exploit", description: "Focused execution of known methodology. Minimal branching, fast convergence." },
      { label: "Adaptive", description: "Start exploring, auto-switch to exploit once approach is validated" }
    ]
  },
  {
    question: "Which research profile for agents?",
    header: "Research Profile",
    multiSelect: false,
    options: [
      { label: "Deep Theory", description: "Rigorous derivations, formal proofs, exact results (highest cost)" },
      { label: "Numerical", description: "Computational implementation, optimization, convergence" },
      { label: "Exploratory (Recommended)", description: "Rapid prototyping, hypothesis testing, parameter scanning" },
      { label: "Review", description: "Critical assessment, error checking, literature comparison (highest cost)" },
      { label: "Paper Writing", description: "LaTeX production, figures, narrative flow" }
    ]
  },
  {
    question: "Unit system?",
    header: "Units",
    multiSelect: false,
    options: [
      { label: "Natural units (hbar=c=1)", description: "Standard for HEP, quantum gravity, cosmology" },
      { label: "Natural units (hbar=c=k_B=1)", description: "Includes Boltzmann constant, for thermal field theory" },
      { label: "SI", description: "International System of Units, standard for experimental physics" },
      { label: "CGS-Gaussian", description: "Common in EM, astrophysics, older condensed matter literature" },
      { label: "Atomic units (hbar=e=m_e=1)", description: "Standard for atomic/molecular physics, quantum chemistry" },
      { label: "Lattice units", description: "Dimensionless, for lattice field theory and simulations" },
      { label: "Custom", description: "Specify your own unit conventions" }
    ]
  },
  {
    question: "Metric signature convention?",
    header: "Metric",
    multiSelect: false,
    options: [
      { label: "Mostly minus (+,-,-,-)", description: "Particle physics convention (Peskin & Schroeder, Weinberg)" },
      { label: "Mostly plus (-,+,+,+)", description: "GR/string theory convention (MTW, Wald, Polchinski)" },
      { label: "Euclidean (+,+,+,+)", description: "Lattice field theory, statistical mechanics" },
      { label: "N/A", description: "Non-relativistic or no spacetime metric needed" }
    ]
  },
  {
    question: "Fourier transform convention?",
    header: "Fourier",
    multiSelect: false,
    options: [
      { label: "Physics: exp(-iwt), 1/(2pi) on k-integral", description: "Standard physics convention" },
      { label: "Mathematics: exp(+iwt), 1/(2pi) on x-integral", description: "Pure math, some engineering" },
      { label: "Symmetric: 1/sqrt(2pi) on both", description: "Quantum mechanics textbooks (Griffiths, Shankar)" },
      { label: "N/A", description: "No Fourier transforms needed" }
    ]
  },
  {
    question: "Default numerical precision?",
    header: "Precision",
    multiSelect: false,
    options: [
      { label: "Single (float32)", description: "GPU calculations, quick estimates, ML workloads" },
      { label: "Double (float64)", description: "Standard scientific computing (recommended)" },
      { label: "Quad (float128)", description: "High-precision: cancellation-prone calculations, RG flows, near-critical systems" },
      { label: "Arbitrary (mpmath)", description: "Variable precision: number theory, special function evaluation, debugging" }
    ]
  },
  {
    question: "Preferred computational tools?",
    header: "Tools",
    multiSelect: true,
    options: [
      { label: "Python + NumPy/SciPy", description: "General scientific computing" },
      { label: "Mathematica", description: "Symbolic computation, exact results" },
      { label: "Julia", description: "High-performance numerical computing" },
      { label: "C/C++", description: "Performance-critical simulations" },
      { label: "Fortran", description: "Legacy HPC codes, LAPACK-heavy work" },
      { label: "MATLAB", description: "Matrix computations, signal processing" },
      { label: "SymPy", description: "Python symbolic math" },
      { label: "Maple", description: "Computer algebra, differential equations" },
      { label: "FORM", description: "Large-scale symbolic manipulation (Feynman diagrams)" },
      { label: "Cadabra", description: "Tensor algebra, field theory" },
      { label: "xAct", description: "Tensor computer algebra in Mathematica" }
    ]
  },
  {
    question: "Spawn Plan Researcher? (researches domain before planning)",
    header: "Research",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Research phase goals before planning" },
      { label: "No", description: "Skip research, plan directly" }
    ]
  },
  {
    question: "Spawn Plan Checker? (verifies plans before execution)",
    header: "Plan Check",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Verify plans meet phase goals" },
      { label: "No", description: "Skip plan verification" }
    ]
  },
  {
    question: "Spawn Execution Verifier? (verifies phase completion)",
    header: "Verifier",
    multiSelect: false,
    options: [
      { label: "Yes", description: "Verify must-haves after execution" },
      { label: "No", description: "Skip post-execution verification" }
    ]
  },
  {
    question: "Run inter-wave verification gates during execution?",
    header: "Wave Verify",
    multiSelect: false,
    options: [
      { label: "Auto (Recommended)", description: "Profile-dependent: enabled for deep-theory/review, disabled for exploratory/numerical/paper-writing" },
      { label: "Always", description: "Run dimensional analysis + convention checks between every wave" },
      { label: "Never", description: "Skip inter-wave checks for fastest execution" }
    ]
  },
  {
    question: "Execute plans within a wave in parallel?",
    header: "Parallel",
    multiSelect: false,
    options: [
      { label: "Yes (Recommended)", description: "Plans in the same wave run concurrently via parallel Task() calls" },
      { label: "No", description: "Plans execute sequentially within each wave" }
    ]
  },
  {
    question: "Git branching strategy?",
    header: "Branching",
    multiSelect: false,
    options: [
      { label: "None (Recommended)", description: "Commit directly to current branch" },
      { label: "Per Phase", description: "Create branch for each phase (gpd/phase-{N}-{name})" },
      { label: "Per Milestone", description: "Create branch for entire milestone (gpd/{version}-{name})" }
    ]
  }
])
```

</step>

<step name="update_config">
Merge new settings into existing config.json:

```json
{
  ...existing_config,
  "autonomy": "supervised" | "guided" | "autonomous" | "yolo",
  "research_mode": "explore" | "balanced" | "exploit" | "adaptive",
  "model_profile": "deep-theory" | "numerical" | "exploratory" | "review" | "paper-writing",
  "parallelization": true/false,
  "workflow": {
    "research": true/false,
    "plan_checker": true/false,
    "verifier": true/false,
    "verify_between_waves": "auto" | true | false
  },
  "physics": {
    "unit_system": "natural" | "natural_thermal" | "si" | "cgs" | "atomic" | "lattice" | "custom",
    "metric_signature": "mostly_minus" | "mostly_plus" | "euclidean" | "na",
    "fourier_convention": "physics" | "math" | "symmetric" | "na",
    "default_precision": "single" | "double" | "quad" | "arbitrary",
    "preferred_tools": ["python", "mathematica", "julia", ...]
  },
  "git": {
    "branching_strategy": "none" | "phase" | "milestone"
  }
}
```

Write updated config to `.gpd/config.json`.
</step>

<step name="confirm">
Display:

```
+-----------------------------------------------------+
  GPD >> SETTINGS UPDATED
+-----------------------------------------------------+

| Setting              | Value |
|----------------------|-------|
| Research Profile     | {deep-theory/numerical/exploratory/review/paper-writing} |
| Unit System          | {natural/SI/CGS/atomic/lattice/custom} |
| Metric Signature     | {(+,-,-,-) / (-,+,+,+) / Euclidean / N/A} |
| Fourier Convention   | {physics/math/symmetric/N/A} |
| Default Precision    | {single/double/quad/arbitrary} |
| Preferred Tools      | {tool1, tool2, ...} |
| Plan Researcher      | {On/Off} |
| Plan Checker         | {On/Off} |
| Execution Verifier   | {On/Off} |
| Inter-Wave Verify    | {Auto/Always/Never} |
| Parallelization      | {On/Off} |
| Git Branching        | {None/Per Phase/Per Milestone} |

These settings apply to future $gpd-plan-phase and $gpd-execute-phase runs.

Quick commands:
- $gpd-set-profile <profile> -- switch research profile
- $gpd-plan-phase --research -- force research
- $gpd-plan-phase --skip-research -- skip research
- $gpd-plan-phase --skip-verify -- skip plan check
```

</step>

</process>

<downstream_consumption>
Physics convention settings from config.json are consumed by:

- **gpd-planner**: Uses metric_signature, fourier_convention, unit_system to set notation in PLAN.md task contexts
- **gpd-executor**: Reads conventions from config to verify consistency during execution
- **gpd-verifier**: Checks results against stated conventions (e.g., correct metric signature in tensor expressions)
- **gpd-consistency-checker**: Cross-references convention settings against actual usage in phase outputs

These settings propagate via the `<context>` sections in PLAN.md files, where conventions are listed explicitly for each task.
</downstream_consumption>

<success_criteria>

- [ ] Current config read
- [ ] User presented with 12 settings (profile + 5 physics conventions + 5 workflow toggles + git branching)
- [ ] Config updated with model_profile, workflow, physics, and git sections
- [ ] Physics conventions (units, metric, Fourier, precision, tools) stored for consistent use across all agents
- [ ] Changes confirmed to user

</success_criteria>
