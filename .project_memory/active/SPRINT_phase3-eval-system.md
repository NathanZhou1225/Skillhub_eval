# SPRINT：SkillHub MVP · 阶段三（评估系统完善）

> **Sprint Root**：工作区根目录（`Skillhub/`）  
> **创建日期**：2026-06-09（2026-06-12 重定标：集市生态移至阶段四；2026-06-17 执行层重定向：W8 改本地 Agent 执行桥，W9 自建 Harness 废弃，W10 移阶段四）  
> **状态**：🟢 W8.7/Q-26 **已合入 main（2026-06-30）+ adapter hardening（2026-07-01）**；🟢 **local-agent-trial-hardening（Q-28/Q-29）已归档并完成主 spec 同步（2026-07-07）**；🟡 **local-cli-runtime-platform 网页实测收口中（2026-07-09）**——preflight 已降级为可选诊断；**环境检查 UI 时机**已落地并实机确认（上传后即可检、顶栏状态 pill、过程态、抽屉不挡聊天）；正式本地评估进入真实 `case_executing`；复杂 Skill 全 case `run_incomplete` 仍属 runtime/model 对照项，不是 preflight/judge bug。阶段三其余：W5.5 剧本 B/C + runbook 待补；OpenSpec archive 仍待对照测试后收尾  
> **Goal**：完善 **Skill 评估系统**——场景分类与安全门禁 → 自动补题与题型门槛 → 作者 Onboarding LUI（对话 + 补题计划 + 代写 + 自动正式评估）→ 专家复核与报告呈现 → **本地 Demo 验收** → **本地 Agent 执行桥（真实执行）**。**本阶段仅本地跑通评估全链路**；不做服务器部署、不做集市上架与消费者发现（均归阶段四）。

---

## Context

- **阶段二**：220 tests，评估引擎闭环已通；Sprint 已归档 `archive/SPRINT_skillhub-mvp_completed.md`
- **阶段三定位（2026-06-12 重定标）**：**只做评估系统**——从上传到 Pass/Warn/Fail 结论的完整链路；集市、Trending、消费者 NL 匹配、正式发布 Freeze 归 **阶段四**
- **入口约束**：不改 1.2 阈值（85/70/90 / R5 10 分线）；题型完整性门槛；专家挂起时 LUI 冻结；`max_auto_runs=5`
- **LUI 定义**：**作者 Onboarding Agent**（补全 + 追问 + 代写 + 自动复评）；消费者 NL 匹配归阶段四集市
- **eval_case 自动生成**：并入 LUI / Propagator 能力，属评估系统主线
- **部署边界**：阶段三止于 **本地 Demo**（`skillhub-eval serve` + 浏览器 + 可选本地 CLI agent）；**服务器部署 / release zip / Linux smoke** 归 **阶段四 W7**
- **2026-07-08 本地 runtime 验收边界**：`本地执行环境检查` 保留为手动诊断，不再是正式评估硬门禁；正式本地评估以真实 case 执行为准。复杂 Skill 若所有本地 case 均 `run_incomplete`，应记录为 `LOCAL_EXEC_ALL_CASES_FAILED` 并用更轻量 Skill / fixture / 其他 Agent 做对照，而不是回退为 sample_io 或恢复 preflight gate。

### 架构防线（硬约束）

| 防线 | 规则 |
|------|------|
| **capability_full 触发门槛（W5.3.2）** | 同步 `assessment_gate`：`gap_zero` + `case_gate` + 无 L0 待澄清 + 安全非 blocked → **自动** `capability_full`；作者路径不跑 degraded 初评 / `readiness_result` |
| **Run quota（W5.1 GQ6）** | `auto_run_count` **仅计 `capability_full` 正式评估**；超限 → `CONVERSATION_QUOTA_EXCEEDED` + frozen |
| **专家冻结** | `conversation.status=frozen` → `/chat` 403；Expert Reject 解冻 + 驳回意见注入 lui_messages |
| **Session Lock** | staging mutation 前：frozen → 403；active_run RUNNING → 409 |
| **侧栏归档（W5.5）** | `DELETE /conversations/{id}?perspective=` → `archived_at` 软删；保留 messages/runs/staging；作者不可删 frozen/待审；专家可删；运行中 409；MVP 无 purge |
| **原稿 vs 练习区** | `originals/` 只读保留用户上传；`staging/` 为评估脚手架；**阶段三不上架**，阶段四再做 listing Export |
| **Security Gate** | `blocked` → 不进 Propagator/评审；`warning` → 继续并展示证据；后置 PII/token sanitizer |

---

## Wave 0 — 基础设施 ✅ 收官（235 tests）

- [x] **W0-1～W0-5** conversations / run lineage / staging / lui_messages DDL；BundleResolver；Session Lock 指针

