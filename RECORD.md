# RECORD — SkillHub MVP

> 总账文档：记录项目目标、决策与状态。Sprint 任务见 `.cursor_memory/active/SPRINT_skillhub-mvp.md`。

---

## 任务目标

构建 **SkillHub MVP**：面向全员的内部 Skill **分享、治理与使用** 平台——**重运营、重标准、低门槛**，而非单纯技术仓库。通过统一元数据规范、**多模型评审 Agent** 交叉验证的三维准入机制（指令遵循度 / 输出合规性 / 业务解决度），确立资产质量底线；并以业务场景化分类、自然语言交互（LUI）与数据驱动推荐，降低非技术员工使用门槛。

**四阶段设计路线**：① 准入规范与自动质检 → ② 闭环验证与评判调优（Capability + 上架后健康检查 + 使用反馈）→ ③ 前端交互与集市生态 → ④ 立项提案与商业价值呈现。

**当前交付边界**：阶段一文档定标已完成；阶段二 **2.0 + Phase 1（T1–T13）工程已收官**（**206 tests passing**，T8/T12 live + runbook）。**下一窗口**接续 **Phase 1 收尾（T14 UI 勾选）** 与 **BACKLOG 2.2–2.4**（对抗集、Prompt 校准、上架后健康检查）；**不重写** 1.2 阈值与 1.3 状态闸门。第一版以 `SKILL.md` 为主契约；R5 红线 case 分歧缩小**已明确不做 P0**（保留人工复核 + `skill_summary` 辅助）。独立 Portal / LUI 后置阶段三。

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

### Completed（阶段二 · Phase 1 — T1–T5）

- [x] **grill-me 8 项决策** 已锁定并写入 Phase 1 计划文末
- [x] **T1** 2.1-fix：Level0 结构/case gate 拆分；pre-confirm → `awaiting_confirm`；degraded 跳过 case gate
- [x] **T2** Gaps 引擎（`scan_gaps` + `required_actions` + confirmations）
- [x] **T3** `GET /bundle/{skill_id}/gaps` + 模板 + UI 补全台（confirm 后软 checklist）
- [x] **T4** 全终态轻量 report（`gaps[]` / `stage_progress[]` / timeout·fail 路径）
- [x] **T5** `provider_summary` 包级+per-case；专家台分歧快照；approve 回写 `human_review`

### Completed（阶段二 · Phase 1 — T6–T8 + Post-T8）

- [x] **Q-04 首版**：`testskills/` 三样本（stock-radar-V6.2、grill-me、tiered-memory-sprint-manager）
- [x] **Phase 1 实现计划**：[`docs/superpowers/plans/2026-06-03-phase2-eval-phase1.md`](docs/superpowers/plans/2026-06-03-phase2-eval-phase1.md) — **已收官**
- [x] **T6** 终态文案统一 + `stage_timing` 消费（API `timing_summary`、历史表得分/耗时列、详情模态）
- [x] **T7** 2.3a 时延（`core/latency.py`、Semaphore(3)、45s/90s high-risk、429/503 重试、workflow 300/600s、`stage_timing`）
- [x] **T8** testskills 三样本 live 验收 + [`docs/runbooks/testskills-phase1-validation.md`](docs/runbooks/testskills-phase1-validation.md)
- [x] **T9–T12** Post-T8 质量修复 + T12 live 复测（Q-10/Q-11 PASS）
- [x] **T13** warn 原因码（`WARN_COMPLETENESS_LOW` / `WARN_SCORE_MIDRANGE`）+ `skill_summary` AI 诊断摘要 + UI 三处接入

### To-Start（阶段二 · 下一窗口 — 按推荐顺序）

