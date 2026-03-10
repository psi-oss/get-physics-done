## Handling the Iterative Nature of Physics Research

Physics research is inherently non-linear. Plans must account for the reality that calculations frequently reveal their own inadequacy.

### Mid-Calculation Course Corrections

**Common scenarios and responses:**

| Scenario                                 | Signal                                                   | Response                                                                      |
| ---------------------------------------- | -------------------------------------------------------- | ----------------------------------------------------------------------------- |
| Integral diverges unexpectedly           | UV/IR divergence not in power counting                   | STOP. Add regularization task. Re-plan from divergence point.                 |
| Perturbation series doesn't converge     | Higher-order term larger than lower                      | STOP. Flag for resummation or non-perturbative approach. Checkpoint decision. |
| Symmetry is anomalous                    | Classical conservation law violated quantum-mechanically | DOCUMENT. This may be physics, not an error. Verify with independent method.  |
| Numerical instability                    | Condition number blows up, NaN/Inf appears               | STOP. Diagnose source. Add preconditioning or reformulation task.             |
| Calculation is algebraically intractable | Expression grows beyond manageable complexity            | SIMPLIFY. Take useful limits first. Consider computer algebra.                |
| Result contradicts physical intuition    | Negative probability, superluminal propagation           | STOP. This IS an error. Trace back to find it. Do not proceed.                |

### Plan Structure for Iterative Work

```xml
<task type="auto">
  <name>Task 1: Attempt leading-order calculation</name>
  <action>
    Derive [quantity] to leading order in [expansion parameter].

    SANITY GATES (stop and flag if any fail):
    - Gate 1: Result has correct dimensions
    - Gate 2: Result is real/positive/finite as required
    - Gate 3: Known limit reproduced
    - Gate 4: Order-of-magnitude estimate consistent

    If all gates pass: proceed to write up result.
    If any gate fails: document failure mode, do NOT proceed to next task.
  </action>
  <verify>[Standard verification]</verify>
  <done>[Success criteria including gate passage]</done>
</task>
```

### Error Propagation Awareness

When planning multi-step calculations, identify error amplification points:

- **Subtractive cancellations:** A - B where A is approximately equal to B amplifies relative error. Plan for extended precision or analytical cancellation.
- **Iterative maps near fixed points:** Small errors can grow or shrink depending on stability. Include Lyapunov exponent estimate.
- **Numerical differentiation:** Amplifies noise. Prefer analytical derivatives or automatic differentiation.
- **Matrix inversion of ill-conditioned systems:** Use SVD or regularization. Include condition number check in verification.
