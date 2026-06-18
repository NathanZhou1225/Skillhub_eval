# Tasks: Wave 5.2 — UI 透明化 + 补题确认 + 全对话澄清

> **前置**：`wave5.1-chat-report-split` ✅（413 tests）。**grill-me** ✅ GQ1–GQ15（2026-06-10）。**实现 + Task 0** ✅（447 tests，2026-06-11）。

---

## Task 0 — 文档对齐（实现完成后）

**文件**：`RECORD.md`、`.cursor_memory/active/SPRINT_phase3-marketplace.md`、`docs/guides/Skill评估系统全景说明.md`

**要点**：
- [x] FB-01～05 标记已解决；W5.2 决策入表
- [x] 全景说明 §3 流程图：Propagator 改为「确认后」；§4.4 三方式
- [x] W5.5 smoke 增：补题计划表 / 三方式 / Pass 徽标 / 无静默 prop（见 Sprint W5.5）

---

## Task 1 — DB v5 `clarifications_json` + 新 conversation status

**文件**：
- `skillhub_eval/persistence/sqlite.py`
- `skillhub_eval/core/ports.py`
- `tests/persistence/test_wave5_2_clarifications.py`（新建）

**要点**：
- [x] `SCHEMA_VERSION = 5`；`conversations.clarifications_json`
- [x] `get_clarifications` / `merge_clarifications`
- [x] status 文档化：`awaiting_propagation_confirm`, `awaiting_propagation_clarify`, `awaiting_manual_upload`, `awaiting_clarify`

**验收**：
```bash
pytest tests/persistence/test_wave5_2_clarifications.py -x --tb=short
```

---

## Task 2 — `propagation_plan` builder + L0 触发

**文件**：
- `skillhub_eval/core/propagation_plan.py`（新建）
- `skillhub_eval/core/case_sanitizer.py`（sample_io gap 若需）
- `tests/core/test_propagation_plan.py`（新建）

**要点**：
- [x] `build_propagation_plan()` 确定性表格 payload
- [x] `detect_l0_clarifications()` 最多 3 问
- [x] 复用 `TYPE_DESCRIPTIONS`、`CASE_TYPE_REQUIREMENTS`、taxonomy `case_template_hint`

**验收**：
```bash
pytest tests/core/test_propagation_plan.py -x --tb=short
```

---

## Task 3 — Deferred Propagator + bootstrap 拆分

**文件**：
- `skillhub_eval/adapters/api/routes/conversations.py`
- `skillhub_eval/core/propagator.py`（clarifications 注入）
- `tests/adapters/test_bootstrap_wave5_2_deferred.py`（新建）

**要点**：
- [x] security 后 sanitizer → plan；有缺口 **不** propagate、**不** create run
- [x] append `propagation_plan` message；`propagation_deferred=true`
- [x] L0 未满足 → `awaiting_propagation_clarify`
- [x] Propagator prompt 注入 `clarifications_json`

**验收**：
```bash
pytest tests/adapters/test_bootstrap_wave5_2_deferred.py -x --tb=short
```

---

## Task 4 — Chat 三方式路由 + propagation_summary

**文件**：
- `skillhub_eval/adapters/api/routes/chat.py`
- `skillhub_eval/adapters/api/_session.py`
- `tests/adapters/test_chat_wave5_2_propagation_gate.py`（新建）

**要点**：
- [x] 「确认」→ propagate → summary message → create run
- [x] 「我自己补」→ `awaiting_manual_upload` + 模板说明
- [x] 「帮我在对话里补」→ `awaiting_draft_confirm`（复用 W5.1）
- [x] 重传 ZIP 重新 sanitizer + plan
- [x] session gate 新 status

**验收**：
```bash
pytest tests/adapters/test_chat_wave5_2_propagation_gate.py -x --tb=short
```

---

## Task 5 — LuiAgent `clarify` intent + UI-S2 prompt

**文件**：
- `skillhub_eval/core/lui_agent.py`
- `tests/core/test_lui_agent_clarify.py`（新建）

**要点**：
- [x] `intent=clarify`；`clarification_keys`；禁止 patch
- [x] 全对话：Skill 设计不确定 → clarify
- [x] 用户回答 → `merge_clarifications`
- [x] clarify 期间 chat mutation → 403

**验收**：
```bash
pytest tests/core/test_lui_agent_clarify.py tests/core/test_lui_agent.py -x --tb=short
```

---

## Task 6 — Engine 初评瘦身（GQ12 R2）

