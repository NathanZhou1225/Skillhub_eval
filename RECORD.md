# RECORD — SkillHub MVP

> 总账文档：记录项目目标、决策与状态。Sprint 任务见 `.cursor_memory/active/SPRINT_skillhub-mvp.md`。

---

## 任务目标

构建 **SkillHub MVP**：面向全员的内部 Skill **分享、治理与使用** 平台——**重运营、重标准、低门槛**，而非单纯技术仓库。通过统一元数据规范、**多模型评审 Agent** 交叉验证的三维准入机制（指令遵循度 / 输出合规性 / 业务解决度），确立资产质量底线；并以业务场景化分类、自然语言交互（LUI）与数据驱动推荐，降低非技术员工使用门槛。

**四阶段设计路线**：① 准入规范与自动质检 → ② 闭环验证与评判调优（Capability + 上架后健康检查 + 使用反馈）→ ③ 前端交互与集市生态 → ④ 立项提案与商业价值呈现。

**当前交付边界**：阶段一以**文档探索**为主，跑通评估 Agent **设计基线**；阶段二已完成**工程搭建**（DeepSeek + Gemini、断言引擎、交互补全 UI，152 tests passing）。第一版以 `SKILL.md` 为主契约；混合最小版（有脚本→沙盒，无脚本→样例 I/O）；人工抽检保留；独立 Portal 后置。

---

## 当前状态

### Completed

- [x] 竞品调研 `docs/research/Skill数据定义与编写规范调研.md`（Task **1.1**）
- [x] 项目背景 `docs/Project-Background.md`；`.cursor_memory/` + `ARCHITECTURE.md`
- [x] 评估/上架协议 `docs/specs/Skill元数据定义与编写规范.md` **v0.5**（含 §14 流程、§6.4 断言语法、§14.6 risk 锁定；对齐 1.3 v0.2）
- [x] 开发者编写指南 **v1.0** `docs/guides/Skill编写指南.md`（作者优先、运营共用；含最小作者包、写法标准、退回处理、模板、Golden Case 规划）
- [x] Task **1.2** 定稿：`docs/specs/评估指标与准入标准.md` **v1.2.1**（评分唯一权威；v1.2.1 仅补结构化输出/1.3 交叉引用，阈值不变）
- [x] Task **1.3 定稿** `docs/specs/评审Agent工作流与Prompt骨架.md` **v0.2 Architecture Contract**（包状态、评估模式、A/B/C/D 编排、Prompt/Schema、`reason_code`、人工抽检与运营解释层；协议/评估标准已补交叉引用）

### Completed（阶段二 · 2.0 评估引擎）

- [x] **2.0** 评估引擎工程实现全部完成（Tasks 1–12，152 tests passing）
  - 六边形单仓架构（`core / adapters / providers / persistence`）
  - 评估状态机引擎（`EvaluationEngine`），C-3 两阶段执行，180s 超时熔断
  - DSL 断言引擎（`core/assert_/dsl.py`），实现协议 §6.4 全部操作符及扩展集
  - DeepSeek + **Gemini**（已替换 WorkBuddy）双模型评审，`BaseLLMProvider` 抽象
  - SQLite 持久化（评估轮次、阶段日志、模型投票、缺口、人工抽检动作）
  - FastAPI 薄适配层（6 个端点，Living Contract），`BackgroundTasks` 异步 Job
  - Typer CLI（`run / status / history / confirm / serve`）
  - 极简双 Tab 确认台 UI（`index.html`，Vanilla JS + Tailwind CDN）
  - 全量 TDD，覆盖 R1–R8、§14 Checklist、C-1~C-6 所有修正项；E2E Smoke 17 用例

### In-Progress（阶段二 · 当前窗口）

- [ ] Q-04 首批真实 Skill 资产清单（阶段二 2.1 样本库前置输入）

### To-Start（阶段二 · 待样本输入后启动）

- [ ] **2.1** 样本库（用户指定常用/自用 Skill；先降级评估）
- [ ] **2.2** 对抗性测试用例集 · **2.3** 校准 · **2.4** 上架后健康检查 + 使用反馈

### To-Start（阶段三 / 四）

