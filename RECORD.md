# RECORD — SkillHub MVP

> 总账文档：记录项目目标、决策与状态。阶段二 Sprint 已归档：`.project_memory/archive/SPRINT_skillhub-mvp_completed.md`；**阶段三** Active Sprint：`active/SPRINT_phase3-eval-system.md`；**阶段四** 待启动：`active/SPRINT_phase4-marketplace-biz.md`。

---

## 任务目标

构建 **SkillHub MVP**：面向全员的内部 Skill **分享、治理与使用** 平台——**重运营、重标准、低门槛**，而非单纯技术仓库。通过统一元数据规范、**多模型评审 Agent** 交叉验证的三维准入机制（指令遵循度 / 输出合规性 / 业务解决度），确立资产质量底线；并以业务场景化分类、自然语言交互（LUI）与数据驱动推荐，降低非技术员工使用门槛。

**四阶段设计路线**（2026-06-12 重定标；**2026-06-23** 阶段边界再收紧）：① 准入规范与自动质检 → ② 闭环验证与评判调优（Capability + 上架后健康检查 + 使用反馈）→ ③ **评估系统完善**（对话式评估、安全门禁、自动补题、专家复核、报告呈现、**本地 Demo 验收**）→ ④ **集市生态 + 服务器部署 + 立项提案与商业价值呈现**（W7 服务器部署、listing / Trending / 消费者发现、痛点映射、Demo 材料、可选 IAM/Portal）。

**当前交付边界**：阶段一文档定标 ✅；阶段二 **全量收官** ✅（220 tests）；阶段三 **W0** ✅（235）、**W1** ✅（250）、**W2** ✅（292）、**W3** ✅（328）、**W4 LUI Agent** ✅（367）、**W5 Chat-First 对话壳** ✅（400）、**W5.1 聊天简卡 + 报告分流** ✅（413）、**W5.2 UI 透明化** ✅（447）、**W5.3 智能对话 + LLM 补题计划** ✅（472）、**W5.3.1 Demo 热修** ✅（475）、**W5.3.2 评估门禁 + 自动正式评估** ✅（478）、**W5.3.3 材料补充卡片 UX** ✅、**W5.3.4 材料补充卡 UI 精修** ✅、**W5.4 评分过程留痕 + 追踪页** ✅（**498+ tests**；OpenSpec 已归档 `archive/2026-06-12-wave5.4-judge-trace/`）。**W5.5 剧本 A**（stock-radar 全流程 + FB-16～18 热修 + 追踪页 + 专家裁定）✅ **实机通过**。**W5.5 UI 制式回单 + 侧栏独立滚动 + 会话归档（DB v8）** ✅ **实机通过**（UI `w5.5-form-archive-hints`）；OpenSpec 已归档 `archive/2026-06-12-conversation-archive/`。**W5.5 安全 gate 分层 + 拦截 UX** ✅（`bundle_security`；**511 tests**）。**W5.5 回归 fixture 三件套 + 评估结果/拦截 UX 热修** ✅（`testskills/stock-radar-fixture-{sec-block,score-low,score-high}`；fail 红标、`security_blocked` 可读说明、共识 fail 聚合、`skill_summary` 兜底；**524 tests**）。**W8 本地 Agent 执行桥 + UI 执行桥** ✅ **收官**（后端 23/23 + UI C01–C16；**595 tests**；DB v9；网页实机验收通过 tiered-memory-sprint-manager + cursor-agent；judge/local agent 超时预算拆分）— OpenSpec 已归档 `archive/2026-06-18-local-agent-exec-bridge/`、`archive/2026-06-18-ui-local-exec-bridge/`。**W4.5 provider-env-factory** ✅（双评审槽位 env 驱动 + 报告/UI/脚本 label 全链路；UI `w4.5-provider-labels`）。**P2 工程优化** ✅（`index.html` 主业务脚本拆分、engine/chat 状态流小拆分、pytest 环境整理）。**不重写** 1.2 准入阈值（85/70/90）。**当前主线（下一窗口）**：**Q-29 本地 CLI 模型真跑成功率排查**——Codex 已实现 Trae 完成态判定修正 + 通用模型就绪诊断（8.1–8.9）；Cursor 真机复验（8.10）历经四轮，**Cursor Agent 与 Trae/GLM-5.2 均已确认端到端跑通** `exec-fixture-minimal`（`status=ok`），过程中按 TDD 修复诊断假阳性（D13）+ Cursor Agent 解析器 bug（D14）+ Trae 三个真实 bug（`--allowed-tool` 叠加解锁 D17、Windows cmd.exe 中文路径 cd 缺陷规避 D18、Trae 解析器 bug D19）；**742 tests**；**Codex CLI 本轮未测**（本机 PATH 里没有 `codex`，此前诊断卡账号额度），8.10 未完全收口（诊断结论见下节「待解决问题」Q-29）。其后：**W5.5 本地验收收官**（剧本 B/C + `phase3-eval-validation.md`）。**服务器部署（原 W7）**、集市生态（原 W6）/ W10 **已移至阶段四**。阶段二可选收尾已取消。

---

## 当前状态

### Completed

- [x] 竞品调研 `docs/research/Skill数据定义与编写规范调研.md`（Task **1.1**）
- [x] 项目背景 `docs/Project-Background.md`；`.project_memory/` + `ARCHITECTURE.md`
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

### To-Start（阶段四 · 集市 + 立项）

| 顺序 | 内容 | 说明 |
|------|------|------|
| **W7** | **服务器部署** | release zip、服务器 env、Linux smoke、`server-deployment.md`（自阶段三迁入） |
| **W6** | **集市生态** | listing / Export Freeze / Trending / 消费者 NL 匹配 / 集市 UI Tab（自阶段三迁入） |
| **4.1** | 痛点 ↔ 价值映射矩阵 | 立项叙事 |
| **4.2** | 风控 + 提效 Demo 材料包 | 可复用阶段三评估剧本 |
| **4.3+** | （可选）IAM / Portal | EQ1 自批 → 生产审批；独立 Portal IA |

> **启动条件**：阶段三 **本地评估验收收官**（W5.5 三剧本 + W8 本地真跑 + runbook）。

---

### In Progress（阶段三 · 评估系统 Wave 清单）

| Wave | 内容 | 状态 |
|------|------|------|
| **W0** | 基础设施（conversations / run lineage / staging / lui_messages DDL） | ✅ 已收官（235 tests） |
| **W1** | 3.1 Q-08 场景分类词表（taxonomy.yaml + ingest 校验 + malformed_cases） | ✅ 已收官（250 tests） |
| **W2** | Security Intake Gate Level 0.5（静态规则 + sanitizer） | ✅ 已收官（292 tests） |
| **W3** | Staging Case Propagator + 题型完整性门槛 + POST /conversations/start | ✅ 已收官（328 tests） |
| **W4** | LUI Agent + Session Lock / quota / 专家冻结（后端 + 旧双栏 UI 已被 W5 取代） | ✅ 已收官（367 tests） |
| **W4.5** | Provider 完全 env 驱动（`provider-env-factory`） | ✅ 收官（2026-06-23；含 UI label 尾项 + 脚本对齐） |
| **W5** | **Chat-First 对话壳**（2 Tab、ZIP Composer、rich_report 气泡、视角切换、历史对话） | ✅ 已收官（400 tests） |
| **W5.2** | UI 透明化（deferred Propagator + readiness + 三方式补题） | ✅ 已收官（447 tests） |
| **W5.3** | 智能对话 + LLM 补题计划 enrich + 交互体验 | ✅ 已收官（472 tests） |
| **W5.3.1** | Demo 热修：澄清去重、全链路等待提示、超时 `.env` 可配、enrich `generate()` 修复 | ✅ 已收官（475 tests） |
| **W5.3.2** | 方案 B：同步 assessment_gate → 补题计划；满足条件自动 `capability_full`（无「开始正式评估」确认） | ✅ 已收官（478 tests） |
| **W5.3.3** | 材料补充复合卡：gate+plan 同批出现；评估材料补充命名；中文 gap；两按钮 | ✅ 已收官 |
| **W5.3.4** | 材料补充卡 UI 精修：去 v1 徽标；2 列表格+红线折叠；gate pill 行；L0 blockquote；历史状态汉化 | ✅ 已收官 |
| **W5.4** | 评分过程留痕：Prompt v0.5、DB v7 `judge_traces`、分歧合成、`/ui/trace.html`、报告 `has_judge_trace` | ✅ 已收官 + 归档（498+ tests） |
| **W5.5** | 本地 Demo 验收（三剧本 + runbook）+ 制式 UI + 会话归档 | 🟡 **剧本 A ✅**；**UI 制式/布局/归档 ✅**；**安全 gate 分层+拦截 UX ✅**；剧本 B/C + runbook 待补 |
| **W8（重定义）** | **本地 Agent 执行桥**（穿透本地 CLI agent 真跑 skill → 回传真实产出 → 复用 judge）；**取代原 W8 Level 2 沙盒 + 原 W9 自建 Harness** | ✅ **收官**（595 tests；网页实机验收通过；OpenSpec 已归档 2026-06-18） |
| ~~**W7 服务器部署**~~ | ~~服务器彩排~~ | **已移至阶段四**（2026-06-23） |
| ~~**W8 Level 2 沙盒**~~ | ~~引擎接 `PythonSubprocessRunner`~~ | **已废弃**（2026-06-17）：本地 agent 跑任务时已执行脚本，中央代码跑冗余 |
| ~~**W9 自建 Harness**~~ | ~~中央 Agent Harness~~ | **已废弃**（2026-06-17）：本地 agent 即分布式 Harness |
| ~~**W6**~~ | ~~集市生态~~ | **已移至阶段四**（见 `SPRINT_phase4-marketplace-biz.md`） |

---

## 进行中

