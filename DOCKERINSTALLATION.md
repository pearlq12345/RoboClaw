# Docker Installation

This guide is the step-by-step Docker installation path for RoboClaw.

If you already have the Docker setup working and want the day-to-day development
and validation flow, use [DOCKER_WORKFLOW.md](./DOCKER_WORKFLOW.md).

If you do not want Docker, use [INSTALLATION.md](./INSTALLATION.md).

## 1. Prerequisites

Start from a clean clone:

```bash
git clone https://github.com/MINT-SJTU/RoboClaw.git
cd RoboClaw
```

## 2. Build or Start a Dev Container

The default Docker install path is the mutable dev container:

```bash
./scripts/docker/start-dev.sh --profile ubuntu2404-ros2 devbox
```

If the image does not exist yet, this command builds it first and then starts
the container.

## 3. Enter the Container

Open a shell inside the running container:

```bash
./scripts/docker/exec-dev.sh --profile ubuntu2404-ros2 devbox
```

The RoboClaw source tree is mounted at `/roboclaw-source`, and the container is
configured so host source edits are visible immediately.

Docker instance state lives under:

```text
~/.roboclaw-docker/instances/<instance>--<profile>/
```

## 4. Verify RoboClaw Inside Docker

Inside the container, confirm the CLI is available:

```bash
roboclaw --help
```

You should see commands such as `onboard`, `status`, `agent`, and `provider`.
