# Design: ui-local-exec-bridge

> 组件 ID、线框 ASCII、锁定决策见 `docs/superpowers/specs/2026-06-17-ui-local-exec-bridge-wireframes.md` §9 终稿。

## Context

- **后端**：`local-agent-exec-bridge` 已实现 `LocalAgentSource`、三 adapter（`detect()` = `shutil.which`）、`consent.py`（进程内 set）、`RoutingExecutionSource`、history 字段 `spot_check_eligible` / `execution_source_used`。
- **前端**：单文件 `index.html`（制式回单 token，w5.5-form）；无 Settings 页；`STAGE_ZH.case_executing` =「运行样例题」。
- **约束**：integrated-ai-workflow — UI 视觉在 `index.html`；本 change **允许** 最小 API + preferences 模块（非纯 ui-only）；eval 核心逻辑除 preferences 读取点外不动。

## Goals / Non-Goals

**Goals:**

- 网页完成 **Scan → 选 CLI → local/sample_io 切换 → Session consent → Test** 闭环。
- 默认 **`exec_source=local`**；C16 **local 未就绪时每次开页提示** + 可选 sample_io。
- C11 **BridgePromptCard v1 含 8s poll 自动变绿**（与 C01 共用 scan 缓存）。
- 双轨可感知：Banner / 报告 / 历史标签。

**Non-Goals:**

- SSE Terminal（v2）；per-case 摘要（v1.5）；独立 bridge daemon；Python/venv 选择卡片。

## Visual direction（frontend-design）

| Token | 值 | 用途 |
|-------|-----|------|
| 背景 | `#E9EDF1` / `white` | 页 / 卡片（延续现有） |
| 品牌 | `#0F4C81` | 选中 Radio Card 左边框、primary 按钮 |
| 字体 | Noto Sans SC + Archivo display + JetBrains Mono | 正文 / 标题 / scan 数据 |
| 圆角 | `2px` 方角 | 与 w5.5 制式一致 |
| Signature | **ExecBridgeIndicator** pill | 顶栏常驻，🔴🟡🟢 + agent 名 |

**Drawer**：右侧 420px，白底，`border-l-2 border-gray-900`，overlay `bg-black/20`。Radio Card：选中 = 左 3px brand 条 + `bg-blue-50`；未检测到 = `opacity-50` + disabled radio。

**C16 Banner**：`bg-blue-50 border-b-2 border-blue-600`，非 modal，不挡 Composer。

**BridgePromptCard**：聊天气泡内嵌，blocked = 左侧 amber 条；ready = 左侧 green 条 + ✓，**in-place** 替换 `.bridge-prompt-body` DOM。

## Decisions

| # | 决策 | 理由 | 排除 |
|---|------|------|------|
| D1 | **全局 preferences 持久化 sqlite**（单行 `exec_preferences`，跨 serve 重启） | 用户 grill B；整台电脑一份 | 仅内存 session |
| D2 | preferences **优先于** env | UI 为零配置入口 | env 优先 |
| D3 | 默认 `exec_source=local` | 产品方向；C16 兜底 | 默认 sample_io |
| D4 | Consent **Session 级** + **持久化进全局 preferences** | 勾一次；重启仍记得（grill B） | 每 Skill 一次 |
| D5 | Scan 复用 adapter detect + 可选 cursor auth 探测 | 与 runner 一致 | 前端 exec |
| D6 | Test：5s smoke；**未 consent 也可 Test**（grill A） | 先测连通再同意 | Test 需 consent |
| D7 | Poll 8s，C01/C11 共享 scan 缓存 | 减请求 | 独立 poll |
| D8 | BridgePromptCard **纯前端**（grill A），不写 DB | 实现快 | 写 lui_messages |
| D9 | 历史筛选复用现有 API | W8 已有 | 新 DB 列 |
| D10 | **local 未就绪则拦正式评估**（grill A） | 避免假「已真跑」 | 静默降级 sample_io |
| D11 | **就绪变绿后自动续跑**被拦的正式评估（grill A） | 对齐 W5 自动正式评 | 手动再点 |
| D12 | **全局设置整台电脑一份**（grill A） | Demo 单人本机 | 每浏览器/账号 |
| D13 | **作者+专家均可改**全局设置（grill A） | 简化 | 专家只读 |
| D14 | **样例模式安静+顶栏灰字轻提示**（grill B） | 不 nag 配 CLI | 完全隐藏 / 全 nag |
| D15 | Skill 要求 local 但用户选 sample → **开评前 Modal 确认**（grill C+A） | 防误用 | 听包 / 听 UI |
| D16 | **C16 横幅**：local 且未就绪时**每次开页都显示**，直到「改用样例」或 CLI 就绪变绿（grill C）；「知道了」仅收起当次浏览，不永久关闭 | 强提醒配环境 | localStorage 永久 dismiss |

