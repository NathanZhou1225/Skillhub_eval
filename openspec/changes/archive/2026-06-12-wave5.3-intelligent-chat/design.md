# Design: Wave 5.3 — 智能对话 + LLM 补题计划 + 交互体验

> **前置**：W5.2 UI 透明化 ✅（447 tests）  
> **源反馈**：W5.5 Demo FB-06～22；用户 2026-06-10 锁定 GQ-W53-1～5

---

## 1. 架构总览

```
┌──────────────────────────────────────────────────────────────────┐
│ UI (index.html)                                                   │
│  · Action Chips → __ACTION_*__ 或 显式文案                        │
│  · optimistic user bubble + agent pending bubble (activity_phase) │
│  · readiness / propagation_plan / draft_preview 卡片              │
└────────────────────────────┬─────────────────────────────────────┘
                             │ POST /chat  ChatResponse.activity_phase
┌────────────────────────────▼─────────────────────────────────────┐
│ chat.py 路由顺序（修订）                                          │
│  1. ZIP bootstrap                                                 │
│  2. IntentRouter.resolve() → action | defer_to_llm               │
│  3. action 白名单执行（skill_confirm, propagate, draft_mode, …）  │
│  4. propagation gate（status 硬门控）                             │
│  5. LuiAgent._llm_respond（自由对话 + mutation + clarify）        │
└────────────────────────────┬─────────────────────────────────────┘
                             │
┌────────────────────────────▼─────────────────────────────────────┐
│ bootstrap (_phase_eval)                                           │
│  security → sanitizer → build_propagation_plan (deterministic)    │
│           → enrich_propagation_plan (LLM, 每次 bootstrap)         │
│           → append plan OR cache enrichment                       │
└──────────────────────────────────────────────────────────────────┘
```

**不变**：Session gate（frozen 403、running 409）；staging 不上架；capability_full 门槛；初评无 rich_report CTA。

---

## 2. P0 热修 — 前后端契约

### 2.1 `readiness_result` payload（二选一，推荐 A）

**A — UI 适配后端（最小 diff）**：

```javascript
// index.html renderReadinessResultHtml
const score = payload.completeness_score;
const security = payload.security_status;
const riskLocked = payload.risk_level_locked;
const gate = payload.case_gate || {};
const gateLabel = gate.passed ? '通过' : '未通过';
```

**B — 后端补 UI 别名**（可选，tasks 二选一）：在 `append_readiness_result_message` 增加 `completeness: { score, status }` 嵌套。

### 2.2 `propagation_plan` 行字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `gap_count` | int | 确定性 |
| `gap` | int | **别名**，与 `gap_count` 同值（兼容 UI） |
| `tests_what` | str | enrich 后 Skill 级补测说明 |
| `business_expectation` | str | enrich 后 Skill 级业务预期 |
| `redline` | bool \| str | enrich 后；UI 显示「是/否」+ 一句红线说明 `redline_note` |
| `enrichment_source` | `llm` \| `deterministic` | 降级标注 |

### 2.3 Composer

```javascript
// 发送成功后始终清空
input.value = '';
```

### 2.4 统一确认词

**模块**：`skillhub_eval/core/confirm_lexicon.py`（新建）

```python
CONFIRM_SYNONYMS = frozenset({
    "确认", "确定", "对", "是的", "yes", "ok", "好", "好的", "可以",
    "正确", "没错", "行", "同意", "y", "yeah",
})
def is_confirm_message(text: str) -> bool: ...
```

替换 `skill_id_resolver.is_confirm_reply`、`LuiAgent.is_draft_confirmation` 的前缀逻辑改为调用 `is_confirm_message`（草案仍允许「按这个补」等前缀扩展）。

---

## 3. LLM 补题计划 enrich（GQ-W53-1）

### 3.1 模块

**文件**：`skillhub_eval/core/propagation_plan_enricher.py`（新建）

```python
async def enrich_propagation_plan(
    plan: dict,
    *,
    skill_md_excerpt: str,
    skill_id: str,
    category_slug: str,
    clarifications: dict,
    ds_provider: BaseLLMProvider,
) -> dict:
    """LLM 填充 rows[].tests_what / business_expectation / redline_note."""
```

