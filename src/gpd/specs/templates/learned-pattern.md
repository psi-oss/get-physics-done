---
template_version: 1
---

# Learned Pattern Template

Template for `~/.gpd/learned-patterns/patterns-by-domain/{domain}/{category}-{slug}.md` -- a reusable error pattern captured from debugging or verification across GPD projects.

**Purpose:** Record a physics error pattern, convention pitfall, or recurring computational issue so that future projects can detect and prevent it before it causes problems.

For how patterns are managed, read, and written, see `@{GPD_INSTALL_DIR}/references/shared/cross-project-patterns.md`.

---

## File Template

```markdown
---
domain:
  [
    qft | condensed-matter | stat-mech | gr | amo | nuclear | classical | fluid | plasma | astro | mathematical | soft-matter | quantum-info,
  ]
category:
  [
    sign-error | factor-error | convention-pitfall | convergence-issue | approximation-failure | numerical-instability | conceptual-error | dimensional-error,
  ]
severity: [critical | high | medium | low]
confidence: [single_observation | confirmed | systematic]
first_seen: YYYY-MM-DD
last_seen: YYYY-MM-DD
occurrence_count: N
---

## Pattern: [Short descriptive title]

**What goes wrong:** [One-sentence description of the error]

**Why it happens:** [Root cause explanation]

**How to detect:** [What the verifier should look for]

**How to prevent:** [What the planner should include in plans]

**Example:** [Concrete example from a real calculation]

**Test value:** [A specific numerical test that would catch this error]
```

---

## Frontmatter Fields

| Field              | Values                                                                                                                          | Notes                                                |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| `domain`           | qft, condensed-matter, stat-mech, gr, amo, nuclear, classical, fluid, plasma, astro, mathematical, soft-matter, quantum-info     | Must match a subdirectory in `patterns-by-domain/`   |
| `category`         | sign-error, factor-error, convention-pitfall, convergence-issue, approximation-failure, numerical-instability, conceptual-error, dimensional-error | Classifies the type of error for filtering           |
| `severity`         | critical, high, medium, low                                                                                                     | How much damage this error causes if undetected      |
| `confidence`       | single_observation, confirmed, systematic                                                                                       | How well-established the pattern is across projects  |
| `first_seen`       | ISO date                                                                                                                        | When the pattern was first recorded                  |
| `last_seen`        | ISO date                                                                                                                        | Updated each time the pattern is observed again      |
| `occurrence_count` | Integer                                                                                                                         | Incremented each time, including within same project |

### Severity guidelines

- **critical:** Produces a wrong answer that passes superficial checks (e.g., wrong sign that still gives a "reasonable" magnitude). These are the most dangerous because they are hard to catch without specific knowledge.
- **high:** Produces a clearly wrong answer but may waste significant debugging time if the pattern is not recognized (e.g., missing factor of 2pi that makes a result off by ~6x).
- **medium:** Produces a suboptimal result or causes avoidable rework (e.g., convergence issues from a known-bad algorithm choice for this problem class).
- **low:** Minor issue that is usually caught quickly but worth documenting to save time (e.g., import convention that differs between two standard references).

### Confidence progression

- **single_observation:** Seen once in one project. May be project-specific rather than general. Worth recording but agents should apply judgment about relevance.
- **confirmed:** Seen independently in at least two different projects. The pattern is real and general. Agents should actively check for this.
- **systematic:** Seen 5+ times across 3+ projects with a well-understood root cause. Agents should treat this as a known hazard and include prevention in every relevant plan.

## Body Section Guidelines

### Pattern title

Short and descriptive. Should be recognizable at a glance when scanning a list of patterns.

- Good: "Metric signature sign flip in propagator denominators"
- Good: "Missing 1/(2pi) in momentum-space Fourier transform"
- Bad: "Sign error" (too vague)
- Bad: "Problem with the calculation of the self-energy in QED at one loop using dimensional regularization with the MS-bar scheme" (too specific)

### What goes wrong

One sentence. State the observable symptom, not the root cause.

- Good: "The retarded propagator has the wrong sign in the imaginary part, making it appear advanced."
- Bad: "The metric signature convention is inconsistent." (This is the cause, not the symptom.)

### Why it happens