| 顺序 | 编号 | 内容 | 说明 |
|------|------|------|------|
| 0（可选收尾） | **T14** | UI 浏览器手工复测 | runbook §T13 + 原 UI 清单；`skillhub-eval serve` |
| 1 | **2.1b** | 存量 Skill 补齐 → `confirmed` + 全量复评 | tiered-memory 等：补 `eval_cases` 后复评；grill-me 完整度 warn→pass 路径 |
| 2 | **2.2** | 对抗性测试用例集 | 诱导偏差 / 不合规 Prompt；high-risk 样本验证拦截 |
| 3 | **2.3** | 对抗集跑通 + **打分方差 / Prompt 校准** | 用 T8/T12 DB + `stage_timing`；R5 红线口径属校准范畴，非紧急改码 |
| 4 | **2.4** | 自动分 vs 专家偏差 → 稳定阈值；上架后健康检查前瞻 | `eval_type: post_listing_health_check` 工程预留 |
| — | **Q-04** | 扩充基准 Skill 清单（3→5+） | 不阻塞 2.2 设计，阻塞更多 live 矩阵 |

### To-Start（阶段三 / 四）

- [ ] 场景分类、LUI、Trending（阶段三）
- [ ] 立项矩阵与 Demo 材料（阶段四）

---

## 进行中

| 事项 | 状态 |
|------|------|
| 阶段二 **2.0 + Phase 1（T1–T13）** | **✅ 工程收官**（206 tests；live runbook 已盖印） |
| 阶段二 **T14** UI 手工复测 | **待下一窗口勾选**（runbook §T13） |
| 阶段二 **2.2–2.4** | **待启动**（见上表；BACKLOG 与 Sprint 已对齐） |
| 运营向说明文档 | `docs/guides/Skill准入与评估机制说明.md`（与 1.2/1.3 对齐，供业务阅读） |

---

## 待解决问题

