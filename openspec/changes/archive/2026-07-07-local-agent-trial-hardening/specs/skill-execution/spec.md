## ADDED Requirements

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
