# Proposal: Wave 5.2 — UI 透明化 + 补题确认 + 全对话澄清

## What

在 **Wave 5.1**（413 tests）已落地基础上，修复 W5.5 Demo 暴露的 **透明化与信任** 问题，并锁定新一轮交互决策：

1. **补题暂停 + 计划表（UI-B3）** — 缺 `eval_cases` / `sample_io` 时 **不静默 Propagator**；展示 **表格化补题计划**（题型、数量、测什么、业务预期）；用户选择路径后再写 staging。
2. **三种补题方式** — 方式一（默认）自行重传 ZIP；方式二「帮我在对话里补」→ W5.1 草案流；方式三「确认」→ 系统自动出题（`prop_*`）。
3. **全对话澄清（UI-S2）** — 对 Skill 设计（用途、受众、输出形态、边界、风险、case 意图）**有任何不确定，必须先问用户**；LuiAgent 新增 `clarify` intent，禁止低置信 silent mutation / propagate。
4. **正式结论徽标（UI-VERDICT）** — 正式评估简卡显式 **通过 / 需人工复核 / 不通过**（保留 C2：初评仍无分数）。
5. **过程可见** — `propagation_plan` / `propagation_summary` 消息类型；Propagator 摘要写入对话；修订 bootstrap 流程（deferred propagation）。
6. **初评瘦身（GQ12–GQ13）** — `degraded` 初评仅 **准入体检**（安全 + 规则风险 + 结构缺口 + 题型门槛 + 完整度）；**不跑**双模型逐题评审、**不跑**风险 AI ③；**不落**全量 `EvaluationReport`；结果 **整条消息自包含**，**无**「查看完整报告」CTA。
7. **正式简卡增强（GQ14）** — 结论 + 一句摘要 + **下一步指引**（可上架 / 需人工 / 未通过请修改）+ 查看完整报告（仅正式）。

## Why

W5.1 解决了「聊天 vs 报告分流」和「草案确认」，但 Demo（grill-me 等）暴露：

| 反馈 ID | 现象 |
|---------|------|
| FB-01 | Pass 后对话无明确「通过」结论，仅分数 |
| FB-02 | 缺 eval_case 时 Propagator **静默**执行，用户不知原包缺什么、系统补了什么 |
| FB-03 | 「结构检查已通过」过粗，自动正式路径无过程叙事 |
| FB-04 | 工作台信息块移除后，对话内无等价「清点 / 来源 / 补题」节点 |
| FB-05 | 「系统做了什么 → 用户做什么 → 结论是什么」三段式断裂 |

**根因**：自动动作（Propagator、auto formal）与对话叙事脱节；Chat-First 做了信息减法，未重建 **知情同意** 节点。

**设计源**：`docs/superpowers/specs/2026-06-10-chat-ui-transparency-design.md`（brainstorm 2026-06-10，用户已审阅 OK）。

## 已锁定决策（2026-06-10）

| 编号 | 决断 |
|------|------|
| **UI-B3** | 缺题 **暂停**；补题计划表 + **三方式**；默认自补重传；「帮我在对话里补」→ 草案；「确认」→ Propagator |
| **UI-TBL** | 表格列：题型 / 需补·已有 / 测什么 / 业务预期（`case_template_hint`）/ sample_io 行 |
| **UI-S2** | **全对话生命周期**不确定则问；`clarify` intent；L0 规则 + L1 LLM |
| **UI-CLARIFY-L0** | category 缺失、description 过短、risk 不符、包过空等 → 最多 3 问，阻塞写盘 |
| **UI-CLARIFY-L1** | 歧义 / 低置信 → `clarify`，禁止 mutation / Propagator |
| **UI-VERDICT** | 正式简卡 `verdict_zh` + 徽标；初评仍无分（W5.1 C2 保持） |
| **UI-3WAY** | 每条计划消息说明三方式 + 「也可直接聊使用场景」 |

## Non-goals

- 第三 Tab「包状态」
- 修改 1.2 阈值 / R5 10 分线（正式评估仍用现有 DecisionStage）
- Propagator 出题算法大改（仅触发时机 + clarifications 注入）
- W6 集市 / publish / IAM
- 本 change 不写 W5.5 runbook 全文（可更新 smoke 条目）

