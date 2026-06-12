# Tasks: Wave 5.3 — 智能对话 + LLM 补题计划 + 交互体验

> **前置**：`wave5.2-ui-transparency` ✅（447 tests）。**用户决策** ✅ GQ-W53-1～12（2026-06-10，含 grill-me）。

---

## Task 0 — 文档对齐（实现完成后）

**文件**：`RECORD.md`、`.cursor_memory/active/SPRINT_phase3-marketplace.md`、`docs/guides/Skill评估系统全景说明.md`

**要点**：
- [x] FB-06～22 入表；FB-01～05 标注「W5.3 回归修复」where applicable
- [x] 全景说明 §3.4：bootstrap LLM enrich；IntentRouter；阶段提示
- [x] W5.5 runbook 更新 smoke 条目

---

## Task 1 — P0 热修：readiness / plan 字段 + composer 清空

**文件**：
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/adapters/test_readiness_payload_contract.py`（新建）

**要点**：
- [x] `renderReadinessResultHtml` 读 `completeness_score` / `security_status` / `risk_level_locked` / `case_gate.passed`
- [x] `renderPropagationPlanHtml` 读 `gap_count`（fallback `gap`）；表头 GQ-W53-8b；`flow_step` 步骤条在卡片顶
- [x] readiness 卡：GQ-W53-8 白话（评估条件门槛等）
- [x] `sendConversationMessage` 成功后 **始终** `input.value = ''`

**验收**：
```bash
pytest tests/adapters/test_readiness_payload_contract.py -x --tb=short
```

---

## Task 2 — 统一确认词 `confirm_lexicon`

**文件**：
- `skillhub_eval/core/confirm_lexicon.py`（新建）
- `skillhub_eval/core/skill_id_resolver.py`
- `skillhub_eval/core/lui_agent.py`
- `tests/core/test_confirm_lexicon.py`（新建）

**要点**：
- [x] `is_confirm_message()` 含「确定」
- [x] `skill_id_resolver.is_confirm_reply` 委托 lexicon
- [x] `LuiAgent.is_draft_confirmation` 委托 lexicon + 保留「按这个补」前缀

**验收**：
```bash
pytest tests/core/test_confirm_lexicon.py -x --tb=short
```

---

## Task 3 — LLM 补题计划 enricher + bootstrap 每次调用

**文件**：
- `skillhub_eval/core/propagation_plan_enricher.py`（新建）
- `skillhub_eval/core/propagation_plan.py`（`gap` 别名、`enrichment_status` 字段）
- `skillhub_eval/adapters/api/routes/conversations.py`
- `skillhub_eval/adapters/api/routes/chat.py`（`_refresh_propagation_plan` re-enrich）
- `tests/core/test_propagation_plan_enricher.py`（新建）
- `tests/adapters/test_bootstrap_wave5_3_enrich.py`（新建）

**要点**：
- [x] `enrich_propagation_plan()` mock 测试：四行 business_expectation 可不同
- [x] 失败降级 `enrichment_status=degraded`
- [x] **每次 bootstrap** 调用 enrich；无缺口时 `set_plan_enrichment` 缓存
- [x] clarify 刷新 plan 后 re-enrich

**验收**：
```bash
pytest tests/core/test_propagation_plan_enricher.py tests/adapters/test_bootstrap_wave5_3_enrich.py -x --tb=short
```

---

## Task 4 — DB v6 `plan_enrichment_json`

**文件**：
- `skillhub_eval/persistence/sqlite.py`
- `skillhub_eval/core/ports.py`
- `tests/persistence/test_wave5_3_plan_enrichment.py`（新建）

**要点**：
- [x] `SCHEMA_VERSION = 6`
- [x] `get_plan_enrichment` / `set_plan_enrichment`

**验收**：
```bash
pytest tests/persistence/test_wave5_3_plan_enrichment.py -x --tb=short
```

---

## Task 5 — IntentRouter + Action 白名单

**文件**：
- `skillhub_eval/core/intent_router.py`（新建）
- `skillhub_eval/adapters/api/routes/chat.py`
- `tests/core/test_intent_router.py`（新建）

**要点**：
- [x] `__ACTION_CONFIRM_SKILL__` / `__ACTION_PROPAGATE__` / `__ACTION_MANUAL_UPLOAD__` / `__ACTION_DRAFT_MODE__` / `__ACTION_DRAFT_CONFIRM__`
- [x] GQ-W53-6：「对话里补」先分叉问 + Chip；GQ-W53-6b 写文件 vs Propagator 二选一
- [x] GQ-W53-9：词表 confirm 快捷 + IntentRouter ≥0.85 模糊句
- [x] `ChatResponse.activity_phase` 字段

**验收**：
```bash
pytest tests/core/test_intent_router.py tests/adapters/test_chat_wave5_3_actions.py -x --tb=short
```

---

## Task 6 — UI Action Chips（Skill ID + draft + __ACTION_*__）

**文件**：
- `skillhub_eval/adapters/ui/static/index.html`

**要点**：
- [x] `awaiting_skill_id_confirm` 渲染确认/名称不对 Chip
- [x] propagation Chips 改发 `__ACTION_*__`
- [x] `draft_preview` 卡片 + 确认写入 Chip
- [x] Chip 点击映射可读用户气泡文案

**验收**：手工 + 现有 E2E 扩展（Task 10）

---

## Task 7 — `draft_preview` + 强制代写路径

**文件**：
- `skillhub_eval/core/lui_agent.py`
- `skillhub_eval/adapters/api/routes/chat.py`
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/adapters/test_wave5_3_draft_flow.py`（新建）