| ID | 问题 | 优先级 | 状态 |
|----|------|--------|------|
| Q-01 | 团队边界：设计 + demo Agent PoC | P0 | **已确认** |
| Q-02 | Skill 载体以 `SKILL.md` 为主 | P0 | **初定** |
| Q-03 | DeepSeek + Gemini；成本/并发 | P1 | **阶段二已落地（Gemini 替换 WorkBuddy）** |
| Q-04 | 首批 Skill 资产清单 | P1 | **首版已提供**（`testskills/` 三样本；可后续扩充） |
| Q-05 | 独立 Portal，当前不急 | P1 | **已确认** |
| Q-06 | 保留人工抽检 | P2 | **已确认** |
| Q-07 | 权重 40/30/30 | P2 | **暂定** |
| Q-08 | 场景分类一级词表 | P2 | 待共创 |
| Q-09 | 评估时延偏高导致 `EVAL_WORKFLOW_TIMEOUT` | P1 | **T8 复测通过**：stock-radar 9 case 全量 **48.8s**（high 预算 600s）；T7 Semaphore+分级 timeout 有效 |
| Q-10 | **DeepSeek 所有 case 恒定打 85 分** | P0 | **T12 live 通过**：stock-radar DS 分 `0/79/80.5/82`；grill-me `91.4–92.6`；无大面积同分锁死 |
| Q-11 | **三维打分字段全为 null**；`awaiting_confirm` / `degraded` 无诊断卡 | P1 | **T12 live 通过**：`model_votes.dimension_scores` 三维均有 0–100 值；A1 诊断卡 API + UI helper 验通 |
| Q-12 | **warn 原因不明确**（完整度不足 vs 分数中等）；pass/warn 均无 Skill 整体摘要 | P2 | **已解决**（T13）：warn 原因码 + `skill_summary` + UI 摘要卡 |
| Q-13 | **R5 频繁触发**（如 stock-radar DS/Gemini 红线 case 口径差）；增加人工复核负担 | P2 | **已决策暂缓工程改码**：用户确认不做 P0「缩小分歧」；2.3 Prompt 校准 + 人工 + `skill_summary` 为主路径 |
| Q-14 | **high-risk 长包 UI 跑评** 偶发双模型全超时、无分数 | P1 | **已缓解**：90s provider timeout + `EVAL_PROVIDER_UNAVAILABLE` 面板；T14 浏览器再验 |

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
| **Level0 拆分：pre-confirm 仅结构门禁，case gate 延至 confirm 后** | minimal 存量须先进 `awaiting_confirm` 交互补全，避免 Level0 直接 `RISK_CASE_COUNT_INSUFFICIENT` | 维持原顺序（case gate 在 awaiting_confirm 前，无法演示补全流） |
| **结构缺口（eval_cases/sample_io）UI 给模板、作者落盘后再评** | confirm API 只持久化元数据字段，不写目录；T3 模板 + runbook 闭环两 minimal 样本 | 自动 scaffold 写盘 API（本 Phase 1 不做，grill-me 可再议） |
| **R5 UI 展示包级 + per-case 双模型分数** | 专家复核需看见 DS/Gemini 分歧依据；`score_total=null` 仍保留 | 仅展示 null 或仅包级汇总（专家盲批） |
| **T5 `provider_summary` + 专家裁定回写** | 包级/per-case 双模型分；Δ≥15 浅红；`submit_review` 后 `report_json.human_review` 与 per-case 快照保留 | 仅 `score_total=null` 文案；裁定后丢弃分歧明细 |
| **T7 时延控制（grill-me Q2）** | `Semaphore(3)` 共享并发；provider **45s**（high-risk **90s**）；429/503 指数退避 max 3× base 1s；workflow **low/medium 300s、high 600s**；`stage_timing` 埋点 | 无并发上限挤爆 API；180s 一刀切；5xx 全量重试拖垮时延 |
| **warn 原因码与 Skill 摘要（T13）** | `DecisionStage.warn_reason_codes()` 区分完整度/分数 warn；Phase 5.5 Gemini 合成 `skill_summary`；UI `renderSkillSummaryCard` + `_warnReasonText` | 仅靠 `review_status=warn` 无文案；客户端拼接 feedback 无结构化摘要 |
| **R5 分歧缩小不做 P0（Q-13）** | 红线 case 模型哲学差属校准范畴；人工复核 + per-case 表 + `skill_summary` 支撑决策 | 本阶段改聚合/均分掩盖分歧（与 1.2 R5 契约冲突） |
| **T6 监控反射面：历史/详情消费 stage_timing** | `GET /eval/report` 暴露 `stage_timings` + `timing_summary`；历史表 `formatScoreCompact` + 耗时列；超时终态展示 `stage_progress` + 阶段条形图 | T8 live 数据仅落库、UI 静默（数据孤岛） |
| **研发交接：四阶段 MVP 全部完成后才交接 + 编写交接文档** | 当前仍在 MVP Demo 阶段；过早交接徒增文档维护成本 | 立项演示后即交接（MVP 尚未完整） |
| **Prompt 格式示例改用 `<integer 0-100>` 占位符，禁止照抄** | T8 live 实测发现 DeepSeek 字面遵循示例数值 85；占位符 + 评分段说明给模型语义锚定，无需具体数字 | 完全删除示例（缺结构引导→可能输出非法 JSON）；保留示例但只改数字（模型仍有锚定风险） |
| **三维权重 40/30/30 硬编码在 `_extract_score`** | 与 1.2 协议 §3 权重统一，单一真源；fallback 保留平均逻辑向后兼容 mock provider | 由 prompt 动态传权重（增加变量，测试困难） |
| **`check_providers.py` 同步修复示例分数** | 防止未来接入新模型时连通测试的示例值影响新模型打分锚定 | 不改（健康检查而已）|

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

## 下一窗口接续指引（阶段二 · 2.2–2.4 + T14）

### 新窗口开场句（可复制）

> 阶段二 **2.0 + Phase 1（T1–T13）已收官**（**206 tests**，T8/T12 live runbook）。本窗口：**T14** runbook UI 勾选（可选）→ **2.1b** 存量补齐复评 → **2.2** 对抗集 → **2.3** 方差/Prompt 校准 → **2.4** 上架后健康检查前瞻。必读 `RECORD.md`「当前状态·To-Start」、Sprint、[`docs/runbooks/testskills-phase1-validation.md`](docs/runbooks/testskills-phase1-validation.md)。**不重写** 1.2 阈值；**不做** R5 聚合改码（Q-13）。

### 已完成（勿重复实现）

| 范围 | 证据 |
|------|------|
| **2.0** 评估引擎 + UI + CLI | `skillhub_eval/` 六边形单仓；206 tests |
| **Phase 1 T1–T13** | gaps、R5 可视化、T7 时延、Post-T8 prompt、T13 warn 文案 + `skill_summary` |
| **2.1 首版样本** | `testskills/` 三样本 + T8/T12 矩阵 |
| **2.3a 时延** | 已并入 T7（非独立待办） |

