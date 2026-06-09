# Proposal: Wave 0 基础设施 — conversations / run lineage / staging / lui_messages

## What

为阶段三 LUI / Propagator / 集市全链路奠定数据基础：

1. **SQLite schema migration**（`PRAGMA user_version` v0→v1）：新建 `conversations`、`lui_messages` 表；`evaluation_runs` 追加 lineage 列（`conversation_id` / `parent_run_id` / `superseded_by_run_id`）
2. **`RunStatus.superseded` 枚举值**：显式状态，防止 UI 状态机歧义——旧 run 被代写顶替时，`status` 字段明确写为 `superseded`
3. **`core/bundle_resolver.py`**：领域语义接口（`ensure_staging` / `get_file_content` / `write_file_content` / `list_files`），彻底屏蔽裸路径，防止写穿透污染用户原目录
4. **Repository Protocol 最小扩展**：`create_conversation` / `get_conversation` / `append_lui_message` + `create_run` 签名升级支持 `conversation_id` / `parent_run_id`

## Why

阶段三 W1–W7 全部 Wave 均依赖 `conversation_id` 关联上下文、run lineage 追踪代写历史、LUI 消息落盘及 staging 路径隔离。

**若不在 Wave 0 建立统一接口抽象**，后续各 Wave 开发者将各自拼接裸路径，产生两类高危风险：
- **写穿透**：Propagator 直接向用户原始 Skill 目录写合成 case，污染 `testskills/` 存量样本
- **状态机歧义**：UI 判断 run 是否废弃须额外查 `superseded_by_run_id`，每处渲染都需双重判断

## Scope

### In-scope

| 组 | 改动 | 文件 |
|----|------|------|
| A | SQLite DDL migration + `PRAGMA user_version` 版本控制 | `skillhub_eval/persistence/sqlite.py` |
| B | `RunStatus.superseded` 枚举；`evaluation_runs` lineage 列 | `skillhub_eval/core/schemas/enums.py`、`skillhub_eval/persistence/sqlite.py` |
| C | `BundleResolver` 领域语义接口（完整路径解析 + IO 实现） | `skillhub_eval/core/bundle_resolver.py`（新建）、`skillhub_eval/settings.py` |
| D | Repository Protocol 最小扩展 + `SqliteRepository` 新 CRUD 方法 | `skillhub_eval/core/ports.py`、`skillhub_eval/persistence/sqlite.py` |
| E | pytest：DDL 幂等 / migration / BundleResolver / conversations CRUD | `tests/persistence/test_wave0_infra.py`（新建） |

### Non-goals（不动）

- 1.2 评估阈值（85/70/90）及 R5 10 分线
- W1–W7 业务逻辑（taxonomy、security scan、propagator、LUI agent 等）
- `conversations.status` frozen/published 同步（API 层责任，归 W4）
- 现有 220 tests 的语义（只做必要兼容，不改存量测试逻辑）
- `upload` zip 解压实现（BundleResolver `ensure_staging` 对 upload 仅创建目录，W3 填充）

## Relation to Sprint

SPRINT `phase3-marketplace.md` Wave 0（W0-1 至 W0-5）。本 change 完成后 Wave 0 全部勾选，W1–W7 可安全并行启动。

## Success Criteria

1. `pytest tests/ -x` 全绿（≥220 + 新增 Wave 0 测试通过）
2. 二次 `repo.init_db()` 不报错（幂等）；旧存量 DB 执行 migration 后 `PRAGMA user_version = 1`
3. `BundleResolver(conv_id, source="local_ref", source_path=...).ensure_staging()` 将源目录深拷贝到 `{STAGING_ROOT}/{conv_id}/`，源目录内容不变
4. `repo.create_run(..., conversation_id=conv_id, parent_run_id=old_run_id)` 写入 DB 可读回
5. `RunStatus.superseded` 可赋值给 `evaluation_runs.status`，且 `list_history` 默认不返回 superseded runs
6. `repo.create_conversation(skill_id, source="local_ref") -> conv_id` 写入 `conversations` 表；`get_conversation(conv_id)` 读回完整 dict
7. `repo.append_lui_message(conv_id, role="agent", content="...")` 写入 `lui_messages`；按 conv_id 查询返回有序列表
