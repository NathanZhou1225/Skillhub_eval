# Phase 2 · Phase 1 Implementation Plan（2.1-fix / 2.3b / 2.3a / testskills 闭环）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Gate:** 本计划经 **grill-me** 挑刺通过后，方可按序执行。执行前勿改 1.2 rubric 阈值与 1.3 状态闸门。

**Goal:** 在 2.0 工程基线上完成 Phase 1：minimal 包引导补全 → confirm → 全量评闭环；全终态轻量 report；R5 双模型 + per-case 分数可视化；降低 `EVAL_WORKFLOW_TIMEOUT`；`testskills/` 三样本验收。

**Architecture:** Level0 拆为「结构门禁」与「case 数门禁」两阶段——pre-confirm（`bundle_state != confirmed` 且非 degraded）仅做结构 + risk_lock，写 gaps/report 后停于 `awaiting_confirm`；**degraded 跳过 case gate**（0 case → case_exec 空跑 → completeness 驱动 WARN）；confirmed 跑完整 case gate（X1）后走评审。Report 增补 `provider_summary`（包级 + per-case）+ `stage_progress`（来自 `stage_transitions` 表）；UI 三 Tab 消费同一 report 契约。Case 评审 `Semaphore(3)` 受控并行 + risk 分级 workflow timeout。

**Tech Stack:** Python 3.11+ · FastAPI · SQLite · asyncio · Vanilla JS + Tailwind CDN · pytest · 现有 `EvaluationEngine` / `AggregateStage` / `Level0Checker`

**样本路径（Q-04 首版）：**

| Skill | 路径 | 用途 |
|-------|------|------|
| stock-radar-V6.2 | `testskills/stock-radar-V6.2/` | 全量评 + R5 人工复核 |
| grill-me | `testskills/grill-me/` | minimal 补全闭环 |
| tiered-memory-sprint-manager | `testskills/tiered-memory-sprint-manager/` | minimal 补全闭环 |

---

## 硬约束（继承 2.0，禁止违反）

1. PASS 仅当 `bundle_state=confirmed` 且 `evaluation_mode=capability_full`。
2. R5 触发时 `score_total=null`（禁止用均分掩盖分歧）；UI 须**额外**展示各模型分数，不得把 null 当「未评」。
3. 降级/未确认 draft 不参与 CodeAssert 失败判定。
4. 不重写 1.2 阈值；2.2 对抗集**不在本窗口**。

---

## 文件结构变更预览

| 文件 | 职责 |
|------|------|
| `skillhub_eval/core/level0.py` | 新增 `check_structure()` / `check_case_gate()` 或 `skip_case_gate` 参数 |
| `skillhub_eval/core/gaps.py` | **新建** — 缺口扫描清单（T2） |
| `skillhub_eval/core/schemas/report.py` | 新增 `ProviderSummary`、`CaseScoreRow` |
| `skillhub_eval/core/engine.py` | 编排分叉、全终态 report、并行 case、timeout 分级 |
| `skillhub_eval/core/aggregate.py` | 导出 per-case 聚合供 report（可选 helper） |
| `skillhub_eval/adapters/api/routes/eval.py` | report 响应 enrich |
| `skillhub_eval/adapters/ui/static/index.html` | gaps 联动、模板、R5/per-case UI |
| `testskills/_templates/` | **新建** — eval_case / sample_io / frontmatter 模板（T3/T8） |
| `tests/core/test_level0.py` | 结构 vs case gate 拆分测试 |
| `tests/core/test_gaps.py` | **新建** |
| `tests/core/test_engine.py` | minimal→awaiting_confirm、report 终态 |
| `tests/test_e2e_smoke.py` | 扩展 S3 minimal 路径 + provider_summary |

---

## Task 1（T1）：2.1-fix 编排 — pre-confirm 跳过 case gate

**Files:**
- Modify: `skillhub_eval/core/level0.py`
- Modify: `skillhub_eval/core/engine.py`
- Test: `tests/core/test_level0.py`, `tests/core/test_engine.py`

**行为规格（grill-me Q1/Q5 已锁）：**

```
ingest → check_structure(SKILL.md 存在、risk_level 可解析)
  → 若 fail → failed + report
  → risk_lock
  → 若 NOT confirmed AND NOT degraded:
       → gaps + awaiting_confirm + 轻量 report（T4 字段占位，T2 接 gaps）
       → return（不跑 case gate、不调 LLM）
  → 若 degraded:
       → 完全跳过 case gate（0 case → case_exec 空跑 → no assertions → agg completeness 驱动 WARN）
       → 后续现有流程
  → 若 confirmed:
       → check_case_gate（X1）→ fail 若不满足
       → 后续现有流程
```

