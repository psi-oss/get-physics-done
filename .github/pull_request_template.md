## What changed

<!-- Brief description of the changes -->

## Why

<!-- Motivation: what problem does this solve? -->

## Testing done

<!-- How did you verify this works? -->

## Phase 15 Verification

- [ ] Red exact repro is recorded for the fixed family
- [ ] Green exact fix is recorded for the fixed family
- [ ] Green adjacent checks are recorded for the fixed family
- [ ] Artifact JSON written under `artifacts/phases/15-verification-contract/verification/fixes/<bug-id>.json`

## Checklist

- [ ] Tests pass (`uv run pytest -v`)
- [ ] Lint clean (`ruff check src/ tests/`)
- [ ] No secrets or credentials in the diff
- [ ] User-facing docs updated (if behavior or install flow changed)