**文件**：
- `skillhub_eval/core/engine.py`
- `tests/core/test_engine_readiness.py`（新建）

**要点**：
- [x] `degraded` 路径在 case_gate/gaps 后 **early terminal**（跳过 model_judging、AI risk ③、skill_summary）
- [x] 保留 security + 规则 risk + completeness + gaps 快照
- [x] 轻量 readiness 持久化（非全量 EvaluationReport）

**验收**：
```bash
pytest tests/core/test_engine_readiness.py -x --tb=short
```

---

## Task 7 — `readiness_result` 消息（GQ13）

**文件**：
- `skillhub_eval/core/chat_notifications.py`（或 `readiness_notifications.py`）
- `skillhub_eval/core/engine.py`（钩子替换初评 rich_report）
- `tests/core/test_readiness_notifications.py`（新建）

**要点**：
- [x] `append_readiness_result_message`；payload 自包含 gaps/安全/风险/门槛
- [x] 初评 **不** `append_rich_report_message`
- [x] 叙事先于 readiness 卡片

**验收**：
```bash
pytest tests/core/test_readiness_notifications.py -x --tb=short
```

---

## Task 8 — 正式简卡 `verdict_zh` + `next_action_zh`（GQ14）

**文件**：
- `skillhub_eval/core/chat_notifications.py`
- `tests/core/test_chat_notifications.py`

**要点**：
- [x] `_resolve_verdict()` + `_resolve_next_action()`（GQ5 映射）
- [x] 仅 formal / formal_pending_review 有 CTA
- [ ] 自动正式叙事可引用 propagator summary（GQ8）

**验收**：
```bash
pytest tests/core/test_chat_notifications.py -x --tb=short
```

---

## Task 9 — UI：plan / readiness / formal 三套卡片

**文件**：
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/api/test_ui.py`

**要点**：
- [x] `renderPropagationPlanHtml` / `renderPropagationSummaryHtml`
- [x] 三 Action Chip（GQ10）+ `handlePropagationAction`
- [x] 计划表单条更新（GQ9 `plan_version`）
- [x] `renderMessages` 分支新 message_type
- [x] `renderReadinessResultHtml`（无报告 CTA，GQ13）
- [x] 正式简卡 `verdict_zh` + `next_action_zh`（GQ14）
- [x] 历史 Tab：**不列出** `degraded` 初评 run（GQ15 B）；API 或前端过滤
- [x] Composer 提示（awaiting_propagation_confirm）

**验收**：
```bash
pytest tests/api/test_ui.py -x --tb=short
```

---

## Task 10 — 集成测试 E2E ✅

**文件**：`tests/integration/test_wave5_2_transparency.py`（新建）

**剧本**：
1. grill-me 类 ZIP（仅 SKILL.md）→ plan 表、无 prop、无 run
2. 「确认」→ prop 文件 + summary + 初评 run
3. 「帮我在对话里补」→ draft_confirm 链
4. L0 category 缺失 → clarify 先于 plan
5. 初评 run 无 model_judging；有 readiness_result、无 rich_report
6. 正式 Pass → verdict_zh + next_action_zh + 报告 CTA
7. 历史列表 **不含** degraded 初评 run（GQ15 B）

**验收**：
```bash
pytest tests/integration/test_wave5_2_transparency.py -x --tb=short
```

---

## Task 11 — 全量回归 ✅

**验收**：
```bash
pytest tests/ -x --tb=short
```

**手工 smoke**（W5.5）：
- [ ] 缺题 ZIP：见表 → 选方式 → 无静默补题
- [ ] Pass 后简卡显示「通过」
- [ ] 不确定时 Agent 主动提问

---

## 依赖图

```
Task1 → Task2 → Task3 → Task4
              ↘ Task5 ↗
Task3 → Task6 → Task7 → Task8 → Task9 → Task10 → Task11 → Task0
```

## 已闭合决策

| ID | 决议 |
|----|------|
| UI-B3 | 缺题暂停；三方式；默认自补 |
| UI-S2 | 全对话 clarify |
| UI-TBL | propagation_plan 表 |
| UI-VERDICT | 正式 Pass/Warn/Fail 徽标 |

## Workflow 下一步

1. **grill-me** ✅ GQ1–GQ15
2. **实现 + Task 0** ✅
3. **待办**：`/opsx:archive` + W5.5 Demo smoke

## grill-me 已闭合

见 `proposal.md` GQ1–GQ11。
