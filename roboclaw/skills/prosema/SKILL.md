---
name: prosema
description: Orchestrate the chat-first ProSemA learning workflow and open the structured workbench only when needed.
---

# ProSemA

Use this skill when the user wants to:

- inspect or choose a learning dataset
- start a ProSemA workflow
- run quality filtering
- run prototype discovery
- check semantic propagation status
- jump from chat into the structured learning workbench

## Operating rules

- Keep the user in chat for launch, status, explanations, and next-step guidance.
- Use the `learning_workbench` tool for all workflow-affecting actions.
- Do not pretend that prototype selection, timeline editing, or annotation span editing can be done safely in plain chat.
- When the user needs structured review or editing, call `learning_workbench` with `action="open_workbench"` and explain why the workbench is needed.

## Suggested chat flow

1. Clarify which dataset or workflow the user means.
2. Use `learning_workbench` to create or inspect the workflow state.
3. Keep routine steps in chat:
   - quality filtering
   - prototype discovery
   - status checks
   - train trigger
4. Escalate to the workbench when the task requires:
   - video review
   - prototype comparison
   - annotation editing
   - semantic result validation
