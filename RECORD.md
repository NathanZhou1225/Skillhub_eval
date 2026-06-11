# RECORD — SkillHub MVP

> 总账文档：记录项目目标、决策与状态。阶段二 Sprint 已归档：`.cursor_memory/archive/SPRINT_skillhub-mvp_completed.md`；阶段三待新建 `active/SPRINT_*.md`。

---

## 任务目标

构建 **SkillHub MVP**：面向全员的内部 Skill **分享、治理与使用** 平台——**重运营、重标准、低门槛**，而非单纯技术仓库。通过统一元数据规范、**多模型评审 Agent** 交叉验证的三维准入机制（指令遵循度 / 输出合规性 / 业务解决度），确立资产质量底线；并以业务场景化分类、自然语言交互（LUI）与数据驱动推荐，降低非技术员工使用门槛。

**四阶段设计路线**：① 准入规范与自动质检 → ② 闭环验证与评判调优（Capability + 上架后健康检查 + 使用反馈）→ ③ 前端交互与集市生态 → ④ 立项提案与商业价值呈现。

**当前交付边界**：阶段一文档定标 ✅；阶段二 **全量收官** ✅（220 tests）；阶段三 **W0** ✅（235）、**W1** ✅（250）、**W2** ✅（292）、**W3** ✅（328）、**W4 LUI Agent** ✅（367）、**W5 Chat-First 对话壳** ✅（400）、**W5.1 聊天简卡 + 报告分流** ✅（413）、**W5.2 UI 透明化** ✅（447）、**W5.3 智能对话 + LLM 补题计划** ✅（472）、**W5.3.1 Demo 热修** ✅（475）、**W5.3.2 评估门禁 + 自动正式评估** ✅（478 tests）。**不重写** 1.2 准入阈值（85/70/90）。**当前主线：W5.5 本地 Demo 验收**（stock-radar 实机彩排 + runbook）。阶段二可选收尾已取消。

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
- [x] **T14** UI 浏览器手工复测（runbook §T13 + 原 UI 清单；用户 2026-06-05 确认收官）

### Completed（阶段二 · 剩余任务 2.1b–2.6 + 2.4）

- [x] **2.1b** tiered-memory 补齐（3 case + sample_io）→ `confirmed + capability_full` live（67s，`awaiting_human_review`/`warn`，`MODEL_DISAGREEMENT_R5`）
- [x] **2.3b** `report_narrative.py` + `docs/guides/报告呈现规范.md` — `headline_zh` / `reasons_zh` 进 report + UI
- [x] **2.3c** `disagreement_brief_zh` 确定性分歧卡 + UI `renderDisagreementCard`
- [x] **2.2** stock-radar high-risk 9 case（h/e/r/a）落盘 + `adversarial_case.yaml.tpl`
- [x] **2.3** `scripts/variance_report.py` + Prompt `case_type_hint` 强化（脚本已备；Markdown 导出**不做**，阶段三覆盖）
- [x] **2.5** AI 风险复核 Step ③（**DeepSeek** `ds_provider`）；`max(自报,规则,AI)` + `RiskLockProvenance` UI
- [x] **2.6** `average_pool` / `redline_pool` 拆分；`REDLINE_MODEL_DISAGREEMENT`；`score_total_source=average_pool_mean`
- [x] **2.4** ADR `post-listing-health-check` + `scripts/expert_bias_table.py`
- [x] **T8 live 复跑**（2026-06-05，`data/t8_validation.db`）：stock-radar 65.2s，R5 + 红线模型分歧 + Approve 回写
- [x] **UI 入口修复**：`/` → `/ui/index.html` 重定向；启动提示区分确认台与 `/docs`

### Completed（阶段二 · UI 体验改进 `ui-ux-improvement`）

- [x] **UI 手工验收**（2026-06-05）：用户确认无阻塞问题
- [x] Level0 中文诊断详情 + `REASON_ZH` 原因码映射
- [x] 专家台/历史模态：运营结论、分歧说明、风险溯源三张卡（per-case 表之前）
- [x] Approve 后 `build_report_narrative` 重建 + DS/GM 参考分展示
- [x] per-case 三维中文标签 + feedback 80 字截断折叠 + Gemini 不可用横幅
- [x] `skill_summary` 视觉重构（亮点/不足双列）；报告 UI 隐藏阶段耗时
- [x] Prompt v0.4：per-case reason/dimension_notes 中文简洁约束
- [x] **220 tests passing**；change 归档至 `openspec/changes/archive/2026-06-05-ui-ux-improvement/`

### Cancelled（阶段二 · 可选收尾 — 用户决定不做）

| 编号 | 原内容 | 取消理由 |
|------|--------|----------|
| **2.3 导出** | `variance_report.py` → `docs/runbooks/variance-*.md` | 阶段三 eval_case 自动生成与校准回路将覆盖方差分析需求；脚本保留备查即可 |
| **A2 环境** | grill-me 未落盘硬防线复测 | 阶段三自动生成 eval_case 后，手工「未落盘」场景不再作为验收主线 |

### Completed（阶段三 · Wave 3 Staging Case Propagator `wave3-propagator`）

- [x] **W3** Staging Case Propagator + 题型完整性门槛 + `POST /conversations/start`（OpenSpec 归档 `openspec/changes/archive/2026-06-09-wave3-propagator/`）
  - `core/schemas/enums.py`：`VALID_CASE_TYPES` + `CASE_TYPE_REQUIREMENTS`（low=3 happy；medium=3h+2e；high=3h+2e+2r+2a）
  - `core/level0.py`：`check_case_gate` 新增类型覆盖检查 → `MISSING_REQUIRED_CASE_TYPES`；返回 `type_coverage` 字段
  - `core/schemas/report.py`：`EvaluationReport` 新增 `case_type_coverage: dict[str, int]`
  - `core/case_sanitizer.py`：`CaseSanitizer`（损坏 case 移至 `_broken/`；type gap 计算；`invalid_type_count` 隔离无效类型）
  - `core/propagator.py`：`CasePropagator`（ds_provider LLM 按类型生成 case YAML + sample_io stub；服务端强制 id；fallback 占位降级）
  - `providers/deepseek.py`：新增 `generate(prompt)` async 方法
  - `adapters/api/routes/conversations.py`：`POST /conversations/start`（Security→Sanitizer→Propagator→re-ingest→post-scan→R_101 degraded；202 Accepted）
  - `core/engine.py`：ingest 后填充 `case_type_coverage`
  - **328 tests passing**（+36 Wave 3 测试，零回归）
  - grill-me 三题锁定：① adversarial 降级方案 A；② type check 留在 check_case_gate；③ invalid_type_count 不计入 existing_counts
  - **Review 修复**：Propagator 后 re-ingest + 重跑 security_scan（blocked→422）；LLM case id 服务端分配；`level0.check()` 补 `type_coverage`

### Completed（阶段三 · Wave 2 安全门禁）

