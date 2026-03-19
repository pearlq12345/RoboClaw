# RoboClaw Agent Instructions

Use this file as the default agent-facing development guide for the RoboClaw repository.

## Scope

- Follow strict framework boundaries.
- Implement code locally in the main RoboClaw repo.
- Validate embodied behavior on the remote robot host.
- Treat ROS2 as the only framework path for embodied execution work.

## Core Rules

- Keep reusable framework logic in `roboclaw/embodied/`.
- Keep setup-specific assets in `~/.roboclaw/workspace/embodied/`.
- Do not mix setup-specific paths, namespaces, devices, or lab assumptions into framework code.
- Do not hard-code a specific robot, platform, or device path into onboarding, runtime, procedures, generic adapters, or agent routing.
- Keep embodiment-specific logic inside manifests, profiles, bridge implementations, or tests.
- Resolve embodiment-specific behavior through registries, manifests, contracts, or profile metadata.
- Keep production framework code, logs, and default user-facing copy in English.
- Preserve the architecture chain: `Agent -> Workspace -> Catalog -> Runtime Session -> Procedure -> Adapter/Bridge -> ROS2 -> Embodiment`.

## Development Workflow

1. Read the relevant embodied code and current validation assets before changing structure.
2. Add or update tests for each behavior change.
3. Review unstaged, staged, and untracked changes for:
   - duplicate logic
   - framework/setup boundary leaks
   - robot-specific hard-coding in generic layers
   - non-English text in production framework paths
   - architecture drift away from the embodied execution chain

## Remote Validation

Before each fresh remote validation run:

1. Sync the current local tree to the remote canonical repo.
2. Run the remote validation reset helper when available.
3. Discover the remote proxy port on the host and export `https_proxy`, `http_proxy`, and `all_proxy` before network-dependent commands.
4. Activate the correct remote RoboClaw validation environment.

## Docker Validation

For embodied ROS2 work, Docker validation is the default developer validation path.

- Require a clean Git worktree before building images.
- Use `scripts/docker/matrix.sh build <instance>` as the default build entrypoint.
- The default validation matrix is `ubuntu2204-ros2,ubuntu2404-ros2`.
- Docker image tags must include the instance name, profile, and current short commit hash.
- Docker instance state lives under `~/.roboclaw-docker/instances/<instance>--<profile>/`.
- Use `scripts/docker/matrix.sh start-dev <instance>` for long-lived containers across the matrix.
- Use `scripts/docker/matrix.sh run-task <instance> -- <roboclaw command...>` to run the same check across the matrix.
- Keep the host `~/.roboclaw` state isolated. Only seed `config.json` on first bootstrap.
- Treat single-profile helpers such as `build-image.sh`, `start-dev.sh`, and `run-task.sh` as focused debugging tools, not the default validation path.

## Proxy and Runtime Checks

- Distinguish shell proxy setup from Docker build/runtime proxy setup.
- Confirm Docker builds receive proxy settings. A working host shell proxy alone is not enough.
- Prefer host networking for Docker build and runtime when the remote host exposes VPN or proxy services on `127.0.0.1`.
- Before judging framework behavior, confirm:
  - serial devices are passed through to the container
  - calibration data is available in the container

## Acceptance

- Do not stop at unit tests when the change affects real embodied behavior.
- Confirm the observed hardware state, not just the command return value.
