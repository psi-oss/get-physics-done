<purpose>
Perform a systematic dimensional analysis audit on every equation in a derivation, computation, or phase. Track dimensions through all algebraic steps, verify consistency, and flag any dimensional anomalies.

Called from /gpd:dimensional-analysis command. Produces DIMENSIONAL-ANALYSIS.md report.

Dimensional analysis is the cheapest and most powerful diagnostic in physics. It catches ~30% of errors at near-zero cost. This workflow applies it systematically rather than ad hoc.
</purpose>

<process>

## 0. Load Project Context

Load project state and conventions to determine the unit system:

- Run:

```bash
INIT=$(gpd init phase-op --include state,config)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

- **If init succeeds** (non-empty JSON with `state_exists: true`): Extract `convention_lock`, especially `units` and `natural_units` settings. Extract active approximations for context on what dimensions are independent.
- **If init fails or `state_exists` is false** (standalone usage): Proceed — the unit system will be established explicitly in Step 1 via ask_user.

The convention_lock unit system setting (natural units, SI, CGS, etc.) directly determines which dimensions are independent and what the dimensional assignments table looks like.

**Convention verification** (if project exists):

```bash
CONV_CHECK=$(gpd --raw convention check 2>/dev/null)
if [ $? -ne 0 ]; then
  echo "WARNING: Convention verification failed — unit system may be inconsistent"
  echo "$CONV_CHECK"
fi
```

Dimensional analysis results depend critically on the unit system. In natural units (hbar=c=1), energy and mass have the same dimension; in SI they don't. A convention mismatch here invalidates the entire analysis.

## 1. Establish Dimensional Framework

Before checking any equations, establish the unit system in use.

Use ask_user if not found in project files:

1. **Unit system** -- Natural units (hbar=c=1)? SI? Gaussian CGS? Heaviside-Lorentz? Planck units?
2. **Independent dimensions** -- Which dimensions are independent?
   - Natural units: [Energy] (or [Mass] or [Length]^{-1})
   - SI: [M], [L], [T], [I], [Theta], [N], [J]
   - Gaussian: [M], [L], [T]
3. **Key dimensional assignments** -- Confirm dimensions of fundamental quantities:
   - Fields, coupling constants, coordinates, momenta
   - Any project-specific quantities

Build dimensional lookup table:

```markdown
## Dimensional Assignments

| Quantity           | Symbol | Dimensions (natural) | Dimensions (SI)   |
| ------------------ | ------ | -------------------- | ----------------- |
| Energy             | E      | [E]                  | [M L^2 T^{-2}]    |
| Momentum           | p      | [E]                  | [M L T^{-1}]      |
| Position           | x      | [E^{-1}]             | [L]               |
| Time               | t      | [E^{-1}]             | [T]               |
| Mass               | m      | [E]                  | [M]               |
| Wavefunction (3D)  | psi    | [E^{3/2}]            | [L^{-3/2}]        |
| Action             | S      | [1]                  | [M L^2 T^{-1}]    |
| Lagrangian density | L      | [E^4]                | [M L^{-1} T^{-2}] |
| {project-specific} | ...    | ...                  | ...               |
```

## 2. Identify All Equations

Scan target for all equations:

```bash
# LaTeX equations
grep -n "\\\\begin{equation\|\\\\begin{align\|\\\\begin{eqnarray\|\\$\\$\|\\\\\\[" "$TARGET_FILE" 2>/dev/null

# Python expressions with physics content
grep -n "=.*\(np\.\|scipy\.\|sympy\.\|integrate\|solve\|eigenval\)" "$TARGET_FILE" 2>/dev/null