- [ ] 场景分类、LUI、Trending（阶段三）
- [ ] 立项矩阵与 Demo 材料（阶段四）

---

## 进行中

| 事项 | 状态 |
|------|------|
| 文档三分离（指南 / 协议 / 评估标准 + 1.3 工作流） | **1.3 v0.2 架构契约完成** |
| Task 1.2 评估指标与准入 | **v1.2.1 定稿**（含上架后健康检查术语；补 1.3 输出契约引用） |
| Task 1.3 评审工作流与 Prompt | **v0.2 Architecture Contract 定稿** |
| 编写指南 v1.0 | **已完成**（真实样本清单 Q-04 后续补充） |
| 阶段二工程 / 样本跑通 | Backlog |

---

## 待解决问题

| ID | 问题 | 优先级 | 状态 |
|----|------|--------|------|
| Q-01 | 团队边界：设计 + demo Agent PoC | P0 | **已确认** |
| Q-02 | Skill 载体以 `SKILL.md` 为主 | P0 | **初定** |
| Q-03 | DeepSeek + Gemini；成本/并发 | P1 | **阶段二已落地（Gemini 替换 WorkBuddy）** |
| Q-04 | 首批 Skill 资产清单 | P1 | **待用户提供** |
| Q-05 | 独立 Portal，当前不急 | P1 | **已确认** |
| Q-06 | 保留人工抽检 | P2 | **已确认** |
| Q-07 | 权重 40/30/30 | P2 | **暂定** |
| Q-08 | 场景分类一级词表 | P2 | 待共创 |

---

## 已做决策

