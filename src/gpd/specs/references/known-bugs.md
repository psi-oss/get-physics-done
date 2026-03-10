# Known Bugs Affecting GPD Workflows

Last updated: 2026-02-24

This file is an index. Full details are in the sub-files linked below.

- **Active bugs:** [known-bugs-active.md](known-bugs-active.md)
- **Resolved bugs:** [known-bugs-resolved.md](known-bugs-resolved.md)

## Summary

| Bug # | Title | Status | File |
|-------|-------|--------|------|
| 1 | Phase Number Parsing Bugs (lossy numeric parsing / naive sorting) | Fixed | [resolved](known-bugs-resolved.md) |
| 2 | State Dual-Write Consistency | Improved (arch remains) | [active](known-bugs-active.md) |
| 3 | Convention Source-of-Truth Multiplicity | Substantially resolved (no pre-commit hook) | [active](known-bugs-active.md) |
| 4 | Context Window Compression Artifacts | Mitigated (platform issue) | [active](known-bugs-active.md) |
| 5 | Git Tag Accumulation from Failed Plans | Workaround only | [active](known-bugs-active.md) |
| 6 | Dollar Sign Backreference in State Replace Calls | Fixed | [resolved](known-bugs-resolved.md) |
| 7 | Phase Remove Cascading Renumber in ROADMAP.md | Fixed | [resolved](known-bugs-resolved.md) |
| 8 | Installer Error Recovery Could Delete Original Data | Fixed | [resolved](known-bugs-resolved.md) |
| 9 | Progress Data Loss from Unconditional Delete in syncStateJson | Fixed | [resolved](known-bugs-resolved.md) |
| 10 | NaN Propagation from Non-Numeric Total Phases/Plans | Fixed | [resolved](known-bugs-resolved.md) |
| 11 | progress_percent Null-to-Zero Roundtrip Corruption | Fixed | [resolved](known-bugs-resolved.md) |
| 12 | depends-on Hyphenated YAML Key Ignored in Wave Validation | Fixed | [resolved](known-bugs-resolved.md) |
| 13 | gpd CLI Required a Deprecated Runtime 18+ (Caveat) | Obsolete (CLI rewritten in Python) | [resolved](known-bugs-resolved.md) |
| 14 | Concurrent Agent File Edit Conflicts | Workaround only | [active](known-bugs-active.md) |
| 15 | State Auto-Compact Implementation Lost During Concurrent Edits | Fixed | [resolved](known-bugs-resolved.md) |
| 16 | validate-return Command Integration | Fixed | [resolved](known-bugs-resolved.md) |
| 17 | verify-conventions Not Integrated Into Inter-Wave Gates | Fixed | [resolved](known-bugs-resolved.md) |
| 18 | Reference Files — Content Duplicated Inline and as Extracted Files | Partially resolved | [active](known-bugs-active.md) |
| 19 | Workflow Init Error Handling Inconsistency | Fixed | [resolved](known-bugs-resolved.md) |
| 20 | Agent Init Error Handling Gap | Fixed | [resolved](known-bugs-resolved.md) |
| 21 | NaN Guard Gaps in gpd CLI parseInt Calls | Fixed | [resolved](known-bugs-resolved.md) |
| 22 | cost-track Command Not Implemented | Fixed | [resolved](known-bugs-resolved.md) |
| 23 | pre-commit-check Only Used in 2 Workflows | Fixed | [resolved](known-bugs-resolved.md) |
| 24 | Verification Gap Analysis Coverage Matrix Was Overstated | Fixed (documentation) | [active](known-bugs-active.md) |
| 25 | Exploratory Profile Verification Void | Reduced (~16 unprotected) | [active](known-bugs-active.md) |
| 26 | derive-equation.md Bypasses All Convention Defense Layers | Fixed | [resolved](known-bugs-resolved.md) |
| 27 | executor-completion.md Used Wrong Return Envelope Key | Fixed | [resolved](known-bugs-resolved.md) |
| 28 | gpd-debugger Used Raw Git Commands / ASSERT_CONVENTION Normalization | Fixed | [resolved](known-bugs-resolved.md) |
| 29 | gpd-verifier Missing "Spawned By" Documentation | Fixed | [resolved](known-bugs-resolved.md) |

## Platform-Specific Known Issues

See [known-bugs-active.md](known-bugs-active.md) for:
- CC#1: classifyHandoffIfNeeded False Failure
- CC#2: @-Reference Behavior in task() Prompts

## Other Platform-Specific Bugs

See [known-bugs-resolved.md](known-bugs-resolved.md) for monitoring-status platform bugs (P1-P5).

## Recent Structural Improvements

See [known-bugs-resolved.md](known-bugs-resolved.md) for the full list of structural improvements from the 2026-02-22/23 session.
