"""Cloud dataset storage contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

StorageProvider = Literal["aliyun_oss"]


@dataclass(frozen=True)
class CloudUploadTarget:
    provider: StorageProvider
    bucket: str
    object_key: str
    cloud_uri: str
    upload_url: str
    method: str = "PUT"
    headers: dict[str, str] | None = None
    expires_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "bucket": self.bucket,
            "objectKey": self.object_key,
            "cloudUri": self.cloud_uri,
            "uploadUrl": self.upload_url,
            "method": self.method,
            "headers": dict(self.headers or {}),
            "expiresAt": self.expires_at,
        }


def utc_iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
