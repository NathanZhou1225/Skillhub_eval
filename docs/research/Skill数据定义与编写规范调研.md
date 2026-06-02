## 调研摘要

本次调研覆盖 OpenAI、Anthropic、Google 三家头部模型厂商，以及腾讯（WorkBuddy）、DeepSeek、字节跳动（Coze）、阿里（钉钉/百炼）四家国内主流 Agent 平台和 OpenClaw、Hermes 两个开源生态代表，共 9 个调研对象。调研从 Skill 数据定义规范、审核与安全评判规范、效果评判机制三个维度展开系统梳理。

核心发现：① JSON Schema 是数据定义的事实标准，各厂商的差异主要体现在 Prompt 编写策略与底层架构设计上；② 审核机制正从静态准入转向"沙盒试跑 + 运行时熔断"的多维动态体系；③ 效果评判不再依赖单一打分，头部厂商已普遍采用"代码 + 模型 + 人工"的三维裁判架构。

## 主流厂商Skill/Tool数据规范

#### 1.1 头部大厂模型厂商

- OpenAI (Function Calling / Assistants API)

  - 数据结构：采用 JSON Schema 规范。需定义 name、description、parameters 树状结构，要求声明 type（object/string/array 等）及 required 必填项列表。

  - Prompt 规范：强调动作确定性。系统提示词侧重描述能力边界而非执行过程，模型通过 Schema 中 description 字段自主理解工具用途，建议使用祈使句编写。

  - 底层规范：Assistants API 引入有状态 Thread 机制。工具执行过程中，底层通过 requires_action 状态挂起模型推理，待宿主系统返回 tool_outputs 后恢复上下文，实现多轮交互。

- Anthropic (Claude Tool Use / Claude Code Skills)

  - 数据结构：采用文件化模块设计。Skill 以结构化目录组织，核心文件为 SKILL.md，封装元数据、参数架构与执行指令。参数输入推荐结合 input_schema 与 XML 标签实现结构化隔离。

  - Prompt 规范：强调思维链与异常处理。要求在 Description 中定义失败场景处理逻辑。调用 Skill 前需输出 \<thinking\> 标签，解释参数推导逻辑。

  - 底层规范：支持长上下文（200K+ tokens）下的工具寻址。底层允许返回体中携带业务 Error，由模型自行修正调用策略。

- Google (Gemini / Vertex AI Extensions)

  - 数据结构：原生对接 OpenAPI 3.0 规范，对枚举值（enum）和数组结构（items）有严格校验。

  - Prompt 规范：除工具描述外，建议补充工具的适用业务域及参数的数据来源要求。

  - 底层规范：Skill 注册在 Extension 层，内置企业级数据隔离、鉴权管理及并发控制。

#### 1.2 国内主流大模型及Agent平台

- 腾讯 (Workbuddy / TencentDB Agent)

  - 数据结构：采用图结构组织任务与代码上下文，Skill以节点形式注册，支持复杂多步任务的结构化拆解。

  - Prompt 规范：引入提示词动态优化与上下文压缩机制。Prompt 根据当前任务图节点执行进度动态裁剪，减少无关信息干扰。

- DeepSeek

  - 数据结构：兼容 MCP（Model Context Protocol）协议与 JSON Schema，与开源生态对接成本低。

  - Prompt 规范：采用规范注入（Specification Injection）机制。支持在 Skill 中硬编码领域专长指令（如金融风险提示话术、企业公文格式规范），该注入具有最高优先级，确保输出符合业务边界。

- 字节跳动 (Coze / 扣子)

  - 数据结构：将 HTTP 接口转化为可视化 I/O 映射模板（底层映射为 OpenAPI Schema）。Workflow 中数据结构被抽象为图计算节点（Node）及连线参数。

  - Prompt 规范：通过 GUI 表单自动生成 System Prompt，降低编写门槛。