- [x] **W2** Security Intake Gate Level 0.5（并行窗口落地；待 OpenSpec 归档）
  - `data/security_patterns.yaml`（5 类规则组：提示注入 / 危险命令 / 硬编码密钥 / 越权描述 / 外传网络）
  - `core/security_scan.py`（`SecurityScanResult`；blocked / warning / passed）
  - `core/output_sanitizer.py`（PII / 手机 / 身份证 / 邮箱 / API key 输出泄密检测）
  - 引擎双注入：Level 0 后 `blocked` → `SECURITY_BLOCKED` FAIL；CodeAssert 后 `leak` → `SECURITY_OUTPUT_LEAK` FAIL；`warning` 继续并写入报告
  - `EvaluationReport` 新增 `security_status` / `security_findings` / `output_sanitizer_status` / `output_sanitizer_findings`
  - **292 tests passing**（+42 Wave 2 测试，零回归）

### Completed（阶段三 · Wave 1 场景分类 `wave1-taxonomy`）

- [x] **W1** Q-08 场景分类词表（OpenSpec 归档 `openspec/changes/archive/2026-06-09-wave1-taxonomy/`）
  - `data/category_taxonomy.yaml`（3 Level1 / 7 Level2 金融业务骨架）
  - `core/taxonomy.py` 加载 + slug 校验 + `to_tree_json()`
  - `ingest` 升级：`malformed_cases` 损坏 case 检测
  - `scan_gaps`：`case_file_malformed` warn + `category` 词表校验
  - `GET /taxonomy/categories` API
  - `testskills/` 三样本 `category` frontmatter 回填
  - **250 tests passing**（+15 Wave 1 测试）

### Completed（阶段三 · Wave 0 基础设施 `wave0-infra`）

- [x] **W0** conversations / run lineage / staging / lui_messages DDL（OpenSpec 归档 `openspec/changes/archive/2026-06-09-wave0-infra/`；grill-me 4 项修正后落地）
  - SQLite 单事务 `init_db()` + `PRAGMA user_version` 宏微观双重门控迁移（`conversation_id` / `parent_run_id` / `superseded_by_run_id`）
  - `conversations` 表（会话、quota、`active_run_id`）+ `lui_messages` 表（LUI 对话历史）
  - `RunStatus.superseded` 显式枚举；`list_history` 默认过滤 superseded runs
  - `create_run` 原子回写 `conversations.active_run_id`（Session Lock 指针）
  - `core/bundle_resolver.py`：领域语义 IO（`ensure_staging` 原子重命名、`BundleNotReadyError` 状态守卫）；`settings.staging_root`
  - **235 tests passing**（+15 Wave 0 测试）

### To-Start（阶段四）

| 顺序 | 内容 | 说明 |
|------|------|------|
| — | **阶段四** | 立项矩阵与 Demo 材料 |

---

### In Progress（阶段三 · Wave 清单）

| Wave | 内容 | 状态 |
|------|------|------|
| **W0** | 基础设施（conversations / run lineage / staging / lui_messages DDL） | ✅ 已收官（235 tests） |
| **W1** | 3.1 Q-08 场景分类词表（taxonomy.yaml + ingest 校验 + malformed_cases） | ✅ 已收官（250 tests） |
| **W2** | Security Intake Gate Level 0.5（静态规则 + sanitizer） | ✅ 已收官（292 tests） |
| **W3** | Staging Case Propagator + 题型完整性门槛 + POST /conversations/start | ✅ 已收官（328 tests） |
| **W4** | LUI Agent + Session Lock / quota / 专家冻结（后端 + 旧双栏 UI 已被 W5 取代） | ✅ 已收官（367 tests） |
| **W4.5** | Provider 完全 env 驱动（`provider-env-factory`） | 🟡 W4 归档后可选 |
| **W5** | **Chat-First 对话壳**（2 Tab、ZIP Composer、rich_report 气泡、视角切换、历史对话） | ✅ 已收官（400 tests） |
| **W5.2** | UI 透明化（deferred Propagator + readiness + 三方式补题） | ✅ 已收官（447 tests） |
| **W5.3** | 智能对话 + LLM 补题计划 enrich + 交互体验 | ✅ 已收官（472 tests） |
| **W5.3.1** | Demo 热修：澄清去重、全链路等待提示、超时 `.env` 可配、enrich `generate()` 修复 | ✅ 已收官（475 tests） |
| **W5.3.2** | 方案 B：同步 assessment_gate → 补题计划；满足条件自动 `capability_full`（无「开始正式评估」确认） | ✅ 已收官（478 tests） |
| **W5.5** | 本地 Demo 验收（三剧本 + runbook） | 🟡 **实机彩排中**（`.env` 超时已调至 300/600/900s） |
| **W6** | 3.3 集市生态（listing / Trending / 消费者 NL 匹配 / publish Freeze） | 🟡 待启动 |
| **W7** | 服务器彩排（release zip + smoke + deployment runbook） | 🟡 待启动 |

---

## 进行中