| 决策 | 理由 | 排除的方案及原因 |
|------|------|------------------|
| **MVP 定位为运营型内部产品** | 对齐门槛/碎片/质量痛点 | 纯技术仓库 |
| **评估尺子 + 入库前补齐** | 最小作者包 + Agent 缺口扫描 + 交互补全 | 全员创作即写满 |
| **评估对象 = Skill 包质量** | 可复现、可对比 | 以单次 Agent 调用链为主评分 |
| **质量分与完整度分解耦** | `score_total` 仅三维；`completeness_score` 独立控制阀 | 混合总分 |
| **双模型未触发 R5 时** `score_total = mean(DS, WB)` | 可展示单一质量分用于阈值 | 强制平均掩盖分歧 |
| **触发 R5 时** `score_total = null` | 保留分歧，人工裁决 | 聚合 pass |
| **红线 case 仅否决、不参与均分** | refusal/adversarial 失败→整包 FAIL | 纳入均分稀释 |
| **非红线 case 等权平均** | happy + edge | 红线参与能力分 |
| **Level 0 失败 → 整包 FAIL** | 契约破裂不耗评审算力 | 仍评三维 |
| **low risk + Level 1 可 PASS** | 降低文本类 Skill 摩擦 | 强迫低风险走沙盒 |
| **中/ high 须 Level 2 才 PASS** | 真实执行验证 | 仅 sample 即 pass |
| **risk_level 在 Level 0 后锁定** | 用例数先校验，避免评完再抬高 | 评审中动态改 risk |
| **完整度 Checklist 扣分；草案=已填项免扣** | 可代码化 | Agent 主观完整度 |
| **安全字段任一项 draft 未确认 → cap 89** | 水桶效应 | 仅三项都 draft 才 cap |
| **双低（完整度&质量均&lt;70）→ FAIL** | 减少 WARN 堰塞湖 | 双低仍 WARN |
| **行业拦截器：通用机制 + 规则包** | 金融等作配置示例 | 写死在 rubric |
| **断言语法 DSL（协议 §6.4）** | 代码断言可执行 | 模型理解断言 |
| **Capability Eval（阶段一文档）+ 上架后健康检查（阶段二）** | 首次准入 vs 上架后 Golden Case 监控 | 仅 Capability |
| **术语：上架后健康检查** | 避免与研发「回归测试」混淆；英文 Post-Listing Health Check；`eval_type`: `post_listing_health_check` | 沿用 Regression Eval 旧称 |
| **1.2 为评分权威；协议 §9 仅导读** | 单源阈值 | 双份 §9 全文 |
| **1.3 升级为 Architecture Contract 主控文档** | 阶段二工程需统一状态、Prompt、Schema、`reason_code` 与人工抽检接口 | 继续停留在 Prompt 骨架，工程实现各自补 if-else |
| **PASS 状态闸门：`bundle_state=confirmed` + `evaluation_mode=capability_full`** | 防止未确认 draft 或降级评估被人工/模型绕过直接上架 | 仅靠人工 approve 覆盖 warn |
| **降级评估中未确认 `draft_value` 不参与代码断言失败判定** | 避免规范化草案污染 CodeAssert，使存量摸底误报 fail | 用 Agent 草案作为正式 schema 直接断言 |
| **数据层驱动运营解释层** | `reason_code/evidence/required_actions` 生成话术，保持裁决可追溯 | 运营话术反向改 `review_status` |
| **DeepSeek + Gemini；人工抽检** | WorkBuddy 替换为 Gemini（OpenAI 兼容端点，markdown 代码围栏自动剥离）；已落地 | 全自动上架 |
| **独立 Portal 后置** | 先质量底座 | 先做 UI |
| **阶段二仓库形态：六边形单仓**（`core/adapters/providers/persistence`） | 内核无 FastAPI/SQLite 依赖，四阶段后研发可只换 adapter；避免 PoC 即抛弃 | 扁平单包（难拆）；多包 workspace（阶段二过重） |
| **执行模型：轻量异步 Job（BackgroundTasks）** | 防止 L2+双模型超 60s 超时；完美彩排生产异步架构；SQLite 状态流转支撑 2.3 分析 | 同步阻塞（Swagger 易 504）；混合模式（分支复杂） |
| **LLM：live 默认 + `BaseLLMProvider` 抽象** | 2.3 打分方差需真实数据；Provider 层统一治理 retry/限流 | 纯 mock（无真实分歧）；单模型 stub（双模型聚合失真） |
| **沙盒：subprocess + 仅 Python + 非 Python 降级 L1** | Windows 本地友好；内部白名单样本无逃逸风险；PoC 专注编排验证 | Docker（Windows 冷启动贵；吃超时预算） |
| **交互补全：极简确认台（Vanilla JS + Tailwind）** | "Aha Moment" 演示 AI 拦截 → 草案 → 人确认 → 闭环；1–2 天前端量；Swagger 无法演示给业务方 | API-only（工程师向）；手改文件（丧失智能化体验） |
| **Case 数量：X1 分 risk 上限（low 6 / medium 8 / high 12）** | 防止 high risk 9 用例与全局 8 上限数学冲突；2.2 对抗集需 high risk 验证 | 全局 8 上限（阶段二无法评 high risk，立项演示丢失拦截能力展示） |
| **研发交接：四阶段 MVP 全部完成后才交接 + 编写交接文档** | 当前仍在 MVP Demo 阶段；过早交接徒增文档维护成本 | 立项演示后即交接（MVP 尚未完整） |

---

## 关键约束

1. **阶段一**：文档定标（1.1–1.3 + 指南 v0.1）；**不**实现完整 Agent 编排与 Portal。
2. **阶段二**：工程实现 + 样本 Capability / 上架后健康检查跑通。
3. **创作 vs 上架**：日常最小作者包；上架前可评估包 + 准入结论。
4. **存量路径**：降级评估（WARN）→ 补齐 → 完整复评 → PASS。
5. **埋点**：评估标准附录 C + 1.3 检查清单（失效场景：裁判洁癖、草案疲劳、拦截器误杀）。
6. **1.3 状态闸门**：人工抽检、模型聚合与运营解释均不得绕过 `confirmed` 包状态直接 PASS。
7. **降级断言边界**：未确认 draft 只用于缺口提示/低置信度评审，不作为 CodeAssert 失败依据。

---

## 阶段一收官说明

**阶段一（标准建立与架构设计）文档侧已完结。** 已完成：1.1 协议 v0.5、1.2 评估标准 v1.2.1、1.3 Architecture Contract v0.2、1.1b 编写指南 v1.0。未完成项不阻塞阶段二：**Q-04** 真实样本清单、Golden Case 实填、可选纸面降级评估——归入阶段二 2.1 及样本验证。

