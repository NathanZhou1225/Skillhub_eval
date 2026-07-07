## ADDED Requirements

### Requirement: 本地 CLI runtime 平台契约

系统 SHALL 将本地 CLI agent 抽象为可复用 runtime，而非由评估引擎直接依赖各 CLI 的启动参数与原始输出格式。每个 runtime SHALL 通过声明式定义描述身份、二进制解析、版本探测、认证/配置探测、模型探测、prompt 传输方式、skill 注入策略、stream 格式、工具能力、preflight 配置、安装/修复指引。系统 SHALL 至少支持 `Codex`、`Cursor Agent`、`Trae`、`Claude`、`Antigravity` 五个 runtime。新增 CLI runtime SHOULD 通过新增 runtime definition、event normalizer 与 preflight fixture 接入，而非修改评估引擎主逻辑。

runtime definition、能力默认值、prompt transport 与 skill injection 策略 SHALL 作为项目级产品定义随代码版本化。resolved CLI path、认证/ready 探测结果、用户选择的 runtime/model、一键切换偏好、preflight cache SHALL 作为本机用户状态保存到现有本地 SQLite/config 层，且 SHALL NOT 写回 runtime definition 或提交到仓库。

#### Scenario: 新增 runtime 不修改评估引擎

- **Given** 一个新 CLI agent 具备可声明的二进制、模型探测、prompt 传输与 stream 格式
- **When** 开发者新增该 runtime 的 definition、event normalizer 与 fixture 测试
- **Then** 该 runtime SHALL 可被 scan/preflight/formal local execution 路径使用
- **And** 不需要修改 judge、R1-R8、报告聚合或专家复核逻辑

#### Scenario: 五个内置 runtime 暴露同一 readiness contract

- **Given** 系统内置 Codex、Cursor Agent、Trae、Claude、Antigravity
- **When** 调用本地 runtime scan API
- **Then** 每个 runtime SHALL 返回同结构的安装、版本、认证、模型、能力与 preflight 状态

#### Scenario: 连接测试与当前 Skill 检查分开展示

- **Given** 用户查看本地工具 readiness card
- **When** 某本地工具连接测试通过但当前 Skill 本地执行环境检查未通过
- **Then** UI SHALL 分开展示“连接测试”和“当前 Skill 检查”两个状态
- **And** SHALL NOT 使用一个笼统“可用”徽章暗示正式本地评估已经可运行

### Requirement: 统一 AgentEvent 事件层

系统 SHALL 将各 CLI 的原始输出流先归一化为内部 `AgentEvent` 流，再由统一逻辑合成 `ParsedStream`/`ExecResult`。评估引擎 SHALL NOT 直接消费 Cursor Agent、Trae、Codex、Claude 或 Antigravity 的原始 JSON/event/text 方言。`AgentEvent` SHALL 至少支持 `text_delta`、`thinking`、`tool_call`、`tool_result`、`file_write`、`usage`、`done`、`error`、`raw_unsupported`。工具调用和工具结果 SHALL 被拍平成包含工具名、命令/参数、stdout/stderr、exit code、错误标记、关联 id 的内部结构。

迁移期内，adapter SHALL 先新增 `normalize_events()` 并保留现有 `parse_stream()` 对外行为。系统 SHALL 用 fixture 测试证明 `parse_stream(raw)` 与 `parsed_stream_from_events(normalize_events(raw))` 在文本、工具证据、usage、duration、完成/错误状态上等价后，再逐步收敛到 AgentEvent-only 路径。

系统 SHALL 只将脱敏后的最小真实 stream fixture 提交到仓库。完整 live CLI raw stream SHALL 仅保存在 ignored 本地捕获目录（例如 `.tmp/raw_runtime_streams/`）。项目 SHOULD 提供 sanitizer，将 raw stream 转换为 fixture，并移除用户名、绝对路径、token、长正文与无关 prompt 内容，同时保留解析测试所需的事件形状。