---

## Wave 1 — 场景分类词表（Q-08）✅ 收官（250 tests）

- [x] **W1-1～W1-6** `category_taxonomy.yaml` + taxonomy 模块 + malformed_cases + API + testskills 回填

---

## Wave 2 — Security Intake Gate ✅ 收官（292 tests）

- [x] **W2-1～W2-5** 静态规则 + output sanitizer + 引擎双注入

---

## Wave 3 — Staging Case Propagator ✅ 收官（328 tests）

- [x] **W3-1～W3-5** Propagator + Sanitizer + `POST /conversations/start` + 题型完整性门槛

---

## Wave 4 — LUI Agent + API ✅ 收官（367 tests）

- [x] **W4-T1～W4-T8** lui_agent + staging_writer + session gate + zip 上传 + Expert 联动（UI 已被 W5 取代）

---

## Wave 4.5 — Provider 完全 env 驱动（P2 预留）

> **OpenSpec change（拟）**：`provider-env-factory`
> **排期说明（2026-06-23）**：列入 P2，与 UI/engine 拆分等后续工程优化同窗口处理；不阻塞 P0/P1 hardening 与 W7 服务器彩排。

- [x] **W4.5-1** `JUDGE_PROVIDER_A_*` / `JUDGE_PROVIDER_B_*` settings
- [x] **W4.5-2** `OpenAICompatibleProvider` + deps 工厂
- [x] **W4.5-3** 报告/UI 用 env `LABEL`（含 per-case 表头、不可用横幅）；运维脚本走 factory；legacy provider 标 deprecated
- [x] **W4.5-4** `.env.example` + pytest 工厂装配

---

## Wave 5 — Chat-First 对话壳 ✅ 收官（400 tests）

- [x] **W5-T1～W5-T7** DB v3、rich_report、2 Tab UI、ZIP Composer、专家视角切换

---

## Wave 5.1 — 聊天简卡 + 报告分流 ✅ 收官（413 tests）

- [x] **W5.1-T1～W5.1-T7** 初评/正式分卡、自动正式评估、草案确认流

---

## Wave 5.2 — UI 透明化 ✅ 收官（447 tests）

- [x] **W5.2-T0～T7** deferred Propagator、三方式补题、readiness、verdict/next_action

---

## Wave 5.3 — 智能对话 + LLM 补题计划 ✅ 收官（472 tests）

- [x] **W5.3-T0～T11** enrich、confirm_lexicon、propagation 分叉、draft_preview

---

## Wave 5.3.2 — 评估门禁 + 自动正式评估 ✅ 收官（478 tests）

- [x] **W5.3.2-T1～T5** `assessment_gate`；满足条件自动 `capability_full`

---

## Wave 5.3.3 / 5.3.4 — 材料补充卡片 UX ✅ 收官

- [x] **W5.3.3** gate+plan 同批；复合卡「评估材料补充」；两按钮 + 中文 gap
- [x] **W5.3.4** UI 精修：2 列表格、gate pill、历史状态汉化

---

## Wave 5.5 — 本地 Demo 验收（runbook）🟡 进行中（剧本 A ✅）

- [x] **W5.5-0** **彩排热修（FB-16～18）**：达标 gate 只读；材料补充卡合并；专家视角裁定 + 弹窗
- [x] **W5.5-1** **剧本 A**：stock-radar ZIP → 材料补充复合卡 → L0 澄清 → 自动出题 → 正式双模型 → 追踪页 → 专家裁定（2026-06-12 实机通过）
- [ ] **W5.5-2** **剧本 B**：high-risk → R5 → 专家 Reject → 解冻复评
- [ ] **W5.5-3** **剧本 C**：quota 熔断 → Expert Approve → reset
- [x] **W5.5-4** 补题 gate + 材料补充合并 + 专家 Chip（随 W5.5-0/1 验收）
- [x] **W5.5-5** 历史 Tab：仅 capability_full 有详情入口（既有行为，剧本 A 已验）
- [ ] **W5.5-6** `docs/runbooks/phase3-eval-validation.md`：验收矩阵（W5.1–W5.4）

---

## Wave 5.5 UI — 制式回单 + 布局 + 会话归档 ✅ 收官（2026-06-12）

> **OpenSpec archive**：`openspec/changes/archive/2026-06-12-conversation-archive/`  
> **UI build**：`w5.5-form-archive-hints`（含 form / layout / archive / 删除提示）

