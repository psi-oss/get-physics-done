"""Regression tests for MCP skill tool list projection."""

from __future__ import annotations

import importlib
import sys
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


def test_get_skill_verify_work_surfaces_staged_loading_sidecar() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    staged_loading = WorkflowStageManifest(
        schema_version=1,
        workflow_id="verify-work",
        stages=(
            WorkflowStage(
                id="session_router",
                order=1,
                purpose="route verification sessions",
                mode_paths=("workflows/verify-work.md",),
                required_init_fields=(),
                loaded_authorities=("workflows/verify-work.md",),
                conditional_authorities=(),
                must_not_eager_load=("references/verification/meta/verification-independence.md",),
                allowed_tools=("file_read",),
                writes_allowed=(),
                produced_state=(),
                next_stages=(),
                checkpoints=(),
            ),
        ),
    )
    command = CommandDef(
        name="gpd:verify-work",
        description="Verify work.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=["file_read"],
        content="Command body.",
        path="/tmp/gpd-verify-work.md",
        source="commands",
        staged_loading=staged_loading,
    )
    skill = SkillDef(
        name="gpd-verify-work",
        description="Verify work.",
        content="Command body.",
        category="verification",
        path="/tmp/gpd-verify-work.md",
        source_kind="command",
        registry_name="verify-work",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-verify-work")

    assert result["staged_loading"]["workflow_id"] == "verify-work"
    assert result["staged_loading"]["stages"][0]["id"] == "session_router"
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