- [ ] **Step 1:** 写 failing test — `minimal + capability_full`，0 cases → `awaiting_confirm`（非 `RISK_CASE_COUNT_INSUFFICIENT` failed）
- [ ] **Step 2:** 实现 `Level0Checker.check_structure()` 与 `check_case_gate()` 分离
- [ ] **Step 3:** `engine._execute` 在 C-3 分支前仅调 structure check；case gate 移到 confirm 后继续路径
- [ ] **Step 4:** 跑 `pytest tests/core/test_level0.py tests/core/test_engine.py -q`

**验收：** `grill-me` 目录 `minimal + capability_full` → status=`awaiting_confirm`

---

## Task 2（T2）：Gaps 引擎 — 缺口清单

**Files:**
- Create: `skillhub_eval/core/gaps.py`
- Modify: `skillhub_eval/core/engine.py` (`_build_gaps_snapshot` 委托 gaps 模块)
- Test: `tests/core/test_gaps.py`

**清单项（每项 → gap 对象 + required_action 文案）：**

| 检查 | severity | 说明 |
|------|----------|------|
| `description` 空 | warn | frontmatter |
| `risk_level` 未声明 | info | 默认 low，提示显式声明 |
| `eval_cases/` 缺失 | block | 全量评阻断 |
| case 数 < X1 min | block | 含 risk、缺几个 |
| case 数 > X1 ceiling | block | |
| 无脚本且无 `sample_io/` | block | L1 路径 |
| 安全字段未确认 | warn | negative_prompts 等 4 项 |

- [ ] **Step 1:** 写 `test_gaps_detects_missing_eval_cases`
- [ ] **Step 2:** 实现 `scan_gaps(bundle, bundle_state) -> GapsSnapshot`
- [ ] **Step 3:** engine 在 awaiting_confirm 路径调用并 `save_gaps`
- [ ] **Step 4:** pytest 全绿

**验收：** gaps JSON 含结构化 `gaps[]` + `required_actions[]`；**不含**可复制模板正文（模板归 T3）

---

## Task 3（T3）：UI 补全台 — API 联动 + 模板

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/eval.py` 或新增 gaps route（若需 `GET /bundle/{id}/gaps`）
- Modify: `skillhub_eval/adapters/ui/static/index.html`
- Create: `testskills/_templates/eval_case.yaml.tpl`
- Create: `testskills/_templates/sample_io.json.tpl`
- Create: `testskills/_templates/frontmatter_snippet.yaml.tpl`

**UI 行为：**

1. `loadGaps(skill_id)` 调用 API 读取最新 gaps snapshot（按 skill_id 或 run_id）
2. 按 gap severity 分区渲染清单（block / warn / info）
3. 对 block 类缺口展示**可复制模板**（从 `_templates/` 或内联 JS 常量）：
   - eval_case 最小 YAML（id / type / user_intent）
   - sample_io 最小 JSON
   - frontmatter `risk_level: low` 片段
4. 安全字段仍保留 confirm 表单；提交 `POST /bundle/{id}/confirm`
5. 提示：**结构文件须保存到 Bundle 路径**后，以 `confirmed + capability_full` 重新发起评估

**结构文件说明（T8 闭环前提）：**  
当前 confirm API **只持久化元数据字段**，不写 `eval_cases/` 到磁盘。作者按 UI 模板在 `testskills/<skill>/` 下手动创建文件（或后续可选 scaffold CLI，本计划不强制）。

- [ ] **Step 1:** 确认/补 `GET` gaps 端点返回最新 snapshot
- [ ] **Step 2:** 写 `_templates/` 三文件
- [ ] **Step 3:** 重写 `loadGaps()` + 模板复制按钮（clipboard）
- [ ] **Step 4:** awaiting_confirm 轮询结束时自动填充 skill_id 并提示「查询 Gaps」

**验收：** grill-me minimal run 后 UI 显示「缺 3 个 case」+ 可复制的 case 模板

---

## Task 4（T4）：2.3b 轻量 report — 全终态写入

**Files:**
- Modify: `skillhub_eval/core/schemas/report.py`
- Modify: `skillhub_eval/core/engine.py`
- Test: `tests/core/test_engine.py`

**终态 report 最小字段集：**

```python
# awaiting_confirm / timeout / failed(level0)
{
  "status", "risk_level_locked", "orchestration_mode",
  "completeness_score",  # 若已算
  "reason_codes", "evidence", "required_actions",
  "gaps": [...],           # 或引用 gaps snapshot id
  "stage_progress": ["level0_checking", "risk_locking", "awaiting_confirm"],
  "score_total": null,
  "score_total_source": "not_applicable" | ...
}
```

- [ ] **Step 1:** test — awaiting_confirm run 的 `GET /eval/report/{id}` 返回非空 `report`
- [ ] **Step 2:** `_park_awaiting_confirm()` helper：写 report + gaps + status
- [ ] **Step 3:** timeout 路径（`run_async` except TimeoutError）写 report + stage_progress + reason
- [ ] **Step 4:** Level0 structure fail 已有 `_save_fail`，补 `stage_progress`

---

## Task 5（T5）：R5 可视化 — provider_summary + per-case

**Files:**
- Modify: `skillhub_eval/core/schemas/report.py` — 新增模型：

```python
class CaseScoreRow(BaseModel):
    case_id: str
    deepseek_score: float | None
    gemini_score: float | None
    gap: float | None
    ds_suggested_status: str | None
    gemini_suggested_status: str | None

