# Change: local-agent-adapter-framework

> 记录性 change（W8.7 / Q-26）。执行真相以实施计划为准：`docs/superpowers/plans/2026-06-30-local-agent-adapter-framework.md`。设计稿：`docs/superpowers/specs/2026-06-30-local-agent-adapter-framework-design.md`。承接 `2026-06-18-local-agent-exec-bridge`（W8）与 Q-24/Q-25 的 follow-up。
> **grill-me 定稿（2026-06-30）**：原"自制 ACP JSON-RPC 传输"已废弃——实测 `trae-cli` 原生支持与 claude/codex 同形的 `--print --output-format stream-json` 模式，trae 改走现有 stream-json 路径；检测改为数据驱动；模型发现用通用 `model_probe`。锁定决策 G1–G8 见 `design.md`。

## Why

W8 执行层（`skillhub_eval/execution/`）已能跑通 claude/codex/cursor-agent（stdin 投喂 + stream-json 行解析），但还不是 open-design 那样的可扩展框架：

- adapter 逐个写死 `build_args`（`adapters/*.py`），**安装位置也写死在 `cli_detect.py` 里**（只给 codex 写了特例）；每来一个装在 PATH 外/带版本号目录的 CLI 就要改检测代码。实测：trae 因名字错（`traecli` vs 实际 `trae-cli`）+ 装在 `%LOCALAPPDATA%\trae-cli\bin`（不在 PATH）+ 无特例 → 完全检测不到。
- 检测无结构化 `authState`（`scan` 对 cursor 占位 `unknown`）。
- 模型只有静态 `fallback_models`，无「按 CLI 发现模型」（实测 `trae-cli models` 可动态列出）。
- trae 旧 adapter 写的是 `acp serve --yolo` + 错误 bin 名 → 实际跑不起来。

## What Changes

- `AgentDef` 增 `stream_format` / `config_dirs` / `install_dir_globs`（含版本号通配）/ `version_args` / `model_probe` / `prompt_via_stdin`；新增 CLI = 加一条登记数据。
- 新增 `detection`：**数据驱动二进制解析**（`PATH → install_dir_globs → npm → where`，处理 PATH 外/带版本号安装）+ config 目录探测 → 三态 `auth_state`（`ok`/`missing`/`unknown`）+ 进程内 TTL 缓存。
- 新增 `models`：**通用 `model_probe`** 混合发现（声明一条"列模型命令"，trae=`trae-cli models` 动态；其余 fallback + 永远允许手输；custom/stale 保留不被静默替换）。
- 新增 `transport` 分派 seam：按 `stream_format` 选实现。`stream-json` 复用现有 `LocalAgentRunner`；`acp-json-rpc` 为**未来扩展点**（`NotImplementedError`，当前不实现）。
- 修 trae adapter：bin 名 `trae-cli`（别名 `traecli/trae-agent/ta`）+ stream-json build_args（`-p --output-format stream-json --include-partial-messages --yolo`）+ 复用 claude 式解析，使 **trae 经现有 stream-json 路径真跑**。
- 新增 `install_hints`：未检测到的 CLI 在 `scan` 返回安装命令 + 官方链接 + 平台备注（仅指引，不执行安装 — D4）。
- `GET /api/exec/agents/scan` 扩展返回 `auth_status`（真三态）、`models[]` + `models_source`、安装指引字段。
- UI 执行模式抽屉填实：三态徽章、按 CLI 的模型下拉（含自定义输入）、可安装卡片（`[ui-only]`）。
- `local_agent_source._execute_once` 改经 `run_via_transport`（stream-json → 现有 runner）；`ExecResult` 字段、level、usage、红线 `HardenedProfile`、降级矩阵全部不变。

## Non-Goals

- **自制 ACP JSON-RPC 传输**（grill 后废弃：trae 走 stream-json；`acp-json-rpc` 仅留扩展点，不实现）。
- 独立 daemon / web app / session 服务（D1：进程内）。
- 真一键安装 CLI（D4：仅指引）。
- 跨 agent 自动 fallback 链、BYOK 直连 API fallback（D5：失败沿用现状降级，不换 agent）。
- 全量 20+ open-design agent 真跑（按需登记即可）。
- judge 流水线 / 双模型 / 聚合 / R1–R8 决策改动（D6/G8：零改动）。
- W8.4 多 agent 对照统计（独立排期）。

## Relation to SPRINT

阶段三 · Wave 8.7（Q-26），见 `.project_memory/active/SPRINT_phase3-eval-system.md`。承接 `2026-06-18-local-agent-exec-bridge`（W8.1–W8.6，已归档）。受影响代码：`skillhub_eval/execution/`、`skillhub_eval/adapters/api/routes/exec.py`、`skillhub_eval/adapters/ui/static/assets/index.js`、`skillhub_eval/settings.py`。规范文档无字段级改动（执行层内部能力增强）。
