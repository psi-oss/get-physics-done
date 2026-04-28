"""Focused assertions for Phase 20 verify-work child-return seams."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_verify_work_verifier_handoff_stays_one_shot_and_routes_on_typed_status() -> None:
    workflow = _read(WORKFLOWS_DIR / "verify-work.md")

    assert "Spawn `gpd-verifier` once and let it own the physics policy." in workflow
    assert 'subagent_type="gpd-verifier"' in workflow
    assert "<spawn_contract>" in workflow
    assert "Route only on the canonical verification frontmatter and `gpd_return.status`; do not route on headings or marker strings." in workflow
    assert "If the canonical verification artifact is missing, unreadable, absent from `gpd_return.files_written`, or fails contract validation, treat the handoff as incomplete and request a fresh verifier continuation. Never trust the return text alone." in workflow
    assert "Human-readable headings in the verifier output are presentation only; route on the canonical verification frontmatter and `gpd_return.status`, not on headings or marker strings." in workflow
    assert "> Runtime delegation rule: this is a one-shot handoff. If the spawned verifier needs user input, it must checkpoint and return." in workflow
    assert "The wrapper must start a fresh continuation after the user responds instead of trying to keep the original verifier alive." in workflow
    assert "Do not recompute canonical verification status in this workflow." in workflow


def test_verify_work_verifier_sync_requires_artifact_gate_before_downstream_routing() -> None:
    workflow = _read(WORKFLOWS_DIR / "verify-work.md")

    assert "Route only on the canonical verification frontmatter and `gpd_return.status`; do not route on headings or marker strings." in workflow
    assert "`${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md` exists on disk and is readable" in workflow
    assert "the same path appears in `gpd_return.files_written`" in workflow
    assert 'gpd validate verification-contract "${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md"' in workflow
    assert "Do not recompute canonical verification status in this workflow." in workflow
    assert "If a canonical verification file already existed before this run" in workflow
    assert "If a canonical verification file already exists, preserve its authoritative frontmatter and append only the session-local overlay here." in workflow
    assert "Write to `${PHASE_DIR_ABS}/${phase_number}-VERIFICATION.md`." in workflow
    assert "Validate the final verification file, then commit it." in workflow
    assert workflow.count("Changed verification files fail `gpd pre-commit-check` when this header is missing or mismatched against the active lock.") == 1
    assert "If the verifier agent fails to spawn or returns an error, keep the session fail-closed." in workflow
    assert "Do not let a stale existing verification file satisfy the success path." in workflow


def test_verify_work_gap_plan_checker_routes_on_canonical_gpd_return_status() -> None:
    workflow = _read(WORKFLOWS_DIR / "verify-work.md")
    checker = _read(AGENTS_DIR / "gpd-plan-checker.md")

    assert 'gpd --raw init verify-work "${PHASE_ARG}" --stage gap_repair' in workflow
    assert "staged payload as the source of truth for planner and checker routing" in workflow
    assert "If the checker returns a structured `gpd_return`, route on `gpd_return.status` and the structured plan lists, not on presentation text:" in workflow
    assert "- `completed`: treat the fresh fix plans as verified only after the on-disk files still match the planner's `files_written` set." in workflow
    assert (
        "- `checkpoint`: some plans are approved and others need revision; record `approved_plans` and `blocked_plans`, then send only the blocked plans back through the revision loop."
        in workflow
    )
    assert "- `blocked`: nothing is approved; feed the checker issues and blocked plan IDs back into the revision loop without rewriting approved plans." in workflow
    assert "- `failed`: present the issues and offer retry or manual revision." in workflow
    assert "Use the structured fields, not the human-readable approval table, as the source of truth." in workflow

    assert "Headings such as `## VERIFICATION PASSED`, `## ISSUES FOUND`, and `## PLAN_BLOCKED — Escalation to User` are presentation only. Route on `gpd_return.status`." in checker
    assert "Headings above are presentation only. Route on `gpd_return.status`, the approved/blocked plan lists, and `issues`." in checker
    assert "approved_plans: [list of plan IDs that passed]" in checker
    assert "blocked_plans: [list of plan IDs needing revision or escalation]" in checker


def test_verify_work_gap_plan_success_reconciles_files_written_and_disk_artifacts() -> None:
    workflow = _read(WORKFLOWS_DIR / "verify-work.md")
    planner_prompt = _read(TEMPLATES_DIR / "planner-subagent-prompt.md")

    assert "Use `templates/planner-subagent-prompt.md` to build the gap_closure planner handoff from the staged payload." in workflow
    assert "Before treating the handoff as complete, verify that the expected `PLAN.md` files exist in the phase directory and are listed in `gpd_return.files_written` from the fresh planner run." in workflow
    assert (
        "If the planner fails to spawn or returns an error, keep the session fail-closed and offer retry or manual plan creation. Do not fall through to gap verification on the basis of preexisting `PLAN.md` files alone."
        in workflow
    )
    assert "Before accepting the handoff as complete, confirm the expected `PLAN.md` files are present, readable, and listed in `gpd_return.files_written` from the planner turn." in workflow
    assert "If the checker fails to spawn or returns an error, proceed without plan verification but note that the plans were not verified." in workflow
    assert "Do not rewrite approved plans during the revision round." in workflow
    assert "Do not fall through to gap verification on the basis of preexisting `PLAN.md` files alone." in workflow

    assert "Planner runs must return a structured `gpd_return` envelope." in planner_prompt
    assert "Do not route on them; route on `gpd_return.status` and the artifact gate below." in planner_prompt
    assert "- `gpd_return.status: completed` means the planner wrote the expected PLAN.md artifacts and they passed the on-disk artifact check." in planner_prompt
    assert "Always verify `gpd_return.files_written` against the expected plan artifacts before accepting completion." in planner_prompt


def test_verify_work_proof_check_handoff_uses_structured_freshness_and_fail_closed_artifact_gates() -> None:
    workflow = _read(WORKFLOWS_DIR / "verify-work.md")

    assert "Use `phase_proof_review_status` as the proof-review freshness summary." in workflow
    assert "> Runtime delegation rule: this is a single-turn handoff. If the spawned agent needs user input, it checkpoints and returns; do not keep the original run waiting inside the same task." in workflow
    assert "Return `status: checkpoint` instead of waiting for user input inside this run." in workflow
    assert "Never trust the return text alone; if the file is missing, stale, malformed, or not passed, keep the verification session fail-closed and start a fresh proof continuation." in workflow
    assert "After the proof critic returns, re-open `${PHASE_DIR_ABS}/${phase_number}-PROOF-REDTEAM.md` from disk and confirm the artifact exists and is `passed` before finalizing the gap ledger." in workflow
    assert "If `gpd-check-proof` still cannot produce a passed audit, keep the verification status fail-closed." in workflow
    assert "File-producing handoffs must prove the expected artifact exists before success is accepted." in workflow