| 事项 | 状态 |
|------|------|
| 阶段二 **全量收官** | **✅**（220 tests；Sprint 归档 `SPRINT_skillhub-mvp_completed.md`） |
| **阶段三 Wave 0** | **✅ 收官** — `wave0-infra` 落地；235 tests |
| **阶段三 Wave 1** | **✅ 收官** — Q-08 场景分类词表（`wave1-taxonomy`）；250 tests |
| **阶段三 Wave 2** | **✅ 收官** — Security Intake Gate Level 0.5；292 tests |
| **阶段三 Wave 3** | **✅ 收官** — Case Propagator + 题型完整性门槛 + POST /conversations/start；328 tests |
| **阶段三 Wave 4** | **✅ 收官 + 归档** — LUI Agent + staging_writer + API；367 tests；`archive/2026-06-12-wave4-lui-agent/` |
| **阶段三 Wave 5** | **✅ 收官 + 归档** — Chat-First 对话壳；DB v3 rich_report；400 tests；`archive/2026-06-12-wave5-chat-first-shell/` |
| **阶段三 Wave 5.1** | **✅ 收官 + 归档** — 聊天简卡 + 报告分流；DB v4 pending_patch；413 tests；`archive/2026-06-12-wave5.1-chat-report-split/` |
| **W5.4 judge-trace** | **✅ 收官 + 归档** — `archive/2026-06-12-wave5.4-judge-trace/`；498+ tests |
| **W5.5 Demo 剧本 A** | **✅ 实机通过** — stock-radar：材料补充合并卡 → 自动出题 → 正式评 → 追踪页 → 专家裁定（FB-16～18 已验） |
| **W5.5 UI 制式回单 + 侧栏归档** | **✅ 收官 + 归档** — 方向三「制式回单」换肤；Layout A；`DELETE /conversations/{id}` 软归档（DB v8）；删除门禁与「需专家删除」提示；UI `w5.5-form-archive-hints`；`archive/2026-06-12-conversation-archive/` |
| **W5.5 安全 gate 分层 + 拦截 UX** | **✅ 收官** — `core/bundle_security.py`（intake 阻断 / propagator case 参考）；gate payload 含 `security_findings` + 红色告警；补题后不再因对抗题误拦开评；**511 tests** |
| **W5.5 Demo 剧本 B/C + runbook** | **🟡 待补** — Reject 解冻复评、quota 熔断、验收矩阵文档 |
| **W5.3.4 材料补充卡 UI 精修** | **✅ 收官** — 去 v1；2 列表格+红线 `<details>`；gate 压缩 pill 行；L0 左侧色条；agent 气泡白底蓝边；历史 Tab 状态汉化；UI w5.3.4 |
| **阶段路线重定标** | **✅ 2026-06-12** — 阶段三 = 评估系统完善；集市 W6 → 阶段四；Sprint 见 `SPRINT_phase3-eval-system.md` / `SPRINT_phase4-marketplace-biz.md` |
| **W5.3.3 材料补充 UX** | **✅ 收官** — gate 延后至 enrich 后与 plan 同批落库；UI 复合卡「评估材料补充」；两按钮 + 中文 gap |
| **W5.3.2 评估门禁流** | **✅ 收官 + 归档** — 方案 B；478 tests；`archive/2026-06-12-wave5.3.2-assessment-gate-flow/` |
| **W5.3.1 Demo 热修** | **✅ 收官** — 澄清去重 + 全链路等待 + 超时可配；475 tests |
| **W5.3 智能对话** | **✅ 收官 + 归档** — `wave5.3-intelligent-chat`；472 tests；`archive/2026-06-12-wave5.3-intelligent-chat/` |
| **W5.2 UI 透明化** | **✅ 收官 + 归档** — 447 tests；`archive/2026-06-12-wave5.2-ui-transparency/` |
| **W5.5 回归 fixture + 拦截 UX 热修** | **✅ 收官** — 三 fixture + UI fail 红标/说明；**524 tests** |
| **W8 本地 Agent 执行桥 + UI** | **✅ 收官 + 归档** — `local-agent-exec-bridge` 23/23 + `ui-local-exec-bridge` C01–C16；**595 tests**；网页实机验收通过；`archive/2026-06-18-local-agent-exec-bridge/`、`archive/2026-06-18-ui-local-exec-bridge/` |
| **W4.5 provider-env-factory** | **✅ 收官** — `JUDGE_PROVIDER_A/B_*` 双评审槽位、`OpenAICompatibleProvider`、API/CLI/脚本工厂、报告/UI 全链路 label（含 per-case 表头与不可用横幅）；UI build `w4.5-provider-labels` |
| **Q-24 / Q-25 功能优化包** | **✅ 已合入 main（2026-06-30）** — Q-24 ①②④⑤ + 五 Agent registry/模型选择 + Q-25 Token 汇总均在 `main`；**W8.4 多 agent 对照统计仍未做** |
| **W8.7 / Q-26 可扩展 adapter 框架** | **✅ 已合入 main + 归档（2026-06-30）+ hardening（2026-07-01）** — 数据驱动检测/三态 auth + 通用 `model_probe` + trae stream-json 真跑 + `transport` 接缝 + scan/UI 三态徽章与安装指引；网页实机 codex/cursor-agent/trae **Test 通过**；smoke test 不再误用全局 `exec_model`；补齐本地 agent 工作区 artifacts 收集、Cursor `models → --list-models` 模型探测 fallback 与非模型提示过滤。OpenSpec `archive/2026-06-30-local-agent-adapter-framework/` |
| **local-agent-trial-hardening（Q-28）** | **✅ 已实现（2026-07-01）** — 实测发现本地执行失败会**静默降级**为 `sample_io` 且报告仍显示原选 Agent/模型已执行；改为**阻断而非静默降级**（按 case incomplete，全部失败才整轮 `failed`，`redline_no_hardened_profile` 仍保留刻意降级）；报告新增 `exec_requested_agent_label/model_label` 区分「选了什么」vs「真跑了什么」；失败原因持久化为 `local_agent_failure` 事件；UI 四项修复：skill 确认 loading 文案按会话状态统一、Cursor 徽章 Test 后乐观转「可用」+ 三卡路径统一 `break-all`、Token 消耗汇总收窄为总计+三分桶+弹窗明细。真机用 Trae/GLM-5.2 验证：`run_id=9f5ff946...` 如实报 `LOCAL_EXEC_ALL_CASES_FAILED` + `exec_agent_label=None`（不再冒充已执行）。OpenSpec `openspec/changes/local-agent-trial-hardening/`（未归档） |

---

## 下一步（功能优化 · Codex 执行）

> **窗口约定（2026-06-23 锁定）**：本包**只做功能与 UI**；**全部 pytest / 剧本 B/C / `phase3-eval-validation.md` 后置到本包完成之后**。`skill_summary` 可选跳过**明确不做**。

| 序 | ID | 内容 | 交付要点 | 主要触点 |
|----|-----|------|----------|----------|
| **①** | Q-24-1 | **引擎多题并行 `case_executing`** | `EvaluationEngine._run_case_exec_phase` 由串行 `for` 改为有界并发（默认 `EXEC_CONCURRENCY=2`）；每题仍走独立 workspace；对齐 W8 spec「并行多题各自隔离」 | `core/engine.py`、`execution/local_agent_source.py` |
| **②** | Q-24-2 | **UI：本地 Agent 阶段预算可见** | `case_executing` 进行中展示 **已用 / 剩余 / 总预算**（秒，来自 `LOCAL_AGENT_WORKFLOW_TIMEOUT_*` + 当前 `risk_level_locked`）；轮询或 SSE 消费 `stage_progress` / 新增轻量字段；超时终态沿用 `EVAL_LOCAL_AGENT_TIMEOUT` | `adapters/ui/static/assets/index.js`、report API（如需补字段） |
| **④** | Q-24-4 | **限流退并发 + 按 risk 单题 agent 超时** | 并行 hit 429/rate-limit 时 **退并发到 1** + 指数退避（对齐 W8 spec G11）；单题 `timeout_s` 按 locked risk 分档（可复用 `provider_call_timeout_*` 或新增 `LOCAL_AGENT_CASE_TIMEOUT_*`） | `execution/local_agent_source.py`、`core/latency.py`、`settings.py`、`.env.example` |
| **⑤** | Q-24-5 | **Provider B 不可用横幅按因分类** | 单侧无分时**禁止**一律写「API 限流」；按 `provider_error` 摘要区分：地域不可用 / 限流 / 密钥或模型错误 / 超时等（中文一句） | `adapters/ui/static/assets/index.js` |
| **⑥** | W8.4 | **多 Agent 对照统计（最小版）** | 同一 skill 可选多 `exec_agent` 跑对照（或同 run 记录 agent 维度）；报告/历史可筛 **agent × case** 执行结果摘要（不必先做运营看板） | `execution/`、`core/schemas/report.py`、UI 历史或报告区 |
| **⑦** | Q-25 | **报告 Token 消耗汇总** | 见下「Q-25 范围」 | providers、engine、report schema、UI |

### Q-25 范围（Token 汇总 · 已锁定）

| 项 | 约定 |
|----|------|
| **采集** | OpenAI 兼容 `/chat/completions` 响应里的 `usage`（`prompt_tokens` / `completion_tokens` / `total_tokens`）；**双模型 judge**、**enrich / 补题 generate**、**divergence 合成**、**skill_summary**、**risk_review** 凡走 provider 的调用均记账 |
| **本地 Agent** | `ExecResult.usage`（stream-json 已解析部分）并入汇总，阶段标 `local_agent` |
| **报告字段** | `EvaluationReport` 增 `usage_summary`：`by_stage[]`（stage、provider_label、prompt、completion、total）+ `totals`（全轮合计）；可选 per-call 明细进 `eval_events` 或 `model_votes[].usage` |
| **UI** | 完整报告 / 历史详情展示「本轮 Token 合计」+ 按环节小计（与 `timing_summary` 同区或独立折叠卡）；**不做** 计费/单价 |
| **不做** | 对话 LUI 每条消息的 token；阶段四运营看板；改 1.2 阈值 |

### 本包明确排除

- `skill_summary` env 跳过（用户决定不做）
- 本包内不新增/不跑 pytest（收官前统一补测）
- W5.5 剧本 B/C、`phase3-eval-validation.md`（本包之后）

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
| **FB-16** | **补题达标后仍显示「对话补充说明 / 我自己改 ZIP」可点击区**，用户误以为还要继续操作 | P0 | **✅ 已解决（W5.5 彩排热修）**：`can_enter_formal` 时独立 gate 卡只展示绿色「评估需求已满足」文案，不再渲染 `renderOptionalImprovementChips` |
| **FB-17** | **L0 澄清刷新补题计划后「评估材料补充」未合并为一张卡**（缺顶部说明、gate 与 plan 分列；旧 plan 标「历史版本」） | P0 | **✅ 已解决（W5.5 彩排热修）**：`findGatePayloadBeforePlan` 向上回溯 gate；刷新 plan 时 `chat.py` 写入 `gate_snapshot`；活跃卡始终显示说明文案 |
| **FB-18** | **专家视角无「批准 / 驳回」**（简卡与完整报告弹窗均不可裁定） | P0 | **✅ 已解决（W5.5 彩排热修）**：`renderMessages` 缓存 key 含视角 + `setPerspective` 清缓存；`openRunDetail` 底部 `renderExpertReviewSection`；文案「专家审核台 Tab」→「专家视角」 |
| **FB-19** | **侧栏删除确认后 toast「Not Found」** | P1 | **✅ 已解决（W5.5 UI 归档）**：`apiFetch` 204 处理；404 区分「接口未更新/需重启服务」；后端 `DELETE` 路由 + 门禁 403/409 |
| **FB-20** | **待审/冻结会话删除无说明**（作者误点 × 不知需切专家） | P1 | **✅ 已解决（W5.5 UI 归档）**：`archiveBlockReason` 点击前拦截；侧栏「· 需专家删除」+ hover 提示；切换视角刷新侧栏 |
| **FB-21** | **补题完成后「门槛通过」仍不开评；「安全已拦截」不明显且无原因说明** | P0 | **✅ 已解决（W5.5 安全热修）**：gate 分层扫描（intake vs eval_cases）；propagator 对抗题不阻断；UI 红色告警 + findings + `hint_zh`；修复嵌入卡「已拦截」颜色 bug |

