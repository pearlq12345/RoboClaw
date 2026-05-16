"""Aliyun OSS helpers for cloud dataset upload."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import quote, urlencode

from roboclaw.cloud.storage import CloudUploadTarget, utc_iso


@dataclass(frozen=True)
class AliyunOSSSettings:
    bucket: str
    endpoint: str
    access_key_id: str = ""
    access_key_secret: str = ""
    prefix: str = "datasets"
    expires_seconds: int = 3600

    @classmethod
    def from_env(cls) -> "AliyunOSSSettings":
        return cls(
            bucket=os.environ.get("ALIYUN_OSS_BUCKET", "").strip(),
            endpoint=os.environ.get("ALIYUN_OSS_ENDPOINT", "").strip(),
            access_key_id=os.environ.get("ALIYUN_OSS_ACCESS_KEY_ID", "").strip(),
            access_key_secret=os.environ.get("ALIYUN_OSS_ACCESS_KEY_SECRET", "").strip(),
            prefix=os.environ.get("ALIYUN_OSS_DATASET_PREFIX", "datasets").strip() or "datasets",
            expires_seconds=_env_int("ALIYUN_OSS_UPLOAD_EXPIRES_SECONDS", 3600),
        )

    @property
    def configured(self) -> bool:
        return bool(self.bucket and self.endpoint)


class AliyunOSSClient:
    """Small OSS signer for browser/direct dataset uploads."""

    def __init__(self, settings: AliyunOSSSettings | None = None, *, now: Callable[[], float] | None = None) -> None:
        self.settings = settings or AliyunOSSSettings.from_env()
        self._now = now or time.time

    def create_upload_target(
        self,
        *,
        dataset_id: str,
        object_name: str = "dataset.tar.gz",
        content_type: str = "application/gzip",
    ) -> CloudUploadTarget:
        if not self.settings.configured:
            raise ValueError("ALIYUN_OSS_BUCKET and ALIYUN_OSS_ENDPOINT must be configured")
        expires = int(self._now()) + self.settings.expires_seconds
        object_key = _join_key(self.settings.prefix, _safe_key_part(dataset_id), _safe_key_part(object_name))
        cloud_uri = f"oss://{self.settings.bucket}/{object_key}"
        upload_url = self._signed_put_url(
            object_key=object_key,
            content_type=content_type,
            expires=expires,
        )
        return CloudUploadTarget(
            provider="aliyun_oss",
            bucket=self.settings.bucket,
            object_key=object_key,
            cloud_uri=cloud_uri,
            upload_url=upload_url,
            headers={"Content-Type": content_type},
            expires_at=utc_iso(expires),
        )

    def _signed_put_url(self, *, object_key: str, content_type: str, expires: int) -> str:
        base_url = _oss_object_url(self.settings.bucket, self.settings.endpoint, object_key)
        if not self.settings.access_key_id or not self.settings.access_key_secret:
            query = urlencode({"Expires": str(expires)})
            return f"{base_url}?{query}"
        resource = f"/{self.settings.bucket}/{object_key}"
        string_to_sign = f"PUT\n\n{content_type}\n{expires}\n{resource}"
        digest = hmac.new(
            self.settings.access_key_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        signature = base64.b64encode(digest).decode("ascii")
        query = urlencode(
            {
                "OSSAccessKeyId": self.settings.access_key_id,
                "Expires": str(expires),
                "Signature": signature,
            }
        )
        return f"{base_url}?{query}"


def build_dataset_manifest(
    *,
    dataset_id: str,
    robot_type: str = "",
    modalities: dict[str, Any] | None = None,
    storage: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "dataset_id": dataset_id,
        "robot_type": robot_type,
        "modalities": dict(modalities or {}),
        "storage": dict(storage or {}),
    }


def _oss_object_url(bucket: str, endpoint: str, object_key: str) -> str:
    normalized_endpoint = endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
    scheme = "https"
    return f"{scheme}://{bucket}.{normalized_endpoint}/{quote(object_key)}"


def _join_key(*parts: str) -> str:
    return "/".join(part.strip("/") for part in parts if part.strip("/"))


def _safe_key_part(value: str) -> str:
    return value.strip().strip("/") or "dataset"


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)
