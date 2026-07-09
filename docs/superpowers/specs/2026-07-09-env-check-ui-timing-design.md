# 本地执行环境检查 UI 时机与入口设计

> Date: 2026-07-09  
> Status: Implemented (2026-07-09) — 用户实机确认可用  
> Plan: `docs/superpowers/plans/2026-07-09-env-check-ui-timing.md`  
> Scope: 可选诊断（preflight）在 Chat UI 中的出现时机、主入口位置、路径就绪机制、过程态反馈  
> Out of scope: 恢复 preflight 硬门禁、首 case canary、正式评估前强制弹窗、改动评分语义

## Goal

在保持「环境检查 = 可选诊断、不阻断正式评估」的前提下，让用户在 **ZIP 上传成功后立刻** 能在执行设置中对当前 Skill 做本地执行环境检查，而不是等到补题结束或评估详情卡才看到入口。

## Problem

后端在 ZIP / bootstrap 时已将 Skill 挂载到 `data/staging/<conversation_id>`，路径实际已存在。前端 `getActiveSkillBundlePath()` 主要依赖：

- 隐藏 Bundle 输入框，或
- 消息流里的 `skill_bundle_path` payload

补题 / 自动出题阶段这两处常为空，导致：

- 执行设置 Agent 卡只显示「连接测试」，不显示「运行环境检查」
- 对话顶栏「环境检查」disabled 或不可用
- 用户误以为没有 preflight 能力，或只能在报告卡事后再测

「连接测试」只证明 CLI 能响应，不能替代 Skill 级环境检查。

## Decisions

| 主题 | 决定 | 说明 |
|------|------|------|
| 时机 | ZIP 上传成功后立刻可点 | 不等补题、不依赖正式评估前后 |
| 主入口 | 执行设置 · Agent 卡 | 与「连接测试」并列；按 Agent 分别诊断 |
| 顶栏 | 状态提示（B3） | 显示未检查 / 检查中 / 已通过 / 未通过；点击打开执行设置，不直接跑 preflight |
| 路径就绪 | ZIP/bootstrap 响应带回 `staging_path`（P2） | 前端按 `conversation_id` 缓存，并立刻 `fetchExecScan` |
| 报告卡 | 移除「运行环境检查」按钮（R2） | 复盘时回执行设置；减少入口 |
| 产品语义 | 可选诊断 | 失败仅 toast/warning，不阻断补题或正式评估 |
| 未检查口径 | 一律 `missing`，可点检查 | 禁止把未跑过标成「失败」或「需要生成检查用例」；点检查时自动生成/跑诊断 |
| 过程态 | 卡片 + 顶栏同步 | 点击后「检查中…」；结束后结果留在卡/顶栏，不只 toast |
| 抽屉交互 | overlay 不挡聊天 | 执行设置打开时仍可点「确认继续」等聊天芯片 |

## Target Interaction

1. **上传 ZIP**  
   用户看到：执行设置中 detected Agent 卡出现「运行环境检查」。  
   系统：响应含 `staging_path` → 前端缓存 → `refreshExecScan`。

2. **点「运行环境检查」**  
   用户看到：卡片与顶栏立刻变为「检查中…」；结束后变为「已通过 / 未通过」并保留；toast 作补充。  
   系统：`POST /api/exec/runtimes/{id}/preflight`；写 cache；`fetchExecScan`；更新顶栏状态。

3. **顶栏**  
   用户看到：环境状态 pill（未检查 / 检查中 / 已通过 / 未通过）。  
   系统：点击打开执行设置抽屉，不在顶栏直接 POST preflight。

4. **正式评估**  
   用户看到：照常进入 `case_executing`。  
   系统：不因 preflight 缺失 / 失败 / 过期返回 `LOCAL_RUNTIME_PREFLIGHT_REQUIRED`。

## Layout

### 执行设置 · Agent 卡（主入口）

- 「连接测试」与「运行环境检查」并列。
- 显示条件：Agent `detected` **且** 当前会话已有缓存 / 已知的 `staging_path`。
- 「当前 Skill 检查：…」状态行在有路径时始终可见；无路径时明确文案「上传 ZIP 后可检查当前 Skill」，禁止静默空白。
- `can_run_local_check === false` 时：按钮可显示为 disabled + 简短原因，或提供「重置轻量检查」路径；不得在路径已就绪时因「尚未生成检查用例」而整颗按钮消失（与「上传后立刻可点」冲突的部分需在实现中修正）。

