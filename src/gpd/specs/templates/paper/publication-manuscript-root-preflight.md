Canonical manuscript-root publication preflight.

Resolve exactly one active manuscript root from the canonical manuscript family: `paper/`, `manuscript/`, or `draft/`.
In explicit-artifact mode, allow one `.tex`, `.md`, `.txt`, or `.pdf` review target outside those roots.
Workflow-specific intake policy remains authoritative: this template defines manuscript-root resolution and manuscript-local artifact gating, but it does not by itself authorize standalone external-subject support for every publication command.
If publication-managed intake/provenance state exists under `GPD/publication/{subject_slug}/intake/`, treat it as intake state only. Keep `GPD/publication/{subject_slug}/manuscript/` as the sole authoritative managed manuscript/build root, and do not let `intake/` participate in manuscript-root discovery or manuscript-local artifact selection.

For a resumed manuscript, strict preflight reads `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` from the resolved manuscript directory itself. Use `ARTIFACT-MANIFEST.json` first and `PAPER-CONFIG.json` second when selecting the active manuscript entry point. Do not use ad hoc wildcard discovery or first-match filename scans.
For explicit-artifact mode, nearby `ARTIFACT-MANIFEST.json`, `BIBLIOGRAPHY-AUDIT.json`, and `reproducibility-manifest.json` are additive when present rather than blocking prerequisites.

Keep all manuscript-local support artifacts rooted at the same explicit manuscript directory, and do not satisfy strict review or packaging with artifacts copied from another manuscript root. Treat `gpd paper-build` as the authoritative step that regenerates the resolved manuscript-root `ARTIFACT-MANIFEST.json` and `BIBLIOGRAPHY-AUDIT.json`. In strict mode, `bibliography_audit_clean` and `reproducibility_ready` must pass before review or packaging proceeds.
Keep GPD-authored auxiliary review, response, and packaging outputs under `GPD/`, but do not treat that as a manuscript-root migration. The manuscript draft and manuscript-local manifests remain rooted at the resolved manuscript directory.