- [x] **W5.5-UI-1** `[ui-only]` **制式回单**：`frontend-design` 方向三；token 换肤；机构题头/Tab；流水号牌；`trace.html` 同步（**w5.5-form**）
- [x] **W5.5-UI-2** `[ui-only]` **Layout A**：侧栏 `#session-list` 与 `#chat-messages` 独立滚动；输入栏贴底；固定视口高度（**w5.5-form-layout**）
- [x] **W5.5-UI-3** DB v8 `archived_at` + `archive_conversation()` + `DELETE /conversations/{id}` 视角门禁（**w5.5-form-archive**）
- [x] **W5.5-UI-4** 侧栏 × 软删除 + 确认框；删当前会话后自动选最新；`test_conversation_archive.py`
- [x] **W5.5-UI-5** 删除 UX：`archiveBlockReason` 预检；「需专家删除」标签；403/404 中文 toast；切换视角刷新侧栏（**w5.5-form-archive-hints**；FB-19/20 ✅；用户实机确认）
- [ ] **W5.5-UI-6**（Phase 2 可选）CLI `purge-archived --older-than 90d`

**测试路径备忘**：`frozen` / 待专家复核会话 **不可聊天**；全流程重测用 **+ 新对话** 或专家 **驳回** 解冻。

---

## Wave 5.4 — 评分过程留痕 + 追踪页（judge-trace）✅ 已收官 + 归档（498+ tests）

> **OpenSpec archive**: `openspec/changes/archive/2026-06-12-wave5.4-judge-trace/`（GQ1–GQ7 已锁定）  
> **Brainstorm spec**: `docs/superpowers/specs/2026-06-12-judge-trace-design.md`（D1–D7 已锁定）

- [x] **W5.4-T1** DB v7 `judge_traces` + Port 方法
- [x] **W5.4-T2** Prompt v0.5（每维 analysis/evidence_quotes/deductions；先分析后打分）+ prompt_text 落库
- [x] **W5.4-T3** `core/divergence.py` 分歧合成（gap≥15 自动；失败 degraded）
- [x] **W5.4-T4** `GET /eval/report/{run_id}/trace` API + `has_judge_trace`
- [x] **W5.4-T5** `/ui/trace.html` 追踪页（并排对照 + 分歧解读卡 + prompt 折叠）`[ui-only]`
- [x] **W5.4-T6** 主 UI：per-case「评分过程 →」链接 + 对话页就地弹报告模态 `[ui-only]`
- [x] **W5.4-T7** 全量回归 **498 passed**；GQ3 live 对比并入 **W5.5** runbook

## 阶段三后续（评估系统增强 · 待排期）

> 后续**新增功能与优化**在本节追加（由产品窗口驱动，不混入阶段四集市）。  
> **产品说明**：`docs/guides/Skill评估系统全景说明.md` **§10**（验证工程现状与演进路线）。

### P2 工程优化预留（2026-06-23）

- [x] **P2-1** `index.html` 模块化拆分：主业务脚本已抽到 `/ui/assets/index.js`，HTML 保留结构与启动配置，UI smoke 覆盖拆分资产
- [x] **P2-2** `engine.py` / `chat.py` 状态流拆分：阶段通知文案、评审 prompt、report 文件写入、补题后 gate payload 构建已拆分
- [x] **P2-3** **W4.5 Provider 完全 env 驱动**：provider factory、label/model/base_url 配置化、报告/UI 展示跟随 env
- [x] **P2-4** Release/测试环境整理：pytest basetemp/cache 固化到 `pyproject.toml`，新增 `docs/runbooks/p2-test-environment.md`

### Wave 8（重定义 2026-06-17）— 本地 Agent 执行桥

> **目标**：把"真实执行"下放到开发者本地已配好的 CLI agent（Cursor / Claude Code / Codex…），穿透握手让本地 agent 真跑 skill 并回传真实产出；SkillHub **judge 流水线（DSL/双模型/安全/聚合/决策）原样复用**，只替换 `actual_output` 来源。  
> **取代**：原 W8 Level 2 中央沙盒 + 原 W9 自建 Agent Harness（均废弃）；原 W10 Golden Case 移至阶段四。  
> **设计依据**：调研 `nexu-io/open-design`（local-first，daemon + per-agent adapter，stream-json）。  
> **背景**：中央 subprocess 沙盒**结构上跑不了内网 skill**（无 VPN/DB）；本地 agent 跑任务时已执行脚本，**中央代码跑冗余** → 砍掉、不留冗余 `PythonSubprocessRunner`（物理删除待执行期按安全协议确认）。  
> **状态**：🟢 W8.1–W8.3 / W8.5–W8.6 **已实现**（OpenSpec `local-agent-exec-bridge`，**583 tests**）；🟢 Q-24/Q-25 **已合入 main**（2026-06-30）；🟢 **W8.7/Q-26 adapter 框架已合入 main**（2026-06-30，网页 codex/cursor/trae Test 通过；2026-07-01 补 artifacts + Cursor probe hardening）；🟢 **local-agent-trial-hardening（Q-28）已实现**（2026-07-01，本地执行失败阻断而非静默降级 + 报告归属诚实性 + 4 项 UI 修复）；🟡 W8.4 多 agent 对照统计待排

