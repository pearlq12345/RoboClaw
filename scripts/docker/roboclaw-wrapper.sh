#!/usr/bin/env bash
set -euo pipefail

if [ "${ROBOCLAW_ROS2_DISTRO:-none}" != "none" ] && [ -f "/opt/ros/${ROBOCLAW_ROS2_DISTRO}/setup.sh" ]; then
  # ROS setup scripts assume several tracing vars may be unset.
  set +u
  # shellcheck disable=SC1090
  source "/opt/ros/${ROBOCLAW_ROS2_DISTRO}/setup.sh"
  set -u
fi

# Run the CLI with the Python environment that owns the wheel dependencies.
# The generated console script can pick up /usr/bin/python3 as its shebang,
# which breaks extension modules like pydantic_core when the app is installed
# into the Python 3.11 environment under /usr/local.
exec /usr/local/bin/python /usr/local/bin/roboclaw-real "$@"
