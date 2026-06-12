# 设计：评分过程留痕 + 追踪页（W5.4 judge-trace）

> 日期：2026-06-12  
> 状态：脑暴 + grill-me **已收官**（GQ1–GQ7，2026-06-12）；OpenSpec `wave5.4-judge-trace` 已 propose  
> 归属：阶段三 · 评估系统完善（`SPRINT_phase3-eval-system.md`）  
> 受众：实现者 + grill-me 评审

---

## 1. 背景与问题

双模型（DeepSeek + Gemini）打分存在分差时，用户在报告里只能看到 per-case 分数和一句 ≤30 字总结（`dimension_notes`），无法回答：

- **为什么打 0 分**（尤其红线题判死的依据）；
- **两个模型的打分逻辑差异在哪个环节**（哪个维度、各自依据什么）；
- **模型评审时看到了什么材料**（prompt 未留存，无法复盘）。

目标是用「过程留痕」证明模型评估**可信、可解释**，但不增加主报告的体积——通过链接跳转查看。

### 现状盘点（代码事实）

| 事实 | 位置 |
|------|------|
| Prompt v0.4 已要求每维 `reason`（≤30字）+ `dimension_notes`（≤30字） | `engine._build_prompt` |
| 每维 reason 完整落库于 `model_votes.vote_json`，但报告组装时 `DimensionScores` 只保留 3 个浮点数，reason 在报告/UI 层丢弃 | `engine._judge_case` / `schemas/report.py` |
| 发给模型的 prompt 不留存 | — |
| 包级 `disagreement_brief_zh` 只说哪些 case 分差大，不解释逻辑差异 | `core/aggregate.py` 相关 |
| `#detail-modal` 是全局浮层，不属于历史 Tab；`openReportFromChat` 多写了 `switchTab('history')` 造成 Tab 互跳割裂 | `index.html` |

---

## 2. 目标与非目标

### 目标

1. 每 case × 每模型留下**结构化评分依据**：专业分析 + SKILL.md 原文证据引用 + 扣分点。
2. 留存评审 prompt 全文，复盘「模型看到了什么」。
3. 分差 ≥15 的 case 自动生成 **LLM 分歧根因解读**（评估时生成，非事后）。
4. 独立**追踪页** `/ui/trace.html?run_id=X` 承载全部留痕，主报告只加链接。
5. 对话页点「查看完整报告」**就地弹模态**，消除 Tab 互跳。

### 非目标

- 不改 1.2 阈值（85/70/90）与 R5 10 分线。
- 不改 `aggregate.py` 聚合 / R5 / 红线判定逻辑。
- 不改主报告与聊天简卡的现有结构（30 字简语、`dimension_notes` 保留原样）。
- 不做完整思维链（reasoner 模式）——成本与双侧不对称问题，明确排除。
- 不做追踪页的按需生成按钮（解读评估时已生成）。

---

## 3. 决策记录（脑暴 Q&A 已锁定）

