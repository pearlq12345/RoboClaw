"""Tests for the learning workbench tool contract."""

from __future__ import annotations

import json

import pytest

from roboclaw.agent.tools.learning_workbench import LearningWorkbenchTool


def test_learning_workbench_schema_is_stable() -> None:
    tool = LearningWorkbenchTool()
    params = tool.parameters

    assert params["type"] == "object"
    assert params["required"] == ["action"]
    assert params["additionalProperties"] is False
    assert "dataset_id" in params["properties"]
    assert "workflow_id" in params["properties"]
    assert "open_workbench" in params["properties"]["action"]["enum"]
    assert "run_semantic_propagation" in params["properties"]["action"]["enum"]


@pytest.mark.asyncio
async def test_open_workbench_prefers_workflow_route() -> None:
    tool = LearningWorkbenchTool()

    result = json.loads(
        await tool.execute(
            action="open_workbench",
            dataset_id="lerobot/aloha_static_cups_open",
            workflow_id="wf-123",
        )
    )

    assert result["status"] == "ready"
    assert result["route"] == "/workbench/workflows/wf-123"


@pytest.mark.asyncio
async def test_pending_actions_return_structured_placeholder() -> None:
    tool = LearningWorkbenchTool()

    result = json.loads(await tool.execute(action="run_quality_filter", workflow_id="wf-456"))

    assert result["status"] == "pending"
    assert result["action"] == "run_quality_filter"
    assert result["workflow_id"] == "wf-456"
