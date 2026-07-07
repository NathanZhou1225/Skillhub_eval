# Spec: skill-execution

## Purpose

本地 Skill 执行与回传契约：引擎在 `case_executing` 阶段通过可插拔 `ExecutionSource` 获取 `actual_output`，支持 `sample_io` 与本地 CLI agent 真跑。

完整 W8 执行桥要求见归档 change `openspec/changes/archive/2026-06-18-local-agent-exec-bridge/specs/skill-execution/spec.md`。本节为 W8.7 可扩展 adapter 框架的 normative 增量（2026-06-30 合入 `main`；2026-07-01 补 artifacts 与 Cursor probe hardening）。

## Requirements

### Requirement: 数据驱动的 agent 登记表

系统 SHALL 以声明式登记表描述每个本地 CLI agent，登记项 SHALL 至少包含 `agent_id`、`label`、`primary_bin` + 别名、`config_dirs`、`install_dir_globs`、`stream_format`、`fallback_models`、`model_probe`、`supports_hardened_redline`。新增一个 CLI SHALL 仅需新增一条登记项（含其安装目录与可选列模型命令），无需修改检测、解析或传输代码。

#### Scenario: 新增一个 stream-json CLI

- **Given** 一个新 CLI 使用 stream-json 输出且装在带版本号的目录
- **When** 在登记表新增一条含 `install_dir_globs` 的登记项
- **Then** 该 CLI 可被检测、列模型、选用并经现有 stream-json 路径执行，无需改动检测/传输代码

### Requirement: 数据驱动二进制解析

系统 SHALL 按「`PATH` → 登记的 `install_dir_globs` → npm 目录 → `where`」顺序解析 agent 可执行文件，`install_dir_globs` SHALL 支持版本号通配并在 `LOCALAPPDATA`/`APPDATA`/`HOME` 根下展开，命中多个时取最新。安装位置 SHALL 为登记表数据而非代码特例。

#### Scenario: 解析 PATH 外带版本号安装

- **Given** 某 agent 装在 `%LOCALAPPDATA%\<dir>\bin`（不在 PATH）且登记了对应 `install_dir_globs`
- **When** 系统解析其二进制
- **Then** 通过通配在登记目录下找到可执行文件并返回其绝对路径

#### Scenario: 新 CLI 无需改检测代码

- **Given** 一个新 CLI 装在带版本号子目录
- **When** 仅在登记表添加其 `install_dir_globs`
- **Then** 检测器无需任何代码改动即可解析到它

### Requirement: 三态 agent 检测

系统 SHALL 用「二进制解析 + `config_dirs` 存在性」两路信号产出 `auth_state ∈ {ok, missing, unknown}`：二进制+config 目录→`ok`；有二进制无 config→`missing`；无法廉价判定鉴权的 agent（如 cursor-agent）→`unknown` 并延后到 Test。检测结果 SHALL 进程内缓存（TTL 可配），可强制刷新。

#### Scenario: 二进制与 config 目录均在

- **Given** 某 agent 二进制可解析且其 config 目录存在
- **When** `detect_agent` 执行
- **Then** `detected=true` 且 `auth_state=ok`

#### Scenario: 有二进制无 config 目录

- **Given** 某 agent 二进制可解析但 config 目录不存在
- **When** `detect_agent` 执行
- **Then** `detected=true` 且 `auth_state=missing`

#### Scenario: 未安装返回安装指引

- **Given** 某 agent 二进制无法解析
- **When** `detect_agent` 执行
- **Then** `detected=false`，且 `scan` 为其返回安装命令 + 文档链接

### Requirement: 通用 model_probe 混合发现

系统 SHALL 以「通用列模型命令（`model_probe`）+ 可选 `fallback_model_probes` + 内置 fallback + 手动输入」混合提供可选模型，并返回 `models_source ∈ {live, fallback, none}`。声明了 `model_probe` 的 agent SHALL 在超时内运行该命令并解析其输出为模型清单（live）；若主探测无有效模型，系统 SHALL 依次尝试 `fallback_model_probes`；全部失败或未声明则用 `fallback_models`。已存储但不在当前清单内的模型 SHALL 被保留并标记 custom/stale，不得静默替换。模型解析 SHALL 过滤登录提示、无模型提示、Tip 等非模型状态文本。

#### Scenario: 探测成功用 live

- **Given** 某 agent 声明了 `model_probe`（如 trae `("models",)`）且命令成功返回清单
- **When** `discover_models` 执行
- **Then** 返回解析出的清单且 `models_source=live`