**核心防线（已定，分阶段）：v1 信任本地**——judge（含双模型读 transcript）pass → PASS + 专家抽检；warn/R5 → 专家。**目标态**（多用户/上云）：公网题中央 agent 复跑高风险子集 + 双模型读 transcript；内网题双模型 + **专家签收**（复用现有专家流）。断言以结构性 + 语义为主（容忍 agent 非确定）。

- [x] **W8.0** `/brainstorm` 收口五岔路 → 设计稿 + OpenSpec change `local-agent-exec-bridge`（grill 已定稿）
- [x] **W8.1** 执行传输层：claude → codex → cursor-agent adapters + stream-json 解析 + Windows stdin spawn
- [x] **W8.2** `ExecutionSource` 接缝 + `entrypoint`/`execution_source` 元数据 + judge 双模式 prompt
- [x] **W8.3** 来源路由 + 降级 + `spot_check_eligible` + `level_2` 执行证据
- [ ] **W8.4** 多 agent 对照统计：同一 skill 多 agent 跑，收集对照数据
- [x] **W8.5** 安全边界：执行前同意 + Security Gate + output sanitizer + `HardenedProfile`（codex 红线）
- [x] **W8.6** `testskills/exec-fixture-minimal` + `docs/runbooks/local-agent-exec-validation.md` + E2E（`RUN_LOCAL_AGENT=1`）
- [x] **Q-24/Q-25（2026-06-24 实现，2026-06-30 核实已合入 main）**：五 Agent registry（`claude` / `codex` / `cursor-agent` / `trae` / `antigravity`）、agent/model 双选择、Trae/Antigravity adapter、有界并发 `case_executing`、rate-limit 降并发、risk 单题 timeout、本地 Agent 预算 UI、Provider 错误按因分类、Token usage 事件与 `EvaluationReport.usage_summary`；验证：focused backend 45 passed、engine/readiness 29 passed、JS check 通过、doc encoding OK。

#### W8.7（Q-26）— open-design 式可扩展 adapter 框架 ✅ 已合入 main（2026-06-30）

> **目标**：把"逐个写死 `build_args`"升级为**数据驱动可扩展框架**——registry 注册一条数据即新增/检测一个 CLI；启动**三态检测**本机 CLI（可用/未登录/未安装，含 PATH 外 + 带版本号目录）；按 CLI 发现/选择模型；并修好 trae 真跑。
> **grill 定稿（2026-06-30）**：原"自制 ACP JSON-RPC 传输"**废弃**——实测 `trae-cli` 原生支持 `--print --output-format stream-json`，trae 改走现有 stream-json 路径。计划 `docs/superpowers/plans/2026-06-30-local-agent-adapter-framework.md`；OpenSpec **已归档** `archive/2026-06-30-local-agent-adapter-framework/`。
> **合并**：`main` @ `d8c83b8`（含 smoke test 忽略全局 `exec_model` 热修）。

- [x] **W8.7-0** settings 超时键 + `AgentDef` 数据字段（`stream_format/config_dirs/install_dir_globs/version_args/model_probe/prompt_via_stdin`）+ 修正 trae 登记（`trae-cli`）
- [x] **W8.7-1** `install_hints` 静态安装指引（D4：只列不自动装）
- [x] **W8.7-2** 数据驱动检测 `detection.py`：PATH→登记目录(含版本通配)→npm→where 解析 + **三态 `auth_state`（ok/missing/unknown）** + TTL 缓存；`preferences` 改走 detection
- [x] **W8.7-3** 通用 `model_probe` 混合发现 `models.py`：trae=`trae-cli models`（live）/ cursor=`models` 优先 + `--list-models` fallback（live）/ 其余 fallback + 自定义保留；过滤未登录/无模型等非模型提示
- [x] **W8.7-4（重构）** trae 改 **stream-json** adapter（丢弃 ACP）；保留 `transport/` 按 `stream_format` 分派骨架，`acp-json-rpc` 为文档化扩展点（`NotImplementedError`）；执行入口经 `run_via_transport` 接缝
- [x] **W8.7-5** `scan` API 返真三态认证 + 发现模型 + 安装指引；UI 三态徽章 + 安装指引卡 + 模型来源标签 `[ui-only]`
- [x] **W8.7-6** 离线回归 + pre-existing 失败修复；`node --check` 通过
- [x] **W8.7-7（实机）** 网页 codex/cursor-agent/trae **Test** 通过；`RUN_LOCAL_AGENT=1` E2E codex+trae+cursor 通过；切换全局模型后点其他 agent Test 不受影响
- [x] **W8.7-8** cursor-agent `--list-models` live 列表 + Test 通过
- [x] **W8.7-9（hardening 2026-07-01）** local agent per-case workspace 执行前后快照；新增/修改小文本产物并入 `actual_output.artifacts`；structured JSON 与 artifacts 可共存；focused 回归 52 passed
- [x] **W8.7-10（Q-27，多人试用前置 2026-07-01）** `ExecResult.degrade_reason` 补进 `CaseScoreRow`（`exec_status`/`exec_degrade_reason`）→ `build_provider_summary` → UI per-case 红色「本地执行未完成」徽章 + hover 中文原因；`tests/core+adapters+execution` 513 passed（1 项既有无关失败）
- [ ] **（后续，Q-27 同批发现）** runbook 补「每人各自起 `serve`」部署说明（consent/exec_agent/exec_model 目前是进程级全局状态，非按用户区分）

