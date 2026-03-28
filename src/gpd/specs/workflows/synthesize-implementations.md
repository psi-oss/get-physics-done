<purpose>
Compare N independent implementations of the same physical simulation or computation, identify what each does well and poorly, and compose a unified implementation that cherry-picks the best components with full provenance tracking.
</purpose>

<required_reading>
Read these files using the file_read tool:
- {GPD_INSTALL_DIR}/references/methods/differentiable-simulation.md -- Gradient methods and verification for differentiable solvers
- {GPD_INSTALL_DIR}/references/methods/approximation-selection.md -- Method selection framework
</required_reading>

<process>

## 0. Load Project Context

```bash
INIT=$(gpd init progress --include state)
if [ $? -ne 0 ]; then
  echo "ERROR: gpd initialization failed: $INIT"
  # STOP — display the error to the user and do not proceed.
fi
```

Parse JSON for: `project_contract`, `active_reference_context`, current phase and milestone.

## 1. Inventory Implementations

For each implementation directory, catalog:

| Dimension | What to record |
|-----------|---------------|
| **Approach** | FDM, FEM, analytical, spectral, meshfree |
| **Physics model** | Governing PDE, constitutive relations, source terms |
| **Boundary conditions** | Dirichlet, Neumann, Robin, periodic — exact specification |
| **Material properties** | Values and sources (datasheet, textbook, fitted) |
| **Solver** | Direct, iterative (type + convergence criterion), time-stepping |
| **Gradient method** | Autodiff, adjoint, finite differences, none |
| **Optimizer** | SGD, Adam, L-BFGS, evolutionary, none |
| **Dependencies** | External libraries, GPU requirements, language |
| **Output format** | What artifacts are produced, file formats |

Write the inventory to a comparison matrix in the project artifacts.

## 2. Convention Audit

Lock conventions using GPD convention system. For each implementation, check:

- **Units**: SI vs CGS vs natural vs dimensionless — must be consistent
- **Coordinate system**: Cartesian vs cylindrical vs spherical, axis orientation
- **Boundary conditions**: Same type and values across implementations
- **Material properties**: Same values from same sources, or document why they differ
- **Sign conventions**: Heat flux direction, force direction, potential definition

Flag any convention conflict. These are the most common source of silent errors when combining code from different implementations.

If conventions conflict: resolve by choosing one and documenting the rationale. Do not silently adopt one implementation's convention — make it an explicit project-level decision.

## 3. Score Each Implementation

Evaluate on these dimensions (rate 1-5 or N/A):

| Dimension | What makes a 5 |
|-----------|----------------|
| **Physics fidelity** | Spatially varying properties, proper interface handling, validated BCs |
| **Solver correctness** | Converged solution, conservation satisfied, mesh-independent |
| **Gradient quality** | AD gradients match FD within 5%, consistent forward/backward fidelity |
| **Computational efficiency** | Fast per iteration, reasonable memory, GPU-capable |
| **Code quality** | Modular, readable, documented, testable |
| **Output quality** | Clear visualizations, machine-readable metrics, reproducible |

Produce a score matrix and identify the best implementation per dimension.

## 4. Compose Unified Implementation

For each module (geometry, solver, optimizer, visualization, entry point):

1. Select the best source implementation for that module based on scores
2. Verify interface compatibility — do the selected modules actually work together?
3. If interfaces conflict: adapt the module with the simpler interface to match the richer one
4. Add provenance comments noting which implementation each module came from

**Composition rules:**
- Never mix unit systems within the unified implementation
- If Implementation A has better physics but Implementation B has better code structure, prefer A's physics in B's structure
- If two implementations are equally good, prefer the one that is simpler

## 5. Validate Unified Implementation

Run all applicable verification checks:

1. **Forward solver**: Does it produce physically plausible results?
2. **Conservation**: Is energy/mass/charge conserved (if applicable)?
3. **Convergence**: Does the solution converge with mesh refinement?
4. **Gradients**: Do AD gradients match FD (if differentiable)?
5. **Regression**: Does the unified implementation match or exceed every individual implementation on its own best dimension?

The unified implementation should never be worse than the best individual on any dimension. If it is, investigate — something was lost in composition.

## 6. Document Provenance

Write a provenance table in the project artifacts:

```markdown
| Component | Source | Why selected |
|-----------|--------|-------------|
| Board geometry | Implementation B | Official reference data, spatially varying properties |
| Solver kernel | Implementation D | GPU-accelerated, autodiff-compatible |
| Optimizer | Implementation D | Adam with adaptive LR, proper constraint projection |
| Visualization | Implementation B + D | B's matplotlib quality + D's HTML report pipeline |
```

</process>

<common_pitfalls>

| Pitfall | Problem | Prevention |
|---------|---------|-----------|
| Silent convention drift | Implementations use different BCs, units, or material values | Run convention audit (step 2) before any composition |
| Interface mismatch | Module A produces data in format X, module B expects format Y | Verify interfaces before composing; write adapter if needed |
| Regression on best dimension | Unified version worse than best individual at something | Run regression check (step 5); investigate if any dimension regresses |
| Provenance loss | Can't trace which implementation a bug came from | Add provenance comments; maintain the comparison matrix |
| Mixing solver fidelity | Forward pass uses N iterations, gradient uses M < N | Always use same fidelity for forward and backward |

</common_pitfalls>

<success_criteria>

- [ ] All implementations inventoried with comparison matrix
- [ ] Conventions locked and conflicts resolved
- [ ] Score matrix produced with clear best-per-dimension
- [ ] Unified implementation runs end-to-end
- [ ] Verification checks pass (conservation, convergence, gradients)
- [ ] No regression vs best individual on any scored dimension
- [ ] Provenance table documents every module's source

</success_criteria>
