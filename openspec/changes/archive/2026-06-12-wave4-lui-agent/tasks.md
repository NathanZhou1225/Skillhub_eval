# Tasks: Wave 4 — LUI Agent + 对话/卡片 UI

> 执行顺序：Task 1 → Task 2 & Task 3（可并行）→ Task 4 → Task 5 → Task 6 → Task 7 → Task 8
> 每个 Task = 一个 subagent 单元；执行前必须先读 design.md。

---

## Task 1 — 契约层：DB migration + Port 扩展 + Session Gate

**目标**：横切基础设施，后续所有 Task 依赖。

**涉及文件**：
- `skillhub_eval/core/schemas/enums.py`（新增 `RUNNING_STATUSES`）
- `skillhub_eval/core/ports.py`（新增 6 个 Port 方法）
- `skillhub_eval/persistence/sqlite.py`（实现新方法 + DB version 2 migration）
- `skillhub_eval/adapters/api/_session.py`（新建，Session Gate 共用函数）
- `tests/persistence/test_wave4_infra.py`（新建）

**实现要点**：
- `enums.py`：追加 `RUNNING_STATUSES: frozenset[str]`（见 design §0.1）
- `ports.py`：追加 6 个方法（见 design §0.3）：`increment_auto_run_count / reset_auto_run_count / set_conversation_auto_confirmed / supersede_run / get_lui_messages / create_conversation`（扩展签名加 `source_path` 参数）
- `sqlite.py`：
  - `SCHEMA_VERSION = 2`，`init_db` 追加 version 2 migration：**两列**（`auto_confirmed INTEGER NOT NULL DEFAULT 0` + `source_path TEXT`）；见 design §0.2
  - 实现 6 个新方法；`increment_auto_run_count` 返回新值
  - `supersede_run`：**只**更新旧 run 的 `status=superseded` + `superseded_by_run_id`；不更新 `conversations.active_run_id`（`create_run` 已原子更新）
  - `create_conversation` 扩展：写入 `source_path`
- `_session.py`：`check_session_gate(conv_id, repo)` → 403 frozen / 409 running（见 design §1）

**验收命令**：
```bash
pytest tests/persistence/test_wave4_infra.py -x --tb=short
```

**测试要点**：
- [x] DB migration 幂等（重复 init_db 无副作用）；两列（auto_confirmed + source_path）均存在
- [x] `increment_auto_run_count` 返回递增后的新值
- [x] `supersede_run` 后：old_run status=superseded；`conversations.active_run_id` **不被** supersede_run 改动（由 create_run 控制）
- [x] `create_conversation` 正确存储 source_path
- [x] `check_session_gate`：status=frozen → 403；active run running → 409；completed → pass

---

## Task 2 — LUI Agent 内核

**目标**：`core/lui_agent.py` 完整实现。

**涉及文件**：
- `skillhub_eval/core/lui_agent.py`（新建）
- `tests/core/test_lui_agent.py`（新建）

**实现要点**（见 design §2）：
- `LuiResponse` dataclass（intent / reply / patch）；**patch 不含 `sample_io` 字段**（grill-me G2）
- `LuiAgent.__init__(self, ds_provider)`
- `respond()` 主流程：
  1. frozen 检查 → 强制 explain_only
  2. 特殊 marker 精确字符串匹配（`__TRIGGER_AGENT_OPENING__` / `__SYSTEM_ACTION_CONFIRM_ALL__`）
  3. LLM 单次结构化调用（强制 JSON schema，失败 fallback explain_only）
- `generate_opening()` 确定性拼装（不调 LLM）— 用 report 字段合成开场白
- **`__TRIGGER_AGENT_OPENING__` 幂等保护**：检查 `get_lui_messages(conv_id)` 是否已含 `role=agent` 消息 → 有则静默返回（grill-me 实现修正）
- `_handle_confirm_all()` — 调用 `scan_gaps(bundle, BundleState.draft_enriched)` 验证 gap 归零，通过则 `set_conversation_auto_confirmed(True)`（grill-me 修正：明确使用 draft_enriched）
- System Prompt：patch 格式中 **仅含** `skill_md_updates` + `eval_cases`；不含 sample_io（grill-me G2）

**验收命令**：
```bash
pytest tests/core/test_lui_agent.py -x --tb=short
```

**测试要点**：
- [x] frozen conversation → intent 恒为 explain_only
- [x] `__TRIGGER_AGENT_OPENING__` 第一次：写 lui_message(role=agent)；第二次：幂等静默忽略
- [x] `__SYSTEM_ACTION_CONFIRM_ALL__` 当 gap 未归零时返回拒绝文案（auto_confirmed 不变）
- [x] `__SYSTEM_ACTION_CONFIRM_ALL__` 当 gap 归零时设 auto_confirmed=True
- [x] LLM JSON 解析失败 → fallback explain_only，不 crash
- [x] mock ds_provider 下 intent=mutation 时 patch 无 sample_io 字段

---

## Task 3 — Staging Writer + Run 谱系（与 Task 2 并行）

