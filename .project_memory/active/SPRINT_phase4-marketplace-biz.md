# SPRINT：SkillHub MVP · 阶段四（集市生态 + 立项与商业价值）

> **Sprint Root**：工作区根目录（`Skillhub/`）  
> **创建日期**：2026-06-12  
> **状态**：⬜ 待启动（依赖阶段三 **本地评估验收收官**：W5.5 三剧本 + W8 本地真跑）  
> **Goal**：在 **评估系统本地已可独立运行** 的前提下，完成 **服务器部署与多人协作彩排**，建设 **Skill 集市与消费者发现**（listing / Trending / NL 匹配 / 发布 Freeze），并完成 **立项提案与商业价值呈现**（痛点映射、Demo 材料、可选 IAM/Portal 细化）。

---

## Context

- **前置条件**：阶段三收官——作者可在**本地**完成上传→补题→正式评估→Pass/Warn/Fail；`originals/` 与 `staging/` 隔离已落地；W8 本地 Agent 执行桥可选验证
- **从阶段三迁入**：原 Wave **W6 集市生态** 全部条目；原阶段三 **W7 服务器部署**；原阶段四 **4.1 / 4.2 立项材料**
- **LUI 消费者侧**：自然语言找 Skill、参数映射归本阶段 **3.3 集市**，不再占用阶段三 Onboarding Agent 叙事

---

## Wave 7 — 评估系统服务器部署（自阶段三迁入，2026-06-23）

> **目标**：将 judge 流水线（双模型评审 + 安全 + 聚合）部署到服务器，供多人通过浏览器访问；**executor 仍留本地**（本地 CLI agent 穿透握手，与 W8 设计一致）。  
> **部署路线**：release zip → 服务器 env + smoke → 后续 Git/Docker。

- [ ] **W7-1** Release zip 制作（排除 `.env` / `venv` / 用户绝对路径）
- [ ] **W7-2** 服务器 env：`STAGING_ROOT`、`DATABASE_URL`、双模型 API Key
- [ ] **W7-3** 服务器 smoke：重跑阶段三 Demo 剧本 A；验证 Linux 路径/编码/权限
- [ ] **W7-4** `docs/runbooks/server-deployment.md`：部署步骤与 env 清单

**建议顺序**：W7 可在 W6 集市开发前或并行启动（多人访问评估 UI 的前置）；公网题中央 agent 复核能力可在 W7 后迭代。

---

## Wave 6 — 集市生态（自阶段三迁入）

- [ ] **W6-1** `skill_listings` DDL：`skill_id`, `display_name`, `category`, `risk_level`, `listing_version`, `snapshot_path`, `passed_at`, `usage_count`, `avg_rating`, `security_status`, `skill_summary_snippet`
- [ ] **W6-2** **上架 Export + Freeze**：
  - Pass 后将 **用户原始文件（`source_path` / originals）** 快照到 `data/listings/{skill_id}/{run_id}/`
  - 写入 `skill_listings`；staging 变只读；`conversation.status=published` → `/chat` mutation 403
- [ ] **W6-3** `POST /conversations/{conv_id}/publish`：显式发布；幂等
- [ ] **W6-4** API：`GET /marketplace/skills`（过滤+分页）；`GET /marketplace/trending`
- [ ] **W6-5** `core/skill_matcher.py`：消费者 NL → category hint + top-3 skill_id
- [ ] **W6-6** `POST /marketplace/search-nl`
- [ ] **W6-7** UI「Skill 集市」Tab：分类侧栏 + 卡片 + NL 搜索
- [ ] **W6-8** pytest：listing / trending / matcher / publish 幂等

---

## Wave 10 — 持续可验证（Golden Case + 上架后健康检查）（2026-06-17 自阶段三迁入）

> **目标**：通过后固化黄金样例；定期重跑防 API/脚本/模型漂移。与上架/集市强联动，故归阶段四。  
> **背景**：原阶段三 W10；执行层重定向后（本地 Agent 执行桥），首次 Pass 不再依赖中央确定性试跑。若 Golden Case 需"精确断言 + 确定性复跑"，可按需接最小版中央执行（`PythonSubprocessRunner` 组件留架子，仅限可中央跑的公网/自包含 skill）。

- [ ] **W10-1** Pass 时固化 Golden Case（本地 agent 真实产出 + 关键 metadata；可选确定性复跑结果）
- [ ] **W10-2** 对接 ADR `post-listing-health-check` 定时重跑与漂移告警
- [ ] **W10-3** 使用侧反馈指标入健康度（不参与首次 Pass）

---

## 立项与商业价值（原阶段四主线）

- [ ] **4.1** 痛点 ↔ 平台价值映射矩阵（对齐 `docs/Project-Background.md` 三维痛点）
- [ ] **4.2** 风控 Demo + 提效 Demo 材料包（可复用阶段三 stock-radar 等评估剧本叙事）
- [ ] **4.3** （可选）IAM / 审批规则细化（EQ1 自批 → 生产审批策略）
- [ ] **4.4** （可选）独立 Portal 信息架构最小字段

---

## Out of Scope（阶段四明确不做）

| 项 | 原因 |
|----|------|
| 重写 1.2 准入阈值 | 已锁定 |
| 评估引擎核心状态机大改 | 归阶段三后续增强 |
| 生产级推荐算法 / 真实调用网关 | MVP 演示级 Trending 即可 |

---

## 验收标准

| 里程碑 | 条件 |
|--------|------|
| **W7 通过** | 服务器承载 judge + 公网中央复核（executor 留本地）；剧本 A smoke 无路径/权限崩溃 |
| W6 通过 | `GET /marketplace/skills` 至少一条 pass listing；NL 搜索 top-3 |
| W10 通过 | Golden Case 固化（本地真实产出 + metadata）+ 上架后健康检查 smoke |
| 4.1–4.2 通过 | 立项材料可独立走查；Demo 链路与评估系统剧本一致 |
| **阶段四收官** | 服务器可多人访问评估 + 集市可演示「发现 → 选用」；立项叙事完整 |