### 3.2 调用时机（GQ-W53-10）

**每次 bootstrap**（`conversations._phase_eval` 在 sanitizer 之后 **必调**）：

```python
plan = build_propagation_plan(...)
plan = await enrich_propagation_plan(plan, ...)  # 失败 → enrichment_status=degraded，不阻断
if needs_propagation:
    append propagation_plan  # UI 占位「正在读懂你的 Skill…」直至返回
else:
    repo.set_plan_enrichment(conv_id, plan.get("enrichment_snapshot"))
    append system: "已读完你的 Skill，评估条件已达标，开始初评…"  # GQ-W53-8
```

**刷新计划**（clarify 回答后 `_refresh_propagation_plan`）：re-build deterministic → **re-enrich**（clarifications 已更新）。

### 3.3 Prompt 要点

- 输入：SKILL.md 摘录（≤3000 字）、risk、category、sanitizer counts、clarifications、每行 `type` + `gap_count`
- 输出：JSON `{ "rows": [{ "type", "tests_what", "business_expectation", "redline_note" }] }`
- 约束：四行内容 **必须互不相同**；refusal/adversarial 必须写清拒绝边界；不得编造包内不存在的 API
- 超时：复用 `PROVIDER_CALL_TIMEOUT_S`；失败 → `enrichment_status=degraded`，保留 deterministic `TYPE_DESCRIPTIONS`

### 3.4 Payload 扩展

```python
{
  "plan_version": 1,
  "enrichment_status": "ok" | "degraded" | "skipped",
  "rows": [...],
  "l0_questions": [...],
}
```

---

## 4. IntentRouter（GQ-W53-2 / GQ-W53-3）

### 4.1 Action 白名单

| Action ID | 触发 | 效果 |
|-----------|------|------|
| `__ACTION_CONFIRM_SKILL__` | Chip / LLM→action | `continue_eval_after_skill_id_confirmed` |
| `__ACTION_PROPAGATE__` | Chip / 同义确认 | Propagator + 初评 |
| `__ACTION_MANUAL_UPLOAD__` | Chip | `awaiting_manual_upload` 模板 |
| `__ACTION_DRAFT_MODE__` | Chip | `awaiting_draft_confirm` 引导 |
| `__ACTION_DRAFT_CONFIRM__` | Chip / 同义 | 应用 pending_patch |
| `__SYSTEM_ACTION_CONFIRM_ALL__` | 既有 | auto_confirmed |

**UI Chip** 发送 `__ACTION_*__`（silent=false 仍显示用户侧文案映射为「确认继续评估」等可读 label）。

### 4.2 解析顺序（`chat.py`）（GQ-W53-9）

```python
if message.startswith("__ACTION_") or message == _CONFIRM_ALL_MARKER:
    return execute_action(...)
# 词表快捷路径：明确 confirm 词 + 当前 status 允许 → 直接 execute
if is_confirm_message(message) and status in CONFIRM_ALLOWED_STATUSES:
    return execute_action(status_default_action(status), ...)
intent = await intent_router.classify(message, status, history_snippet)
if intent.action in WHITELIST and intent.confidence >= 0.85:
    return execute_action(intent.action, ...)
return lui_agent.respond(...)  # explain + next_hint + suggest chips
```

模糊表述（「帮我弄一下」）**仅** IntentRouter 高置信执行；否则 reply 高亮对应 Chip。

### 4.3 `IntentRouter`（新建 `core/intent_router.py`）

- 单次 LLM JSON：`{ "action": null|"propagate"|..., "confidence": 0-1, "reply": "..." }`
- `action=null` → 仅回复 + 建议点哪个 Chip
- **禁止** LLM 直接返回 patch（patch 仅 LuiAgent mutation 路径）

---

## 5. `draft_preview` 与强制代写（FB-12～13）

### 5.1 新 message_type

`draft_preview` payload：

```python
{
  "files_to_write": ["SKILL.md (frontmatter)", "eval_cases/lui_hp_01.yaml", "sample_io/lui_hp_01.json"],
  "cases_preview": [
    {"id": "lui_hp_01", "type": "happy_path", "user_intent": "...", "input_snippet": "..."}
  ],
  "skill_md_updates": {"negative_prompts": "..."},
  "cta": ["确认写入", "继续修改"],
}
```

