# testskills Phase 1 — Live 验收 Runbook

> **执行时间**：2026-06-03（T12 自动化已盖印；**T14 UI 手工复测**待本轮勾选）  
> **数据库**：`data/t8_validation.db`（或 UI 跑出的 `data/skillhub_eval.db`）  
> **自动化脚本**：`scripts/t8_live_validation.py` · `scripts/t12_audit.py`  
> **前置**：`.env` DeepSeek + Gemini live key；单元测试 **206 passed**；服务 `skillhub-eval serve`

## 验收矩阵（实测记录）

| Skill 实例 / 路径 | 评估状态（Expected Mode） | 实测终态（Status / Review） | 主错误码（Reason Codes） | 总耗时 / 评审耗时 | 双模打分（DS / Gemini） |
|---|---|---|---|---|---|
| A1 grill-me 草案入库 | minimal + capability_full | `awaiting_confirm` / `None` | — | 0.1s | — |
| A2 grill-me 未落盘硬防线 | confirmed + capability_full | `completed` / `pass` | — | 19.4s / 评审 19.3s | DS 91.5 / Gemini 94.5 |
| A3 grill-me 物理闭环 | confirmed + capability_full | `completed` / `pass` | — | 17.1s / 评审 17.0s | DS 92.2 / Gemini 94.5 |
| B tiered-memory 降级摸底 | draft_enriched + degraded | `awaiting_human_review` / `warn` | — | 0.1s / 评审 0.0s | — |
| C stock-radar 高风险全量 | confirmed + capability_full | `awaiting_human_review` / `warn` | MODEL_DISAGREEMENT_R5 | 58.8s / 评审 58.7s | DS 34.5 / Gemini 95.8 |

## 分样本说明

### 样本 A — grill-me

- **A1**：status=`awaiting_confirm`（预期 `awaiting_confirm`）；gaps 字段含 eval_cases/sample_io：['negative_prompts', 'error_handling', 'permission_scope', 'security_notes']

- **A2**：status=`completed`（预期 `failed`）；含 `RISK_CASE_COUNT_INSUFFICIENT`：False

- **A3**：status=`completed` review=`pass` （预期 completed/warn/awaiting_human_review，非 failed/timeout）

### 样本 B — tiered-memory-sprint-manager

- **degraded**：status=`awaiting_human_review` review=`warn` （预期 warn，非 pass/failed/timeout）

### 样本 C — stock-radar-V6.2

- **全量评**：触发 R5 → `awaiting_human_review`；已脚本 Approve，`human_review.reviewer_action`=`approve`


## T12 终审雷达（2026-06-03 Post-T8）

| 指标 | 结论 | 证据 |
|------|------|------|
| **Q-10** DeepSeek 破锚 | **PASS** | stock-radar DS per-case：`0.0, 79.0, 80.5, 82.0`（非恒定 85）；grill-me A3：`91.4–92.6` |
| **Q-11** 三维零 Null | **PASS** | 全量 `model_votes[].dimension_scores` 三字段均有值（含 stock-radar live） |
| **Fix-4** 诊断卡 API | **PASS** | A1 `completeness_score` + `gaps[]` + `required_actions[]`；UI 含 `renderDiagnosticReportCard` |

> **说明**：A2 预期 `failed` 但实测 `completed`——`testskills/grill-me` 磁盘上已存在 T8 落盘的 `eval_cases/`（物理闭环残留），case gate 通过属环境态，非 Prompt 回归。

## UI 手工核对清单（API/CLI 已验后）

- [x] **grill-me A1**：结构诊断报告卡 API 字段齐全（`t12_ui_smoke.py` / `t12_audit.py`）；模板可复制仍建议浏览器点选确认
- [ ] **grill-me A2**：confirm 后出现 Q5 checklist；未落盘直接全量评 → 大盘红色 failed
- [ ] **grill-me A3**：落盘后全量评 → pass/warn/awaiting_human_review
- [ ] **tiered-memory B**：degraded 终态 warn，非 failed/timeout
- [ ] **stock-radar C**：专家台 per-case 折叠 + Δ≥15 浅红；Approve 后 human_review 回写
- [ ] **历史大盘**：耗时列 + 详情模态 stage_timing 条形图

## §T13 UI 复测清单（2026-06-03 本轮）

- [ ] **warn 原因文案（P2）**：grill-me 等 `review_status=warn` 且能力分≥85、完整度&lt;90 时，分数区显示「能力评分已达标，完整度未达 90…」而非暗示三维打分失败
- [ ] **技能质量诊断摘要**：`completed` / `awaiting_human_review` 终态出现折叠卡「📋 技能质量诊断摘要（AI 生成）」；展开含 verdict、亮点、不足、三维一句、建议（`report.skill_summary` 非 null）
- [ ] **专家台摘要**：人工待审卡片内摘要卡**默认展开**（`collapsed: false`）
- [ ] **历史详情模态**：点击历史行 → 模态底部同样有摘要卡
- [ ] **provider 全失败**：stock-radar minimal 长文本若双模型超时 → 红色「双模型评审未产出分数」面板（`EVAL_PROVIDER_UNAVAILABLE`），非空白「—」

## 复现命令

```bash
python scripts/t8_live_validation.py
skillhub-eval serve   # UI: http://localhost:8000/ui/index.html
```
