---
load_when:
  - "verification"
  - "computational check"
  - "spot-check"
  - "oracle"
tier: 2
context_cost: medium
---

# Computational Verification Templates

Copy-paste-ready Python/SymPy templates for the most common computational verification tasks. These provide the **external oracle** that breaks LLM self-consistency loops — every VERIFICATION.md must include at least one executed code block from this catalog.

**Usage:** Copy the relevant template, replace the placeholder comments with actual expressions from the phase artifacts, execute via shell, and paste both the code AND output into VERIFICATION.md.

---

## Template 1: Dimensional Analysis Check

Verify that all terms in an equation have consistent dimensions using SymPy's unit system.

```python
#!/usr/bin/env python3
"""Dimensional analysis verification template."""
from sympy import symbols, sqrt, pi
from sympy.physics.units import Dimension
from sympy.physics.units.dimensions import (
    length, mass, time, energy, action
)

# === REPLACE BELOW WITH ACTUAL QUANTITIES ===
# Define symbols with their dimensions
# Example: for E = p^2/(2m) + V(r)
# [E] = energy = mass * length^2 / time^2
# [p^2/(2m)] = (mass * length / time)^2 / mass = mass * length^2 / time^2  ✓
# [V(r)] must also be energy

# Define the dimensions of each symbol in the expression
dims = {
    # "symbol_name": Dimension expression
    # "E": energy,
    # "p": mass * length / time,
    # "m": mass,
    # "hbar": action,  # mass * length^2 / time
}

# Check each term
terms = {
    # "term_description": dimension_expression,
    # "LHS: E": energy,
    # "RHS term 1: p^2/(2m)": mass * length**2 / time**2,
    # "RHS term 2: V(r)": energy,
}

print("=== Dimensional Analysis ===")
reference_name, reference_dim = list(terms.items())[0]
for name, dim in terms.items():
    match = (dim == reference_dim)
    status = "CONSISTENT" if match else "MISMATCH"
    print(f"  {name}: {dim} -> {status}")

# === CHECK TRANSCENDENTAL ARGUMENTS ===
# Every argument of exp(), log(), sin(), cos() must be dimensionless
transcendental_args = {
    # "exp argument: -beta*E": "beta=[1/energy], E=[energy] -> dimensionless ✓",
}
for name, check in transcendental_args.items():
    print(f"  {name}: {check}")
```

---

## Template 2: Limiting Case Evaluation

Evaluate an expression in a known limiting case and compare with the expected result.

```python
#!/usr/bin/env python3
"""Limiting case verification template."""
import sympy as sp

# === DEFINE SYMBOLS ===
# x, m, g, hbar = sp.symbols('x m g hbar', positive=True)

# === DEFINE THE EXPRESSION TO CHECK ===
# expr = ...  # The expression from the derivation

# === TAKE THE LIMIT ===
# Common limits:
#   sp.limit(expr, g, 0)              # Weak coupling
#   sp.limit(expr, m, 0)              # Massless limit
#   sp.limit(expr, m, sp.oo)          # Heavy mass limit
#   sp.limit(expr, hbar, 0)           # Classical limit
#   expr.subs(x, 0)                   # Zero argument
#   sp.series(expr, g, 0, n=3)        # Series expansion

limits_to_check = {
    # "description": (expression, variable, limit_point, expected_result),
    # "free particle (V=0)": (energy_expr, V, 0, p**2/(2*m)),
    # "classical limit": (quantum_expr, hbar, 0, classical_expr),
    # "non-relativistic": (rel_expr, c, sp.oo, nr_expr),
}

print("=== Limiting Case Verification ===")
for name, (expr, var, point, expected) in limits_to_check.items():
    if point == sp.oo or point == 0:
        computed = sp.limit(expr, var, point)
    else:
        computed = expr.subs(var, point)

    diff = sp.simplify(computed - expected)
    match = (diff == 0)
    print(f"\n  {name}:")
    print(f"    Computed: {computed}")
    print(f"    Expected: {expected}")
    print(f"    Difference: {diff}")
    print(f"    Status: {'MATCH' if match else 'MISMATCH'}")
```

---

## Template 3: Numerical Spot-Check

Evaluate an expression at specific numerical test points and compare with known values.

```python
#!/usr/bin/env python3
"""Numerical spot-check verification template."""
import numpy as np

# === DEFINE THE FUNCTION FROM THE DERIVATION ===
# def result_function(params):
#     """The expression derived in the phase."""
#     # return ...

# === DEFINE TEST POINTS WITH KNOWN ANSWERS ===
test_cases = [
    # {
    #     "name": "trivial case (zero coupling)",
    #     "params": {"g": 0, "m": 1.0, "E": 0.5},
    #     "expected": 1.0,
    #     "tolerance": 1e-10,
    # },
    # {
    #     "name": "literature benchmark (Peskin & Schroeder Eq. 7.28)",
    #     "params": {"alpha": 1/137, "m_e": 0.511e-3, "q2": -1.0},
    #     "expected": 0.02323,  # Known numerical value
    #     "tolerance": 1e-4,
    # },
    # {
    #     "name": "symmetry test (should be invariant under k -> -k)",
    #     "params_a": {"k": 0.5},
    #     "params_b": {"k": -0.5},
    #     "test": "equality",  # computed(a) == computed(b)
    # },
]

print("=== Numerical Spot-Check ===")
for tc in test_cases:
    name = tc["name"]
    # computed = result_function(**tc["params"])
    # expected = tc["expected"]
    # tol = tc.get("tolerance", 1e-10)
    # match = np.isclose(computed, expected, rtol=tol)
    # rel_err = abs(computed - expected) / max(abs(expected), 1e-300)
    # print(f"  {name}: computed={computed:.6e}, expected={expected:.6e}, "
    #       f"rel_err={rel_err:.2e}, {'PASS' if match else 'FAIL'}")
    print(f"  {name}: [REPLACE WITH ACTUAL COMPUTATION]")
```