- 阿里 (钉钉 AI 助理 / 阿里云百炼)

  - 数据结构：与企业钉钉组织 Open API 深度融合，参数结构中包含鉴权 Token 和组织架构 ID。

  - Prompt 规范：角色与权限感知。Prompt 中注入当前调用者的岗位角色，影响参数提取和生成语气。

#### 1.3 开源生态框架

- OpenClaw

  - 数据结构：采用文件系统目录结构组织 Skill（SKILL.md 与 references 目录）。

  - Prompt 规范：支持渐进式披露（Progressive Disclosure）。参数众多的 Skill 在 Prompt 中仅展示核心入口，模型决定调用后再展开完整参数，节省上下文 Token。

  - 底层规范：支持快照机制（Snapshot）、上下文引用与结构化命令传递，应对网络中断或页面刷新导致的执行失败，增强网页自动化等场景的系统稳定性。

- Hermes

  - 数据结构：作为 Function Calling 专用模型，严格遵循 OpenAI 兼容的 JSON Schema，底层通信嵌入 \<tool_call\> 和 \<tool_response\> 特殊 Token 实现闭环。

  - Prompt 规范：依赖 System Prompt Steering（系统指令引导），需在系统提示词中精确说明如何将内部逻辑转化为 XML 或 JSON 格式输出。

  - 底层规范：权重层面对工具调用进行了专门微调（Fine-tuning），无需外围解析脚本即可自主抑制幻觉，适合作为本地私有化 Skill 质检基座。

#### 1.4 核心设计原则提炼

说明：语义确定性原则与强结构化契约原则的完整阐述见 2.4 节，本节仅列出数据定义视角独有的两条原则。

**原则一：防御性边界原则**

- 规范提炼：在编写 Skill 的描述时，必须强制包含"使用禁区（Negative Prompt）"与"异常预期"。

- 示例："仅支持查询 2023 年以后的数据；如果查不到相关员工，请直接返回'查无此人'，严禁尝试猜测同音字。"这种防御性声明能最大程度阻断多模型交叉验证时的"幻觉对冲"。

  **原则二：输入输出白盒化原则**

- 规范提炼：为了让便于后期对Skill的质检，Skill 不仅要定义怎么"入"，还要明确定义怎么"出"。系统必须配置 returns_schema（预期返回格式），使得"指令遵循度"和"有效性"的考核有客观的 JSON 格式比对标准，而不是靠人工去读日志。

#### 1.5 Skill命名规范参考

**命名格式要求**

采用英文动宾短语，以下划线连接（如 query_user_info、generate_report），全局唯一。

**禁止使用的词类型**

修饰性词汇（如 powerful、excellent）、模糊动词（如 handle、process、manage）、"这是一个......"等无信息量前缀。

**示例对比**

✓ query_employee_data（动宾明确）    ✗ handle_staff_stuff（动词模糊）

✓ generate_daily_report（描述动作）    ✗ a_powerful_report_tool（含修饰词）

✓ search_product_by_keyword（参数明确）    ✗ search_product_maybe（语义不确定）

## 主流厂商Skill/Tool审核与安全评判规范

#### 2.1 头部厂商审核规范

- OpenAI (GPT Store & Actions：强合规与自动化拦截)

  - 以 App Store 模式运作，核心机制是自动化准入门槛校验------强制验证隐私政策 URL 和开发者域名。违规工具被服务端强制降级为"仅开发者私有可用"。同时从模型层面拦截涉及高风险敏感领域（如金融信贷、医疗诊断）的请求。

- Anthropic (Claude & MCP：权限沙盒与语义精准度)

  - 以零信任沙盒为核心，工具默认只读权限，涉及文件写入、网络请求等动作需用户显式授权。要求 Description 必须与实际功能完全一致，严禁隐藏指令或诱导模型拉取外部未知指令，并在 Token 消耗上保持极度克制。

- Google (Model Context Protocol 体系：企业级全链路监控)

  - 侧重企业级全链路安全，核心机制是在网关层对返回结果进行严格的输入输出清洗（防范 XSS 与指令注入）。同时将 Skill 审核与 Cloud IAM 鉴权融为一体，全链路追踪调用频率和数据流向。

