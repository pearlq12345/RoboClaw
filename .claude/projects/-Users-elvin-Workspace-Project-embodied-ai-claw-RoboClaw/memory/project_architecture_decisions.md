---
name: Architecture Decisions (2026-03-22)
description: 11 architecture decisions made during deep architecture review session
type: project
---

Architecture decisions confirmed on 2026-03-22:

1. Remove unused schema abstractions (ControlGroups, SafetyZones, SafetyBoundaries, ResourceOwnership, FailureDomains, CompensationSpec, IdempotencyMode)
2. ROS2 is the ONLY transport — simulation also goes through ROS2, product-vision.md "transport abstraction" is wrong
3. Planner lives inside embodied/ (not agent/), calls LLM for intent decomposition
4. Perception is an independent module parallel to execution/
5. Simulation is high priority — MuJoCo first choice, URDF as primary model format
6. Only modify roboclaw/embodied/ — agent/, channels/ etc come from nanobot and don't need major changes
7. simulation/ sits at embodied level (parallel to execution/)
8. Direct MuJoCo adapter deleted — unified ROS2 path only
9. research/ renamed to learning/
10. SOUL.md rewritten as agent identity/capability manual; AGENTS.md has embodied workflows
11. Codex CLI: use `-m gpt-5.4` (no --fast or --reasoning-effort flags exist)

**Why:** User tends to over-architect; hardware + agent verification is the bottleneck, not coding speed. Architecture should minimize unverifiable abstractions.

**How to apply:** Every new module must serve a concrete verification goal. Don't add abstractions ahead of need.
