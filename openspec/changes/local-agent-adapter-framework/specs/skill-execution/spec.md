# Spec Delta: skill-execution

> 承接已归档 `2026-06-18-local-agent-exec-bridge` 的 skill-execution 能力，新增数据驱动可扩展框架要求。judge 双模式、执行证据、隔离并发、红线加固、降级回退、信任 v1、level 语义等既有要求**不变**。
> grill-me 定稿：trae 走 stream-json（非 ACP）；检测数据驱动；模型发现用通用 `model_probe`。

## ADDED Requirements

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

系统 SHALL 以「通用列模型命令（`model_probe`）+ 内置 fallback + 手动输入」混合提供可选模型，并返回 `models_source ∈ {live, fallback, none}`。声明了 `model_probe` 的 agent SHALL 在超时内运行该命令并解析其输出为模型清单（live）；失败或未声明则用 `fallback_models`。已存储但不在当前清单内的模型 SHALL 被保留并标记 custom/stale，不得静默替换。

#### Scenario: 探测成功用 live

- **Given** 某 agent 声明了 `model_probe`（如 trae `("models",)`）且命令成功返回清单
- **When** `discover_models` 执行
- **Then** 返回解析出的清单且 `models_source=live`

#### Scenario: 探测失败或未声明回退 fallback

- **Given** `model_probe` 未声明、超时或非零退出
- **When** `discover_models` 执行
- **Then** 返回登记表 `fallback_models` 且 `models_source=fallback`

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

## MODIFIED Requirements

### Requirement: 执行来源传输分派

`LocalAgentSource` 获取产出 SHALL 经「按 `AgentDef.stream_format` 的传输分派」：`stream-json` SHALL 复用现有 `LocalAgentRunner`；`acp-json-rpc` SHALL 为受控扩展点（当前抛 `NotImplementedError`，不实现）。claude/codex/cursor-agent 的执行、usage 透传、红线 `HardenedProfile`、降级矩阵与 `ExecResult` 字段 SHALL 保持不变。trae SHALL 作为 stream-json adapter 经同一路径真跑（修正其 bin 名 `trae-cli` 与 stream-json 调用参数后）。

#### Scenario: stream-json agent 行为不回归

- **Given** 选用 claude / codex / cursor-agent 执行某 case
- **When** 引擎经传输分派执行
- **Then** 走 stream-json 传输（现有 runner），产出与本变更前一致

#### Scenario: trae 经 stream-json 真跑

- **Given** 选用 trae 执行某 case
- **When** 引擎经传输分派执行
- **Then** 走 stream-json 传输（`trae-cli -p --output-format stream-json --include-partial-messages --yolo`），产出经现有 judge 出 Pass/Warn/Fail

#### Scenario: ACP 为未实现扩展点

- **Given** 某登记项 `stream_format="acp-json-rpc"`
- **When** 引擎尝试经传输分派执行
- **Then** 系统抛出明确的 `NotImplementedError`（受控扩展点），不静默失败