#### 2.2 各厂商审核机制多维对比

| 厂商/平台 | 静态审核与准入机制 | 动态沙盒与测试验证 | 运行时监控与惩罚机制 | 核心审核导向 |
|---|---|---|---|---|
| OpenAI | 强依赖 OpenAPI Schema 校验；强制验证开发者域名与隐私政策 URL。 | 无强制沙盒跑通要求，依赖自动化内容安全与品牌合规扫描。 | 核心监控 Invalid Request Rate (无效请求率) 与超时。违规或高频报错自动降级/下架，提供申诉通道。 | 内容生态与合规（类似 App Store，重政策管控与标准化） |
| Anthropic | 严查工具 Description 的语义清晰度，要求强制显式声明失败处理逻辑。 | 零信任沙盒隔离，网络请求和文件操作默认拦截，需提供 3 个以上的标准测试用例。 | 引入思维链 (CoT) 反思监控，防止模型为凑齐参数而编造数据（幻觉）。需用户显式授权高危动作。 | 防幻觉与边界隔离（重底层沙盒隔离与模型认知约束） |
| Google | OpenAPI 3.0 强类型校验（Type, Enum 严格比对）；企业级 IAM 鉴权审查。 | 侧重云原生部署的安全隔离，与 Google Cloud 安全策略拉齐。 | 严格的输入输出清洗 (Sanitization)。拦截不符合 Schema 的返回体，防范前端 XSS 与指令注入。 | 企业级设施与数据链路安全（重供应链审计与防注入） |
| 字节跳动 | API 基础字段与命名规范扫描，防废话修饰。 | 强制在线沙盒试运行，抓取真实 I/O 固化为 Test Case；内置 AI 投毒对抗测试。 | 实时监控 API 连通率与报错率。根据真实调用数据和用户评分驱动"热榜"分发或限流。 | 高可用性与非技术人员体验（重开箱即用与业务闭环） |
| 微软 | 依托 Partner Center 的企业资质强认证；Responsible AI 原则合规扫描。 | 模拟企业租户环境测试，验证跨应用数据读取的合规性。 | 监控数据流转边界，确保不违反企业数据防泄漏 (DLP) 策略。 | 商业合规与知识产权（重企业级合规与数据驻留） |

#### 2.3 审核多步验证

**一、 静态元数据与合规准入审核 (Static Metadata & Compliance Review)**

这类审核主要发生在 Skill 提交的最初阶段。系统在不实际运行代码的情况下，通过规则引擎对工具的"身份证"------即 API Schema、参数描述、开发者资质以及法律合规性文件进行死板但严格的扫描。

- 包含平台：OpenAI、微软 (Copilot)、字节跳动 (Coze)。

**二、 动态沙盒与安全攻防验证 (Dynamic Sandbox & Offensive/Defensive Isolation)**

这类审核是系统将 Skill 放入一个虚拟的"隔离室"中进行试运行，或者引入对抗机制来测试该工具在面对复杂、甚至恶意的用户输入时，是否会引发系统崩溃、数据泄露或模型失控。

- 包含平台：Anthropic、字节跳动 (Coze)、Google。

**三、 运行时监控与模型反思评判**

这类评判发生在上架之后，属于动态的、持续的质量考核。通过监控实际业务中大模型调用该 Skill 的成功率、报错率以及资源消耗，来决定该工具在集市中的生死存亡。

- 包含平台：OpenAI、Anthropic。

**四、 组织权限与数据边界审查**

- 这类审核主要面向企业内部应用场景，核心目标是防止 Agent 在调度工具时发生"越权访问"或突破内网数据隔离带。

- 包含平台：阿里 (钉钉)、微软 (Copilot)、Google。

#### 2.4 核心设计原则提炼

**原则一：强契约与语义确定性原则**