### 必读（按顺序）

1. 本 `RECORD.md` — 「当前状态」「待解决问题」「已做决策」
2. [`.cursor_memory/active/SPRINT_skillhub-mvp.md`](.cursor_memory/active/SPRINT_skillhub-mvp.md)
3. [`.cursor_memory/backlog/BACKLOG.md`](.cursor_memory/backlog/BACKLOG.md)
4. [`docs/runbooks/testskills-phase1-validation.md`](docs/runbooks/testskills-phase1-validation.md) — T14 §T13
5. [`docs/specs/评审Agent工作流与Prompt骨架.md`](docs/specs/评审Agent工作流与Prompt骨架.md) v0.2
6. [`docs/specs/评估指标与准入标准.md`](docs/specs/评估指标与准入标准.md) v1.2.1
7. [`docs/guides/Skill准入与评估机制说明.md`](docs/guides/Skill准入与评估机制说明.md) — 业务向

### 推荐执行顺序

| 步骤 | 任务 | 验收 |
|------|------|------|
| 0 | **T14** UI 手工复测（可选） | runbook §T13 + 原 UI 清单全部 `[x]` |
| 1 | **2.1b** | tiered-memory / grill-me 补齐 `eval_cases` → confirmed 全量 → pass 或可追溯 warn |
| 2 | **2.2** | 对抗 case YAML + 接入 `eval_cases`；high-risk 可演示拦截 |
| 3 | **2.3** | 跑对抗集；方差报告；Prompt 迭代（含红线 `case_type_hint`，**不改 R5 聚合**） |
| 4 | **2.4** | 专家偏差表；`post_listing_health_check` 数据模型/API 草图 |

### 硬约束（仍有效）

1. **PASS** 仅 `confirmed` + `capability_full`。
2. **R5** → `score_total = null`，禁止均分掩盖。
3. **降级**未确认 draft 不参与 CodeAssert 失败。
4. 校准结论写入文档/配置，**不**在 2.3 中静默改 1.2 正文。

### 勿做

- 重复 Phase 1 工程（T1–T13）。
- P0 级「强制缩小 R5 分差」改聚合（Q-13）。
- 阶段三 Portal / LUI / Q-08 词表。

---

## 参考资料

