# Tasks: UI/UX Improvement

> 实现真源：本文件。Subagent 执行前必须读 `design.md` 确认接口细节。
> 验证命令：每任务末注明；整体门禁 `pytest tests/ -x`。

---

## Task 1 — C-01/D-02：Prompt 加中文简洁指令 + 字数约束

**文件**：`skillhub_eval/core/engine.py`

**改动 1**：`_build_prompt` 方法，在 `"【三维子项】..."` 行之后、`"【输出格式】..."` 行之前，追加一行：
```python
"\n请用简洁中文填写所有 reason、dimension_notes 字段，每项不超过 30 字，禁止技术术语。\n"
```

**改动 2**：`_generate_skill_summary` 方法，将 skill summary prompt 的占位符改为带字数约束：
- `"<1句话总结该技能当前质量>"` → `"<1句话总结，不超过20字>"`
- `"<优势1>", "<优势2>"` → `"<优势，不超过15字>", "<优势，不超过15字>"`
- `"<不足1>", "<不足2>"` → `"<不足，不超过15字>", "<不足，不超过15字>"`

**验证**：
```bash
pytest tests/core/test_engine.py::test_prompt_no_hardcoded_scores -v
pytest tests/core/test_engine.py::test_skill_summary_field_populated_on_pass -v
```

---

## Task 2 — B-03 Backend：Approve 后重建 narrative

**文件 1**：`skillhub_eval/persistence/sqlite.py`

`patch_report_after_human_review` 签名加可选参数 `narrative_override=None`：
```python
def patch_report_after_human_review(
    self,
    run_id: str,
    action: str,
    operator: str,
    comment: str,
    review_status: str,
    narrative_override=None,   # ← 新增
) -> None:
    ...
    if narrative_override is not None:
        report["narrative"] = (
            narrative_override.model_dump()
            if hasattr(narrative_override, "model_dump")
            else dict(narrative_override)
        )
    report["human_review"] = hr
    ...
```

**文件 2**：`skillhub_eval/adapters/api/routes/eval.py`

`submit_review` 中，在 `repo.save_human_review(...)` 之前，approve 时构造 narrative override：
```python
from skillhub_eval.core.report_narrative import build_report_narrative

narrative_override = None
if body.action == "approve":
    report_data = repo.get_report(run_id) or {}
    ps = report_data.get("provider_summary") or {}
    nar = build_report_narrative({
        "review_status": "pass",
        "reason_codes": [],
        "required_actions": [],
        "score_total": run.get("score_total"),
    })
    if ps.get("deepseek_score") is not None:
        score_str = f"DS 参考分 {ps['deepseek_score']}"
        if ps.get("gemini_score") is not None:
            score_str += f" / GM 参考分 {ps['gemini_score']}"
        nar = nar.model_copy(update={"score_display_zh": score_str})
    narrative_override = nar
```

然后将 `narrative_override` 传入 `repo.patch_report_after_human_review(...)` 调用。

**验证**：
```bash
pytest tests/api/test_api.py -v -k "review"
pytest tests/ -x --tb=short
```

---

## Task 3 — A-01/A-02：Level0 evidence 展示 + reasons_zh 替换

**文件**：`skillhub_eval/adapters/ui/static/index.html`

**A-01**：在 `<script>` 块中添加 `renderLevel0Evidence(d)` helper（见 design.md 接口）。
在 `pollStatus` 的 `reasonHtml` 后插入 `${renderLevel0Evidence(d)}`；
在 `openRunDetail` 的 `reason_codes` 行后插入相同调用。

**A-02**：在 `<script>` 中添加 `REASON_ZH` 映射对象（见 design.md）。
将 `pollStatus` 中：
```javascript
reasonHtml = `<div class="text-xs text-gray-500">reason_codes: ${reasonCodes.join(', ')}</div>`;
```
改为：
```javascript
const zhReasons = reasonCodes.map(c => REASON_ZH[c] || c).filter(Boolean);
reasonHtml = zhReasons.length
  ? `<div class="text-xs text-amber-700 mt-1">${zhReasons.map(r => `• ${escapeHtml(r)}`).join('<br>')}</div>`
  : '';
```
同样处理 `openRunDetail` 中的 `reason_codes` 展示。

**验证**：
```bash
pytest tests/api/test_ui.py::test_ui_has_level0_evidence_helper -v
pytest tests/api/test_ui.py::test_ui_has_reason_zh_map -v
```

---

## Task 4 — B-01/B-02：专家台/历史模态接入运营解释层

**文件**：`skillhub_eval/adapters/ui/static/index.html`

