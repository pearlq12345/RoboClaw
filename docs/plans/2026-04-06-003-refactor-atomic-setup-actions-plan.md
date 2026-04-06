---
title: "refactor: Decompose identify wizard into atomic Agent-callable actions"
type: refactor
status: active
date: 2026-04-06
---

# refactor: Decompose identify wizard into atomic Agent-callable actions

## Overview

Replace the monolithic `setup(action="identify")` wizard with atomic actions that the Agent can freely compose. The Agent decides the sequence based on user intent and current state, rather than running a fixed pipeline every time.

## Problem Frame

The current `identify` wizard is a fixed linear pipeline:
```
select type → select model → scan ALL → motion detect ALL → name ALL → commit ALL
```

This causes multiple UX failures:
- "配置相机" triggers the full arm+camera wizard
- Adding one arm requires re-scanning and re-identifying everything
- Can't add a camera without first going through arm motion detection
- Can't skip steps the user doesn't need
- Agent has no way to call individual steps

The fix: expose each step as an independent tool action. The Agent reads the current manifest state, decides what's needed, and calls only those steps.

## Requirements Trace

- R1. Agent can scan hardware without entering the identify wizard
- R2. Agent can probe a specific port to detect motor protocol and IDs
- R3. Agent can start/poll/stop motion detection on unbound ports independently
- R4. Agent can bind an arm to a known port+type without motion detection
- R5. Agent can bind a camera by dev path (already done: `bind camera`)
- R6. Agent can rebind an arm's role/alias (already done: `rebind arm`)
- R7. The identify wizard still works as a convenience but is NOT the only path
- R8. AGENTS.md guides the Agent to compose these actions intelligently

## Scope Boundaries

