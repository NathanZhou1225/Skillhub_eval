# Proposal: Wave 5 — Chat-First 对话壳（Conversational Shell）

## What

将 SkillHub 作者入口从 **「表单 + 双栏仪表盘 + 第三 Tab 专家台」** 重构为 **「ChatGPT 式对话产品」**：

1. **全屏对话主界面** — 左侧会话列表 + 中央消息流 + 底部 Composer（**ZIP 上传**为主；本地路径仅 Demo 开关）
2. **上传与评估全程在对话内完成** — Agent 引导 → 接收 bundle → 自动跑 pipeline → **以 Rich Message 气泡推送完整报告**
3. **交互动作内嵌消息** — 【整包确认】、专家批准/驳回等以 **消息内 Action Chips** 呈现
4. **双视角同一页面** — 「作者 / 专家」模式切换（见 design §4.5 warn 复核流程）
5. **仅两个顶层 Tab** — **对话评估** | **评估历史**（历史须能 **查询对话摘要 + 跳回完整会话**，见 D7）
6. **后端薄扩展** — 会话列表 API、Rich Message、终态 report 气泡、chat 内 bootstrap；**不重写** Engine / LUI 核心

## Why

Wave 4 交付了 LUI 内核与 `/conversations/*` API，但 UI 仍是 **内部运营确认台** 形态：

- 用户必须先填表单才能进入聊天
- 报告渲染在右侧固定卡片，与消息流割裂
- 专家审核独立 Tab，作者无法在同一对话时间线里看到「待审 → 已通过/已驳回」闭环
- 刷新后会话与历史两条线，不像连续对话产品

产品目标（RECORD / 阶段三）强调 **LUI 降低非技术员工门槛**；Chat-First 壳是把已有引擎能力包装成 **单一对话智能体** 体验。

## 已锁定决策（2026-06-10 用户确认）

| 编号 | 决断 |
|------|------|
| D1 | 顶层仅 **2 Tab**：对话评估 + 评估历史；**移除独立专家审核 Tab** |
| D2 | 同一页面 **作者 / 专家视角切换**（非第三 Tab）；warn / 人工待审由后端记录，UI 在专家视角呈现操作 |
| D3 | **左侧会话列表**（可新建 / 切换多个 Skill 上传对话） |
| D4 | Composer **默认仅 ZIP 上传**（📎 附件）；**本地路径仅 Demo**（见 D8） |
| D5 | 评估报告以 **单条 Rich Message 气泡** 内嵌完整卡片（可折叠） |
| D6 | **插队为 Sprint 新 W5**；原 Demo runbook 顺延 **W5.5** |
| D7 | **评估历史 Tab 必须能查对话**：每条 run 展示 `conversation_id`、消息条数、最近预览；详情模态含 **对话摘要区** +「打开完整对话」 |
| D8 | **正式产品只要 ZIP**；`local_ref` 仅开发/Demo：`SKILLHUB_DEMO_LOCAL_REF=true` 时 UI 露出路径框 + API 接受 bootstrap local_ref；生产/默认 **关闭** |
| D9 | **warn + 人工复核** 的视角切换规则见 design §4.5（非 grill-me 阻塞，已给出默认方案） |

## 文档同步 Gate（grill-me 之后、subagent 之前）

**硬顺序**（避免 RECORD/Sprint 与 OpenSpec 实践冲突）：

```
grill-me 闭合 EQ* → Task 0 同步 RECORD + Sprint → Task 1…7 实现 → 归档前 Task 7 终检
```

- **Task 0**（仅文档）：按已定稿的 `proposal/design/tasks` 更新 `RECORD.md` + `SPRINT_phase3-marketplace.md`（Wave 5 替换、W5.5 Demo、删除/取代 W4 双栏 UI 描述、D8 Demo 开关）
- **禁止**：在 grill-me 未完成时改 RECORD 决策表；在 Task 0 未完成时启动 Task 1 代码

## 待 grill-me 明确（实现前必须闭合）

| 编号 | 问题 | 默认倾向（可推翻） |
|------|------|-------------------|
| **EQ1** | 专家审核是否允许 **上传者本人** 在专家视角自批？ | **允许自批**（MVP）；`human_review.operator` 记录操作者；**阶段四 IAM 再细化审批规则**（用户 2026-06-10） |
| **EQ2** | Skill ID 来源 | **纯对话（B）** + 自动识别（§4.8）；**EQ2b**：用户未说明时 **SKILL.md 优先**，zip 名兜底；识别成功后 **Agent 向用户确认名称**，用户肯定后再开评 |
| **EQ3** | Rich Report 消息由 **服务端** 在 run 终态写入 `lui_messages`，还是 **前端** 渲染后回写？ | **服务端写入**（刷新/多端一致；历史 Tab 跳回对话可复现） |
| **EQ4** | 原 Debug 面板（`/eval/run` 手工触发） | **删除默认 UI**；保留 Swagger/CLI 供开发，不在 Chat 壳暴露 |
| **EQ5** | 专家视角下待审队列：仅当前会话 vs 全局待审列表嵌入侧栏 | **侧栏「待人工」分组**（跨会话 badge + 点击跳转该对话） |

## Non-goals

- 不改 1.2 阈值（85/70/90 / R5 10 分线）
- 不重写 `EvaluationEngine`、`LuiAgent` 意图/patch 协议、`StagingWriter` 路由
- 不实现 W6 集市 / publish / listing
- 不做 IAM / SSO / 真实专家权限体系（仅 UI 视角切换 + operator 字符串）
- 不做多 Skill 同一会话
- 不在本 change 写 Demo runbook（顺延 W5.5）

## Relation to Sprint

- **依赖**：Wave 4 ✅（367 tests，`wave4-lui-agent` 应先归档或与本 change 并行合并）
- **取代**：Wave 4 **T7 双栏 UI** 的产品形态（后端 API 复用）
- **顺延**：`.cursor_memory/active/SPRINT_phase3-marketplace.md` 原 Wave 5 Demo → **Wave 5.5**
- **不重复**：Sprint W0–W4 后端清单；OpenSpec tasks 仅覆盖 Chat Shell + 必要 API/DB 扩展

## Success Criteria

1. 打开「对话评估」即见 **会话列表 + 聊天区**，无「先填表再开始」门槛
2. 新会话：Agent 欢迎 → 用户提供 Skill ID + 路径或 ZIP → 自动 `start` + 初评 → **Rich Report 气泡**出现在消息流
3. gap 未清零 / 需补全：Agent 文字说明 + 用户继续聊；满足门禁后消息内出现 **【整包确认】** chip
4. `human_review_required` + warn：作者视角只读 + 系统消息；**按 §4.5 切换专家视角** 完成批准/驳回；结果消息回到 **同一会话**；操作后可自动切回作者
5. 「评估历史」Tab：run 行含对话字段；详情含 **对话摘要** + **打开完整对话**（跳 Tab1 并选中会话）
6. 默认 Composer **仅 ZIP**；`SKILLHUB_DEMO_LOCAL_REF=true` 时可选本地路径（Demo 加速）
7. `pytest tests/ -x --tb=short` 全绿（≥367 + W5 新测试）

## Workflow 下一步

1. **grill-me** — 闭合 EQ1–EQ2 等未决项（D7/D8/D9 已锁定，不进 grill-me）
2. **Task 0** — 同步 RECORD + Sprint（**subagent 代码前必做**）
3. **subagent-driven-development** — Task 1…7
4. Wave 4 归档 + 本 change 归档后 → **W5.5 Demo runbook**（全对话路径 + Demo 本地路径剧本）