#### Scenario: 探测失败或未声明回退 fallback

- **Given** `model_probe` 未声明、超时或非零退出
- **When** `discover_models` 执行
- **Then** 返回登记表 `fallback_models` 且 `models_source=fallback`

#### Scenario: Cursor 模型探测兼容不同 CLI 版本

- **Given** cursor-agent 登记 `model_probe=("models",)` 且 `fallback_model_probes` 包含 `("--list-models",)`
- **When** `models` 无有效模型但 `--list-models` 返回模型清单
- **Then** `discover_models` 返回 fallback probe 的 live 清单，且不会把登录提示或 "No models available" 当作模型

#### Scenario: 保留自定义模型

- **Given** 存储的 `exec_model` 不在发现清单内
- **When** `discover_models` 执行
- **Then** 该模型仍出现在结果中并标记 custom/stale

### Requirement: 安装指引（不自动安装）

对未检测到的 agent，系统 SHALL 在扫描结果中提供可复制安装命令、官方文档链接与平台备注，并提示安装后「重新扫描」。系统 SHALL NOT 自动执行任何安装脚本。

#### Scenario: 未安装 agent 显示指引

- **Given** 某推荐 agent 未在本机检测到
- **When** 调用 `GET /api/exec/agents/scan`
- **Then** 该 agent 项返回 `install_command`、`install_docs_url`、`install_note`，且系统不执行安装

### Requirement: 执行来源传输分派

`LocalAgentSource` 获取产出 SHALL 经「按 `AgentDef.stream_format` 的传输分派」：`stream-json` SHALL 复用现有 `LocalAgentRunner`；`acp-json-rpc` SHALL 为受控扩展点（当前抛 `NotImplementedError`，不实现）。claude/codex/cursor-agent 的执行、usage 透传、红线 `HardenedProfile`、降级矩阵与 `ExecResult` 字段 SHALL 保持不变。trae SHALL 作为 stream-json adapter 经同一路径真跑（修正其 bin 名 `trae-cli` 与 stream-json 调用参数后）。

正式评估 SHALL 使用全局偏好中的 `exec_agent` 与 `exec_model`（经 `resolve_adapter` 传入各 adapter 的 `--model` 等参数）；agent 连通性 smoke test SHALL 固定使用默认模型，不得误用其他 agent 的 `exec_model`。

本地 agent 执行 SHALL 在每个 case 的隔离 workspace 执行前后做文件指纹快照；新增或修改的小文本文件 SHALL 作为 `actual_output.artifacts[]` 回传（至少包含 `path`、`size_bytes`、`content`）。系统 SHALL 跳过未变化的原始 bundle 文件、常见二进制/缓存文件与过大的文件。若 agent 最终文本包含 structured JSON，artifacts SHALL 与该 JSON 共存而非被丢弃。

#### Scenario: stream-json agent 行为不回归

- **Given** 选用 claude / codex / cursor-agent 执行某 case
- **When** 引擎经传输分派执行
- **Then** 走 stream-json 传输（现有 runner），产出与本变更前一致

#### Scenario: trae 经 stream-json 真跑

- **Given** 选用 trae 执行某 case
- **When** 引擎经传输分派执行
- **Then** 走 stream-json 传输（`trae-cli -p --output-format stream-json --include-partial-messages --yolo`），产出经现有 judge 出 Pass/Warn/Fail

#### Scenario: 正式评估使用所选模型

- **Given** 用户在执行设置中选定 `exec_agent=trae` 且 `exec_model=GLM-5.2`
- **And** 已授予本地执行同意且 bundle `execution_source=local`
- **When** 引擎进入 `case_executing`
- **Then** `LocalAgentSource` 以 `resolve_adapter("trae", model="GLM-5.2")` 启动 agent，并将 `--model GLM-5.2` 传入 CLI

#### Scenario: 工作区产物进入 actual_output

- **Given** 本地 agent 执行某 case 后在 per-case workspace 新增 `report.json`
- **When** `LocalAgentSource` 合成 `ExecResult`
- **Then** `actual_output.artifacts` 包含该文件的相对路径、大小与文本内容

#### Scenario: ACP 为未实现扩展点

- **Given** 某登记项 `stream_format="acp-json-rpc"`
- **When** 引擎尝试经传输分派执行
- **Then** 系统抛出明确的 `NotImplementedError`（受控扩展点），不静默失败

