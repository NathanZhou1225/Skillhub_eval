# ARCHITECTURE — SkillHub MVP（产品设计视角）

> 全局技术/产品记忆（Evergreen）。Sprint 任务见 `active/`；叙事与决策见根目录 `RECORD.md`。

**Sprint Root**：工作区根目录（`Skillhub/`）  
**最后更新**：2026-06-12  
**用途**：MVP 架构蓝图与模块边界。阶段一：文档定标 ✅；阶段二：评估引擎 ✅（220 tests）；阶段三：**评估系统完善** 🟡（W0–W5.3.4 已落地，W5.5/W7 进行中）；阶段四：集市 + 立项商业化 ⬜ 待启动。

---

## 1. 系统定位

| 项 | 说明 |
|----|------|
| **产品形态** | 企业内部 Skill 集市 + 治理平台（重运营、重标准、低门槛） |
| **当前优先级** | 阶段三：**评估系统**（对话评估、补题、专家复核、Demo/部署）；阶段四：集市与消费者发现 |
| **主载体** | `SKILL.md`；OpenAPI / MCP 作为后续兼容方向 |
| **规范策略** | 评估尺子 + 入库前补齐；创作最小包 → 规范化 + 交互补全 → 可评估包 |
| **非目标（MVP 设计期需克制）** | 极客向技术栈分类目录；纯静态人工走查上架；无质检的黑盒压缩包流转 |
| **质量哲学** | 统一三维评判 + DeepSeek / WorkBuddy 交叉评审；沙盒或样例 I/O 固化证据；人工抽检校准 |

---

## 2. 逻辑架构（目标态）

```
┌─ 资产层 ─────────────────────────────────────────────────────┐
│  Skill 包（SKILL.md / eval_cases / sample_io / scripts 可选）  │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌─ 准入与质检层 ─────────────▼────────────────────────────────────┐
│  静态 Schema 校验 → 样例 I/O 或沙盒执行 → 评审 Agent 交叉评审   │
│  维度：指令遵循度 | 输出合规性 | 业务解决度                      │
│  产出：Transcript · pass/warn/fail · model_votes · feedback      │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌─ 集市与体验层 ─────────────▼────────────────────────────────────┐
│  业务场景分类树 · LUI 意图路由 · 参数自动映射 · 卡片指标透传    │
│  Trending / 评分 / 调用量飞轮                                    │
└───────────────────────────┬────────────────────────────────────┘
                            │
┌─ 治理层 ───────────────────▼────────────────────────────────────┐
│  IAM/SSO · 上架后健康检查 · 运行时监控 · IRR · 降权/熔断          │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. 核心模块（设计拆分）

| 模块 | 职责 | MVP 阶段 |
|------|------|----------|
| **元数据规范** | `SKILL.md` / JSON Schema / returns_schema / 防御性边界 | 阶段一 |
| **评估包规范** | `eval_cases` / `sample_io` / 可选 `scripts` / 可执行性 Level 0-3 | 阶段一 |
| **评估流程** | 缺口扫描 → 规范化 Agent → 交互补全 → 评审 → 准入（协议 §14） | 阶段一文档 / 阶段二实现 |
| **评估指标引擎** | 三维 40/30/30 + 元数据完整度；代码/模型/人工抽检协同 | 阶段一 |
| **规范化 Agent** | 缺口清单、草案生成、须人确认字段 | 阶段二 |
| **评审 Agent 工作流** | DeepSeek + Gemini 交叉评审；R5/红线分歧入人工 | 阶段二 ✅ |
| **样本与对抗集** | 3–5 基准 Skill + 诱导/违规边界用例 | 阶段二 |
| **校准回路** | 自动分 vs 专家预期偏差 → Prompt/权重迭代 | 阶段二 |
| **场景分类字典** | 财务/宏观等高内聚业务树（评估 ingest 校验） | 阶段三 ✅ |
| **作者 Onboarding LUI** | 对话补全、补题计划、代写、自动正式评估 | 阶段三 ✅ |
| **集市与消费 LUI** | NL 找 Skill → 参数映射 → 选用 | 阶段四 |
| **资产评价 UI** | 安装量/调用量/综合分；Trending | 阶段四 |
| **listing / Export Freeze** | Pass 后 originals 快照上架 | 阶段四 |
| **立项材料** | 痛点-价值矩阵；风控 Demo + 提效 Demo | 阶段四 |

---

## 4. 评审 Agent Prompt 骨架（调研沉淀）

```
<task>        — 评审目标与 Skill 范围（开发者填）
<thinking>    — 选型与参数推导（模型生成）
<criteria>    — 指令遵循 40% / 输出合规 30% / 业务解决 30%
<summary>     — 一句话结论（模型生成）
<feedback>    — pass/warn/fail + 归因（模型生成）
```

参考：`docs/research/Skill数据定义与编写规范调研.md` §3.3；协议正文见 `docs/specs/Skill元数据定义与编写规范.md`。

**文档三分离**：开发者指南 `docs/guides/Skill编写指南.md` · 评估协议 v0.3 · **评估标准 v1.0** `docs/specs/评估指标与准入标准.md`（评分权威）。

---

## 5. 关键约束（初稿）

1. **统一维度**：准入不做业务长尾定制规则堆叠。
2. **双向契约**：入参 Schema + 出参 `returns_schema`（白盒质检）。
3. **混合执行**：有脚本走沙盒执行；无脚本走样例 I/O 模拟。
4. **人工抽检**：`warn`、高风险、模型分歧、拒绝用例失败必须进入人工。
5. **分类**：用户触达以业务场景为主，非 Python/API 标签。
6. **安全**：网关 Sanitization；拒绝测试 / 越权场景入评测集。

---

## 6. 待架构确认项

| ID | 项 | 影响 |
|----|-----|------|
| A-01 | DeepSeek + WorkBuddy 的具体调用方式、并发与成本上限 | 工作流与成本 |
| A-02 | 用户指定首批常用 Skill / 自用 Skill 清单 | 样本库遴选 |
| A-03 | `SKILL.md` 与 OpenAPI / MCP 的后续兼容字段 | 生态扩展 |
| A-04 | 独立 SkillHub Portal 的信息架构与最小字段 | 阶段四 IA |

---

## 7. 阶段二已落地实现（2026-06-05 提取）

| 层 | 路径 / 能力 |
|----|-------------|
| **内核** | `skillhub_eval/core/` — `EvaluationEngine`、Level0 拆分、DSL 断言、`aggregate` average/redline 池、`report_narrative`、`risk_review`（DeepSeek） |
| **适配** | FastAPI 6 端点 + Typer CLI + `adapters/ui/static/index.html` 三 Tab 确认台 |
| **持久化** | SQLite：`evaluation_runs`、`model_votes`、`human_reviews`、`stage_timing` |
| **双模型** | `providers/deepseek.py` + `providers/gemini.py`；prompt `review-agent-v0.4` |
| **运营层** | `headline_zh` / `disagreement_brief_zh` / `RiskLockProvenance` / `skill_summary`；UI 运营结论·分歧·风险溯源三卡 |
| **验收** | 220 pytest；T8 live 矩阵 `data/t8_validation.db`；runbook `docs/runbooks/testskills-phase1-validation.md` |

**阶段二可选收尾（已取消）**：方差报告导出、grill-me A2 环境隔离 — 由阶段三 eval_case 自动生成承接。