| 事项 | 状态 |
|------|------|
| 阶段二 **全量收官** | **✅**（220 tests；Sprint 归档 `SPRINT_skillhub-mvp_completed.md`） |
| **阶段三 Wave 0** | **✅ 收官** — `wave0-infra` 落地；235 tests |
| **阶段三 Wave 1** | **✅ 收官** — Q-08 场景分类词表（`wave1-taxonomy`）；250 tests |
| **阶段三 Wave 2** | **✅ 收官** — Security Intake Gate Level 0.5；292 tests |
| **阶段三 Wave 3** | **✅ 收官** — Case Propagator + 题型完整性门槛 + POST /conversations/start；328 tests |
| **阶段三 Wave 4** | **✅ 收官** — LUI Agent + staging_writer + API；367 tests；OpenSpec 待归档 |
| **阶段三 Wave 5** | **✅ 收官** — Chat-First 对话壳（`wave5-chat-first-shell`）；DB v3 rich_report；400 tests；OpenSpec 待归档 |
| **阶段三 Wave 5.1** | **✅ 收官** — 聊天简卡 + 报告分流（`wave5.1-chat-report-split`）；DB v4 pending_patch；413 tests；OpenSpec 待归档 |
| **W5.5 Demo runbook** | **🟡 实机彩排中** — stock-radar 全流程；`.env` 超时 **300s/次 LLM、600–900s 工作流**；待用户本轮反馈 |
| **W5.3.2 评估门禁流** | **✅ 收官** — 方案 B：`assessment_gate_result` 替代作者路径 degraded→readiness；补题后自动正式双模型；478 tests |
| **W5.3.1 Demo 热修** | **✅ 收官** — 澄清阶段去重 + 全链路「正在…请稍候」+ `settings.py` 超时可配；475 tests |
| **W5.3 智能对话** | **✅ 收官** — `wave5.3-intelligent-chat`；472 tests；confirm_lexicon；bootstrap enrich；IntentRouter；propagation 分叉 + draft_preview |
| **W5.2 UI 透明化** | **✅ 收官** — `wave5.2-ui-transparency`；447 tests；初评 readiness + 补题确认 + 全对话 clarify |
| **W4.5 provider-env-factory** | **🟡 待启动** — 双评审槽位完全 env 驱动 |

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
| Q-08 | 场景分类一级词表 | P2 | **骨架已落地（W1）**；`data/category_taxonomy.yaml` + API；PM 可扩展词条；Propagator（W3）待接入 |
| Q-09 | 评估时延偏高导致 `EVAL_WORKFLOW_TIMEOUT` | P1 | **T8 复测通过**：stock-radar 9 case 全量 **48.8s**（high 预算 600s）；T7 Semaphore+分级 timeout 有效 |
| Q-10 | **DeepSeek 所有 case 恒定打 85 分** | P0 | **T12 live 通过**：stock-radar DS 分 `0/79/80.5/82`；grill-me `91.4–92.6`；无大面积同分锁死 |
| Q-11 | **三维打分字段全为 null**；`awaiting_confirm` / `degraded` 无诊断卡 | P1 | **T12 live 通过**：`model_votes.dimension_scores` 三维均有 0–100 值；A1 诊断卡 API + UI helper 验通 |
| Q-12 | **warn 原因不明确**（完整度不足 vs 分数中等）；pass/warn 均无 Skill 整体摘要 | P2 | **已解决**（T13）：warn 原因码 + `skill_summary` + UI 摘要卡 |
| Q-13 | **R5 频繁触发**（如 stock-radar DS/Gemini 红线 case 口径差）；增加人工复核负担 | P2 | **2.6 已落地**：average/redline 池拆分 + `REDLINE_MODEL_DISAGREEMENT`；能力分可经 `average_pool_mean` 展示；真分歧仍人工 |
| Q-14 | **high-risk 长包 UI 跑评** 偶发双模型全超时、无分数 | P1 | **已缓解 + T14 收官** |
| Q-15 | **业务场景归类 + eval_case 自动生成**（与 Q-08 联动） | P2 | **W3 主线**；Q-08 词表已落地（W1）；Propagator 按 risk+category 生成分型 case（低=happy，中=happy+edge，高=happy+edge+refusal+adversarial）；利用 `category_taxonomy.yaml` 的 `case_template_hint` 定制场景 |
| Q-16 | **风险 Step ③ AI 复核未落地**（仅 ① 自报 + ② 规则扫描） | P1 | **已解决（2.5）**：DeepSeek `review_risk_level` + `RiskLockProvenance`；失败降级为 ①+② |
| Q-17 | **UI 业务可读性**（中文结论/分歧卡/专家台信息密度） | P1 | **已解决**（`ui-ux-improvement` 归档；用户 2026-06-05 验收通过） |
| Q-18 | **grill-me A2 验收环境** | P2 | **取消**（2026-06-05）：阶段三 eval_case 自动生成覆盖；A2 手工未落盘场景不再追 |
| **FB-05** | **整体 UI 交互流程需第二轮设计** | P1 | **✅ 已解决（W5.2）**：补题计划表 + 三方式 + readiness/正式分卡 + verdict/next_action |
| **FB-01** | **Pass 结论在对话流未显式呈现** | P0 | **✅ 已解决（W5.2）**：正式简卡 `verdict_zh` + `next_action_zh` |
| **FB-02** | **Propagator 自动补题对用户不可见** | P0 | **✅ 已解决（W5.2）**：deferred Propagator + `propagation_plan` + 确认后 `propagation_summary` |
| **FB-03** | **「结构检查已通过」叙事过粗** | P0 | **✅ 已解决（W5.2）**：readiness 自包含卡片 + 补题摘要叙事 |
| **FB-04** | **Chat-First 信息回归** | P1 | **✅ 已解决（W5.2）**：`propagation_plan` / `readiness_result` / 正式简卡三套 UI |
| **FB-06** | **初评 readiness 卡分数/安全/门槛全 `—`** | P0 | **✅ 已解决（W5.3）**：`renderReadinessResultHtml` 读扁平 payload 字段 |
| **FB-07** | **发送后输入框不清空（尤其 Chip）** | P0 | **✅ 已解决（W5.3）**：`sendConversationMessage` 成功后始终清空 + optimistic bubble |
| **FB-08** | **「对话里补」草案路径不明确** | P1 | **✅ 已解决（W5.3）**：propagation_fork 两步分叉（自动出题 vs 描述场景 → 写文件 vs Propagator） |
| **FB-09** | **缺 eval_case 时模型不自动落盘** | P1 | **✅ 已解决（W5.3）**：`generate_draft_for_staging` + `draft_preview` + 确认写入 |
| **FB-10** | **Skill 名称确认无按钮** | P1 | **✅ 已解决（W5.3）**：`awaiting_skill_id_confirm` Chip + `__ACTION_CONFIRM_SKILL__` |
| **FB-11** | **「确定」不被接受（仅「确认」）** | P0 | **✅ 已解决（W5.3）**：`confirm_lexicon` 统一词表含「确定」 |
| **FB-12** | **补题计划模板化（缺口 `—`、业务预期雷同）** | P1 | **✅ 已解决（W5.3）**：bootstrap 每次 `enrich_propagation_plan` + DB 缓存 |
| **FB-13** | **对话阶段无进行中提示** | P2 | **✅ 已解决（W5.3.1）**：每步系统消息 + optimistic pending + 轮询 RUNNING 阶段中文 |
| **FB-14** | **点「自动出题」后记录混乱（「澄清已记录」重复）** | P0 | **✅ 已解决（W5.3.1）**：澄清阶段空消息/`ACTION_PROPAGATE` 不再刷新计划；确认阶段跳过多余 enrich |
| **FB-15** | **补题计划 enrich 降级致业务预期雷同** | P1 | **✅ 已缓解（W5.3.1）**：`propagation_plan_enricher` 改 `generate()`+fence 解析；超时提至 300s；实机待观察 |

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
| **T7 时延控制（grill-me Q2）** | `Semaphore(3)` 共享并发；429/503 指数退避 max 3× base 1s；`stage_timing` 埋点；**W5.3.1 起超时经 `settings.py` + `.env` 可配**（代码默认 90/120/600/900s；**本地 Demo `.env`：300/300/600/900s**） | 无并发上限挤爆 API；180s 一刀切；5xx 全量重试拖垮时延；超时写死代码无法按环境调参 |
| **W5.3.1 澄清/出题去重** | `awaiting_propagation_clarify` 仅在有新澄清答案时刷新计划；`ACTION_PROPAGATE` 走出题而非误触澄清；确认阶段点出题不再重复 enrich | 每次消息都 refresh+append（Demo 出现 5 条重复「澄清已记录」） |
| **W5.3.1 全链路等待反馈** | 后端落库「正在…请稍候」系统消息；前端 `activity_phase` + 轮询 RUNNING 保持 pending 气泡 | 长同步 HTTP 期间用户无感知（Demo FB） |
| **warn 原因码与 Skill 摘要（T13）** | `DecisionStage.warn_reason_codes()` 区分完整度/分数 warn；Phase 5.5 Gemini 合成 `skill_summary`；UI `renderSkillSummaryCard` + `_warnReasonText` | 仅靠 `review_status=warn` 无文案；客户端拼接 feedback 无结构化摘要 |
| **R5 优化纳入 2.6（修订 Q-13）** | 1.2 已定义红线不参与能力均分，但 `aggregate.py` 当前用**全 case** 算包级分触发 R5；2.6 对齐 `average_pool`/`redline_pool` 拆分，减少「红线口径差」导致的无谓 null 分；真分歧仍 `score_total=null` + 人工 | **简单对 disagree 取平均**（掩盖分歧、违反 R5）；**调高 10 分阈值**（属改 1.2 阈值，本阶段不做） |
| **报告运营解释层（2.3b）** | `headline_zh` / `reasons_zh` 进 `report`；UI 只读；便于业务观察 | 继续裸露 `reason_codes` 英文枚举 |
| **分歧说明卡（2.3c）** | R5 必出确定性 `disagreement_brief_zh`；非 R5 仅 per-case Δ≥15 高亮 | 全 case 都出长文说明（信息过载） |
| **AI 风险复核（2.5）** | 补齐 1.2/1.3 第三步；与规则扫描就高合并 | AI 单独下调 risk（违反就高不就低） |
| **场景联动 eval_case（B 登记）** | 与 Q-08 词表、阶段三集市分类一致后再做自动生成 | 评估阶段无分类硬编码长尾规则（与 Project-Background 原则冲突） |
| **T6 监控反射面：历史/详情消费 stage_timing** | `GET /eval/report` 暴露 `stage_timings` + `timing_summary`；历史表 `formatScoreCompact` + 耗时列；超时终态展示 `stage_progress` + 阶段条形图 | T8 live 数据仅落库、UI 静默（数据孤岛） |
| **研发交接：四阶段 MVP 全部完成后才交接 + 编写交接文档** | 当前仍在 MVP Demo 阶段；过早交接徒增文档维护成本 | 立项演示后即交接（MVP 尚未完整） |
| **Prompt 格式示例改用 `<integer 0-100>` 占位符，禁止照抄** | T8 live 实测发现 DeepSeek 字面遵循示例数值 85；占位符 + 评分段说明给模型语义锚定，无需具体数字 | 完全删除示例（缺结构引导→可能输出非法 JSON）；保留示例但只改数字（模型仍有锚定风险） |
| **三维权重 40/30/30 硬编码在 `_extract_score`** | 与 1.2 协议 §3 权重统一，单一真源；fallback 保留平均逻辑向后兼容 mock provider | 由 prompt 动态传权重（增加变量，测试困难） |
| **`check_providers.py` 同步修复示例分数** | 防止未来接入新模型时连通测试的示例值影响新模型打分锚定 | 不改（健康检查而已）|
| **2.6-A：R5/能力分仅用 average_pool** | 对齐 1.2 `case_scoring`；红线分歧标 `REDLINE_MODEL_DISAGREEMENT` 不单独触发包级 R5；`score_total_source=average_pool_mean` | 全 case 混算 R5（放大无谓分歧）；R5 时强行均分（掩盖分歧） |
| **红线模型分歧仍强制人工**（grill-me Q1） | `REDLINE_MODEL_DISAGREEMENT` → `awaiting_human_review`；能力分可展示但不 auto pass | 红线分歧自动 pass；红线参与能力均分 |
| **AI 风险复核用 DeepSeek**（grill-me Q2） | 与主评审分工一致；Gemini 仅作双模型打分 | Gemini 做 risk-only（增加耦合与成本） |
| **方差报告落盘路径**（grill-me Q5） | `docs/runbooks/variance-*.md` 可提交；便于 2.3 迭代对照 | 仅 stdout 临时输出 |
| **确认台根路径重定向** | `/` → `/ui/index.html`；避免业务方访问 404 | 仅文档提示正确 URL（易踩坑） |
| **UI 体验改进（ui-ux-improvement）** | 手工验收驱动：Level0 中文诊断、运营结论/分歧/风险溯源卡前置、Approve narrative 重建、per-case 中文标签与截断、Gemini 横幅、skill_summary 双列、隐藏阶段耗时；prompt v0.4 中文约束 | 仅改 prompt 不改阈值；旧 DB 记录 feedback 仍为英文（新跑生效）；进度条 dimension_notes（值为字符串无法驱动） |
| **阶段二可选收尾取消** | 方差报告 Markdown 导出、grill-me A2 环境隔离**不做**；阶段三 eval_case 自动生成与场景联动承接 | 继续追 A2 手工隔离（阶段三后意义递减）；方差报告落盘（阶段三校准回路更系统） |
| **3.2 LUI 重定义为「作者 Onboarding Agent」** | LUI 主线是评审流程中的对话式补全+代写+自动复评，不是「用自然语言找 Skill」；后者归 3.3 集市 | LUI = 消费者搜索（误解；导致 Propagator / staging / 专家冻结等核心能力无处安放） |
| **B1 方案：Propagator 预生成 case 再 degraded 初评** | 上传后静默生成 case 激活双模型评审（阶段三早期探索） | B2/B3 见原决策；**初评双模型路径已被 W5.2 GQ12 取代** → readiness 体检，不跑 model_judging |
| **合成 case 身份隔离（原方案，已修订）**：`confirmed=false` 仅参与 degraded 初评 | 原意：堵死「靠 AI 伪造 case 刷分上架」漏洞 | **已被 W3 新方案取代**（见下方「W3 case 评估策略」决策行） |
| **W3 case 评估策略：题型完整性门槛取代 confirmed 计数门槛** | 反作弊逻辑从「谁写的题」改为「包含了什么类型的题」：adversarial/refusal case 本身是天然反向压力，AI 生成合法；low=全 happy_path，medium=happy+edge，high=happy+edge+refusal+adversarial；上架仅需：题型完整 + 数量达标（3/5/9）+ 分数达标；`confirmed` 字段降级为可选透明度标注（listing 展示，非门槛） | 原 confirmed 计数（摩擦极高，无人手写 9 道 YAML；high-risk 作者放弃上架）；纯 AI 自问自答无类型约束（circular signal 风险） |
| **conversation_id + 级联 run_id + superseded** | 一次上传创建 conversation；每次代写开新 run_id；旧 run 归档为 superseded；保留完整修改历史和回溯能力 | 单 run_id 聊到底（丢历史；超时后找不回及格分） |
| **max_auto_runs=5 + Expert 操作后 quota reset=0** | 防止死循环烧 token；Expert Approve/Reject 后重置计数，给作者新的 5 次生命线 | 不设上限（无限 LLM 调用风险）；Expert 后不重置（作者永久卡死） |
| **专家挂起时 LUI 只读冻结；Reject 解冻** | 防止作者在专家审 R_102 时偷跑到 R_104 导致审计快照失效；Reject 携带驳回意见重新激活 LUI | Expert 挂起时仍允许代写（专家审计与实际文件脱节） |
| **Session Lock 409（mutation 前检查 active run 状态）** | `/chat` 和 `/confirm-cases` 在 staging mutation 前检查引擎是否 running；防止 LUI 聊天代写与 case confirm 并发冲突 | 无锁（前端并发导致 active_run_id 错乱） |
| **上架物 Export Freeze（data/listings/ 物理快照）** | Pass 后将 staging 快照到 `data/listings/{skill_id}/{version}/`；集市只读归档目录；staging 变只读，断开 onboarding 影子沙盒与集市的物理纽带 | 集市软引用 staging 目录（上架后 LUI 继续代写会篡改已上架 Skill） |
| **Security Intake Gate Level 0.5（静态规则 + adversarial case 复用）** | MVP 不新增独立 LLM 安全链路；静态规则扫描 + 后置 PII sanitizer；adversarial/refusal case 通过现有双模型评审覆盖动态安全测试 | 独立 LLM 安全评审 Agent（成本翻倍；与现有评分体系重复） |
| **本地 Demo → 服务器彩排（release zip）→ 后续 Git/Docker** | Wave 5 纵切跑通后先 release zip 彩排，提前发现 Linux 路径/权限问题；不等阶段三全完才第一次部署 | 先迁服务器再开发阶段三（部署问题混入产品开发）；等阶段三全完再部署（彩排太晚） |
| **Wave 0 DDL：单事务 cursor.execute + user_version + table_info 微观列检** | 消除 `executescript` 隐式 COMMIT 的 crash 窗口；migration 幂等可重跑 | 纯 `executescript`（crash 后 duplicate column）；仅 try/except ALTER（无版本追踪） |
| **Wave 0 RunStatus.superseded 显式枚举** | UI/历史台仅凭 `status` 判断废弃 run，无需额外查 `superseded_by_run_id` | 隐式标记（每处渲染双重判断，状态机不完整） |
| **Wave 0 BundleResolver 领域语义接口 + 原子重命名** | 屏蔽裸路径；`ensure_staging` tmp→rename 消除半复制中间态；`BundleNotReadyError` 替代 upload 模式 TypeError | 只返回路径 tuple（写穿透风险）；`exists()` 幂等跳过残缺 staging |
| **Wave 0 create_run 原子回写 active_run_id** | Session Lock 指针与 run 插入同事务，W3 初评期间即有锁保护 | API 层显式两步（幽灵 run 窗口）；推迟到 W4（R_101 期间无锁） |
| **W4 bundle_state=confirmed 触发机制：gap 归零 + UI 硬按钮** | `__SYSTEM_ACTION_CONFIRM_ALL__` 精确字符串匹配（绕过 LLM）；状态穿透风险不可接受 | LLM intent=confirm_all 意图分类（误识别率不可控） |
| **W4 per-case confirmed 纯透明度** | 题型完整性（CASE_TYPE_REQUIREMENTS）是 capability_full 唯一硬卡口；W3 已废弃计数防线 | per-case confirmed 计数参与 PASS 门槛（W3 已证明摩擦极高） |
| **W4 staging_writer 全域代写：SKILL.md frontmatter only** | body 原封不动；作者辛苦写的业务说明不可被 LLM 覆盖 | 全文替换（灾难性体验；无法 Diff 找回） |
| **W4 路由 B→degraded（gap 存在时不做 capability_full）** | 负向提示词/权限等字段必须人确认；gap 未归零不可正式打分 | gap 存在仍 capability_full（权限字段 draft 进入正式评分） |
| **W4 LUI 开场白：UI-driven（前端轮询触发 __TRIGGER_AGENT_OPENING__）** | Engine 绝对纯洁，不知道 LUI 的存在；UI 轮询 status，run 完成且 messages=0 时静默发 marker | engine 内置 LUI callback（破坏 core/engine.py 纯洁性） |
| **W4 LUI Agent：单次结构化 LLM 调用 {intent, reply, patch}** | 一次 token 消耗同时解决分类与生成；JSON 约束在 system prompt | 独立分类路由（多一次 LLM 调用；延迟翻倍） |
| **W4 冻结层：conversation.status=frozen + /chat 网关 403** | 会话层物理 frozen 标签最坚固；run 状态时序竞态无法单独防御 | 仅靠 awaiting_human_review run 状态判断（竞态条件） |
| **W4 quota 熔断：改当前 active run 为 awaiting_human_review** | 当前 run 就是"死在半路"的那次评估，暴露在专家台；不新建 run（语义混乱） | 新建专门 quota-exceeded run（多余状态；历史链断裂） |
| **W4 UI 入口：Tab1 全切 conversation flow；旧 /eval/run 折入 Debug 开关** | MVP 必须强迫体验"小白从头创建对话"；工程师调试入口隐藏不消失 | 两套并行入口（用户体验割裂；新用户找不到主路径） |
| **W4 GET /conversations/{id}/messages 全量不分页** | max_auto_runs=5 决定 session 消息量极小；分页增加复杂度无收益 | 分页（过度设计） |
| **W4 zip 上传支持（multipart）** | 服务器部署后需多人上传；local_ref 仅本机可用 | 仅 local_ref（服务器无法使用） |
| **W4 上架物 = 用户原始文件（source_path）；staging 是评估脚手架** | LUI 改写的内容是评估辅助，不代表作者意图；作者可自行采纳建议后重新上传 | 上架 staging 版本（含 AI 代写内容，作者未确认即发布） |
| **W4 grill-me G1：zip 上传双目录隔离（originals/ + staging/）** | staging = 评估沙盒；originals = 不可写原始文件；W6 listing 仅从 originals/ 复制；conversations 表加 `source_path` 列 | staging = source（两者重合时 LUI 代写内容混入 listing） |
| **W4 grill-me G2：patch 移除 sample_io；_write_cases 自动生成空 stub** | LLM 不知道服务端分配的 case_id，无法正确引用；空 stub 对 degraded 无影响；与 Propagator 行为一致 | LLM 生成 sample_io 并用索引对齐（脆弱；eval 时 LLM 编造的 output 误导打分） |
| **W4 grill-me G4：mutation + hash_changed → /chat 层重置 auto_confirmed=False** | staging 内容变了，用户的上次确认作废；每次实质修改后必须重新点【整包确认】 | 不重置（用户不知情下以新内容跑 capability_full） |
| **W4 `__TRIGGER_AGENT_OPENING__` 幂等：后端检查 messages>0 则忽略** | UI 3s 轮询可能在消息写入前重复触发；后端幂等保护防止双重开场白 | 仅靠前端去重（竞态窗口） |
| **W4 supersede_run 单步模式（无 __pending__ 占位）** | create_run 已原子更新 active_run_id；supersede_run 只改旧 run 字段；两步不存在中间态 | 3 步模式（__pending__ → create → fix；crash 后 superseded_by_run_id 为非法值） |
| **W4.5 Provider 完全 env 驱动（待做）** | 换模型/换 OpenAI 兼容厂商仅改 `.env`；`OpenAICompatibleProvider` + `JUDGE_PROVIDER_A/B` 槽位；报告/UI 用 `LABEL` 展示别名 | 继续硬编码 `DeepSeekProvider`/`GeminiProvider` 类名（每次换厂商改 deps + 部分文案） |
| **skill_summary 改用 DeepSeek；`DEEPSEEK_MODEL` 接入 settings** | 除 per-case 双模型外统一 DeepSeek；型号切换只改 env | skill_summary 继续用 Gemini；`DEEPSEEK_MODEL` 写死 `deepseek-chat` |
| **W5 Chat-First：2 Tab（对话 + 历史）；专家为视角切换非独立 Tab** | ChatGPT 式单窗口；报告以 rich_report 消息气泡呈现；历史 Tab 含对话摘要与「打开完整对话」（D7） | 保留 W4 三 Tab 专家台（与产品愿景不符；报告与对话割裂） |
| **W5 ZIP 默认上传；local_ref 仅 Demo** | `SKILLHUB_DEMO_LOCAL_REF=true` 时 UI 显示本地路径框 + bootstrap local_ref；默认 env 拒绝纯路径（D8） | 常驻 Skill ID 输入框 + local_ref 默认（非技术用户门槛高） |
| **W5 Skill ID：纯对话收集；自动识别须确认** | 优先级 user_message > SKILL.md > zip 名；仅自动识别走 awaiting_skill_id_confirm；用户消息已含 ID 则跳过（EQ2/2b/2c） | 独立表单填 ID（与 Chat-First 冲突） |
| **W5 人工复核 §4.5：作者只读 + 专家 chip；裁定后自动切回作者** | 待审期间作者 Composer 禁用；专家视角可见 approve/reject chip；MVP 允许自批（EQ1） | 独立 Expert Tab 队列（W5 已移除） |
| **W5 rich_report 服务端幂等写入** | run 终态自动 append `message_type=rich_report` + payload_json；UI 不再轮询右栏 report | 前端拉 /eval/report 填侧栏（W4 模式；刷新丢失上下文） |
| **W5 DB v3：`lui_messages.message_type` + `payload_json`** | welcome/system/rich_report 分型；`list_conversations` 供会话侧栏 | 纯 text 消息（无法渲染报告卡片） |
| **W5.1 方向 A：聊天简卡 + 历史详情全量报告** | 2 Tab 不变；聊天仅 headline/summary/CTA；完整报告在历史模态 | 聊天内长折叠块 + 整包确认 chip（Demo 反馈：信息密度过高、流程不清） |
| **W5.1 C2：初评简卡不展示分数** | `report_phase=initial` 时 `score_line_html=null`（W5.1）；**W5.2 起初评改为 `readiness_result`，不再 rich_report** | 初评展示分数（用户困惑 degraded vs 正式） |
| **W5.1 R3：结构通过自动正式评估** | gap_zero + case_gate → `auto_confirmed=True` + `capability_full`；移除主路径 `confirm_all` | 保留整包确认按钮（与自动链路重复） |
| **W5.1 GQ1/GQ3：草案 patch 落库确认写入** | `pending_patch_json` + `awaiting_draft_confirm`；确认原样 apply，不二次 LLM | 确认时重新 LLM 生成 patch（不可复现） |
| **W5.1 GQ4/GQ6：先 LLM 叙事后简卡；额度仅计 capability_full** | `on_run_terminal_chat_notifications` 顺序；`increment_auto_run_count` 仅正式评估 | 简卡先于叙事；初评也计 quota（与产品语义不符） |
| **W5.2 UI-B3：缺题暂停 + 三方式补题** | 补题计划表；默认自补重传 ZIP；「帮我在对话里补」→ W5.1 草案；「确认」→ Propagator | 静默 Propagator（Demo FB-02） |
| **W5.2 UI-S2：全对话 Skill 设计不确定则问** | L0 规则 + LuiAgent `clarify` intent；禁止低置信 mutation/propagate | 仅补题阶段提问（S1）；模型猜测后写盘 |
| **W5.2 UI-TBL / VERDICT** | `propagation_plan` 结构化表；正式简卡 Pass/Warn/Fail 徽标 | LLM 生成表格；仅分数无结论 |
| **W5.2 GQ1–GQ11** | grill-me 2026-06-10：部分缺题也暂停；status+LLM 分流「确认」；表与澄清同条；warn 无专家=「通过（有改进建议）」；澄清可跳过；重传整包重载；叙事必提补题；表单条更新；三 Chip；high 无二次确认 | 见 `openspec/changes/wave5.2-ui-transparency/proposal.md` |
| **W5.2 GQ12–GQ14** | 初评 R2：安全+规则风险+结构门槛，无模型评审；初评 readiness 消息自包含、无报告 CTA；正式卡 verdict+next_action+完整报告链 | 初评仍跑双模型；初评 rich_report 链历史详情 |
| **W5.2 GQ15** | 历史 Tab **不展示**初评 run；初评仅在对话 `readiness_result` | 历史仍列初评但无报告入口（GQ15 A） |
| **W5.3 GQ-W53-1～12** | bootstrap 每次 LLM enrich；无 SSE 阶段占位；`__ACTION_*__` Chip；对话补题两步分叉；步骤条；白话表头；confirm_lexicon+IntentRouter≥0.85；enrich 降级；draft 失败 2 次；评估中 409 锁聊 | 见 `openspec/changes/wave5.3-intelligent-chat/` |
| **W5.3.2 方案 B（作者路径）** | Skill ID 确认后先同步 `assessment_gate`（文案：「正在分析 Skill 并检查是否满足评估需求」）；不满足 →「需补充评估测试用例」+ 补题计划；满足或补题后 gate 通过 → **自动** `start_capability_full_eval`（移除 degraded 初评 + readiness 卡 + 人工「开始正式评估」）；UI `renderAssessmentGateHtml` | 保留 degraded→readiness→手动正式（Demo 反馈冗余三步）；gate 后仍跑 degraded 再 readiness（与「满足即评」冲突） |