## Relation to Sprint / prior changes

- **依赖**：`wave5.1-chat-report-split` ✅（413 tests）
- **修订**：W3 Propagator「上传即静默出题」→ **用户确认后出题**；全景说明 §3 / §4.4 流程图需同步
- **Sprint**：`.cursor_memory/active/SPRINT_phase3-marketplace.md` Wave 5.2 条目
- **参考 spec**：`docs/superpowers/specs/2026-06-10-chat-ui-transparency-design.md`

## Success Criteria

1. 缺 eval_case 的 ZIP：**无 run_id**；对话出现 `propagation_plan`；staging **无** `prop_*` 直至用户「确认」
2. 计划表含 sample_io 行 + 三方式说明 + 交流引导
3. L0 触发时先澄清再展示完整表；L1 `clarify` 期间 mutation → 403
4. 「帮我在对话里补」进入 W5.1 `awaiting_draft_confirm`；「我自己补」可重传 ZIP 重新清点
5. Propagator 执行后 `propagation_summary` 消息列出写入文件
6. 正式简卡：`verdict_zh` + `next_action_zh` + 摘要 + CTA 完整报告；初评 **无** rich_report、**无** 报告 CTA
7. 初评 run：引擎 **无** `model_judging` 阶段；对话 `readiness_result` 含 gaps/安全/风险/门槛/完整度/下一步
8. `pytest tests/ -x --tb=short` 全绿（≥413 + W5.2 新测试）

## grill-me 已闭合（2026-06-10）

| 编号 | 决议 |
|------|------|
| **GQ1** | **A**：只要缺任何题型数量（含「已有 1 缺 2」），一律暂停出表 + 三选一 |
| **GQ2** | **A**：「确认」等自然语言靠 **conversation.status 硬分流** + **LLM 软识别**同义表述；写盘/Propagator 仅 status 允许时执行 |
| **GQ3** | **C**：补题表与 L0 澄清 **同一条消息**；答后 **刷新** 表（业务预期列更新） |
| **GQ4** | **A+B**：选「我自己补」后只答疑/模板不写入；用户描述具体题目时可 **提议** 切方式二 |
| **GQ5** | **B**：仅 `awaiting_human_review`/冻结时简卡「需人工复核」；warn 无专家 → **「通过（有改进建议）」** |
| **GQ6** | **A**：L0 澄清 **可跳过**；跳过后业务预期用通用模板并标明 |
| **GQ7** | **A**：重传 ZIP = **整包重载** staging 后重新清点 |
| **GQ8** | **A**：自动出题后初评前叙事 **必须** 提及已补 N 道题 + 下一步 |
| **GQ9** | **B**：计划表 **只保留最新一条**（同消息逻辑更新），不堆多张表 |
| **GQ10** | **B**：计划卡 **三个 Action Chip** + 自然语言仍有效 |
| **GQ11** | **A**：high 风险 refusal/adversarial **不** 在按钮外二次确认；表内红线说明即可 |
| **GQ12** | **R2**：初评 = 安全扫描 + **规则**风险锁定 + gaps + case_gate + **completeness_score**；**跳过** model_judging、风险 AI ③、skill_summary LLM |
| **GQ13** | 初评 **不出报告**；`readiness_result` 消息 **自包含全部可读结论**；**无** `openRunDetail` / 无初评 rich_report |
| **GQ14** | 正式简卡：`verdict_zh` + `summary_one_liner` + `next_action_zh`（可进入上架流程 / 需人工 / 请修改重评）+ **仅正式**保留「查看完整报告 →」 |
| **GQ15** | **B**：历史 Tab **不展示**初评（`degraded`）run；初评结论 **仅在对话** `readiness_result` 可见；历史仅列 `capability_full` 正式评估 |

## Workflow 下一步

1. 用户确认本 proposal（**已完成**）
2. **grill-me** ✅ GQ1–GQ11（2026-06-10）
3. **subagent-driven-development** — 按 `tasks.md`
4. Task 0 同步 RECORD + Sprint + `Skill评估系统全景说明.md` §3（实现后）
