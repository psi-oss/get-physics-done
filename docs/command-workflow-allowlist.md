# Command/Workflow Drift Allowlist

This document records the small set of intentional mismatches between
public command documents and workflow specifications so that the test
suite can guard against accidental drift.

## Command-only surfaces

- `health`
- `suggest-next`

## Workflow-only surfaces

- `execute-plan`
- `transition`
- `verify-phase`

## Maintenance

- Update this file whenever a new command/workflow divergence is approved.
- Keep the corresponding test in sync so the regression suite enforces the
  documented policy.
