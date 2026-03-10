## Notation and Convention Tracking

Every phase plan MUST establish or inherit conventions. Ambiguous notation is the #1 source of cascading errors in physics calculations.

**Required convention declarations:**

```yaml
conventions:
  units: "natural (hbar = c = 1)" | "SI" | "Gaussian CGS" | "lattice"
  metric_signature: "(+,-,-,-)" | "(-,+,+,+)" | "Euclidean (+,+,+,+)"
  index_convention: "Einstein summation" | "explicit sums"
  coordinates: "Cartesian" | "spherical (r,theta,phi)" | "light-cone" | ...
  gauge: "Coulomb" | "Lorenz" | "axial" | "Feynman" | ...
  fourier_convention: "physics (exp(-iwt))" | "math (exp(+iwt))" | "QFT (exp(-ipx))"
  normalization:
    states: "<p|q> = delta(p-q)" | "<p|q> = (2pi)^3 2E delta(p-q)"
    fields: "canonical" | "relativistic"
  spinor_convention: "Dirac" | "Weyl" | "Majorana"
```

**Inherit from prior phases:** If Phase 01 established metric (+,-,-,-), all subsequent phases MUST use it unless an explicit convention change task is included.

**Convention conflict detection:** Before writing any plan, verify that the chosen conventions are mutually consistent. Flag conflicts like:

- Natural units declared but dimensional quantities appear in formulas
- Metric signature mismatch between Lagrangian and propagator
- Fourier convention inconsistency between position and momentum space expressions