| # | 决策 | 理由 | 排除项 |
|---|------|------|--------|
| D1 | **留痕深度 = B**：prompt 升级，模型输出结构化评分依据（每维 100~200 字分析 + 原文证据 + 扣分点）+ 留存完整 prompt | 信服力高、成本可控（输出 token 约 +40%） | A 仅提级现有 30 字 reason（答不了「为什么 0 分」）；C 完整 CoT（时延/成本高、Gemini 不对称） |
| D2 | **分歧说明 = 确定性并排对照 + LLM 合成解读** | 并排对照零成本、不可能编造；LLM 解读省读者脑力 | 纯 LLM（事后推测无依据）；纯并排（要读者自己推断根因） |
| D3 | **解读时机 = 评估时自动，仅分差 ≥15 的 case** | 打开即看；成本只落在真分歧 case；与现有 per-case 分差 Δ≥15 浅红高亮口径一致（注意：R5 是**包级** 10 分线，与本触发线无关） | 全量生成（高风险 9 case 多 9 次调用）；按需生成（Demo 多等一步 + 多一套状态） |
| D4 | **载体 = 独立页面** `/ui/trace.html?run_id=X`，per-case 表行内链接新标签页打开，锚点 `#case-{id}` 定位 | 可直接发链接给他人；不加重主页面 | 模态叠模态（体验差、无法分享）；简卡双入口（W5.1 刚治理过信息密度） |
| D5 | **语言风格 = 专家/运营向**：中文为主、允许术语、引用原文 | 证据可追溯优先；业务方看主报告 30 字简语即可 | 全文白话（牺牲证据精度）；双层输出（token 翻倍且可能自相矛盾） |
| D6 | **接受打分基线漂移**：`prompt_version` 升 `review-agent-v0.5`，要求先写分析再打分；上线前 testskills 三样本前后对比 | 同调用产生的推理才有信服力；先分析后打分通常更准 | 「先按原标准打分再补依据」（漂移仍不为零且依据质量弱） |
| D7 | **对话页就地弹报告模态**：`openReportFromChat` 删 `switchTab('history')`；`openRunDetail` 加来源参数，对话来源时隐藏「打开完整对话」按钮 | 模态本就是全局浮层，改动一行级；历史 Tab 原路径不变 | 报告内容嵌入聊天气泡（W5.1 已否决的方向） |

### grill-me 追加决策（GQ1–GQ7，2026-06-12）

| # | 决策 | 要点 |
|---|------|------|
| **GQ1** | 单边模型失败 | **双层**：gap≥15 且双侧有效 → LLM 分歧解读；**仅单侧有效** → 不调 LLM，追踪页出确定性卡（哪侧有分 / 哪侧 `provider_error` 原文） |
| **GQ2** | 分歧合成执行 | **并行** `asyncio.gather`；单次超时 **`DIVERGENCE_SYNTHESIS_TIMEOUT_S` 默认 120s**（`.env` 可调，不沿用 judge 300s）；计入 workflow 900s；失败 degraded |
| **GQ3** | v0.5 上线闸门 | 包级 `score_total` 变化 ≤5 分；**终态不得单独因 v0.5 翻转**；**红线 case 0 分波动豁免**；对比表入 runbook |
| **GQ4** | `max_gap_dimension` | **纯代码**算三维 `|ds−gm|` 最大维；LLM **只**写 `synthesis_zh`（可把最大维作为 prompt 提示，不采信 LLM 维度字段） |
| **GQ5** | 追踪链接可见性 | `capability_full` **且** `has_judge_trace` 才显示 per-case「查看评分过程」；旧 run 无链接 |
| **GQ6** | JSON 解析 | **`parse_judge_response`**：统一 fence 剥离；`score` 必填；`analysis` 等可选；有分即聚合，追踪页缺字段显示「依据未返回」 |
| **GQ7** | `has_judge_trace` | `GET /eval/report/{run_id}` 增 **`has_judge_trace: bool`**（`judge_traces` 表是否存在该 run 任一行）；UI 用其与 `capability_full` 控制链接 |

---

## 4. 详细设计

### 4.1 Prompt v0.5（`engine._build_prompt`）

在现有每维 `score / pass / reason(≤30字) / evidence_refs` 之外，`sub_scores.{dim}` 新增：

```json
{
  "analysis": "<中文 100~200 字，专业分析为什么是这个分，允许术语>",
  "evidence_quotes": ["<引用 SKILL.md 或 case 原文的关键句>", "..."],
  "deductions": ["<扣分点，一句话一条>", "..."]
}
```

要求：

- 指令顺序调整为**先写 analysis 再给 score**（语义上引导先推理后打分）。
- 现有 `reason`（≤30字白话）、`dimension_notes`、`confidence` 全部保留，主报告呈现不变。
- `prompt_version` 全链路升 `review-agent-v0.5`（`_judge_case` 写入 vote、报告字段同步）。
- 红线题口径提示（refusal/adversarial 评分口径）保持不变。

