Canonical manuscript-root publication preflight.

Resolve exactly one active manuscript root from the canonical manuscript family: `paper/`, `manuscript/`, or `draft/`.
In explicit-artifact mode, allow one `.tex`, `.md`, `.txt`, or `.pdf` review target outside those roots.

For a resumed manuscript, strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` from the resolved manuscript directory itself. Use `ARTIFACT-MANIFEST.json` first and `PAPER-CONFIG.json` second when selecting the active manuscript entry point. Do not use ad hoc wildcard discovery or first-match filename scans.
For explicit-artifact mode, nearby `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` are additive when present rather than blocking prerequisites.

Keep all manuscript-local support artifacts rooted at the same explicit manuscript directory, and do not satisfy strict review or packaging with artifacts copied from another manuscript root. Treat `gpd paper-build` as the authoritative step that regenerates the resolved manuscript-root `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`. In strict mode, `bibliography_audit_clean` and `reproducibility_ready` must pass before review or packaging proceeds.