---

## 关键约束

1. **阶段一**：文档定标（1.1–1.3 + 指南 v0.1）；**不**实现完整 Agent 编排与 Portal。
2. **阶段二**：工程实现 + 样本 Capability / 上架后健康检查跑通。
3. **创作 vs 上架**：日常最小作者包；上架前可评估包 + 准入结论。
4. **存量路径**：降级评估（WARN）→ 补齐 → 完整复评 → PASS。
5. **埋点**：评估标准附录 C + 1.3 检查清单（失效场景：裁判洁癖、草案疲劳、拦截器误杀）。
6. **1.3 状态闸门**：人工抽检、模型聚合与运营解释均不得绕过 `confirmed` 包状态直接 PASS。
7. **降级断言边界**：未确认 draft 只用于缺口提示/低置信度评审，不作为 CodeAssert 失败依据。
8. **超时调参（W5.3.1）**：在 `.env` 配置 `PROVIDER_CALL_TIMEOUT_S`、`PROVIDER_CALL_TIMEOUT_HIGH_RISK_S`、`WORKFLOW_TIMEOUT_LOW_S` / `_MEDIUM_S` / `_HIGH_S`；改后须重启 `serve`。本地 Demo 当前：**300s/次 LLM、600s 初评工作流、900s 高风险正式双模型工作流**。

