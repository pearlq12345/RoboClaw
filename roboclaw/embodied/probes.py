"""Embodied onboarding probe contracts and registry."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

ToolRunner = Callable[[str, dict[str, Any], Callable[..., Awaitable[None]] | None], Awaitable[str]]


@dataclass(frozen=True)
class ProbeResult:
    """Structured probe result returned to onboarding."""

    ok: bool
    detail: str = ""


class ProbeProvider(Protocol):
    """Robot-specific onboarding probe provider."""

    id: str

    async def probe_serial_device(
        self,
        serial_by_id: str,
        *,
        run_tool: ToolRunner,
        on_progress: Callable[..., Awaitable[None]] | None = None,
    ) -> ProbeResult:
        """Probe one stable serial device path."""


class ProbeProviderRegistry:
    """Registry of onboarding probe providers."""

    def __init__(self) -> None:
        self._entries: dict[str, ProbeProvider] = {}

    def register(self, provider: ProbeProvider) -> None:
        self._entries[provider.id] = provider

    def get(self, provider_id: str | None) -> ProbeProvider | None:
        if provider_id is None:
            return None
        return self._entries.get(provider_id)

    def list(self) -> tuple[ProbeProvider, ...]:
        return tuple(self._entries.values())


_PROBE_PROVIDERS = ProbeProviderRegistry()


def register_probe_provider(provider: ProbeProvider) -> None:
    """Register one onboarding probe provider."""

    _PROBE_PROVIDERS.register(provider)


def get_probe_provider(provider_id: str | None) -> ProbeProvider | None:
    """Resolve one onboarding probe provider by id."""

    return _PROBE_PROVIDERS.get(provider_id)


def list_probe_providers() -> tuple[ProbeProvider, ...]:
    """List all onboarding probe providers."""

    return _PROBE_PROVIDERS.list()


__all__ = [
    "ProbeProvider",
    "ProbeProviderRegistry",
    "ProbeResult",
    "ToolRunner",
    "get_probe_provider",
    "list_probe_providers",
    "register_probe_provider",
]
