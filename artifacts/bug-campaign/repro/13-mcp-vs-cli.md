# Phase 13 MCP vs CLI

## Scope

This report covers the bridge-facing and direct-MCP comparison slice only.

## Raw CLI Anchor

- The copied `bridge-vs-cli` fixture workspaces were usable through raw CLI after rerunning `uv run gpd` with unrestricted access.
- The first sandboxed probe failed before GPD started because `uv` could not read `/Users/sergio/.cache/uv/sdists-v9/.git`.

## Runtime Bridge

- Case `ENV-02 bridge-vs-cli` closed as `bridge_bug`.
- The bridge-facing sidecar still reports `bridge_status=cancelled` while the CLI surface remains usable.
- That is a bridge-local mismatch rather than a workspace-state or config-dir failure.

## Direct MCP Tool Surface

- Case `ENV-03-direct-mcp-blocked-comparator` closed as `not_product_local`.
- Direct MCP calls were reachable and returned authoritative data on a copied fixture workspace.
- The blocked comparator families remained anchorless because the raw CLI comparator was still sandbox-blocked in the same environment.
- That means the MCP surface itself is not the failing substrate here; the missing stable comparator keeps those blocked references out of product-local closure.

## Blockers

- Sandbox `uv` cache denial blocks the first raw CLI probe unless unrestricted `uv run gpd` is allowed.
- Direct MCP cases without a stable CLI comparator remain `not_product_local` rather than being force-classified as bridge bugs.

## Verdict

- `bridge-vs-cli` is a real `bridge_bug`.
- Direct MCP / blocked comparator cases are `not_product_local` in the current environment because the comparator boundary is still unstable.