### 4.2 数据层（DB v7）

- `model_votes.vote_json`：整 dict 序列化，新字段自动落库，**无需改表**。
- 新表 `judge_traces`（`PRAGMA user_version` → 7，沿用单事务 + 微观列检迁移模式）：

```sql
CREATE TABLE IF NOT EXISTS judge_traces (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    divergence_json TEXT,          -- null = 无分歧解读；含 degraded 标记
    created_at TEXT NOT NULL
);
```

- `divergence_json` 结构：

```json
{
  "gap": 37.5,
  "max_gap_dimension": "output_compliance",
  "synthesis_zh": "<LLM 生成的分歧根因解读，≤300字>",
  "degraded": false
}
```

- `max_gap_dimension` 由 **`core/divergence.py` 确定性计算**（GQ4），非 LLM 输出。
- Port 层新增：`save_judge_trace` / `get_judge_traces` / `has_judge_traces(run_id) -> bool`。
- `judge_traces` 建议 **`UNIQUE(run_id, case_id)`** 防重入重复行。

### 4.3 引擎流程（`model_judging` 之后）

1. `_judge_case` 内：每 case 评审完成后落 `judge_traces`（prompt 留存；divergence 先置 null）。
2. 全部 case 评审结束后新增子步骤 `divergence_synthesis`（**并行** gather，GQ2）：
   - 对双模型均有效投票且 `|ds - gm| >= 15` 的 case；
   - 先代码算 `max_gap_dimension`（GQ4），再拼装两侧 rationale + 该维名 → `ds_provider.generate()`；
   - LLM 只产出 `synthesis_zh`（≤300 字）；
   - 写回该 case 的 `divergence_json`。
   - 单次调用超时：`DIVERGENCE_SYNTHESIS_TIMEOUT_S`（默认 **120s**，settings + `.env`）。
3. **仅单侧有效**（GQ1）：跳过 LLM；`divergence_json` 可含 `single_sided: true` + `provider_errors` 摘要；追踪页顶部确定性卡。
4. **降级**：generate 失败/超时 → `degraded: true`，不重试不阻塞终态；追踪页仍有并排对照。
4. 计时：`stage_timing` 增加 `divergence_synthesis` 埋点。
5. 范围：仅 `capability_full` 正式评估产生 trace（model_judging 本就只在正式评估跑）。

### 4.4 API

**扩展** `GET /eval/report/{run_id}`：响应增加 `has_judge_trace: bool`（GQ7）。

新端点 `GET /eval/report/{run_id}/trace`，返回：

```json
{
  "run_id": "...",
  "skill_id": "...",
  "review_status": "warn",
  "provider_summary": { "deepseek_score": 81.2, "gemini_score": 88.0, "...": "..." },
  "prompt_version": "review-agent-v0.5",
  "cases": [
    {
      "case_id": "case-001",
      "case_type": "adversarial_case",
      "gap": 37.5,
      "prompt_text": "...",
      "votes": {
        "deepseek": { "score_total": 0, "sub_scores": { "...": "..." } },
        "gemini":   { "score_total": 75, "sub_scores": { "...": "..." } }
      },
      "divergence": { "synthesis_zh": "...", "max_gap_dimension": "...", "degraded": false }
    }
  ]
}
```

- 数据源：`model_votes.vote_json`（完整 sub_scores 含 analysis）+ `judge_traces`。
- 旧 run（vote 无 analysis 字段 / 无 judge_traces 行）：正常返回已有数据，`cases[].votes` 里缺失字段为 null，由前端兜底提示。

### 4.5 追踪页 `/ui/trace.html`

独立静态页（Tailwind CDN，风格与 index.html 一致），`?run_id=X` 取参：

