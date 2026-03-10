---
template_version: 1
---

<!-- Used by: gpd-debugger agent. Template for debug session files. -->

# Debug Template

Template for `.gpd/debug/[slug].md` - active debug session tracking for physics calculations.

---

## File Template

```markdown
---
status: gathering | investigating | fixing | verifying | resolved
phase: [phase number or slug, e.g. "02-syk-sff"]
trigger: "[verbatim user input]"
created: [ISO timestamp]
updated: [ISO timestamp]
---

## Current Focus

<!-- OVERWRITE on each update - always reflects NOW -->

hypothesis: [current theory being tested]
test: [how testing it]
expecting: [what result means if true/false]
next_action: [immediate next step]

## Symptoms

<!-- Written during gathering, then immutable -->

expected: [what the calculation should produce]
actual: [what it actually produces]
discrepancy: [quantitative difference: magnitude, sign, units]
errors: [error messages, convergence failures, or NaN/inf occurrences]
reproduction: [how to trigger: which script, parameters, input values]
started: [when it broke / always broken / after which change]

## Eliminated

<!-- APPEND only - prevents re-investigating after /clear -->

- hypothesis: [theory that was wrong]
  evidence: [what disproved it]
  timestamp: [when eliminated]

## Evidence

<!-- APPEND only - facts discovered during investigation -->

- timestamp: [when found]
  checked: [what was examined: equation, code block, numerical output]
  found: [what was observed]
  implication: [what this means for the root cause]

## Diagnostic Tests

<!-- APPEND only - specific tests performed to isolate the issue -->

- test: [description of diagnostic test]
  command: [exact command or code snippet to reproduce]
  result: [output or observation]
  conclusion: [what this tells us]

## Resolution

<!-- OVERWRITE as understanding evolves -->

root_cause: [empty until found - e.g., sign error, missing factor of 2, wrong convention, index contraction error]
fix: [empty until applied]
verification: [empty until verified - limiting cases, cross-checks, numerical agreement]
lessons_learned: [empty until resolved - what pattern to watch for in future]
files_changed: []
```

---

<section_rules>

**Frontmatter (status, trigger, timestamps):**

- `status`: OVERWRITE - reflects current phase
- `phase`: IMMUTABLE - phase number or slug this debug session relates to (e.g., "02-syk-sff"); set from current phase context at creation time
- `trigger`: IMMUTABLE - verbatim user input, never changes
- `created`: IMMUTABLE - set once
- `updated`: OVERWRITE - update on every change

**Current Focus:**

- OVERWRITE entirely on each update
- Always reflects what GPD is doing RIGHT NOW
- If GPD reads this after /clear, it knows exactly where to resume
- Fields: hypothesis, test, expecting, next_action

**Symptoms:**

- Written during initial gathering phase
- IMMUTABLE after gathering complete
- Reference point for what we are trying to fix
- Fields: expected, actual, discrepancy, errors, reproduction, started
- `discrepancy` is critical for physics: quantify the difference (factor of 2? wrong sign? off by 10^3?)

**Eliminated:**

- APPEND only - never remove entries
- Prevents re-investigating dead ends after context reset
- Each entry: hypothesis, evidence that disproved it, timestamp
- Critical for efficiency across /clear boundaries

**Evidence:**

- APPEND only - never remove entries
- Facts discovered during investigation
- Each entry: timestamp, what checked, what found, implication
- Builds the case for root cause

**Diagnostic Tests:**

- APPEND only - never remove entries
- Specific reproducible tests performed to isolate the issue
- Each entry: description, exact command, result, conclusion
- Physics debugging often requires systematic parameter variation or limiting-case checks

**Resolution:**

- OVERWRITE as understanding evolves
- May update multiple times as fixes are tried
- Final state shows confirmed root cause and verified fix
- `lessons_learned` captures the pattern to watch for in future derivations
- Fields: root_cause, fix, verification, lessons_learned, files_changed

</section_rules>

<lifecycle>

**Creation:** Immediately when /gpd:debug is called

- Create file with trigger from user input
- Set status to "gathering"
- Current Focus: next_action = "gather symptoms"
- Symptoms: empty, to be filled

**During symptom gathering:**

- Update Symptoms section as user answers questions
- Quantify the discrepancy: magnitude, sign, units, functional form
- Update Current Focus with each question
- When complete: status -> "investigating"

**During investigation:**

- OVERWRITE Current Focus with each hypothesis
- APPEND to Evidence with each finding
- APPEND to Diagnostic Tests with each test performed
- APPEND to Eliminated when hypothesis disproved
- Common physics hypotheses to check systematically:
  - Sign errors (metric signature, Fourier convention, commutator vs anticommutator)
  - Missing factors (2pi, hbar, combinatorial factors, symmetry factors)
  - Wrong convention (active vs passive transformations, East Coast vs West Coast metric)
  - Index contraction errors (up vs down, summation range)
  - Approximation validity (is the expansion parameter actually small?)
  - Numerical issues (convergence, precision, discretization artifacts)
- Update timestamp in frontmatter

**During fixing:**

- status -> "fixing"
- Update Resolution.root_cause when confirmed
- Update Resolution.fix when applied
- Update Resolution.files_changed

**During verification:**

- status -> "verifying"
- Update Resolution.verification with results
- Check at least two independent validations:
  - Limiting case that should recover a known result
  - Numerical cross-check against independent computation or literature value
  - Dimensional analysis of the corrected expression
- If verification fails: status -> "investigating", try again

**On resolution:**

- status -> "resolved"
- Update Resolution.lessons_learned
- Move file to .gpd/debug/resolved/

</lifecycle>

<resume_behavior>

When GPD reads this file after /clear:

1. Parse frontmatter -> know status
2. Read Current Focus -> know exactly what was happening
3. Read Eliminated -> know what NOT to retry
4. Read Evidence -> know what has been learned
5. Read Diagnostic Tests -> know what has been tested
6. Continue from next_action

The file IS the debugging brain. GPD should be able to resume perfectly from any interruption point.

</resume_behavior>

<size_constraint>

Keep debug files focused:

- Evidence entries: 1-2 lines each, just the facts
- Eliminated: brief - hypothesis + why it failed
- Diagnostic Tests: command + result + one-line conclusion
- No narrative prose - structured data only

If evidence grows very large (10+ entries), consider whether you are going in circles. Check Eliminated to ensure you are not re-treading.

</size_constraint>
