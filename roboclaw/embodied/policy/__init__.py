"""Policy / model registry — one-line pull for any open-source VLA.

Closes the data → train → **deploy** half of the loop:

```
edge collect → curate → train (PR 4) → fetch (this package) → edge deploy
```

Three model sources ship in v1:

- :class:`HuggingFaceModelSource` — fetches checkpoints from the HF Hub.
  Covers AlphaBrain, Dexbotic, FluxVLA, OpenVLA, SmolVLA, V-JEPA, Cosmos.
- :class:`LocalModelSource` — wraps an on-disk directory tree (private
  / lab models that never leave the machine).
- (OSS / custom registries can be added by users via the
  :class:`ModelSource` Protocol — same extension pattern as exporters.)

A curated catalog (:data:`CURATED_MODELS`) maps short slugs to
``ModelRef`` instances so users can write
``policy.pull("alphabrain-neurovla")`` instead of remembering the full
HF repo id.
"""

from __future__ import annotations

from roboclaw.embodied.policy.base import (
    FetchResult,
    ModelRef,
    ModelSource,
)
from roboclaw.embodied.policy.huggingface import HuggingFaceModelSource
from roboclaw.embodied.policy.local import LocalModelSource
from roboclaw.embodied.policy.registry import (
    CURATED_MODELS,
    SOURCE_REGISTRY,
    get_curated,
    get_source,
    list_curated_slugs,
    register_curated,
    register_source,
)

__all__ = [
    "CURATED_MODELS",
    "FetchResult",
    "HuggingFaceModelSource",
    "LocalModelSource",
    "ModelRef",
    "ModelSource",
    "SOURCE_REGISTRY",
    "get_curated",
    "get_source",
    "list_curated_slugs",
    "register_curated",
    "register_source",
]
