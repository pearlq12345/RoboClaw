"""HuggingFace Hub model source.

Covers AlphaBrain, Dexbotic, FluxVLA, OpenVLA, SmolVLA, Cosmos, V-JEPA,
and any other VLA / world-model checkpoint published on the HF Hub.

Uses ``huggingface_hub.snapshot_download`` — already a transitive
dependency via ``data/curation/validators.py``. We do not pin any
optional libs (``transformers``, ``torch``) here; this module only
*pulls files*. Loading the checkpoint is the deployment layer's job.
"""

from __future__ import annotations

from pathlib import Path

from roboclaw.embodied.policy.base import (
    FetchResult,
    ModelRef,
    default_cache_root,
)


class HuggingFaceModelSource:
    """Fetch model snapshots from the HuggingFace Hub."""

    name: str = "huggingface"

    def __init__(self, cache_root: Path | None = None) -> None:
        self.cache_root = (cache_root or default_cache_root()) / "huggingface"

    def can_fetch(self, ref: ModelRef) -> bool:
        return ref.source == self.name

    def is_cached(self, ref: ModelRef) -> bool:
        local = self._cache_path(ref)
        marker = self._complete_marker(local)
        return marker.is_file() and any(
            child.name != marker.name for child in local.iterdir()
        )

    def fetch(self, ref: ModelRef, *, force: bool = False) -> FetchResult:
        if not self.can_fetch(ref):
            raise ValueError(
                f"HuggingFaceModelSource cannot fetch ref with source={ref.source!r}"
            )

        local = self._cache_path(ref)

        if not force and self.is_cached(ref):
            files = _list_relative(local)
            return FetchResult(
                ref=ref,
                local_path=local,
                files=files,
                bytes_downloaded=0,
                cached_hit=True,
            )

        local.mkdir(parents=True, exist_ok=True)
        downloaded_path = _snapshot_download(
            repo_id=ref.repo_id,
            revision=ref.revision or "main",
            local_dir=local,
        )
        local = Path(downloaded_path)
        self._complete_marker(local).write_text("ok\n", encoding="utf-8")
        files = _list_relative(local)
        bytes_total = sum((local / f).stat().st_size for f in files if (local / f).is_file())
        return FetchResult(
            ref=ref,
            local_path=local,
            files=files,
            bytes_downloaded=bytes_total,
            cached_hit=False,
        )

    def list_cached(self) -> list[ModelRef]:
        if not self.cache_root.is_dir():
            return []
        out: list[ModelRef] = []
        for org_dir in self.cache_root.iterdir():
            if not org_dir.is_dir():
                continue
            for repo_dir in org_dir.iterdir():
                if not repo_dir.is_dir() or not self._complete_marker(repo_dir).is_file():
                    continue
                out.append(
                    ModelRef(
                        source=self.name,
                        repo_id=f"{org_dir.name}/{repo_dir.name}",
                        revision="main",
                    )
                )
        return out

    # ----------------------------------------------------------------- helpers

    def _cache_path(self, ref: ModelRef) -> Path:
        if "/" in ref.repo_id:
            org, repo = ref.repo_id.split("/", 1)
        else:
            org, repo = "_no_org", ref.repo_id
        return self.cache_root / org / repo

    def _complete_marker(self, root: Path) -> Path:
        return root / ".roboclaw_complete"


# ---------------------------------------------------------------------------
# Indirection: lets tests inject a fake snapshot_download
# ---------------------------------------------------------------------------


def _snapshot_download(
    repo_id: str,
    revision: str,
    local_dir: Path,
) -> str:
    """Thin wrapper around ``huggingface_hub.snapshot_download``.

    Kept as a module-level function so tests can monkey-patch it without
    importing the real library, and so callers see a single seam if HF
    Hub's API changes.
    """
    from huggingface_hub import snapshot_download

    return snapshot_download(
        repo_id=repo_id,
        revision=revision,
        local_dir=str(local_dir),
        local_dir_use_symlinks=False,
    )


def _list_relative(root: Path) -> tuple[str, ...]:
    if not root.is_dir():
        return ()
    marker_name = ".roboclaw_complete"
    return tuple(
        sorted(
            str(p.relative_to(root))
            for p in root.rglob("*")
            if p.is_file() and p.name != marker_name
        )
    )
