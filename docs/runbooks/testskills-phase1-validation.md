# testskills Phase 1 — Live 验收 Runbook

> **执行时间**：2026-06-05 05:50 UTC  
> **数据库**：`data/t8_validation.db`  
> **自动化脚本**：`scripts/t8_live_validation.py`  
> **前置**：`.env` 已配置 DeepSeek + Gemini live key；单元测试 **195 passed**

## 验收矩阵（实测记录）

| Skill 实例 / 路径 | 评估状态（Expected Mode） | 实测终态（Status / Review） | 主错误码（Reason Codes） | 总耗时 / 评审耗时 | 双模打分（DS / Gemini） |
|---|---|---|---|---|---|
| A1 grill-me 草案入库 | minimal + capability_full | `awaiting_confirm` / `None` | — | 0.0s | — |
| A2 grill-me 未落盘硬防线 | confirmed + capability_full | `completed` / `pass` | — | 16.9s / 评审 16.8s | DS 92.6 / Gemini 94.5 |
| A3 grill-me 物理闭环 | confirmed + capability_full | `completed` / `pass` | — | 36.0s / 评审 35.9s | DS 92.2 / Gemini 94.5 |
| B tiered-memory 降级摸底 | draft_enriched + degraded | `awaiting_human_review` / `warn` | MODEL_DISAGREEMENT_R5 | 52.3s / 评审 52.2s | DS 75.3 / Gemini 92.6 |
| C stock-radar 高风险全量 | confirmed + capability_full | `awaiting_human_review` / `warn` | REDLINE_MODEL_DISAGREEMENT, MODEL_DISAGREEMENT_R5 | 65.2s / 评审 65.1s | DS 85.7 / Gemini 75.7 |

## 分样本说明

### 样本 A — grill-me

- **A1**：status=`awaiting_confirm`（预期 `awaiting_confirm`）；gaps 字段含 eval_cases/sample_io：['negative_prompts', 'error_handling', 'permission_scope', 'security_notes']

- **A2**：status=`completed`（预期 `failed`）；含 `RISK_CASE_COUNT_INSUFFICIENT`：False

- **A3**：status=`completed` review=`pass` （预期 completed/warn/awaiting_human_review，非 failed/timeout）

### 样本 B — tiered-memory-sprint-manager

- **degraded**：status=`awaiting_human_review` review=`warn` （预期 warn，非 pass/failed/timeout）

### 样本 C — stock-radar-V6.2

- **全量评**：触发 R5 → `awaiting_human_review`；已脚本 Approve，`human_review.reviewer_action`=`approve`


## UI 手工核对清单（API/CLI 已验后）

- [ ] **grill-me A1**：补全台 gaps 分区 + `eval_case` / `sample_io` 模板可复制
- [ ] **grill-me A2**：confirm 后出现 Q5 checklist；未落盘直接全量评 → 大盘红色 failed
- [ ] **grill-me A3**：落盘后全量评 → pass/warn/awaiting_human_review
- [ ] **tiered-memory B**：degraded 终态 warn，非 failed/timeout
- [ ] **stock-radar C**：专家台 per-case 折叠 + Δ≥15 浅红；Approve 后 human_review 回写
- [ ] **历史大盘**：耗时列 + 详情模态 stage_timing 条形图

## 复现命令

```bash
python scripts/t8_live_validation.py
python -m skillhub_eval.adapters.cli.main serve --host 127.0.0.1 --port 8000
# UI: http://127.0.0.1:8000/ui/index.html  （根路径 / 亦会跳转）
# API: http://127.0.0.1:8000/docs
```
