# Design: UI/UX Improvement

## 模块映射

```
skillhub_eval/
├── adapters/
│   ├── ui/static/index.html        ← 主要改动（A/B/C/D 组）
│   └── api/routes/eval.py          ← B-03：submit_review approve 重建 narrative
├── persistence/sqlite.py           ← B-03：patch_report_after_human_review 加可选参数
└── core/
    └── engine.py                   ← C-01/D-02：两处 Prompt 增量修改
tests/
└── api/test_ui.py                  ← 新增 4 个 UI 断言
```

---

## 组 A — Level0 诊断可见性

### A-01：展示 evidence.detail

**现状**：`pollStatus` 只渲染 `reason_codes` 文字，`report.evidence` 数组未被消费。  
**目标**：Level0 fail 时在分数区域下方展示 evidence，精确告知失败原因。

**新 helper**（`index.html`）：
```javascript
function renderLevel0Evidence(d) {
  const ev = (getReportPayload(d).evidence || [])
    .filter(e => e.field && e.detail);
  if (!ev.length) return '';
  const items = ev.map(e =>
    `<li class="text-xs text-red-800">
       <code class="text-red-600">${escapeHtml(e.field)}</code> — ${escapeHtml(e.detail)}
     </li>`).join('');
  return `<div class="mt-2 p-3 bg-red-50 border border-red-200 rounded-lg">
    <div class="text-xs font-medium text-red-800 mb-1">Level0 诊断详情</div>
    <ul class="list-disc list-inside space-y-0.5">${items}</ul>
  </div>`;
}
```

**接入**：`pollStatus` body 中，`reason_codes` 文字后紧跟 `${renderLevel0Evidence(d)}`；同样加入 `openRunDetail`。

### A-02：reason_codes → reasons_zh

**现状**：`reasonHtml` 直接拼接英文码（`MODEL_DISAGREEMENT_R5,...`）。  
**目标**：优先展示 `report.narrative.reasons_zh`；无 narrative 时降级显示中文码（`REASON_CODE_ZH` 字典已在后端，前端维护同款精简版）。

前端增加映射对象：
```javascript
const REASON_ZH = {
  'MODEL_DISAGREEMENT_R5': '双模型评审存在明显分歧，综合分暂不展示',
  'REDLINE_MODEL_DISAGREEMENT': '红线用例上模型判断不一致，需人工复核',
  'WARN_COMPLETENESS_LOW': '元数据完整度未达 90',
  'WARN_SCORE_MIDRANGE': '综合分处于中等档（70–84）',
  'LEVEL0_SCHEMA_FAIL': 'Skill 包结构校验失败',
  'RISK_CASE_COUNT_INSUFFICIENT': '当前风险等级用例数量不足',
  'EVAL_WORKFLOW_TIMEOUT': '评估超时',
  'EVAL_PROVIDER_UNAVAILABLE': '双模型 API 均未返回有效分数',
};
```

---

## 组 B — 专家台/历史模态运营解释层

### B-01：renderExpertCard 补三张卡

`renderExpertCard` 在 `modelBlock` 之后、操作按钮之前，插入：
```javascript
${detail ? renderNarrativeCard(detail) : ''}
${detail ? renderDisagreementCard(detail) : ''}
${detail ? renderRiskLockCard(detail) : ''}
```

### B-02：openRunDetail 补三张卡 + 裁定摘要

`openRunDetail` body 末尾 `renderSkillSummaryCard` 之前插入：
```javascript
${renderNarrativeCard(d)}
${renderDisagreementCard(d)}
${renderRiskLockCard(d)}
${renderHumanReviewVerdict(d)}   // 新 helper，见下
```

**新 helper `renderHumanReviewVerdict`**：
```javascript
function renderHumanReviewVerdict(d) {
  const hr = (getReportPayload(d).human_review) || {};
  if (!hr.reviewer_action) return '';
  const label = hr.reviewer_action === 'approve' ? '批准通过' : '驳回';
  return `<div class="mt-2 p-2 bg-indigo-50 border border-indigo-200 rounded-lg text-xs text-indigo-800">
    <span class="font-medium">专家裁定：${label}</span>
    ${hr.operator ? ` · ${escapeHtml(hr.operator)}` : ''}
    ${hr.comment ? ` <span class="text-indigo-600">${escapeHtml(hr.comment)}</span>` : ''}
  </div>`;
}
```