默认测试套件 SHALL NOT 依赖本机已安装 CLI、登录态、网络/模型访问或 quota。live local CLI E2E 测试 SHALL 仅在显式环境变量（例如 `RUN_LOCAL_AGENT=1`）开启时运行。若某 runtime 未安装、未登录、模型不可用或 preflight 条件不满足，live E2E SHALL 以可读原因 SKIP，而不是让默认测试失败。

#### Scenario: Cursor Agent 真实 tool_call 被识别为工具证据

- **Given** Cursor Agent 输出真实嵌套 `tool_call`/`shellToolCall` 事件
- **When** runtime normalizer 处理该 stream
- **Then** 系统 SHALL 产出内部 `tool_call`/`tool_result` 事件
- **And** entrypoint evidence 校验 SHALL 能看到实际执行的命令与 stdout/stderr

#### Scenario: Trae 真实 user/tool_result 被识别为工具证据

- **Given** Trae 输出 assistant `tool_calls` 与 `type=user, subtype=tool_result` 事件
- **When** runtime normalizer 处理该 stream
- **Then** 系统 SHALL 用 tool id 关联命令与结果
- **And** 产出统一 `tool_result` 事件供 entrypoint evidence 校验使用

### Requirement: 正式本地评估必须通过 runtime preflight

当用户选择本地 CLI runtime 作为执行源时，系统 SHALL 在正式本地评估开始前检查所选 runtime/model 是否存在有效的 preflight pass。若 preflight 缺失、失败、过期或因指纹变化失效，系统 SHALL 阻止正式本地评估进入 `case_executing`，并向用户展示可操作诊断与修复/切换路径。系统 SHALL NOT 在未通过 preflight 的情况下直接尝试正式本地评估。

面向普通用户的产品文案 SHALL 将该能力称为“本地执行环境检查”或等价非技术名称。UI SHALL NOT 要求普通用户理解 `safe_preflight`、runtime fingerprint、SQLite cache、YAML 标记或 OpenSpec 术语。开发者日志、runbook 与 diagnostics MAY 继续使用 preflight 术语。

#### Scenario: preflight 缺失时阻止正式评估

- **Given** 用户选择 `execution_source=local` 且 runtime/model 没有有效 preflight pass
- **When** 用户尝试开始正式本地评估
- **Then** 系统 SHALL 先尝试运行当前 skill 的本地执行环境检查
- **And** 若检查无法运行或未通过，系统 SHALL 阻止该正式评估
- **And** 返回 `LOCAL_RUNTIME_PREFLIGHT_REQUIRED` 或等价可读原因
- **And** UI SHALL 提供运行/重试本地执行环境检查或显式切换到已验证 runtime 的入口

#### Scenario: preflight 通过后允许正式评估

- **Given** 所选 runtime/model 存在有效 preflight pass
- **When** 用户开始正式本地评估
- **Then** 系统 SHALL 允许进入 `case_executing`
- **And** 后续评分 SHALL 沿用现有 judge / R1-R8 / 专家复核逻辑

#### Scenario: 缺失 preflight 但可自动检查时不让用户手工配置

- **Given** 用户选择 `execution_source=local`
- **And** 当前 skill 尚无有效 preflight pass
- **And** 系统能为当前 skill 准备安全本地执行环境检查用例
- **When** 用户开始正式本地评估
- **Then** 系统 SHALL 自动运行该本地执行环境检查
- **And** 检查通过后 SHALL 继续正式本地评估
- **And** 用户不需要手动编辑 eval case、YAML 或 `safe_preflight` 字段
- **And** UI SHALL 将该过程显示为正式评估前的可见阶段，例如“正在检查本地执行环境”

#### Scenario: 本地执行环境检查失败时不可绕过继续真跑

- **Given** 用户选择本地执行
- **And** 当前 runtime/model 的本地执行环境检查失败、阻断或过期
- **When** 用户查看恢复动作
- **Then** UI SHALL NOT 提供“忽略检查继续本地真跑”或等价绕过入口
- **And** UI SHALL 提供“重新检查”、“重新生成检查用例”、“改用另一个已检查通过的本地工具”或“使用样例输出评估（非本地真跑）”等恢复动作

