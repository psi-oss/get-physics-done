<overview>
Git integration for GPD framework.
</overview>

<core_principle>

**Commit results, not process.**

The git log should read like a record of established results and validated calculations, not a diary of research planning activity.
</core_principle>

<commit_points>

| Event                     | Commit? | Why                                         |
| ------------------------- | ------- | ------------------------------------------- |
| PROJECT + ROADMAP created | YES     | Research project initialization             |
| PLAN.md created           | NO      | Intermediate - commit with plan completion  |
| LITERATURE.md created     | NO      | Intermediate                                |
| EXPLORATION.md created    | NO      | Intermediate                                |
| **Task completed**        | YES     | Atomic unit of work (1 commit per task)     |
| **Plan completed**        | YES     | Metadata commit (SUMMARY + STATE + ROADMAP) |
| Handoff created           | YES     | WIP state preserved                         |

</commit_points>

<git_check>

```bash
[ -d .git ] && echo "GIT_EXISTS" || echo "NO_GIT"
```

If NO_GIT: Run `git init` silently. GPD research projects always get their own repo.
</git_check>

<commit_formats>

<format name="initialization">
## Project Initialization (brief + roadmap together)

```
docs: initialize [project-name] ([N] phases)

[One-liner from PROJECT.md]

Phases:
1. [phase-name]: [goal]
2. [phase-name]: [goal]
3. [phase-name]: [goal]
```

What to commit:

```bash
gpd commit "docs: initialize [project-name] ([N] phases)" --files .gpd/
```

</format>

<format name="task-completion">
## Task Completion (During Plan Execution)

Each task gets its own commit immediately after completion.

```
{type}({phase}-{plan}): {task-name}

- [Key result 1]
- [Key result 2]
- [Key result 3]
```

**Commit types:**

- `calc` - New calculation or derivation completed
- `fix` - Error correction in derivation or numerics
- `verify` - Verification task (hypothesis-driven research PREDICT phase)
- `simplify` - Reorganization or simplification of derivation or computation (hypothesis-driven research REFINE phase)
- `sim` - Simulation or numerical computation
- `data` - Data analysis, fitting, or processing
- `chore` - Dependencies, config, tooling

**Examples:**

```bash
# Standard calculation task
git add derivations/self_energy.py notes/self_energy.tex
git commit -m "calc(08-02): derive one-loop self-energy in GW approximation

- Evaluated polarization bubble with Lindhard function
- Obtained Im[Sigma] ~ (E-E_F)^2 near Fermi surface
- Spectral weight Z = 0.72 at r_s = 4
"

# Hypothesis-driven research - PREDICT phase
git add tests/test_dispersion_limits.py
git commit -m "verify(07-02): define expected limiting behavior for dispersion

- Acoustic branch must vanish linearly at q=0
- Optical branch gap must close when m1=m2
- Zone boundary frequencies must match analytical expressions
"

# Hypothesis-driven research - DERIVE phase
git add derivations/diatomic_dispersion.py
git commit -m "calc(07-02): derive diatomic chain dispersion relation

- Solved 2x2 eigenvalue problem for omega(q)
- Both branches satisfy all predicted limits
- Band gap expression matches Born-von Karman theory
"
```

</format>

<format name="plan-completion">
## Plan Completion (After All Tasks Done)

After all tasks committed, one final metadata commit captures plan completion.

```
docs({phase}-{plan}): complete [plan-name] plan

Tasks completed: [N]/[N]
- [Task 1 name]
- [Task 2 name]
- [Task 3 name]

SUMMARY: ${phase_dir}/{phase}-{plan}-SUMMARY.md
```

What to commit:

```bash
gpd commit "docs({phase}-{plan}): complete [plan-name] plan" --files ${phase_dir}/{phase}-{plan}-PLAN.md ${phase_dir}/{phase}-{plan}-SUMMARY.md .gpd/STATE.md .gpd/ROADMAP.md
```

