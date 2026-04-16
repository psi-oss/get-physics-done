# Phase 01 Taxonomy Spec

## Units

- Candidate: one verifier record from the source bundle; not a unique bug type.
- Atomic finding: one expected-vs-actual claim with one trigger and one scope.
- Bug type: one broken invariant on one product surface under one trigger scope.
- Symptom: downstream manifestation of a bug type on another surface.
- Noise record: environment pollution, missing prerequisite, sandbox constraint, observer failure, or transport failure.

## Merge Key

Use `surface x invariant x trigger x scope`.  Do not merge on title, category,
experiment slug, or raw fingerprint alone.

## Confidence Policy

The raw and verified confidence scores are triage evidence only.  They do not
replace deterministic reproduction and must not close a bug type.