---

## 阶段一收官说明

**阶段一（标准建立与架构设计）文档侧已完结。** 已完成：1.1 协议 v0.5、1.2 评估标准 v1.2.1、1.3 Architecture Contract v0.2、1.1b 编写指南 v1.0。未完成项不阻塞阶段二：**Q-04** 真实样本清单、Golden Case 实填、可选纸面降级评估——归入阶段二 2.1 及样本验证。

---

## 阶段二接续指引（2.1b–2.6）

### 新窗口开场句（可复制 · 阶段三 Wave 3）

> 阶段三 **W0/W1/W2 已收官**（292 tests）。本窗口主线：**Wave 3** — Staging Case Propagator + Case Sanitizer + `POST /conversations/start` + R_101 `degraded` 初评 + `confirmed=false` 合成 case 防线。必读 `RECORD.md`、`.cursor_memory/active/SPRINT_phase3-marketplace.md` §Wave 3。**不重写** 1.2 阈值。W2 安全门禁已落地（Level 0.5 静态扫描 + 输出脱敏）；W3 上传入口需复用 `security_scan`。合成 case 仅参与初评，**不得**计入 `capability_full` PASS 数量门槛。

### 2.6 R5 聚合优化说明（减小分歧 ≠ 掩盖分歧）

**现象（stock-radar）**：红线题上 DeepSeek 打 0、Gemini 打 90+ → 包级分差 ≥10 → 触发 R5 → `score_total=null` → 整包必进人工。