### 对话顶栏（B3）

- 将现有可点击「环境检查」改为状态提示（例如「环境：未检查」）。
- 过程中显示「环境：检查中…」；结束后「已通过 / 未通过」（勿用「失败」表示未检查）。
- 点击 → 打开执行设置，聚焦本地执行区。
- 仅在 `exec_source=local` 时显示该状态区。
- 执行设置抽屉打开时，overlay **不得**挡住聊天区芯片（如「确认继续」）。

### 评估详情卡

- 从 `renderExecAttributionCard` 移除「运行环境检查」按钮。
- 本地执行归属文案保留；诊断入口统一回执行设置。

## Path Readiness (P2)

1. Bootstrap / ZIP 上传相关 API 在成功挂载 staging 后，响应中返回 `staging_path`（字符串，与现有 `skill_bundle_path` 语义一致）。
2. 前端维护 `Map<conversation_id, staging_path>`（或等价会话级状态）。
3. `getActiveSkillBundlePath()` 优先级建议：
   1. 会话缓存的 `staging_path`
   2. 隐藏 Bundle 输入框
   3. 消息 payload 中的 `skill_bundle_path`
4. 路径写入缓存后立刻 `fetchExecScan(true)`，使 Agent 卡 `local_check_*` 字段与按钮可见。
5. 本轮不做前端硬拼 `data/staging/<id>`（P3）。刷新后缓存丢失时，可从后续消息或后续增强的 status 字段补齐；P1（status 始终带路径）列为可选后续，非本轮硬依赖。

## Non-Goals

- 恢复 skill-specific preflight 作为正式评估硬门禁
- 正式评估前强制弹窗 / 强制先检查
- 首 case canary（另议 P1）
- 在报告卡保留环境检查入口
- 前端硬编码推断 staging 根路径
- 改变「失败 case 不评分 / 全失败整轮 failed」的评分语义

## Implementation Touchpoints (indicative)

- `skillhub_eval/adapters/api/routes/conversations.py` / chat bootstrap：成功响应增加 `staging_path`
- `skillhub_eval/adapters/ui/static/assets/index.js`：路径缓存、`getActiveSkillBundlePath`、Agent 卡按钮条件、顶栏 B3、去掉报告卡按钮
- `skillhub_eval/adapters/ui/static/index.html`：顶栏按钮改为状态控件（若需）
- 测试：UI contract / API 响应字段；可选：路径缓存后 scan 带 `skill_bundle_path`
- 文档：`docs/runbooks/local-agent-exec-validation.md` 补「上传后即可在执行设置检查」一句

## Success Criteria

- 新对话上传 ZIP 成功后，无需等补题完成，打开执行设置即可对 detected Agent 点击「运行环境检查」
- 顶栏显示环境状态，点击进入执行设置，不直接跑检查；未检查不显示为「失败」
- 点击检查后卡片与顶栏有「检查中…」过程态，结束后结果持久显示
- 开着执行设置时仍可点击聊天区「确认继续」
- 评估详情卡不再出现环境检查按钮
- 环境检查失败不阻止正式评估进入 `case_executing`
- 连接测试与环境检查在 UI 上仍可区分

## Open Follow-ups (not blocking)

- P1：`GET /conversations/{id}/status` 始终返回 `staging_path`，刷新页面后仍稳
- 正式评估前弱提醒（非强制）是否需要
- 高风险缺 authored 模板时「重置轻量检查」入口的发现性

## Implementation notes (landed 2026-07-09)

- Confirm loop: internal actions / `awaiting_skill_id_confirm` ignore lingering ZIP attachments.
- Readiness: no prior result → `missing` + `can_run_local_check=true` (not `blocked`).
- Live progress: `_runtimePreflightStatus` drives card + header while request in flight.
- Drawer: `#exec-drawer-overlay` uses `pointer-events-none`; aside uses `pointer-events-auto`.

## Visual Companion

讨论过程画板：`.cursor/projects/.../canvases/env-check-ui-timing.canvas.tsx`（决策定稿视图）。