**目标**：`core/staging_writer.py` 完整实现。

**涉及文件**：
- `skillhub_eval/core/staging_writer.py`（新建）
- `tests/core/test_staging_writer.py`（新建）

**实现要点**（见 design §3）：
- `WriterResult` dataclass（files_written / hash_changed）
- `apply_patch(staging_path, patch)` — 两路写入（grill-me G2：移除 sample_io 路由）：
  - `skill_md_updates` → `_patch_skill_md`（严格保护 body；frontmatter Upsert）
  - `eval_cases` → `_write_cases`（id prefix=`lui_`, origin=`lui_agent`）；每条 case 写完后自动创建对应空 stub JSON（复用 Propagator 逻辑）
- `compute_next_run_mode(staging_path, conv)` — 路由 A/B/C（见 design §3.3）
- `trigger_next_run()` — quota 检查 → supersede → create_run → background_task（见 design §3.4）
- `_freeze_and_escalate()` — 改 run 状态 + 置 frozen + 写 LUI 熔断消息

**验收命令**：
```bash
pytest tests/core/test_staging_writer.py -x --tb=short
```

**测试要点**：
- [x] `apply_patch` 仅改 frontmatter，body 原封不动
- [x] `apply_patch` 对无 frontmatter 的 SKILL.md 安全跳过（返回 hash_changed=False）
- [x] `compute_next_run_mode`：题型未完整 → degraded/minimal；gap 存在 → degraded/draft_enriched；题型完整+gap归零+confirmed → capability_full/confirmed
- [x] `trigger_next_run` quota 满时返回 None + conversation 变 frozen + run 变 awaiting_human_review
- [x] `trigger_next_run` 正常时：auto_run_count +1 → `create_run`（原子更新 active_run_id）→ 单步 `supersede_run(old, new)`；**无 `"__pending__"` 两步模式**（grill-me 修正）
- [x] mutation + hash_changed → `/chat` 处理器重置 auto_confirmed=False；explain_only 不重置（grill-me G4）

---

## Task 4 — API 路由：/chat + /messages + /status + /confirm-cases

**目标**：新建 chat 路由，注册到 app。

**涉及文件**：
- `skillhub_eval/adapters/api/routes/chat.py`（新建）
- `skillhub_eval/adapters/api/app.py`（修改，注册 router）
- `tests/api/test_chat.py`（新建）

**实现要点**（见 design §4.1–4.4）：

`POST /conversations/{conv_id}/chat`：
- 依赖注入：`repo`, `ds_provider`, `gemini_provider`；`BackgroundTasks`
- 完整执行流程：session gate → append user msg → 拉 report → lui_agent.respond → append agent msg → 可选 staging_writer
- 特殊 marker `__SYSTEM_ACTION_CONFIRM_ALL__`：lui_agent 处理后若 auto_confirmed=True → 立即触发 trigger_next_run

`POST /conversations/{conv_id}/confirm-cases`：
- Session gate check
- 逐 case_id 读写 YAML `confirmed: true`
- 返回 `{updated: [...]}`

`GET /conversations/{conv_id}/messages`：
- 调 `repo.get_lui_messages(conv_id)`

`GET /conversations/{conv_id}/status`（见 design §4.4）：
- 实时计算 `gap_zero` + `case_gate_passed` + `case_type_coverage`
- staging_path 通过 `BundleResolver.from_settings` 取得

**app.py 注册**：
```python
from .routes.chat import router as chat_router
app.include_router(chat_router, prefix="/conversations", tags=["conversations"])
```

**验收命令**：
```bash
pytest tests/api/test_chat.py -x --tb=short
```

**测试要点**：
- [x] frozen conversation → `/chat` 返回 403
- [x] engine running → `/chat` 返回 409
- [x] 正常消息 → lui_message 写入 + reply 返回
- [x] intent=mutation → staging 写入 + 新 run 触发
- [x] `__SYSTEM_ACTION_CONFIRM_ALL__` → auto_confirmed=True + trigger_next_run capability_full
- [x] confirm-cases → YAML confirmed:true 写入，无 run 触发
- [x] GET /messages → 按 created_at 排序全量返回
- [x] GET /status → gap_zero / case_gate_passed 正确计算

---

## Task 5 — ZIP 上传支持

**目标**：`POST /conversations/start` 支持 multipart zip。

**涉及文件**：
- `skillhub_eval/adapters/api/routes/conversations.py`（修改）
- `tests/api/test_conversations_upload.py`（新建）

**实现要点**（见 design §4.5）：
- endpoint 改为接受 Form fields + 可选 `UploadFile`
- zip 上传路径：创建 conv → mkdir staging → 解压 zip → 验证 SKILL.md 存在（否则 422 + 清理）
- 解压后走原有 ingest → security scan → sanitizer → propagator → create_run 流程
- `source` 记录为 `"upload"`；staging_path = source_path（zip 上传时两者重合）
- 错误处理：BadZipFile → 422；SKILL.md 缺失 → 422；均需清理 staging 目录

**验收命令**：
```bash
pytest tests/api/test_conversations_upload.py -x --tb=short
```