生成：`LuiAgent._generate_draft_patch` 成功后 `append_lui_message(..., message_type=draft_preview)` + `set_pending_patch`。

### 5.2 「直接帮我写」路由（GQ-W53-11）

**When** `awaiting_draft_confirm` 且用户消息匹配 `DIRECT_WRITE_PHRASES`（词表）**或** LLM classify `action=draft_regenerate`：

- 重新调用 `_generate_draft_patch`，prompt **强制**：缺 `eval_cases/` 时必须输出 ≥1 case；每条 case 含完整四字段
- 最多 **2 次**尝试；仍空 patch → `message_type=draft_failed` + Chip：**再试一次** / **手动上传 ZIP** / **自动出题**（若仍缺评估条件）

### 5.3 `StagingWriter`

- 已有 `_write_cases` 连带 `sample_io` — 保持不变
- mutation 在 `awaiting_draft_confirm` + 确认后 **允许**（现有逻辑）

### 5.4 Propagation vs Readiness 分流（GQ-W53-6 / GQ-W53-6b）

**When** `awaiting_propagation_confirm` 且用户点「对话里补」或同类意图：

1. **不**直接进入 `awaiting_draft_confirm`
2. Agent **先问**（步骤条 1/3）：「你想 **系统自动出题**，还是 **先描述使用场景**？」+ Chip
3. 用户选 **自动出题** → `__ACTION_PROPAGATE__`（或词表/IntentRouter 确认）
4. 用户选 **描述场景** → 步骤条 2/3，**再问**：
   - **「写进文件让我确认」** → `awaiting_draft_confirm` + `_generate_draft_patch` → `draft_preview`
   - **「你理解后自动出整套题」** → merge `clarifications_json` → refresh enrich plan → 引导点「自动出题」

**When** 初评后 `awaiting_draft_confirm`（缺目录/字段/eval_cases）：

- 直接 draft_preview 流；「直接帮我写」失败两次 → GQ-W53-11 失败 Chip

### 5.5 流程引导与步骤条（GQ-W53-7 / GQ-W53-7b）

- 多步流程（补题分叉、草案确认）在 **卡片顶部** 渲染 `flow_step: { current, total, label_zh }`
- 每步 Agent 回复 **必须** 含 `next_hint_zh`（一句白话 + 可用 Chip 列表）
- 非流程节点：仅白话 + Chip，不出步骤条

**补题分叉示例步骤**：

| step | label_zh |
|------|----------|
| 1/3 | 选择补全方式 |
| 2/3 | 描述场景或确认自动出题 |
| 3/3 | 确认写入或开始初评 |

---

## 6. 交互体验 — 阶段提示（GQ-W53-2）

### 6.1 客户端（无 SSE）

**发送时**：

1. 立即 render optimistic user bubble
2. 插入 agent pending bubble：`message_type=ui_pending`，文案来自 `activityPhaseLabel(phase)`
3. `POST /chat` 返回后移除 pending，poll 刷新

**`activityPhaseLabel`**：

| phase | 文案 |
|-------|------|
| `thinking` | 正在理解你的意思… |
| `enriching_plan` | 正在分析 Skill 并生成补题计划… |
| `propagating` | 正在自动生成评估题目（约 1–2 分钟）… |
| `initial_eval` | 正在进行初评体检… |
| `formal_eval` | 正在进行正式双模型评估… |
| `writing_draft` | 正在生成修改草案… |

### 6.2 服务端

`ChatResponse` 扩展：

```python
class ChatResponse(BaseModel):
    ...
    activity_phase: str | None = None  # 供 UI 首帧 pending 文案
```

bootstrap / propagate / draft 生成路径在 long-running 步骤 **开始前** 可选 append system narrative（已有部分，补齐 propagate 前「正在出题」）。

### 6.3 评估进行中（GQ-W53-12）

- 保留 top banner「评估进行中…」；**不开放**评估中 `/chat`（409 保持）
- chat 内追加 **阶段轨迹** 一行（读 `run.stage_progress` 最新 stage **白话**映射，如「正在做正式双模型评估…」）
- 409 时 toast「评估进行中，请稍候」+ 移除 pending；composer disabled

