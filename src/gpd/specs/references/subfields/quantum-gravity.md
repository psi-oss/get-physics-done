---
load_when:
  - "quantum gravity"
  - "semiclassical gravity"
  - "black hole information"
  - "replica wormhole"
  - "Page curve"
  - "holography"
  - "AdS/CFT"
  - "asymptotic safety"
  - "background independent gravity"
  - "causal dynamical triangulations"
tier: 2
context_cost: medium
---

# Quantum Gravity

## Core Methods

**Detailed protocols:** For step-by-step calculation protocols, see `references/protocols/holography-ads-cft.md`, `references/protocols/de-sitter-space.md`, `references/protocols/asymptotic-symmetries.md`, `references/protocols/effective-field-theory.md`, `references/protocols/path-integrals.md`, `references/protocols/supersymmetry.md` (for protected sectors), `references/protocols/renormalization-group.md` (for asymptotic-safety/FRG work), and `references/protocols/random-matrix-theory.md` (for quantum-chaos diagnostics). For worldsheet methods, D-branes, compactification, or swampland-specific reasoning, also load `references/subfields/string-theory.md`.

**Semiclassical Gravity and QFT in Curved Spacetime:**

- Work in the regime where matter is quantized on a classical geometry and the semiclassical Einstein equation makes sense
- Keep track of curvature scales, backreaction size, renormalized stress tensors, and state dependence (Unruh, Hartle-Hawking, Boulware, etc.)
- Hawking radiation, generalized entropy, and horizon thermodynamics are the core operational tools; they are not yet a full microscopic theory of quantum gravity
- Claims about information recovery must state whether they are semiclassical, holographic, or dependent on an assumed UV completion

**Black Hole Information, Islands, and Entanglement:**

- The generalized entropy `S_gen = A/(4G_N) + S_bulk + ...` is the central bookkeeping quantity
- Page-curve calculations require specifying the radiation region, the ensemble or state, and the competing saddles or quantum extremal surfaces
- Islands and replica-wormhole methods are powerful semiclassical tools, but the analytic continuation and saddle selection must be stated explicitly
- Quantum chaos, ETH-style reasoning, OTOCs, and spectral statistics are useful diagnostics, but they are not interchangeable with entropy calculations

**Holography and Emergent Geometry:**

- AdS/CFT provides the sharpest non-perturbative dictionary currently available in quantum gravity
- Entanglement wedge reconstruction, RT/HRT/QES, and large-`N` factorization organize much of the modern information-theoretic language
- Flat-space and de Sitter holography remain active programs with fewer settled dictionary entries
- Weak-coupling boundary calculations should only be extrapolated to the bulk when the observable is protected or otherwise controlled

**Canonical, Continuum, and Discrete Approaches:**

- Canonical quantization emphasizes constraints, Dirac observables, Wheeler-DeWitt-type equations, and the problem of time
- Asymptotic safety emphasizes functional RG flows, fixed points, and truncation systematics
- Causal dynamical triangulations and causal-set approaches emphasize continuum emergence from nonperturbative discrete structures
- These are not interchangeable approximations of one calculation; each framework comes with its own notion of observable and approximation control

## Key Tools and Software

| Tool | Purpose | Notes |
|------|---------|-------|
| **xAct / xTensor** | Tensor algebra and perturbation theory | Symbolic GR, curvature, effective actions |
| **Cadabra** | Field-theory tensor algebra | Good for gravity plus matter and index manipulations |
| **Black Hole Perturbation Toolkit** | Black hole perturbations and self-force | Useful for semiclassical and near-horizon calculations |
| **SageManifolds** | Differential geometry | Coordinate and invariant checks for curved backgrounds |
| **Mathematica / Python notebooks** | Symbolic + numerical experimentation | Common for replica saddles, entropy variations, and FRG truncations |
| **Einstein Toolkit / SpECTRE** | Numerical GR backgrounds | Useful when quantum-gravity questions depend on controlled classical geometries |

## Validation Strategies

**Semiclassical Control:**

- Verify the curvature scale is well above the Planck length: `ell_P^2 * R << 1`
- Verify the quantum stress tensor does not invalidate the chosen background without an explicit backreaction treatment
- State the quantum state and renormalization prescription for `<T_{mu nu}>`

**Generalized Entropy and Islands:**

- Compare all relevant saddles: no-island, island, and any symmetry-related branches
- State the homology/extremization conditions and the regime in which the QES prescription is being applied
- A Page curve is not meaningful until the radiation subsystem and coarse-graining choice are specified