### Requirement: preflight 缓存与指纹失效

系统 SHALL 在现有 SkillHub SQLite 数据库中持久化 runtime preflight pass 结果 24 小时（默认数据库为 `settings.eval_db_path`，即 `data/skillhub_eval.db`）。正式评估 gate 使用的 preflight SHALL 绑定当前 skill fingerprint，并至少绑定 runtime id、model id、skill fingerprint、resolved CLI path、CLI version、runtime definition fingerprint、SkillHub version。任一绑定输入变化时，系统 SHALL 将旧 preflight 视为失效并要求重新运行。过期或失效的 preflight SHALL 不允许正式本地评估。

#### Scenario: 同一 skill 指纹 24 小时内复用 preflight

- **Given** 某 runtime/model/skill fingerprint 在 24 小时内通过 preflight
- **And** runtime id、model id、skill fingerprint、CLI path、CLI version、runtime fingerprint、SkillHub version 均未变化
- **When** 用户再次选择该 runtime/model 进行正式本地评估
- **Then** 系统 SHALL 复用该 preflight pass

#### Scenario: skill 内容变化导致 preflight 失效

- **Given** 某 runtime/model 曾对某 skill fingerprint 通过 preflight
- **When** 该 skill 的 `SKILL.md`、entrypoint、eval case 或相关 bundle 内容变化导致 skill fingerprint 改变
- **Then** 系统 SHALL 将旧 preflight 标记为失效
- **And** 要求对新 skill fingerprint 重新运行 preflight 后才能正式评估

#### Scenario: CLI version 变化导致 preflight 失效

- **Given** 某 runtime/model 曾通过 preflight
- **When** 该 runtime 的 CLI version 发生变化
- **Then** 系统 SHALL 将旧 preflight 标记为失效
- **And** 要求重新运行 preflight 后才能正式评估

#### Scenario: serve 重启后仍可复用有效 preflight

- **Given** 某 runtime/model/skill fingerprint 在 SQLite 中有未过期且指纹匹配的 preflight pass
- **When** `skillhub-eval serve` 重启
- **Then** 系统 SHALL 仍能读取该 preflight pass
- **And** 不要求用户仅因进程重启而重新运行 preflight

### Requirement: runtime preflight 证明真实 skill 执行能力

runtime preflight SHALL 针对当前 skill bundle 使用安全 preflight probe 验证该 runtime 能读取 SkillHub 提供的指令、在正确 workspace 中执行该 skill 的安全 entrypoint/probe（若脚本执行被要求）、产出可解析的实际结果、提供工具执行证据（若脚本执行被要求），并通过 sanitizer 与 entrypoint evidence 校验。仅模型文本回复成功 SHALL NOT 被视为 preflight 通过。系统 MAY 继续保留标准 fixture preflight 作为 runtime 开发/回归测试工具，但正式评估 gate SHALL 使用当前 skill fingerprint 级安全 preflight。

系统 SHALL 优先自动准备安全 preflight probe，而不是要求普通用户手动维护 preflight case。自动生成的 probe SHALL 作为系统检查用例持久化在 staging/bundle 内部，使 skill fingerprint、cache invalidation 与 serve 重启后的行为稳定。该检查用例 SHALL 不参与正式 eval case 完整性门槛、评分、报告 verdict、专家复核触发或 case 数量统计。

自动生成 SHALL 使用混合策略：系统 MAY 调用现有 LLM 能力生成候选检查用例，但候选结果 MUST 经过确定性 schema 与安全规则校验；若 LLM 不可用、超时、输出无法解析或未通过规则校验，系统 SHALL 使用确定性模板兜底。系统 SHALL NOT 将未经规则校验的 LLM 输出直接作为安全检查用例持久化或执行。

系统 SHALL 在写入或重新生成内部检查用例后重新读取 bundle 并重新计算 skill fingerprint。preflight cache SHALL 绑定写盘后的新 fingerprint，而不是生成前的旧 fingerprint。

