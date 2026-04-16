# Phase 00 Decision Log

1. Use `artifacts/bug-campaign` as the tracked campaign root because `tmp/` is ignored.
2. Treat `tmp/handoff-bundle` as the frozen source bundle and do not edit it.
3. Use nested raw JSON provenance over candidate Markdown headers when they disagree or lose line data.
4. Interpret `verified_from_source` as source-confirmed, not fresh-reproduced.
5. Keep Phase 08 reconstruction partial unless the original `/tmp/gpd-bug-campaign/repro/08-*` corpus is present.
6. Import only small Phase 11-14 summary/matrix artifacts from `/tmp/gpd-bug-campaign`, not run workspaces.