---

## 下一窗口接续指引（阶段二 · Agent 评估体系）

### 新窗口开场句（可复制）

> 阶段一已收官。本窗口启动**阶段二**：基于 [`评审Agent工作流与Prompt骨架.md`](docs/specs/评审Agent工作流与Prompt骨架.md) **v0.2 Architecture Contract** 做 Agent 评估体系**工程设计与实现**；先 brainstorm + grill-me 定稿，再编码与样本验证。**不重写** 1.2 评分 rubric 与 1.3 状态闸门。

### 必读（按顺序）

1. 本 `RECORD.md`（尤其「已做决策」「关键约束」）
2. [`.cursor_memory/backlog/BACKLOG.md`](.cursor_memory/backlog/BACKLOG.md) — 阶段二 Task 2.0–2.4
3. [`docs/specs/评审Agent工作流与Prompt骨架.md`](docs/specs/评审Agent工作流与Prompt骨架.md) **v0.2** — **阶段二实现主入口**（编排 A/B/C/D、Schema、`reason_code`、§14 检查清单）
4. [`docs/specs/评估指标与准入标准.md`](docs/specs/评估指标与准入标准.md) **v1.2.1** — 评分与 R1–R8 权威（只引用，不改阈值）
5. [`docs/specs/Skill元数据定义与编写规范.md`](docs/specs/Skill元数据定义与编写规范.md) **v0.5** — 包结构、DSL §6.4、§14 流程
6. [`docs/guides/Skill编写指南.md`](docs/guides/Skill编写指南.md) **v1.0** — 作者/运营人类语言版

### 阶段一已交付（勿重复造轮子）

| 文档 | 版本 | 角色 |
|------|------|------|
| 评估指标与准入标准 | v1.2.1 | 评分尺子、红线、准入矩阵 |
| 元数据与上架协议 | v0.5 | 目录、Schema、DSL、端到端流程导读 |
| 评审 Agent 架构契约 | v0.2 | 工程编排、Prompt、输入输出、人工抽检 |
| Skill 编写指南 | v1.0 | 作者/运营操作手册 |

### 阶段二目标与推荐节奏

**目标**：工程实现评估 Agent 体系（规范化 + 风险复核 + 双模型评审 + 代码断言 + 聚合层），并用 3–5 个真实 Skill 跑通 Capability Eval（含降级评估 → 补齐 → 复评）。

| 步骤 | 动作 | 产出 |
|------|------|------|
| 1 | **Brainstorm** | 模块边界、技术栈、存储/编排形态（脚本 vs 服务） |
| 2 | **Grill-me** | 压测：PASS 闸门、人工 approve 边界、降级 CodeAssert、R5 聚合 |
| 3 | **设计定稿** | 阶段二实现设计稿（建议单独 md，对照 1.3 §14） |
| 4 | **实现 2.0** | 编排引擎 + 断言引擎 + DS/WB 调用 + 结构化输出 |
| 5 | **验证** | 对照 1.3 §14 检查清单逐项勾选；至少 1 个样本端到端 |
| 6 | **2.1–2.4** | 样本库、对抗集、校准、上架后健康检查前瞻 |

### 实现时必须遵守的硬约束（来自 1.3）

1. **PASS 仅当** `bundle_state = confirmed` 且 `evaluation_mode = capability_full`。
2. **人工 approve 不得绕过** 未确认 draft 直接 PASS。
3. **降级模式下** 未确认 `draft_value` 不作为 CodeAssert 失败依据。
4. **R5 触发时** `score_total = null`，禁止用均分掩盖分歧。
5. **三类 Prompt 分离**：规范化 / 风险复核 / 质量评审，禁止单 Agent 包办。
6. **数据层驱动解释层**：`reason_code` → 运营话术；话术不得反向改 `review_status`。

### 阶段二任务清单（BACKLOG 摘要）

- **2.0** Agent 评估体系架构与实现（对照 1.3 §14）
- **2.1** 遴选 3–5 个基准 Skill（**Q-04**；先降级评估）
- **2.1b** 存量补齐 → 完整复评
- **2.2** 对抗性测试用例集
- **2.3** 对抗集跑通与拦截率记录
- **2.4** 自动分 vs 专家偏差 → Prompt/权重校准