| 资源 | 路径 |
|------|------|
| 项目背景 | `docs/Project-Background.md` |
| **评估指标与准入标准（权威）** | `docs/specs/评估指标与准入标准.md` |
| **评审 Agent 工作流与 Prompt** | `docs/specs/评审Agent工作流与Prompt骨架.md` |
| 元数据与上架协议 | `docs/specs/Skill元数据定义与编写规范.md` |
| 开发者编写指南 v1.0 | `docs/guides/Skill编写指南.md` |
| Skill 准入与评估机制说明（业务向） | `docs/guides/Skill准入与评估机制说明.md` |
| Skills 评估标准说明 | `docs/guides/Skills评估标准说明.md` |
| Post-T8 质量修复计划 | `docs/superpowers/plans/2026-06-03-prompt-quality-improvement.md` |
| testskills live runbook | `docs/runbooks/testskills-phase1-validation.md` |
| **阶段二工程化设计 Spec** | `docs/superpowers/specs/2026-06-02-phase2-eval-engine-design.md` |
| 竞品调研 | `docs/research/Skill数据定义与编写规范调研.md` |
| 架构 | `.cursor_memory/global/ARCHITECTURE.md` |
| Active Sprint | `.cursor_memory/active/SPRINT_skillhub-mvp.md` |
| Backlog | `.cursor_memory/backlog/BACKLOG.md` |
| Skill 样例参考 | `../个股诊断/Skill/stock-radar-V6.2/` |
| **Phase 1 实现计划** | `docs/superpowers/plans/2026-06-03-phase2-eval-phase1.md` |
| testskills 样本库 | `testskills/`（stock-radar-V6.2、grill-me、tiered-memory-sprint-manager） |

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
| 2026-06-02 | **阶段二运行验证补记**：`.env` 双模型连通性复测通过；`stock-radar-V6.2` 补齐至 high-risk 用例门槛；UI 增强 timeout 根因可见（回退展示顶层 `reason_codes`）；发现 `confirmed + capability_full` 仍有 `EVAL_WORKFLOW_TIMEOUT`，已并入 **2.3a 时延优化** |
| 2026-06-02 | **阶段二下一窗口待办**：Sprint/RECORD 增补 **2.3b**（`awaiting_confirm`/timeout 轻量 report + UI 结构阶段展示）；Handoff 开场句更新为 2.1–2.4 优化接续 |
| 2026-06-03 | **Phase 1 计划定稿**：Q-04 首版 `testskills/` 三样本；T1–T8 计划写入 `docs/superpowers/plans/2026-06-03-phase2-eval-phase1.md`；T8 含 minimal 补全后全量闭环；R5 per-case 可视化；**grill-me gate 后执行** |
| 2026-06-03 | **Phase 1 T1–T5 交付**：Level0 拆分 + gaps/API/UI；全终态 report；`provider_summary` + 专家台 per-case；`formatScoreDisplay` 提前覆盖部分 T6；修复 `scan_gaps` 导入；**185 tests** |
| 2026-06-03 | **路由决策**：跳过 T6 扫尾，优先 **T7 时延承重墙**；T6 历史表对齐置于 T7 之后，与 `stage_timing`/残缺分一并消费 |
| 2026-06-03 | **Phase 1 T7 交付**：`core/latency.py` + `providers/http_retry.py`；case `Semaphore(3)` 并行评审；risk 分级 workflow 300/600s；provider 45s + 429/503 重试；`stage_timing` / per-case 埋点；**191 tests** |
| 2026-06-03 | **路由：T6 先于 T8**；**T6 交付**：`core/stage_timing.py`；report/history API 聚合时延；UI 历史得分/耗时列 + 详情阶段条形图 + 超时轨迹 |
| 2026-06-03 | **Phase 1 T8 live 收官**：三样本矩阵实测写入 runbook；grill-me 最小补全包落盘；stock-radar 48.8s 无 timeout；R5+Approve 回写验通 |
| 2026-06-03 | **T8 Live 质量反馈 & 优化计划**：发现 P0（DeepSeek 恒定 85，根因 `_build_prompt` 示例污染）、P1（三维字段全 null，`DimensionScores()` 传空 + prompt 仅含 `step_completeness`）、P2（UI 无诊断报告卡）；Prompt 全域审计完成，`check_providers.py` 同为污染点；优化计划立项 [`docs/superpowers/plans/2026-06-03-prompt-quality-improvement.md`](docs/superpowers/plans/2026-06-03-prompt-quality-improvement.md)；Q-10/Q-11 录入问题表 |
| 2026-06-03 | **Post-T8 Fix-1–4 交付**：`engine._build_prompt` 占位符三维 rubric + SKILL 摘录；`_extract_score` 40/30/30；`dimension_scores_from_sub_scores`；`check_providers` 去固定分；UI 结构诊断卡 + per-case 反馈/三维；**201 tests** |
| 2026-06-03 | **T12 live 收官**：`t8_live_validation.py` 矩阵复跑（stock-radar 58.8s，R5+Approve）；`t12_audit.py` Q-10/Q-11 **PASS**；`t12_ui_smoke.py` Fix-4 **PASS**；Phase 1 工程收官 |
| 2026-06-03 | **T13 交付**：P2 warn 原因码 + `skill_summary` Phase 5.5 合成 + UI 诊断摘要卡；provider 全失败显式 `EVAL_PROVIDER_UNAVAILABLE`；high-risk 90s call timeout；**206 tests** |
| 2026-06-03 | **阶段二 Phase 1 Handoff**：RECORD/Sprint/BACKLOG 对齐；下一窗口 **T14（可选）→ 2.1b → 2.2 → 2.3 → 2.4**；Q-13 R5 缩小暂缓；Handoff 节重写；增补 `Skill准入与评估机制说明.md` 引用 |