| **Q-19** | **Level 2 隔离试跑未接入主引擎**：标准规定中/高风险 Pass 须试跑级，当前实际读 sample_io 样例文件 | P1 | **✅ W8 收官（2026-06-18）**：`execution_source: local` + 网页 consent 实机通过；默认仍为 sample_io |
| **Q-20** | **中央 subprocess 沙盒跑不了内网 skill**（无 VPN/DB） | P1 | **W8 路线已定**：穿透本地 CLI agent；中央 judge 复用 |
| **Q-21** | **被穿透的本地 agent 以 `bypassPermissions`/`--trust` 全自动跑任意 skill 代码**（含内网权限机器），本身是攻击面 | P1 | **W8.5 已落地**：执行前 consent gate + Security Gate + output sanitizer + `HardenedProfile`（codex 红线） |
| **Q-22** | **回传契约怎么定**：actual_output 应含 agent 最终文本 **+** `tool_result`（skill 被调用时真实产出 + exit_code）/ usage/duration / cwd 产物 | P1 | **W8 已落地 + 2026-07-01 hardening**：stream-json 流解析统一契约（grill G1）；本地 agent 执行前后对工作区做快照，收集新增/修改的小文本 artifacts 并入 `actual_output.artifacts`；见 design D3 |
| **Q-24** | **W8 本地 Agent 评估时延 + 执行 UX 优化** | P1 | **✅ 已合入 main（2026-06-30 核实）**：① 并行 case_exec ② UI Agent 预算 ④ 限流退并发 + risk 单题超时 ⑤ Provider 横幅按因分类；新增 agent registry + `claude/codex/cursor-agent/trae/antigravity` + agent/model 双选择；**W8.4 多 agent 对照统计未做** |
| **Q-25** | **报告 Token 消耗汇总** | P1 | **✅ 已合入 main（2026-06-30 核实）**：`usage_summary` 进 `EvaluationReport` + UI 展示；provider `usage` 透传；local agent `ExecResult.usage` 并入；不做单价计费与 LUI 逐条记账 |
| **Q-26** | **执行层照搬 open-design 的可扩展 adapter 框架** | P1 | **✅ 已合入 main + 归档（2026-06-30）+ hardening（2026-07-01）**：grill 定稿 trae 改 stream-json（弃自制 ACP）；`detection`/`models`/`install_hints`/`transport` + scan/UI 三态；`RUN_LOCAL_AGENT=1` codex+trae+cursor E2E 通过；网页 Test 三 CLI 通过；`test` 固定默认模型；Cursor 模型探测改为 `models` 优先、`--list-models` 兜底并过滤登录/无模型提示；actual_output 补 workspace artifacts。**未做**：W8.4 多 agent 对照、Antigravity 真跑、`exec-fixture-minimal` 网页纵切（选模型跑正式评）。OpenSpec `archive/2026-06-30-local-agent-adapter-framework/` |
| **Q-27** | **多人试用前置排查**：`ExecResult.degrade_reason` 只落在执行层，报告/UI 全程不可见，本地 agent 跑失败时同事无法自诊断 | P1 | **✅ 已解决（2026-07-01）**：`CaseScoreRow` 增 `exec_status`/`exec_degrade_reason`；`build_provider_summary(exec_results=...)`；`renderPerCaseDetails` 加红色「本地执行未完成」徽章 + hover 中文原因。**后续经 Q-28 排查发现的更深问题**：①`consent_granted`/`exec_agent`/`exec_model` 是进程级全局状态，仍需 runbook 明确「每人各自起 `serve`」；②Q-28 已确认真实根因不是「无版本 fallback」，而是**执行结果曾被静默替换为 sample_io，从未把 `degrade_reason` 传到报告**——Q-28 已堵住替换路径，`run_incomplete` 现已可在事件日志/报告中查到；trae-cli 为何 `run_incomplete`（流式未读到结束标记）本身仍是待查的 CLI 层问题，留后续 backlog |
| **Q-28** | **local-agent-trial-hardening**：实测确认本地执行失败会静默替换为 `sample_io`（`status` 改 `ok`），报告仍显示原选 Agent/模型「已执行」，同时四项 UI 一致性问题（loading 文案、Cursor 徽章、Codex 路径溢出、Token 消耗占位过大） | P0 | **✅ 已解决（2026-07-01）**：见上方完成表 `local-agent-trial-hardening（Q-28）` 行；真机 Trae/GLM-5.2 验证阻断行为生效。**未做**：trae-cli 具体为何 `run_incomplete`（CLI 层根因）留后续 backlog，非本次范围 |
| **Q-29** | **本地 CLI 模型真跑成功率排查**：Q-28 阻断生效后，Trae/GLM-5.2 真机测试的 5 个 case **全部** 以 `degrade_reason=run_incomplete` 失败，`stderr_excerpt` 均为空 | P0 | **🟡 Cursor Agent + Trae 已收口，Codex 未测，8.10 整项暂不勾选（2026-07-02）**：Codex 按 Cursor 起草的 TDD 计划实现 Task 1–9（`is_error` 识别修正、`is_model_verified_live()` 防自掩盖、`TraeAdapter.diagnose()`、scan/test API 诊断字段、UI 展示；728 tests）。Cursor 真机复验（8.10）历经四轮：**第一轮**——①Trae/GLM-5.2 用生产同款参数直接跑通，证明 N1/N2 修复在真机有效；②发现并修复 `TraeAdapter.diagnose()` 假阳性（D13）；③Codex CLI 卡账号额度；④Cursor Agent smoke test 完成但极简 prompt 未触发文本事件。**第二轮（真实 `exec-fixture-minimal` 全流程）**——⑤Cursor Agent 其实真的执行成功，是 `CursorAgentAdapter.parse_stream()` 从未识别真实事件形状的代码 bug，已按 TDD 修复（D14）。⑥Trae/GLM-5.2 这次真的没执行任何东西——Bash 工具白名单没有 `python` 等执行类命令，看起来是 Trae CLI 自身工具权限策略（D15，当时暂开放）。**第三轮**——⑦Cursor Agent 仍 `run_incomplete`，根因换成本机 `cursor-agent` CLI **安装本身损坏**（缺失按需加载的 JS chunk），`cursor-agent update` 是官方自带修复命令（D16）。**第四轮（2026-07-02 收尾）**——⑧核实用户已跑过 `cursor-agent update`（版本从损坏的 `2026.07.01-41b2de7` 变为 `2026.06.29-2ad2186`），`RUN_LOCAL_AGENT=1` E2E **Cursor Agent 收口**（1 passed）。⑨用户带回 Trae CLI 自诊断结论：D15 的只读白名单**不是硬编码**，`--allowed-tool`/`allowed_tools` 是叠加机制，可解锁——按此在 `TraeAdapter.build_args()` 补 `--allowed-tool Bash`（D17，解决 D15）。⑩解锁后发现并修复两个新 bug：**D18** 模型习惯先 `cd "<含空格+中文的绝对路径>"`，命中一个独立存在、可用 `cmd /c` 直接复现的 Windows cmd.exe 嵌套引号缺陷（与 Trae/SkillHub 均无关），且该 shell 本来就已在正确 cwd——`harness_prompt.py` 补一句「已在正确工作目录，用相对路径，别 cd 绝对路径」通用提示解决；**D19** 与 D14 同类的解析器 bug——`TraeAdapter.parse_stream()` 复用的通用解析器只认扁平 `type:"tool_result"`，Trae 真实事件是 `type:"user",subtype:"tool_result"` 且不回显命令本身，按 TDD 补归一化修复。三修复叠加后，`python .tmp/run_fixture_real.py` 直跑 `LocalAgentSource.get_actual_output()` 对 **Trae/GLM-5.2 与 Cursor Agent 均返回 `status=ok`**，输出与 fixture 期望完全一致；全量回归 **742 passed/9 failed**（既有基线不变，净增 4）。剩余：**Codex** 本机当前 shell `codex` 不在 PATH（此前诊断为账号额度耗尽），下个窗口需先确认额度/安装路径再补测，通过后 8.10 才能整项勾选 |

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
| **场景联动 eval_case（B 登记）** | 与 Q-08 词表一致后做自动生成（**已落地 W3**）；集市消费分类归阶段四 | 评估阶段无分类硬编码长尾规则（与 Project-Background 原则冲突） |
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
| **阶段三/四边界重定标（2026-06-12）** | **阶段三** = 评估系统完善（上传到 Pass/Warn/Fail，含 Onboarding LUI）；**阶段四** = 集市生态 + 立项商业化；原 W6 整体后移 | 阶段三夹带集市（分散评估主线；用户明确先专注评估） |
| **3.2 LUI 重定义为「作者 Onboarding Agent」** | LUI 主线是评审流程中的对话式补全+代写+自动复评，不是「用自然语言找 Skill」；后者归 **阶段四** 集市 | LUI = 消费者搜索（误解；导致 Propagator / staging / 专家冻结等核心能力无处安放） |
| **B1 方案：Propagator 预生成 case 再 degraded 初评** | 上传后静默生成 case 激活双模型评审（阶段三早期探索） | B2/B3 见原决策；**初评双模型路径已被 W5.2 GQ12 取代** → readiness 体检，不跑 model_judging |
| **合成 case 身份隔离（原方案，已修订）**：`confirmed=false` 仅参与 degraded 初评 | 原意：堵死「靠 AI 伪造 case 刷分上架」漏洞 | **已被 W3 新方案取代**（见下方「W3 case 评估策略」决策行） |
| **W3 case 评估策略：题型完整性门槛取代 confirmed 计数门槛** | 反作弊逻辑从「谁写的题」改为「包含了什么类型的题」：adversarial/refusal case 本身是天然反向压力，AI 生成合法；low=全 happy_path，medium=happy+edge，high=happy+edge+refusal+adversarial；上架仅需：题型完整 + 数量达标（3/5/9）+ 分数达标；`confirmed` 字段降级为可选透明度标注（listing 展示，非门槛） | 原 confirmed 计数（摩擦极高，无人手写 9 道 YAML；high-risk 作者放弃上架）；纯 AI 自问自答无类型约束（circular signal 风险） |
| **conversation_id + 级联 run_id + superseded** | 一次上传创建 conversation；每次代写开新 run_id；旧 run 归档为 superseded；保留完整修改历史和回溯能力 | 单 run_id 聊到底（丢历史；超时后找不回及格分） |
| **max_auto_runs=5 + Expert 操作后 quota reset=0** | 防止死循环烧 token；Expert Approve/Reject 后重置计数，给作者新的 5 次生命线 | 不设上限（无限 LLM 调用风险）；Expert 后不重置（作者永久卡死） |
| **专家挂起时 LUI 只读冻结；Reject 解冻** | 防止作者在专家审 R_102 时偷跑到 R_104 导致审计快照失效；Reject 携带驳回意见重新激活 LUI | Expert 挂起时仍允许代写（专家审计与实际文件脱节） |
| **Session Lock 409（mutation 前检查 active run 状态）** | `/chat` 和 `/confirm-cases` 在 staging mutation 前检查引擎是否 running；防止 LUI 聊天代写与 case confirm 并发冲突 | 无锁（前端并发导致 active_run_id 错乱） |
| **上架物 Export Freeze（data/listings/ 物理快照）** | Pass 后将 staging 快照到 `data/listings/{skill_id}/{version}/`；集市只读归档目录；staging 变只读，断开 onboarding 影子沙盒与集市的物理纽带 | 集市软引用 staging 目录（上架后 LUI 继续代写会篡改已上架 Skill） |
| **Security Intake Gate Level 0.5（静态规则 + adversarial case 复用）** | MVP 不新增独立 LLM 安全链路；静态规则扫描 + 后置 PII sanitizer；adversarial/refusal case 通过现有双模型评审覆盖动态安全测试 | 独立 LLM 安全评审 Agent（成本翻倍；与现有评分体系重复） |
| **本地 Demo 收官 → 阶段四服务器部署（release zip）→ 后续 Git/Docker** | 阶段三止于本地评估跑通；多人访问与 Linux 路径/权限验证归 **阶段四 W7**，不与本地功能开发混排 | 阶段三夹带服务器部署（分散本地验收主线）；等阶段四才第一次部署（多人协作太晚——但本地纵切优先） |
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
| **W4.5 Provider 完全 env 驱动** | 换模型/换 OpenAI 兼容厂商仅改 `.env`；`OpenAICompatibleProvider` + `JUDGE_PROVIDER_A/B` 槽位；报告/UI/运维脚本用 `LABEL` 展示别名；旧 `DeepSeekProvider`/`GeminiProvider` deprecated 保留单测 | 继续硬编码 `DeepSeekProvider`/`GeminiProvider` 类名（每次换厂商改 deps + 部分文案） |
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
| **W5.3.3 材料补充卡片 UX** | 需补题时 gate **延后**至 LLM enrich 后与 plan 同批落库（避免 3s 轮询先露 gate）；UI 合并为「评估材料补充」复合卡（条件检查+评测案例计划+待澄清）；仅「自动出题/我自己补」两 Chip；gap 英文 UI 层中文化；L0 待澄清时禁用自动出题 | 保留「对话里补」第三按钮（与自动出题边界模糊）；gate 先写后 enrich（轮询导致分步展示） |
| **W5.3.4 材料补充卡 UI 精修** | 移除 plan/gate **v1 徽标**；评测案例表 **5 列→2 列**（场景+数量 / 补测+业务预期）；红线说明收进 `<details>` 折叠；嵌入 gate **三盒→pill 行**；L0 每题左侧色条；agent 文本气泡白底+左蓝边；历史 Tab 状态 **汉化短标签** | 保留 5 列等宽表（红线列占宽导致横向滚动）；保留 v1 版本 badge（对用户无信息价值） |
| **W5.4 评分过程留痕** | 独立 `/ui/trace.html` + DB v7 `judge_traces`；Prompt v0.5 每维 analysis/evidence/deductions；gap≥15 并行分歧合成（120s 超时）；链接仅 `capability_full && has_judge_trace`；对话「查看完整报告」就地弹模态 | 嵌入主报告 Tab（信息过载）；旧 run 回填 trace（无 prompt 数据）；改 aggregate/1.2 阈值 |
| **W5.5 彩排热修：补题卡合并** | L0 澄清后 `_append_propagation_plan_message` 附带最新 `gate_snapshot`；UI `findGatePayloadBeforePlan` 跨中间 agent/用户消息回溯 `assessment_gate_result`；活跃卡标题固定「评估材料补充」+ 沙盒说明 | 仅依赖「上一条消息是 gate」（澄清刷新后断裂）；历史卡也强行显示说明（干扰已结束会话） |
| **W5.5 彩排热修：达标 gate 只读** | `can_enter_formal && !embedded` → `renderAssessmentGatePassedHtml`（绿色达标文案）；嵌入材料补充卡内仍用 pill 行展示门槛 | 达标后仍展示可点击「可选改进」Chip（用户困惑）；完全隐藏 optional gaps 列表（运营失去可见性） |
| **W5.5 彩排热修：专家裁定入口** | 专家视角：简卡 `formal_pending_review` 显示 approve/reject；完整报告弹窗 `renderExpertReviewSection`；缓存 key 含 `perspective` | 恢复独立「专家审核台」Tab（W5 已删）；作者视角弹窗也显示裁定按钮（越权） |
| **W5.5 UI：制式回单视觉** | `frontend-design` 方向三：机构 token（Archivo/Noto Sans SC/JetBrains Mono）、方角、1px 边框、流水号牌 `runRefLabel`；`trace.html` 同步；无 emoji | 保留默认 Tailwind 圆角/渐变（「AI slop」）；气泡不对称圆角方案二（用户回退） |
| **W5.5 UI：Layout A** | 聊天行 `h-[calc(100vh-9.5rem)]`；`#session-list` 与 `#chat-messages` 各自 `overflow-y-auto`；输入栏贴底 | 整页无限增高侧栏（挤压主区）；双栏共用滚动 |
| **W5.5 会话归档（软删除）** | `conversations.archived_at` + `DELETE /conversations/{id}?perspective=`；侧栏移除、**保留** `lui_messages`/`evaluation_runs`/staging；作者禁删 frozen/待审，专家可删；运行中 409；MVP 无自动 purge | 物理 DELETE 行（丢评估历史）；作者可删待审（审计风险）；侧栏「隐藏」不做 API |
| **W5.5 归档删除 UX** | 客户端 `archiveBlockReason` 先于 confirm；侧栏琥珀 × +「需专家删除」；403/404 中文 toast；`list_conversations` 附带 `active_run_status` | 仅依赖 API 403 事后报错；404 裸显 `Not Found` |
| **执行层路线重定向（2026-06-17）** | 调研 `nexu-io/open-design`（local-first，穿透本地 CLI agent）；确定 **W8 重定义 = 本地 Agent 执行桥**；废弃中央 Level 2 沙盒 + W9 自建 Harness；W10 移阶段四 | 继续中央 subprocess 沙盒（内网 skill 结构性不可行）；自建中央 Harness（与开发者已有 CLI agent 重复） |
| **W8 回传契约：流解析非 MCP**（grill G1） | cursor/codex 无 MCP 注入；统一解析 stream-json 取最终文本 + tool_result + cwd 产物 | MCP `submit_case_output`（仅 claude 可用，不通用） |
| **W8 artifacts 采集边界（2026-07-01）** | 本地 agent 跑题前后对 per-case workspace 做文件指纹快照，仅收集新增/修改的小文本文件并入 `actual_output.artifacts`；structured JSON 与 artifacts 可共存 | 只看最终文本（会丢文件型产物）；整包全量入评审（噪声大且可能泄漏无关文件） |
| **W8 judge 双 prompt**（grill G2） | 真跑 → 执行结果 rubric；sample_io 回退 → 现有 doc-centric prompt | prompt 不动直接填 actual_output（红线口径自相矛盾） |
| **W8 level_2 = 本地真跑 + entrypoint 证据** | 废弃 `has_scripts AND self.sandbox`；PASS 本地真跑标 `spot_check_eligible` | 仅信文本输出（agent 可绕 pipeline 手写） |
| **W8 v1 三 agent 顺序 claude→codex→cursor-agent** | DX 最低门槛；顺序按流解析器复杂度/红线能力 | v1 只打通 1 个；全量 agent（YAGNI） |
| **W8 红线隔离** | 红线真跑仅在 codex 加固档；claude/cursor 无加固 → 红线降级 doc-centric | 原生 Windows 防火墙 ACL（脆弱）；强行全 WSL |
| **W8 信任 v1** | judge pass → PASS + `spot_check_eligible`；专家抽检纯人工但 history 可筛 | v1 建中央复跑（过早）；永久信任（多用户泄漏） |
| **砍掉中央代码执行，不留冗余 `PythonSubprocessRunner`** | 本地 agent 跑任务时已执行 skill 脚本，中央再跑 python 冗余；组件留架子供阶段四 Golden Case 按需接 | 物理删除 runner（阶段四可能需确定性复跑） |
| **执行前 consent 进程内 gate（无 UI）**（W8.5） | v1 用 `EXEC_CONSENT_REQUIRED` + `grant_exec_consent(skill_id)`；Demo 走 CLI/文档 | 首版就做 UI 同意弹窗（阻塞 W8 纵切） |
| **W8 超时预算拆分（judge vs local agent）**（2026-06-18） | 本地 `case_executing` 与双模型 `model_judging` 分开计时；避免 Agent 真跑占满 `WORKFLOW_TIMEOUT_*`；本地模式 `asyncio.to_thread` 不阻塞 serve | 继续整轮单一 `wait_for`（tiered-memory 3 题 Cursor 实测 `EVAL_WORKFLOW_TIMEOUT`） |
| **W8 收官归档（2026-06-18）** | 网页实机验收通过后归档 `local-agent-exec-bridge` + `ui-local-exec-bridge`；阶段三主线切 **本地验收收官**（W5.5 B/C + runbook） | 继续挂活跃 change 等更多优化；把 Q-24 优化并入 W8 再归档（纵切已满足） |
| **Q-24 下一窗范围（2026-06-23）** | ①②④⑤⑥ + Q-25 Token 汇总；**pytest / 剧本 B/C / runbook 后置**；**不做** skill_summary 跳过 | 本包夹带 W5.5 验收（分散 Codex 窗口）；skill_summary 跳过（用户明确不要） |
| **Q-25 Token 汇总落盘** | `usage_summary` 进 `EvaluationReport` + UI 展示；provider `usage` 透传；local agent `ExecResult.usage` 并入；**不做** 单价计费与 LUI 逐条记账 | 仅 stdout 临时统计（无法历史对比）；独立运营看板（归阶段四） |
| **W8.7 smoke test 与全局模型解耦** | `POST /api/exec/agents/{id}/test` 固定 `resolve_adapter(..., model=None)`；下拉选的 `exec_model` 仅影响正式评估，避免 trae 模型误传给 codex/cursor 导致 stream 不完整 | Test 继续读 `prefs.exec_model`（三 CLI 同报 did not complete） |
| **阶段三/四边界再收紧（2026-06-23）** | **阶段三** = 本地 Skill 评估跑通（`skillhub-eval serve` + 浏览器 + 可选本地 agent）；**原 W7 服务器部署** 整体移 **阶段四** | 阶段三继续追服务器彩排（与用户「先本地验通」冲突） |
| **W5.5 安全 gate 分层扫描** | `scan_bundle_security`：**intake**（SKILL.md + scripts）决定 `can_enter_formal` / bootstrap 422；**eval_cases** 单独扫描；`origin=staging_propagator` 的 blocked 命中降级为 info；gate payload 透传 `security_findings` + `security_block_reason_zh`；UI `renderSecurityFindingsHtml` 红色拦截条 | 继续合并扫描 SKILL+cases（补题后对抗题误拦）；仅改 Propagator prompt（不稳定）；引擎与 gate 扫描范围强行统一为仅 SKILL（弱化作者上传恶意 case 检测） |
| **本地执行失败阻断，不再静默替换 sample_io（Q-28/D1）** | 静默替换会把「Agent 根本没跑」伪装成「跑了但用示例数据」，多人试用前信任成本高于「暂时没报告」；`redline_no_hardened_profile` 是刻意设计的降级（非失败），单独保留替换 | 保留自动替换只加「已降级」标注（用户明确拒绝：secretly-substituted 数据比暂停更差）；整轮一刀切阻断（否决——单个 case 失败不应牵连全轮，改为按 case incomplete，仅「预检无 agent」或「全部 case 失败」才整轮 `failed`） |
| **报告执行归属拆分为「实际执行」vs「用户选择」两组字段（Q-28/D3）** | `exec_agent_label` 曾经「无成功 case 时静默回退全局偏好」，是 Q-28 报告造假的直接原因；拆成 `exec_agent_label`（仅真跑成功才非空）+ `exec_requested_agent_label`（用户选了什么，始终可见）从结构上杜绝二义性 | 加一个 `exec_actually_ran: bool` 布尔位（仍是同一字段两种语义叠加，容易被消费方忽略） |
| **`TraeAdapter.diagnose()` 先信任在线探测、后看静态配置（Q-29/D13，2026-07-02）** | 真机复验发现 GLM-5.2 是 Trae 内置模型（账号鉴权，无需本地 `models:` provider 定义），但 `diagnose()` 先检查 `trae_cli.yaml` 有没有 `models:` 字段、不管就直接报 `TRAE_MODEL_NOT_CONFIGURED`，导致模型明明能跑仍报错；改为有 `configured_model` 时先调 `is_model_verified_live()`，探测到 `live` 就以此为准（`ok` 或 `TRAE_MODEL_NOT_IN_LIST`），`models:` 字段只在探测不到时作兜底信号 | 让用户先手动改 `trae_cli.yaml` 补 `models:`（用户明确按提示做了会发现模型本来就是好的，纯浪费时间且不解决任何问题） |
| **`CursorAgentAdapter.parse_stream()` 改为按真实设备事件形状解析（Q-29/D14，2026-07-02）** | 真实 `exec-fixture-minimal` 全流程测试导出原始 stream-json 后发现：真实 cursor-agent 用 `type:"tool_call"`（嵌套 `shellToolCall`/`readToolCall` 等）报告工具调用，从不用旧代码假设的扁平 `type:"tool_result"`；终态 `type:"result"` 事件的 `result` 字段带着完整回答文本，旧代码只用它取 `usage`/`duration_ms`，从未并入 `final_text`；`assistant` 事件文本嵌套在 `message.content[].text`，不是顶层 `text`/`delta`。三处一起导致：即使 agent 真的执行成功（`exitCode:0`），`missing_entrypoint_evidence` 依旧永远触发，`final_text` 永远为空。按 TDD 用真实事件形状补 4 条回归测试后修复 `cursor_agent.py`：新增 `_normalize_tool_call_event()` 拍平 `tool_call` 事件、`assistant` 改读嵌套 `content[].text`、`final_text` 优先取终态 `result` 文本 | 继续用旧的“假设 schema”测试掩盖问题（此前的单测全部基于参考实现猜测的事件形状，从未用真实 cursor-agent 输出校准过，和 Trae 当初同一类坑） |
| **Cursor Agent `run_incomplete` + 模型列表退化为「本机 CLI 安装损坏」定性，非 SkillHub 代码问题（Q-29/D16，2026-07-02，暂开放）** | D14 修好后重跑 stock-radar 真机评估，`prop_happy_01/02/03` 三个 case 仍 `run_incomplete`，`stderr_excerpt` 为 `Error: Cannot find module './2240.index.js'`；手动跑 `cursor-agent models`（模型探测命令）也崩溃，报的是另一个编号 `./2289.index.js`；两次缺的 chunk 文件编号不同，说明 `C:\Users\19430\AppData\Local\cursor-agent\versions\2026.07.01-41b2de7\` 这个版本目录里大批按需加载的 JS 分片缺失，是**安装本身不完整**（`cursor-agent --version` 能跑是因为这条路径不需要这些分片），不是 SkillHub 侧的 bug。同时这也解释了 UI 上模型下拉框退化成写死的 `Default`/`GPT-5`「内置列表」——`discover_models()` 的在线探测 `_run_probe()` 因为这个崩溃返回 `None`，只能兜底到 `agent.fallback_models` | 继续排查 SkillHub 解析器/模型探测代码找 bug（用 `is_model_verified_live()`/`discover_models()` 单测复现过，探测函数本身逻辑是对的，问题在于它调用的 `cursor-agent` 子进程自己会崩溃）。已确认 `cursor-agent` 自带 `update` 子命令（`cursor-agent --help` 列出），建议先跑 `cursor-agent update` 修复安装再复测，而不是在 SkillHub 里加针对这个损坏安装的特殊兜底逻辑 |
| **`TraeAdapter.build_args()` 无条件加 `--allowed-tool Bash`（Q-29/D17，2026-07-02）** | 用户带回 Trae CLI 自诊断结论并用真机 A/B 对比 `init` 事件的 `tools` 字段验证：`--permission-mode bypass_permissions`/`--yolo` 只管「要不要弹确认框」，D15 那份只读白名单是 GLM-5.2 的默认 tool 集，`--allowed-tool`/`allowed_tools` 是**叠加**在其之上、不是被其锁死的硬策略；红线题从不走到 `build_args()`（Trae 无 hardened profile，`redline_no_hardened_profile` 提前降级），每 case 已有独立 workspace 隔离，故可安全无条件解锁，且 `entrypoint` 规范允许 `.py`/`.sh` 等任意脚本类型，不宜只放 `Bash(python:*)` | 只放开 `Bash(python:*)`（entrypoint 允许 `.sh` 等其他解释器，窄放会重演「跑不了非 python 脚本」的同类问题）；让用户手改 `trae_cli.yaml`（问题在启动参数，不在配置文件） |
| **`harness_prompt.py` 补「已在正确工作目录，用相对路径，别 cd 绝对路径」通用提示（Q-29/D18，2026-07-02）** | D17 解锁 Bash 后，模型第一反应是 `cd "<含空格+中文的绝对路径>" && python ...`，命中一个独立存在、可用 `cmd /c` 直接复现的 Windows cmd.exe 嵌套引号缺陷（与 Trae/SkillHub 均无关），且 Bash 工具本来就已经在正确 cwd 启动，`cd` 完全没必要；提示加在跨 agent 共用的 `harness_prompt.py`（非 Trae 专属代码），因为任何本地 agent 在这台 Windows 机器 + 中文路径下都可能踩同一个坑 | 改 Trae adapter 自动包一层 quoting 修复命令（治标不治本，且模型仍可能生成其他形式的绝对路径 cd；本仓库路径本身就含中文+空格，避免依赖绝对路径才是根本解法） |
| **`TraeAdapter.parse_stream()` 补 `tool_result` 事件归一化（Q-29/D19，2026-07-02）** | D17/D18 解决后 Bash 真的跑通了 `python scripts/run.py` 且输出正确，但 `verify_entrypoint_evidence()` 仍报 `missing_entrypoint_evidence`——通用 `stream_parser.parse_stream_events()` 只认扁平 `type:"tool_result"`，Trae 真实事件是 `type:"user",subtype:"tool_result"`（且不回显命令本身，需按 `tool_use_id` 关联 assistant 的 `tool_calls`），和 D14 是同一类「测试从未用真实设备输出校准过 schema」的坑；仿 D14 模式在 `TraeAdapter.parse_stream()` 里补归一化，不改通用解析器（避免影响已经工作的 Claude/Codex/Antigravity） | 直接改通用 `stream_parser.parse_stream_events()` 兼容 Trae 的事件形状（会把 Trae 专属的 `type:"user"` 判断逻辑混进所有 agent 共用的解析路径，增加其他 agent 回归风险） |

---

## 关键约束

1. **阶段一**：文档定标（1.1–1.3 + 指南 v0.1）；**不**实现完整 Agent 编排与 Portal。
2. **阶段二**：工程实现 + 样本 Capability / 上架后健康检查跑通。
3. **阶段三**：**评估系统完善**（对话评估、补题、正式双模型、专家复核、报告、**本地 Demo**）；**不**做服务器部署、集市 listing / Trending / 消费者 NL 搜索。
4. **阶段四**：**服务器部署（W7）** + 集市生态 + 立项商业化（W6 listing、Trending、NL 匹配、publish Freeze；4.1–4.2 材料；可选 IAM/Portal）。
5. **创作 vs 上架**：日常最小作者包；上架前可评估包 + 准入结论。
6. **存量路径**：降级评估（WARN）→ 补齐 → 完整复评 → PASS。
7. **埋点**：评估标准附录 C + 1.3 检查清单（失效场景：裁判洁癖、草案疲劳、拦截器误杀）。
8. **1.3 状态闸门**：人工抽检、模型聚合与运营解释均不得绕过 `confirmed` 包状态直接 PASS。
9. **降级断言边界**：未确认 draft 只用于缺口提示/低置信度评审，不作为 CodeAssert 失败依据。
10. **超时调参（W5.3.1 + W8 2026-06-18）**：`.env` 配置 `PROVIDER_CALL_TIMEOUT_*`；**`WORKFLOW_TIMEOUT_*` 仅计双模型评审**；**`LOCAL_AGENT_WORKFLOW_TIMEOUT_*` 仅计本地 Agent case_executing**（二者分开，改后须重启 `serve`）。本地 Demo：**300s/次 LLM、judge 600/600/1200s、local agent 1800/2400/7200s**。
11. **对话 UI 渲染缓存（W5.5 热修）**：`renderMessages` 的增量跳过 key **必须含作者/专家视角**；`setPerspective` 须清空 `_lastRenderedMessageKeys`，否则专家 Chip 不刷新。
12. **专家裁定入口（W5.5 热修）**：无独立专家 Tab；裁定仅在 **专家视角** 下的对话简卡（`awaiting_human_review`）与 **完整报告弹窗** 底部；`status !== awaiting_human_review` 时不显示按钮。
13. **冻结会话不可聊天（W4 防线）**：`conversation.status=frozen` 时后端 `/chat` 403，**所有人**不可改包；作者视角 `awaiting_human_review` 时 Composer 禁用；专家可批准/驳回/侧栏归档。**继续全流程测试**请 **+ 新对话** 或专家 **驳回** 解冻。
14. **UI 视觉层边界**：`index.html` / `trace.html` 换肤走 `[ui-only]` + `frontend-design`；归档 API/DB 以 OpenSpec `conversation-archive` 为准；评估逻辑不变。
15. **安全 gate 分层（W5.5 热修）**：`can_enter_formal` 的 `security_status` **仅反映 intake**（SKILL.md + `scripts/`）；Propagator 写入的 `eval_cases` 命中规则记入 `security_case_findings`（参考，不阻断）；真正 blocked 须在 UI 展示 `security_findings` + `hint_zh`。

---

## 阶段一收官说明

**阶段一（标准建立与架构设计）文档侧已完结。** 已完成：1.1 协议 v0.5、1.2 评估标准 v1.2.1、1.3 Architecture Contract v0.2、1.1b 编写指南 v1.0。未完成项不阻塞阶段二：**Q-04** 真实样本清单、Golden Case 实填、可选纸面降级评估——归入阶段二 2.1 及样本验证。

---

## 阶段二接续指引（2.1b–2.6）

### 新窗口开场句（可复制 · 阶段三评估系统）

> 阶段三定位：**本地 Skill 评估跑通**（不做服务器、不做集市）。**W0–W8 + Q-24～Q-28 已收官**（742 tests；local-agent-trial-hardening 未归档但已实现）。**本窗口首选**：**Q-29 收尾——补测 Codex**（见「待解决问题」Q-29）——Cursor Agent、Trae 两个本地 CLI 已在 2026-07-02 确认端到端跑通 `exec-fixture-minimal`（`status=ok`），只剩 **Codex** 待验证：当前 shell 里 `codex` 不在 PATH（此前诊断是账号额度耗尽），需先确认额度是否恢复、安装路径在哪，再用 `.tmp/run_fixture_real.py` 同款方式（或补 `test_e2e_local_agent_runs_fixture` 的 `codex` 参数化）跑一次真实 fixture。**Codex 通过后 8.10 才能整项勾选**，随后进入 **W5.5 剧本 B/C + `phase3-eval-validation.md`**。Trae 收尾过程中发现并修复了三个真实 bug（均已落地，见「已做决策」D17/D18/D19）：①`--allowed-tool`/`allowed_tools` 是叠加机制而非硬编码限制，`TraeAdapter.build_args()` 补 `--allowed-tool Bash`；②Windows `cmd.exe` 处理含空格+中文的绝对路径 `cd "..."` 会报路径语法错误（与 Trae/SkillHub 均无关，`cmd /c` 可直接复现），`harness_prompt.py` 补一句「已在正确工作目录，用相对路径，别 cd」规避；③`TraeAdapter.parse_stream()` 和 D14 同类的解析器 bug——通用解析器不认 Trae 真实的 `type:"user",subtype:"tool_result"` 事件形状，已按 TDD 补归一化。详细证据链见 `design.md`「Q-29 D15 Resolved + Two New Real Bugs Found and Fixed」节、`tasks.md` 8.10 进展备注。必读 `testskills/README-fixtures.md`、runbook `docs/runbooks/local-agent-exec-validation.md`。**不重写** 1.2 阈值。服务器部署（原 W7）、集市见 **阶段四** `SPRINT_phase4-marketplace-biz.md`。

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
| 架构 | `.project_memory/global/ARCHITECTURE.md` |
| 已归档 Sprint | `.project_memory/archive/SPRINT_skillhub-mvp_completed.md` |
| Active Sprint（阶段三） | `.project_memory/active/SPRINT_phase3-eval-system.md` |
| Active Sprint（阶段四） | `.project_memory/active/SPRINT_phase4-marketplace-biz.md` |
| Wave 0 change | `openspec/changes/archive/2026-06-09-wave0-infra/` |
| Wave 1 change | `openspec/changes/archive/2026-06-09-wave1-taxonomy/` |
| Wave 3 change | `openspec/changes/archive/2026-06-09-wave3-propagator/` |
| **W8 本地 Agent 执行桥 runbook** | `docs/runbooks/local-agent-exec-validation.md` |
| **W8 OpenSpec change（已归档）** | `openspec/changes/archive/2026-06-18-local-agent-exec-bridge/`、`archive/2026-06-18-ui-local-exec-bridge/` |
| **W8 设计稿** | `docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md` |
| **W8 exec fixture** | `testskills/exec-fixture-minimal/` |
| **W8.7 adapter 框架计划** | `docs/superpowers/plans/2026-06-30-local-agent-adapter-framework.md` |
| **W8.7 OpenSpec change（已归档）** | `openspec/changes/archive/2026-06-30-local-agent-adapter-framework/` |
| **skill-execution 主 spec** | `openspec/specs/skill-execution/spec.md` |
| **Skill 评估系统全景说明 §10** | `docs/guides/Skill评估系统全景说明.md` |
| W5.5 会话归档 change | `openspec/changes/archive/2026-06-12-conversation-archive/` |
| Backlog | `.project_memory/backlog/BACKLOG.md` |
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
| 2026-06-01 | 初版 RECORD；四阶段拆分；`.project_memory/` 初始化 |
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
| 2026-06-09 | **阶段三 Sprint 创建**：`.project_memory/active/SPRINT_phase3-marketplace.md`（Wave 0–7，42 个子任务，含 4 个工程漏洞补丁）；RECORD.md 推进至进行中 |
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
| 2026-06-10 | **W5.3.3 材料补充 UX**：gate 延后 enrich 后与 plan 同批；UI 复合卡「评估材料补充」+ 中文 gap + 两按钮（方案 A 去掉「对话里补」）；476 tests 通过（latency 2 项受 `.env` 300s 影响） |
| 2026-06-12 | **W5.3.4 材料补充卡 UI 精修**：去 v1 徽标；2 列表格+红线折叠；gate pill 行；L0 blockquote；历史状态汉化；UI build **w5.3.4** |
| 2026-06-12 | **OpenSpec 批量归档**：`wave4-lui-agent`、`wave5-chat-first-shell`、`wave5.1-chat-report-split`、`wave5.2-ui-transparency`、`wave5.3-intelligent-chat`、`wave5.3.2-assessment-gate-flow` → `openspec/changes/archive/2026-06-12-*`；**活跃 change 目录已清空** |
| 2026-06-12 | **四阶段路线重定标**：阶段三 = **评估系统完善**；原 W6 集市生态 + 原阶段四立项材料合并为 **阶段四**；新增 `SPRINT_phase3-eval-system.md`、`SPRINT_phase4-marketplace-biz.md`；删除冗余 `SPRINT_phase3-marketplace.md` |
| 2026-06-12 | **W5.4 judge-trace 收官**：OpenSpec `wave5.4-judge-trace`；grill-me GQ1–GQ7；DB v7 `judge_traces`；Prompt **review-agent-v0.5**；`parse_judge_response` + `divergence_synthesis`；`GET /eval/report/{id}/trace` + `has_judge_trace`；`/ui/trace.html`；对话「查看完整报告」就地弹模态；**498 tests**；全景说明 v1.3 §8.4；GQ3 v0.4/v0.5 对比待 W5.5 live |
| 2026-06-12 | **W5.5 Demo 彩排回归 — FB-16～18 热修**：① 达标 gate 只读文案；② 澄清刷新 plan 写 `gate_snapshot` + UI 回溯合并「评估材料补充」；③ 专家视角缓存/弹窗裁定；根因见决策表「W5.5 彩排热修」三行 |
| 2026-06-12 | **W5.5 剧本 A 实机通过**：用户第 2 轮 stock-radar 全流程验收无阻塞；含 W5.4 评分过程追踪 + 专家批准/驳回 |
| 2026-06-12 | **OpenSpec 归档**：`wave5.4-judge-trace` → `archive/2026-06-12-wave5.4-judge-trace/`；活跃 change 目录仅剩历史重复副本（非本次交付） |
| 2026-06-12 | **W5.5 UI 制式回单收官**：`frontend-design` 方向三；token 换肤 + 制式题头/Tab/流水号牌；`trace.html` 同步；UI build **w5.5-form** |
| 2026-06-12 | **W5.5 UI Layout A**：侧栏与会话区固定高度 + 独立滚动；输入栏贴底；UI build **w5.5-form-layout** |
| 2026-06-12 | **W5.5 会话归档收官**：OpenSpec `conversation-archive`；DB v8 `archived_at`；`DELETE /conversations/{id}` + 视角门禁；侧栏 × 软删除；`test_conversation_archive.py`；UI **w5.5-form-archive** |
| 2026-06-12 | **W5.5 归档删除 UX 热修**：`archiveBlockReason` 预检 + 侧栏「需专家删除」；404/403 中文提示；切换视角刷新侧栏；UI **w5.5-form-archive-hints**；用户确认实机验收通过 |
| 2026-06-12 | **OpenSpec 归档**：`conversation-archive` → `archive/2026-06-12-conversation-archive/`；无 delta specs；活跃 change 目录已清空 |
| 2026-06-16 | **验证工程现状文档化**：`docs/guides/Skill评估系统全景说明.md` **v2.1** 新增 **§10**（设计 vs 现状、sample_io 来源、能力边界、演进路线） |
| 2026-06-17 | **执行层路线重定向（脑暴前定标）**：调研 `nexu-io/open-design`（local-first，穿透本地 CLI agent）；确定 **W8 重定义 = 本地 Agent 执行桥**；废弃 W8 Level 2 沙盒 + W9 Harness；W10 移阶段四 |
| 2026-06-17 | **W8 设计稿 + OpenSpec change + grill 收口**：设计稿 `docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md`；OpenSpec `local-agent-exec-bridge`；grill 11 项修订 |
| 2026-06-17 | **W8 本地 Agent 执行桥代码落地**：OpenSpec tasks 1–23 完成；**583 tests**；DB v9；fixture + runbook；🟡 待实机验收 |
| 2026-06-18 | **W5.5 回归 fixture 热修收官**：`stock-radar-fixture-{sec-block,score-low,score-high}`；**524 tests** |
| 2026-06-18 | **W8 超时预算拆分**：judge `WORKFLOW_*` 与 local agent `LOCAL_AGENT_WORKFLOW_*` 分开计时；`.env` / `.env.example` 已写入 Demo 推荐值；实机 tiered-memory 3 题 Cursor 曾整轮 `EVAL_WORKFLOW_TIMEOUT` → 已解 |
| 2026-06-18 | **W8 网页实机验收通过**：tiered-memory-sprint-manager + cursor-agent；扫描/Test/正式评全流程；阶段标签「本地 Agent 真跑」→「双模型评估」 |
| 2026-06-18 | **OpenSpec 归档**：`local-agent-exec-bridge` → `archive/2026-06-18-local-agent-exec-bridge/`；`ui-local-exec-bridge` → `archive/2026-06-18-ui-local-exec-bridge/`；**595 tests** |
| 2026-06-23 | **阶段三/四边界再收紧**：原 **W7 服务器部署** 整体移 **阶段四**；阶段三止于 **本地评估验收**（W5.5 三剧本 + runbook）；Sprint / RECORD / 全景说明 §11.3 已同步 |
| 2026-06-23 | **P2/W4.5 工程优化落地**：双评审 provider 改为 env 槽位驱动（`JUDGE_PROVIDER_A/B_*`），新增 OpenAI-compatible provider factory；API/CLI 统一装配；报告与 UI 展示跟随 env label；`.env.example` 示例模型名与代码默认值对齐；补充 P2 阶段通知文案抽取记录 |
| 2026-06-23 | **P2 工程优化收口**：`index.html` 主业务脚本拆至 `/ui/assets/index.js`；`engine.py` prompt 构造抽到 `core/judge_prompt.py`，report 文件写入抽到 `core/report_files.py`；`chat.py` 补题后 gate payload 构建集中；pytest basetemp/cache 固化，新增 `docs/runbooks/p2-test-environment.md` |
| 2026-06-23 | **W4.5-3 尾项收官**：UI per-case 表头 / Provider B 不可用横幅跟随 `provider_*_label`；`check_providers.py` / `t8_live_validation.py` 改走 `build_judge_providers`；`DeepSeekProvider`/`GeminiProvider` 标 deprecated（主路径保留兼容）；UI build `w4.5-provider-labels` |
| 2026-06-23 | **下一窗 Codex 范围锁定**：`RECORD.md` 增「下一步」— Q-24 ①并行 case_exec ②Agent 预算 UI ④限流退并发+risk 单题超时 ⑤Provider 横幅按因 ⑥W8.4 多 agent 对照 + **Q-25 Token 汇总**；明确不做 skill_summary 跳过；pytest / W5.5 B/C / runbook **后置** |
| 2026-06-24 | **Q-24/Q-25 worktree 实现完成，待合入主工作区**：worktree `C:\tmp\skillhub-q24-q25-local-agent-usage`，branch `codex/q24-q25-local-agent-usage`；完成五 Agent registry、agent/model 选择、Trae/Antigravity adapter、有界并发 case_exec、rate-limit 降并发、risk 单题 timeout、本地 Agent 预算 UI、Provider 错误按因分类、Token usage 事件与报告汇总；验证：focused backend 45 passed、engine/readiness 29 passed、JS `node --check` 通过、doc encoding OK；**未实现完整 OpenDesign adapter 层迁移**，列为阶段三后续优化；**W8.4 多 agent 对照统计未做**，留后续验收 |
| 2026-06-30 | **状态核实 + 记账纠偏**：核实 Q-24/Q-25 已在 `main`（worktree 已落后，将移除）；执行层与 `nexu-io/open-design` 框架对照盘点，记 **Q-26**（缺可扩展 adapter 契约 / 结构化 authState 检测 / ACP 传输层 / 多策略 skill 注入 / 归一化 AgentEvent / agent fallback；Trae/Antigravity 实际未打通）；确定下一方向 = 照搬 open-design 可扩展 adapter 架构（注册即新增 CLI + 检测可运行 CLI + 检测/选择 CLI 模型），计划待商讨 |
| 2026-06-30 | **W8.7/Q-26 adapter 框架实施（feat 分支）**：grill 定稿后 subagent-driven 逐 task TDD 落地——settings 超时 + `AgentDef` 数据字段 + 修 trae 登记；新增 `install_hints`/`detection`(三态+TTL)/`models`(通用 probe)/`transport` 接缝；trae 改 stream-json；`scan` 返三态+模型+安装指引；UI 三态徽章+安装卡 `[ui-only]`；opt-in 真机 E2E（默认 skip）。离线回归绿——5 项 pre-existing 失败已于 base commit `3095c78` 同样存在（codex/cursor adapter 全路径、stub 缺 `parse_stream`、readiness UI token 漂移），与本框架无关。**待真机补验** codex+trae + cursor 重装；未合并 main |
| 2026-06-30 | **W8.7/Q-26 合入 main + 实机收口**：`feat/local-agent-adapter-framework` fast-forward 至 `main`（`d8c83b8`）；cursor `--list-models` live 列表；trae positional prompt + stream-json；smoke test 忽略全局 `exec_model`；网页 codex/cursor-agent/trae Test 通过；`RUN_LOCAL_AGENT=1` E2E 三 agent 通过 |
| 2026-06-30 | **OpenSpec 归档**：`local-agent-adapter-framework` → `archive/2026-06-30-local-agent-adapter-framework/`；delta spec 同步至 `openspec/specs/skill-execution/spec.md` |
| 2026-07-01 | **W8.7 adapter hardening**：对照 `nexu-io/open-design` 后补齐两处高收益优化——本地 agent per-case workspace 执行前后快照，新增/修改小文本产物写入 `actual_output.artifacts`；Cursor 模型发现改为 `models` 优先、`--list-models` fallback，并过滤登录/无模型提示。验证：adapter/执行桥 focused 回归 **52 passed**；完整测试集当前 **693 passed / 6 skipped / 9 failed**，失败为既有 UI contract token 与 DB `user_version` 10→11 断言，不属于本次 adapter 改动。 |
| 2026-07-01 | **多人试用前置·Q-27 执行失败原因回传**：`ExecResult.degrade_reason` 此前只落在执行层、从未进报告/UI，同事跑失败时无法自诊断。`CaseScoreRow` 增 `exec_status`/`exec_degrade_reason`；`build_provider_summary` 新增 `exec_results` 参数并回填；`engine.py` 传入 `self._case_exec_results`；UI `renderPerCaseDetails` 对 `exec_status=incomplete` 的 case 加「本地执行未完成」红色徽章 + hover 显示中文原因（复用/扩充 `EXEC_READY_REASON_ZH`，新增 `run_incomplete`/`missing_entrypoint_evidence`/`output_leak`/`redline_no_hardened_profile`）。验证：`test_provider_summary.py` 5 passed（含 2 项新测试）；`tests/core + tests/adapters + tests/execution` 共 **513 passed, 6 skipped, 1 failed**（失败为既有 `completeness_score` UI token 漂移，无关）；`node --check` 通过。 |
| 2026-07-01 | **local-agent-trial-hardening（Q-28）实测发现 4 项问题**：①打字确认/纠正 skill 名无「正在分析 Skill…」loading 提示（仅 chip 点击有）；②Cursor 卡片常驻「待测试」、Codex 长路径撑出卡片；③Token 消耗表只有双模型评审、无本地 agent 且始终展开占位；④报告不显示本地测试用了哪个模型，且经排查发现**根因是执行侧静默把本地失败替换为 `sample_io`**（`RoutingExecutionSource` 本地失败即回退，`degrade_reason` 被丢弃，`exec_agent_label` 靠全局偏好伪装成「已执行」）——用真实历史 run `837c503c` 复核确认：`execution_source_used=sample_io`、`case_executing` 9 case 仅 13s（真实 CLI 不可能）、零 `local_agent` token 事件，但报告仍显示「Trae / GLM-5.2」。用户决策：**阻断而非静默降级**（按 case，不牵连全轮）+ 走完整 OpenSpec 流程（`openspec/changes/local-agent-trial-hardening/`，含 grill-me 定案按 case 阻断粒度、暂缓人工强制 sample_io 开关）。 |
| 2026-07-01 | **local-agent-trial-hardening 实现完成**：D1 `execution_source.py` 移除静默替换（保留 `redline_no_hardened_profile` 刻意降级）+ `ExecResult.stderr_excerpt`（截断 2000 字符）；D2 失败原因经 `engine._log_local_agent_failure` 持久化为 `local_agent_failure` 事件（`case_id`/`degrade_reason`/`stderr_excerpt`）；D3 `EvaluationReport` 新增 `exec_requested_agent_label`/`exec_requested_model_label`，`exec_agent_label`/`exec_model_label` 语义收紧为「仅真成功才非空」；整轮阻断：全部 case 本地失败或预检无 agent 时复用 `RunStatus.failed`（`reason_codes` 新增 `LOCAL_EXEC_UNAVAILABLE`/`LOCAL_EXEC_ALL_CASES_FAILED`），单 case 失败保持按 case `incomplete` 不牵连全轮；D4 `index.js` 新增 `pendingPhaseForCurrentStatus` 按会话状态（非输入方式）选 loading 文案，`chat.py` 打字纠正分支补齐与确认分支一致的持久化消息；D5 `testExecAgent` 成功后乐观置 `auth_status=ok`，三卡路径统一 `break-all`；D6 `renderUsageSummary` 改为总计 + Provider A/B/本地 Agent 三分桶 + 弹窗明细（新增 `usage-detail-modal`，独立于 `detail-modal`）；`openRunDetail` 新增 `renderExecAttributionCard` 展示「已选择 X，但未成功执行」或「X 已成功执行」。修复既有测试对旧静默行为的隐式依赖：`make_confirmed_low_bundle`/`test_e2e_smoke._make_bundle`/`test_security.py` 一处 fixture 补 `execution_source: sample_io`（这些测试本意是纯模型评审，不测本地执行，此前只是靠全局默认 `exec_source=local` + 静默回退才能跑通）。验证：`tests/core tests/adapters tests/execution` 518 passed/6 skipped（仅 1 项与本变更无关的既有 UI contract 失败）；全量 `pytest tests/` 700 passed（剩余 9 项失败均为预置的 sqlite `user_version` 断言与同一 UI contract 项，已用 `git stash` 对比 `main` 确认为改动前既存）；`node --check` 通过。**真机验证**（重启 server 后用 API 直接触发新 run，非 mock）：`run_id=9f5ff946-ccca-4e26-8ac6-d3a82fc312d1` 用 Trae/GLM-5.2 → `status=failed`，`reason_codes=['LOCAL_EXEC_ALL_CASES_FAILED']`，`exec_agent_label=None`（未伪装），`exec_requested_agent_label=Trae`；5 个 case 的 `local_agent_failure` 事件均为 `degrade_reason=run_incomplete`（stderr 为空）。trae-cli 具体为何 `run_incomplete` 留后续 backlog，不在本次范围内修复。 |
| 2026-07-01 | **文档收口 + Q-29 立项**：`local-agent-trial-hardening` 文档任务 7.3/7.4 完成——`.project_memory/active/SPRINT_phase3-eval-system.md` 补 T1–T8 子任务表，`docs/runbooks/local-agent-exec-validation.md` 新增「本地执行失败阻断，不再静默降级」与「exec 偏好为进程级全局状态」两节；`python scripts/check_doc_encoding.py` 通过。随后针对 Trae/GLM-5.2 真机测试 5 case 全 `run_incomplete` 做代码级诊断（未改代码，纯分析）：确认判定链是 `runner.is_run_complete()` 依赖 `stream_parser.parse_stream_events()` 看到 `"type":"result"`/`"turn.completed"`；这一 schema 假设从未用真实 trae-cli 输出校准过（`archive/2026-06-30-local-agent-adapter-framework/design.md` G7 早已标注「唯一需真机校准项」，此前测试用的是猜测样例）；结合空 `stderr_excerpt`，锁定两个候选根因（parser/schema 不匹配 vs `--yolo --permission-mode bypass_permissions` 未覆盖全部确认场景导致超时挂起）但尚未有实证区分。录入 **Q-29**，定为下一窗口主线；用户已并行让 Codex 跑一次独立 review，结论带入下一窗口再排修复顺序。 |
| 2026-07-02 | **Q-29 Codex 实现（8.1–8.9）+ Cursor 独立复核**：Codex 按 Cursor 起草并经两轮 grill-me 修正的 TDD 计划（`docs/superpowers/plans/2026-07-02-trae-completion-diagnostics.md`）实现完毕——`stream_parser.py`/`runner.py` 正确识别 Trae `is_error` 完成态；`is_model_verified_live()` 堵住 `discover_models()` 自掩盖 bug（D10）；`TraeAdapter.diagnose()` 五种 reason_code + 两处自加固（写探测不覆盖用户文件、YAML 损坏返回 `TRAE_CONFIG_PARSE_ERROR`）；`GET /api/exec/agents/scan` 返回 Trae 专属诊断字段 + 全 agent 通用 `selected_model_status`；`POST /agents/{id}/test` 支持可选 `model`；UI 展示诊断/模型状态。Cursor 独立复核：重新跑 `pytest tests/ -q` 得 726 passed/6 skipped/9 failed（与 Codex 汇报一致，9 项确认为既有基线），`node --check`/`check_doc_encoding.py` 通过，逐条比对代码与两轮 grill-me 修正点（`Body(default=None)`、`selected_model_status` default/stale 两条测试、D10 回归测试）均落地，`tasks.md` 8.1–8.9 勾选属实。 |
| 2026-07-02 | **Q-29 真机复验（8.10，部分完成）+ 发现并修复诊断假阳性（D13）**：Cursor 启动本机 `skillhub-eval serve`，用 `GET /api/exec/agents/scan` 查看 Trae 实际诊断结果，并用与 `TraeAdapter.build_args()`/`CodexAdapter.build_args()` 完全一致的参数手动直跑三个 CLI 做真机验证。**Trae/GLM-5.2 确认跑通**：`trae-cli` 直接返回 `{"type":"result","is_error":false,"result":"OK",...}`，`.tmp/check_real_agents.py` 复测一致，证明 N1/N2 的 `is_error` 完成态修复在真机上有效，Q-29 最初的 `run_incomplete` 症状已解决。但同一次 scan 里 `selected_model_status="ok"` 与 `diagnosis_reason_code="TRAE_MODEL_NOT_CONFIGURED"` 自相矛盾——查证 [Trae 官方文档](https://docs.trae.cn/ide_models) 确认 GLM-5.2 是内置模型（账号鉴权，不需要本地 `models:` provider 定义），`TraeAdapter.diagnose()` 却因为判断顺序先看静态配置、后看在线探测，导致模型明明能跑仍报错。按 TDD 修复（见「已做决策」D13 行）：`models.py`/`trae.py` 改为有 `configured_model` 时先信任 `is_model_verified_live()`；补 2 条回归测试，顺带修正 2 条隐含依赖「本机没装 trae-cli」这一假设的旧测试；全量回归 **728 passed/6 skipped/9 failed**（既有基线 +2 新测试），`node --check`/`check_doc_encoding.py` 通过。**Codex CLI** 直跑卡在账号额度（`turn.failed`: usage limit，非代码 bug，`is_run_complete()` 判它未完成是正确行为）。**Cursor Agent** smoke test `complete=True` 但极简 prompt 未触发文本事件采集，需要补一次真实 `exec-fixture-minimal` 才能算完整验证。**8.10 整体未勾选**：待 Codex 账号额度恢复后重测 + Cursor Agent/Trae 各跑一次正式 fixture 出 Pass/Warn/Fail。已同步更新 `design.md`（D13 节）、`tasks.md`（8.10 进展备注）、`SPRINT_phase3-eval-system.md`（N2.1）、`docs/runbooks/local-agent-exec-validation.md`（诊断更新说明）。 |
| 2026-07-02 | **Q-29 真实 exec-fixture-minimal 全流程复测（8.10 续）：发现并修复 Cursor Agent 解析器真实 bug（D14）+ 定位 Trae 工具权限缺口（D15，开放）**：直接调 `LocalAgentSource.get_actual_output()`（非 smoke prompt）对 Trae/GLM-5.2 与 Cursor Agent 各测一次，两者都报 `missing_entrypoint_evidence`；导出原始 stream-json 逐行比对后发现根因完全不同。**Cursor Agent**：原始 stream 显示 `shellToolCall` 真实执行了 `python scripts/run.py`（`exitCode:0`，stdout 正确），终态 `result` 事件也带着完整正确回答——是 `CursorAgentAdapter.parse_stream()` 的真实 bug：只找从不存在的扁平 `tool_result` 事件（真实形状是嵌套的 `tool_call`），从未把终态 `result` 文本并入 `final_text`，`assistant` 增量文本也读错了字段路径（应为 `message.content[].text`）。按 TDD 用真实事件形状补 4 条回归测试（`tests/execution/test_adapter_cursor_agent.py`）后修复 `cursor_agent.py`（详见「已做决策」D14 行），全量回归 **731 passed/6 skipped/9 failed**（既有基线不变，净增 5），`check_doc_encoding.py` 通过。**Trae/GLM-5.2**：原始 stream 全程无 `run.py`/`SKILL.md`/`Bash` 字样，直接凭 prompt 里的断言编答案；session 初始化事件显示 Bash 白名单仅含 `cat/find/grep/head/ls/rg/tail/awk/cut/diff/sort/uniq/wc/git.../cd/date/echo/env/pwd/which`，没有 `python` 等执行类命令，`--permission-mode bypass_permissions --yolo` 未改变这一点；`trae_cli.yaml` 无 `tools:` 配置，判断是 Trae CLI 自身默认工具权限策略而非本机误配置，超出 SkillHub 诊断范围（D15，暂开放）。已同步更新 `design.md`（新增节）、`tasks.md`（8.10 进展续）。剩余：Codex 额度恢复后重测；用户直接向 Trae CLI 询问解锁完整命令执行权限的方式，拿到结果后 Trae 再跑一次 `exec-fixture-minimal`。 |
| 2026-07-02 | **Q-29 D14 修复后网页真机复测（8.10 续）：定位 Cursor Agent `run_incomplete` 真正根因为本机 CLI 安装损坏（D16，暂开放），交接下个窗口收尾**：用户在网页 UI 上用 Cursor Agent 跑了一次 stock-radar 真机评估。发现本机 `skillhub-eval serve` 进程从当天中午 12:10 起就没重启过，D14 修复代码还没生效，先重启服务加载新代码。查该次评估（`run_id=354b5345...`）的 `analytics_events`：`prop_happy_01/02/03` 三个 case 仍各自记了一条 `local_agent_failure`，`degrade_reason=run_incomplete`，`stderr_excerpt` 都是 `Error: Cannot find module './2240.index.js'`（来自 `C:\Users\19430\AppData\Local\cursor-agent\versions\2026.07.01-41b2de7\index.js` 的 require 链）。手动直接跑 `cursor-agent models`（模型探测命令）复现同类崩溃，但缺失的是另一个编号 `./2289.index.js`——两次编号不同，说明是这个版本目录里一大批按需加载的 JS 分片文件缺失，是**安装本身损坏**（`cursor-agent --version` 能正常输出是因为那条代码路径不需要这些分片）。用代码直接调用 `discover_models(agent, stored_model=None)` 复现 UI 上「模型列表变成内置列表」的现象：`_run_probe()` 因为上述崩溃返回 `None`，`discover_models()` 按设计兜底到写死的 `fallback_models`（`Default`/`GPT-5`），逻辑本身没问题，问题在于它调用的子进程自己会崩溃。确认 `cursor-agent --help` 里有官方自带的 `update` 子命令，可用于修复安装。**定性为环境问题，不在本轮 SkillHub 代码修复范围**（D16，暂开放，等用户手动跑 `cursor-agent update` 后由下个窗口复测收尾）。已更新 `design.md`/`tasks.md`/RECORD.md「新窗口开场句」，把三个 Agent 各自当前卡点和下一步动作写清楚，方便下个窗口直接接手，不用重新排查。 |
| 2026-07-02 | **Q-29 收尾：Cursor Agent 确认收口 + Trae 三个真实 bug（D17/D18/D19）按 TDD 修复，端到端跑通**：核实用户已跑过 `cursor-agent update`（版本从损坏的 `2026.07.01-41b2de7` 变为 `2026.06.29-2ad2186`，`cursor-agent models` 恢复正常），`RUN_LOCAL_AGENT=1` E2E fixture 测试 **Cursor Agent 1 passed（41s）**，收口。随后用户带回 Trae CLI 自诊断的确定性结论：D15 的只读白名单不是硬编码，`--allowed-tool`/`allowed_tools` 是叠加机制可解锁——按 TDD 在 `TraeAdapter.build_args()` 补 `--allowed-tool Bash`（**D17**）。解锁后连续发现两个新真实 bug：**D18** 模型习惯先 `cd "<含空格+中文的绝对路径>"`，命中一个独立存在、用 `cmd /c` 可直接复现的 Windows cmd.exe 嵌套引号缺陷（与 Trae/SkillHub 均无关），且 Bash 工具本来就已在正确 cwd 启动——`harness_prompt.py` 补一句「已在正确工作目录，用相对路径，别 cd 绝对路径」通用提示解决；**D19** 与 D14 同类的解析器 bug——`TraeAdapter.parse_stream()` 复用的通用解析器只认扁平 `type:"tool_result"`，Trae 真实事件是 `type:"user",subtype:"tool_result"` 且不回显命令本身（需按 `tool_use_id` 关联 assistant 的 `tool_calls`），按 TDD 补归一化（`_extract_bash_commands` + `_normalize_tool_result_event`）。三修复叠加后，`python .tmp/run_fixture_real.py` 直调 `LocalAgentSource.get_actual_output()` 对 **Trae/GLM-5.2 与 Cursor Agent 均返回 `status=ok`**，`actual_output={'status': 'success', 'ok': True}` 与 fixture 期望完全一致；全量回归 **742 passed/9 failed**（既有基线不变，净增 4 条新回归测试）。剩余：**Codex CLI** 本机当前 shell `codex` 不在 PATH（此前诊断为账号额度耗尽），未在本轮验证；**8.10 的 Cursor Agent + Trae 两项已收口，Codex 待补，故整项仍暂不勾选**。已更新 `design.md`（D17–D19 节）、`tasks.md`（8.10 进展续）、RECORD.md（Q-29 行 + 决策表 + 新窗口开场句）。 |

| 2026-06-16 | **W5.5 安全 gate 分层 + 拦截 UX 热修**：`core/bundle_security.py`；assessment_gate 透传 findings；补题后 propagator 对抗题不再误拦 `can_enter_formal`；UI 红色安全告警 + 修复嵌入卡颜色；**511 tests**（+13）；根因 FB-21 |

---

## W5.5 Demo 彩排回归说明（2026-06-12）

### 出现的问题与根因

| ID | 现象 | 根因（工程） | 为何当时没拦住 |
|----|------|--------------|----------------|
| **FB-16** | 自动出题完成后仍出现「对话补充说明 / 我自己改 ZIP」 | `renderAssessmentGateHtml` 在 `can_enter_formal && optional_gaps` 时仍调用 `renderOptionalImprovementChips`；该交互本为 **readiness 时代**「可选改进不阻断」设计，未区分 **已自动开正式评** 的终态 | W5.3.2 改自动正式评估后未回归 gate 独立卡文案；pytest 未覆盖「达标后 gate 无按钮」 |
| **FB-17** | 回复 L0 后材料补充卡分裂、缺说明 | ① `chat.py` 刷新 `propagation_plan` **未带** `gate_snapshot`（仅 bootstrap `_defer_with_propagation_plan` 写入）；② UI `findGatePayloadBeforePlan` 只认「上一条消息是 gate」，澄清后中间夹 agent/用户消息即 **合并失败**；③ `introBlock` 误绑 `gatePayload` 存在才显示 | W5.3.3 合并设计只验了「首轮上传」路径；集成测未模拟「澄清 → 刷新 plan v2」 |
| **FB-18** | 切到专家视角仍无批准/驳回 | ① `renderMessages` 增量缓存 **不含视角**，切专家不重绘，`visible_in: expert` 的 action 永不出现；② W5 删除「专家审核台」Tab 后 **`openRunDetail` 弹窗未迁移** 裁定区；③ 文案仍指向已删除 Tab | W5.1 专家 action 写在简卡逻辑里，但 W5.3 性能优化引入缓存后缺视角维度；手测若一直停留专家视角则不易发现 |
| **FB-21** | 补题完成、门槛通过仍不开评；「安全已拦截」不醒目且无说明 | ① gate 将 **SKILL.md + eval_cases** 合并扫描，对抗题攻击描述触发 `blocked`；② `assessment_gate` payload **无** `security_findings`；③ UI「门槛」≠ `can_enter_formal`，且嵌入卡用 `阻断` 判断颜色（实际文案为「已拦截」） | W3 设计「Propagator 后重跑 security_scan」未区分评测题语义；W5.3.2 gate 文案无 blocked 分支；手测易误以为四项 warn 缺口是主因 |

### 第 2 轮彩排检查清单（stock-radar）— ✅ 已通过（2026-06-12）

1. **硬刷新** `index.html`（Ctrl+F5）；若改过 `chat.py` 则 **重启** `skillhub-eval serve`。
2. **补题阶段**：一张「评估材料补充」含说明 + 条件 pill + 计划表 + 待澄清；澄清刷新后仍为 **一张活跃卡**（旧版标历史）。
3. **自动出题后**：绿色「评估需求已满足」短卡，**无**补充说明/改 ZIP 按钮；**不应**再因 propagator 对抗题出现「安全已拦截」阻断开评（intake 本身有问题时仍显示红色说明）。
4. **待专家复核**：右上角切 **专家** → 简卡底部 **批准/驳回**；「查看完整报告」弹窗底部亦有裁定区。
5. **W5.4**：正式报告 per-case「评分过程 →」可开 `trace.html`。

**待续**：剧本 B（Reject 解冻）、剧本 C（quota）、`docs/runbooks/phase3-eval-validation.md` 验收矩阵。

### 冻结会话与测试路径（2026-06-12）

| 场景 | 聊天 | 可操作 |
|------|------|--------|
| 正式评完成 / `frozen` / 待专家复核 | **禁用**（黄条「会话已冻结」或作者「需人工复核」） | 专家：**批准 / 驳回**；侧栏删除（专家可删待审/冻结） |
| 继续跑 stock-radar 全流程 | — | **+ 新对话**，或专家 **驳回** 解冻后切回作者 |
| 侧栏删除待审会话（作者） | — | 拦截 + toast「请切换【专家】视角」 |

---