- 定义规范：Skill 必须被视为高度标准化的外挂函数，大模型是"意图路由引擎"。所有 Skill 强制采用标准的 JSON Schema 或 YAML 定义。

- 动作导向 (Action-Oriented)：工具命名（Name）必须是全局唯一且机器友好的英文动宾短语（如 query_employee_data）。描述（Description）必须使用祈使句，精准界定"此工具解决什么具体问题"，彻底杜绝过度营销或毫无业务价值的废话修饰。

- 硬性类型校验：严格区分"必填项（Required）"与"选填项（Optional）"。对于有固定取值范围的参数，强制使用 Enum（枚举值），绝不给大模型自由发挥或猜测的空间。

  **原则二：防御性边界与容错原则**

<!-- -->

- 负向提示墙 (Negative Prompts)：在 Skill 的元数据描述中，必须强制包含"使用禁区"。即明确写出"在什么情况下绝对不能调度此工具"（例如："如果需要查询跨年数据，请勿使用此工具"），以此物理阻断大模型的越界推理。

- 显式异常预期 (Explicit Error Handling)：默认工具调用存在失败率。开发者必须在描述中声明找不到数据或接口超时后的"兜底返回逻辑"（例如："如查无此人，请直接返回'未匹配到员工'，严禁自行推断同音字"），防止模型因凑齐参数而产生严重幻觉。

  **原则三：输入输出白盒化与清洗原则**

<!-- -->

- 双向契约：为了支撑后续"AI 裁判"的自动化质检，Skill 不仅要定义清晰的"入参（Parameters）"，更要定义明确的"出参（Returns Schema）"。质检的客观标准即为大模型输出是否完美契合 Returns Schema。

- 输出清洗 (Sanitization)：在 SkillHub 的网关层设立数据过滤机制。拦截不符合 Schema 的返回体，清洗掉冗余的超长 null 字段或潜在的恶意载荷，确保喂给大模型上下文的数据绝对纯净，防范前端指令注入。

  **原则四：多维漏斗式沙盒验证原则**

<!-- -->

- 沙盒强制跑通：拒绝纯静态的人工代码走查。任何 Skill 提交上架前，必须在平台的 Playground（沙盒）中至少成功调通一次，系统以此抓取真实的 Input/Output 固化为"黄金测试集（Golden Test Case）"。

- 交叉对抗质检：引入多基座模型作为"评审 Agent"，基于"指令遵循度、输出合规性、业务解决度"进行红蓝对抗打分。

- 运行时熔断监控：上线不是终点。系统需监控 Skill 的"无效请求率 (Invalid Request Rate)"与连通率，一旦因元数据描述歧义导致模型频频传错参数，系统自动执行降权或熔断下架。

  **原则五：组织权限感知与场景化隔离原则**

<!-- -->

- 动态权限穿透：Skill 的执行必须与企业内部的 SSO/IAM 鉴权打通。底层 API 网关需要隐式注入当前调用者的组织架构 ID 与角色 Token，防止普通员工通过 AI 越权查询敏感数据（如薪资、高管考勤）。

- 业务场景主导：在集市分发层面，摒弃按底层技术栈（Python/API/RPA）的极客分类法。强制以高度内聚的业务场景（如"财务审计"、"人力资源"、"运维监控"）建立分类树，扫除业务人员的认知障碍。

## 主流厂商Skill/Tool效果评判

#### 3.1 参考效果评判机制

**Anthropic (Claude)：业界最完善的 Agentic 评判体系**

Anthropic 是目前在"工具评测（Tool Evaluation）"领域公开工程化实践最深入的厂商。他们明确指出，评判一个 Skill/Tool 不能只看单次请求，而必须置于多轮对话的 Agent 循环中去评估。

- 分级评测体系 (Capability vs. Post-Listing Health Check)

<!-- -->

- 能力评测 (Capability Evals)： 针对新提交的 Skill，测试"大模型到底能不能用好这个工具"。这通常是一个带有挑战性的基准测试，初始通过率可能很低，用于探明工具描述的边界。

