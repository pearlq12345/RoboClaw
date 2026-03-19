# Docker Workflow

Use this guide after Docker installation is already working and a dev container
is available. It covers the normal RoboClaw Docker development loop and the
matrix validation flow.

## Normal Development Loop

Use this loop for day-to-day work:

1. Start or re-enter the dev container.
2. Edit code on the host.
3. Run the command or test you are working on inside the dev container.
4. Repeat without rebuilding for normal source edits.
5. Run matrix validation before acceptance-sensitive changes are considered done.

For normal Python edits, keep the dev container running and rerun the command
you are testing.

## When To Rebuild

Use `build-image.sh` only when the runtime environment changes:

- Dockerfile changes
- ROS/system dependency changes
- explicit Python dependency changes
- release or acceptance validation

## Matrix Validation Workflow

Use the matrix workflow for clean acceptance validation across the supported
ROS2 profiles.

### Profiles

- `ubuntu2204-ros2`
- `ubuntu2404-ros2`

### Build the Matrix

```bash
./scripts/docker/matrix.sh build devbox
```

Build from a clean Git worktree. Each image is tagged by instance, profile, and
current short commit hash.

### Run a Validation Task

Run the same RoboClaw command across both profiles:

```bash
./scripts/docker/matrix.sh run-task devbox -- status
./scripts/docker/matrix.sh run-task devbox -- agent -m "hello" --no-markdown
```
