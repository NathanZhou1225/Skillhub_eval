# Change: local-agent-exec-bridge

> 2026-06-17 grill 修订：回传契约由「MCP submit 工具」改为「stream-json 流解析」（open-design 实测仅 claude 有 MCP 注入）；judge 新增执行模式 prompt；新增 `entrypoint`/`execution_source` 元数据；红线题分加固档/降级。详见 `docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md` §0。

## Why

当前评估在 `case_executing` 阶段不真跑 skill：`skillhub_eval/core/engine.py` 直接 `load_sample_io(skill_bundle_path, case_id)` 读取作者预放的 `sample_io/{case}.json` 作为 `actual_output`（engine.py:313/330/1010）。后果：

- 原计划的中台 subprocess 沙盒（W8 Level 2）**结构上跑不了内网 skill**（中台无 VPN/DB/Token），而内网 skill 恰恰最需要真跑。
- 评的是「材料是否自洽」，不是「真实使用时能否跑通」。

本变更把「真实执行」下放到开发者本地已配好的 CLI agent（claude / codex / cursor-agent），由 SkillHub **同机 spawn** 驱动其真跑 skill，**解析其 stream-json 输出**收集真实产出；评分系统（DSL 断言 / 双模型 / 安全 / 聚合 / 决策）结构复用，judge 按执行/样例分两套 prompt，`actual_output` 来源改为真实执行。

设计依据：`nexu-io/open-design`（local-first，daemon + per-agent adapter + stream-json 流解析）。完整设计稿见 `docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md`。

## What Changes

- 新增 `ExecutionSource` 抽象（Port），引擎 `case_executing` 经它取 `actual_output`，取代直接 `load_sample_io`。
- 新增 `SampleIoSource`（包现有行为，作回退/作者可选）与 `LocalAgentSource`（驱动本地 agent 真跑）。
- 新增 `LocalAgentRunner`（抄 open-design）：agent 检测 / 同机 spawn（原生 Windows，prompt 经 stdin）+ **StreamParser 流解析** / 完成判定 / 产物提取 / entrypoint 执行证据校验；v1 支持 claude、codex、cursor-agent（实现顺序 claude → codex → cursor-agent）。
- **回传走流解析**（非 MCP）：`actual_output` = 最终 result 文本 + tool_result + per-run cwd 产物文件 + 可选收尾 fenced JSON。
- judge 新增**执行模式 prompt**（真跑时按执行结果评）；样例模式（现有 doc-centric）保留；流水线结构、双模型、聚合、R1–R8 决策不变。
- 新增 `PerRunWorkspace`：每题每次运行从 staging clone 临时 cwd；有界并发（默认 2，可配）+ 限流退避。
- 新增元数据字段 `entrypoint`（has_scripts 必填）、`execution_source`（per-skill，默认随 env `EXEC_SOURCE`）。
- 红线题：happy/edge 由 agent 真跑；红线真跑仅 codex 加固档（`--sandbox workspace-write` + `network_access=false`），claude/cursor 红线降级 doc-centric。
- 信任模型分阶段（v1：信任本地，judge pass→PASS，标 `spot_check_eligible` 且 history 可筛）；执行来源可选 + 降级回退矩阵。
- 安全：执行前同意、权限约束在 per-run 目录、与现有 Security Gate 打通、回传过 output sanitizer。
- `level_achieved`：本地真跑（有 entrypoint 证据）→ level_2（source=local_agent）；sample_io = level_1；废弃 `has_scripts AND self.sandbox` 判定。

## Non-Goals

- `submit_case_output` MCP 工具 / `SkillHubMcpServer`——grill 后删除（cursor/codex 无 MCP 注入，不通用）。
- 多 agent 对照统计（W8.4）——本变更只保证三 agent 各能单独跑通。
- 公网中台复核 / 自动分级 PASS——属目标态（多用户/上云），v1 不做。
- 网络桥 / 上云 transport——v1 只做同机 spawn。
- claude/cursor 红线容器加固（WSL+firejail）——目标态。
- hybrid 会话分组——测出「太慢」再议。
- 中台确定性代码跑 / Golden Case / 上架后健康检查——已移阶段四（W10）。
- 物理删除 `skillhub_eval/sandbox/python_subprocess.py`——留架子，按安全协议另行确认。

## Relation to SPRINT

阶段三 · Wave 8（重定义 2026-06-17），覆盖 W8.1–W8.6，见 `.project_memory/active/SPRINT_phase3-eval-system.md`。取代原 W8 Level 2 中台沙盒 + 原 W9 自建 Harness。受影响规范文档：`docs/specs/Skill元数据定义与编写规范.md`（新增 `entrypoint`/`execution_source`、returns_schema / sample_io）、`docs/specs/评估指标与准入标准.md`（准入与信任、level 语义）。
