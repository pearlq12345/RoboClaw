"""Tests for the model library HTTP routes (/api/models/*)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from roboclaw.embodied.policy import huggingface as hf_module
from roboclaw.http.routes.models import register_model_routes


@pytest.fixture(autouse=True)
def isolated_cache_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Force the model cache root into tmp_path so tests never write to ~/.roboclaw."""
    monkeypatch.setenv("ROBOCLAW_MODEL_CACHE", str(tmp_path / "cache"))
    yield


@pytest.fixture()
def app() -> FastAPI:
    application = FastAPI()
    register_model_routes(application)
    return application


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# /api/models/curated
# ---------------------------------------------------------------------------


class TestCurated:
    def test_returns_all_curated_entries(self, client: TestClient) -> None:
        resp = client.get("/api/models/curated")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "cache_root" in data
        assert "count" in data
        assert "total_curated" in data
        assert "hidden_count" in data
        assert data["count"] == len(data["items"])
        assert data["count"] >= 1
        assert data["total_curated"] >= data["count"]
        assert data["hidden_count"] == data["total_curated"] - data["count"]

    def test_each_item_has_required_fields(self, client: TestClient) -> None:
        items = client.get("/api/models/curated").json()["items"]
        required = {
            "slug", "source", "repo_id", "revision", "framework", "notes",
            "access", "size_label", "v1_ready", "cached",
        }
        for item in items:
            assert required.issubset(item.keys()), f"Missing fields in {item}"

    def test_only_returns_v1_ready_public_entries(self, client: TestClient) -> None:
        items = client.get("/api/models/curated").json()["items"]
        assert items
        assert all(item["v1_ready"] is True for item in items)
        assert all(item["access"] == "public" for item in items)
        assert {item["slug"] for item in items} == {
            "openvla-7b",
            "openvla-libero-ft",
            "pi0",
            "smolvla",
            "smolvla-libero",
            "smolvla-vlabench",
            "octo-base",
            "octo-small-1.5",
        }

    def test_cached_flag_initially_false_for_empty_cache(self, client: TestClient) -> None:
        items = client.get("/api/models/curated").json()["items"]
        assert all(item["cached"] is False for item in items)


# ---------------------------------------------------------------------------
# /api/models/pull
# ---------------------------------------------------------------------------


class TestPull:
    def test_unknown_slug_returns_404(self, client: TestClient) -> None:
        resp = client.post("/api/models/pull", json={"slug": "no-such-model"})
        assert resp.status_code == 404
        assert "Unknown" in resp.json()["detail"]

    def test_missing_slug_field_rejected(self, client: TestClient) -> None:
        resp = client.post("/api/models/pull", json={})
        assert resp.status_code == 422  # FastAPI validation error

    def test_successful_pull_returns_local_path(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Mock snapshot_download so the pull succeeds without network I/O."""

        def fake_snapshot_download(repo_id: str, revision: str, local_dir: Path) -> str:
            local = Path(local_dir)
            local.mkdir(parents=True, exist_ok=True)
            (local / "config.json").write_text('{"k": 1}', encoding="utf-8")
            return str(local)

        monkeypatch.setattr(hf_module, "_snapshot_download", fake_snapshot_download)

        resp = client.post("/api/models/pull", json={"slug": "smolvla"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "smolvla"
        assert data["cached_hit"] is False
        assert "config.json" in data["files"]
        assert data["bytes_downloaded"] > 0

    def test_pull_serves_from_cache_when_present(
        self, client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cache_root = tmp_path / "cache"
        populated = cache_root / "huggingface" / "lerobot" / "smolvla_base"
        populated.mkdir(parents=True)
        (populated / "weights.bin").write_bytes(b"x" * 16)
        (populated / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")

        call_count = {"n": 0}

        def fake_snapshot_download(repo_id: str, revision: str, local_dir: Path) -> str:
            call_count["n"] += 1
            return str(local_dir)

        monkeypatch.setattr(hf_module, "_snapshot_download", fake_snapshot_download)

        resp = client.post("/api/models/pull", json={"slug": "smolvla"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["cached_hit"] is True
        assert call_count["n"] == 0

    def test_pull_returns_clear_error_for_gated_or_private_repo(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo_error = type("RepositoryNotFoundError", (RuntimeError,), {})

        def fake_fetch(self, ref, *, force=False):
            raise repo_error("401 Unauthorized")

        monkeypatch.setattr(hf_module.HuggingFaceModelSource, "fetch", fake_fetch)

        resp = client.post("/api/models/pull", json={"slug": "smolvla"})
        assert resp.status_code == 403
        assert "authentication" in resp.json()["detail"] or "public" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# /api/models/cached
# ---------------------------------------------------------------------------


class TestCached:
    def test_empty_cache_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/models/cached")
        assert resp.status_code == 200
        assert resp.json()["count"] == 0
        assert resp.json()["items"] == []

    def test_populated_cache_lists_entries(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        cache_root = tmp_path / "cache" / "huggingface"
        (cache_root / "openvla" / "openvla-7b").mkdir(parents=True)
        (cache_root / "openvla" / "openvla-7b" / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")
        (cache_root / "lerobot" / "smolvla_base").mkdir(parents=True)
        (cache_root / "lerobot" / "smolvla_base" / ".roboclaw_complete").write_text("ok\n", encoding="utf-8")

        data = client.get("/api/models/cached").json()
        repo_ids = {item["repo_id"] for item in data["items"]}
        assert "openvla/openvla-7b" in repo_ids
        assert "lerobot/smolvla_base" in repo_ids


# ---------------------------------------------------------------------------
# /api/models/local
# ---------------------------------------------------------------------------


class TestLocal:
    def test_missing_local_dir_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/models/local")
        assert resp.status_code == 200
        data = resp.json()
        assert data["count"] == 0
        assert data["items"] == []

    def test_populated_local_dir_lists_entries(
        self, client: TestClient, tmp_path: Path,
    ) -> None:
        local_root = tmp_path / "cache" / "local"
        (local_root / "my_lab_model").mkdir(parents=True)
        (local_root / "my_lab_model" / "weights.bin").write_bytes(b"x" * 16)

        data = client.get("/api/models/local").json()
        repo_ids = {item["repo_id"] for item in data["items"]}
        assert "my_lab_model" in repo_ids