**Holographic Dictionary Control:**

- Check the large-`N` / central-charge / `G_N` scaling that justifies a semiclassical bulk
- Match the same boundary conditions and observables on both sides of the duality
- Distinguish protected observables from genuinely dynamical strong-coupling quantities

**Approach-Specific Nonperturbative Claims:**

- Asymptotic safety: test regulator dependence, truncation stability, and robustness of fixed-point data
- Canonical/discrete approaches: state the continuum or semiclassical limit and the observable extracted from the construction
- Do not call a framework predictive unless a controlled observable or scaling limit is actually computed

## Common Pitfalls

- **Conflating semiclassical gravity with a full microscopic theory of quantum gravity**
- **Importing the AdS/CFT dictionary into de Sitter or flat space without stating the extra assumptions**
- **Using the island formula without specifying the radiation region, ensemble, or saddle competition**
- **Treating a truncation, toy model, or one solvable example as a general solution of quantum gravity**
- **Confusing coarse-grained black hole entropy with fine-grained von Neumann entropy**
- **Ignoring the regime of validity of EFT, semiclassical, or large-`N` approximations**

---

## Research Frontiers (2024-2026)

| Frontier | Key question | Active groups | GPD suitability |
|----------|-------------|---------------|-----------------|
| **Black hole information / islands** | When and why do semiclassical gravity plus generalized entropy recover unitary Page-curve behavior? | Penington, Almheiri, Maldacena, Hartman, Engelhardt | Good — strong on saddle competition, entropy bookkeeping, and regime checks |
| **Holography beyond AdS** | What is the right observable framework for flat-space, celestial, or de Sitter quantum gravity? | Strominger, Pasterski, Anninos, Donnay, Ciambelli | Good — symmetry and dictionary discipline are essential; the full dualities remain unsettled |
| **Asymptotic safety** | Does gravity possess a UV fixed point with predictive infrared consequences? | Reuter, Eichhorn, Percacci, Pawlowski | Good — truncation bookkeeping and RG reasoning are a natural fit |
| **Discrete and causal quantum gravity** | How do CDT and causal-set approaches recover semiclassical spacetime and controlled observables? | Ambjorn, Loll, Surya | Moderate — conceptually strong, but workflow and observables remain highly approach-specific |
| **Quantum gravity and quantum information** | How far can entanglement wedges, error correction, chaos, and complexity reorganize spacetime physics? | Harlow, Jafferis, Hayden, Penington | Good — especially for controlled entropy and reconstruction problems |

## Methodology Decision Tree

```
What regime of quantum gravity?
├── Low curvature, matter on fixed background
│   └── Semiclassical gravity / QFT in curved spacetime
├── AdS or large-N duality available
│   └── Holography / AdS-CFT
├── Horizon entropy, Page curve, replica saddles
│   └── Generalized entropy + islands + semiclassical path integral
├── UV completion via continuum RG
│   └── Asymptotic safety / functional RG
├── Background-independent canonical or discrete framework
│   └── Wheeler-DeWitt methods / CDT / causal sets
└── Positive or flat asymptotics
    └── Load de Sitter or asymptotic-symmetries references explicitly
```

## Common Collaboration Patterns

- **Quantum gravity + GR:** Classical geometry, horizons, and perturbation theory provide the background control for semiclassical questions
- **Quantum gravity + QFT:** Matter entanglement, anomalies, EFT reasoning, and RG flow are often the calculational backbone
- **Quantum gravity + quantum information:** Entropy, reconstruction, error correction, and chaos organize protected or semiclassical observables
- **Quantum gravity + string theory:** Holography, supersymmetry, and swampland ideas often enter through string constructions rather than pure GR reasoning. If the calculation depends on worldsheet control, D-branes, or compactification data, load `references/subfields/string-theory.md` explicitly.

## Project Scope by Career Stage

| Level | Typical scope | Example |
|-------|--------------|---------|
| **PhD thesis** | One controlled regime or one framework-specific observable | "Replica-wormhole corrections to a toy-model Page curve" |
| **Postdoc** | New calculational control, bridge between frameworks, or sharper observable map | "Relating asymptotic-safety truncations to canonical observables" |
| **Faculty** | New framework synthesis or major conceptual advance with clear observables | "A controlled observable dictionary for quantum gravity beyond AdS" |