- 上架后健康检查 (Post-Listing Health Check；业界文献或 Anthropic 语境中或称 Regression Evals)： 当一个 Skill 跑通并上架后，系统定期重跑 Golden Case（非研发意义上的「回归测试」），要求通过率接近 100%，以监控底层 API 是否发生了暗中变更（Breaking changes）。

<!-- -->

- "三足鼎立"的打分器机制 (The Grader Triad) Anthropic 建议在评判流中混合使用三种裁判：

<!-- -->

- 代码打分器 (Code-based graders)： 速度快、成本低。直接写断言（Assertions）比对 JSON 格式、必填项缺失、以及底层 API 返回的 HTTP 状态码。

- 模型打分器 (Model-based graders / LLM-as-a-judge)： 用于评判"业务解决度"。例如，工具返回了 500 行数据，模型裁判需要评估执行 Agent 是否从中提取了正确的结论。

- 人类打分器 (Human graders)： 作为黄金标准，仅用于定期抽样，以此来校准"模型打分器"的准确度（防止 AI 裁判产生偏见）。

<!-- -->

- 强制思维链与反馈注入 (CoT & Feedback Injection) 在实际的自动评测工作流中，Anthropic 会强制 Agent 在输出最终调用指令前，先输出特定的 XML 标签：

<!-- -->

- \<summary\>：解释当前的任务步骤，以及为什么选择调用这个 Skill。

- \<feedback\>：如果在调用中发生错误，要求 Agent 反思是工具的名字太模糊、参数定义不清晰，还是 API 报错。

- 评判标准： AI 裁判不仅给最终结果打分，还会对这些 \<feedback\> 内容进行语义分析，从而反向给 Skill 的开发者提供修改建议（例如："参数 user_id 文档缺失，导致模型多次试错"）。

<!-- -->

- Transcript Auditing（审计原纪录）

<!-- -->

- Anthropic 强调，纯粹的分数是会骗人的。有时候打分器给了一个"Fail（失败）"，但如果去阅读原始调用日志（Transcript），会发现大模型其实用了一种极其聪明但出乎意料的方式组合了 Skill 解决了问题。因此，高质量的评判系统必须保留完整的 I/O 日志面板。

  **业界通用基准：BFCL (Berkeley Function Calling Leaderboard)**

  在开源界与 OpenAI 等厂商的底层能力测试中，加州大学伯克利分校发布的 BFCL 是目前衡量大模型 Function Calling 能力的绝对事实标准。他们的评判维度极具参考价值，主要分为两条路线：

<!-- -->

- AST 评测 (Abstract Syntax Tree Evaluation) - 静态遵循度

<!-- -->

- 不真实发起网络请求，而是将模型输出的 JSON 字符串解析为抽象语法树，与设定的 Schema 进行严格的参数匹配度检查。

- 考核点： 类型不匹配（Type Mismatch）、参数缺失（Missing Parameter）、幻觉参数（Hallucinated Parameter，即编造了 Skill 中根本不存在的入参）。

<!-- -->

- Executable 评测 (Executable Evaluation) - 动态有效性

<!-- -->

- 将大模型输出的参数实际代入沙盒环境中的 REST API 或 Python 函数去运行。

- 考核点： \* API Executability： 接口是否能走通，是否返回 200 状态码。

<!-- -->

- State Changes（状态变更）： 对于有副作用的写操作 Skill（如发邮件、建日程），系统会去查询底层数据库，验证副作用是否真实发生且正确。

  **OpenAI 与 Google 的核心评测导向**

<!-- -->

- OpenAI (Invalid Request Rate - IRR)

<!-- -->

- OpenAI 极其看重"无效请求率 (IRR)"。在 GPTs/Actions 的生态中，如果一个 Skill 的 Schema 描述写得很烂，导致模型经常传错参数格式，OpenAI 的后端不仅会记录这次失败，还会通过自动化的限流机制对该 Skill 进行隐性降权。