**测试要点**：
- [x] 合法 zip（含 SKILL.md）→ 202 + conversation_id + run_id；**originals/ 和 staging/ 分别创建**（grill-me G1 双目录）
- [x] 合法 zip：`conversations.source_path` = `data/originals/{conv_id}/`（原文件路径）
- [x] 无效 zip → 422 + originals/ 目录清理
- [x] zip 内无 SKILL.md → 422 + originals/ 目录清理
- [x] local_ref：`conversations.source_path` = 用户提供的原始目录路径
- [x] local_ref 原有路径仍正常工作（回归）

---

## Task 6 — Expert Review 扩展 + Reject 解冻

**目标**：`POST /eval/review/{run_id}` 联动 conversation。

**涉及文件**：
- `skillhub_eval/adapters/api/routes/eval.py`（修改）
- `tests/api/test_review_conversation.py`（新建）

**实现要点**（见 design §4.6）：
- 在现有 `submit_review` 成功分支末尾追加 conversation 联动逻辑
- `reject`：`update_conversation_status(active)` + `set_auto_confirmed(False)` + `reset_auto_run_count` + 写 lui_message(system, 驳回文案)
- `approve`：`reset_auto_run_count` 只（不解冻，W6 publish 负责）
- 联动仅在 `run.conversation_id` 非 null 时执行（兼容旧 run）

**验收命令**：
```bash
pytest tests/api/test_review_conversation.py -x --tb=short
```

**测试要点**：
- [x] Reject：conversation.status 从 frozen → active；auto_run_count=0；lui_messages 包含驳回意见
- [x] Approve：auto_run_count=0；conversation.status 保持不变
- [x] 无 conversation_id 的旧 run：联动代码静默跳过（回归）

---

## Task 7 — UI 双栏对话重构

**目标**：Tab1 演进为 conversation flow 主入口。

**涉及文件**：
- `skillhub_eval/adapters/ui/static/index.html`（修改）

**实现要点**（见 design §5）：

布局：
- Tab1 双栏：左 40% 聊天面板 + 右 60% report 卡片
- 左栏分两阶段：① 入口区（未创建 conversation）② 对话区（已创建）
- 入口区：skill_id 输入 + local_ref 路径 OR zip 文件上传（radio 切换）

聊天面板：
- 消息气泡（role=user 右对齐蓝色 / role=agent 左对齐灰色 / role=system 居中灰小字）
- 底部输入框 + 发送按钮 + `auto_run_count x/5` 角标
- `gap_zero && case_gate_passed && !auto_confirmed` → 显示绿色【整包确认】按钮
- 403 横幅（专家审核中）/ 409 横幅（评估运行中）/ quota 熔断横幅

右侧卡片：
- `Evaluating...` 骨架屏（run running 时）
- `skill_summary` 亮点/不足双列
- `gaps` 列表（severity badge）
- 分数 + case 类型覆盖率进度条
- `security_status` 徽标
- staging case 预览（LUI 写入的 case 小卡片，含 confirmed toggle）

Debug 开关：
- Header 右上角小按钮，点击展示/隐藏原有「手填路径 + POST /eval/run」面板

轮询逻辑（见 design §5.2）：
- `RUNNING_STATUSES` JS 常量对应后端枚举
- run completed + messages_count=0 → 发 `__TRIGGER_AGENT_OPENING__`
- `gap_zero` 变 true → 显示【整包确认】按钮（不自动确认）

**验收**：手工 UI smoke（无 pytest，记录于 W5 runbook）：
- 入口 → 对话 → Agent 开场白出现
- 输入 "帮我补 edge case" → 骨架屏 → 新 report 卡片更新
- 5 次后 quota 熔断横幅出现

---

## Task 8 — 全量集成测试（W4-10）

**目标**：端到端场景 pytest 覆盖；零回归。

**涉及文件**：
- `tests/integration/test_wave4_e2e.py`（新建）

**场景覆盖**：
- [x] **剧本 A 骨干**（mock LLM）：`/conversations/start` → R_101 degraded 完成 → `__TRIGGER_AGENT_OPENING__` → mutation → R_102 → `__SYSTEM_ACTION_CONFIRM_ALL__` → R_103 capability_full
- [x] **Session Lock 409**：engine running 期间 POST /chat 返回 409
- [x] **Quota 熔断**：连续 5 次 mutation 后第 6 次触发 frozen + awaiting_human_review
- [x] **专家 Reject 解冻**：POST /eval/review action=reject → conversation.status=active + auto_run_count=0 + lui_messages 含驳回意见
- [x] **confirm-cases 纯标注**：POST /confirm-cases 仅改 YAML，无新 run 触发
- [x] **路由 C 防线**：题型完整 + gap 归零 + auto_confirmed → capability_full；否则 degraded
- [x] **zip 上传 E2E**：multipart POST → conversation + run；后续 /chat 正常工作

**验收命令**：
```bash
pytest tests/ -x --tb=short
# 目标：328（基线）+ Wave 4 新测试 全绿
```