### 6.4 初评→正式时序（FB-18）

1. 初评 terminal → narrative → **`readiness_result`（数据完整后一次 append）**
2. 若 `can_enter_formal` → system「结构检查已通过，正在启动正式评估…」→ auto formal
3. formal terminal → 正式简卡（既有）

避免先 append 空 readiness 再补数据 — `append_readiness_result_message` 仅在 report 持久化完成后调用（已如此；修 UI 即可）。

---

## 7. 用户可见文案规范（GQ-W53-8 / GQ-W53-8b）

| 内部概念 | 对用户说法 |
|----------|------------|
| case types / 题型 | **评估场景** |
| gap / gap_count | **尚需补齐**（数量） |
| case_gate | **评估条件门槛** |
| gap_zero + gate | **评估条件已达标** |
| readiness | **初评体检**（避免 degraded/摸底） |

**补题计划表头**（整表）：评估场景 | 尚需补齐 | 建议补测什么 | 业务上期望什么 | 是否红线

**readiness 卡**：完整度 / 安全 / **评估条件门槛** / 待补齐项（不用 case_gate、field_path 直出）

---

## 8. UI Chip 清单

| 场景 | Chips |
|------|-------|
| `awaiting_skill_id_confirm` | `确认「{skill_id}」` / `名称不对` |
| `propagation_plan` | 既有三 Chip + 发送 `__ACTION_*__` |
| `draft_preview` | `确认写入` / `继续修改` |
| `awaiting_draft_confirm`（无 preview） | 同上 |

---

## 9. Clarify 答案 LLM 解析（FB-19）

**When** `awaiting_clarify` 或 `awaiting_propagation_clarify`：

```python
async def parse_clarification_message(message, pending_keys, ds) -> dict[str, str]
```

- 单条消息可填多 key
- 失败 fallback 现有 `key：value` / 单 key 启发式

---

## 10. LuiAgent 上下文增强

`_build_prompt` 增加：

- `skill_md_excerpt`（staging SKILL.md ≤2000 字）
- `plan_enrichment_json` / 最新 propagation_plan rows
- `conversation.status`

仍单次 JSON 调用；reply 上限放宽至 400 字（草案说明场景）。

---

## 11. DB / API

| 变更 | 说明 |
|------|------|
| `conversations.plan_enrichment_json` | SCHEMA v6；无缺口 bootstrap 缓存 enrich |
| `ChatResponse.activity_phase` | 可选字段 |
| message_type 新增 | `draft_preview`, `ui_pending`（仅客户端也可不落库 pending） |

**建议**：`ui_pending` **仅客户端**维护，不落 DB，减少迁移。

---

## 12. 测试策略

| 区域 | 测试文件 |
|------|----------|
| confirm_lexicon | `tests/core/test_confirm_lexicon.py` |
| plan enricher | `tests/core/test_propagation_plan_enricher.py`（mock LLM） |
| intent router | `tests/core/test_intent_router.py` |
| readiness UI payload | `tests/adapters/test_readiness_payload_contract.py` |
| draft_preview E2E | `tests/adapters/test_wave5_3_draft_flow.py` |
| bootstrap always enrich | `tests/adapters/test_bootstrap_wave5_3_enrich.py` |

---

## 13. 文件 touch 清单

| 文件 | 变更 |
|------|------|
| `core/confirm_lexicon.py` | 新建 |
| `core/intent_router.py` | 新建 |
| `core/propagation_plan_enricher.py` | 新建 |
| `core/propagation_plan.py` | gap 别名；enrich 钩子 |
| `core/lui_agent.py` | excerpt；draft_preview；direct write |
| `core/skill_id_resolver.py` | 委托 confirm_lexicon |
| `adapters/api/routes/chat.py` | IntentRouter；activity_phase |
| `adapters/api/routes/conversations.py` | bootstrap enrich |
| `adapters/ui/static/index.html` | 卡片/Chips/pending/清空 |
| `persistence/sqlite.py` | v6 plan_enrichment_json |
| `core/chat_notifications.py` | 可选 UI 别名 |
