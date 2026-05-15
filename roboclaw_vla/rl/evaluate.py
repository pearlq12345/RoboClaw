"""Minimal artifact evaluator for RoboClaw VLA training outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint_path", default="")
    parser.add_argument("--artifact_path", required=True)
    parser.add_argument("--suite", default="")
    args = parser.parse_args()

    artifact_path = Path(args.artifact_path)
    artifact_path.mkdir(parents=True, exist_ok=True)
    (artifact_path / "eval_info.json").write_text(
        json.dumps(
            {
                "checkpointPath": args.checkpoint_path,
                "suite": args.suite,
                "success_rate": None,
                "implemented": False,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
