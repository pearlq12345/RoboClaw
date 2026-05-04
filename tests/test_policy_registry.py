"""Tests for the policy / model registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from roboclaw.embodied.policy import (
    CURATED_MODELS,
    SOURCE_REGISTRY,
    HuggingFaceModelSource,
    LocalModelSource,
    ModelRef,
    ModelSource,
    get_curated,
    get_source,
    list_curated_slugs,
    register_curated,
    register_source,
)
from roboclaw.embodied.policy import huggingface as hf_module

# ---------------------------------------------------------------------------
# ModelRef
# ---------------------------------------------------------------------------


def test_model_ref_is_frozen() -> None:
    ref = ModelRef(source="huggingface", repo_id="x/y")
    with pytest.raises(Exception):
        ref.repo_id = "z/w"  # type: ignore[misc]


def test_model_ref_defaults() -> None:
    ref = ModelRef(source="local", repo_id="my_model")
    assert ref.revision == "main"
    assert ref.framework == ""
    assert ref.notes == ""
    assert ref.access == "public"
    assert ref.size_label == ""
    assert ref.v1_ready is False


# ---------------------------------------------------------------------------
# Source registry
# ---------------------------------------------------------------------------


def test_source_registry_includes_huggingface_and_local() -> None:
    assert "huggingface" in SOURCE_REGISTRY
    assert "local" in SOURCE_REGISTRY


def test_get_source_returns_class() -> None:
    assert get_source("huggingface") is HuggingFaceModelSource
    assert get_source("local") is LocalModelSource


def test_get_source_unknown_raises() -> None:
    with pytest.raises(ValueError, match="Unknown model source"):
        get_source("not_a_real_source")


def test_register_source_rejects_duplicate() -> None:
    with pytest.raises(ValueError, match="already registered"):
        register_source("huggingface", HuggingFaceModelSource)


# ---------------------------------------------------------------------------
# Curated catalog
# ---------------------------------------------------------------------------


def test_curated_catalog_includes_public_frontier_frameworks() -> None:
    slugs = list_curated_slugs()
    # FluxVLA
    assert any(s.startswith("fluxvla") for s in slugs)
    # OpenVLA
    assert any(s.startswith("openvla") for s in slugs)
    # LeRobot / SmolVLA / Pi0
    assert "pi0" in slugs
    assert "smolvla" in slugs
    # Octo
    assert any(s.startswith("octo") for s in slugs)


def test_curated_catalog_includes_open_baselines() -> None:
    slugs = list_curated_slugs()
    assert "openvla-7b" in slugs
    assert "v-jepa-2-vit-l" in slugs
    assert "smolvla" in slugs


def test_v1_curated_slugs_only_return_ready_subset() -> None:
    assert list_curated_slugs(v1_only=True) == (
        "octo-base",
        "octo-small-1.5",
        "openvla-7b",
        "openvla-libero-ft",
        "pi0",
        "smolvla",
        "smolvla-libero",
        "smolvla-vlabench",
    )


def test_get_curated_returns_model_ref() -> None:
    ref = get_curated("pi0")
    assert ref.source == "huggingface"
    assert ref.repo_id == "lerobot/pi0"
    assert ref.framework == "lerobot"


def test_get_curated_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unknown curated model"):
        get_curated("psychic_xyz")


def test_register_curated_then_resolve() -> None:
    custom = ModelRef(source="local", repo_id="my_lab_model")
    register_curated("test_custom_lab_model", custom)
    assert get_curated("test_custom_lab_model") == custom


def test_register_curated_rejects_duplicate() -> None:
    custom = ModelRef(source="local", repo_id="dup")
    register_curated("test_dup_slug", custom)
    with pytest.raises(ValueError, match="already exists"):
        register_curated("test_dup_slug", custom)


def test_register_curated_overwrite_works() -> None:
    a = ModelRef(source="local", repo_id="a")
    b = ModelRef(source="local", repo_id="b")
    register_curated("test_overwrite_slug", a)
    register_curated("test_overwrite_slug", b, overwrite=True)
    assert get_curated("test_overwrite_slug") == b


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_huggingface_source_satisfies_protocol() -> None:
    src = HuggingFaceModelSource(cache_root=Path("/tmp/never_used"))
    assert isinstance(src, ModelSource)


def test_local_source_satisfies_protocol(tmp_path: Path) -> None:
    src = LocalModelSource(root=tmp_path)
    assert isinstance(src, ModelSource)


# ---------------------------------------------------------------------------
# LocalModelSource
# ---------------------------------------------------------------------------


def test_local_fetch_returns_existing_directory(tmp_path: Path) -> None:
    root = tmp_path / "models"
    (root / "my_model").mkdir(parents=True)
    (root / "my_model" / "weights.bin").write_bytes(b"x" * 100)

    src = LocalModelSource(root=root)
    ref = ModelRef(source="local", repo_id="my_model")
    result = src.fetch(ref)
    assert result.local_path == root / "my_model"
    assert "weights.bin" in result.files
    assert result.cached_hit is True


def test_local_fetch_missing_raises(tmp_path: Path) -> None:
    src = LocalModelSource(root=tmp_path)
    with pytest.raises(FileNotFoundError):
        src.fetch(ModelRef(source="local", repo_id="not_here"))


def test_local_fetch_empty_dir_raises(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()
    src = LocalModelSource(root=tmp_path)
    with pytest.raises(FileNotFoundError, match="empty"):
        src.fetch(ModelRef(source="local", repo_id="empty"))


def test_local_fetch_rejects_wrong_source(tmp_path: Path) -> None:
    src = LocalModelSource(root=tmp_path)
    with pytest.raises(ValueError, match="cannot fetch"):
        src.fetch(ModelRef(source="huggingface", repo_id="x/y"))


def test_local_can_fetch_only_local_refs(tmp_path: Path) -> None:
    src = LocalModelSource(root=tmp_path)
    assert src.can_fetch(ModelRef(source="local", repo_id="x"))
    assert not src.can_fetch(ModelRef(source="huggingface", repo_id="x/y"))


def test_local_list_cached_returns_only_non_empty_dirs(tmp_path: Path) -> None:
    (tmp_path / "ready").mkdir()
    (tmp_path / "ready" / "f.bin").write_bytes(b"x")
    (tmp_path / "empty").mkdir()
    src = LocalModelSource(root=tmp_path)
    cached = src.list_cached()
    cached_ids = {ref.repo_id for ref in cached}
    assert "ready" in cached_ids
    assert "empty" not in cached_ids


# ---------------------------------------------------------------------------
# HuggingFaceModelSource (with mocked snapshot_download)
# ---------------------------------------------------------------------------


def test_hf_can_fetch_only_huggingface_refs(tmp_path: Path) -> None:
    src = HuggingFaceModelSource(cache_root=tmp_path)
    assert src.can_fetch(ModelRef(source="huggingface", repo_id="org/model"))
    assert not src.can_fetch(ModelRef(source="local", repo_id="x"))


def test_hf_fetch_rejects_wrong_source(tmp_path: Path) -> None:
    src = HuggingFaceModelSource(cache_root=tmp_path)
    with pytest.raises(ValueError, match="cannot fetch"):
        src.fetch(ModelRef(source="local", repo_id="x"))


def test_hf_fetch_calls_snapshot_download_and_records_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mock snapshot_download to write a fake snapshot, verify FetchResult."""

    def fake_snapshot_download(repo_id: str, revision: str, local_dir: Path) -> str:
        local = Path(local_dir)
        local.mkdir(parents=True, exist_ok=True)
        (local / "config.json").write_text('{"k": 1}', encoding="utf-8")
        (local / "model.safetensors").write_bytes(b"x" * 1024)
        return str(local)

    monkeypatch.setattr(hf_module, "_snapshot_download", fake_snapshot_download)

    src = HuggingFaceModelSource(cache_root=tmp_path)
    ref = ModelRef(source="huggingface", repo_id="fake_org/fake_model")
    result = src.fetch(ref)

    assert result.cached_hit is False
    assert result.bytes_downloaded > 0
    assert "config.json" in result.files
    assert "model.safetensors" in result.files
    assert (result.local_path / ".roboclaw_complete").is_file()