**B-01**：在 `renderExpertCard` 函数体内，`r5Notice` 变量下方、return 模板字符串的操作按钮 `<div class="flex gap-3...">` 之前插入：
```javascript
${detail ? renderNarrativeCard(detail) : ''}
${detail ? renderDisagreementCard(detail) : ''}
${detail ? renderRiskLockCard(detail) : ''}
```

**B-02**：
1. 添加 `renderHumanReviewVerdict(d)` helper（见 design.md）。
2. 在 `openRunDetail` 的 body innerHTML 末尾，`renderSkillSummaryCard` 之前插入：
```javascript
${renderNarrativeCard(d)}
${renderDisagreementCard(d)}
${renderRiskLockCard(d)}
${renderHumanReviewVerdict(d)}
```

**验证**：
```bash
pytest tests/api/test_ui.py::test_ui_expert_card_has_narrative -v
pytest tests/api/test_ui.py::test_ui_has_human_review_verdict -v
```

---

## Task 5 — C-02/C-03/C-04：Per-case 反馈截断 + Gemini 横幅 + 中文标签

**文件**：`skillhub_eval/adapters/ui/static/index.html`

**C-02**：在 `renderModelVotesFeedback` 函数开头添加 `truncateFb(s)` helper（见 design.md）。
将 `dsFb`、`gmFb` 的赋值改为 `truncateFb(ds?.feedback)` / `truncateFb(gm?.feedback)`。

**C-03**：在 `renderProviderSummaryBars` 函数开头，DS 分数条渲染之前，插入 Gemini 不可用横幅逻辑（见 design.md）。

**C-04**：全文替换三维标签：
- `formatDimensionTriple` 函数：`IF`/`OC`/`BR` → `指令遵循`/`输出合规`/`业务解决`
- `renderSkillSummaryCard` dimRows：`instruction_following` label → `指令遵循`，等
- `renderModelVotesFeedback` 表头：`DeepSeek（三维 · 反馈）` 和 `Gemini（三维 · 反馈）` 表头中的列标题

**验证**：
```bash
pytest tests/api/test_ui.py::test_ui_per_case_uses_chinese_labels -v
pytest tests/api/test_ui.py::test_ui_has_gemini_unavailable_banner -v
```

---

## Task 6 — D-01：renderSkillSummaryCard 视觉重构

**文件**：`skillhub_eval/adapters/ui/static/index.html`

完整重写 `renderSkillSummaryCard` 函数体（保留函数名和签名）。
按 design.md 目标结构实现：
- `overall_verdict`：`bg-slate-100` 底色，`text-base font-semibold`
- `strengths`/`weaknesses`：`grid grid-cols-2 gap-2`，每项小卡片（绿底/红底）
- `dimension_notes`：行式进度条，中文标签，数值右对齐
- `recommendation`：`bg-blue-50 border-l-4 border-blue-400 px-3 py-2` callout

保留 `collapsed` 参数逻辑（`<details open>` 或不 open）。

**验证**：
```bash
pytest tests/api/test_ui.py::test_ui_has_skill_summary_card -v
# 手工验收：重启服务，刷新 grill-me 评估详情，确认新卡片样式
```

---

## Task 7 — 新增 test_ui.py 断言

**文件**：`tests/api/test_ui.py`

添加 design.md 「测试策略」章节定义的 6 个测试函数：
- `test_ui_has_level0_evidence_helper`
- `test_ui_has_reason_zh_map`
- `test_ui_expert_card_has_narrative`
- `test_ui_has_human_review_verdict`
- `test_ui_per_case_uses_chinese_labels`
- `test_ui_has_gemini_unavailable_banner`

**验证（门禁）**：
```bash
pytest tests/ -x --tb=short
# 期望：原 214 + 新增 6 = 220 tests passing
```

---

## 执行顺序与依赖

```
Task 1 (Prompt)     ──┐
Task 2 (Backend)    ──┼─→ Task 4 (B-01/B-02 可完整测试)
Task 3 (A-01/A-02)  ──┘
Task 5 (C-02~C-04)  ── 独立
Task 6 (D-01)       ── 独立
Task 7 (Tests)      ── 全部完成后

建议顺序：1 → 2 → 3 → 4 → 5 → 6 → 7
```

## 完成门禁

- [x] `pytest tests/ -x` 全绿（≥220 tests）
- [x] 服务重启后浏览器验收：专家台/详情模态有三张中文卡
- [x] Approve stock-radar：headline_zh = "评估通过，可进入上架流程" + DS/GM 参考分
- [x] Level0 fail（输入错误路径）：UI 显示中文诊断详情
- [x] Per-case 三维标签全中文，feedback ≤80 字截断
- [x] skill_summary 亮点/不足双列；阶段耗时已从报告 UI 隐藏