### 待输入（不阻塞设计，阻塞 2.1 首跑）

| ID | 内容 | 说明 |
|----|------|------|
| **Q-04** | 首批 Skill 资产清单 | 常用/自用 Skill 名称与路径 |
| **Q-03** | DeepSeek / Gemini 成本与并发 | 阶段二已细化 |
| **Q-08** | 场景分类一级词表 | 阶段三，本阶段可忽略 |

### 勿做

- 不重写 1.2 三维权重与 R1–R8 阈值（校准放 2.4）。
- 不把 1.3 契约再拆成多套 if-else 口径。
- 阶段二 MVP 不做完整 Portal / LUI（阶段三）。

---

## 参考资料

| 资源 | 路径 |
|------|------|
| 项目背景 | `docs/Project-Background.md` |
| **评估指标与准入标准（权威）** | `docs/specs/评估指标与准入标准.md` |
| **评审 Agent 工作流与 Prompt** | `docs/specs/评审Agent工作流与Prompt骨架.md` |
| 元数据与上架协议 | `docs/specs/Skill元数据定义与编写规范.md` |
| 开发者编写指南 v1.0 | `docs/guides/Skill编写指南.md` |
| Skills 评估说明（可选） | `docs/guides/Skills评估说明.md` |
| **阶段二工程化设计 Spec** | `docs/superpowers/specs/2026-06-02-phase2-eval-engine-design.md` |
| 竞品调研 | `docs/research/Skill数据定义与编写规范调研.md` |
| 架构 | `.cursor_memory/global/ARCHITECTURE.md` |
| Active Sprint | `.cursor_memory/active/SPRINT_skillhub-mvp.md` |
| Backlog | `.cursor_memory/backlog/BACKLOG.md` |
| Skill 样例参考 | `../个股诊断/Skill/stock-radar-V6.2/` |

---

## 变更流水

| 日期 | 变更 |
|------|------|
| 2026-06-01 | 初版 RECORD；四阶段拆分；`.cursor_memory/` 初始化 |
| 2026-06-01 | 评估 demo 边界、规范分层、编写指南 v0.1、Task 1.1 协议 |
| 2026-06-01 | Task 1.2 v1.0；协议 v0.2–v0.3 |
| 2026-06-01 | Claude 评估报告：v1.1 评估标准、v0.4 协议、1.3 v0.1 骨架 |
| 2026-06-01 | **RECORD 对齐新窗口**：1.2/1.3 骨架完成；1.3 定稿 Handoff；决策表扩充 |
| 2026-06-01 | **术语统一**：Regression Eval / 回归评测 → **上架后健康检查**（Post-Listing Health Check）；Level 3 改称「上架后运行时监控」 |
| 2026-06-02 | **Task 1.3 v0.2 定稿**：评审 Agent 工作流升级为 Architecture Contract；补 A/B/C/D 编排、状态闸门、`reason_code`、人工抽检、降级断言边界，并完成协议 v0.5 / 评估标准 v1.2.1 交叉引用 |
| 2026-06-02 | **Task 1.1b 完成**：`Skill编写指南.md` 升级为 v1.0；面向作者与运营，补最小作者包、5 项写法标准、退回处理、运营追问、模板与 Golden Case 规划 |
| 2026-06-02 | **阶段一收官**：文档定标完成；新增「阶段二 Handoff」接续指引 |
| 2026-06-02 | **阶段二 Brainstorm 定稿**：六边形单仓 + 异步 Job + live LLM Provider + subprocess 沙盒 + 双 Tab 确认台 + Case X1；design spec 写入 `docs/superpowers/specs/`；Implementation Plan 产出中 |
| 2026-06-02 | **阶段二 2.0 工程实现完成**：Tasks 1-12 全部完成，152 tests passing。引擎状态机（C-3 两阶段 + 180s 超时）、DSL 断言引擎（§6.4 全操作符）、SQLite 持久化、FastAPI 6 端点、Typer CLI、极简双 Tab UI 全部联通；**WorkBuddy 替换为 Gemini**（\providers/gemini.py\uff0cOpenAI 兼容端点） |