def test_hf_fetch_serves_from_cache_when_present(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_root = tmp_path
    src = HuggingFaceModelSource(cache_root=cache_root)

    # Pre-populate the cache directory the way snapshot_download would.
    populated = cache_root / "huggingface" / "fake_org" / "fake_model"
    populated.mkdir(parents=True)
    (populated / "weights.bin").write_bytes(b"x" * 16)
    (populated / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")

    call_count = {"n": 0}

    def fake_snapshot_download(repo_id: str, revision: str, local_dir: Path) -> str:
        call_count["n"] += 1
        return str(local_dir)

    monkeypatch.setattr(hf_module, "_snapshot_download", fake_snapshot_download)

    ref = ModelRef(source="huggingface", repo_id="fake_org/fake_model")
    result = src.fetch(ref)
    assert result.cached_hit is True
    assert result.bytes_downloaded == 0
    assert call_count["n"] == 0


def test_hf_fetch_force_re_downloads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache_root = tmp_path
    src = HuggingFaceModelSource(cache_root=cache_root)

    populated = cache_root / "huggingface" / "fake_org" / "fake_model"
    populated.mkdir(parents=True)
    (populated / "weights.bin").write_bytes(b"x" * 16)
    (populated / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")

    call_count = {"n": 0}

    def fake_snapshot_download(repo_id: str, revision: str, local_dir: Path) -> str:
        call_count["n"] += 1
        return str(local_dir)

    monkeypatch.setattr(hf_module, "_snapshot_download", fake_snapshot_download)

    ref = ModelRef(source="huggingface", repo_id="fake_org/fake_model")
    result = src.fetch(ref, force=True)
    assert result.cached_hit is False
    assert call_count["n"] == 1


def test_hf_list_cached_enumerates_org_repo_pairs(tmp_path: Path) -> None:
    cache_root = tmp_path
    (cache_root / "huggingface" / "AlphaBrainGroup" / "NeuroVLA").mkdir(parents=True)
    (cache_root / "huggingface" / "Dexmal" / "CogACT").mkdir(parents=True)
    (cache_root / "huggingface" / "AlphaBrainGroup" / "NeuroVLA" / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")
    (cache_root / "huggingface" / "Dexmal" / "CogACT" / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")

    src = HuggingFaceModelSource(cache_root=cache_root)
    cached = src.list_cached()
    repo_ids = {ref.repo_id for ref in cached}
    assert "AlphaBrainGroup/NeuroVLA" in repo_ids
    assert "Dexmal/CogACT" in repo_ids


def test_hf_partial_download_without_marker_is_not_cached(tmp_path: Path) -> None:
    partial = tmp_path / "huggingface" / "org" / "repo"
    partial.mkdir(parents=True)
    (partial / "weights.bin").write_bytes(b"x")

    src = HuggingFaceModelSource(cache_root=tmp_path)
    ref = ModelRef(source="huggingface", repo_id="org/repo")

    assert src.is_cached(ref) is False
    assert src.list_cached() == []


# ---------------------------------------------------------------------------
# Cache root resolution
# ---------------------------------------------------------------------------


def test_default_cache_root_honors_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    from roboclaw.embodied.policy.base import default_cache_root

    monkeypatch.setenv("ROBOCLAW_MODEL_CACHE", "/tmp/custom_root")
    assert default_cache_root() == Path("/tmp/custom_root")


def test_default_cache_root_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    from roboclaw.embodied.policy.base import default_cache_root

    monkeypatch.delenv("ROBOCLAW_MODEL_CACHE", raising=False)
    root = default_cache_root()
    assert root.parts[-3:] == (".roboclaw", "cache", "models")


# ---------------------------------------------------------------------------
# Sanity: catalog refs are well-formed
# ---------------------------------------------------------------------------


def test_every_curated_ref_has_known_source() -> None:
    for slug, ref in CURATED_MODELS.items():
        assert ref.source in SOURCE_REGISTRY, (
            f"Curated entry '{slug}' uses unknown source '{ref.source}'"
        )


def test_every_curated_ref_has_repo_id() -> None:
    for slug, ref in CURATED_MODELS.items():
        assert ref.repo_id, f"Curated entry '{slug}' has empty repo_id"