class ProviderSummary(BaseModel):
    deepseek_score: float | None      # 包级均值
    gemini_score: float | None
    score_gap: float | None
    r5_triggered: bool
    deepseek_bundle_status: str | None
    gemini_bundle_status: str | None
    per_case: list[CaseScoreRow]
```

- Modify: `skillhub_eval/core/engine.py` — 从 `all_votes` + `agg` 构建并写入 report
- Modify: `skillhub_eval/adapters/api/routes/eval.py` — 顶层 `provider_summary` 便于 UI
- Modify: `skillhub_eval/adapters/ui/static/index.html`

**UI 规格：**

| 位置 | 展示 |
|------|------|
| 作者台 run-status | 包级 DS / Gemini 分数条 + Δ；R5 时文案「模型分歧，综合分暂不可用」 |
| 专家审核台卡片 | 同上 + **per-case 表格**（case_id / DS / Gemini / Δ / 建议状态） |
| 历史详情 | 替换 `alert()` 为模态或内联折叠（至少展示 provider_summary） |

- [ ] **Step 1:** test — R5 run report 含 `provider_summary.per_case` 长度 = n_cases
- [ ] **Step 2:** 实现 `_build_provider_summary(votes, agg)`
- [ ] **Step 3:** 作者台 + 专家台 UI（专家卡 fetch `/eval/report/{run_id}`）
- [ ] **Step 4:** 人工 approve 后卡片保留 per-case 快照 + 「专家裁定」标注

---

## Task 6（T6）：终态文案分叉

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/index.html`

| 条件 | 文案 |
|------|------|
| `status=awaiting_confirm` | 「待作者补全，尚未进入模型评审」 |
| `score_total_source=null_due_to_disagreement` | 「模型分歧（R5），综合分暂不可用」+ 展示双模型分 |
| `reason_codes` 含 `EVAL_WORKFLOW_TIMEOUT` | 「评估超时」+ stage_progress |
| 正常 completed | `score_total/100` |

- [ ] **Step 1:** 抽取 `formatScoreDisplay(d)` 函数
- [ ] **Step 2:** 作者台 + 专家台 + 历史统一调用

---

## Task 7（T7）：2.3a 时延优化

