---
template_version: 1
---

# Notation Glossary Template

Template for `.gpd/NOTATION_GLOSSARY.md` - comprehensive notation reference for the research project.

**Purpose:** Single source of truth for all symbols, indices, and conventions used across phases. Prevents notation drift and sign-convention errors when multiple phases build on each other.

---

## File Template

```markdown
# Notation Glossary

**Analysis Date:** [YYYY-MM-DD]
**Last Updated:** [YYYY-MM-DD]

## Coordinates and Spacetime

| Symbol          | Meaning                 | Convention                                    | Defined In      |
| --------------- | ----------------------- | --------------------------------------------- | --------------- |
| [e.g., $x^\mu$] | [Spacetime coordinates] | [e.g., $(t, x, y, z)$, signature $(-,+,+,+)$] | [Phase or file] |

## Fields and Operators

| Symbol            | Meaning              | Units                            | Defined In      |
| ----------------- | -------------------- | -------------------------------- | --------------- |
| [e.g., $\psi(x)$] | [Dirac spinor field] | [e.g., $[\text{length}]^{-3/2}$] | [Phase or file] |

## Parameters and Constants

| Symbol      | Meaning             | Value / Range         | Units           | Defined In      |
| ----------- | ------------------- | --------------------- | --------------- | --------------- |
| [e.g., $g$] | [Coupling constant] | [e.g., $0 < g \ll 1$] | [Dimensionless] | [Phase or file] |

## Indices

| Index              | Range        | Convention                      | Example                    |
| ------------------ | ------------ | ------------------------------- | -------------------------- |
| [e.g., $\mu, \nu$] | [0, 1, 2, 3] | [Spacetime, Einstein summation] | [$g_{\mu\nu} x^\mu x^\nu$] |
| [e.g., $i, j, k$]  | [1, 2, 3]    | [Spatial, Einstein summation]   | [$\delta_{ij}$]            |
| [e.g., $a, b$]     | [1, ..., N]  | [Internal/flavor]               | [$\phi^a$]                 |

## Abbreviations and Acronyms

| Abbreviation | Full Term               | Context                     |
| ------------ | ----------------------- | --------------------------- |
| [e.g., RG]   | [Renormalization Group] | [Used throughout]           |
| [e.g., PN]   | [Post-Newtonian]        | [Expansion parameter $v/c$] |

## Fourier Transform Convention

$$
\tilde{f}(\omega) = \int_{-\infty}^{\infty} f(t)\, e^{[+/-] i\omega t}\, dt
$$

**Sign choice:** [e.g., $+i\omega t$ for physics convention, $-i\omega t$ for engineering convention]
**Normalization:** [e.g., symmetric $1/\sqrt{2\pi}$ or asymmetric $1/(2\pi)$ on inverse]

## Special Functions and Notation

| Notation                        | Meaning                      | Notes                                     |
| ------------------------------- | ---------------------------- | ----------------------------------------- |
| [e.g., $\langle \cdot \rangle$] | [Thermal/ensemble average]   | [$\langle A \rangle = \text{Tr}(\rho A)$] |
| [e.g., $[\cdot, \cdot]$]        | [Commutator]                 | [$[A, B] = AB - BA$]                      |
| [e.g., $\{\cdot, \cdot\}$]      | [Anticommutator]             | [$\{A, B\} = AB + BA$]                    |
| [e.g., $\mathcal{O}(\cdot)$]    | [Order of magnitude / big-O] | [Error bound in expansions]               |

## Phase-Specific Notation

### Phase [XX]: [Name]

| Symbol                             | Meaning   | Notes            |
| ---------------------------------- | --------- | ---------------- |
| [Symbols introduced in this phase] | [Meaning] | [Any subtleties] |

### Phase [YY]: [Name]

| Symbol                             | Meaning   | Notes            |
| ---------------------------------- | --------- | ---------------- |
| [Symbols introduced in this phase] | [Meaning] | [Any subtleties] |

## Potential Conflicts

[Document any notation that could be ambiguous or conflicts between subfields]

| Symbol           | Meaning 1      | Meaning 2      | Resolution                                                         |
| ---------------- | -------------- | -------------- | ------------------------------------------------------------------ |
| [e.g., $\sigma$] | [Pauli matrix] | [Conductivity] | [Context: $\sigma_i$ for Pauli, $\sigma(\omega)$ for conductivity] |

---

_Notation glossary: [date]_
_Update when new symbols are introduced or conventions change_
```

<guidelines>
**What belongs in NOTATION_GLOSSARY.md:**
- Every symbol used in derivations and code, with meaning and units
- Index conventions and summation rules
- Fourier transform sign and normalization choices
- Abbreviations and acronyms
- Phase-specific notation additions
- Notation conflicts and their resolution

**What does NOT belong here:**

- Broad theoretical framing (that's PRIOR-WORK.md or FORMALISM.md)
- Computational methods (that's METHODS.md)
- File organization (that's STRUCTURE.md)
- Full derivations (those live in phase files)

**When filling this template:**

- Start with coordinates, metric signature, and unit system from CONVENTIONS.md
- Add fields and operators as they appear in the theoretical framework
- Track parameters with their physical ranges and units
- Record index conventions explicitly (Einstein summation? Which indices are summed?)
- Note the Fourier transform convention once and reference it everywhere
- Update per-phase notation as new phases introduce new symbols

**Relationship to CONVENTIONS.md:**

- CONVENTIONS.md defines the high-level choices (metric signature, unit system, sign conventions)
- NOTATION_GLOSSARY.md is the detailed lookup table for every symbol
- They are complementary: CONVENTIONS.md says "we use natural units", NOTATION_GLOSSARY.md lists every quantity with its natural-unit dimensions

**Why this matters for multi-phase research:**

- Phase 3 uses $\Sigma$ for self-energy; Phase 7 introduces $\Sigma$ for stress tensor -> conflict
- Without a glossary, downstream phases may silently adopt wrong conventions
- The "Potential Conflicts" section catches these before they cause errors
  </guidelines>