---

## Template 4: Identity / Relation Verification

Verify a claimed mathematical identity or physics relation by evaluating both sides.

```python
#!/usr/bin/env python3
"""Identity/relation verification template."""
import sympy as sp

# === DEFINE SYMBOLS ===
# x, a, n = sp.symbols('x a n')

# === DEFINE BOTH SIDES OF THE IDENTITY ===
# lhs = ...  # Left-hand side
# rhs = ...  # Right-hand side

# === METHOD 1: Symbolic simplification ===
# diff = sp.simplify(lhs - rhs)
# print(f"Symbolic: LHS - RHS = {diff}")
# print(f"Identity holds symbolically: {diff == 0}")

# === METHOD 2: Numerical evaluation at test points ===
identities = [
    # {
    #     "name": "Completeness relation",
    #     "lhs": "sum_n |n><n|",
    #     "rhs": "identity",
    #     "test_values": [
    #         {"x": 0.1, "lhs_val": 1.0, "rhs_val": 1.0},
    #         {"x": 0.5, "lhs_val": 1.0, "rhs_val": 1.0},
    #         {"x": 2.0, "lhs_val": 1.0, "rhs_val": 1.0},
    #     ]
    # },
]

print("=== Identity Verification ===")
for ident in identities:
    print(f"\n  {ident['name']}:")
    for tv in ident["test_values"]:
        match = np.isclose(tv["lhs_val"], tv["rhs_val"])
        print(f"    x={tv['x']}: LHS={tv['lhs_val']}, RHS={tv['rhs_val']}, {'PASS' if match else 'FAIL'}")

# === METHOD 3: SymPy verification for known identities ===
# Common identities to verify:
#   Gamma function: sp.gamma(n+1) == sp.factorial(n)
#   Euler: sp.exp(sp.I * sp.pi) + 1 == 0
#   Gaussian: sp.integrate(sp.exp(-x**2), (x, -sp.oo, sp.oo)) == sp.sqrt(sp.pi)
#   Fourier: delta normalization
```

---

## Template 5: Convergence Test

Verify that a numerical result converges as resolution/samples increase.

```python
#!/usr/bin/env python3
"""Convergence test verification template."""
import numpy as np

# === DEFINE THE COMPUTATION AT DIFFERENT RESOLUTIONS ===
# def compute_at_resolution(N):
#     """Run the computation with N grid points / samples / terms."""
#     # return result_value

resolutions = [10, 20, 40, 80, 160, 320]
# results = [compute_at_resolution(N) for N in resolutions]

# === PLACEHOLDER: replace with actual computed values ===
results = []  # [val_at_10, val_at_20, ...]

if len(results) >= 3:
    print("=== Convergence Test ===")
    print(f"{'N':>6} {'Result':>15} {'Delta':>12} {'Ratio':>8}")
    print("-" * 45)
    for i, (N, val) in enumerate(zip(resolutions, results)):
        if i == 0:
            print(f"{N:6d} {val:15.8e}    ---       ---")
        elif i == 1:
            delta = abs(val - results[i-1])
            print(f"{N:6d} {val:15.8e} {delta:12.4e}    ---")
        else:
            delta = abs(val - results[i-1])
            prev_delta = abs(results[i-1] - results[i-2])
            ratio = prev_delta / delta if delta > 0 else float('inf')
            print(f"{N:6d} {val:15.8e} {delta:12.4e} {ratio:8.2f}")

    # Richardson extrapolation (assuming power-law convergence O(h^p))
    if len(results) >= 3:
        # Estimate convergence order from last 3 points
        d1 = abs(results[-2] - results[-3])
        d2 = abs(results[-1] - results[-2])
        if d2 > 0 and d1 > 0:
            p_est = np.log(d1/d2) / np.log(2)  # Assuming resolution doubles
            extrapolated = results[-1] + (results[-1] - results[-2]) / (2**p_est - 1)
            print(f"\nEstimated convergence order: p = {p_est:.2f}")
            print(f"Richardson extrapolation: {extrapolated:.8e}")
            print(f"Status: {'CONVERGING' if 1.5 < p_est < 10 else 'CHECK ORDER'}")
else:
    print("ERROR: Need at least 3 resolution points for convergence test")
```

---

## Usage in VERIFICATION.md

Every VERIFICATION.md must include at least ONE executed code block. The format:

````markdown
### Computational Oracle: [Check Name]

**Template:** [which template above]
**Test:** [what is being verified]

```python
# [Actual code with expressions from this phase — NOT placeholders]
import numpy as np
...
```

**Output:**
```
[Actual execution output pasted here]
```

**Verdict:** PASS / FAIL / INCONCLUSIVE
````

The presence of at least one such block (with both code AND output) is a **hard requirement** for VERIFICATION.md completeness. A VERIFICATION.md without computational output blocks is flagged as INCOMPLETE regardless of other content.
