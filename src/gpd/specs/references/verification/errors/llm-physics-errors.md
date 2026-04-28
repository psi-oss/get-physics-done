# LLM Physics Error Catalog

Language models make characteristic physics errors that differ from human errors. Human physicists make sign errors and algebraic mistakes; LLMs confuse conventions between sources, hallucinate identities, and get combinatorial factors wrong in systematic ways. This catalog documents the most common LLM physics error classes with detection strategies.

Consult this catalog before trusting any LLM-generated physics calculation. Every error class below has been observed in production.

## Error Class Index

The full catalog is split across 4 files for efficient context loading:

| File | Error Classes | Domain |
|---|---|---|
| [llm-errors-core.md](llm-errors-core.md) | #1-25 | Core error classes: CG coefficients, Green's functions, group theory, asymptotics, delta functions, phase conventions, thermodynamics, field theory basics, variational bounds, partition functions |
| [llm-errors-field-theory.md](llm-errors-field-theory.md) | #26-51 | Field theory & advanced: coherent states, second quantization, angular momentum coupling, Boltzmann factors, path ordering, ensembles, numerical methods, regularization, Fierz identities, effective potentials, metric signatures, topological terms |
| [llm-errors-extended.md](llm-errors-extended.md) | #52-81, #102-104 | Extended & deep domain: numerical relativity, stellar structure, quantum chemistry, plasma physics, fluid dynamics, quantum computing, biophysics, turbulence, finite-size effects. New: catastrophic cancellation, functional Jacobians, IR safety |
| [llm-errors-deep.md](llm-errors-deep.md) | #82-101 | Cross-domain: nuclear shell model, astrophysics, AMO physics, superconductivity, magnetic reconnection, decoherence, constraints, critical phenomena, conformal mappings, Brillouin zones, Penrose diagrams, entanglement |

## Error Class to Verification Check Traceability

For a context-efficient matrix mapping each error class to the checks most likely to catch it, load `llm-errors-traceability.md`. That companion index covers dimensional analysis, limiting cases, symmetry, conservation, Ward/sum-rule checks, numerical convergence, literature cross-checks, and positivity/unitarity against all 104 classes.

Use the matrix with `../core/verification-core.md` and the relevant domain-specific verification file when selecting targeted verification strategies.

## Usage Guidelines

1. **Proactive checking.** When an LLM generates a physics calculation, scan for ALL error classes, not just the ones that seem relevant. Errors from class 11 (hallucinated identities), class 15 (dimensional failures), class 33 (natural unit restoration), and class 37 (metric signature inconsistency) can appear in any context.
2. **Priority ordering.** The most dangerous errors are those that produce plausible-looking results: classes 3, 5, 9, 11, 17, 21, 42 (missing anomalies), 84 (Friedmann equation), 90 (critical exponents). Sign errors (classes 7, 12, 22, 36, 37) are usually caught by consistency checks. Factor errors (classes 2, 6, 8, 19, 41, 83, 96) are caught by dimensional analysis and limiting cases. Structural errors (classes 13, 14, 16, 18, 43, 46, 89, 97) are caught by substitution checks. Convention errors (classes 34, 37, 38, 45) require tracking conventions from the start. Domain-specific errors (classes 82-101) are particularly insidious because they require specialized knowledge to detect — the cross-domain classes cover nuclear, astrophysical, AMO, condensed matter, plasma, and mathematical physics pitfalls.
3. **Compound errors.** LLMs can make multiple errors from different classes in a single calculation. A wrong CG coefficient (class 1) combined with a wrong phase convention (class 7) can accidentally cancel, producing a "correct" result for the wrong reason. Similarly, a metric signature error (class 37) combined with a covariant derivative error (class 38) can produce a doubly-wrong result that passes superficial checks. Always verify intermediate steps, not just the final answer.
4. **Confidence calibration.** LLMs present all results with equal confidence. A standard textbook identity and a hallucinated generalization are stated with the same certainty. The absence of hedging language does NOT indicate correctness.
5. **Cross-referencing.** For any non-trivial identity or coefficient: verify against at least two independent sources (textbooks, published tables, numerical computation). LLMs can reproduce errors from a single training source.
6. **Use the traceability matrix.** When a specific error class is suspected, consult `llm-errors-traceability.md` to identify which verification checks are most effective for detection.