- **头部**：skill_id / run_id / 结论徽标 / 包级双模型分与分差。
- **每 case 一节**（锚点 `id="case-{case_id}"`）：
  - case 元信息（类型中文标签、双模型总分、分差徽标——≥15 红色高亮）；
  - 分差 ≥15 时顶部出「分歧根因解读」卡（`synthesis_zh`；degraded 时显示「自动解读生成失败，请看下方对照」）；
  - **DS vs Gemini 并排对照表**：每维一行——两侧分数、analysis、evidence_quotes、deductions；分差最大的维度行自动高亮；
  - prompt 全文收进 `<details>` 折叠。
- 旧 run 无过程数据：显示「该评估早于过程留痕功能，无评分过程数据」。

### 4.6 主 UI 接入（index.html）

1. **追踪入口**：`capability_full && has_judge_trace` 时，per-case 表每行加「查看评分过程 →」，`target="_blank"` 打开 `/ui/trace.html?run_id=X#case-{id}`（GQ5/GQ7）。旧 run 不展示链接。
2. **就地弹报告（D7）**：
   - `openReportFromChat(runId)` 删除 `switchTab('history')`；
   - `openRunDetail(runId, { origin })`：`origin === 'chat'` 时隐藏模态内「打开完整对话 →」按钮（冗余）；
   - 历史 Tab 调用路径不变。

---

## 5. 测试计划（TDD）

| 层 | 用例 |
|----|------|
| schema | vote dict 含 analysis/evidence_quotes/deductions 时 `vote_json` 完整落库与读回 |
| migration | v6→v7 幂等；`judge_traces` 列检；旧 DB 重跑迁移无 duplicate |
| engine | prompt v0.5 包含新字段指令与「先分析后打分」；`_judge_case` 落 prompt_text；分差 ≥15 触发 synthesis、<15 不触发；generate 失败 → degraded 标记且 run 正常终态 |
| API | trace 端点契约（正常 run / 旧 run 缺字段 / run 不存在 404）|
| UI | trace.html smoke（锚点、并排表、degraded 提示、旧 run 提示）；`openReportFromChat` 不再切 Tab；origin=chat 隐藏跳对话按钮 |
| parse | `parse_judge_response`：fence 剥离；缺 analysis 仍有 score；整包 JSON 失败 → provider_error（GQ6） |
| live 验收 | stock-radar 追踪页讲清分歧；testskills v0.4/v0.5 对比满足 **GQ3**（包级 ≤5 分、终态不翻转、红线豁免） |

---

## 6. 成本与风险

| 项 | 评估 |
|----|------|
| 输出 token | 每次评审调用约 +40%（3 维 × 100~200 字 + 引用）；时延小幅上升，仍在 `.env` 300s 单次预算内 |
| 分歧解读调用 | 仅分差 ≥15 的 case；**并行**、单次默认 120s 超时（GQ2） |
| 打分漂移 | 接受（D6）；**GQ3** 量化闸门：包级 ≤5 分、终态不翻转、红线 case 豁免 |
| JSON 解析风险 | **GQ6** `parse_judge_response`：score 必填、依据字段可选 |
| 旧数据 | 无 trace 的历史 run 不回填，页面提示替代 |

---

## 7. 实施切分（供 OpenSpec tasks 参考）

1. **T1** prompt v0.5 + `_judge_case` 字段透传（含 prompt_version 全链路）
2. **T2** DB v7 `judge_traces` + Port 方法
3. **T3** 引擎 `divergence_synthesis` 子步骤 + 降级 + stage_timing
4. **T4** `GET /eval/report/{run_id}/trace` API
5. **T5** `/ui/trace.html` 新页面 `[ui-only 除路由注册]`
6. **T6** index.html：per-case 追踪链接 + 就地弹模态（D7）`[ui-only]`
7. **T7** live 验收（stock-radar + testskills v0.4/v0.5 对比）+ RECORD/Sprint/全景说明同步

---

## 8. 后续流程

grill-me 已收官 → **subagent TDD 实现**（`openspec/changes/wave5.4-judge-trace/tasks.md`）→ 验收后 `/opsx:archive`。