#### local-agent-trial-hardening（Q-28）— 本地执行失败阻断，不再静默降级 ✅ 已实现（2026-07-01）

> 实测发现 Q-27 之后仍有更深问题：本地执行失败会被 `RoutingExecutionSource` 静默替换为 `sample_io`（`status` 改 `ok`），导致报告显示原选 Agent/模型「已成功执行」，同时暴露 4 项实测问题（loading 文案不一致、Cursor 徽章常驻待测试、Codex 路径溢出、Token 消耗表占位过大）。用户决策：**阻断而非静默降级**（按 case，不牵连全轮）+ 走完整 OpenSpec（`openspec/changes/local-agent-trial-hardening/`，未归档）。

- [x] **T1** `execution_source.py`：移除本地失败静默替换 `sample_io` 的逻辑，改为直接返回原始失败 `ExecResult`；保留 `redline_no_hardened_profile` 的刻意降级（非失败）
- [x] **T2** 失败原因经 `engine._log_local_agent_failure` 持久化为 `local_agent_failure` 事件（`case_id`/`degrade_reason`/`stderr_excerpt`，`ExecResult` 新增 `stderr_excerpt` 字段，截断 2000 字符）
- [x] **T3** `EvaluationReport` 新增 `exec_requested_agent_label`/`exec_requested_model_label`；`exec_agent_label`/`exec_model_label` 语义收紧为「仅真有 case 成功走 local_agent 才非空」，不再回退全局偏好伪装成已执行
- [x] **T4** 整轮阻断：全部 case 本地失败或预检无 agent 时复用 `RunStatus.failed`（`reason_codes` 新增 `LOCAL_EXEC_UNAVAILABLE`/`LOCAL_EXEC_ALL_CASES_FAILED`）；单 case 失败保持按 case `incomplete`，不牵连全轮（grill-me 定案粒度）
- [x] **T5 [ui-only]** `index.js` 新增 `pendingPhaseForCurrentStatus`：loading 文案按会话状态（非输入方式）选择，打字确认/纠正也显示「正在分析 Skill…」；`chat.py` 打字纠正分支补齐与确认分支一致的持久化消息
- [x] **T6 [ui-only]** `testExecAgent` 成功后乐观置 `auth_status=ok`（Cursor 徽章「待测试」→「可用」）；`renderExecAgentCards` 三卡路径统一 `break-all`
- [x] **T7 [ui-only]** `renderUsageSummary` 改为总计 + Provider A（DeepSeek）/ Provider B（Gemini）/ 本地 Agent 三分桶 + 「查看明细」弹窗（新增 `usage-detail-modal`）；`openRunDetail` 新增 `renderExecAttributionCard` 展示「已选择 X，未成功执行」或「X 已成功执行」
- [x] **T8** 回归 + 真机验证：`tests/core tests/adapters tests/execution` 518 passed/6 skipped（仅 1 项既有无关 UI contract 失败）；全量 700 passed（剩余 9 项为改动前既存，已用 `git stash` 对比 `main` 确认）；重启 server 后用 API 直接触发新 run（Trae/GLM-5.2，`run_id=9f5ff946...`）：`status=failed`、`reason_codes=LOCAL_EXEC_ALL_CASES_FAILED`、`exec_agent_label=None`（未伪装）、`exec_requested_agent_label=Trae`；`local_agent_failure` 事件确认 5 个 case 均为 `degrade_reason=run_incomplete`
- [ ] **（后续 backlog，非本次范围）** trae-cli 具体为何 `run_incomplete`（流式输出未读到结束标记）——CLI 层根因排查

#### Q-29（下一窗口主线）— 本地 CLI 模型真跑成功率排查

