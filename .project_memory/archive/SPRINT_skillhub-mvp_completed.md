# SPRINT：SkillHub MVP · 阶段二收官

> **Sprint Root**：工作区根目录（`Skillhub/`）  
> **创建日期**：2026-06-01  
> **状态**：✅ **阶段二收官**（工程 + UI 验收 + `ui-ux-improvement` 已归档）  
> **Goal**：阶段二评估引擎全链路（2.0 + Phase 1 + 2.1b–2.6 + UI 体验改进）全部交付。

---

## Context

- 业务痛点：认知门槛高、资产碎片化、质量无标准（见 `docs/Project-Background.md`）
- MVP 定位：重运营、重标准、低门槛的内部 SkillHub，非纯技术仓库
- **220 tests passing**（2026-06-05）；T8 live 矩阵写入 `docs/runbooks/testskills-phase1-validation.md`
- Live DB：`data/t8_validation.db`（全矩阵）、`data/acceptance_2_1b.db`（tiered 2.1b）
- UI 入口：`http://127.0.0.1:8000/ui/index.html`（`/` 已重定向）
- OpenSpec change **`ui-ux-improvement`** 已归档 → `openspec/changes/archive/2026-06-05-ui-ux-improvement/`

---

## Tasks — 阶段一（文档定标）

**阶段一：已完成。** 详见 `RECORD.md`「阶段一收官说明」。

---

## 阶段二 · 2.0 工程实现（✅）

Tasks 1–12，**152 tests**，2026-06-02。六边形单仓 + 状态机 + DSL + 双模型 + SQLite + FastAPI + CLI + 确认台 UI。

---

## 阶段二 · Phase 1 T1–T14（✅）

| Task | 内容 | 状态 |
|------|------|------|
| T1–T5 | Level0 拆分、gaps、report、provider_summary | ✅ |
| T6–T7 | stage_timing、时延分级 | ✅ |
| T8 | testskills live + runbook | ✅ |
| T9–T12 | Prompt 质量修复 + live 复测 | ✅ |
| T13–T14 | warn 原因码、skill_summary、UI 手工复测 | ✅ |

---

## 阶段二 · 剩余任务 2.1b–2.6 + 2.4（✅ 2026-06-05）

> 计划：[`docs/superpowers/plans/2026-06-05-phase2-eval-remaining.md`](../docs/superpowers/plans/2026-06-05-phase2-eval-remaining.md)

| Task | 内容 | 状态 |
|------|------|------|
| **2.1b** | tiered-memory 3 case 补齐 → confirmed full live | ✅ |
| **2.3b** | `report_narrative` + `报告呈现规范.md` + UI 结论卡 | ✅ |
| **2.3c** | `disagreement_brief_zh` + UI 分歧卡 | ✅ |
| **2.2** | stock-radar 9 case（h/e/r/a）+ 对抗模板 | ✅ |
| **2.3** | `variance_report.py` + Prompt `case_type_hint` | ✅ 脚本；**导出待做** |
| **2.5** | AI 风险复核（DeepSeek）+ `RiskLockProvenance` | ✅ |
| **2.6** | average/redline 池拆分 + `REDLINE_MODEL_DISAGREEMENT` | ✅ |
| **2.4** | Health Check ADR + `expert_bias_table.py` | ✅ |
| **T8 复跑** | `scripts/t8_live_validation.py` 全矩阵 | ✅ 2026-06-05 |

---

## UI 验收 + 体验改进（✅ 2026-06-05）

> OpenSpec：`openspec/changes/archive/2026-06-05-ui-ux-improvement/`

| # | 验收项 | 状态 |
|---|--------|------|
| 1 | grill-me A1：补全台 gaps + 模板可复制 | ✅ |
| 2 | grill-me A2/A3：confirm → 全量评路径 | ✅ |
| 3 | tiered-memory B：degraded warn 展示 | ✅ |
| 4 | stock-radar C：专家台 per-case + Δ≥15 浅红 | ✅ |
| 5 | 中文 `headline_zh` / `reasons_zh` 运营结论卡 | ✅ |
| 6 | R5 `disagreement_brief_zh` 分歧卡 | ✅ |
| 7 | 风险锁定来源（自报/规则/AI）风险溯源卡 | ✅ |
| 8 | Approve 后 narrative 重建 + `human_review` 回写 | ✅ |
| 9 | Level0 中文诊断详情 + REASON_ZH 映射 | ✅ |
| 10 | per-case 三维中文标签 + feedback 截断折叠 | ✅ |
| 11 | Gemini 不可用黄色横幅 | ✅ |
| 12 | skill_summary 视觉重构（亮点/不足双列） | ✅ |
| 13 | 报告 UI 隐藏阶段耗时面板 | ✅ |

**手工验收结论（2026-06-05）：** 用户确认无阻塞问题；新跑评估 per-case 反馈受 v0.4 prompt 约束输出中文。

---

## 阶段二 · 剩余可选收尾（非阻塞）

| 顺序 | 编号 | 内容 | 说明 |
|------|------|------|------|
| 1 | **2.3 导出** | `variance_report.py` 基于 live DB 落盘 | `python scripts/variance_report.py` → `docs/runbooks/variance-*.md` |
| 2 | **环境** | grill-me A2「未落盘硬防线」样本隔离 | 磁盘已有 eval_cases → A2 live 为 pass；runbook 标注或临时移盘 |
| — | **Q-04** | 扩充基准 Skill 清单（3→5+） | 不阻塞阶段三 |
| — | **B→后续** | 场景分类联动 + eval_case 自动生成 | 依赖 **Q-08**；登记 BACKLOG |

---

## Out of Scope（阶段二已关闭）

- 阶段三 Portal / LUI 全量
- Q-08 场景联动 + eval_case 自动生成
- 1.2 阈值 / R5 10 分线修改
- 生产级网关与运行时熔断

---

## 阶段二状态总结

**阶段二评估引擎：收官（220 tests，2.0 + Phase 1 + 2.1b–2.6 + UI 体验改进）。**  
可选 Mode D 归档本 Sprint 文件至 `archive/SPRINT_skillhub-mvp_completed.md` 并提取 UI/运营经验至 `knowledge/`。
