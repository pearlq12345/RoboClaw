"""Structured learning-workbench tool for chat-first workflow orchestration."""

from __future__ import annotations

import json
from typing import Any

from roboclaw.agent.tools.base import Tool

_ACTIONS = [
    "open_workbench",
    "list_datasets",
    "create_workflow",
    "get_workflow_status",
    "run_quality_filter",
    "run_prototype_discovery",
    "list_prototypes",
    "get_annotation",
    "save_annotation",
    "get_annotation_suggestions",
    "run_semantic_propagation",
    "get_final_result",
    "start_train",
    "get_train_status",
]


class LearningWorkbenchTool(Tool):
    """Expose a stable contract for the future ProSemA-backed learning flow."""

    name = "learning_workbench"
    description = (
        "Coordinate the chat-first learning workbench. Use this tool to open the learning UI, "
        "create or inspect workflows, and trigger ProSemA-oriented workflow stages."
    )
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": _ACTIONS,
                "description": "Learning workbench action to perform.",
            },
            "dataset_id": {
                "type": "string",
                "description": "Dataset identifier for dataset/workflow actions.",
            },
            "workflow_id": {
                "type": "string",
                "description": "Workflow identifier for stateful actions.",
            },
            "annotation_id": {
                "type": "string",
                "description": "Annotation identifier when reading or writing a saved annotation.",
            },
            "notes": {
                "type": "string",
                "description": "Short operator note or request context.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs["action"]
        dataset_id = kwargs.get("dataset_id", "")
        workflow_id = kwargs.get("workflow_id", "")

        if action == "open_workbench":
            route = "/workbench"
            if workflow_id:
                route = f"/workbench/workflows/{workflow_id}"
            elif dataset_id:
                route = f"/workbench/datasets/{dataset_id}"
            return json.dumps(
                {
                    "status": "ready",
                    "action": action,
                    "route": route,
                    "message": "Open the learning workbench UI for structured review or annotation.",
                },
                ensure_ascii=False,
            )

        return json.dumps(
            {
                "status": "pending",
                "action": action,
                "dataset_id": dataset_id,
                "workflow_id": workflow_id,
                "message": (
                    "The learning workbench backend is not implemented yet. "
                    "Use this tool contract as the stable workflow interface for future phases."
                ),
            },
            ensure_ascii=False,
        )
