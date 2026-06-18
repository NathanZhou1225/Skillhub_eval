# SkillHub · 本地执行桥 UI 线框与组件清单

> **版本**：v0.1（2026-06-17）  
> **状态**：OpenSpec `openspec/changes/ui-local-exec-bridge/` 已 propose + **grill-me 闭合** → **可 implement**  
> **参考**：Open Design「Execution mode」扫描面板；SkillHub 现有「制式回单」token（`index.html` w5.5-form）  
> **范围**：v1 = Scan + 选 CLI + 模式切换 + Consent + 双轨标签；v1.5 = LUI 引导卡 + 执行摘要；v2 = Live Terminal 流

---

## 1. 设计定位

| 项 | 选择 |
|----|------|
| **受众** | 非技术作者（主）+ 内部评测运营（副） |
| **单页任务** | 在对话评估流程中，**看清**当前是「样例自证」还是「本地真跑」，并完成 **零 .env** 的 CLI 就绪配置 |
| **视觉** | **延续制式回单**（白底、方角、机构蓝 `#0F4C81`、JetBrains Mono 数据区）；执行设置抽屉借鉴 Open Design 的 **Radio Card + Rescan**，但用 **浅色** 而非 Open Design 深色，避免与主界面割裂 |
| **Signature** | 顶栏 **「执行桥状态 pill」**——一眼区分 🔴未就绪 / 🟡待授权 / 🟢已连接 + 当前 agent 名 |

---

## 2. 信息架构（IA）

```text
全局（Header）
├── ExecBridgeIndicator          ← 常驻状态 + 点击打开设置
└── ExecSettingsDrawer           ← Scan / 模式 / Agent / Consent

对话评估 Tab
├── LUI 消息流
│   └── BridgePromptCard         ← local 未就绪时插入（v1.5 可完整自动变绿）
├── chat-status-banner           ← 评估进行中：区分 local vs sample_io 阶段文案
└── rich_report 正式简卡         ← 完成后：执行来源徽章 + level 标签

评估历史 Tab
├── 筛选：执行来源 / 待抽检
└── 行内标签：sample_io | local_agent | mixed

报告弹窗 / trace（增量）
└── per-case 行：ExecCaseBadge + ExecSummaryFold（v1.5）
```

---

## 3. 页面线框

### 3.1 顶栏（改造现有 `<header>`）

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ SKILLHUB │ 对话评估后台          [作者|专家]  [⚙执行设置]  [ExecBridge ●]   │
│                                              Demo  API●  UI-build  刷新     │
└──────────────────────────────────────────────────────────────────────────────┘
                                      ↑
                         ExecBridgeIndicator（新增，在作者/专家左侧或 API 状态旁）
