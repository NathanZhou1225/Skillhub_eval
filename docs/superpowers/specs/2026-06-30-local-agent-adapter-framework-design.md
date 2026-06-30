# 本地 Agent 可扩展 adapter 框架 — 设计稿（W8.7 / Q-26）

> 日期：2026-06-30
> 状态：Brainstorm 定稿，待用户复核
> 范围：阶段三 · 评估系统 · 把"逐个写死 build_args"的执行层升级为 open-design 风格的可扩展 adapter 框架
> 设计依据：`nexu-io/open-design`（`docs/agent-adapters.md`、`docs/architecture.md`、`docs/new-agent-runtime-acp.md`）
> 上游：`docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md`（W8）、`docs/superpowers/specs/2026-06-24-q24-q25-local-agent-usage-design.md`（Q-24/Q-25，本稿承接其 follow-up）
> 相关：`RECORD.md` Q-26、`.project_memory/active/SPRINT_phase3-eval-system.md` W8.7

---

## 0. 一句话目标

把 SkillHub 评估的"本地 agent 穿透"做到 **open-design 同等丝滑**：注册一条即新增一个 CLI；启动能**三态检测**本机 CLI（可用 / 未登录 / 未安装）；**按 CLI 列出可选模型**让用户挑；并补上 **trae 的 ACP 传输**让它真能跑。所有能力塞进 SkillHub 现有后台，不新增独立 daemon。

## 1. 背景与现状差距

当前执行层（`skillhub_eval/execution/`）能跑通 claude/codex/cursor-agent（stdin 投喂 + stream-json 行解析），但：

- adapter 是**逐个写死 `build_args`**（`adapters/*.py`），不是数据驱动的可扩展框架。
- 检测仅 PATH（`cli_detect.py`），无 config 目录探测，无结构化 `authState`（`scan` 仅 cursor 占位 `unknown`）。
- 模型只有静态 `fallback_models`，无"按 CLI 发现模型"。
- **trae / antigravity 只声明 `build_args` + `detect`，没有对应传输层 → 实际跑不起来**（trae 需要 ACP JSON-RPC 双向握手，runner 只会单次 stdin→stdout）。

本稿即 Q-24/Q-25 设计文档结尾列出的 follow-up（"full Open Design adapter-layer migration / generic ACP transport / richer auth diagnostics / model discovery"）的落地。

## 2. 取 / 舍（只要评估用得到的）

**取（open-design 框架层）**：声明式 runtime 登记表、PATH + config-dir 检测与 authState、模型混合发现、按 `streamFormat` 复用的传输（stream-json + ACP JSON-RPC）、归一化事件、可安装发现列表。

**舍（评估用不到，YAGNI）**：独立 daemon / web app / session 服务、`DESIGN.md` 设计系统、预览 iframe / comment / slider、导出（PDF/PPTX/MP4）、插件市场、BYOK 直连 API fallback、surgical edit / 多轮 resume、跨 agent 自动 fallback 链、真一键安装 CLI。

## 3. 已锁定决策（brainstorm 2026-06-30）

| # | 决策 | 取舍 |
|---|------|------|
| D1 | **进程内框架，不开独立 daemon** | 排除独立 agent 服务（SkillHub 已有后台 + 引擎；daemon 多一套维护与版本对齐成本，目前无第三方复用需求） |
| D2 | **首批一等公民：codex / cursor-agent / trae 全部真跑**；trae 补 ACP；其余 CLI 仅登记 + 安装指引 | 排除"先只做 codex/cursor、trae 后置"（用户要一次打通）；排除全量 20+ agent 真跑（YAGNI） |
| D3 | **模型混合发现**：能探测就探测 + 内置 fallback 清单 + 永远允许手动输入 | 排除纯静态清单（新模型进不来）；排除纯动态（很多 CLI 拿不到，体验不稳） |
| D4 | **"可安装"= 仅指引**：列推荐 CLI + 可复制安装命令/官方链接 + 装完"重新扫描" | 排除真一键安装（每 CLI 装法不同、跨平台、装后仍需登录、在后台执行安装脚本有安全/维护风险）；排除完全隐藏可安装列表（丢失发现感） |
| D5 | **失败降级沿用现状**：选定 agent 未登录/超时/跑挂 → 回退 sample_io 或标 incomplete，并显示原因；**不**自动切别的 agent | 排除跨 agent 自动 fallback（评估要可追溯，换 agent 会让结果对不上） |
| D6 | **judge 流水线零改动、现有测试不回归** | 传输层不同 CLI 最终都吐成同一个 `ExecResult`，引擎/断言/双模型/聚合/决策完全不动 |

## 4. 架构概览（进程内）

```
评估引擎 core/engine.py（不变）
  └─ case_executing 经 ExecutionSource 取 actual_output（不变）
        └─ LocalAgentSource（执行层入口，瘦身：只编排，不写死 CLI）
              ├─ AgentRegistry        ← 声明式 RuntimeAgentDef 登记表（数据）
              ├─ Detection            ← PATH + config-dir 探测 → DetectionResult(authState)
              ├─ ModelDiscovery       ← live 探测 + fallback + 自定义
              └─ TransportDispatcher  ← 按 def.stream_format 选传输
                    ├─ StreamJsonTransport（现成：claude/codex/cursor）
                    └─ AcpTransport（新造：trae，JSON-RPC over stdio）
                          ↓ 两条传输都产出统一 ParsedRun
              └─ collect → ExecResult（actual_output/usage/level/...，结构不变）
```