#### Scenario: 有安全 preflight case 时使用它

- **Given** 当前 skill bundle 提供安全 preflight case 或等价元数据
- **When** 用户运行 runtime preflight
- **Then** 系统 SHALL 使用该安全 preflight case
- **And** SHALL NOT 使用正式 eval case 作为默认 preflight 输入

#### Scenario: 高风险 skill 自动生成系统检查用例

- **Given** 当前 skill 为 high-risk 或 redline 相关 skill
- **And** bundle 未提供安全 preflight case
- **And** 系统可从已有 skill 元数据、输出要求或低风险示例中构造不会触发真实业务动作的最小检查输入
- **When** 系统准备本地执行环境检查
- **Then** 系统 SHALL 自动生成并持久化一条内部检查用例
- **And** 该用例 SHALL 标记为 `type: preflight` 与 `safe_preflight: true`
- **And** 该用例 SHALL 保留在 bundle 的 eval case 列表中供本地执行环境检查使用
- **But** 该用例 SHALL 从正式 case 数量、题型覆盖、缺口扫描、正式 case 执行、评分、报告与专家复核中排除
- **And** 系统 SHALL 使用写盘后的 bundle fingerprint 运行并缓存本地执行环境检查
- **And** UI SHALL 告知用户系统已准备本地执行环境检查，而非要求用户编辑 YAML

#### Scenario: LLM 候选未通过安全校验时使用模板兜底

- **Given** 系统调用 LLM 生成本地执行环境检查候选用例
- **And** LLM 输出缺少必填字段、包含真实业务动作、买卖/下单/支付/删除/发送/发布等指令，或无法解析为固定 schema
- **When** 系统准备本地执行环境检查
- **Then** 系统 SHALL 丢弃该候选
- **And** SHALL 使用确定性安全模板兜底
- **And** SHALL 记录开发者诊断信息但不向普通用户暴露 LLM 失败细节

#### Scenario: 高风险 skill 缺少安全 preflight 时阻断

- **Given** 当前 skill 为 high-risk 或 redline 相关 skill
- **And** bundle 未提供安全 preflight case
- **And** 系统无法自动生成安全检查用例
- **When** 用户运行 runtime preflight
- **Then** 系统 SHALL 阻断 preflight
- **And** 返回要求补充最小安全检查问题的可读原因
- **And** UI SHALL 优先提供“生成检查用例”或“重试环境检查”的产品动作，而不是要求普通用户理解 `safe_preflight`
- **And** UI SHALL 使用普通用户可理解的中文动作，例如“改用另一个已检查通过的本地工具”和“使用样例输出评估（非本地真跑）”，而不是直接暴露 `runtime` 或 `sample_io`

#### Scenario: 文本 smoke 成功但 entrypoint 未调用不能通过

- **Given** 某 runtime 能对简单 prompt 返回文本
- **But** 在 fixture 中没有调用 entrypoint 或没有工具执行证据
- **When** 系统运行 preflight
- **Then** preflight SHALL 失败
- **And** failure reason SHALL 指向 `runtime_entrypoint_not_called` 或等价原因

#### Scenario: fixture entrypoint 成功执行通过 preflight

- **Given** 某 runtime 执行 fixture 时调用 entrypoint 并返回期望结构化结果
- **When** 系统运行 preflight
- **Then** preflight SHALL 标记为 passed
- **And** 记录完成事件、工具证据与输出摘要

### Requirement: skill 注入策略

系统 SHALL 为 runtime 提供可声明的 skill 注入策略：native skill loading、file-placed workflow、prompt injection。每个 runtime SHALL 至少支持 prompt injection 作为兜底。系统 SHALL 根据 runtime capability 选择优先策略，并在策略不可用时降级到已声明 fallback。注入层 SHALL 避免把无关引用文件无边界塞入 prompt，并 SHALL 在 prompt/argv 过大时返回明确失败原因。

#### Scenario: runtime 无 native skill loading 时走 prompt injection

