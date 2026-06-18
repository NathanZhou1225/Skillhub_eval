# Change: ui-local-exec-bridge

> 依赖后端 change `local-agent-exec-bridge`（W8 引擎已落地，583 tests）。本 change 将 Scan / 选 CLI / 模式切换 / Consent / 双轨 UI 暴露到网页，**零 .env 手工配置**完成 Demo 验收。
> 线框与组件清单（权威视觉）：`docs/superpowers/specs/2026-06-17-ui-local-exec-bridge-wireframes.md`

## Why

W8 后端已能在 `skillhub-eval serve` 同机 spawn 本地 CLI agent 真跑 skill，但网页 UI **零暴露**：用户仍须改 `.env`（`EXEC_SOURCE` / `EXEC_AGENT` / `EXEC_CONSENT_REQUIRED`）或 Python 注入 consent；阶段文案仍写「运行样例题」，无法区分样例自证 vs 本地真跑。Open Design 已验证「Scan → Radio Card → 即时切换」的 DX；SkillHub 需在 **制式回单** 视觉语言下补齐同等感知，才能做网页端 `exec-fixture-minimal` 验收并 archive W8。

## What Changes

- 新增 **Exec Bridge API**：`GET /api/exec/agents/scan`、`GET|PUT /api/exec/preferences`、`POST /api/exec/consent`、`POST /api/exec/agents/{id}/test`（连接测试）。
- **Session 级 preferences** → **sqlite 全局单行持久化**（`exec_preferences` 表，DB v10）；覆盖 env；整台电脑一份。
- **UI 组件 C01–C11, C15–C16**（见线框 doc）：顶栏状态 pill、420px 右侧设置 Drawer、首次进入 C16 横幅、BridgePromptCard（**8s poll 同卡自动变绿**）、评估 Banner / 报告 / 历史双轨标签。
- **C16 定稿文案**：默认本地 Agent CLI 真跑测试 Skill；可选切换样例评估 sample_io。
- 引擎 `RoutingExecutionSource` 读取 **session preferences**（优先于 env `EXEC_SOURCE` / `EXEC_AGENT`）。
- chat 流 **BridgePromptCard 纯前端**（local 未就绪时；不写 DB）；就绪后 in-place 变绿并 **自动续跑** 被拦的正式评估。
- **正式评估门禁**：local 且未就绪 → 不启动；Skill 要求 local 但全局为 sample → **Modal 确认**。
- **Non-breaking**：用户可切回 sample_io，行为与 W8 前一致。

## Capabilities

### New Capabilities

- `exec-bridge-api`: HTTP API for CLI scan, session preferences, consent grant, and agent connection test; wires into existing `LocalAgentSource` / `consent` / adapters.
- `exec-bridge-ui`: Eval UI (`index.html`) components for indicator, settings drawer, onboarding banner, bridge prompt card with poll, dual-track labels in banner/report/history.

### Modified Capabilities

- （无）`openspec/specs/` 主规范目录为空；后端执行语义已在 change `local-agent-exec-bridge` 的 `specs/skill-execution/spec.md` 定义。本 change 仅增 UI/API 暴露层。

## Non-Goals

- 独立 `skillhub-cli bridge` daemon 或浏览器直连 CLI（架构仍为 serve 同机 spawn）。
- Open Design 深色主题 / 三栏 case 侧栏重构。
- Live Terminal 流式 log（C14，v2）。
- per-case 执行摘要折叠（C12–C13，v1.5）。
- W8.4 多 agent 对照统计。
- 修改 1.2 阈值 / R1–R8 决策逻辑。

## Relation to Sprint

阶段三 · Wave 8 UI 层（`.project_memory/active/SPRINT_phase3-eval-system.md`）。后端 W8.1–W8.6 ✓；本 change = **W8 网页验收门槛**。完成后：网页跑通 fixture → grill-me → implement → archive `local-agent-exec-bridge` + `ui-local-exec-bridge` → W7 服务器编排。

## Success Criteria

1. 新用户首次进入见 C16；默认 local；可一键改 sample_io。
2. 设置 Drawer Rescan 列出 claude/codex/cursor-agent PATH 状态；Test 按钮可 smoke。
3. 不配 `.env` EXEC_* 即可 local + consent + 选 agent 跑通 `testskills/exec-fixture-minimal`。
4. BridgePromptCard 在 CLI 就绪后 **同气泡自动变绿**（≤10s）。
5. 报告/历史可见 `execution_source_used` / `spot_check_eligible` 标签；历史筛选可用。
6. `pytest tests/ -q` 全绿（含新 API + UI smoke 契约测试）。

## Impact

| 区域 | 路径 |
|------|------|
| API 路由 | `skillhub_eval/adapters/api/routes/exec.py`（新） |
| 偏好存储 | `skillhub_eval/execution/preferences.py`（新，session 作用域） |
| 引擎接线 | `skillhub_eval/core/execution_source.py`、`engine.py`（读 preferences） |
| UI | `skillhub_eval/adapters/ui/static/index.html` |
| 测试 | `tests/adapters/test_exec_bridge_api.py`、`tests/ui/` 或 JS 契约 stub |
| 文档 | `.env.example` 说明 UI 可覆盖；全景说明 §10 一句 UI 已暴露 |