# Mathematica expressions
grep -n "=.*\(Integrate\|Solve\|DSolve\|Eigenvalues\)" "$TARGET_FILE" 2>/dev/null
```

Number each equation for tracking.

## 3. Analyze Each Equation

For every equation, perform the following checks:

### 3a. Term-by-term dimensional check

For each term in each equation:

1. Identify all quantities (variables, constants, operators)
2. Look up dimensions from the dimensional table
3. Compute dimensions of the full term
4. Verify all terms in sums/differences have identical dimensions
5. Verify both sides of equalities have identical dimensions

### 3b. Function argument check

For every transcendental function (exp, log, sin, cos, erf, Bessel, etc.):

- Verify the argument is **dimensionless**
- If not dimensionless: **ERROR** -- dimensional inconsistency

For every power law (x^n where n is not integer):

- Verify the base has well-defined dimensions under the fractional power
- Flag if dimensions become irrational

### 3c. Integration and differentiation check

For every integral:

- Track the integration measure (dx, d^3x, d^4k/(2pi)^4, etc.)
- Verify [integrand * measure] has correct dimensions
- Check that integration limits are dimensionally consistent with variable

For every derivative:

- [d/dx] has dimensions [x]^{-1}
- [partial/partial t] has dimensions [T]^{-1} (or [E] in natural units)
- Verify the result has [f(x)] \* [x]^{-1} dimensions

### 3d. Delta function and distribution check

Dirac delta function delta(x) has dimensions [x]^{-1}:

- delta(x - x_0): dimensions [x]^{-1}
- delta^3(r - r_0): dimensions [x]^{-3}
- delta(E - E_0): dimensions [E]^{-1}

Verify everywhere delta functions appear.

### 3e. Tensor index check (if applicable)

For tensor equations:

- Verify free indices match on both sides
- Verify contracted indices appear once up and once down (or use metric for raising/lowering)
- Check that the metric tensor is used consistently

## 4. Track Dimensions Through Derivation

For multi-step derivations, track dimensions through the chain:

```
Step 1: [LHS] = [A] + [B]           Check: [A] == [B]
Step 2: [LHS'] = [f(LHS)]           Check: dimensions propagate correctly through f
Step 3: [Result] = [LHS'] * [C]     Check: [Result] has expected final dimensions
```

Flag the first step where dimensions become inconsistent -- this is likely where the error was introduced.

## 5. Special Checks

### 5a. Natural units restoration

If working in natural units, restore factors of hbar, c, k_B explicitly for at least the final result:

- Every term must have consistent SI dimensions when factors are restored
- This catches errors hidden by natural units (e.g., missing hbar in quantum mechanical expression)

### 5b. Action dimensionality

The action S must be dimensionless in natural units (or have dimensions [M L^2 T^{-1}] = [hbar] in SI):

- Verify S = integral(L d^4x) has [S] = [L] * [x]^4 = [E^4] * [E^{-4}] = [1] in natural units
- Common error: wrong number of spacetime dimensions in the measure

### 5c. Partition function dimensionality

The partition function Z = Tr(e^{-beta H}) must be dimensionless:

- beta*H must be dimensionless: [beta] = [E^{-1}], [H] = [E] -- check
- Z itself is a sum of dimensionless exponentials -- check

### 5d. Probability and normalization

Probabilities and probability densities:

- P(event) is dimensionless
- p(x) dx is dimensionless, so [p(x)] = [x]^{-1}
- |psi(x)|^2 d^3x is dimensionless, so [psi] = [L^{-3/2}]

## 6. Generate Report

Write DIMENSIONAL-ANALYSIS.md:

```markdown
---
target: { phase or file }
date: { YYYY-MM-DD }
unit_system: { natural/SI/CGS }
equations_checked: { N }
anomalies_found: { M }
status: consistent | anomalies_found
---

# Dimensional Analysis Report

## Unit System

{Unit system and dimensional assignments used}

## Equations Checked

| #   | Equation           | Location    | Status | Notes          |
| --- | ------------------ | ----------- | ------ | -------------- |
| 1   | {name/description} | {file:line} | OK     |                |
| 2   | {name/description} | {file:line} | ERROR  | {what's wrong} |

## Anomalies Found

### Anomaly {N}: {Brief description}

- **Location:** {file:line}
- **Equation:** {the equation}
- **Expected dimensions:** {what it should be}
- **Found dimensions:** {what it actually is}
- **Likely cause:** {missing factor of hbar, wrong measure, etc.}
- **Severity:** CRITICAL (wrong physics) | WARNING (suspicious) | NOTE (convention-dependent)

## Dimensional Tracking

{For multi-step derivations, show the dimension chain step by step}

## Summary

- Equations checked: {N}
- Consistent: {M}
- Anomalies: {K}
- {Assessment}
```

Ensure output directory exists:

```bash
mkdir -p .gpd/analysis
```

Save to appropriate location:

- Phase target: `${phase_dir}/DIMENSIONAL-ANALYSIS.md`
- File target: `.gpd/analysis/dimensional-{slug}.md`

## 7. Present Results

If anomalies found:

```
## Dimensional Analysis: {N} anomalies found

{List anomalies with severity}

Suggested next steps:
- `/gpd:debug` -- investigate anomalies
- Fix directly -- if cause is obvious (missing factor, wrong measure)
```

If all consistent:

```
## Dimensional Analysis: All {N} equations consistent

No dimensional anomalies detected.
```

**Commit the report:**

```bash
PRE_CHECK=$(gpd pre-commit-check --files "${OUTPUT_PATH}" 2>&1) || true
echo "$PRE_CHECK"

gpd commit \
  "docs: dimensional analysis audit — ${phase_slug:-standalone}" \
  --files "${OUTPUT_PATH}"
```

Where `${OUTPUT_PATH}` is the path where DIMENSIONAL-ANALYSIS.md was written.

</process>

<output>
DIMENSIONAL-ANALYSIS.md written with full audit results.
</output>

<success_criteria>

- [ ] Unit system established (natural, SI, etc.)
- [ ] Dimensional assignments built for all quantities
- [ ] Every equation in target identified and numbered
- [ ] Term-by-term analysis performed on each equation
- [ ] Function arguments verified dimensionless
- [ ] Integration measures checked
- [ ] Delta function dimensions verified
- [ ] Natural units restored for key results
- [ ] Report generated with all anomalies classified
- [ ] Anomalies linked to specific locations in the derivation
</success_criteria>