Explain the root cause clearly enough that someone unfamiliar with the specific calculation can understand the mechanism. Include which conventions or choices lead to the error.

### How to detect

Concrete, actionable checks that the verifier can perform. Reference specific verification patterns from `@get-physics-done/references/verification/core/verification-core.md` (or the relevant domain file) where applicable.

- Good: "Check the sign of Im[G^R(omega)] for omega > 0. It must be negative (for the convention where G^R has a pole at omega - epsilon_k + i\*eta). If positive, the metric signature is likely flipped."
- Bad: "Check the propagator carefully." (Not actionable.)

### How to prevent

Concrete guidance for the planner to include in plans.

- Good: "Add a must_have physics_check: 'Verify Im[G^R(omega=1)] < 0 for a free particle with epsilon_k=0.5'. Include explicit metric signature declaration in the convention lock."
- Bad: "Be careful with signs." (Not actionable.)

### Example

A concrete instance from a real calculation. Include enough detail that the reader can see exactly where the error manifests. Strip project-specific context but preserve the physics.

### Test value

A specific numerical test that would catch this error. This is the most valuable field -- it turns a qualitative warning into a quantitative check.

- Good: "For a free scalar propagator with m=1 in natural units: G^R(omega=2, k=0) should have Im part = -pi*delta(omega^2 - m^2)/(2*omega). At omega=2, k=0: Im[G^R] = 0 (off-shell). At omega=1, k=0: Im[G^R] = -pi/(2\*1) = -1.5708. If you get +1.5708, the sign is wrong."
- Bad: "Check a known value." (Not a test.)

---

## Example

```markdown
---
domain: qft
category: sign-error
severity: critical
confidence: confirmed
first_seen: 2026-03-15
last_seen: 2026-03-15
occurrence_count: 3
---

## Pattern: Metric signature sign flip in propagator denominators

**What goes wrong:** The retarded Green's function has the wrong sign in its imaginary part, producing an advanced propagator that violates causality.

**Why it happens:** Mixing East Coast (-,+,+,+) and West Coast (+,-,-,-) metric conventions within the same derivation. The propagator denominator is p^2 - m^2 in one convention and m^2 - p^2 in the other. When the i\*epsilon prescription is applied, the sign of the imaginary part flips, turning a retarded propagator into an advanced one.

**How to detect:** Evaluate Im[G^R(omega, k=0)] for omega > m. The imaginary part must be negative for a retarded propagator (with the convention G^R ~ 1/(omega - epsilon_k + i\*eta)). If it is positive, the metric signature is inconsistent. Cross-check by verifying G^R(t < 0) = 0 in the time domain.

**How to prevent:** Add an explicit `metric_signature` field to STATE.md conventions at project initialization. Include a must_have physics_check that evaluates the propagator at a specific test point and verifies the sign of the imaginary part. Require all derivation files to state the convention in a comment at the top.

**Example:** In a one-loop self-energy calculation, the intermediate propagator was written as 1/(k^2 - m^2 + i\*epsilon) following Peskin & Schroeder (West Coast), but the external momentum routing used p_mu = (E, p) with E > 0 following the East Coast convention. The resulting self-energy had Im[Sigma] with the wrong sign, which was not caught until the optical theorem check failed.

**Test value:** Free scalar propagator, m=1 (natural units). At omega=1.5, k=0: the spectral function A(omega) = -2*Im[G^R(omega)] should be positive. Specifically, A(1.5, 0) = 2*pi*delta(omega^2 - 1)/(2*omega) = 0 (off-shell). At omega=1, k=0 (on-shell): A(1, 0) = pi/omega = pi. If A is negative at any on-shell point, the sign convention is wrong.
```

---

## Naming Convention

Pattern files are named `{category}-{short-slug}.md` within the appropriate domain subdirectory:

```
patterns-by-domain/qft/sign-error-metric-signature.md
patterns-by-domain/condensed-matter/convergence-issue-dmrg-bond-dimension.md
patterns-by-domain/stat-mech/factor-error-partition-function-overcounting.md
patterns-by-domain/gr/convention-pitfall-coordinate-vs-proper-time.md
```

**Slug rules:**

- Lowercase, hyphen-separated
- 2-5 words that identify the specific pattern
- Unique within the domain subdirectory