### Requirement: 本地执行失败阻断而非静默回退

本地 agent 执行失败或超时时，系统 SHALL NOT 自动将该 case（或整轮）静默替换为 `sample_io` 产出并以 `status=ok` 继续评分。系统 SHALL 保留原始失败信号（`degrade_reason`，若可得则含 stderr 摘要）并将该 case（或整轮，若 `execution_source=local` 且本机无可用 agent）标记为阻断/未完成，不计入 pass。本条 SHALL 取代已归档 change `2026-06-18-local-agent-exec-bridge` 中「执行降级与回退」要求所述的自动降级为 `sample_io` 的行为——该行为在真机试用中被证实会掩盖本地 agent 从未真正执行成功的事实，且不可追溯失败原因。

#### Scenario: 单题本地执行失败不再静默换成样例

- **Given** 某 case 的本地 agent 执行超时或报错（`status != ok` 或 `actual_output is None`）
- **When** `RoutingExecutionSource` 处理该 case 的执行结果
- **Then** 系统 SHALL NOT 返回一个 `source=sample_io, status=ok` 的替代 `ExecResult`
- **And** 该 case 的 `ExecResult` SHALL 保留原始 `status`、`degrade_reason` 与（若可得）stderr 摘要，供报告与 UI 呈现

#### Scenario: 整轮本地不可用不再整轮回退

- **Given** `execution_source=local` 但本机未检测到可用 agent
- **When** 引擎进入 `case_executing`
- **Then** 系统 SHALL NOT 整轮回退 `SampleIoSource`
- **And** 该轮 SHALL 标记为阻断，并向用户呈现「本地 agent 不可用」而非返回一份看似正常完成的 `level_1` 报告

#### Scenario: 红线题的既定降级不受影响

- **Given** 某红线（refusal/adversarial）case 选用的 agent 不支持加固档（`degrade_reason=redline_no_hardened_profile`）
- **When** `RoutingExecutionSource` 处理该 case 的执行结果
- **Then** 该 case 仍按既有设计降级为 `sample_io` 的 doc-centric 样例模式评分（此为规范既定行为，非执行失败），并在报告标明降级原因
- **And** 该 case 不计入「本地执行失败」的阻断判定

### Requirement: 阻断粒度为按 case，不因单题失败牵连整轮

单个 case 的本地执行失败（非红线既定降级）SHALL 仅将该 case 标记为 `incomplete`，不计入 pass，不影响同轮其他 case 的正常执行与评分。仅当满足以下任一条件时，系统 SHALL 将整轮标记为阻断（复用既有 `RunStatus.failed` 收尾路径与其 `reason_codes`/`evidence` 字段）：`execution_source=local` 且预检未检测到可用 agent；或该轮内声明走本地执行的 case 中，没有任何一个成功产出 `source=local_agent, status=ok` 的结果（即全部本地执行均失败，红线既定降级不计入此统计）。

#### Scenario: 单题失败不牵连整轮

- **Given** 一轮评估声明本地执行，9 道 case 中 1 道因超时/报错本地执行失败，其余 8 道成功
- **When** 引擎完成 `case_executing` 阶段
- **Then** 该轮 SHALL NOT 被标记为阻断，整体继续完成并出具报告
- **And** 失败的那道 case 在报告中标记为 `incomplete`，不计入 pass

#### Scenario: 全部本地执行失败判定整轮阻断

- **Given** 一轮评估声明本地执行，且该轮所有声明本地执行的 case 均执行失败（无一成功产出 `source=local_agent, status=ok`）
- **When** 引擎完成 `case_executing` 阶段
- **Then** 该轮 SHALL 标记为阻断（复用 `RunStatus.failed`），且 `reason_codes` 包含区分性代码（如 `LOCAL_EXEC_ALL_CASES_FAILED`）

### Requirement: 本地执行失败原因持久化可追溯

本地 agent 执行失败时，系统 SHALL 将失败原因（`degrade_reason` 及可得的 stderr 摘要）以事件形式持久化（例如 `token_usage`/`local_agent_failure` 类事件的 payload），供后续排查，不得在处理过程中被丢弃而无法复原。

#### Scenario: 失败原因可在事件日志中查到

- **Given** 一次本地 agent 执行因超时/报错未完成
- **When** 系统记录该 case 的执行结果
- **Then** 该失败的 `degrade_reason`（及可得的 stderr 摘要）SHALL 可通过该轮的事件日志查询到，不依赖重新执行复现

