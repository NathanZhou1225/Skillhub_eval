# Spec Delta: skill-execution

## ADDED Requirements

### Requirement: 可插拔执行来源（ExecutionSource）

引擎在 `case_executing` 阶段 SHALL 通过 `ExecutionSource` 抽象获取每个 case 的 `actual_output`，而非直接读取 `sample_io`。系统 SHALL 提供 `SampleIoSource`（读 `sample_io/{case}.json`）与 `LocalAgentSource`（驱动本地 CLI agent 真跑）。执行来源 SHALL 由 per-skill 元数据 `execution_source` 决定，缺省时回落到环境变量 `EXEC_SOURCE`。

#### Scenario: 作者选择本地真跑且 agent 可用

- **Given** 一个 skill bundle 的 `execution_source` 为 `local`
- **And** 本地已安装并登录 claude / codex / cursor-agent 之一
- **When** 引擎进入 `case_executing`
- **Then** 系统通过 `LocalAgentSource` 同机 spawn 该 agent 真跑每个 case
- **And** 将解析回传的产出作为 `actual_output` 喂给 judge 的执行模式 prompt

#### Scenario: 作者选择 sample_io 或缺省

- **Given** 一个 skill bundle 的 `execution_source` 为 `sample_io`，或未声明且 `EXEC_SOURCE=sample_io`
- **When** 引擎进入 `case_executing`
- **Then** 系统通过 `SampleIoSource` 读取 `sample_io/{case}.json` 作为 `actual_output`
- **And** judge 走样例模式 prompt，行为与本变更前一致

### Requirement: 流解析回传契约

系统 SHALL 通过解析本地 agent 子进程的 stream-json 输出获取产出，**不依赖注入 MCP 工具**。`actual_output` SHALL 由以下证据合成：最终 result 文本、`tool_result`（stdout + exit_code/isError）、per-run cwd 新增/改动的产物文件、以及可选的收尾 fenced JSON（best-effort，匹配 returns_schema）。完成判定 SHALL 采用两层：子进程 exit 与 stream-json 终结 `result` 事件。

#### Scenario: 解析 agent 流取得产出

- **Given** 一个本地 agent 子进程跑某 case 并输出 stream-json
- **When** `LocalAgentRunner` 检测到子进程 exit 且收到终结 `result` 事件
- **Then** `ArtifactCollector` 提取最终文本、tool_result、cwd 产物、收尾 JSON
- **And** 合成 `actual_output` 并在进入 judge 前过 output sanitizer（PII/密钥）

#### Scenario: 收尾结构化 JSON 缺失

- **Given** agent 未在末尾打印可解析的 fenced JSON
- **When** `ArtifactCollector` 合成 `actual_output`
- **Then** 系统用最终文本 + tool_result + cwd 产物合成，不视为失败

### Requirement: 执行证据校验

对 has_scripts 的技能，系统 SHALL 要求 transcript 中存在 `tool_result` 证据，证明 skill 声明的 `entrypoint` 被真实执行；否则该 case 不得计为真实执行。`entrypoint` 字段 SHALL 在 has_scripts 技能的元数据中必填。

#### Scenario: entrypoint 真实执行

- **Given** 一个 has_scripts 技能声明 `entrypoint: scripts/run_diagnosis_pipeline.sh`
- **And** agent 的 tool_result 显示该 entrypoint 被调用
- **When** `EvidenceVerifier` 校验
- **Then** 该 case 计为真实执行，`level_achieved=level_2`，`source=local_agent`

#### Scenario: 缺少执行证据

- **Given** 一个 has_scripts 技能在真跑中未见 entrypoint 执行的 tool_result
- **When** `EvidenceVerifier` 校验失败
- **Then** 系统对该 case 重试一次；仍无证据则回退 sample_io（若有），否则标 `incomplete` 不计 pass

### Requirement: 判子执行/样例双模式

judge SHALL 按 `ExecResult.source` 选择评分 prompt：`local_agent` 走执行模式（评执行结果是否符合 user_intent/returns_schema、是否真跑通、读 tool_result/产物），`sample_io` 走现有 doc-centric 样例模式。双模型调用结构、聚合与 R1–R8 决策规则 SHALL 不变。

#### Scenario: 真跑结果按执行模式评

- **Given** 一个 case 的 `actual_output.source=local_agent`
- **When** judge 构造 prompt
- **Then** 使用执行模式 rubric，让双模型按真实执行结果评分

#### Scenario: 样例按 doc-centric 评

- **Given** 一个 case 的 `actual_output.source=sample_io`
- **When** judge 构造 prompt
- **Then** 使用现有 doc-centric rubric，行为与本变更前一致

### Requirement: 每题隔离执行与有界并发

