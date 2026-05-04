"""Local-filesystem model source.

For private models that never leave the lab machine: a directory tree
under a configured root holds one subdirectory per ``repo_id``. Useful
for:

- in-house checkpoints that haven't been (or won't be) published.
- Federated / air-gapped deployments where HF Hub is unreachable.
- Models pulled by other tools (e.g. ``aliyun-pai`` artifacts) and
  staged on disk before RoboClaw consumes them.

There is no network I/O — ``fetch`` just validates the directory exists
and returns a :class:`FetchResult` pointing at it.
"""

from __future__ import annotations

from pathlib import Path

from roboclaw.embodied.policy.base import FetchResult, ModelRef


class LocalModelSource:
    """Resolve a :class:`ModelRef` to a directory under a configured root."""

    name: str = "local"

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def can_fetch(self, ref: ModelRef) -> bool:
        return ref.source == self.name

    def is_cached(self, ref: ModelRef) -> bool:
        return self._path(ref).is_dir() and any(self._path(ref).iterdir())

    def fetch(self, ref: ModelRef, *, force: bool = False) -> FetchResult:
        if not self.can_fetch(ref):
            raise ValueError(
                f"LocalModelSource cannot fetch ref with source={ref.source!r}"
            )

        path = self._path(ref)
        if not path.is_dir():
            raise FileNotFoundError(
                f"Local model not found: {path}. "
                f"Place files at this path before calling fetch()."
            )
        files = tuple(
            sorted(str(p.relative_to(path)) for p in path.rglob("*") if p.is_file())
        )
        if not files:
            raise FileNotFoundError(
                f"Local model directory is empty: {path}"
            )
        return FetchResult(
            ref=ref,
            local_path=path,
            files=files,
            bytes_downloaded=0,
            cached_hit=True,  # local source is always a "hit" by definition
        )

    def list_cached(self) -> list[ModelRef]:
        if not self.root.is_dir():
            return []
        out: list[ModelRef] = []
        for entry in self.root.iterdir():
            if entry.is_dir() and any(entry.iterdir()):
                out.append(ModelRef(source=self.name, repo_id=entry.name))
        return out

    # ----------------------------------------------------------------- helpers

    def _path(self, ref: ModelRef) -> Path:
        # Repo ids may contain "/" (org/repo) — preserve that as a sub-tree.
        return self.root / ref.repo_id