### API 形状（锁定）

```text
GET  /api/exec/agents/scan
→ { scanned_at, agents: [{ id, label, detected, auth_status, model_hint }] }

GET  /api/exec/preferences
→ { exec_source, exec_agent, consent_granted, ready, ready_reason? }

PUT  /api/exec/preferences
← { exec_source?, exec_agent? }
→ 同上

POST /api/exec/consent
→ { granted: true }

POST /api/exec/agents/{id}/test
→ { ok, message, duration_ms? }
```

`ready` = `exec_source!=local` OR (`detected(selected)` AND `consent_granted` AND `selected_agent` set).

### 引擎接线

```python
# execution/preferences.py
def get_exec_source() -> str:  # preferences > settings.exec_source
def get_exec_agent() -> str:   # preferences > settings.exec_agent
```

`RoutingExecutionSource` / `LocalAgentSource` 经 `settings` 或显式 inject 读 preferences。

## Risks / Trade-offs

| 风险 | 缓解 |
|------|------|
| 默认 local 无 CLI 导致评失败 | C16 + C11 + 顶栏 🔴 + 降级 sample_io 按钮 |
| Session preferences 重启 serve 丢失 | Demo 可接受；文档说明 |
| poll 频繁 scan | 8s + 共享缓存；scan 仅 which/status 无 spawn |
| Test 误触发真实 agent 调用 | 极短 prompt + 5s cap + 明确「连接测试」文案 |
| index.html 体积膨胀 | 组件函数分区 + 注释 C01–C16 |

## Migration Plan

1. 部署 API + preferences（默认 local 不改变 env 文件）。
2. UI 上线；旧用户 `.env` 仍作 fallback（preferences 未设时）。
3. 验收 fixture → archive 两 change。
4. Rollback：preferences 默认改 sample_io 或 UI feature flag（可选 `SKILLHUB_EXEC_UI=0`）。

## Open Questions（grill-me 2026-06-17 已闭合）

| # | 决议 |
|---|------|
| 1 | preferences **sqlite 持久化**，跨 serve 重启（**B**） |
| 2 | bridge_prompt **纯前端**，不写 DB（**A**） |
| 3 | Test **无需 consent**（**A**） |
| 4 | local 未就绪 **拦正式评估**（**A**） |
| 5 | Skill 要求 local + 用户选 sample → **Modal 确认**（**C** + **A**） |
| 6 | 引导卡变绿后 **自动续跑**正式评估（**A**） |
| 7 | 设置 **整台电脑一份**（**A**） |
| 8 | **作者+专家** 均可改设置（**A**） |
| 9 | 样例模式 **顶栏灰字轻提示**，不 nag（**B**） |
| 10 | 冲突确认用 **居中 Modal**（**A**） |
| 11 | C16：**每次开页显示**（local 且未就绪），直到改用样例或 CLI 就绪；「知道了」不永久关闭（**C**） |
