"""RoboClaw VLA RLinf launcher stub.

The production launcher should build RLinf Cluster, HybridComponentPlacement,
actor, rollout, and env worker groups before calling EmbodiedRunner.run().
This stub exists so EVO_Train preflight can verify the module contract without
pretending the worker orchestration is already implemented here.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from roboclaw_vla.rl import registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-name", required=True)
    parser.add_argument("--dataset_path", default=os.environ.get("RLINF_DATASET_PATH", ""))
    parser.add_argument("--checkpoint_path", default=os.environ.get("RLINF_CHECKPOINT_PATH", ""))
    parser.add_argument("--artifact_path", default=os.environ.get("RLINF_ARTIFACT_DIR", "outputs"))
    args, unknown = parser.parse_known_args()

    registered = registry.register()
    artifact_path = Path(args.artifact_path)
    artifact_path.mkdir(parents=True, exist_ok=True)
    (artifact_path / "launcher_stub.json").write_text(
        json.dumps(
            {
                "configName": args.config_name,
                "datasetPath": args.dataset_path,
                "checkpointPath": args.checkpoint_path,
                "unknownArgs": unknown,
                "registryLoaded": registered,
                "runnerImplemented": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    raise SystemExit(
        "RoboClaw RLinf launcher stub imported successfully, but full "
        "actor/rollout/env worker orchestration is not implemented in this PR."
    )


if __name__ == "__main__":
    main()