系统 SHALL 对每个 case 在独立的 per-run 工作目录中以干净 agent 会话执行，并以可配置的有界并发（默认 2）调度。检测到限流（rate-limit/429）时 SHALL 自动退并发到 1 并指数退避重试。

#### Scenario: 并行多题各自隔离

- **Given** 一个含多个 case 的 skill
- **When** 引擎并行执行这些 case
- **Then** 每个 case 从 staging clone 出独立临时 cwd
- **And** 并发数不超过配置上限，各 case 产物互不串扰

#### Scenario: 命中限流自动退避

- **Given** 并行执行中某 agent 返回 rate-limit/429
- **When** StreamParser 检测到限流
- **Then** 系统退并发到 1 并指数退避重试该题
- **And** 持续失败则该题进入降级矩阵

### Requirement: 红线题加固执行或降级

happy/edge 类 case SHALL 由三 agent 任一真跑。refusal/adversarial 红线题真跑 SHALL 仅在加固档下进行：codex 使用 `--sandbox workspace-write` + `network_access=false` + `default_permissions=":workspace"`；claude / cursor-agent 因原生无网络/文件系统约束，红线题 SHALL 降级为 doc-centric 样例模式，并在报告标明原因。

#### Scenario: codex 红线加固真跑

- **Given** 一个红线 case 且选用 codex
- **When** 系统准备执行
- **Then** 以加固档（禁外联 + 限 fs）spawn codex 真跑并按执行模式评

#### Scenario: claude/cursor 红线降级

- **Given** 一个红线 case 且选用 claude 或 cursor-agent
- **When** 系统准备执行
- **Then** 该红线 case 降级 doc-centric 样例模式
- **And** 报告标明「无加固档，红线降级」

### Requirement: 执行降级与回退

当本地 agent 不可用或单题执行失败时，系统 SHALL 自动降级，保证一轮评估仍可出结论且功能不退化。

#### Scenario: 未检测到本地 agent

- **Given** `execution_source=local` 但本机无可用 agent
- **When** 引擎进入 `case_executing`
- **Then** 系统整轮回退 `SampleIoSource` 并标记为低置信（level_1）

#### Scenario: 单题执行失败

- **Given** 某 case 执行超时、报错或限流持续失败
- **When** `LocalAgentRunner` 判定该题失败
- **Then** 若该 case 有 `sample_io` 则回退用之；否则标 `incomplete`，不计入 pass

### Requirement: v1 分阶段信任

在 v1（同机、内部、作者本人）下，系统 SHALL 在 judge 判定 pass 后给出 PASS 终态，并将该 run 标记 `spot_check_eligible` 且在 history 中可按执行来源筛选（供人工抽检）；warn 与 R5 等触发 SHALL 仍进入现有 human_review 流程。R1–R8 决策规则 SHALL 不被修改。

#### Scenario: 本地真跑通过

- **Given** 本地 agent 真跑回传的 `actual_output` 经执行模式 judge 判定 pass
- **When** 引擎进入决策阶段
- **Then** 系统给出 PASS 终态，并标 `spot_check_eligible`
- **And** 该 run 可在 history 按 `source=local_agent` 筛出供人工抽检（不阻塞终态）

#### Scenario: 触发人工复核

- **Given** judge 结果为 warn 或命中 R5
- **When** 引擎进入决策阶段
- **Then** 系统按现有规则置 `human_review_required` 并路由专家

### Requirement: 本地执行安全边界

系统 SHALL 在 spawn 本地 agent 前取得作者明确同意，并将 agent 的全自动权限约束在 per-run 临时目录与评估期内；进入本地执行的 skill 代码 SHALL 已通过现有 intake 安全扫描。

#### Scenario: 执行前同意

- **Given** 作者首次对某 skill 选择本地真跑
- **When** 系统准备 spawn agent
- **Then** 系统提示「将以全自动权限在本机临时目录运行该 skill 代码」并要求确认
- **And** 未确认则不 spawn

#### Scenario: 安全扫描拦截

- **Given** 某 skill bundle 在 intake 阶段被 Security Gate 标记 blocked
- **When** 引擎尝试进入本地执行
- **Then** 系统拒绝执行，不 spawn agent

### Requirement: 执行级别语义

`level_achieved` SHALL 反映真实执行：有 entrypoint 执行证据的本地真跑为 `level_2`（`source=local_agent`），sample_io 来源为 `level_1`。原 `has_scripts AND sandbox 存在` 的判定 SHALL 废弃。

#### Scenario: 真跑记 level_2

- **Given** 某 case 经本地 agent 真跑且通过执行证据校验
- **When** 引擎记录该 case 的 level
- **Then** `level_achieved=level_2`，`source=local_agent`

#### Scenario: 样例记 level_1

- **Given** 某 case 走 sample_io 来源
- **When** 引擎记录该 case 的 level
- **Then** `level_achieved=level_1`
