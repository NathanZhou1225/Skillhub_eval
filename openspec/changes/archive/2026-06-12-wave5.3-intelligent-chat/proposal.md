# Proposal: Wave 5.3 — 智能对话 + LLM 补题计划 + 交互体验

## What

在 **Wave 5.2**（447 tests）Demo 彩排暴露的体验回归基础上，统一修复实现疏漏，并将 Chat-First 从「状态机 + 词表」升级为 **「按钮门控 + LLM 理解 + 阶段提示」**：

1. **P0 热修（FB-06～09）** — 初评卡片字段对齐；补题表缺口列；发送后清空输入框；统一确认同义词（含「确定」）。
2. **LLM 补题计划 enrich（FB-11 / GQ-W53-1）** — **每次 bootstrap** 在确定性骨架之后调用 LLM，按 **实际 SKILL.md** 生成每行的补测内容、业务预期、红线说明；失败降级 deterministic 表并标注。
3. **IntentRouter 混合路由（FB-21 / GQ-W53-2）** — 状态变更 **仅** 通过 Action Chip / `__ACTION_*__` 或高置信 LLM→action 映射执行；自然语言同义（「确定」「好的」「帮我补题」）由 LLM 归类并 **引导点按钮**，不 silent 穿透。
4. **可推进的结构补齐（FB-12～13）** — `draft_preview` 结构化卡片（将写入的文件 + case 摘要）；「直接帮我写」强制 mutation 路径产出 `eval_cases` + 连带 `sample_io`。
5. **交互体验（FB-10、FB-14～19）** — Skill ID / 确认 / 草案 **全面 Chip 化**；optimistic 用户气泡 + agent「思考中 / 阶段提示」占位（**无 SSE**，MVP 用客户端占位 + `ChatResponse.activity_phase` + 轮询刷新）；评估阶段 chat 内文案；clarify 答案 LLM 解析。
6. **初评→正式时序（FB-18）** — readiness 卡片在数据就绪后再展示；结构通过时阶段提示明确「正在启动正式评估」。

## Why

W5.5 Demo（grill-me / tiered-memory / stock-radar）暴露 W5.2 **标记已解决** 的 FB 项仍有关键体验失败：

| 反馈 ID | 现象 | 根因摘要 |
|---------|------|----------|
| FB-06 | 初评卡片分数/安全全 `—` | 前后端 payload 字段名不一致 |
| FB-07 | 补题表缺口列全 `—` | `gap_count` vs `gap` |
| FB-08 | Chip 发送后输入框残留 | `if (!text)` 才清空 |
| FB-09 | 「确定」不认 | 词表无同义词 |
| FB-10 | Skill 名只能打字 | UI 未做 Chip |
| FB-11 | 补题计划模板化 | W5.2 刻意 deterministic + category 级 hint |
| FB-12～13 | 对话补看不懂、不落盘 | 无 preview 卡；gate 阻断 mutation；LLM patch 常空 |
| FB-14～19 | 不像智能对话 | 主流程 bypass LLM；同步 POST 无阶段反馈 |

**产品诉求**：LUI 应像 Onboarding Agent（懂 Skill、能代写、过程可见），而非表单式词表匹配。

## 已锁定决策（2026-06-10 用户确认）

| 编号 | 决断 |
|------|------|
| **GQ-W53-1** | **每次 bootstrap** 均调用 LLM enrich 补题计划（有缺口则 enrich 后出表；无缺口则 enrich 写入 `conversations.plan_enrichment_json` 供后续 LUI，不出 propagation_plan 卡） |
| **GQ-W53-2** | **无 SSE 流式**；MVP = optimistic 气泡 + agent 占位 + `activity_phase` 阶段文案 + 现有 3s 轮询 |
| **GQ-W53-3** | **混合确认**：关键动作一律 Chip / `__ACTION_*__`；LLM 负责同义理解 + 回复 + 建议下一步按钮；`auto_confirmed` / Propagator / mutation 仍服务端 gate |
| **GQ-W53-4** | LLM enrich **失败** → 保留 deterministic 行 + `enrichment_status=degraded` + 表内标注「通用模板」 |
| **GQ-W53-5** | 统一 `CONFIRM_SYNONYMS`（含「确定」）供 skill_id / propagation / draft 三处复用；Chip 优先于词表 |