```

**ExecBridgeIndicator 三种态：**

```text
🔴  本地执行：未就绪          （无 CLI on PATH）
🟡  本地执行：待授权          （有 CLI，未 consent 或未选 agent）
🟢  本地执行：cursor-agent    （local 模式 + consent + 已选 agent）
──  样例评估模式              （exec_source=sample_io 时弱化显示，灰字）
```

---

### 3.2 执行设置抽屉（Open Design 式，浅色制式）

触发：`ExecBridgeIndicator` 点击 / 顶栏「⚙ 执行设置」/ LUI 卡片「打开执行设置」

```text
┌─ 执行与 CLI 设置 ───────────────────────────────────────────── [×] ─┐
│                                                                      │
│  ┌─ 评估产出来源 ────────────────────────────────────────────────┐  │
│  │  ○ 样例评估（sample_io）                                       │  │
│  │     读取 Skill 包内预置 sample_io，默认路径                    │  │
│  │  ● 本地真跑（local）                                           │  │
│  │     借本机 CLI Agent 执行 skill 并解析真实产出                 │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  本机 CLI   Scan complete · 2 available          [↻ 重新扫描]       │
│  ─────────────────────────────────────────────────────────────────  │
│  ┌─ Radio Card ─ selected ─────────────────────────────────────┐   │
│  │ ● Cursor Agent          PATH ✓   Auth ?                      │   │
│  │   Cursor 命令行 · model: auto                    [Test]       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ┌─ Radio Card ────────────────────────────────────────────────┐   │
│  │ ○ Claude Code           PATH ✓                               │   │
│  │   stream-json · bypassPermissions                [Test]       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│  ┌─ Radio Card ─ disabled ──────────────────────────────────────┐   │
│  │ ○ Codex                 未安装                                 │   │
│  │   安装后点击重新扫描                                            │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ▼ 可用但未安装（折叠，v1 可选静态文案）                             │
│                                                                      │
│  ┌─ 本地执行授权 ────────────────────────────────────────────────┐  │
│  │  [✓] 我同意 SkillHub 在本机 spawn CLI 执行当前 Skill 脚本     │  │
│  │      执行范围限于 per-run 工作目录；blocked 包不会 spawn。      │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  Skill 包要求（只读提示，有 bundle 时显示）                          │
│  · 本 Skill 要求 execution_source: local                           │
│  · entrypoint: scripts/run.py                                      │
│                                                                      │
│  帮助：若已 npm/brew 安装仍扫不到，请确认 PATH 并 Rescan。           │
└──────────────────────────────────────────────────────────────────────┘
```

**交互：**

- 选模式 / 选 agent / 勾 consent → **即时 PUT**（无「保存」按钮，Open Design 式）
- `[Test]` → POST test spawn（短 prompt，5s 超时，返回 ok/fail 文案）
- `[↻ 重新扫描]` → GET scan，卡片列表刷新 + indicator 同步

---

### 3.3 对话区 — 评估进行中 Banner

改造现有 `#chat-status-banner`：

```text
样例模式：
┌────────────────────────────────────────────────────────┐
│ 评估进行中…（校验样例输出）                             │
└────────────────────────────────────────────────────────┘

本地模式：
┌────────────────────────────────────────────────────────┐
│ 本地 Agent 真跑中…（cursor-agent · h01）    [LOCAL]    │
└────────────────────────────────────────────────────────┘
```

---

### 3.4 LUI — BridgePromptCard（v1：含自动变绿）

插入条件：`exec_source=local` && indicator ≠ 🟢 && 即将/正在 formal_eval

**未就绪态：**

```text
┌─ 系统引导卡（bridge_prompt）─────────────────────────────────┐
│  本地 Agent 尚未就绪                                            │
│  1. 安装 CLI：cursor-agent / claude / codex                     │
│  2. 终端验证：cursor-agent --version              [复制命令]      │
│  3. 打开执行设置 → 选择 Agent → 勾选授权          [打开设置]      │
│  状态：🔴 未检测到 CLI · 正在监听…（每 8s 自动重扫）             │
└─────────────────────────────────────────────────────────────────┘
```

**就绪态（v1 同卡自动变绿，不刷新页）：**

```text
┌─ 系统引导卡（bridge_prompt · ready）───────────────────────────┐
│  ✓ 本地 Agent 已就绪（cursor-agent）                            │
│  将继续正式评估…                                                │
└─────────────────────────────────────────────────────────────────┘
```

**实现要点：**

- 卡片挂载后启动 **scan poll**（8s 间隔，与顶栏 C01 共用同一 scan 结果缓存）
- `ready = detected && consent && selectedAgent` 时，**原地**替换卡片 DOM / 更新 message payload 为 ready 态
- 可选：ready 后 2s 自动折叠卡片或触发「继续评估」提示（不自动重跑整轮，避免重复 spawn）

---

### 3.5 正式简卡（rich_report）— 执行来源区

在现有 `renderReportHtml`  verdict 下方增加 **ExecOutcomeStrip**：

```text
┌─ 正式评估结果 ───────────────────────────────────────────┐
│  [通过]  …现有 verdict…                                   │
│  ─────────────────────────────────────────────────────   │
│  执行来源  [LOCAL AGENT]  level_2  ·  cursor-agent       │
│  待专家抽检  [eligible]  （仅 pass + local 时）            │
│  …现有 score / skill_summary…                             │
└───────────────────────────────────────────────────────────┘
```

---

### 3.6 报告弹窗 — per-case 行（v1.5 ExecSummaryFold）

