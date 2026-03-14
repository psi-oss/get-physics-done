# ARCHITECTURE.md Template (computation focus)

```markdown
# Mathematical Formalism

**Analysis Date:** [YYYY-MM-DD]

## Mathematical Setting

**Spaces:**

- [Space name]: [Type, dimension, properties]
  - e.g., "Hilbert space H: separable, infinite-dimensional, inner product <.|.>"
  - File: `[path]`

**Key Mathematical Objects:**

| Object | Type                                  | Symbol   | Defined In       |
| ------ | ------------------------------------- | -------- | ---------------- |
| [Name] | [e.g., Operator, Field, Tensor, Form] | [Symbol] | `[path]` (Eq. X) |

## Notation and Conventions

**Index Conventions:**

- [Index type]: [Range, meaning]
  - e.g., "Greek mu,nu = 0,...,3 for spacetime; Latin i,j = 1,...,3 for spatial"

**Custom Macros / Notation:**

- `[macro]`: [What it represents]
  - Defined in: `[path]`

**Operator Ordering:**

- [Convention]: [e.g., Normal ordering, Weyl ordering, time ordering]

## Algebraic Structure

**Algebras:**

- [Algebra]: [Generators, commutation/anticommutation relations]
  - File: `[path]` (Eq. X)

**Representations:**

- [Representation]: [Dimension, irreducibility, where used]
  - File: `[path]`

**Tensor Structures:**

- [Tensor]: [Rank, symmetry properties, contraction conventions]

## Functional Structure

**Actions / Functionals:**

- [Functional name]: [Schematic form]
  - File: `[path]` (Eq. X)

**Variational Principles:**

- [Principle]: [What is extremized, constraints]
  - File: `[path]`

## Computational Architecture

**Directory Layout:**
```

[project-root]/
+-- [dir]/ # [Purpose]
+-- [dir]/ # [Purpose]
+-- [file] # [Purpose]

```

**Computational Pipeline:**
1. [Step]: [Input] -> [Output]
   - Script: `[path]`
2. [Step]: [Input] -> [Output]
   - Script: `[path]`

**Key Algorithms:**
- [Algorithm]: [What it computes, complexity]
  - Implementation: `[path]`

**Symbolic Computation:**
- [CAS tool]: [What is computed symbolically]
  - File: `[path]`

**Numerical Methods:**
- [Method]: [What it solves, order of accuracy]
  - Implementation: `[path]`
  - Parameters: [Grid size, tolerances, etc.]

## Transformation Properties

**How Objects Transform:**
- [Object] under [Transformation]: [Rule]
  - File: `[path]`

**Covariance / Invariance:**
- [Statement of covariance]: [Under what group]
  - Verified in: `[path]`

## Boundary and Initial Conditions

**Boundary Conditions:**
- [Type]: [Where applied, physical motivation]
  - File: `[path]`

**Initial Conditions:**
- [Type]: [Physical motivation]
  - File: `[path]`

---

*Formalism analysis: [date]*
```