> Trae/GLM-5.2 真机测试 5 个 case **全部** `degrade_reason=run_incomplete`、`stderr_excerpt` 均为空。诊断（未改代码）：`runner.is_run_complete()` 依赖 `stream_parser.parse_stream_events()` 看到 `"type":"result"`/`"turn.completed"` 才算完成，这条 schema 假设从未用真实 trae-cli 输出校准过——`archive/2026-06-30-local-agent-adapter-framework/design.md` G7 早已标注「唯一需真机校准项」，此前单测用的是猜测样例。候选根因：①解析器/CLI 输出 schema 不匹配 ②`--yolo --permission-mode bypass_permissions` 未覆盖全部确认场景导致超时挂起。用户已并行让 Codex 跑一次独立 review + 分析，结论带入下一窗口再定修复顺序，避免重复排查。

- [x] **N1** 拿到 Codex review 结论后，补 `run_incomplete` 诊断证据链：Trae 的 `is_error` completion 现已被识别为真实失败，且 scan/test 暴露本机 Trae 配置/权限根因（Q-29 commits）。
- [x] **N2** 据实证修正/扩展 `stream_parser.py` 的完成事件识别：`result`/`turn.completed` 的 `is_error` / `error_during_execution` 不再被当成成功完成（Q-29 commits）。
- [x] **N2.1（2026-07-02 真机复验，8.10 部分完成）** Trae/GLM-5.2 实测跑通确认（`is_error:false` 真实完成），证明 N1/N2 的修复在真机上有效；顺带发现并修复 `TraeAdapter.diagnose()` 假阳性 bug（`TRAE_MODEL_NOT_CONFIGURED` 在模型明明能跑时误报，原诊断建议"手改 `trae_cli.yaml` 补 `models:`"是错的——GLM-5.2 是内置模型不需要该字段）；改为先信任 `is_model_verified_live()`，`models:` 只作探测失败时的兜底信号（design.md D13）；TDD 补 2 条回归测试，全量 728 passed/6 skipped/9 failed（既有基线）。Codex CLI 本轮卡在账号额度（非代码 bug），Cursor Agent 需补一次真实 fixture 验证——8.10 整体未收口。
- [x] **N2.2（2026-07-02 续）** 真实 `exec-fixture-minimal` 全流程测试发现并按 TDD 修复 `CursorAgentAdapter.parse_stream()` 真实 bug（从未识别真实 `tool_call`/`result` 事件形状，导致 `missing_entrypoint_evidence`/`final_text` 空，design.md D14，731 passed/6 skipped/9 failed）；Trae 确认结构性缺少 `python` 等命令执行权限，非配置问题（D15，当时暂开放，本轮已解决见 N2.3）；D14 修复后网页真机复测又发现 Cursor Agent `run_incomplete` 真正根因是本机 `cursor-agent` CLI **安装本身损坏**（大批 JS chunk 缺失），同一根因导致模型列表退化成写死的 `Default`/`GPT-5`（D16，本轮已核实用户跑过 `cursor-agent update` 并复测通过）。
- [x] **N2.3（2026-07-02 收尾）** 核实 Cursor Agent 已收口（`cursor-agent update` 后版本恢复，`RUN_LOCAL_AGENT=1` E2E fixture 1 passed）。用户带回 Trae CLI 自诊断结论：`--allowed-tool`/`allowed_tools` 是叠加机制非硬编码限制（解答 N4，见下）——按 TDD 在 `TraeAdapter.build_args()` 补 `--allowed-tool Bash`（D17，解决 D15）；解锁后发现并修复两个新真实 bug：Windows cmd.exe 中文+空格绝对路径 `cd` 缺陷（`harness_prompt.py` 补通用提示，D18）、`TraeAdapter.parse_stream()` 与 D14 同类的 `tool_result` 事件解析 bug（补归一化，D19）。三修复叠加后 Trae/GLM-5.2 与 Cursor Agent 对 `exec-fixture-minimal` **均返回 `status=ok`**；全量回归 **742 passed/9 failed**（既有基线不变，净增 4）。**剩余**：Codex CLI 本机当前 shell `codex` 不在 PATH，未在本轮验证，8.10 整项待 Codex 补测后再勾选。
- [x] **N2.4（2026-07-02 完全收官）** Codex 额度重置后真机跑 `exec-fixture-minimal`，发现并按 TDD 修复与 D14/D19 同类的解析器 bug——`CodexAdapter.parse_stream()` 从未识别 `codex exec --json` 真实的 `type:"item.completed"` + `item.type:"command_execution"` 事件形状（D20）；修复后 `status=ok`。三个本地 Agent（Codex/Cursor Agent/Trae）全部确认端到端跑通，**8.10 整项勾选，Q-29 完全收官**。
- [ ] **N3** 把「`exit_code==0` 但无完成事件（疑似解析器漏判）」与「真超时被杀」拆成两个不同 `degrade_reason`，而不是都归为 `run_incomplete`
- [x] **N4** 核实 `--yolo --permission-mode bypass_permissions` 是否覆盖 trae-cli 全部确认场景——**结论**：不覆盖，二者管的是完全不同的事。`bypass_permissions`/`--yolo` 只跳过确认弹窗；`--allowed-tool`/`allowed_tools` 才是决定模型能看到哪些命令的白名单，且是叠加而非替换默认集（见 design.md D17）
- [x] **N6（2026-07-02）** 排查网页上一次真实卡住的 Cursor Agent 评估（`case_executing` 停留 50+ 分钟远超配置超时），确认 `LocalAgentRunner._stream_until_complete()` 的 `proc.stdin.write()` 此前阻塞主线程、发生在超时截止时间循环建立之前，导致 `timeout_s` 从未真正生效；叠加 Windows `.cmd` 包装进程 `proc.kill()` 只杀直接子进程、留下 `node.exe` 孙进程变孤儿的问题。按 TDD 修复：stdin 写入移到后台线程 + 新增 `_kill_process_tree()`（Windows 用 `taskkill /PID <pid> /T /F` 整树终止），详见 design.md D21
- [ ] **N5**（视诊断结果决定是否需要）按 agent/模型差异化本地执行超时，而不是只按 case 风险等级分档
- [ ] **（后续）** UI 选 trae 模型 → 跑 `exec-fixture-minimal` 出 Pass/Warn/Fail（正式评估纵切，非阻塞框架收口）
- [ ] **（未纳入 grill 范围）** 多策略 skill 注入 / 归一化 AgentEvent / fallback chain / W8.4 多 agent 对照统计