在 per-case 表增加列/折叠区（**非独立右栏**——当前 UI 无三栏，case 列表在模态内）：

```text
| case_id | 类型   | 执行        | DS | GM | 评分过程 → |
|---------|--------|-------------|----|----|------------|
| h01     | happy  | LOCAL ✓     | 88 | 90 | →          |
|         |        | ▼ 执行摘要  |    |    |            |
|         |        | agent: cursor-agent · 12.3s · ok    |
```

v2 展开为 Terminal 黑框流式 log。

---

### 3.7 历史 Tab — 筛选与列

```text
[全部] [样例评估] [本地真跑] [待专家抽检 ▼]

| run_id | skill | 结论 | 执行来源      | 等级    | 时间 |
|--------|-------|------|---------------|---------|------|
| …      | …     | pass | local_agent   | level_2 | …    |
```

对接已有 API：`?execution_source=local_agent&spot_check_only=true`

---

## 4. 组件清单（Component Inventory）

| ID | 组件名 | 挂载位置 | v1 | 主要状态 | 依赖 API |
|----|--------|----------|-----|----------|----------|
| **C01** | `ExecBridgeIndicator` | Header | ✅ | disconnected / pending_consent / ready / sample_io_mode | `GET /api/exec/agents/scan`, `GET /api/exec/preferences` |
| **C02** | `ExecSettingsDrawer` | 全屏 overlay / 右侧 drawer | ✅ | open / closed | C03–C07 |
| **C03** | `ExecModeRadioGroup` | Drawer §1 | ✅ | sample_io \| local | `PUT /api/exec/preferences` `{ exec_source }` |
| **C04** | `ExecAgentScanHeader` | Drawer §2 顶 | ✅ | scanning / complete / error | `GET /api/exec/agents/scan` |
| **C05** | `ExecAgentRadioCard` | Drawer §2 列表 | ✅ | selected, detected, undetected, auth_unknown, auth_ok | scan + `PUT preferences` `{ exec_agent }` |
| **C06** | `ExecAgentTestButton` | Card 内 | ✅ | idle / testing / pass / fail | `POST /api/exec/agents/{id}/test` |
| **C07** | `ExecConsentCheckbox` | Drawer §3 | ✅ | unchecked / checked | `POST /api/exec/consent` `{ skill_id? }` |
| **C08** | `ExecSkillHintBlock` | Drawer 底部 | ✅ | hidden / readonly hints | 当前 conversation bundle meta（ingest 摘要或 bootstrap payload） |
| **C09** | `ExecRunningBanner` | `#chat-status-banner` | ✅ | sample_io_running / local_running | run status poll + preferences |
| **C10** | `ExecOutcomeStrip` | rich_report / 报告模态 | ✅ | sample_io / local / mixed + level + spot_check | report JSON 字段 |
| **C11** | `BridgePromptCard` | LUI message / gate 前 | ✅ | blocked → **ready（v1 轮询自动变绿）** | scan poll（5–10s）+ preferences |
| **C12** | `ExecCaseBadge` | per-case 表 | v1.5 | LOCAL / SAMPLE / incomplete | report per-case exec 摘要（需后端字段） |
| **C13** | `ExecSummaryFold` | per-case 折叠 | v1.5 | collapsed / expanded | `GET .../exec-summary` 或 report 内嵌 |
| **C14** | `ExecLiveTerminal` | per-case 折叠内 | v2 | streaming / done | SSE 或 stage metadata log |
| **C15** | `HistoryExecFilterChips` | 历史 Tab 顶 | ✅ | all / sample_io / local / spot_check | `GET /api/eval/history?...` |
| **C16** | `LocalNotReadyOnboarding` | local 且未就绪时顶栏 Banner | ✅ | visible / session-dismissed / resolved | preferences `ready` + `exec_source`（**非** localStorage 永久 dismiss） |

---

## 4b. C16 本地未就绪提示（grill G11=C 已锁定）

**每次打开评估页**，当 `exec_source=local` 且 `ready=false` 时，顶部展示 **非阻塞 Banner**：

