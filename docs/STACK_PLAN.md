# RoboClaw submission stack

This repository currently has one upstream pull request that acts as the base for the remaining work:

- Upstream PR: https://github.com/MINT-SJTU/RoboClaw/pull/109
- Head branch: `pearlq12345:feat/dataset-adapter-contract`
- Base commit for the next stack: `b7fed2c`

The remaining changes are organized locally as a stacked series. Each branch builds on the previous branch.

| Order | Local branch | Base | Scope |
| --- | --- | --- | --- |
| 0 | `stack/00-upstream-pr109-base` | `origin/main` | Current upstream PR #109 head |
| 1 | `stack/01-autonomous-cloud-training` | `stack/00-upstream-pr109-base` | Cloud runtime bindings, VLA/RL planning, supervisor routes, Training Center state and panels |
| 2 | `stack/02-dataset-push-assets` | `stack/01-autonomous-cloud-training` | Dataset push command, asset registration, dataset UI/store updates |
| 3 | `stack/03-provider-chat-reliability` | `stack/02-dataset-push-assets` | Provider compatibility, chat connection handling, provider tests |
| 4 | `stack/04-code-hygiene-safe-auto` | `stack/03-provider-chat-reliability` | Helper splits, operational error visibility, safe automatic repair loop |

## Published branch mapping

| Review branch | Remote head | Current tip |
| --- | --- | --- |
| Upstream PR #109 | `pearlq12345:feat/dataset-adapter-contract` | `b7fed2c` |
| Follow-up 1 | `pearlq12345:pr/01-autonomous-cloud-training` | `201498d` |
| Follow-up 2 | `pearlq12345:pr/02-dataset-asset-flow` | `186ffaa` |
| Follow-up 3 | `pearlq12345:pr/03-provider-chat-reliability` | `8705ac4` |
| Follow-up 4 | `pearlq12345:pr/04-code-hygiene-and-observability` | `4e76143` |

## Review notes

- Do not put all post-109 work into PR #109. It would make the upstream review too large.
- Keep #109 focused on dataset adapters, curation rewards, account credit exchange, and dataset ingestion.
- Use the `stack/*` branches above for follow-up review.
- The older `pr/1-*` through `pr/6-*` branches remain useful as historical references, but the `stack/*` branches are the cleaner review path.
- The `submit/*fine` branches point at the same tips as the corresponding `stack/*` branches and can be used for comparison.

## Known overlap with open upstream pull requests

| Upstream PR | Overlap area | Handling |
| --- | --- | --- |
| #95 | `pyproject.toml`, `roboclaw/embodied/service/session/train.py`, `roboclaw/http/routes/train.py`, `ui/src/domains/training/pages/TrainingCenterPage.tsx`, `ui/src/domains/training/store/useTrainingStore.ts` | Treat as the older provider-aware training backend path. Rebase or make an explicit architecture decision before moving cloud training UI changes upstream. |
| #97 | `roboclaw/embodied/policy/*`, `tests/test_policy_registry.py` | Do not publish duplicate policy registry work until #97 is merged, closed, or replaced. |
| #107 | `roboclaw/cli/commands.py`, `roboclaw/providers/custom_provider.py`, `roboclaw/agent/loop.py`, `roboclaw/http/runtime.py` | Keep provider reliability changes isolated in `stack/03-provider-chat-reliability`; rebase after #107 lands if it is accepted. |
| #108 | `pyproject.toml` only | No architectural dependency. Resolve dependency metadata conflict if #108 lands first. |

## Verification commands

Run targeted checks before publishing a branch:

```bash
python -m pytest tests/test_evo_train_routes.py tests/test_agent_cloud_training_tool.py tests/test_vla_rl_routes.py -q
python -m pytest tests/test_dataset_push_cli.py tests/test_dataset_upload_completion.py -q
python -m pytest tests/test_provider_text_tool_fallback.py -q
cd ui && npm run build
```

Run the full backend suite before an upstream submission:

```bash
python -m pytest tests/ -x -q
```