**Files:**
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/providers/deepseek.py`, `skillhub_eval/providers/gemini.py`（timeout/retry 参数）
- Modify: `skillhub_eval/core/schemas/enums.py` 或 `settings` — risk → workflow_timeout 映射

**规格（grill-me Q2 已锁）：**

| 项 | 值 | 说明 |
|----|------|------|
| workflow timeout | low/medium: 300s；high: 600s | 按 risk_level_locked 分级 |
| case 并发 | `asyncio.Semaphore(3)`（DS + Gemini 共享） | 付费档 DS ~120 RPM 容忍；峰值 6 并发 |
| provider 单 call timeout | **45s** | DS 实测 15–25s；45s 留余量 |
| 重试策略 | 503/429 → 指数退避 max 3×，base 1s | 服务端 burst 自愈；非 RPM 拦截 |
| 埋点 | `repo.log_event(run_id, "stage_timing", {stage, ms})` | 每阶段耗时；慢 case top-N |

- [ ] **Step 1:** test — mock provider 延迟，验证并行比串行快（单元级）
- [ ] **Step 2:** 实现 case 并行 + semaphore
- [ ] **Step 3:** `_workflow_timeout` 按 `risk_level_locked` 分级
- [ ] **Step 4:** stage_timing 埋点
- [ ] **Step 5:** live 复测 `stock-radar-V6.2` confirmed full 不 timeout

---

## Task 8（T8）：testskills 三样本跑通矩阵

**Files:**
- Create: `docs/runbooks/testskills-phase1-validation.md`（或 Sprint 内嵌验收表）
- Create/Modify: `testskills/grill-me/eval_cases/*.yaml` 等（**补全后**用于闭环验收，可提交最小 3 case）
- Create/Modify: `testskills/tiered-memory-sprint-manager/eval_cases/*.yaml` 同上

**验收矩阵（必须全部通过）：**

| # | 样本 | 步骤 | 预期终态 |
|---|------|------|----------|
| 1 | grill-me | minimal + capability_full | `awaiting_confirm` + gaps 含 case/sample_io |
| 2 | grill-me | 按 UI 模板补 3 case + sample_io + risk_level + confirm 字段 → confirmed + full | `completed` / `warn` / `awaiting_human_review`（任一合法终态，非 failed/timeout） |
| 3 | tiered-memory | 同 #1–#2 | 同 |
| 4 | stock-radar | confirmed + capability_full | 完成评审；若 R5 → 专家台可见 per-case 分数 |
| 5 | stock-radar | minimal → gaps → 补全 → confirm → full | 可选回归 |

**grill-me / tiered-memory 最小补全包（T8 参考）：**

```
testskills/<skill>/
  SKILL.md          # 加 risk_level: low
  eval_cases/
    c01.yaml        # happy_path
    c02.yaml        # edge
    c03.yaml        # happy_path 或 refusal（low 不要求 adversarial）
  sample_io/
    c01.json        # 最小 actual 字段供 L1
    c02.json
    c03.json
```

- [ ] **Step 1:** 文档化 runbook（CLI + UI 步骤）
- [ ] **Step 2:** 为两 minimal skill 创建上述最小补全文件（用于自动化/手工验收）
- [ ] **Step 3:** 跑通矩阵并记录终态、耗时、reason_codes 到 runbook

---

## Task 9（T9）：文档同步

**Files:**
- Modify: `RECORD.md`
- Modify: `.cursor_memory/active/SPRINT_skillhub-mvp.md`

- [ ] 更新 Q-04 为 testskills 三样本
- [ ] In-Progress → Phase 1 任务 T1–T8
- [ ] 决策表：Level0 拆分、provider_summary、结构文件手动落盘
- [ ] 变更流水一条

---

## 执行顺序

```
T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T9
         ↑ gaps 清单    ↑ report 基础
              ↓ 模板依赖 T2 清单项
T5/T6 可部分并行；T7 在 T5 report 字段稳定后；T8 最后 live 验收
```

---

## grill-me 决策记录（已全部锁定 ✅）

| Q | 问题 | 决定 |
|---|------|------|
| Q1 | degraded + minimal case gate | **B**：跳过 case gate，0 case → 空跑 → completeness WARN |
| Q2 | Semaphore + Provider 重试 | **B 变体**：Semaphore(3)，45s timeout，503/429 指数退避 max 3× base 1s |
| Q3 | Gaps API 端点 | **A**：`GET /bundle/{skill_id}/gaps`；report 内联 gaps |
| Q4 | per-case UI 折叠 + 高亮 | **B**：`<details>` 折叠；Δ≥15 浅红高亮 |
| Q5 | 落盘检测与 bundle_state 切换 | **B**：UI 软提示 checklist + Mode D case gate 硬报错；不加 422 |
| Q6 | approve 后 report 回写 | **A**：`submit_review` 后重新 save_report，human_review 字段写入 report_json |
| Q7 | sample_io 内容 | **A**：`{"response":"ok","status":"completed"}` 占位符 |
| Q8 | 多 reason_code 文案优先级 | **A**：LEVEL0 > TIMEOUT > R5；已算分照常展示 + 「仅供参考」 |

---

## 不在本计划范围

- 2.2 对抗性用例集
- 2.3 Prompt 校准 / 2.4 上架后健康检查
- Portal / PDF 导出
- 自动 scaffold 写盘 API（若 grill-me 强烈需要，可降为 T3 可选子任务）

---

## 参考资料

- `docs/specs/评审Agent工作流与Prompt骨架.md` v0.2 — C-3 双阶段
- `docs/specs/评估指标与准入标准.md` v1.2.1 — R5 / X1
- `docs/superpowers/plans/2026-06-02-phase2-eval-engine.md` — 2.0 基线
- `RECORD.md` · `.cursor_memory/active/SPRINT_skillhub-mvp.md`