- **Given** 某 runtime 不支持 native skill loading
- **When** 系统为其准备本地评估 prompt
- **Then** 系统 SHALL 通过 prompt injection 或 file-placed workflow 提供 `SKILL.md` 与必要引用
- **And** 不要求该 CLI 具备原生 SkillHub/Codex skill 机制

#### Scenario: prompt 过大返回明确原因

- **Given** 某 runtime 只能通过 argv 接收 prompt
- **And** 组合后的 skill/case prompt 超过该 runtime 的安全命令行长度
- **When** 系统准备执行或 preflight
- **Then** 系统 SHALL 阻止执行
- **And** 返回 `runtime_prompt_too_large` 与可操作缩减提示

### Requirement: 显式 runtime 切换而非自动 fallback

本地 runtime 失败、preflight 未通过或 preflight 过期时，系统 SHALL NOT 自动切换到其他 runtime。系统 MAY 在 UI 中展示其他已通过 preflight 的 runtime，并提供显式“一键切换并重跑”操作。只有用户主动触发切换后，系统才 SHALL 更新 runtime/model 偏好并创建新的评估运行。

#### Scenario: runtime 失败后不自动切换

- **Given** 用户选择 Trae 运行正式本地评估
- **And** Trae 在运行中失败
- **When** 系统检测到 Claude 已通过 preflight
- **Then** 系统 SHALL NOT 自动改用 Claude
- **And** UI MAY 显示“可改用 Claude 重跑”的显式操作

#### Scenario: 用户显式切换后新运行使用新 runtime

- **Given** 当前运行因所选 runtime 失败而阻断
- **And** UI 展示另一个 preflight-passed runtime
- **When** 用户点击显式切换并重跑
- **Then** 系统 SHALL 更新所选 runtime/model
- **And** 创建新的运行
- **And** 报告 SHALL 区分 requested runtime/model 与实际成功执行 runtime/model

### Requirement: runtime 失败原因产品化

系统 SHALL 使用稳定、可读、可持久化的 runtime failure taxonomy，而非把所有未完成统一归为 `run_incomplete`。失败原因 SHALL 至少覆盖：未安装、不可启动、未登录/登录过期、模型不可用、模型探测不可用、preflight 缺失/过期、工具权限不足、prompt 过大、CLI 崩溃、进程超时、完成事件缺失、parser 不支持、entrypoint 未调用、输出泄漏、workspace 错误。报告、事件日志与 UI SHALL 使用这些原因生成中文说明与修复提示。

#### Scenario: CLI 崩溃与完成事件缺失区分

- **Given** 某 runtime 子进程退出并输出模块缺失错误
- **When** 系统记录失败
- **Then** failure reason SHALL 为 `runtime_cli_crashed` 或等价代码
- **And** 不得误标为完成事件缺失

#### Scenario: 进程超时与 parser 未识别区分

- **Given** 某 runtime 进程被 timeout 杀死
- **When** 系统记录失败
- **Then** failure reason SHALL 为 `runtime_process_timeout`
- **But** 如果进程正常退出且输出中没有可识别完成事件
- **Then** failure reason SHALL 为 `runtime_completion_event_missing` 或 `runtime_parser_unsupported`

## MODIFIED Requirements

### Requirement: 执行来源传输分派

`LocalAgentSource` 获取产出 SHALL 经 runtime platform 分派执行。现有 `stream_format` 分派 SHALL 被保留为 runtime launch/normalization 的一部分，但正式执行 SHALL 先经过 runtime readiness 与 preflight 校验。`ExecResult` 仍为评估引擎边界，judge prompt 与评分聚合 SHALL 根据 `ExecResult.source`/`actual_output` 沿用现有逻辑。

#### Scenario: 评分逻辑不因 runtime platform 改变

- **Given** 某 runtime 已通过 preflight 并成功产生 `ExecResult(source=local_agent, status=ok)`
- **When** 引擎进入 judge 与 report 阶段
- **Then** 系统 SHALL 使用现有 dual-model judge、R1-R8、阈值与专家复核流程
- **And** 不因 runtime 平台引入新的评分规则