```text
┌─ 欢迎使用 SkillHub 评估 ─────────────────────────────────── [知道了] ─┐
│  默认使用本地 Agent CLI 真跑测试 Skill；需先配置本机 CLI 并授权。         │
│  可选：在「执行设置」中切换为「样例评估（sample_io）」— 读取包内预置输出评分。│
│                                              [打开执行设置]  [改用样例评估] │
└──────────────────────────────────────────────────────────────────────────┘
```

**定稿文案（C16）：**

> 默认使用**本地 Agent CLI** 真跑测试 Skill；请先在「执行设置」中配置 CLI 并授权。  
> **可选**：切换为**样例评估（sample_io）**— 读取 Skill 包内预置 sample_io 输出进行评分。

- **默认 `exec_source=local`**（sqlite 全局 preferences 初始值 + UI 一致）
- 「改用样例评估」→ 一键 PUT `sample_io` + 关闭提示 + indicator 切为样例模式
- 「知道了」→ **仅收起当次浏览**；下次开页若仍 `local && !ready` **再次显示**
- CLI 配置完成且 `ready=true` → Banner **自动消失**
- 设置内可「重新查看说明」手动展开（可选 v1）

---

## 5. 组件规格摘要

### C01 ExecBridgeIndicator

```yaml
props:
  execSource: 'sample_io' | 'local'
  scanState: 'idle' | 'scanning' | 'error'
  agentsAvailable: number
  selectedAgentId: string | null
  consentGranted: boolean
  ready: boolean  # local 模式下的综合就绪
events:
  onClick: open C02
copy:
  sample_io_mode: "评估模式：样例自证"
  disconnected: "本地执行：未就绪"
  pending: "本地执行：待授权"
  ready: "本地执行：{agentLabel}"
```

### C05 ExecAgentRadioCard

```yaml
props:
  agentId: 'claude' | 'codex' | 'cursor-agent'
  label: string
  subtitle: string
  detected: boolean
  authStatus: 'unknown' | 'ok' | 'fail' | null
  selected: boolean
  modelHint: string | null   # v1 可固定 "auto" / built-in
actions:
  select: PUT preferences
  test: POST .../test
visual:
  selected: 左边框 brand-600 + 浅蓝底
  undetected: opacity-50, radio disabled
```

### C07 ExecConsentCheckbox

```yaml
copy_zh: |
  我同意 SkillHub 在本机 spawn CLI 执行当前 Skill 脚本。
  执行范围限于 per-run 工作目录；安全拦截的包不会 spawn。
behavior:
  onCheck: POST consent (global session; optional skill_id when known)
  localModeOnly: true  # sample_io 模式下隐藏或 disabled
```

### C09 ExecRunningBanner

```yaml
replace STAGE_ZH.case_executing:
  sample_io: "校验样例输出"
  local: "本地 Agent 真跑中"
suffix: "（{agentId} · {currentCaseId?}）"
badge: "[LOCAL]"  # mono pill, brand 色系
```

### C10 ExecOutcomeStrip

```yaml
fields from report:
  - execution_source_used
  - level_achieved
  - spot_check_eligible
badges:
  LOCAL AGENT: green outline
  SAMPLE IO: gray outline
  level_2: brand
  spot_check eligible: amber
```

### C11 BridgePromptCard

```yaml
states: blocked | ready
poll:
  interval_ms: 8000
  sharedWith: C01  # 同一 scan 缓存，避免重复请求
  stopWhen: ready || user_switches_to_sample_io
readyCondition:
  exec_source: local
  agent_detected: true
  consent_granted: true
  selected_agent: not null
dom:
  inPlaceUpdate: true   # v1 必须：同气泡变绿，不 refresh 消息列表
copy_blocked: 见 §3.4
copy_ready: "✓ 本地 Agent 已就绪（{agentLabel}）"
```

---

## 6. 与现有 UI 的挂载点

| 现有 DOM / 函数 | 改造 |
|-----------------|------|
| `<header>` L85–100 | 插入 C01 + `btn-exec-settings` |
| `#chat-status-banner` | C09 文案分支 |
| `STAGE_ZH` / `activityPhaseLabel` | local 分支文案 |
| `renderReportHtml` | 底部 C10 |
| message type 渲染（`rich_report` 等） | v1 增 `bridge_prompt` → C11（含 poll 自动变绿） |
| 历史 Tab 列表渲染 | C15 + 列 `execution_source_used` |
| `renderModelVotesFeedback` per-case 表 | v1.5 C12/C13 |

