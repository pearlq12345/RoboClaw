"""Source registry + curated model catalog.

Two registries live in this module:

1. :data:`SOURCE_REGISTRY` — name → ``ModelSource`` class. Tells the
   system which classes know how to fetch which kind of ref.
2. :data:`CURATED_MODELS` — short-slug → ``ModelRef``. A friendly
   alias table so users can write ``pull("alphabrain-neurovla")``
   instead of remembering ``"AlphaBrainGroup/NeuroVLA"``.

The curated catalog is intentionally a flat dict — extension is a
single-line addition, no plug-in framework.
"""

from __future__ import annotations

from roboclaw.embodied.policy.base import ModelRef, ModelSource
from roboclaw.embodied.policy.huggingface import HuggingFaceModelSource
from roboclaw.embodied.policy.local import LocalModelSource

# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------

SOURCE_REGISTRY: dict[str, type[ModelSource]] = {
    "huggingface": HuggingFaceModelSource,
    "local": LocalModelSource,
}


def get_source(name: str) -> type[ModelSource]:
    """Look up a model source class by name."""
    cls = SOURCE_REGISTRY.get(name)
    if cls is None:
        raise ValueError(
            f"Unknown model source: '{name}'. "
            f"Available: {sorted(SOURCE_REGISTRY.keys())}"
        )
    return cls


def register_source(name: str, source_cls: type[ModelSource]) -> None:
    """Add a custom :class:`ModelSource` class to the registry."""
    if name in SOURCE_REGISTRY:
        raise ValueError(
            f"Source '{name}' is already registered. "
            f"Use a different name or remove the existing entry first."
        )
    SOURCE_REGISTRY[name] = source_cls


# ---------------------------------------------------------------------------
# Curated catalog
# ---------------------------------------------------------------------------

CURATED_MODELS: dict[str, ModelRef] = {
    # FluxVLA (LimX Dynamics, 2026)
    "fluxvla-engine": ModelRef(
        source="huggingface",
        repo_id="limxdynamics/FluxVLAEngine",
        framework="fluxvla",
        notes="FluxVLA full engine release (Pi / GR00T / DreamZero).",
        access="public",
        size_label="约 166 GiB",
    ),
    # Public open-source VLA / policy baselines
    "openvla-7b": ModelRef(
        source="huggingface",
        repo_id="openvla/openvla-7b",
        framework="openvla",
        notes="OpenVLA 7B from Stanford / Google.",
        access="public",
        size_label="约 14 GiB",
        v1_ready=True,
    ),
    "openvla-libero-ft": ModelRef(
        source="huggingface",
        repo_id="moojink/openvla-7b-oft-finetuned-libero-spatial-object-goal-10",
        framework="openvla",
        notes="公开可拉取的 OpenVLA Libero finetune 版本。",
        access="public",
        track="dataset_finetune",
        size_label="约 15 GiB",
        v1_ready=True,
    ),
    "pi0": ModelRef(
        source="huggingface",
        repo_id="lerobot/pi0",
        framework="lerobot",
        notes="LeRobot 官方公开的 Pi0 policy checkpoint。",
        access="public",
        size_label="约 13 GiB",
        v1_ready=True,
    ),
    "smolvla": ModelRef(
        source="huggingface",
        repo_id="lerobot/smolvla_base",
        framework="lerobot",
        notes="LeRobot 官方公开的 SmolVLA base checkpoint。",
        access="public",
        size_label="约 0.9 GiB",
        v1_ready=True,
    ),
    "smolvla-libero": ModelRef(
        source="huggingface",
        repo_id="lerobot/smolvla_libero",
        framework="lerobot",
        notes="LeRobot 官方公开的 SmolVLA Libero finetune。",
        access="public",
        track="dataset_finetune",
        size_label="约 0.9 GiB",
        v1_ready=True,
    ),
    "smolvla-vlabench": ModelRef(
        source="huggingface",
        repo_id="lerobot/smolvla_vlabench",
        framework="lerobot",
        notes="LeRobot 官方公开的 SmolVLA VLABench finetune。",
        access="public",
        track="dataset_finetune",
        size_label="约 0.9 GiB",
        v1_ready=True,
    ),
    "octo-base": ModelRef(
        source="huggingface",
        repo_id="rail-berkeley/octo-base",
        framework="octo",
        notes="公开可拉取的 Octo base checkpoint。",
        access="public",
        size_label="约 0.8 GiB",
        v1_ready=True,
    ),
    "octo-small-1.5": ModelRef(
        source="huggingface",
        repo_id="rail-berkeley/octo-small-1.5",
        framework="octo",
        notes="公开可拉取的 Octo small 1.5 checkpoint。",
        access="public",
        size_label="约 0.5 GiB",
        v1_ready=True,
    ),
    # Public foundation backbones
    "v-jepa-2-vit-l": ModelRef(
        source="huggingface",
        repo_id="facebook/vjepa2-vitl-fpc64-256",
        framework="backbone",
        notes="公开可拉取的 V-JEPA 2 ViT-L visual backbone。",
        access="public",
        size_label="约 6 GiB",
    ),
}


def get_curated(slug: str) -> ModelRef:
    """Resolve a curated short-slug to its :class:`ModelRef`."""
    ref = CURATED_MODELS.get(slug)
    if ref is None:
        raise KeyError(
            f"Unknown curated model: '{slug}'. "
            f"Use list_curated_slugs() to see available entries."
        )
    return ref


def list_curated_slugs(*, v1_only: bool = False) -> tuple[str, ...]:
    """Return curated short-slugs sorted alphabetically."""
    if not v1_only:
        return tuple(sorted(CURATED_MODELS.keys()))
    return tuple(sorted(slug for slug, ref in CURATED_MODELS.items() if ref.v1_ready))


def register_curated(slug: str, ref: ModelRef, *, overwrite: bool = False) -> None:
    """Add a custom curated entry.

    Raises ``ValueError`` if ``slug`` already exists and ``overwrite`` is
    False — per AGENTS.md, no silent override.
    """
    if slug in CURATED_MODELS and not overwrite:
        raise ValueError(
            f"Curated slug '{slug}' already exists. "
            f"Pass overwrite=True to replace it."
        )
    CURATED_MODELS[slug] = ref