**1.2 本意**：红线 case **一票否决**，**不参与** happy/edge 能力均分（JSON 字段 `case_scoring.redline_pool` / `average_pool`）。

**当前实现缺口**：`aggregate.py` 用**全部 case** 的模型均分算 R5，红线低分与高分题混在一起，放大无谓 R5。

**2.6 推荐方向（2.3 有方差数据后 grill-me 选型）**：

| 方案 | 做法 | 效果 |
|------|------|------|
| **2.6-A（首选）** | R5 分差与 `score_total` 聚合**仅用 average_pool**（happy+edge）；红线单独二元否决 + 可选「红线模型分歧」子原因 | 能力分可展示；红线真分歧仍人工 |
| **2.6-B** | 红线 case 仅当**双模型均判 fail** 才 veto；单模型 fail → 标 `REDLINE_DISAGREEMENT` + 人工，不直接 FAIL | 减少误杀；需 1.3 运营话术 |
| **2.6-C（2.3 重叠）** | 仅 Prompt 校准红线 rubric，不改 `aggregate.py` | 软收敛，不保证结构性修复 |

**明确不做**：分歧时强行 `mean(DS,WB)` 出综合分；调高 R5 的 10 分阈值（改 1.2）。

### 已完成（勿重复实现）

| 范围 | 证据 |
|------|------|
| **2.0** 评估引擎 + UI + CLI | `skillhub_eval/`；214 tests |
| **Phase 1 T1–T14** | gaps、R5 可视化、T7、T13、T14 |
| **2.1b–2.6 + 2.4** | `report_narrative`/`risk_review`/`aggregate` 池拆分；T8 live 矩阵 |
| **2.3a 时延** | T7 |

