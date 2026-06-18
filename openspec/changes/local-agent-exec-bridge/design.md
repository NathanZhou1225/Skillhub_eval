# Design: local-agent-exec-bridge

> 完整论证与决策取舍见 `docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md`（设计稿，权威，含 grill 修订 §0）。本文件聚焦 **模块映射到 `skillhub_eval/` 的接口与改动点**，不重复论证。

## 锁定决策（brainstorm + grill 2026-06-17）

| # | 决策 |
|---|------|
| D1 | 同机 spawn，无网络桥（原生 Windows，prompt 经 stdin） |
| D2 | 每题隔离 + 有界并发（默认 2，可配）+ risk 分级超时 + 限流退避 |
| D3 | **流解析回传**（非 MCP）：最终文本 + tool_result + cwd 产物 + 可选收尾 fenced JSON |
| D4 | 每次运行从 staging clone per-run 临时 cwd；权限仅限该目录 |
| D5 | 增量 + 来源可选（per-skill `execution_source` > env 默认）+ 失败回退 sample_io（无样例才 incomplete） |
| D6 | 信任分阶段：v1 信任本地（pass→PASS，标 spot_check_eligible 且 history 可筛）；目标态分级 |
| D7 | 断言结构性 + 语义为主，容忍非确定 |
| D8 | v1 三 agent：claude → codex → cursor-agent |
| D9 | judge 执行/样例双 prompt（按 ExecResult.source 选） |
| D10 | has_scripts 技能要 entrypoint 执行证据；无证据降级/incomplete |
| D11 | 红线真跑仅 codex 加固档；claude/cursor 红线降级 doc-centric |

## 模块映射（skillhub_eval/）

### 新增

| 路径 | 职责 | 关键接口 |
|------|------|----------|
| `skillhub_eval/core/execution_source.py` | `ExecutionSource` 路由 + 降级矩阵 | `get_actual_output(case, bundle, ctx) -> ExecResult` |
| `skillhub_eval/core/sample_io_source.py` | 包 `ingest.load_sample_io`（回退/可选） | 实现 `ExecutionSource` |
| `skillhub_eval/execution/local_agent_source.py` | 驱动本地 agent、并发/限流、收集回传 | 实现 `ExecutionSource` |
| `skillhub_eval/execution/runner.py` | `LocalAgentRunner`：detect/spawn/完成判定/产物提取 | `run(agent, prompt, cwd, profile, timeout) -> RunOutcome` |
| `skillhub_eval/execution/stream_parser.py` | per-agent StreamParser（claude-stream-json / codex / cursor json-event-stream） | `parse(stdout_iter) -> ParsedStream` |
| `skillhub_eval/execution/evidence.py` | `EvidenceVerifier`：tool_result 是否跑过 entrypoint | `verify(parsed, entrypoint) -> bool` |
| `skillhub_eval/execution/adapters/claude.py` | claude adapter（buildArgs/stdin） | `Adapter` 协议 |
| `skillhub_eval/execution/adapters/codex.py` | codex adapter（含加固档沙箱标志） | `Adapter` 协议 |
| `skillhub_eval/execution/adapters/cursor_agent.py` | cursor-agent adapter | `Adapter` 协议 |
| `skillhub_eval/execution/workspace.py` | `PerRunWorkspace`：clone staging→临时 cwd / 清理 / 留证 | `acquire()/release()` |
| `skillhub_eval/execution/profile.py` | `HardenedProfile`：codex 沙箱档；claude/cursor 无→红线降级 | `for_case(agent, case_type) -> Profile` |
| `skillhub_eval/execution/harness_prompt.py` | 强制用 harness prompt 构造 | `build(case, bundle, entrypoint) -> str` |

> **不新增 MCP server**（grill G1：回传走流解析，不靠 MCP 注入）。

### 修改

