"""Regression tests for MCP skill tool list projection."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from unittest.mock import patch

import gpd.registry as registry_module
from gpd.core.workflow_staging import WorkflowStage, WorkflowStageConditionalAuthority, WorkflowStageManifest
from gpd.registry import AgentDef, CommandDef, SkillDef


def test_get_skill_command_allowed_tools_are_defensive_copies() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    command_tools = ["file_read", "shell", "shell"]
    command = CommandDef(
        name="gpd:help",
        description="Help.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=command_tools,
        content="Command body.",
        path="/tmp/gpd-help.md",
        source="commands",
    )
    skill = SkillDef(
        name="gpd-help",
        description="Help.",
        content="Command body.",
        category="help",
        path="/tmp/gpd-help.md",
        source_kind="command",
        registry_name="help",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-help")

    assert result["allowed_tools"] == ["file_read", "shell"]
    assert result["allowed_tools"] is not command.allowed_tools
    assert result["allowed_tools_surface"] == "command.allowed-tools"
    result["allowed_tools"].append("network")
    assert command.allowed_tools == ["file_read", "shell", "shell"]


def test_get_skill_command_surfaces_agent_metadata() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    command = CommandDef(
        name="gpd:plan-phase",
        description="Plan.",
        argument_hint="",
        agent="gpd-planner",
        requires={},
        allowed_tools=["file_read"],
        content="## Command Requirements\n\n```yaml\ncontext_mode: project-required\nproject_reentry_capable: false\nagent: gpd-planner\nallowed_tools:\n  - file_read\n```\n\nBody.",
        path="/tmp/gpd-plan-phase.md",
        source="commands",
    )
    skill = SkillDef(
        name="gpd-plan-phase",
        description="Plan.",
        content=command.content,
        category="planning",
        path="/tmp/gpd-plan-phase.md",
        source_kind="command",
        registry_name="plan-phase",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-plan-phase")

    assert result["agent"] == "gpd-planner"
    assert result["allowed_tools_surface"] == "command.allowed-tools"
    assert result["structured_metadata_authority"]["agent"] == "mirrored"
    assert "agent: gpd-planner" in result["content"]


def test_list_skills_filters_consistency_checker_by_verification_category() -> None:
    from gpd.mcp.servers.skills_server import list_skills

    consistency_checker = SkillDef(
        name="gpd-consistency-checker",
        description="Consistency checker.",
        content="Consistency checker body.",
        category="verification",
        path="/tmp/gpd-consistency-checker.md",
        source_kind="agent",
        registry_name="gpd-consistency-checker",
    )
    help_skill = SkillDef(
        name="gpd-help",
        description="Help.",
        content="Help body.",
        category="help",
        path="/tmp/gpd-help.md",
        source_kind="command",
        registry_name="help",
    )

    with patch("gpd.mcp.servers.skills_server._load_skill_index", return_value=[consistency_checker, help_skill]):
        result = list_skills(category="verification")

    assert result["count"] == 1
    assert result["skills"] == [
        {
            "name": "gpd-consistency-checker",
            "category": "verification",
            "description": "Consistency checker.",
        }
    ]
    assert result["categories"] == ["help", "verification"]


def test_list_skills_filters_beginner_help_entrypoints_by_help_category() -> None:
    from gpd.mcp.servers.skills_server import list_skills

    registry_module.invalidate_cache()
    help_skill = registry_module.get_skill("gpd-help")
    start_skill = registry_module.get_skill("gpd-start")
    tour_skill = registry_module.get_skill("gpd-tour")

    with patch(
        "gpd.mcp.servers.skills_server._load_skill_index",
        return_value=[help_skill, start_skill, tour_skill],
    ):
        result = list_skills(category="help")

    assert result["count"] == 3
    assert result["skills"] == [
        {
            "name": "gpd-help",
            "category": "help",
            "description": help_skill.description,
        },
        {
            "name": "gpd-start",
            "category": "help",
            "description": start_skill.description,
        },
        {
            "name": "gpd-tour",
            "category": "help",
            "description": tour_skill.description,
        },
    ]
    assert result["categories"] == ["help"]


def test_get_skill_command_surfaces_staged_loading_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    staged_loading = WorkflowStageManifest(
        schema_version=1,
        workflow_id="new-project",
        stages=(
            WorkflowStage(
                id="scope_intake",
                order=1,
                purpose="intake",
                mode_paths=("workflows/new-project.md",),
                required_init_fields=("researcher_model",),
                loaded_authorities=("workflows/new-project.md",),
                conditional_authorities=(
                    WorkflowStageConditionalAuthority(
                        when="conditional",
                        authorities=("references/research/questioning.md",),
                    ),
                ),
                must_not_eager_load=("references/research/questioning.md",),
                allowed_tools=("file_read",),
                writes_allowed=(),
                produced_state=(),
                next_stages=(),
                checkpoints=(),
            ),
        ),
    )
    command = CommandDef(
        name="gpd:new-project",
        description="New project.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path="/tmp/gpd-new-project.md",
        source="commands",
        staged_loading=staged_loading,
    )
    skill = SkillDef(
        name="gpd-new-project",
        description="New project.",
        content="Command body.",
        category="project",
        path="/tmp/gpd-new-project.md",
        source_kind="command",
        registry_name="new-project",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-new-project")

    assert result["staged_loading"]["workflow_id"] == "new-project"
    assert result["staged_loading"]["stages"][0]["id"] == "scope_intake"
    assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"


def test_get_skill_plan_phase_surfaces_staged_loading_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    staged_loading = WorkflowStageManifest(
        schema_version=1,
        workflow_id="plan-phase",
        stages=(
            WorkflowStage(
                id="phase_bootstrap",
                order=1,
                purpose="phase lookup",
                mode_paths=("workflows/plan-phase.md",),
                required_init_fields=("researcher_model",),
                loaded_authorities=("workflows/plan-phase.md",),
                conditional_authorities=(),
                must_not_eager_load=("references/ui/ui-brand.md",),
                allowed_tools=("file_read",),
                writes_allowed=(),
                produced_state=(),
                next_stages=("research_routing",),
                checkpoints=(),
            ),
        ),
    )
    command = CommandDef(
        name="gpd:plan-phase",
        description="Plan.",
        argument_hint="",
        agent="gpd-planner",
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path="/tmp/gpd-plan-phase.md",
        source="commands",
        staged_loading=staged_loading,
    )
    skill = SkillDef(
        name="gpd-plan-phase",
        description="Plan.",
        content="Command body.",
        category="planning",
        path="/tmp/gpd-plan-phase.md",
        source_kind="command",
        registry_name="plan-phase",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-plan-phase")

    assert result["staged_loading"]["workflow_id"] == "plan-phase"
    assert result["staged_loading"]["stages"][0]["id"] == "phase_bootstrap"
    assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"


def test_get_skill_command_surfaces_spawn_contract_sidecar_without_content_injection() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    spawn_contracts = (
        {
            "agent": "gpd-notation-coordinator",
            "shared_state_policy": "return_only",
            "write_scope": {"mode": "scoped_write", "paths": ["GPD/CONVENTIONS.md"]},
            "expected_artifacts": ["GPD/CONVENTIONS.md"],
        },
    )
    command = CommandDef(
        name="gpd:new-project",
        description="New project.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path="/tmp/gpd-new-project.md",
        source="commands",
        spawn_contracts=spawn_contracts,
    )
    skill = SkillDef(
        name="gpd-new-project",
        description="New project.",
        content="Command body.",
        category="project",
        path="/tmp/gpd-new-project.md",
        source_kind="command",
        registry_name="new-project",
        spawn_contracts=spawn_contracts,
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-new-project")

    assert result["content"] == "Command body."
    assert result["spawn_contracts"] == [dict(spawn_contracts[0])]
    assert result["spawn_contracts"] is not command.spawn_contracts
    result["spawn_contracts"][0]["expected_artifacts"].append("GPD/EXTRA.md")
    assert command.spawn_contracts[0]["expected_artifacts"] == ["GPD/CONVENTIONS.md"]
    assert result["structured_metadata_authority"]["spawn_contracts"] == "mirrored"


def test_get_skill_execute_phase_surfaces_staged_loading_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    staged_loading = WorkflowStageManifest(
        schema_version=1,
        workflow_id="execute-phase",
        stages=(
            WorkflowStage(
                id="phase_bootstrap",
                order=1,
                purpose="phase lookup and routing",
                mode_paths=("workflows/execute-phase.md",),
                required_init_fields=(),
                loaded_authorities=("workflows/execute-phase.md",),
                conditional_authorities=(),
                must_not_eager_load=("references/ui/ui-brand.md",),
                allowed_tools=("file_read",),
                writes_allowed=(),
                produced_state=(),
                next_stages=(),
                checkpoints=(),
            ),
        ),
    )
    command = CommandDef(
        name="gpd-execute-phase",
        description="Execute.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=["file_read"],
        content="Execute body.",
        path="/tmp/gpd-execute-phase.md",
        source="commands",
        staged_loading=staged_loading,
    )
    skill = SkillDef(
        name="gpd-execute-phase",
        description="Execute.",
        content="Execute body.",
        category="execution",
        path="/tmp/gpd-execute-phase.md",
        source_kind="command",
        registry_name="execute-phase",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-execute-phase")

    assert result["staged_loading"]["workflow_id"] == "execute-phase"
    assert result["staged_loading"]["stages"][0]["id"] == "phase_bootstrap"
    assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"


def test_get_skill_index_surfaces_spawn_contract_presence_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill_index

    skill = SkillDef(
        name="gpd-new-project",
        description="New project.",
        content="Command body.",
        category="project",
        path="/tmp/gpd-new-project.md",
        source_kind="command",
        registry_name="new-project",
    )
    command = CommandDef(
        name="gpd:new-project",
        description="New project.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path="/tmp/gpd-new-project.md",
        source="commands",
        spawn_contracts=(
            {
                "agent": "gpd-notation-coordinator",
                "shared_state_policy": "return_only",
                "write_scope": {"mode": "scoped_write", "paths": ["GPD/CONVENTIONS.md"]},
                "expected_artifacts": ["GPD/CONVENTIONS.md"],
            },
        ),
    )

    with (
        patch("gpd.mcp.servers.skills_server._load_skill_index", return_value=[skill]),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill_index()

    assert result["total_skills"] == 1
    assert result["command_envelopes"]["gpd-new-project"]["has_spawn_contracts"] is True
    assert result["command_envelopes"]["gpd-new-project"]["has_review_contract"] is False


def test_get_skill_verify_work_surfaces_staged_loading_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    repo_root = Path(__file__).resolve().parents[2]
    manifest_path = repo_root / "src" / "gpd" / "specs" / "workflows" / "verify-work-stage-manifest.json"
    original_resolve_manifest_path = registry_module.resolve_workflow_stage_manifest_path
    with (
        patch(
            "gpd.registry.resolve_workflow_stage_manifest_path",
            lambda workflow_id: manifest_path
            if workflow_id == "verify-work"
            else original_resolve_manifest_path(workflow_id),
        ),
    ):
        registry_module.invalidate_cache()
        result = get_skill("gpd-verify-work")

    assert [stage["id"] for stage in result["staged_loading"]["stages"]] == [
        "session_router",
        "phase_bootstrap",
        "inventory_build",
        "interactive_validation",
        "gap_repair",
    ]
    assert result["staged_loading"]["workflow_id"] == "verify-work"
    assert result["staged_loading"]["stages"][0]["loaded_authorities"] == ["workflows/verify-work.md"]
    assert "Follow the included workflow file exactly." in result["content"]
    assert (
        "The workflow file owns the detailed check taxonomy; this wrapper only bootstraps the canonical "
        "verification surfaces and delegates the physics checks."
        in result["content"]
    )
    assert "Severity Classification" not in result["content"]
    assert "One check at a time, plain text responses, no interrogation." not in result["content"]
    assert "Physics verification is not binary:" not in result["content"]
    assert "For deeper focused analysis" not in result["content"]
    assert result["staged_loading"]["stages"][2]["loaded_authorities"] == [
        "workflows/verify-work.md",
        "references/verification/meta/verification-independence.md",
    ]
    assert result["staged_loading"]["stages"][2]["next_stages"] == ["interactive_validation"]
    assert result["staged_loading"]["stages"][2]["checkpoints"] == [
        "verifier delegation completed",
        "handoff remains fail-closed",
        "anchor obligations explicit",
    ]
    assert result["staged_loading"]["stages"][3]["allowed_tools"] == [
        "ask_user",
        "file_read",
        "file_edit",
        "file_write",
        "find_files",
        "search_files",
        "shell",
        "task",
    ]
    assert result["staged_loading"]["stages"][3]["loaded_authorities"] == [
        "workflows/verify-work.md",
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
    ]
    assert result["staged_loading"]["stages"][3]["writes_allowed"] == ["GPD/phases/XX-name/XX-VERIFICATION.md"]
    assert result["staged_loading"]["stages"][3]["next_stages"] == ["gap_repair"]
    assert result["staged_loading"]["stages"][3]["checkpoints"] == [
        "verification file can be written",
        "writer-stage schema is visible",
        "check results remain contract-backed",
    ]
    assert result["staged_loading"]["stages"][4]["loaded_authorities"] == [
        "workflows/verify-work.md",
        "templates/research-verification.md",
        "templates/verification-report.md",
        "templates/contract-results-schema.md",
        "references/shared/canonical-schema-discipline.md",
        "references/protocols/error-propagation-protocol.md",
    ]
    assert result["staged_loading"]["stages"][4]["writes_allowed"] == ["GPD/phases/XX-name/XX-VERIFICATION.md"]
    assert result["staged_loading"]["stages"][4]["next_stages"] == []
    assert result["staged_loading"]["stages"][4]["checkpoints"] == [
        "gaps are diagnosed",
        "repair plans are verified",
        "verification closeout is ready",
    ]
    assert result["structured_metadata_authority"]["staged_loading"] == "mirrored"
    assert result["allowed_tools_surface"] == "command.allowed-tools"


def test_get_skill_unrelated_command_does_not_expose_stage_sidecars() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    command = CommandDef(
        name="gpd:help",
        description="Help.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path="/tmp/gpd-help.md",
        source="commands",
    )
    skill = SkillDef(
        name="gpd-help",
        description="Help.",
        content="Command body.",
        category="help",
        path="/tmp/gpd-help.md",
        source_kind="command",
        registry_name="help",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-help")

    assert "staged_loading" not in result
    assert "staged_loading" not in result["structured_metadata_authority"]
    assert "new-project-stage-manifest.json" not in result["content"]


def test_get_skill_agent_surfaces_allowed_tools() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    agent_tools = ["shell", "file_read", "shell"]
    agent = AgentDef(
        name="gpd-debugger",
        description="Debugger.",
        system_prompt="Agent body.",
        tools=agent_tools,
        color="blue",
        path="/tmp/gpd-debugger.md",
        source="agents",
    )
    skill = SkillDef(
        name="gpd-debugger",
        description="Debugger.",
        content="Agent body.",
        category="debugging",
        path="/tmp/gpd-debugger.md",
        source_kind="agent",
        registry_name="gpd-debugger",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_agent", return_value=agent),
    ):
        result = get_skill("gpd-debugger")

    assert result["allowed_tools"] == ["shell", "file_read"]
    assert result["allowed_tools"] is not agent.tools
    assert result["allowed_tools_surface"] == "agent.tools"
    assert result["structured_metadata_authority"] == {
        "content": "canonical",
        "allowed_tools": "mirrored",
        "agent_policy": "mirrored",
    }
    result["allowed_tools"].append("network")
    assert agent.tools == ["shell", "file_read", "shell"]


def test_get_skill_debugger_agent_keeps_schema_dependencies_transitive_only() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    result = get_skill("gpd-debugger")

    assert result["allowed_tools_surface"] == "agent.tools"
    assert result["schema_references"] == []
    assert result["schema_documents"] == []
    assert result["contract_references"] == []
    assert result["contract_documents"] == []
    assert result["transitive_schema_references"] == []
    assert result["transitive_schema_documents"] == []
    assert result["structured_metadata_authority"] == {
        "content": "canonical",
        "allowed_tools": "mirrored",
        "agent_policy": "mirrored",
    }


def test_get_skill_executor_agent_does_not_expose_staged_loading_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    result = get_skill("gpd-executor")

    assert result["allowed_tools_surface"] == "agent.tools"
    assert result["structured_metadata_authority"] == {
        "content": "canonical",
        "allowed_tools": "mirrored",
        "agent_policy": "mirrored",
    }
    assert "staged_loading" not in result
    assert "staged_loading" not in result["structured_metadata_authority"]


def test_get_skill_planner_agent_does_not_expose_staged_loading_sidecar(monkeypatch) -> None:
    from pathlib import Path

    from gpd import registry as content_registry
    from gpd.mcp.servers.skills_server import get_skill

    repo_agents_dir = Path(__file__).resolve().parents[2] / "src/gpd/agents"
    monkeypatch.setattr(content_registry, "AGENTS_DIR", repo_agents_dir)
    content_registry.invalidate_cache()

    result = get_skill("gpd-planner")

    assert result["allowed_tools_surface"] == "agent.tools"
    assert result["structured_metadata_authority"]["content"] == "canonical"
    assert "staged_loading" not in result
    assert "staged_loading" not in result["structured_metadata_authority"]


def test_get_skill_plan_checker_agent_surfaces_direct_schema_dependency_and_least_privilege(
    tmp_path, monkeypatch
) -> None:
    from functools import lru_cache
    from shutil import copytree

    from gpd import registry as content_registry
    from gpd.mcp.servers.skills_server import get_skill

    agents_dir = tmp_path / "agents"
    copytree(Path(__file__).resolve().parents[2] / "src" / "gpd" / "agents", agents_dir)
    plan_checker_path = agents_dir / "gpd-plan-checker.md"
    plan_checker_text = plan_checker_path.read_text(encoding="utf-8")
    plan_checker_text = plan_checker_text.replace(
        "artifact_write_authority: return_only",
        "artifact_write_authority: read_only",
    )
    plan_checker_path.write_text(
        plan_checker_text.replace(
            "tools: file_read, file_write, shell, find_files, search_files, web_search, web_fetch",
            "tools: file_read, shell, find_files, search_files, web_search, web_fetch",
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(content_registry, "AGENTS_DIR", agents_dir)
    monkeypatch.setattr(
        content_registry,
        "_builtin_agent_names",
        lru_cache(maxsize=1)(lambda: frozenset()),
    )
    content_registry.invalidate_cache()

    result = get_skill("gpd-plan-checker")
    schema_documents = {Path(entry["path"]).name: entry for entry in result["schema_documents"]}

    assert result["allowed_tools_surface"] == "agent.tools"
    assert "file_write" not in result["allowed_tools"]
    assert any(path.endswith("plan-contract-schema.md") for path in result["schema_references"])
    assert "@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" in result["content"]
    assert "plan-contract-schema.md" in schema_documents
    assert "PLAN Contract Schema" in schema_documents["plan-contract-schema.md"]["body"]


def test_skills_server_import_is_resilient_to_registry_index_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        registry_module,
        "list_skills",
        lambda: (_ for _ in ()).throw(ValueError("boom")),
    )
    sys.modules.pop("gpd.mcp.servers.skills_server", None)

    module = importlib.import_module("gpd.mcp.servers.skills_server")

    assert hasattr(module, "list_skills")
    assert hasattr(module, "get_skill")