关键原则：**adapter 退化为"数据 + 一个 build_args 函数"**，真正干活的"翻译器"按 `stream_format` 共享。新增一个走 stream-json 或 ACP 的 CLI = 加一条登记，不写新代码。

## 5. 模块设计

### 5.1 登记表 `execution/agent_registry.py`（演进现有 `AgentDef`）

`RuntimeAgentDef` 字段（对齐 open-design `RuntimeAgentDef`）：

- `agent_id`、`label`、`aliases`
- `primary_bin` + `binary_aliases`（检测用）
- `config_dirs: tuple[str, ...]`（如 `~/.codex`、`~/.cursor`、`~/.trae`，用于 config-dir 探测；相对 `USERPROFILE`/`HOME`）
- `stream_format: "stream-json" | "acp-json-rpc"`
- `build_args(cwd, hardened, model) -> list[str]`（保留每 CLI 差异，如 codex 加固档、cursor `--workspace`、trae `acp serve --yolo`）
- `prompt_via_stdin: bool`（默认 True）
- `fallback_models: tuple[ModelOption, ...]`
- `model_probe: ModelProbeSpec | None`（见 5.3）
- `supports_hardened_redline: bool`
- `install_hint: InstallHint`（命令 + 官方链接 + 平台备注，见 5.2）
- `version_args: tuple[str, ...]`（默认 `("--version",)`，检测/诊断用）

`get_agent_catalog()` / `get_agent_def()` 保持现有签名；`resolve_adapter()` 改为返回"def + 选定 transport"组合，而非具体 Adapter 类。

### 5.2 检测 `execution/detection.py`（新增，吸收 `cli_detect.py`）

`detect_agent(def) -> DetectionResult`：

- **两路信号**：① PATH/well-known 二进制解析（复用现有 `find_cli_binary`）；② `config_dirs` 任一存在。
- `auth_state: "ok" | "missing" | "unknown"`：
  - 二进制 + config 目录都在 → 倾向 `ok`（除非该 def 声明了便宜的鉴权探针）。
  - 只有二进制、无 config 目录 → `missing`（提示去登录）。
  - 无法判定（如 cursor `auth status` 在 Windows 可能挂）→ `unknown`，鉴权判定**延后到 Test**（沿用现状）。
- 结果**缓存**（进程内 + TTL，默认 24h，可被"重新扫描"强制刷新），避免每次 scan 重复探测。

`InstallHint`（D4）：`install_command`（可复制，如 `npm i -g @openai/codex`）、`docs_url`、`platform_note`。检测为 `missing/未安装` 时，`scan` 返回这些字段供"可安装"卡片展示。**不执行安装**。

### 5.3 模型发现 `execution/models.py`（新增，D3 混合）

`discover_models(def, *, timeout_s) -> ModelDiscovery`，返回 `models[]` + `models_source: "live" | "fallback" | "none"`：

- **live**：当 `def.model_probe` 存在且能在超时内拿到清单：
  - stream-json 系：若该 CLI 有列模型命令（如有）则解析其输出；拿不到则跳过。
  - ACP 系（trae）：在一次短超时的 `initialize` + `session/new` 握手里读 `session/new` 响应报告的模型 / model config options（见 5.4）。
- **fallback**：探测失败 → 用 `def.fallback_models`。
- **custom**：UI 永远允许手动输入；存储的 `exec_model` 若不在当前清单，**保留并标记为 custom/stale**，不静默替换（沿用 Q-24 既定行为）。

### 5.4 传输层 `execution/transport/`（新增包）

统一接口 `Transport.run(def, prompt, *, cwd, model, timeout_s, hardened) -> ParsedRun`，`ParsedRun` = 现 `ParsedStream` 超集（`final_text` / `tool_results` / `usage` / `duration_ms` / `is_complete`）。

- **`stream_json.py`**：把现有 `runner.LocalAgentRunner` + `stream_parser.parse_stream_events` 收敛进来（claude/codex/cursor）。行为不变（stdin 投 prompt、stdout 读 JSONL、`result`/`turn.completed` 判完成）。cursor 的文本去重（`_emit_cursor_text_delta`）作为该格式下的可选 per-def 解析钩子保留。
- **`acp.py`（新造，trae）**：JSON-RPC 2.0 over stdio 的会话驱动，方法序列对齐 open-design `new-agent-runtime-acp.md`：
  1. `initialize`（client metadata + clientCapabilities）
  2. `session/new`（含 `cwd`；读取响应里的 `sessionId` 与可选模型/`model config options`）
  3. 选了非默认模型 → `session/set_config_option`（优先，若 `session/new` 报告了该选项）否则 `session/set_model`
  4. `session/prompt`（投 harness prompt；其响应 = 本轮完成 + usage）
  5. 取消/超时 → `session/cancel`，不可用时回退进程终止（`SIGTERM` + 宽限）
  - 通知映射：`session/update` 的 `agent_message_chunk` → 文本；`agent_thought_chunk` → thinking（评估只需最终文本，可丢弃）；`session/request_permission` → 自动选 approve/allow，无可接受项则快速失败。
  - 实现为**纯 stdio JSON-RPC 客户端**（按行读写、id 配对、读 `stderr` 仅日志）。
  - trae `build_args = ["acp", "serve", "--yolo"]`（沿用现有 def，`--yolo` 免交互审批）。

