# Equation Audit

## Scope

This audit covers every displayed equation retained in `paper/manuscript.md` and the corrected tracked equations in `GPD/STATE.md` and `GPD/state.json`.

## Audited Equations

### `m^2 R_{\mathrm{dS}}^2 = 4\Delta(1-\Delta)`

- Status: passes dimensional consistency once the de Sitter radius is kept explicit.
- Reason: `m^2` has dimension `[L]^{-2}` and `R_{\mathrm{dS}}^2` has dimension `[L]^2`, so the left-hand side is dimensionless and can consistently match the dimensionless function of `\Delta`.
- Limiting cases:
  - `\Delta \to 0`: `m^2 R_{\mathrm{dS}}^2 \to 0`.
  - `\Delta \to 1`: `m^2 R_{\mathrm{dS}}^2 \to 0`.
  - `\Delta = 1/2`: `m^2 R_{\mathrm{dS}}^2 = 1`.
- Correction applied: the stale shorthand `m^2 = 4\Delta(1-\Delta)` was removed from the retained paper/state layer because it suppresses the radius and is dimensionally ambiguous.
- GPD correspondence: this is the corrected version of `r-nv-correlator`.

### `G_{\mathrm{Liouville-dS}}^{(2)}(\tau_1,\tau_2;\lambda) = G_{\mathrm{DSSYK}}^{(2)}(\tau_1,\tau_2;\lambda)`

- Status: passes as a normalized correlator equality.
- Reason: both sides are the same type of boundary two-point function evaluated with the same arguments and the same double-scaling parameter `\lambda`, so the equality is dimensionally well-posed after common normalization.
- Limiting cases:
  - `\lambda \to 0`: the equality reduces to the semiclassical correlator picture behind the doubled-sector proposal.
  - finite `\lambda` in the double-scaling regime: the claim remains an exact two-point-function statement, not a full equality between complete thermodynamic theories.
- Correction applied: the tracked/state equation now specifies the two-point function rather than an unqualified equality `G_{\mathrm{Liouville-dS}} = G_{\mathrm{DSSYK}}`.
- GPD correspondence: this is the corrected version of `r-liouville-exact`.

## Schematic Relations Intentionally Left in Prose

The following statements remain in prose rather than as displayed equations because they are limiting or interpretive claims, not unit-sensitive equalities:

- upper-edge DSSYK scaling yields de Sitter JT gravity,
- naive Bekenstein-Hawking entropy fails in periodic/sine-dilaton models,
- restricted-sector duality is not the same claim as a full-model semiclassical de Sitter duality.

Keeping those statements in prose avoids presenting symbolic arrows or inequalities as if they were standalone derivational formulas.

## Tooling Note

I attempted to call the GPD MCP dimensional and limiting-case verifiers directly during this audit, but those calls again returned `user cancelled MCP tool call` in this workspace. The equation audit in this file is therefore manual and source-based rather than MCP-generated.
