"""Base abstractions for model sources.

A *model source* knows how to materialize a ``ModelRef`` (a logical
pointer like ``("huggingface", "AlphaBrainGroup/NeuroVLA", "main")``)
into a local directory of files that downstream inference code can
load.

The Protocol stays narrow on purpose:

- ``can_fetch(ref)``: cheap match check — does this source own this ref?
- ``fetch(ref, *, force)``: do the work, return a :class:`FetchResult`.
- ``is_cached(ref)``: True if the local cache already has it.
- ``list_cached()``: enumerate what's locally available.

Concrete sources (HuggingFace, local, custom) just implement these
four methods.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ModelRef:
    """Logical pointer to a model checkpoint.

    Attributes:
        source: Source name registered in :data:`SOURCE_REGISTRY`.
            Examples: ``"huggingface"``, ``"local"``.
        repo_id: Source-specific identifier. For ``huggingface`` this is
            the ``org/repo`` string; for ``local`` it is a directory name
            within the configured local root.
        revision: Source-specific revision pointer. Defaults to
            ``"main"``. For HuggingFace this can be a branch, tag, or
            commit SHA. For local sources, ignored.
        framework: Optional hint about which training stack produced
            the checkpoint (``alphabrain`` / ``dexbotic`` / ``fluxvla``
            / ``lerobot`` / ``openvla`` / etc.). Surfaces in logs and
            informs deployment-time loaders.
        notes: Free-form description (curated catalog entries fill this in).
        access: Whether the upstream repo is expected to be publicly
            pullable from a default deployment, or usually requires
            Hugging Face authentication / gating acceptance.
        track: Whether this entry is a general base model or a
            dataset-specific finetune for benchmarks like LIBERO /
            VLABench.
        size_label: Human-friendly storage estimate for the full pull.
        v1_ready: Whether this entry is suitable for the current public
            v1 UI list (publicly reachable, directly pullable, and a
            reasonable size for a first-run deployment experience).
    """

    source: str
    repo_id: str
    revision: str = "main"
    framework: str = ""
    notes: str = ""
    access: str = "public"
    track: str = "general"
    size_label: str = ""
    v1_ready: bool = False


@dataclass(frozen=True)
class FetchResult:
    """Outcome of a successful fetch.

    Attributes:
        ref: The :class:`ModelRef` that was fetched.
        local_path: Directory where the model files now live.
        files: Relative paths of files in the local cache.
        bytes_downloaded: Network bytes pulled (0 if served from cache).
        cached_hit: True if the result was served entirely from cache.
    """

    ref: ModelRef
    local_path: Path
    files: tuple[str, ...] = ()
    bytes_downloaded: int = 0
    cached_hit: bool = False


@runtime_checkable
class ModelSource(Protocol):
    """Contract for a source that materializes :class:`ModelRef` to disk."""

    name: str

    def can_fetch(self, ref: ModelRef) -> bool:
        """True if this source claims responsibility for ``ref``."""
        ...

    def is_cached(self, ref: ModelRef) -> bool:
        """True if the local cache already contains a usable copy of ``ref``."""
        ...

    def fetch(self, ref: ModelRef, *, force: bool = False) -> FetchResult:
        """Materialize ``ref`` to disk.

        Args:
            ref: Logical pointer to fetch.
            force: If True, re-fetch even if the cache hit is valid.
        """
        ...

    def list_cached(self) -> list[ModelRef]:
        """Return refs currently materialized in this source's cache."""
        ...


# ---------------------------------------------------------------------------
# Cache root resolution
# ---------------------------------------------------------------------------


def default_cache_root() -> Path:
    """Resolve the default RoboClaw model cache root.

    Honors ``ROBOCLAW_MODEL_CACHE`` env var if set; otherwise falls back
    to ``~/.roboclaw/cache/models``.
    """
    import os

    env = os.environ.get("ROBOCLAW_MODEL_CACHE")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".roboclaw" / "cache" / "models"