## grill-me 已闭合（2026-06-10）

| 编号 | 决议 |
|------|------|
| **GQ-W53-6** | 补题计划阶段点「对话里补」→ **先分叉问**（自动出题 vs 自己描述场景），不默认进草案流 |
| **GQ-W53-6b** | 用户选「描述场景」→ **再分叉**：**写进文件**（draft_preview 流）或 **理解后 Propagator 自动出题**（clarifications 注入）；两条都支持 |
| **GQ-W53-7** | 流程型节点 **引导**：平常白话 + Chip；补题/草案等多步流程加 **2～4 步轻量步骤条** |
| **GQ-W53-7b** | 步骤条 **嵌在卡片顶部**（补题计划 / draft_preview），与表格同屏 |
| **GQ-W53-8** | **用户可见文案规范**：统一说「评估条件 / 评估需求」，少说「题型、case_gate」；无缺口时系统句：「已读完你的 Skill，评估条件已达标，开始初评…」 |
| **GQ-W53-8b** | 补题表表头改白话：**评估场景 \| 尚需补齐 \| 建议补测什么 \| 业务上期望什么 \| 是否红线** |
| **GQ-W53-9** | 模糊自然语言（「帮我弄一下」）→ IntentRouter ≥0.85 才执行；「确认/确定」等 **词表快捷路径** 可直接执行 |
| **GQ-W53-10** | bootstrap enrich：**占位 + 失败降级出表**（不阻断）；无缺口不出表，仅系统提示（GQ-W53-8 文案） |
| **GQ-W53-11** | 草案生成 **连续两次失败** → 明确失败 + Chip：再试 / 手动上传 / 自动出题 |
| **GQ-W53-12** | 评估引擎运行中 **保持 409 锁定**；靠 banner + 阶段提示 + 轮询，不开放评估中闲聊 |

## Non-goals

- SSE / WebSocket 流式 reply（留 Phase 2）
- 修改 1.2 阈值 / R5 / engine 双模型评审逻辑
- Propagator 出题 **算法**大改（仅 plan enrich + clarifications 注入增强）
- W6 集市 / publish
- 新增独立 LLM 安全链路

## Relation to Sprint / prior changes

- **依赖**：`wave5.2-ui-transparency` ✅（447 tests）；W5.5 Demo runbook 待本 change 后重跑
- **修订**：W5.2 GQ2「LLM 软识别」从部分实现升级为 `IntentRouter`；W5.2「计划表无 LLM」→ **bootstrap 必 enrich**
- **文档**：实现后 Task 0 同步 `RECORD.md`（FB-06～22）、Sprint、`Skill评估系统全景说明.md` §3.4
- **Normative**：`docs/specs/Skill元数据定义与编写规范.md` 字段名不变

## Success Criteria

1. 初评 `readiness_result` 卡片：完整度 / 安全 / case_gate / 缺口列表 **有值**（非全 `—`）
2. 补题计划表：缺口列显示数字；业务预期 **因 Skill 而异**（同 Skill 四行可不同）；enrich 失败有降级标注
3. 「确定」与 Chip「确认」等效；Skill ID 步骤有确认 Chip
4. 「帮我在对话里补」→ `draft_preview` 卡 → 确认后 **落盘** eval_cases + sample_io（缺目录场景）
5. 发送消息：输入框清空；聊天区即时出现用户气泡 + agent「正在…」占位；长操作有阶段文案（ enrich / 出题 / 初评 / 正式评估）
6. 自由文本「你直接帮我补充写」在 draft 流内触发 mutation，不再复读缺口清单
7. `pytest tests/ -x --tb=short` 全绿（≥447 + W5.3 新测试）

## Workflow 下一步

1. 用户确认本 proposal（**已完成**）
2. **grill-me** ✅ GQ-W53-6～12（2026-06-10）
3. **subagent-driven-development** — 按 `tasks.md`
4. Task 0 文档同步（实现后）
5. W5.5 Demo 三剧本重跑
