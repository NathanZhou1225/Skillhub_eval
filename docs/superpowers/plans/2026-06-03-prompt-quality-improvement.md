# Phase 2 · Prompt 质量改进计划（T8 Live 反馈后）

> **触发**：T8 live 验收（2026-06-03）发现四类问题，需系统性修复后重跑三样本矩阵  
> **状态**：✅ Fix-1–4 + **T12 live 收官**（2026-06-03）；**201 tests**；Q-10/Q-11/Fix-4 终审 PASS  
> **执行顺序**：Fix-1 → Fix-2（同步）→ Fix-3 → Fix-4（UI）→ T8 重跑验收

---

## 审计结论：Prompt 示例污染全景

| 文件 | 位置 | 问题 | 严重度 |
|------|------|------|--------|
| `skillhub_eval/core/engine.py` L559 | `_build_prompt()` | 格式示例硬编码 `"score":85`，DeepSeek 所有 case 均返回 85 | **P0 critical** |
| `skillhub_eval/core/engine.py` L558–560 | `_build_prompt()` | 仅要求 `step_completeness` 单维，缺 3 个 rubric 维度 | **P1 high** |
| `skillhub_eval/core/engine.py` L257 | `_judge_case` | `DimensionScores()` 传空对象，三维字段全 null | **P1 high** |
| `skillhub_eval/core/engine.py` L563–571 | `_extract_score` | 平均所有 sub_scores，fallback 70；三维修复后须改为 40/30/30 加权 | **P1 high** |
| `scripts/check_providers.py` L14 | 连通性检测 prompt | 示例含 `"score":80`（仅健康检查，非评估链路） | **P3 low** |
| `skillhub_eval/adapters/ui/static/index.html` | 详情模态 / 历史 | `awaiting_confirm` / `degraded` 无诊断卡；完成评审后无 feedback 展示 | **P2 medium** |

> **不是问题的位置**：`tests/` 目录中的硬编码分数全部是测试 fixture，不发送给 LLM，不需要修改。

---

## 任务清单

### Fix-1（P0）：消除 DeepSeek 打分锁死——重写 `_build_prompt`

**文件**：`skillhub_eval/core/engine.py`

**改动要点**：
1. 格式示例中的具体数值全部替换为 `<integer 0-100>` 占位符
2. 增加明确禁止复制示例的指令："请根据实际评估生成真实分数，勿照抄本格式"
3. 添加评分标准说明（<60 差 / 60-79 中 / 80-89 良 / 90-100 优），帮助模型锚定分数区间语义
4. 新增 `system` 角色指令与 `user` 内容分离（DeepSeek 支持 `messages` 数组，`temperature=0` 时效果更稳定）
5. 补充 SKILL.md 实际内容到 prompt（目前只传 `user_intent`，模型无法读取技能描述）

```python
# 修复后的格式片段（示意）
"""
【评分规则】请根据以下 case 真实评估，给出 0-100 整数（勿照抄示例数值）：
- 90-100：完全满足，证据充分
- 80-89：基本满足，有小缺口
- 60-79：部分满足，有明显缺陷
- 0-59：严重不足

【输出格式】仅输出合法 JSON，字段说明如下（<...> 为你需要填写的值）：
{
  "sub_scores": {
    "instruction_following": {"score": <integer 0-100>, "pass": <bool>, "reason": "<str>", "evidence_refs": []},
    "output_compliance":     {"score": <integer 0-100>, "pass": <bool>, "reason": "<str>", "evidence_refs": []},
    "business_resolution":   {"score": <integer 0-100>, "pass": <bool>, "reason": "<str>", "evidence_refs": []}
  },
  "confidence": "<low|medium|high>",
  "dimension_notes": "<str>"
}
"""
```

**测试影响**：
- `tests/core/test_engine.py` 中的 mock provider（`HighScoreProvider` / `DisagreeProvider`）返回的是 mock 数据，与 prompt 格式无关，**无需修改**
- `tests/core/test_providers.py` 中的 `FAKE_RESPONSE` 只测 HTTP 层，**无需修改**
- 需新增测试 `test_prompt_no_hardcoded_scores()`：断言 `_build_prompt()` 返回字符串中不含 `"score":8` / `"score":9` 等两位具体数值示例

---

### Fix-2（P1）：三维打分正确映射——`_extract_score` + `_judge_case`

**文件**：`skillhub_eval/core/engine.py`

**改动要点**：

1. **`_extract_score` 改为 40/30/30 加权**（对应 1.2 协议 §3 权重）：
```python
def _extract_score(self, raw: dict) -> float:
    sub = raw.get("sub_scores", {})
    weights = {
        "instruction_following": 0.40,
        "output_compliance":     0.30,
        "business_resolution":   0.30,
    }
    weighted = sum(
        sub[k]["score"] * w
        for k, w in weights.items()
        if k in sub and isinstance(sub[k], dict)
    )
    # fallback: 平均所有维度（兼容单维度 mock provider）
    if weighted == 0.0:
        scores = [v.get("score", 70) for v in sub.values() if isinstance(v, dict)]
        return round(sum(scores) / len(scores), 1) if scores else 70.0
    return round(weighted, 1)
```

2. **`_judge_case` 中 `DimensionScores` 正确从 `sub_scores` 映射**：
```python
ss = raw.get("sub_scores", {})
dim = DimensionScores(
    instruction_following=ss.get("instruction_following", {}).get("score"),
    output_compliance=ss.get("output_compliance", {}).get("score"),
    business_resolution=ss.get("business_resolution", {}).get("score"),
)
```

