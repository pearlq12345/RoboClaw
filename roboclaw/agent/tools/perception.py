"""Perception tools for the agent: scene understanding, depth, spatial reasoning."""
from __future__ import annotations

from typing import Any

from roboclaw.agent.tools.base import Tool
from roboclaw.embodied.perception import (
    DepthEstimator,
    SpatialReasoner,
    VLM,
    grab_all_frames,
    grab_frame,
)


class SceneUnderstandTool(Tool):
    """Ask a vision-language model to describe what a camera sees."""

    name = "scene_understand"
    description = (
        "Ask a question about what a camera sees. "
        "Use this to understand the robot's visual environment, "
        "detect objects, check if a grasp was successful, "
        "or compare before/after states."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["describe", "detect_objects", "grasp_check", "describe_all", "what_changed"],
                    "description": "The perception action to perform.",
                },
                "camera_alias": {
                    "type": "string",
                    "description": "Camera alias (from setup_show output, e.g. 'front', 'wrist').",
                },
                "question": {
                    "type": "string",
                    "description": "Free-text question for describe/describe_all actions.",
                },
                "object_name": {
                    "type": "string",
                    "description": "Target object name for detect_objects or grasp_check.",
                },
                "model": {
                    "type": "string",
                    "description": "Override VLM model (e.g. 'anthropic/claude-sonnet-4-5'). Uses default if omitted.",
                },
            },
            "required": ["action"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        action = kwargs.get("action", "describe")
        camera_alias = kwargs.get("camera_alias", "")
        model = kwargs.get("model") or None

        vlm = VLM()

        if action == "describe_all":
            results = vlm.describe_all(question=kwargs.get("question", "Describe this scene."), model=model)
            if not results:
                return "No cameras configured. Run setup_show first."
            lines = []
            for alias, desc in results.items():
                lines.append(f"[{alias}]: {desc.text}")
            return "\n".join(lines)

        if action == "describe":
            if not camera_alias:
                return "camera_alias is required for describe."
            result = vlm.describe(camera_alias, question=kwargs.get("question", "Describe what you see."), model=model)
            return f"[{camera_alias}]: {result.text}"

        if action == "detect_objects":
            if not camera_alias:
                return "camera_alias is required for detect_objects."
            if not kwargs.get("object_name"):
                return "object_name is required for detect_objects."
            result = vlm.detect_objects(camera_alias, kwargs["object_name"], model=model)
            return f"[{camera_alias}] {kwargs['object_name']}: {result.text}"

        if action == "grasp_check":
            if not camera_alias:
                return "camera_alias is required for grasp_check."
            if not kwargs.get("object_name"):
                return "object_name is required for grasp_check."
            result = vlm.grasp_check(camera_alias, kwargs["object_name"], model=model)
            return f"[{camera_alias}] grasp check for '{kwargs['object_name']}': {result.text}"

        if action == "what_changed":
            if not camera_alias:
                return "camera_alias is required for what_changed."
            frames = grab_all_frames()
            if camera_alias not in frames:
                return f"Camera '{camera_alias}' not found."
            # Grab a fresh "after" frame; "before" is whatever was last saved
            import tempfile, os
            tmp_before = os.path.join(tempfile.gettempdir(), f"roboclaw_before_{camera_alias}.npy")
            after_frame = grab_frame(camera_alias)
            if not after_frame:
                return f"Failed to grab current frame from '{camera_alias}'."
            import numpy as np
            if os.path.exists(tmp_before):
                before_frame = np.load(tmp_before)
                np.save(tmp_before, after_frame)
                from roboclaw.embodied.perception import VLM as VLM_cls
                v = VLM_cls()
                result = v.what_changed(camera_alias, before_frame, after_frame, model=model)
                return f"Changes on [{camera_alias}]: {result.text}"
            else:
                np.save(tmp_before, after_frame)
                return "No previous frame saved. Captured current frame as 'before'. Call again after the action to see what changed."

        return f"Unknown action: {action}"


class DepthTool(Tool):
    """Estimate depth from a camera frame."""

    name = "depth_estimate"
    description = (
        "Estimate a monocular depth map from a configured camera using Depth Anything 3. "
        "Returns a brief summary: min/max depth, mean depth, and whether DA3 model is available. "
        "Use this before planning grasp poses to check if the scene is in range."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "camera_alias": {
                    "type": "string",
                    "description": "Camera alias (from setup_show output).",
                },
            },
            "required": ["camera_alias"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        camera_alias = kwargs.get("camera_alias", "")
        frame = grab_frame(camera_alias)
        if frame is None:
            return f"No camera found with alias '{camera_alias}'."

        depth = DepthEstimator()
        dmap = depth.estimate(frame)
        if dmap is None:
            return (
                "Depth Anything 3 model is not available. "
                "Install it with: pip install transformers torch && python -c \"from transformers import AutoImageProcessor, AutoModelForDepthEstimation; AutoImageProcessor.from_pretrained('Depth-Anything/Depth-Anything-V2-Base-hf')\""
            )

        h, w = dmap.shape
        total = h * w
        return (
            f"Depth map for [{camera_alias}] ({w}x{h}):\n"
            f"  min={dmap.min():.3f}  max={dmap.max():.3f}  mean={dmap.mean():.3f} (normalized [0,1])\n"
            f"  Use pixel_to_3d for individual point back-projection."
        )


class SpatialTool(Tool):
    """Infer spatial relationships between objects from depth."""

    name = "spatial_relation"
    description = (
        "Infer spatial relationship (left/right/above/below/closer/farther) between two objects "
        "given their pixel bounding boxes. Requires depth estimation; falls back to center-position "
        "comparison if DA3 is unavailable."
    )

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "camera_alias": {
                    "type": "string",
                    "description": "Camera alias (from setup_show output).",
                },
                "object_a": {"type": "string", "description": "Name of the first object."},
                "bbox_a": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "[x_min, y_min, x_max, y_max] pixel coords for object_a.",
                },
                "object_b": {"type": "string", "description": "Name of the second object."},
                "bbox_b": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "[x_min, y_min, x_max, y_max] pixel coords for object_b.",
                },
            },
            "required": ["camera_alias", "object_a", "bbox_a", "object_b", "bbox_b"],
            "additionalProperties": False,
        }

    async def execute(self, **kwargs: Any) -> str:
        bbox_a = tuple(kwargs["bbox_a"])  # type: ignore[arg-type]
        bbox_b = tuple(kwargs["bbox_b"])  # type: ignore[arg-type]
        sr = SpatialReasoner()
        result = sr.relation_between(
            kwargs["camera_alias"],
            kwargs["object_a"],
            kwargs["object_b"],
            bbox_a,
            bbox_b,
        )
        conf = result.confidence
        return (
            f"{result.object_a} is '{result.relation}' {result.object_b} "
            f"(confidence: {conf:.0%})"
        )