**要点**：
- [x] `_generate_draft_patch` 注入 SKILL.md excerpt；缺目录时 prompt 强制 eval_cases
- [x] 成功后 append `draft_preview` + `set_pending_patch`
- [x] GQ-W53-11：`draft_failed` 消息 + 再试/手动上传/自动出题 Chip；最多 2 次 generate
- [x] GQ-W53-7：`next_hint_zh` + 卡片顶 `flow_step`
- [x] 确认后 `StagingWriter.apply_patch` 写入 eval_cases + sample_io

**验收**：
```bash
pytest tests/adapters/test_wave5_3_draft_flow.py -x --tb=short
```

---

## Task 8 — 交互：optimistic 气泡 + 阶段 pending + 评估阶段文案

**文件**：
- `skillhub_eval/adapters/ui/static/index.html`
- `skillhub_eval/adapters/api/routes/chat.py`（long op 返回 `activity_phase`）
- `skillhub_eval/adapters/api/routes/conversations.py`（bootstrap/propagate phase）

**要点**：
- [x] 发送后立即 user bubble + agent pending（`activityPhaseLabel`）
- [x] poll / chat 响应后移除 pending
- [x] RUNNING 时 chat 内 stage 中文一行（读 status API）
- [x] GQ-W53-10：无缺口 system「评估条件已达标，开始初评…」
- [x] GQ-W53-12：评估中 409 保持；stage 白话映射

**验收**：手工 smoke；单元测试 pending 逻辑（可选 js 免测，靠 Task 10）

---

## Task 9 — Clarify LLM 解析

**文件**：
- `skillhub_eval/core/clarification_parser.py`（新建）
- `skillhub_eval/adapters/api/routes/chat.py`
- `tests/core/test_clarification_parser.py`（新建）

**要点**：
- [x] `awaiting_clarify` / `awaiting_propagation_clarify` 多 key 解析
- [x] fallback 现有启发式

**验收**：
```bash
pytest tests/core/test_clarification_parser.py -x --tb=short
```

---

## Task 10 — LuiAgent 上下文 + E2E 集成

**文件**：
- `skillhub_eval/core/lui_agent.py`
- `tests/adapters/test_wave5_3_e2e.py`（新建）

**要点**：
- [x] prompt 注入 skill_md_excerpt + plan_enrichment
- [x] E2E：bootstrap → enrich plan → confirm → readiness 有值 → draft 流（mock LLM）

**验收**：
```bash
pytest tests/adapters/test_wave5_3_e2e.py -x --tb=short
```

---

## Task 11 — 全量回归

**验收**：
```bash
pytest tests/ -x --tb=short
```

目标：≥447 全绿 + W5.3 新增测试。**✅ 472 passed**

---

## 建议实现顺序

```
Task 1 → Task 2 → Task 4 → Task 3 → Task 5 → Task 6 → Task 7 → Task 8 → Task 9 → Task 10 → Task 11 → Task 0
```

**grill-me 已闭合** — 无开放议题。实现后 Task 0 更新 RECORD + Sprint。