**测试影响**：
- `tests/core/test_engine.py`：mock provider 返回 `step_completeness` 单维——`_extract_score` 加权逻辑的 fallback 分支会接住，分数不变，**不会破坏现有测试**
- 新增 `test_extract_score_weighted_three_dimensions()`：验证 3 维 40/30/30 结果

---

### Fix-3（P3 low）：修复 `check_providers.py` 中的示例污染

**文件**：`scripts/check_providers.py`

**改动**：把 PROMPT 中的 `"score":80` 改为 `"score":85` → `"score": <integer>`，或直接改成只要求模型返回任意合法 JSON。这个文件不影响评估结果，改动量极小（1 行）。

---

### Fix-4（P2）：Skill 诊断报告卡 UI

**文件**：`skillhub_eval/adapters/ui/static/index.html`

**三个位置的改动**：

#### 4a：`awaiting_confirm` / `degraded` 诊断卡（作者台运行状态区）

当 `status=awaiting_confirm` 时，轮询结束后在运行状态卡中追加「结构诊断报告」：
- 展示 `report.completeness_score`（条形进度条）
- 展示 `report.gaps[]` 分区（阻断/警告/提示）
- 展示 `report.required_actions[]` 有序清单
- 文案：「本次仅完成结构检查，尚未进入模型质量评审。请按补全清单操作后重新提交全量评估。」

当 `status` 为已完成 `degraded` 评审时（`review_status=warn`，`model_votes` 存在）：
- 追加双模型包级分数（`provider_summary`）
- 说明文案：「降级摸底评估已完成，结论仅供参考，不作为上架准入依据。」

#### 4b：完成评审后的 per-case feedback（详情模态 + 专家台）

在 `openRunDetail(runId)` 和 `renderExpertCard` 中，从 `report.model_votes[]` 提取每个 case 的 `feedback` 字段，渲染 per-case feedback 列表：
```
case_id | DS feedback (自然语言) | Gemini feedback | DS维度分 | Gemini维度分
```

#### 4c：三维得分展示（专家台 per-case 表）

扩展现有 per-case `<details>` 表，在 Δ 列右侧增加「DS 维度 / Gemini 维度」折叠列，展示 `instruction_following / output_compliance / business_resolution` 三个分数（需要 Fix-2 先把数据打通）。

**测试影响**：`tests/api/test_ui.py` 新增 `test_ui_has_completeness_score_display()` 和 `test_ui_has_per_case_feedback()` 断言字符串存在。

---

## 执行顺序与依赖关系

```
Fix-1 (prompt 重写)
    ↓
Fix-2 (三维映射)  ←── 依赖 Fix-1 的新格式
    ↓
Fix-3 (check_providers)  ←── 独立，可并行
    ↓
pytest 全量（验证不破坏现有 195 条测试）
    ↓
Fix-4 (UI)  ←── 独立，可并行于 Fix-1/2
    ↓
T8 重跑 (scripts/t8_live_validation.py)
验收：DeepSeek 分数有差异化、三维字段非 null、诊断卡可见
```

---

## 验收标准（Fix 完成后）

| 验收项 | 方法 | 通过条件 |
|--------|------|----------|
| DeepSeek 不再固定 85 | T8 重跑后 `provider_summary.deepseek_score` 在不同 case 有差异 | ≥2 个不同分值 |
| 三维字段非 null | DB 中 `model_votes.dimension_scores` 三字段有值 | 全部 ≠ null |
| 加权分正确 | 单元测试 `test_extract_score_weighted_three_dimensions` | green |
| 诊断卡可见 | 浏览器跑 grill-me minimal → 运行状态卡展示 completeness_score + gaps | 肉眼确认 |
| feedback 可见 | stock-radar 完成后详情模态展示 per-case feedback 文本 | 肉眼确认 |
| 测试不退化 | `pytest -q` | ≥195 passed |

---

## 估计改动量

| Fix | 文件 | 新增/修改行数 | 新增测试 |
|-----|------|-------------|---------|
| Fix-1 | `engine.py` | ~30 行 prompt 重写 | 1 个 |
| Fix-2 | `engine.py` | ~25 行 | 1 个 |
| Fix-3 | `check_providers.py` | ~5 行 | 0 |
| Fix-4a | `index.html` | ~50 行 JS | 1 个 UI |
| Fix-4b/c | `index.html` | ~40 行 JS | 1 个 UI |
| **合计** | **2 文件** | **~150 行** | **4 个** |

---

## 决策记录

| 决策 | 理由 | 排除方案 |
|------|------|---------|
| prompt 格式改用 `<integer 0-100>` 占位符，禁止照抄 | DeepSeek 对指令敏感但对示例值过于字面遵循；占位符语义清晰 | 完全删除示例（模型缺少结构引导，可能输出非法 JSON）|
| 三维权重 40/30/30 硬编码在 `_extract_score` | 与 1.2 协议 §3 保持一致；单一真源 | 由 prompt 动态传权重（增加变量，测试困难） |
| DimensionScores fallback 保留平均逻辑 | 向后兼容 mock provider 返回单维；测试不需要修改 | 强制要求三维否则报错（破坏现有 195 条测试） |
| check_providers.py 同步修复 | 防止未来接入新模型时连通测试的「示例 80」影响新模型校准 | 不改（只是健康检查）|

---

## 变更流水

| 日期 | 内容 |
|------|------|
| 2026-06-03 | T8 live 反馈：DeepSeek 恒定 85 / 三维 null / 无诊断卡；prompt 质量改进计划立项 |
