# BACKLOG — SkillHub

> 非当前 Sprint 的较大项或 scope creep 落点。Active Sprint 见 `active/SPRINT_phase3-eval-system.md`（阶段三）、`active/SPRINT_phase4-marketplace-biz.md`（阶段四，待启动）。

---

## 阶段二（已收官 2026-06-05）

> 方差报告导出、grill-me A2 环境隔离 — **已取消**（由阶段三 eval_case 自动生成覆盖）

- [x] 2.0 评估引擎 + Phase 1 T1–T14 + 2.1b–2.6 + UI 体验改进（220 tests）
- [x] T8/T12/T14 live + UI 手工验收
- [ ] **Q-04** 扩充基准 Skill（3→5+）

---

## 阶段三（评估系统完善 · 当前主线）

> **2026-06-12 重定标**：本阶段只做评估系统；集市归阶段四。

### 已落地（Wave 0–W5.3.4）

- [x] **基础设施** — conversations / staging / run lineage（W0）
- [x] **场景分类词表** — Q-08 taxonomy（W1）
- [x] **安全门禁** — Level 0.5 + output sanitizer（W2）
- [x] **自动补题** — Propagator + 题型完整性门槛（W3）；Q-15 已闭合
- [x] **作者 Onboarding LUI** — 对话补全、代写、专家冻结、quota（W4）
- [x] **Chat-First 对话壳** — W5 / W5.1 / W5.2 / W5.3 / W5.3.2 / W5.3.3 / W5.3.4

### 进行中 / 待做

- [ ] **W5.5** 本地 Demo 验收（三剧本 + runbook）
- [x] **P2 / W4.5** Provider 完全 env 驱动（`JUDGE_PROVIDER_A/B_*` + OpenAI-compatible factory + label 展示）
- ~~**W7** 评估系统服务器彩排~~ → 阶段四 W7
- [ ] **评估系统增强 TBD** — 待产品窗口追加（见 `SPRINT_phase3-eval-system.md` §阶段三后续）

### P2 工程优化预留（2026-06-23）

- [x] `index.html` 模块化拆分（主业务脚本抽到 `/ui/assets/index.js`，保留现有 UI 行为）
- [x] `engine.py` / `chat.py` 状态流拆分（prompt、report 文件写入、propagation gate payload 已拆分）
- [x] W4.5 Provider env factory（模型、base_url、label、报告/UI 展示统一配置）
- [x] W7 前置测试环境整理（pytest basetemp/cache、release smoke 命令）

### 明确不做（归阶段四）

- ~~3.3 集市 / listing / Trending / 消费者 NL 匹配~~ → 阶段四 W6
- ~~W7 评估系统服务器彩排~~ → 阶段四 W7
- ~~独立 Portal / IAM~~ → 阶段四 4.3+

---

## 阶段四（集市生态 + 立项与商业价值 · 待启动）

> 依赖阶段三 W5.5 本地验收。W7 服务器彩排已移入本阶段。详见 `active/SPRINT_phase4-marketplace-biz.md`。

- [ ] **W6** 集市生态（listing、Export Freeze、Trending、NL 搜索、集市 UI）
- [ ] **W7** 评估系统服务器彩排（release zip、服务器 env、Linux smoke、`server-deployment.md`）
- [ ] **4.1** 痛点 ↔ 平台价值映射矩阵
- [ ] **4.2** 风控 Demo + 提效 Demo 材料包
- [ ] **4.3+** （可选）IAM / Portal 信息架构
