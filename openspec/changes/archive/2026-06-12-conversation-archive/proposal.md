# conversation-archive

## What

侧栏会话「删除」实为归档：`DELETE /conversations/{id}` 将 `status` 设为 `archived` 并写入 `archived_at`；列表默认隐藏；`lui_messages` 与 `evaluation_runs` 保留供评估历史查阅。

## Why

侧栏会话堆积导致 clutter；用户需清理列表但不能破坏评估审计链。

## Scope

- MVP：归档 API + 侧栏删除 UI + 门禁（运行中 409、冻结/待审作者 403）
- 非目标：purge CLI、删 run、删 staging