`TransportDispatcher` 按 `def.stream_format` 选实现。`runner.py` 现有 `LocalAgentRunner` 保留为 stream-json 传输的底层 spawn 工具，被 `stream_json.py` 复用。

### 5.5 执行入口 `execution/local_agent_source.py`（瘦身）

- `get_actual_output(...)` 流程不变（consent gate → 解析 def → detect → 红线加固判定 → 有界并发 → 重试/退避 → `collect_actual_output` → sanitizer → `ExecResult`）。
- 唯一变化：拿 transport 的方式从"具体 Adapter 类"改为"`def` + `TransportDispatcher`"。`ExecResult` 字段、level 判定、usage 透传、red-line `HardenedProfile` 全部不变（D6）。
- 降级矩阵不变（D5）。

### 5.6 引擎与 UI 接缝（D6，尽量零改动）

- **引擎**：`core/engine.py` / `ExecutionSource` / judge / 断言 / 聚合 / 决策**不改**。
- **API**：`adapters/api/routes/exec.py` 的 `GET /agents/scan` 扩展返回：`auth_state`（三态可读）、`models[]` + `models_source`、`install_hint`（未装时）；`PUT /preferences`、`POST /agents/{id}/test`、`POST /consent` 不变。
- **UI**：`adapters/ui/static/assets/index.js` 的执行模式抽屉**已有壳**（你的 CLI / 已安装 / 模型下拉 / 可安装列表 / 重新扫描 / Test，见现状截图）。本次只把数据填实：三态灯、按 CLI 的模型下拉（含 custom 输入）、可安装卡片显示安装命令+链接（D4）。`[ui-only]` 视觉走 `frontend-design`，不改评估逻辑。

## 6. 数据 / 契约变更

- `RuntimeAgentDef` 新增字段（5.1）。
- `scan` 响应新增 `auth_state` 取值规范、`install_hint`；`models_source` 沿用 Q-24 的 `live|fallback|none`。
- `.env` / `settings.py`：ACP 握手短探测超时（如 `ACP_PROBE_TIMEOUT_S`）、模型发现超时（`MODEL_DISCOVERY_TIMEOUT_S`）、检测缓存 TTL（`AGENT_DETECT_CACHE_TTL_S`）。沿用现有 `LOCAL_AGENT_*` 超时，不改语义。
- DB：无新增表（执行偏好 `exec_*` 已有）。

## 7. 测试（放最后）

框架可脱离真 CLI 测：

- 登记表解析 / 别名 / build_args（含 trae `acp serve --yolo`、codex 加固档）。
- 检测三态：mock PATH + config 目录组合 → `ok/missing/unknown`；缓存 TTL 与强制刷新。
- 模型发现：live 成功 / 超时回退 fallback / 未知 CLI → none / custom 保留。
- **ACP 传输**：用**录制的 JSON-RPC 握手回放**（fake stdio）驱动 `acp.py`，断言方法序列、`session/update` → 文本、`request_permission` 自动批准、`session/prompt` 完成与 usage、取消路径。
- stream-json 传输回归：复用现有 fake 进程用例，确认行为不变。
- `scan` API 返回新字段；偏好读写。
- 真机冒烟（`requires_local_agent`，默认 skip）：codex / cursor / trae 各跑一次。

全量 pytest 与 W5.5 剧本 B/C 验收**沿用阶段三既定后置**，框架落地后统一补。

## 8. 不做 / 后续

- 全量 20+ open-design agent 真跑（按需登记即可，不预先做传输）。
- 跨 agent 自动 fallback 链、BYOK 直连 API fallback。
- Windows 命令行长度预算守卫（走 stdin 已基本规避；如遇 trae/未来 CLI 命中再补）。
- 独立 daemon / 第三方复用（若将来需要再升级为 D1 的 B 方案）。
- W8.4 多 agent 对照统计（独立排期）。

## 9. 验收口径

- 执行模式界面：扫描后 codex/cursor/trae 显示**正确三态**；选中任一可见**其模型下拉 + 手动输入**；未装 CLI 显示**安装命令/链接**且"重新扫描"能在装好后认出。
- **trae 经 ACP 真跑通**一个 fixture skill，产出经现有 judge 出 Pass/Warn/Fail。
- codex/cursor 行为与现状一致，现有执行/usage/红线逻辑不回归。
- 新增 CLI 仅需在登记表加一条（走 stream-json 或 acp-json-rpc）即可被检测与选用。
