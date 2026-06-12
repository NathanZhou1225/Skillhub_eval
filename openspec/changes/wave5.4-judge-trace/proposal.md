# Proposal: Wave 5.4 — 评分过程留痕 + 追踪页（judge-trace）

## Why

双模型分差出现时，报告只有 per-case 分数 + ≤30 字简语，回答不了「为什么 0 分」「两模型逻辑差异在哪个环节」「评审时模型看到了什么」。需要过程留痕来证明模型评估**可信、可解释**，但不增加主报告体积。

代码事实：每维 30 字 reason 已落 `model_votes.vote_json` 但报告层丢弃；评审 prompt 不留存；包级 `disagreement_brief_zh` 不解释逻辑差异；`openReportFromChat` 多余的 `switchTab('history')` 造成对话/历史 Tab 互跳割裂。

## What

1. **Prompt v0.5**：每维新增 `analysis`（100~200 字专业分析）+ `evidence_quotes`（原文引用）+ `deductions`（扣分点）；先分析后打分；现有 30 字简语不动。
2. **DB v7**：新表 `judge_traces`（prompt 全文 + 分歧解读 JSON）；vote_json 自动吸收新字段。
3. **分歧解读**：评估时对双模型分差 ≥15 的 case 自动调一次 DeepSeek 合成「分歧根因」；失败降级不阻塞终态。
4. **追踪页** `/ui/trace.html?run_id=X`：DS vs Gemini 并排对照（分数/分析/证据/扣分点）+ 分歧解读卡 + prompt 折叠；报告 per-case 表行内「查看评分过程」链接新标签打开。
5. **就地弹报告**：对话页「查看完整报告」直接弹详情模态，不再切历史 Tab；对话来源隐藏「打开完整对话」按钮。

## Relation to Sprint

阶段三「评估系统完善」（`SPRINT_phase3-eval-system.md` §阶段三后续）首个增强项，编号 **W5.4**；在 W5.5 Demo 验收前落地，追踪页纳入 Demo 叙事（评分信服力）。

## Non-goals / Out of scope

- 不改 1.2 阈值（85/70/90）与 R5 包级 10 分线（分歧解读触发线 15 为 per-case 高亮口径，非 R5）。
- 不改 `aggregate.py` 聚合 / 红线判定。
- 不做完整思维链（reasoner 模式）；不做追踪页按需生成按钮。
- 不回填历史 run 的 trace（页面提示替代）。
- 不动主报告/聊天简卡现有结构。

## Affected docs

- 不触碰规范正文（`docs/specs/` 阈值与协议不变）。
- `docs/guides/Skill评估系统全景说明.md` 收官时补「评分过程追踪」一节（T7）。
- Brainstorm + grill-me spec：`docs/superpowers/specs/2026-06-12-judge-trace-design.md`（D1–D7 + **GQ1–GQ7 已锁定**）。

## grill-me 收官摘要（2026-06-12）

| ID | 决策 |
|----|------|
| GQ1 | 单边失败：确定性卡，不调 LLM |
| GQ2 | 分歧合成并行 gather；`DIVERGENCE_SYNTHESIS_TIMEOUT_S` 默认 120s |
| GQ3 | v0.5 闸门：包级 ≤5 分、终态不翻转、红线 case 豁免 |
| GQ4 | `max_gap_dimension` 代码算；LLM 只写 `synthesis_zh` |
| GQ5 | 链接仅 `capability_full && has_judge_trace` |
| GQ6 | `parse_judge_response`：score 必填、依据可选 |
| GQ7 | `GET /eval/report/{id}` 增 `has_judge_trace` |

## 已知风险

| 风险 | 缓解 |
|------|------|
| 打分基线漂移（D6 已接受） | `prompt_version=review-agent-v0.5` 标记；testskills 三样本 v0.4/v0.5 对比作上线闸门 |
| 输出 token +40%、JSON 解析失败率升 | 单次预算仍在 `.env` 300s 内；解析沿用 fence 剥离，缺 analysis 不阻塞打分 |
| 分歧解读 LLM 失败 | `degraded` 标记，追踪页保底确定性并排对照 |