- 他们最近的对齐评测（Alignment Evaluation）中也强调，Skill 评测不仅是功能跑通，还要包含越权与拒绝测试（Refusal Testing）：即在评测集里故意混入"请帮我查询全公司薪资"的恶意 Prompt，评判模型是否能正确地拒绝调用某些敏感 Skill。

<!-- -->

- Google (Gemini Extensions)

<!-- -->

- 侧重于强类型闭环。因为 Google 原生支持 OpenAPI 3.0，他们的内部评测极度依赖预设的黄金测试集（Golden Test Set）。

- 如果返回的 JSON 嵌套层级深且包含非法枚举值（Enum violation），系统的底层网关（Gateway）会直接在运行时给该次调用打上"格式熔断"的极低评分。

#### 3.2 核心设计原则提炼

**原则一：双轨评测与沙盒执行原则 (Principle of Dual-Track Evaluation & Execution)**

- 规范提炼： 评判不能仅停留在静态代码扫描，必须结合"静态语法树（AST）校验"与"动态沙盒执行" 。在生命周期管理上，新入库技能需通过高难度的"能力评测（Capability Evals）"探明边界；已上架技能需定期进行"上架后健康检查（Post-Listing Health Check）"以监控底层 API 异动 。

- 考核红线： 静态扫描需排查类型不匹配与大模型"幻觉参数" ；动态执行必须真实发起调用，验证 HTTP 状态码及底层状态的真实变更 。

  **原则二：三维"裁判"协同评判原则**

- 规范提炼： 摒弃单一维度的打分，构建代码、大模型与人类协同的复合评判体系 。

- 机制设计： 基础参数和返回状态码交由低成本的"代码打分器 (Code-based graders)"实行秒级断言比对 ；业务结论的正确性交由"模型打分器 (Model-based graders)"进行语义评估 ；定期引入"人类打分器 (Human graders)"抽样复核，以校准模型裁判的偏差 。

  **原则三：全链路可观测与反馈闭环原则**

- 规范提炼： 评判系统不仅要给出"通过/失败"的结论，更要输出失败的"归因"。必须保留完整的 API 调用日志（Transcript Auditing），以防止纯粹的分数掩盖了模型执行的真实逻辑 。

- 机制设计： 强制要求"评审 Agent"在判定失败时输出 \<feedback\> 标签，指出是 Skill 命名模糊、参数缺失还是底层报错，反向为开发者提供精准的修改建议 。

  **原则四：红线越权测试与运行时熔断原则**

- 规范提炼： 评测体系必须包含防御性边界测试。向 Skill 注入恶意提示词，考核模型是否能准确执行"拒绝调用（Refusal Testing）"，防止敏感接口越权 。

- 机制设计： 引入"无效请求率 (Invalid Request Rate - IRR)"作为运行时核心指标 。若因描述含糊导致模型高频报错，或底层网关遭遇非法枚举值 ，系统需自动触发隐性降权或格式熔断机制 。

#### 3.3 评审Agent参考Prompt结构

基于 Anthropic 等头部厂商的工程实践，一个符合业界标准的评审 Agent Prompt 应包含以下模块：

```
<task>
定义评审目标，说明当前评审的 Skill 名称及预期功能。开发者填写，一句话描述，明确评审范围。

<thinking>
评审前的推导过程：为什么选择该 Skill、参数及来源。模型自主生成，开发者无需填充。

<criteria>
评审维度及权重——
指令遵循度（40%）：参数格式、必填/选填项是否符合 Schema；
输出合规性（30%）：返回体是否符合 Returns Schema、是否存在非法枚举值；
业务解决度（30%）：调用结果是否准确回应原始请求。

<summary>
一句话概括本次调用是否按预期执行。模型自主生成（如"Skill 按预期返回员工数据，参数匹配完整"）。

<feedback>
评审结论及失败归因。若未通过，须指出具体原因（如"参数 user_id 缺失""命名模糊导致误调其他工具"）。模型自主生成，包含 pass/fail 状态及原因。
```