**不新增三栏布局**（v1）：Open Design 右侧 case 跑马灯 **映射到** banner + 报告模态 per-case，降低布局风险。

---

## 7. 后端 API 最小集（供 OpenSpec 引用，非 UI 文档正文）

| Method | Path | 用途 |
|--------|------|------|
| GET | `/api/exec/agents/scan` | 三 adapter detect + 可选 auth 探测 |
| GET | `/api/exec/preferences` | `{ exec_source, exec_agent, consent_granted }` |
| PUT | `/api/exec/preferences` | 更新 source/agent |
| POST | `/api/exec/consent` | `{ skill_id?: string }` grant |
| POST | `/api/exec/agents/{id}/test` | 短跑 smoke（**v1 必做** — 连接测试） |

优先级：**scan + preferences + consent** 为 v1 阻塞项；test 与 per-case 摘要为增强。

---

## 8. v1 / v1.5 / v2 切分（确认用）

| 里程碑 | 组件 | 验收 |
|--------|------|------|
| **v1** | C01–C11（**C11 含 8s poll 自动变绿 + 自动续跑**）, C15–C16 + 4 API（含 test）+ 正式评估门禁 + 冲突 Modal | 默认 local + C16 未就绪反复提示 + fixture 网页验收 |
| **v1.5** | C12–C13 + report per-case 摘要 | case 级执行摘要折叠 |
| **v2** | C14 + SSE/log 持久化 | Terminal 流式 log |

---

## 9. 已锁定决策（2026-06-17，终稿）

| # | 议题 | 决定 |
|---|------|------|
| 1 | Drawer vs Modal | ✅ **右侧 Drawer 420px** |
| 2 | Consent + 设置持久化 | ✅ **sqlite 全局单行**；consent 勾选后跨 serve 重启仍有效（grill G1） |
| 3 | 默认模式 + C16 | ✅ **默认 local**；**C16**：`local && !ready` 时**每次开页显示**，直到改用样例或 CLI 就绪（grill G11=C） |
| 4 | Test 按钮 | ✅ **v1 必做**；**无需 consent** 也可 Test（grill G3） |
| 5 | BridgePromptCard | ✅ **纯前端**；8s poll 自动变绿 + **自动续跑**正式评估（grill G2/G6） |
| 6 | 正式评估门禁 | ✅ local 未就绪 **拦截**（grill G4） |
| 7 | Skill vs UI 冲突 | ✅ bundle 要求 local 但 prefs=sample → **居中 Modal** 确认（grill G5/G10） |
| 8 | 设置权限 | ✅ **作者+专家** 均可改（grill G8） |
| 9 | 样例模式 UX | ✅ **安静评估** + 顶栏灰字轻提示（grill G9） |
| 10 | 设置作用域 | ✅ **整台电脑一份**（grill G7） |

### Consent + preferences（grill 后）

勾选「我同意本机执行」→ 写入 sqlite 全局 preferences；重启 `skillhub-eval serve` 后仍记得。非「每 Skill 一次」。

### C16 反复提示（grill G11=C）

`local && !ready` → 每次开页见 Banner；「知道了」仅收起当次；改用样例或 `ready=true` 后不再自动弹出。

### BridgePromptCard 自动变绿（v1 范围）

local 未就绪时插入引导卡 → 后台每 8s 与顶栏共用 scan → CLI + consent + agent 齐备后**同一条聊天气泡**变绿「已就绪」，并**自动续跑**被拦的正式评估。

---

## 10. 下一步

1. ~~确认 §9~~ ✅ 已锁定  
2. ~~`/opsx:propose "ui-local-exec-bridge"`~~ ✅  
3. ~~grill-me~~ ✅（G1–G11 已写入 OpenSpec）  
4. **实现** → 网页验收 → archive `local-agent-exec-bridge` + `ui-local-exec-bridge`