#### local-cli-runtime-platform — 产品化 runtime 底座 🟡 待网站真实测试后收尾（2026-07-07）

> **定位**：在 Q-29 三个本地 Agent 端到端跑通之后，把本地执行层继续向 `nexu-io/open-design` 的 local-first CLI runtime 形态靠拢。它不是改评分系统，而是把「选择 runtime → 检测 → 注入 skill → preflight → 真跑 → 归一化事件 → 失败归因」做成一套可复用平台。评分、R1-R8、专家流、报告聚合继续沿用现有逻辑。
> **计划来源**：Superpowers 计划 `docs/superpowers/plans/2026-07-02-local-cli-runtime-platform.md` 指导实施；OpenSpec `openspec/changes/local-cli-runtime-platform/tasks.md` 作为当前任务勾选口径。计划文件保留原始拆解，不机械同步全部 checkbox。

- [x] **Runtime contract / catalog**：新增五 runtime 定义（Codex / Cursor Agent / Trae / Claude / Antigravity），保留与现有 `AgentDef` 的兼容桥。
- [x] **AgentEvent 归一化**：五个 adapter 统一走 normalized event → parsed stream / `ExecResult`，保留既有行为兼容测试。
- [x] **Skill injection**：实现 native / file-placed / prompt fallback 策略与 prompt-size guard；未知 runtime 明确失败，不静默绕过。
- [x] **Preflight platform（2026-07-08 口径修订）**：SQLite 24h cache + fingerprint invalidation + API action 保留为手动诊断；正式本地评估不再自动跑 preflight，也不因 preflight 缺失/失败/过期阻断 `case_executing`。
- [x] **确定性轻量检查用例**：高风险 Skill 缺本地执行环境检查用例时，默认使用平台固定轻量模板；旧 LLM/重型系统检查题会自动迁移回模板；默认产品路径不调用 Provider A / LLM，authored safe preflight 仅静默兼容。
- [x] **Failure taxonomy**：把 `agent_unavailable` / `run_incomplete` / `missing_entrypoint_evidence` / parser failure 映射到稳定 runtime failure reason，并透传到事件、报告与基础 UI 文案。
- [x] **基础 UI/API 验证**：报告详情和对话顶部已有「环境检查」诊断动作；runtime 失败展示与本地 Agent case 进度可见；回归 `589 passed / 6 skipped`，`node --check` 通过。
- [x] **补强项（2026-07-07）**：显式切换已检查通过的本地工具时保留已验证 `runtime+model`，不再固定 `default`；stream sanitizer 增强 Windows 含空格/中文路径脱敏；相关回归 `646 passed / 6 skipped`，`node --check`，`check_doc_encoding.py`。
- [x] **网站真实测试第一轮（2026-07-08）**：stock-radar + Cursor Agent/Auto 确认进入真实 `case_executing`，但复杂 Skill 多个 case `run_incomplete` 后整轮 `LOCAL_EXEC_ALL_CASES_FAILED`；结论是 runtime/model 对复杂 Skill 的真实执行失败，不是 preflight gate 或 judge bug。
- [x] **UI 进度与性能热修（2026-07-08）**：live progress 限高滚动、最后刷新时间、轮询失败提示、前端轮询防重入、messages/session list 节流、后端运行态 status 跳过 bundle 重扫。
- [x] **环境检查 UI 时机与过程态（2026-07-09）**：ZIP/bootstrap 返回 `staging_path` + 前端缓存；上传后即可在执行设置点「运行环境检查」；顶栏 B3 状态 pill（未检查/检查中/已通过/未通过，不直接 POST）；未检查一律 `missing` 可点；过程态与结果持久显示；抽屉 overlay 不挡「确认继续」；确认态忽略残留 ZIP。设计/计划：`docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md`、`docs/superpowers/plans/2026-07-09-env-check-ui-timing.md`。用户实机确认可用。可选后续：P1 status 始终带 `staging_path`。
- [ ] **后续网站对照测试**：用更轻量 Skill / `exec-fixture-minimal` / 不同 Agent 跑对照，确认平台路径稳定后再 archive。
- [ ] **产品化收尾**：真实 stream fixture 固化、raw stream 捕获/sanitizer、`RUN_LOCAL_AGENT=1` live E2E 扩展、runbook 补全、OpenSpec archive。
- [x] **成熟 UI runtime 面板 P0**：安装/登录/模型/环境检查/过期时间/失败原因一眼可见；显式「切换到已验证 runtime 并重跑」，不做自动切换。