| 路径 | 改动 |
|------|------|
| `skillhub_eval/core/engine.py` | `case_executing` 三处 `load_sample_io`（:313/:330/:1010）改经 `ExecutionSource`；`_build_case_prompt` 加执行/样例双模式（按 source）；`level_achieved` 改看执行证据（废弃 :296 `has_scripts AND self.sandbox`）；pass→PASS 标 `spot_check_eligible` |
| `skillhub_eval/core/ports.py` | 增 `ExecutionSource` Protocol（与 `Repository` 并列） |
| `skillhub_eval/core/ingest.py` | 解析新元数据 `entrypoint` / `execution_source` |
| `skillhub_eval/settings.py` | 增 `EXEC_SOURCE`(`local`/`sample_io`)、`EXEC_CONCURRENCY`(默认 2)、`EXEC_AGENT`、per-risk timeout |
| `skillhub_eval/core/schemas/report.py` | `ExecResult`/`RunOutcome`/`ParsedStream` 数据类（actual_output + source + confidence + transcript_ref + usage + status + level） |
| `skillhub_eval/core/output_sanitizer.py` | 解析出的 actual_output 过 sanitizer（复用 `run_output_sanitizer`） |
| `docs/specs/Skill元数据定义与编写规范.md` | 新增 `entrypoint`（has_scripts 必填）、`execution_source` 字段定义 |
| `skillhub_eval/persistence/*` | history 增 `spot_check_eligible` / `execution_source` 可筛字段（复用现有 review 流） |

### 不动 / 留架子

- `skillhub_eval/sandbox/python_subprocess.py`：保留，阶段四 Golden Case 按需接最小版；不物理删除。
- `core/assert_/dsl.py`、`aggregate.py`、`decision.py`（R1–R8）、双模型 judge 调用结构：完全复用。

## 完成判定与产物提取（实读 open-design daemon）

`LocalAgentRunner` 两层完成判定：① 子进程 `exit`；② stream-json `{type:"result"}` 终结事件（带 usage/duration）。`ArtifactCollector` 取四类作 actual_output 证据 + 双模型输入：最终文本、`tool_result`(stdout + exit_code/isError)、per-run cwd 产物文件、收尾 fenced JSON(best-effort)。

各 agent 流格式（实读源码）：claude=`claude-stream-json`；codex=`json-event-stream`(codex parser)；cursor-agent=`json-event-stream`(cursor 私有 parser，去重见 `emitCursorTextDelta`)。

## 判子双模式

`_build_case_prompt` 按 `ExecResult.source`：
- `sample_io` → 现有 doc-centric prompt（评 SKILL.md 自洽，含红线 doc 口径）。
- `local_agent` → 执行模式 prompt（评执行结果：符合 user_intent/returns_schema、真跑通、读 tool_result/产物；红线看真实拒答行为）。
双模型调用、聚合、R1–R8、human_review 路由不变。

## 降级矩阵

| 情况 | 行为 |
|------|------|
| 无 agent / 作者选 sample_io | 整轮 `SampleIoSource`（样例模式，低置信，level_1） |
| 未登录 | 回退 + 提示去 CLI 登录 |
| 红线 + claude/cursor（无加固档） | 该红线题降级 doc-centric，报告标原因 |
| has_scripts 无 entrypoint 证据 | 回退该题 sample_io；无样例 → `incomplete` |
| 单题超时/失败 | 回退该题 sample_io；无样例 → `incomplete` |
| 限流持续失败 | 退并发到 1 + 退避后仍失败 → 同上失败分支 |
| 全失败 | 等同现有 sample_io 路径，不退化 |

## 信任（分阶段）

v1（同机/内部/作者本人）：judge（双模型读 transcript）pass→PASS，标 `spot_check_eligible` 且 history 可筛（人工抽检）；warn/R5 仍进 human_review。伪造风险记「已知暂受」。目标态（多用户/上云）：公网中央复核 / 内网专家签收。不改 R1–R8。

## 风险与未决

- 单题失败默认回退 sample_io（已锁，无样例才 incomplete）。
- cursor-agent 私有 eventParser 放最后做（参照 open-design `emitCursorTextDelta`）。
- agent 不调 entrypoint → 强制 harness prompt + EvidenceVerifier → retry 一次 → 降级。
- 收尾 fenced JSON 解析失败 → 用文本 + tool_result + cwd 产物合成。
- claude/cursor 红线 v1 无法真跑（接受，目标态容器加固）。
