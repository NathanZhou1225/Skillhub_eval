# Proposal: UI/UX Improvement — 确认台体验全面提升

## What

基于 2026-06-05 UI 手工验收反馈，对 SkillHub 极简确认台 (`index.html`) 和评估引擎
Prompt 层做一批体验改进，消除业务可读性盲区，对齐`docs/guides/报告呈现规范.md`三层结构。

## Why

- **Level0 诊断不透明**：`LEVEL0_SCHEMA_FAIL` 原因码无上下文，用户不知道是路径错误还是 SKILL.md 缺失
- **专家台/历史模态缺运营解释层**：`renderNarrativeCard`/`renderDisagreementCard`/`renderRiskLockCard` 仅在作者台轮询中调用，专家在待审队列里看不到中文结论
- **Approve 后信息倒退**：批准通过后 `headline_zh` 仍显示"需人工复核"，`score_total` 仍为 `—`，语义不一致
- **Per-case 反馈语言杂乱**：`reason`/`dimension_notes` 字段由 LLM 自选语言，产出英文或中英混杂长段落，业务方难读
- **三维标签英文缩写**：`IF/OC/BR` 对非技术用户不直观
- **Skill Summary 排版密集**：`renderSkillSummaryCard` 内容有价值但视觉层级混乱，一屏塞满

## Scope

### In-scope

| 组 | 改动 | 文件 |
|----|------|------|
| A | Level0 evidence 展示 + reason_codes → reasons_zh | `index.html` |
| B | 专家台/历史模态接入3张中文卡；Approve后重建 narrative | `index.html`, `routes/eval.py`, `persistence/sqlite.py` |
| C | Prompt 加中文简洁指令；per-case feedback 截断折叠；Gemini不可用横幅；IF/OC/BR中文 | `engine.py`, `index.html` |
| D | renderSkillSummaryCard 视觉重构；summary Prompt 加字数约束 | `index.html`, `engine.py` |

### Non-goals（不动）

- 1.2 评估阈值（85/70/90）及 R5 10分线
- 阶段三 Portal / LUI 全量功能
- Q-08 场景联动 eval_case 自动生成
- `EVAL_DB_PATH` 运行时切换（仅 runbook 补注）
- 已有 214 tests 的逻辑语义（测试只做必要新增断言，不改存量）

## Relation to Sprint

当前 Sprint `SPRINT_skillhub-mvp.md` 已标注「UI 手工验收 → 反馈驱动改进」为主线。
本 change 执行后，UI 验收清单全部勾选，Sprint 可进入 Mode D 归档。

## Success Criteria

1. `pytest tests/` 214 + 新增断言全部通过
2. 服务重启后：专家台展示中文结论卡、分歧卡、风险锁定卡
3. Approve 后 `headline_zh` = "专家已批准，可进入上架流程"
4. Level0 fail 时 UI 显示 `evidence.detail` 中文说明
5. Per-case feedback 截断至 ≤80 字，超出折叠
6. Per-case 三维标签全部显示中文（指令遵循/输出合规/业务解决）
7. `renderSkillSummaryCard` 呈现双列亮点/不足 + 三维进度条
