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
