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
- The owning tests are `tests/test_repo_hygiene.py::test_command_workflow_parity_matches_allowlist`
  and `tests/test_repo_hygiene.py::test_command_workflow_allowlist_entries_reference_existing_surfaces`.
