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

## Review notes

- Do not put all post-109 work into PR #109. It would make the upstream review too large.
- Keep #109 focused on dataset adapters, curation rewards, account credit exchange, and dataset ingestion.
- Use the `stack/*` branches above for follow-up review.
- The older `pr/1-*` through `pr/6-*` branches remain useful as historical references, but the `stack/*` branches are the cleaner review path.
- The `submit/*fine` branches point at the same tips as the corresponding `stack/*` branches and can be used for comparison.

## Known overlap with open upstream pull requests

| Upstream PR | Overlap area | Handling |
| --- | --- | --- |
| #95 | Training UI, training store, train route, training session files | Rebase or resolve after #95 is merged or closed |
| #97 | Policy registry files and policy registry tests | Avoid duplicating policy registry scope in follow-up PRs |
| #107 | Agent loop, provider factory, custom provider, runtime wiring, CLI commands | Keep provider reliability changes isolated in `stack/03-provider-chat-reliability` |

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
