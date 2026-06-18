# Tasks: Wave 5 — Chat-First 对话壳

> **执行顺序（用户 2026-06-10 调整）**：`grill-me` 已闭合 → **Task 1…7 实现** → **Task 0 文档同步**（实现后再对齐 RECORD/Sprint，避免文档与代码脱节）

---

## Task 0 — 文档对齐（**实现完成后** · 归档前）

**目标**：实现落地后同步 RECORD / Sprint；**不写代码**。

**时机**：Task 7 全绿之后、OpenSpec 归档之前。

**文件**：
- `RECORD.md` — 决策表 + 当前状态（W5 Chat-First；W5.5 Demo；D8 Demo 开关；grill-me EQ*）
- `.cursor_memory/active/SPRINT_phase3-marketplace.md` — Wave 5 替换为 Chat-First；原 Demo → **W5.5**；W4 T7「被 W5 取代」

**必须对齐的条目**：
- [ ] 仅 2 Tab（对话 + 历史）；历史含对话查询（D7）
- [ ] 上传默认 ZIP；`SKILLHUB_DEMO_LOCAL_REF` 控制 local_ref（D8）
- [ ] 专家视角 §4.5；Skill ID §4.8（EQ2/2b/2c）
- [ ] Wave 4：实现完成 + OpenSpec 归档状态
- [ ] **禁止** Sprint 仍写「三 Tab 专家台」为当前目标

**验收**：用户确认 RECORD + Sprint 与代码及 `openspec/changes/wave5-chat-first-shell/` 一致。

## Task 1 — 消息模型 + 会话列表（DB v3 + Port）

**目标**：`lui_messages.message_type` / `payload_json`；`list_conversations`；rich_report 幂等查询。

**文件**：
- `skillhub_eval/core/ports.py`
- `skillhub_eval/persistence/sqlite.py`
- `tests/persistence/test_wave5_messages.py`（新建）

**要点**：
- `SCHEMA_VERSION = 3`；migration 追加两列
- `append_lui_message` 扩展 `message_type`, `payload_json`（JSON serialize）
- `list_conversations(limit)`：JOIN 最近一条 message 作 preview；`human_review_pending` 由 active_run 计算
-  helper `has_rich_report_for_run(conv_id, run_id) -> bool`

**验收**：
```bash
pytest tests/persistence/test_wave5_messages.py -x --tb=short
```

---

## Task 2 — Rich Report 服务端写入

**目标**：run 终态自动写入 `rich_report` 气泡。

**文件**：
- `skillhub_eval/core/chat_notifications.py`（新建）
- `skillhub_eval/core/engine.py`（终态钩子）
- `tests/core/test_chat_notifications.py`（新建）

**要点**：
- `build_rich_report_payload(run_id, repo)` — 对齐 `GET /eval/report` 形状
- `append_rich_report_message(conv_id, run_id, repo)` — 幂等
- 在 `_park_awaiting_confirm` 与 finalize 路径调用（需 `run.conversation_id`）
- `actions` 数组含 confirm_all / expert_* 元数据（enabled/visible_in）

**验收**：
```bash
pytest tests/core/test_chat_notifications.py tests/core/test_engine.py -x --tb=short
```

---

## Task 3 — API：会话列表 + Bootstrap

**目标**：对话内启动评估，无需独立表单。

**文件**：
- `skillhub_eval/adapters/api/routes/conversations.py`
- `tests/adapters/test_conversations_wave5.py`（新建）

**要点**：
- `GET /conversations` — list + optional `pending_review=true`
- `POST /conversations/{id}/bootstrap` — **upload 默认**；`local_ref` 仅 `settings.demo_allow_local_ref`
- `POST /conversations/new` — 空会话 + welcome
- `GET /eval/history` 扩展 conversation 字段 + `GET /eval/history/{run_id}/conversation`（D7）
- bootstrap 成功/失败写 system 消息

**验收**：
```bash
pytest tests/adapters/test_conversations_wave5.py -x --tb=short
```

---

## Task 4 — API：Chat Multipart + Review 消息闭环

**目标**：Composer 发 ZIP；专家操作回写对话。

**文件**：
- `skillhub_eval/adapters/api/routes/chat.py`
- `skillhub_eval/adapters/api/routes/eval.py`
- `tests/adapters/test_chat_wave5.py`（新建）

**要点**：
- `POST /conversations/{id}/chat` multipart（message + bundle_zip）
- 无 Demo 时拒绝纯文本路径 bootstrap
- `settings.demo_allow_local_ref` + `.env.example`（D8）
- review approve/reject → system 消息；reject 后作者可继续

**验收**：
```bash
pytest tests/adapters/test_chat_wave5.py -x --tb=short
```

---

## Task 5 — UI 重写：Chat-First 壳

**目标**：删除三 Tab 运营布局；实现 proposal §Success Criteria 1–4。

**文件**：
- `skillhub_eval/adapters/ui/static/index.html`（重写）

**要点**：
- 两 Tab：对话评估 | 评估历史
- Composer：**ZIP 默认**；Demo env 时显示本地路径框
- §4.5 视角切换：待审作者只读 + 专家 badge + chip；裁定后 **自动切回作者**
- 历史 Tab：对话列 + 详情对话摘要 +「打开完整对话」
- 删除专家 Tab、右栏 report、默认 Debug

**验收**：手工 smoke（见 Task 7 checklist）

---

## Task 6 — 集成测试 E2E

**目标**：自动化覆盖 Chat-First 主路径。

**文件**：
- `tests/integration/test_wave5_chat_shell.py`（新建）

**剧本**：
1. 创建空会话 → welcome 消息
2. bootstrap **ZIP**（test fixture zip）→ rich_report
2b. （可选）Demo env bootstrap local_ref
3. awaiting_human_review → 作者只读 → 切专家 → approve → 自动回作者
4. history API 含 conversation 字段 + conversation 端点

**验收**：
```bash
pytest tests/integration/test_wave5_chat_shell.py -x --tb=short
```

---

## Task 7 — 全量回归 + 归档前终检

**目标**：pytest 全绿；手工 smoke。

**文件**：
- `docs/runbooks/phase3-lui-validation.md`（占位：W5.5 再写）

**验收**：
```bash
pytest tests/ -x --tb=short
```

**手工 smoke checklist**：
- [ ] ZIP 上传 → rich_report 在消息流
- [ ] Demo env：本地路径可用；默认 env 路径框不可见
- [ ] warn + 人工复核：作者只读 → 切专家 → 批准 → 自动回作者 + system 消息
- [ ] 评估历史：对话摘要 + 打开完整对话
- [ ] 刷新 → 会话列表 + 消息仍在

---

## 依赖图

```
grill-me ✓ → Task1 → Task2 → Task3 ∥ Task4 → Task5 → Task6 → Task7 → Task0 (RECORD/Sprint)
```

## grill-me 状态：**已闭合**（2026-06-10）

| ID | 决议 |
|----|------|
| EQ1 | MVP **允许自批**；审批 IAM 阶段四细化 |
| EQ2 | **纯对话**收集 ID；无常驻输入框 |
| EQ2b | 静默上传：**SKILL.md > zip 名**；识别后 **向用户确认** |
| EQ2c | **仅自动识别**须确认；用户消息已明说 ID → **跳过确认**直接开评 |

**当前**：Task 1 起 subagent 实现；Task 0 在 Task 7 之后。