**Note:** Calculation files NOT included - already committed per-task.

</format>

<format name="handoff">
## Handoff (WIP)

```
wip: [phase-name] paused at task [X]/[Y]

Current: [task name]
[If blocked:] Blocked: [reason]
[Key state:] Current parameter values: [...]
```

What to commit:

```bash
gpd commit "wip: [phase-name] paused at task [X]/[Y]" --files .gpd/
```

</format>
</commit_formats>

<example_log>

**Old approach (per-plan commits):**

```
a7f2d1 calc(transport): Boltzmann equation with phonon scattering
3e9c4b calc(bandstructure): tight-binding model with spin-orbit coupling
8a1b2c calc(screening): RPA dielectric function with local field corrections
5c3d7e calc(foundation): set up Hamiltonian and establish notation
2f4a8d docs: initialize electron-gas-transport (5 phases)
```

**New approach (per-task commits):**

```
# Phase 04 - Transport
1a2b3c docs(04-01): complete Boltzmann transport plan
4d5e6f calc(04-01): compute resistivity from scattering rates
7g8h9i sim(04-01): evaluate phonon-electron scattering matrix elements
0j1k2l calc(04-01): derive linearized Boltzmann equation

# Phase 03 - Bandstructure
3m4n5o docs(03-02): complete spin-orbit coupling plan
6p7q8r calc(03-02): compute band splittings at high-symmetry points
9s0t1u calc(03-02): add spin-orbit terms to tight-binding Hamiltonian
2v3w4x calc(03-01): construct tight-binding model from Wannier functions

# Phase 02 - Screening
5y6z7a docs(02-02): complete local field corrections plan
8b9c0d calc(02-02): evaluate local field factors G(q)
1e2f3g verify(02-02): define expected limits for dielectric function
4h5i6j docs(02-01): complete RPA screening plan
7k8l9m calc(02-01): derive Lindhard function and static screening
0n1o2p chore(02-01): set up numerical integration framework

# Phase 01 - Foundation
3q4r5s docs(01-01): complete Hamiltonian setup plan
6t7u8v calc(01-01): establish notation and second-quantized form
9w0x1y calc(01-01): define model parameters and physical constants
2z3a4b calc(01-01): write down full Hamiltonian with interactions

# Initialization
5c6d7e docs: initialize electron-gas-transport (5 phases)
```

Each plan produces 2-4 commits (tasks + metadata). Clear, granular, bisectable.

</example_log>

<anti_patterns>

**Still don't commit (intermediate artifacts):**

- PLAN.md creation (commit with plan completion)
- LITERATURE.md (intermediate)
- EXPLORATION.md (intermediate)
- Minor planning tweaks
- "Fixed typo in roadmap"

**Do commit (results):**

- Each task completion (calc/sim/verify/data/fix/simplify)
- Plan completion metadata (docs)
- Project initialization (docs)

**Key principle:** Commit validated results and established calculations, not research planning process.

</anti_patterns>

<commit_strategy_rationale>

## Why Per-Task Commits?

**Context engineering for AI:**

- Git history becomes primary context source for future AI sessions
- `git log --grep="{phase}-{plan}"` shows all work for a plan
- `git diff <hash>^..<hash>` shows exact changes per task
- Less reliance on parsing SUMMARY.md = more context for actual research

**Failure recovery:**

- Task 1 committed, Task 2 had an error
- The AI in next session: sees task 1 complete, can retry task 2 with correct approach
- Can `git reset --hard` to last validated result

**Debugging:**

- `git bisect` finds exact task where an error was introduced
- `git blame` traces a specific equation or parameter to its derivation context
- Each commit is independently revertable

**Research reproducibility:**

- Every intermediate result is preserved with full context
- Atomic commits make the logical progression of the research transparent
- "Commit noise" irrelevant when consumer is the AI, not humans scanning a log

</commit_strategy_rationale>