### B-03：Approve 后 narrative 重建

**`routes/eval.py` `submit_review`**：approve 时从已存 report 读取 `provider_summary`，
构造 override narrative：

```python
if body.action == "approve":
    from skillhub_eval.core.report_narrative import build_report_narrative
    nar_override = build_report_narrative({
        "review_status": new_status,
        "reason_codes": [],            # 清空分歧码，已裁定
        "required_actions": [],
        "score_total": report.get("score_total"),  # 仍可能 null
    })
    # 追加 DS/GM 参考分到 score_display_zh
    ps = report.get("provider_summary") or {}
    if ps.get("deepseek_score") is not None:
        nar_override = nar_override.model_copy(update={
            "score_display_zh": (
                f"DS 参考分 {ps['deepseek_score']} / GM 参考分 {ps.get('gemini_score', '—')}"
            )
        })
else:
    nar_override = None
```

**`persistence/sqlite.py` `patch_report_after_human_review`**：加可选参数 `narrative_override=None`，
若非 None 则 `report["narrative"] = narrative_override.model_dump()`。

**接口变更**：`patch_report_after_human_review` 签名新增 `narrative_override: object | None = None`，
已有调用（仅 `routes/eval.py` 一处）传新参数，其余不影响。

---

## 组 C — Per-case 反馈简洁中文

### C-01：`_build_prompt` 增加语言指令

在 `_build_prompt` 返回字符串的评分规则段末尾追加一行：

```python
"\n请用简洁中文填写所有 reason、dimension_notes 字段，每项不超过 30 字，禁止技术术语。\n"
```

位置：`"【三维子项】..."` 行之后，`"【输出格式】..."` 行之前。

**测试兼容**：`test_prompt_no_hardcoded_scores` 验证 `<integer 0-100>` 和 `禁止照抄`，本修改不移除这两处，断言不受影响。

### C-02：per-case feedback 截断折叠

`renderModelVotesFeedback` 中：
```javascript
const MAX_FB = 80;
function truncateFb(s) {
  if (!s || s === '—') return '—';
  return s.length <= MAX_FB ? escapeHtml(s)
    : `${escapeHtml(s.slice(0, MAX_FB))}<span class="text-gray-400">…</span>
       <details class="inline"><summary class="text-xs text-blue-500 cursor-pointer">展开</summary>
       <div class="text-gray-600 mt-0.5">${escapeHtml(s)}</div></details>`;
}
```
替换 `dsFb`/`gmFb` 的 `escapeHtml(...)` 调用为 `truncateFb(...)`。

### C-03：Gemini 全部不可用横幅

`renderProviderSummaryBars` 中，若 `ps.gemini_score == null` 且 R5 未触发，
在双模格子上方插入：
```html
<div class="text-xs text-amber-700 bg-amber-50 border border-amber-200 rounded px-2 py-1 mb-1">
  ⚠ Gemini 本次不可用（API 限流），仅 DeepSeek 有效评审，结论仅供参考
</div>
```
条件：`ps.gemini_score == null && !ps.r5_triggered && ps.deepseek_score != null`

### C-04：三维标签全面中文化

全局替换（`index.html`）：

| 旧 | 新 |
|----|----|
| `IF` | `指令遵循` |
| `OC` | `输出合规` |
| `BR` | `业务解决` |
| `instruction_following` label | `指令遵循` |
| `output_compliance` label | `输出合规` |
| `business_resolution` label | `业务解决` |

涉及函数：`formatDimensionTriple`、`renderSkillSummaryCard` `dimRows`、`renderModelVotesFeedback` 表头。

---

## 组 D — Skill Summary 视觉重构

### D-01：renderSkillSummaryCard 布局

