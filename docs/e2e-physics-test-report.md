# End-to-End Physics Test Report

This note records what is verifiable in this branch-local workspace. It does not reproduce the original Schwarzschild project bundle, so any claim that depends on that bundle is intentionally omitted here.

## Scope

The original test target was a Schwarzschild derivation workflow: metric ansatz, Christoffel symbols, Ricci tensor, and vacuum equations through to the final metric. In this pass I did not rerun that full physics derivation. Instead, I validated the tooling surfaces that the report depends on: paper-quality scoring, bibliography handling, verification MCP tools, and convention-lock behavior.

## Reproduction

Focused validation command:

```bash
uv run pytest tests/core/test_paper_quality.py tests/test_bibliography.py tests/core/test_verification_report_strict_status.py tests/core/test_conventions.py tests/mcp/test_verification_contract_server_regressions.py -q
```

Result:

- `251 passed in 2.42s`

## Verified Behavior

- `score_paper_quality` is deterministic and strict about blockers. The scoring model is defined in `src/gpd/core/paper_quality.py`, and the tests cover both a fully passing paper and papers with explicit blocking issues.
- The bibliography pipeline normalizes citation sources, deduplicates BibTeX keys, rejects extra fields, and writes audit metadata. The test suite exercises both the happy path and strict validation failures.
- The verification MCP tools are structural helpers, not CAS proof engines. `dimensional_check` validates bracket-annotated dimensions, while `limiting_case_check` and `symmetry_check` return documented guidance and classification rather than performing full symbolic verification.
- The convention-lock system normalizes aliases and metric-signature variants, parses `ASSERT_CONVENTION` directives from Markdown/LaTeX/Python comments, and reports mismatches against a lock.

## What This Report Does Not Claim

- It does not claim that the original Schwarzschild derivation was rerun in this repository snapshot.
- It does not quote numeric paper-quality scores, paper-readiness labels, or bibliography counts unless those values are derived from a captured input bundle.
- It does not treat the limiting-case or symmetry endpoints as automated theorem provers. The code and tests show that they provide structure and guidance, but rigorous math still requires an external symbolic check or a separately captured derivation artifact.

## Limitations

- The paper-quality model expects structured input, not raw LaTeX alone. Without the original JSON payload or generated artifact bundle, any score from the original branch-local run is not reproducible from this note.
- The verification tools deliberately stop short of full symbolic evaluation. They are useful for documenting checks and catching missing coverage, but they do not replace a CAS-backed derivation review.
- If you need a fully reproducible physics-result report, capture the exact input payload, the generated artifacts, and the command invocation together. This note only preserves the validation evidence available in this workspace.