**建议顺序**：W8.0 → W8.1 → W8.2 →（先用专家签收兜底 PASS 跑通"真输出→评估"闭环）→ W8.3 / W8.5 → W8.6 → W5.5 本地验收收官；W8.4 与服务器部署（阶段四 W7）可并行排期。

> **Golden Case + 上架后健康检查（原 W10）已移至阶段四**（与上架联动，见 `SPRINT_phase4-marketplace-biz.md`）。`PythonSubprocessRunner` 组件留架子，若阶段四 Golden Case 需"精确断言 + 确定性复跑"再按需接最小版。

---

## Out of Scope（阶段三明确不做）

| 项 | 归哪一阶段 | 原因 |
|----|------------|------|
| **Skill 集市 / listing / Trending / NL 搜索** | **阶段四** | 评估系统与消费发现解耦；先跑通评估再上架 |
| **publish Export + Freeze** | **阶段四** | 依赖 listing 与集市 IA |
| **服务器部署 / release zip / Linux smoke（原 W7）** | **阶段四** | 阶段三仅本地评估；上云与多人协作归阶段四 |
| **独立 Portal / IAM / SSO** | **阶段四** | 立项与商业化窗口细化 |
| **1.2 阈值 / R5 10 分线修改** | — | 已锁定 |
| **真实网关调用统计 / 生产级推荐** | **阶段四** | 需集市与使用数据 |
| **多 Skill 同一会话** | — | 超出 MVP |
| **独立 LLM 安全评审 Agent** | — | 静态规则 + adversarial case 复用 |
| **方差 Markdown 报告导出** | — | 阶段二已取消，脚本保留 |

---

## 执行顺序

```
W0 → W1 ∥ W2 → W3 → W4 → W5 → W5.4 → W5.5 → W8（本地真跑）
         ↑___↑
       可并行

（W5.4 在 W5.5 Demo 验收前落地）
（2026-06-17 重定向：W8 = 本地 Agent 执行桥 W8.0→W8.6；W9 自建 Harness 废弃；W10 Golden Case 移阶段四）
（2026-06-23 重定标：原 W7 服务器部署移阶段四；阶段三止于本地评估验收）
```

---

## 验收标准

| 里程碑 | 条件 |
|--------|------|
| Wave 3 通过 | `POST /conversations/start` + 题型门槛 + Propagator |
| Wave 4–5.4 通过 | Chat-First 全链路；assessment_gate 自动正式；judge-trace；498+ tests |
| **W5.5 通过** | 三剧本**本地**实测通过；`phase3-eval-validation.md` runbook 完整（**剧本 A ✅**；**UI 制式/归档 ✅**） |
| **W8 通过** | 本地 CLI agent 真跑 ≥1 个 skill（含 1 个可执行 fixture）→ 回传真实产出 → judge 复用出 Pass/Warn/Fail；本地=readiness，PASS 走分级信任（公网中央复核 / 内网专家签收）；现有 tests + fixture 不回归 |
| **阶段三收官** | **本地**可独立演示（上传→补题→**本地 agent 真跑**→正式评→专家裁定），**无需服务器、无需集市 Tab** |
| ~~W9 / W10~~ | W9 自建 Harness **废弃**（本地 agent 即分布式 Harness）；W10 Golden Case **移阶段四** |