- NOT removing the identify wizard (it's still useful for first-time setup)
- NOT changing the Manifest or Binding data model
- NOT changing calibration, teleop, record, or any downstream flow

## Key Technical Decisions

- **Expose existing internal methods, don't create new abstractions** — SetupSession already has scan, motion detect, assign. We just need tool-layer wiring.
- **`bind_arm` needs port path + arm_type** — Agent gets the port from scan results, chooses arm_type from registry. No motion detection required if the Agent already knows which port is which.
- **Motion detection remains optional** — useful for first-time identification when the user doesn't know which port is which arm. Not needed when rebinding or when scan results make it obvious.
- **Agent decides the flow** — AGENTS.md gives decision rules, not a fixed sequence.

## High-Level Technical Design

> *Directional guidance, not implementation specification.*

```
BEFORE (fixed pipeline):
  Agent → identify wizard → [type→model→scan→motion→name→commit] → done

AFTER (atomic actions, Agent composes):
  Agent reads manifest state
    ├── "配置相机"     → scan → show cameras → bind_camera(dev, alias)
    ├── "加一个臂"     → scan → show ports → motion_detect OR bind_arm(port, type, alias)
    ├── "改角色"       → rebind_arm(alias, new_type)
    ├── "重新识别全部"  → identify wizard (still works as convenience)
    └── "换个名字"     → rename_arm(alias, new_alias)
```

New tool actions in setup group:

| Action | Params | What it does |
|--------|--------|-------------|
| `scan` | (none) | Scan ports + cameras, return list (already exists) |
| `probe` | `port` | Probe a specific port, return protocol + motor IDs |
| `motion_start` | (none) | Start motion detection on unbound serial ports |
| `motion_poll` | (none) | Poll motion, return which port moved |
| `motion_stop` | (none) | Stop motion detection |
| `bind_arm` | `alias, arm_type, port` | Bind a serial port as an arm directly |
| `bind_camera` | `alias, dev` | Bind a camera (already done) |

## Implementation Units

- [ ] **Unit 1: Expose `probe` action**

**Goal:** Agent can probe a specific port to detect what motors are on it

**Requirements:** R2

**Dependencies:** None

**Files:**
- Modify: `roboclaw/embodied/tool.py`
- Test: `tests/test_embodied_tool.py`

**Approach:**
- Add `probe` action to setup tool group
- Takes `port` param (by-id path from scan results)
- Calls HardwareDiscovery.discover() or prober directly on that port
- Returns protocol (dynamixel/feetech) + motor IDs

**Patterns to follow:**
- Existing `scan` action dispatch in tool.py

**Test scenarios:**
- Happy path: probe a valid port → returns protocol + motor IDs
- Error path: probe a non-existent port → clear error
- Edge case: probe a camera serial port → returns empty motor list

**Verification:**
- Agent can call `setup(action="probe", port="/dev/serial/by-id/usb-...")` and get motor info

---

- [ ] **Unit 2: Expose `motion_start` / `motion_poll` / `motion_stop` actions**

**Goal:** Agent can use motion detection independently of the identify wizard

**Requirements:** R3

**Dependencies:** None

**Files:**
- Modify: `roboclaw/embodied/tool.py`
- Test: `tests/test_embodied_tool.py`

**Approach:**
- Add 3 actions to setup tool group: `motion_start`, `motion_poll`, `motion_stop`
- `motion_start`: calls SetupSession.start_motion_detection() on unbound serial ports
- `motion_poll`: calls SetupSession.poll_motion(), returns moved port stable_id
- `motion_stop`: calls SetupSession.stop_motion_detection()
- SetupSession must be in ASSIGNING or IDENTIFYING phase (scan must have run first)

**Patterns to follow:**
- SetupSession already has these methods, just not wired to tool.py

**Test scenarios:**
- Happy path: start → poll (stub reports movement) → returns moved port → stop
- Error path: poll without start → clear error
- Error path: motion_start when embodiment is busy → EmbodimentBusyError
- Edge case: start when no unbound serial ports → clear message

**Verification:**
- Agent can run motion detection as 3 separate calls, not one monolithic wizard

---

- [ ] **Unit 3: Expose `bind_arm` action**

**Goal:** Agent can bind a serial port as an arm directly, without motion detection

**Requirements:** R4

**Dependencies:** None (uses Manifest.set_arm directly)

**Files:**
- Modify: `roboclaw/embodied/tool.py`
- Test: `tests/test_embodied_tool.py`

**Approach:**
- Add `bind_arm` to modify dispatch (like `bind_camera`)
- Params: `alias`, `arm_type` (e.g., "koch_leader"), `port` (by-id path)
- Scans ports to find matching SerialInterface, then calls Manifest.set_arm()
- No motion detection — Agent already knows which port from scan/probe results

**Patterns to follow:**
- `bind_camera` implementation we just added

**Test scenarios:**
- Happy path: bind_arm with valid port + type → arm appears in manifest
- Error path: invalid arm_type → clear error listing valid types
- Error path: port not found → clear error with available ports
- Error path: port already bound to another arm → conflict error
- Edge case: bind same port with same alias (idempotent) → success

**Verification:**
- Agent can say `setup(action="modify", operation="bind", target="arm", alias="left", arm_type="koch_follower", port="/dev/serial/by-id/...")` and it works

---

- [ ] **Unit 4: Update AGENTS.md with composition rules**

**Goal:** Agent knows how to compose atomic actions based on user intent

**Requirements:** R8

**Dependencies:** Units 1-3

**Files:**
- Modify: `roboclaw/templates/AGENTS.md`

**Approach:**
Add decision rules:
```
## Device Configuration

Read current manifest state before deciding what to do:
- "配置相机" / "add camera" → scan, then bind_camera
- "配置机械臂" / "add arm" → scan, then either:
  - bind_arm (if user knows which port) 
  - motion_start → motion_poll → bind_arm (if user needs to identify by moving)
- "改角色" / "change role" → rebind_arm
- "重新配置" / "reconfigure everything" → identify (full wizard)
- "重命名" → rename

Do NOT default to the full identify wizard for simple operations.
Use scan first to show the user what's available, then compose the appropriate actions.
```

**Test expectation:** none — pure documentation

**Verification:**
- Agent uses `scan` + `bind_camera` for "配置相机" instead of launching identify wizard

---

- [ ] **Unit 5: Keep identify wizard as convenience wrapper**

**Goal:** Ensure the existing identify wizard still works unchanged

**Requirements:** R7

**Dependencies:** None (this is a verification, not a change)

**Files:**
- No changes needed — identify wizard is untouched

**Test expectation:** none — verify existing identify tests still pass

**Verification:**
- `setup(action="identify")` still runs the full wizard as before
- Existing tests pass

## System-Wide Impact

- **API surface parity:** CLI tool actions and Web API routes. New tool actions should also get HTTP routes in `roboclaw/http/routes/setup.py` (deferred to follow-up, Web UI is Elvinyk's domain)
- **Unchanged invariants:** Manifest data model, Binding structure, calibration flow, teleop/record — all unchanged
- **Interaction graph:** New actions go through EmbodiedService, respect embodiment lock, emit events via EventBus — same as existing actions

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| Agent may call actions in wrong order (e.g., bind_arm before scan) | Clear error messages + AGENTS.md guidance |
| Motion detection lock leak if Agent crashes between start/stop | SetupSession.reset() already cleans up; add timeout to motion_start |
| Elvinyk's concurrent UI changes may conflict | Our changes are in tool.py (not setup_session.py internals). Low conflict risk. |