### Requirement: 报告执行归属诚实性

`EvaluationReport` 的 `exec_agent_id`/`exec_agent_label`/`exec_model_id`/`exec_model_label` 字段 SHALL 仅反映真实执行成功的本地 agent/model（即存在至少一个 `ExecResult.source=local_agent` 且执行成功的 case），系统 SHALL NOT 在没有任何 case 真正本地执行成功时，用用户的全局偏好设置（`exec_agent`/`exec_model` 选择）伪装成「已执行」的结果呈现在报告字段中。

#### Scenario: 全部阻断时报告不冒充已执行

- **Given** 一轮评估中所有 case 的本地执行均失败/阻断，没有任何 case 的 `ExecResult.source=local_agent` 成功
- **When** 引擎生成 `EvaluationReport`
- **Then** `exec_agent_label`/`exec_model_label` SHALL NOT 显示用户选择的 agent/model 名称，如同其已成功执行
- **And** 报告 SHALL 清楚呈现「已选择 `<agent>/<model>` 但本次未成功执行」

#### Scenario: 部分成功时报告反映真实来源

- **Given** 一轮评估中至少一个 case 的 `ExecResult.source=local_agent` 成功执行
- **When** 引擎生成 `EvaluationReport`
- **Then** `exec_agent_label`/`exec_model_label` SHALL 取自该成功 `ExecResult` 的 `agent_label`/`model_label`

## Runtime platform（2026-07-07 合入）

以下增量自 OpenSpec change `local-cli-runtime-platform` 同步。用户面向文案使用「本地执行环境检查」；实现与开发者文档仍可使用 preflight/runtime 术语。

### Requirement: 本地 CLI runtime 平台契约

系统 SHALL 将本地 CLI agent 抽象为可复用 runtime，而非由评估引擎直接依赖各 CLI 的启动参数与原始输出格式。每个 runtime SHALL 通过声明式定义描述身份、二进制解析、版本探测、认证/配置探测、模型探测、prompt 传输方式、skill 注入策略、stream 格式、工具能力、preflight 配置、安装/修复指引。系统 SHALL 至少支持 `Codex`、`Cursor Agent`、`Trae`、`Claude`、`Antigravity` 五个 runtime。

runtime definition SHALL 随代码版本化；resolved CLI path、用户选择的 runtime/model、preflight cache SHALL 作为本机用户状态保存在 SQLite，且 SHALL NOT 写回 runtime definition。

### Requirement: 统一 AgentEvent 事件层

系统 SHALL 将各 CLI 原始输出流归一化为内部 `AgentEvent` 流，再由统一逻辑合成 `ParsedStream`/`ExecResult`。完整 live raw stream SHALL 仅保存在 ignored 目录（例如 `.tmp/raw_runtime_streams/`）；仓库内 fixture SHALL 经 sanitizer 脱敏。默认测试套件 SHALL NOT 依赖本机已安装 CLI；live E2E 仅在 `RUN_LOCAL_AGENT=1` 等显式开关下运行。

### Requirement: 正式本地评估必须通过 runtime preflight（本地执行环境检查）

当用户选择本地 CLI runtime 时，系统 SHALL 在正式本地评估开始前检查所选 runtime/model 是否存在有效的 preflight pass（绑定当前 skill fingerprint）。缺失/失败/过期时 SHALL 阻止进入 `case_executing` 并返回 `LOCAL_RUNTIME_PREFLIGHT_REQUIRED`。高风险 bundle 缺少安全 preflight case 时，系统 MAY 自动生成 `runtime_preflight_01`（`type: preflight`），且该 case SHALL 不计入正式 case 数量与 judge 评分。

缓存 SHALL 在 SQLite 中保存 24 小时，并在 runtime id、model id、skill fingerprint、CLI path/version 或 SkillHub version 变化时失效。

### Requirement: 显式 runtime 切换而非自动 fallback

preflight 未通过或 runtime 失败时，系统 SHALL NOT 自动切换 runtime。UI MAY 展示其他已通过检查的 runtime，并通过 `POST /api/exec/runtimes/switch` 等显式操作更新本地偏好后由用户重新发起评估。

### Requirement: 执行来源传输分派（修订）

`LocalAgentSource` 获取产出 SHALL 经 runtime platform 分派；正式执行 SHALL 先经过 runtime readiness 与 preflight 校验。`ExecResult` 仍为评估引擎边界，judge 与评分聚合逻辑不变。