### 硬约束（仍有效）

1. **PASS** 仅 `confirmed` + `capability_full`。
2. **真分歧**仍 `score_total = null`，禁止简单均分掩盖。
3. **风险锁定**只抬不降：`max(自报, 规则, AI)`。
4. 校准结论进 report/运营配置，**不**静默改 1.2 阈值正文。

### 勿做（Wave 3 窗口）

- 重复 W0/W1/W2 工程实现（conversations DDL、taxonomy、security_scan / output_sanitizer 已通）。
- 静默修改 1.2 阈值或 R5 10 分线。
- 合成 case `confirmed=false` 参与 `capability_full` PASS 数量判定（防线漏洞）。
- Wave 4 LUI 全量 UI（W3 只做 Propagator + conversation start API + confirmed 防线；LUI 对话归 W4）。

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
| 已归档 Sprint | `.cursor_memory/archive/SPRINT_skillhub-mvp_completed.md` |
| Active Sprint | `.cursor_memory/active/SPRINT_phase3-marketplace.md` |
| Wave 0 change | `openspec/changes/archive/2026-06-09-wave0-infra/` |
| Wave 1 change | `openspec/changes/archive/2026-06-09-wave1-taxonomy/` |
| Wave 3 change | `openspec/changes/archive/2026-06-09-wave3-propagator/` |
| Backlog | `.cursor_memory/backlog/BACKLOG.md` |
| Skill 样例参考 | `../个股诊断/Skill/stock-radar-V6.2/` |
| **Phase 1 实现计划** | `docs/superpowers/plans/2026-06-03-phase2-eval-phase1.md` |
| **阶段二剩余实施计划** | `docs/superpowers/plans/2026-06-05-phase2-eval-remaining.md` |
| **报告呈现规范（业务向）** | `docs/guides/报告呈现规范.md` |
| Post-Listing Health Check ADR | `docs/superpowers/specs/2026-06-05-post-listing-health-check-adr.md` |
| testskills 样本库 | `testskills/`（stock-radar-V6.2、grill-me、tiered-memory-sprint-manager） |
| Live 验收 DB | `data/t8_validation.db`、`data/acceptance_2_1b.db` |

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
| 2026-06-05 | **需求对齐**：T14 收官；Q-A～E 默认锁定；新增 **2.3b/c**（报告规范 + 分歧说明卡）、**2.5**（AI 风险复核）、**2.6**（R5 聚合优化，修订 Q-13）；**Q-15** 场景联动 eval_case 登记后续（依赖 Q-08）；本窗主线 **2.1b** |
| 2026-06-05 | **实施计划落盘**：[`docs/superpowers/plans/2026-06-05-phase2-eval-remaining.md`](docs/superpowers/plans/2026-06-05-phase2-eval-remaining.md) — Task 1–9（2.1b→2.3b/c→2.2→2.3→2.5→2.6→2.4）；文末 grill-me 决策表待挑刺 |
| 2026-06-05 | **阶段二剩余 Task 1–9 首版执行**：`report_narrative`/`risk_review`(DS)/aggregate 池拆分/`REDLINE_MODEL_DISAGREEMENT`/UI 中文卡/tiered-memory 2.1b 补全包/ADR+方差脚本；**214 tests**；Q1–Q5 锁定 |
| 2026-06-05 | **T8 live 复跑收官**：`t8_live_validation.py` ~236s；stock-radar `REDLINE_MODEL_DISAGREEMENT`+R5+Approve；tiered 2.1b 67s warn；`/`→UI 重定向 |
| 2026-06-05 | **UI 体验改进收官**：OpenSpec `ui-ux-improvement` 实现 + 手工验收通过；**220 tests**；归档至 `openspec/changes/archive/2026-06-05-ui-ux-improvement/`；**阶段二收官** |
| 2026-06-05 | **Sprint 归档**：`SPRINT_skillhub-mvp` → `archive/SPRINT_skillhub-mvp_completed.md`；方差导出 + A2 环境**取消**；**下一窗口阶段三**（eval_case 自动生成纳入主线） |
| 2026-06-09 | **阶段三 Scope 定标**：LUI 重定义为「作者 Onboarding Agent」（B1 Propagator + conversation/run lineage + staging + 专家冻结 + quota 熔断）；Security Intake Gate Level 0.5（静态规则 + adversarial case 复用）；上架物 Export Freeze；消费者 NL 匹配归 3.3 集市；eval_case 自动生成并入 3.2 Propagator；Q-08 金融业务词表骨架确定；部署路线：本地 Demo → 服务器彩排（release zip）→ Git/Docker |
| 2026-06-09 | **阶段三 Sprint 创建**：`.cursor_memory/active/SPRINT_phase3-marketplace.md`（Wave 0–7，42 个子任务，含 4 个工程漏洞补丁）；RECORD.md 推进至进行中 |
| 2026-06-09 | **Wave 0 收官**：OpenSpec `wave0-infra` grill-me 4 项修正后 subagent 落地；conversations/lui_messages DDL、run lineage、BundleResolver、Session Lock 指针；**235 tests**；Sprint W0-1～W0-5 勾选；下一 Wave 1（Q-08 taxonomy） |
| 2026-06-09 | **Wave 1 收官**：OpenSpec `wave1-taxonomy`；金融业务词表 + taxonomy 模块 + malformed_cases + category gaps + API + testskills 三样本回填；**250 tests**；Q-08 骨架落地；下一 Wave 2/3 |
| 2026-06-09 | **Wave 1 归档**：`openspec/changes/wave1-taxonomy` → `archive/2026-06-09-wave1-taxonomy/`；无 delta specs 需 sync |
| 2026-06-09 | **Wave 0 归档**：`openspec/changes/wave0-infra` → `archive/2026-06-09-wave0-infra/`；无 delta specs 需 sync |
| 2026-06-09 | **Wave 2 收官**（并行窗口）：Security Intake Gate Level 0.5 落地；data/security_patterns.yaml（5 类规则组）+ core/security_scan.py（SecurityScanResult）+ core/output_sanitizer.py（PII/手机/身份证/API key 检测）；引擎双注入（Level 0 后 blocked→SECURITY_BLOCKED FAIL；CodeAssert 后 leak→SECURITY_OUTPUT_LEAK FAIL）；EvaluationReport 新增 4 个安全字段；**292 tests**（+42） |
| 2026-06-09 | **W3 设计方向锁定（脑暴）**：废弃「confirmed=true 计数门槛」；改为「题型完整性门槛」——Propagator 按 risk 生成分型 case 套餐（low=3 happy；medium=3 happy+2 edge；high=3 happy+2 edge+2 refusal+2 adversarial）；adversarial/refusal 本身是天然反向压力，AI 生成合法；`confirmed` 字段降级为透明度标注；PASS 门槛改为：题型完整 + 数量达标 + 分数达标；W3 需先 grill-me 后执行 |
| 2026-06-09 | **Wave 3 收官**：OpenSpec `wave3-propagator`；grill-me 3 题锁定；subagent 5 tasks 执行；**328 tests**（+36）；Q-15 场景联动 eval_case 自动生成已落地 |
| 2026-06-09 | **Wave 3 Review 修复 + 归档**：Propagator 后 re-ingest + post-scan（合成 case blocked→422）；服务端强制 case id；OpenSpec → `archive/2026-06-09-wave3-propagator/`；**328 tests** 全绿 |
| 2026-06-10 | **Wave 4 脑暴 + OpenSpec propose 完成**：Q1–Q12 + SQ1–SQ3 + 上架物隔离决断全部锁定；OpenSpec `wave4-lui-agent` 三份 artifact（proposal/design/tasks）产出；RECORD 决策表补 14 条 W4 决断；SPRINT W4 条目同步修订（题型完整性对齐 W3 废弃 per-case confirmed 防线） |
| 2026-06-10 | **Wave 5 Chat-First 收官**：OpenSpec `wave5-chat-first-shell`；grill-me EQ1/EQ2/D7–D9 闭合；DB v3 `message_type`/`payload_json`；rich_report 服务端写入；2 Tab UI（对话+历史）+ 会话侧栏 + ZIP Composer + 作者/专家视角切换；**400 tests**（+33）；待 OpenSpec 归档 + W5.5 Demo runbook |
| 2026-06-10 | **Wave 5.1 聊天简卡 + 报告分流收官**：OpenSpec `wave5.1-chat-report-split`；grill-me GQ1–GQ7；DB v4 `pending_patch_json`；初评/正式分阶段简卡 + 自动正式评估 + 草案确认流；UI 轮询增量跳过；**413 tests**（+13）；待 OpenSpec 归档 + W5.5 Demo smoke |
| 2026-06-11 | **Wave 5.2 UI 透明化收官 + Task 0 文档同步**：OpenSpec `wave5.2-ui-transparency`；grill-me GQ1–GQ15；DB v5 `clarifications_json`；deferred Propagator + 三方式补题；初评 readiness（无模型评审）+ `readiness_result`；正式 verdict/next_action；历史 Tab 不列初评（GQ15 B）；全景说明 v1.2；**447 tests**（+34）；待 OpenSpec 归档 + W5.5 Demo smoke |
| 2026-06-10 | **Wave 5.3 智能对话收官**：OpenSpec `wave5.3-intelligent-chat`；grill-me GQ-W53-1～12；DB v6 `plan_enrichment_json`；`confirm_lexicon` / `IntentRouter` / `propagation_plan_enricher`；对话补题分叉 + `draft_preview`；UI optimistic pending + `__ACTION_*__` Chips；Demo FB-06～13 闭合；**472 tests**（+25）；待 OpenSpec 归档 + W5.5 Demo smoke |
| 2026-06-10 | **W5.3.1 Demo 热修收官**：澄清/出题去重；全链路「正在…请稍候」；`settings.py` + `.env` 超时可配；enrich 改 `generate()`+fence；**475 tests**；本地 `.env` 超时调至 **300/300/600/900s**；W5.5 stock-radar 实机彩排进行中 |
| 2026-06-10 | **W5.3.2 方案 B 评估门禁收官**：`core/assessment_gate.py` + `assessment_gate_result` 消息；作者路径移除 degraded→readiness→手动正式；补题确认后 gate 通过即 `start_capability_full_eval`；UI `renderAssessmentGateHtml`；**478 tests**（+3 集成/契约调整）；W5.5 剧本 A 待按新流复跑 |
