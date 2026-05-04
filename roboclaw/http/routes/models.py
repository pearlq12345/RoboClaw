"""Model library routes — curated SOTA model registry.

Distinct from ``/api/policies`` (which lists locally-trained checkpoints
under ``workspace/embodied/policies``). These routes expose the
:mod:`roboclaw.embodied.policy` registry: short slugs to upstream VLA /
world-model repos hosted on HuggingFace (AlphaBrain, Dexbotic, FluxVLA,
OpenVLA, V-JEPA, Cosmos, ...).

Pairs with :mod:`roboclaw.http.routes.train` (PR #95): once a remote
training job finishes, users pull the resulting checkpoint back to the
edge cache from this route, closing the data → train → deploy loop.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from roboclaw.embodied.policy import (
    CURATED_MODELS,
    HuggingFaceModelSource,
    LocalModelSource,
    ModelRef,
    get_curated,
    list_curated_slugs,
)
from roboclaw.embodied.policy.base import default_cache_root

logger = logging.getLogger(__name__)


class PullRequest(BaseModel):
    slug: str
    force: bool = False


def _serialize_ref(slug: str, ref: ModelRef, cached: bool) -> dict:
    return {
        "slug": slug,
        "source": ref.source,
        "repo_id": ref.repo_id,
        "revision": ref.revision,
        "framework": ref.framework,
        "notes": ref.notes,
        "access": ref.access,
        "track": ref.track,
        "size_label": ref.size_label,
        "v1_ready": ref.v1_ready,
        "cached": cached,
    }


def _translate_pull_error(slug: str, exc: Exception) -> tuple[int, str]:
    """Map backend/source failures to user-facing HTTP errors."""
    name = exc.__class__.__name__
    message = str(exc)
    if isinstance(exc, ImportError):
        return 503, (
            "This deployment is missing Hugging Face support. "
            "Install the optional policy dependency first."
        )
    if name in {"RepositoryNotFoundError", "GatedRepoError"}:
        return 403, (
            f"Model '{slug}' is gated, private, or not publicly reachable from "
            "this deployment. Sign in to Hugging Face or choose a public model."
        )
    if name == "RevisionNotFoundError":
        return 404, f"Model '{slug}' points to a revision that does not exist."
    if "401" in message or "403" in message:
        return 403, (
            f"Model '{slug}' requires Hugging Face authentication or is not "
            "publicly accessible from this deployment."
        )
    return 502, f"Failed to fetch model '{slug}': {message}"


def register_model_routes(app: FastAPI) -> None:
    """Register model library routes."""

    @app.get("/api/models/curated")
    async def models_curated() -> dict:
        """Return the curated model catalog with cache status per entry."""
        hf = HuggingFaceModelSource()
        items = [
            _serialize_ref(slug, get_curated(slug), hf.is_cached(get_curated(slug)))
            for slug in list_curated_slugs(v1_only=True)
        ]
        return {
            "items": items,
            "cache_root": str(default_cache_root()),
            "count": len(items),
            "total_curated": len(CURATED_MODELS),
            "hidden_count": len(CURATED_MODELS) - len(items),
        }

    @app.get("/api/models/cached")
    async def models_cached() -> dict:
        """Return refs currently materialized in the local cache."""
        hf = HuggingFaceModelSource()
        cached_refs = await asyncio.to_thread(hf.list_cached)
        items = [
            {
                "source": ref.source,
                "repo_id": ref.repo_id,
                "revision": ref.revision,
            }
            for ref in cached_refs
        ]
        return {
            "items": items,
            "cache_root": str(default_cache_root()),
            "count": len(items),
        }

    @app.post("/api/models/pull")
    async def models_pull(body: PullRequest) -> dict:
        """Pull a curated model to the local cache.

        Synchronous (blocks the response until the snapshot completes).
        For large models the caller should expect a long wait — UI shows
        a spinner; long-poll/streaming progress is a follow-up.
        """
        if body.slug not in CURATED_MODELS:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown curated model slug: '{body.slug}'",
            )
        ref = get_curated(body.slug)
        if ref.source != "huggingface":
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Model '{body.slug}' has source='{ref.source}', "
                    f"only 'huggingface' is supported via this route. "
                    f"Use LocalModelSource directly for local refs."
                ),
            )
        hf = HuggingFaceModelSource()
        try:
            result = await asyncio.to_thread(hf.fetch, ref, force=body.force)
        except Exception as exc:
            status_code, detail = _translate_pull_error(body.slug, exc)
            logger.warning("Model pull failed for %s: %s", body.slug, exc)
            raise HTTPException(status_code=status_code, detail=detail) from exc
        return {
            "slug": body.slug,
            "local_path": str(result.local_path),
            "files": list(result.files),
            "bytes_downloaded": result.bytes_downloaded,
            "cached_hit": result.cached_hit,
        }

    @app.get("/api/models/local")
    async def models_local() -> dict:
        """Return refs from the optional local model directory.

        Local model root defaults to ``<cache_root>/local`` if absent —
        this returns an empty list rather than erroring so the UI can
        show a placeholder.
        """
        local_root = default_cache_root() / "local"
        if not local_root.is_dir():
            return {"items": [], "root": str(local_root), "count": 0}
        local = LocalModelSource(root=local_root)
        cached_refs = await asyncio.to_thread(local.list_cached)
        items = [
            {
                "source": ref.source,
                "repo_id": ref.repo_id,
                "revision": ref.revision,
            }
            for ref in cached_refs
        ]
        return {"items": items, "root": str(local_root), "count": len(items)}