**目标结构**：
```
┌─────────────────────────────────────────────────────┐
│ 📋 技能质量诊断摘要  [▼]                             │  ← details summary
├─────────────────────────────────────────────────────┤
│  ██ 总体结论（overall_verdict）                      │  ← 大字 + 醒目背景
├──────────────────┬──────────────────────────────────┤
│  ✓ 亮点（2列）   │  ✗ 不足（2列）                   │  ← 双列小卡
├─────────────────────────────────────────────────────┤
│  指令遵循 ████████░░ 85    输出合规 ████████░░ 90    │  ← 三维进度条
│  业务解决 ████████░░ 80                               │
├─────────────────────────────────────────────────────┤
│  💡 建议：...                                        │  ← 蓝色 callout
└─────────────────────────────────────────────────────┘
```

- `overall_verdict`：`text-base font-semibold` + `bg-slate-100 rounded-lg px-3 py-2`
- strengths/weaknesses：`grid grid-cols-2 gap-2`，每项 `text-xs rounded-md px-2 py-1`（绿/红底）
- dimension_notes：`<div class="flex items-center gap-2">` + inline bar `<div style="width:${score}%">`，保留中文标签
- recommendation：`bg-blue-50 border-l-4 border-blue-400 px-3 py-2 text-xs text-blue-800`

### D-02：skill_summary Prompt 字数约束

`engine.py` Phase 5.5 prompt 占位符改为带字数约束：
```python
'  "overall_verdict": "<1句话总结，不超过20字>",\n'
'  "strengths": ["<优势，不超过15字>", "<优势，不超过15字>"],\n'
'  "weaknesses": ["<不足，不超过15字>", "<不足，不超过15字>"],\n'
```

---

## 测试策略

### 新增断言（`tests/api/test_ui.py`）

```python
def test_ui_has_level0_evidence_helper():
    """A-01: Level0 evidence renderer must exist."""
    r = client.get("/ui/index.html")
    assert "renderLevel0Evidence" in r.text
    assert "Level0 诊断详情" in r.text

def test_ui_has_reason_zh_map():
    """A-02: Chinese reason code map must exist."""
    r = client.get("/ui/index.html")
    assert "REASON_ZH" in r.text
    assert "双模型评审存在明显分歧" in r.text

def test_ui_expert_card_has_narrative():
    """B-01: Expert card must call narrative + disagreement + risk_lock helpers."""
    r = client.get("/ui/index.html")
    # renderExpertCard function must invoke these helpers
    expert_fn = r.text[r.text.find("function renderExpertCard"):
                       r.text.find("function renderExpertVerdictCard")]
    assert "renderNarrativeCard" in expert_fn
    assert "renderDisagreementCard" in expert_fn
    assert "renderRiskLockCard" in expert_fn

def test_ui_has_human_review_verdict():
    """B-02: Human review verdict helper must exist."""
    r = client.get("/ui/index.html")
    assert "renderHumanReviewVerdict" in r.text
    assert "专家裁定" in r.text

def test_ui_per_case_uses_chinese_labels():
    """C-04: IF/OC/BR must be Chinese."""
    r = client.get("/ui/index.html")
    assert "指令遵循" in r.text
    assert "输出合规" in r.text
    assert "业务解决" in r.text

def test_ui_has_gemini_unavailable_banner():
    """C-03: Gemini unavailable notice must exist."""
    r = client.get("/ui/index.html")
    assert "Gemini 本次不可用" in r.text
```

### 已有测试兼容性验证

| 测试 | 预期结果 |
|------|---------|
| `test_prompt_no_hardcoded_scores` | ✅ 通过（C-01 只追加，不删 `<integer 0-100>`/`禁止照抄`） |
| `test_skill_summary_field_populated_on_pass` | ✅ 通过（mock 数据结构不变） |
| `test_ui_has_skill_summary_card` | ✅ 通过（函数名 `renderSkillSummaryCard` 保留） |
| `test_ui_has_diagnostic_and_feedback_helpers` | ✅ 通过（`renderModelVotesFeedback` 名称保留） |

---

## 实现顺序（依赖关系）

```
C-01 prompt → 独立，不依赖 UI
D-02 prompt → 独立，不依赖 UI

B-03 backend → routes/eval.py + sqlite.py（先于 B-03 UI）

A-01/A-02 → 独立 UI helper，不互相依赖
B-01/B-02 → 依赖 B-03 backend 完成
C-02/C-03/C-04 → 独立 UI，不互相依赖
D-01 → 独立 UI 重构

test_ui.py 新断言 → 最后（所有 UI 改完后）
```
