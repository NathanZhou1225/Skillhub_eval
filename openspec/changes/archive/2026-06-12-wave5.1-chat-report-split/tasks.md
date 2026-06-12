# Tasks: Wave 5.1 — 聊天简卡 + 报告分流 + 初评话术流

> **前置**：`wave5-chat-first-shell` 已落地（400 tests）。**grill-me** ✅ GQ1–GQ7（2026-06-10）。

---

## Task 0 — 文档对齐（实现完成后）

**文件**：`RECORD.md`、`.cursor_memory/active/SPRINT_phase3-marketplace.md`

**要点**：
- [x] 新增 Wave 5.1 决策：取消主路径整包确认、C2、方向 A、草案确认流
- [x] 修订 W5 Success Criteria #3 描述（已被 W5.1 取代）
- [x] W5.5 Demo smoke 增「初评无分 / 自动正式 / 历史详情」条目

---

## Task 1 — DB v4 `pending_patch_json` + quota 仅计 capability_full

**文件**：
- `skillhub_eval/persistence/sqlite.py`
- `skillhub_eval/core/ports.py`
- `skillhub_eval/core/staging_writer.py`
- `tests/persistence/test_wave5_1_pending_patch.py`（新建）

**要点**：
- [x] `SCHEMA_VERSION = 4`；`conversations.pending_patch_json`
- [x] `increment_auto_run_count` 仅 capability_full 路径调用（GQ6）
- [x] get/set/clear `pending_patch_json`

**验收**：
```bash
pytest tests/persistence/test_wave5_1_pending_patch.py -x --tb=short
```

---

## Task 2 — rich_report 分阶段 payload + 自动正式评估钩子

**目标**：`report_phase`、简卡字段；初评无缺口自动 `auto_confirmed` + `capability_full`。

**文件**：
- `skillhub_eval/core/chat_notifications.py`
- `skillhub_eval/core/engine.py`（或 notifications 内钩子）
- `tests/core/test_chat_notifications.py`

**要点**：
- [x] `initial` / `formal` / `formal_pending_review`
- [x] `headline_zh`, `summary_one_liner`, `score_line_html`（初评 null）
- [x] `maybe_auto_start_formal_eval` — 仅 degraded 终态 + gap_zero + case_gate
- [x] 移除 payload `actions` 中 `confirm_all`（主路径）

**验收**：
```bash
pytest tests/core/test_chat_notifications.py -x --tb=short
```

---

## Task 3 — 会话状态 `awaiting_draft_confirm` + session gate

**目标**：草案展示后、用户确认前禁止写 staging。

**文件**：
- `skillhub_eval/adapters/api/_session.py`
- `skillhub_eval/adapters/api/routes/chat.py`
- `tests/adapters/test_chat_wave5_1_draft_gate.py`（新建）

**要点**：
- [x] `awaiting_draft_confirm` 允许 explain；mutation 需确认意图
- [x] 未确认 mutation → 403 + 白话 detail

**验收**：
```bash
pytest tests/adapters/test_chat_wave5_1_draft_gate.py -x --tb=short
```

---

## Task 4 — LuiAgent 初评/正式叙事 + 草案流（pending_patch）

**目标**：LLM 白话说明；草案 explain_only；确认后才 patch。

**文件**：
- `skillhub_eval/core/lui_agent.py`
- `tests/core/test_lui_agent.py`

**要点**：
- [x] `compose_post_initial_narrative` / `compose_post_formal_narrative`
- [x] gaps vs case_gate prompt 分叉（design §3.3）
- [x] 生成白话 + **同步写入 `pending_patch_json`**
- [x] 确认 → apply 存盘 patch，**不**二次 LLM
- [x] 修改意见 → 更新白话 + pending_patch
- [x] 消息顺序：叙事 **先于** rich_report（GQ4）

**验收**：
```bash
pytest tests/core/test_lui_agent.py -x --tb=short
```

---

## Task 5 — UI 三套简卡 + 报告 CTA + 轮询修复

**目标**：聊天简卡；跳转历史详情；移除整包确认 chip；修复秒收。

**文件**：
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/api/test_ui.py`

**要点**：
- [x] `renderReportHtml` 按 `report_phase` 分支（C2）
- [x] `openReportFromChat(runId)` → history + modal
- [x] 删除聊天内长折叠块 / confirm_all chip
- [x] 轮询：增量更新或去掉聊天 `<details>`

**验收**：
```bash
pytest tests/api/test_ui.py -x --tb=short
```

---

## Task 6 — 集成测试 E2E

**文件**：`tests/integration/test_wave5_1_report_split.py`（新建）

**剧本**：
1. ZIP 初评无缺口 → 无 confirm chip → 自动第二个 run `capability_full`
2. 有缺口 fixture → 草案消息 → 未确认 mutation 403 → 确认后 patch → 再初评
3. 正式评估简卡含分数行；初评不含
4. CTA `openRunDetail` 数据链（API 层 assert conversation + report）

**验收**：
```bash
pytest tests/integration/test_wave5_1_report_split.py -x --tb=short
```

---

## Task 7 — 全量回归

**验收**：
```bash
pytest tests/ -x --tb=short
```

**手工 smoke**：
- [ ] grill-me ZIP：初评简卡无分数；LLM 说明结构通过；自动正式评估（W5.5 执行）
- [ ] 有缺口样本：先看草案文字，回复确认后才写入（W5.5 执行）
- [ ] 正式完成：简卡有分 + 点击跳转历史详情全量报告（W5.5 执行）
- [ ] 待专家：作者只读 + 专家批准（W5 §4.5）（W5.5 执行）

---

## 依赖图

```
Task1 → Task2 → Task3 ∥ Task4 → Task5 → Task6 → Task7 → Task0
```

## 已闭合决策

| ID | 决议 |
|----|------|
| R1–R8 | 见 proposal |
| GQ1 | 固定 pending_patch，确认原样写入 |
| GQ2 | warn 不拦自动正式 |
| GQ3 | pending_patch 落库 |
| GQ4 | 先 LLM 后简卡 |
| GQ5 | 额度靠 badge |
| GQ6 | 仅 capability_full 计额度 |
| GQ7 | 初评 = degraded 终态 |
