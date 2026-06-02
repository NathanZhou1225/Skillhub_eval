# 阶段二 · 评估引擎工程化设计

> **状态**：Brainstorm 定稿（2026-06-02）  
> **范围**：Task 2.0 工程实现主设计；2.1–2.4 验证与校准在设计中有落点  
> **权威契约**（不重写阈值与 rubric）：  
> - [`评估指标与准入标准.md`](../../specs/评估指标与准入标准.md) v1.2.1  
> - [`评审Agent工作流与Prompt骨架.md`](../../specs/评审Agent工作流与Prompt骨架.md) v0.2  
> - [`Skill元数据定义与编写规范.md`](../../specs/Skill元数据定义与编写规范.md) v0.5  

---

## 1. 目标与交付边界

### 1.1 阶段二完成定义

**阶段二完成 =** 一个能在**本地**跑通的评判引擎：

- 吃进 Skill 包目录（filesystem）
- 走通 1.3 状态机与编排模式 A/B/C/D
- 产出完整 `evaluation_report.json`
- 将 `model_votes`、断言 Transcript、阶段状态、人工动作沉淀到 **SQLite**
- 提供 **CLI + 薄 FastAPI + 双 Tab 极简确认台**（Swagger `/docs` 为 Living Contract）

### 1.2 非目标（阶段二不做）

| 非目标 | 说明 |
|--------|------|
| 用户认证 | 无 JWT/OAuth |
| 任务队列 | 无 Celery/Redis |
| 重型 ORM | 无 SQLAlchemy 级联；`sqlite3` + 手写 SQL |
| Docker 沙盒 | 本地 subprocess；隔离留研发二期/K8s |
| SkillHub Portal / LUI | 阶段三 |
| 研发交接文档包 | **四阶段 MVP 全部完成后**再编写 |
| `replay`/`mock` LLM 模式 | 阶段二默认 `live`；Provider 抽象预留扩展 |

### 1.3 项目生命周期（记录）

```
阶段一（文档定标）✓
  → 阶段二（本设计：引擎 PoC + 持久化 + 确认台）
  → 阶段三（Portal / 分类 / LUI）
  → 阶段四（立项材料）
  → 四阶段完成后：正式交接研发 + 交接文档包
```

阶段二保证**可工程化演进**（内核 / 适配器 / 契约分离），不提前交付交接文档。

---

## 2. 架构决策摘要

| # | 议题 | 决策 |
|---|------|------|
| 1 | 交付形态 | 可运行 PoC + SQLite 最小持久化 |
| 2 | 仓库形态 | **六边形单仓**（`core` / `adapters` / `providers` / `persistence`） |
| 3 | 对外暴露 | 内核 + **CLI** + **薄 FastAPI** |
| 4 | 执行模型 | 轻量异步 Job（`BackgroundTasks` / `asyncio`），无队列 |
| 5 | LLM | **live 默认** + `BaseLLMProvider`（DS / WB 分实现） |
| 6 | 沙盒 | 本地 **subprocess**，仅 **Python** 入口，180s 超时 |
| 7 | 非 Python 运行时 | 降级 Level 1（sample_io），`WARN` + `UNSUPPORTED_RUNTIME_ENV` |
| 8 | 交互补全 | **极简确认台** Tab1（作者补全） |
| 9 | 人工抽检 | 确认台 **Tab2**（专家审核） |
| 10 | Case 数量 | **X1**：下限跟 1.2；上限 low **6** / medium **8** / high **12**；超出硬拒绝，**不截断** |

---

## 3. 逻辑架构

```
┌─────────────────────────────────────────────────────────────┐
│  adapters/                                                   │
│  ├─ cli/          skillhub-eval run | gaps | confirm       │
│  ├─ api/          FastAPI + OpenAPI + BackgroundTasks       │
│  └─ ui/static/    index.html（Tab1 补全 / Tab2 抽检）        │
├─────────────────────────────────────────────────────────────┤
│  core/            EvaluationEngine（1.3 状态机 A/B/C/D）     │
│  ├─ ingest, level0, risk_lock, normalize, case_exec         │
│  ├─ code_assert, aggregate, decision, explain                │
│  └─ ports: LLMProvider, SandboxRunner, Repository            │
├─────────────────────────────────────────────────────────────┤
│  providers/       DeepSeekProvider, WorkBuddyProvider        │
│  persistence/     SqliteRepository（stdlib sqlite3）       │
└─────────────────────────────────────────────────────────────┘
         │                              │
         ▼                              ▼
   Skill 包目录（filesystem）      data/skillhub_eval.db
   + evaluation_report.json
```

**演进原则**：四阶段后研发可替换 `persistence`（Postgres）、增加队列 Worker、上 K8s 沙盒；**`core` 与 JSON 契约字段名保持不变**。

---

## 4. 仓库结构

```text
Skillhub/
├── pyproject.toml              # 包名 skillhub-eval, Python ≥3.11
├── .env.example                # DS/WB API keys, EVAL_DB_PATH, live defaults
├── data/                       # .gitignore: sqlite, reports, snapshots
├── docs/superpowers/specs/
│   └── 2026-06-02-phase2-eval-engine-design.md   # 本文档
└── skillhub_eval/
    ├── core/
    │   ├── engine.py
    │   ├── orchestration/      # modes A/B/C/D
    │   ├── assert/             # Level0 + §6.4 DSL
    │   ├── aggregate/          # R1–R8, R5
    │   └── schemas/            # Pydantic ↔ 1.3 JSON
    ├── providers/
    │   ├── base.py             # BaseLLMProvider.judge()
    │   ├── deepseek.py
    │   └── workbuddy.py
    ├── sandbox/
    │   └── python_subprocess.py
    ├── persistence/
    │   ├── repository.py
    │   └── sqlite.py
    └── adapters/
        ├── cli/
        ├── api/
        │   ├── app.py
        │   └── routes/
        └── ui/static/
            ├── index.html
            ├── confirm-tab.js
            └── review-tab.js
```

### 4.1 技术栈

| 层 | 选型 |
|----|------|
| 语言 | Python 3.11+ |
| API | FastAPI + Pydantic v2 |
| DB | SQLite（`sqlite3` 标准库） |
| 前端 | Vanilla JS + Tailwind CDN |
| 服务 | uvicorn |

---

## 5. Living Contract · API

| 方法 | 路径 | 作用 |
|------|------|------|
| POST | `/eval/run` | 提交评估 → `run_id`, `status=pending` |
| GET | `/eval/report/{id}` | 报告 + 状态（**建议轮询 3–5s**） |
| GET | `/eval/history` | 历史列表；支持 `human_review_required` 过滤 |
| GET | `/bundle/{skill_id}/gaps` | `gaps.json` + 只读缺口列表 |
| POST | `/bundle/{skill_id}/confirm` | 确认安全字段 / eval_cases 草案 |
| POST | `/eval/{id}/human-review` | 专家抽检：approve_warn / reject / escalate |

OpenAPI `/docs` 为对外演示与研发接手的 **活契约**；Pydantic 校验 `bundle_state`、`evaluation_mode` 等 1.3 字段。

### 5.1 性能与超时

| 项 | 值 |
|----|-----|
| 工作流硬超时 | **180s** → `failed`, `EVAL_WORKFLOW_TIMEOUT` |
| 沙盒子进程超时 | **180s** → `SANDBOX_EXEC_TIMEOUT` |
| 预期时长（参考） | L0+L1：30–45s；L2+双模型：60–120s |
| 客户端轮询 | 3–5s（写入 OpenAPI 说明） |

---

## 6. 编排模式（1.3 §4）

| 模式 | 触发 | Normalize | 评审 `evaluation_mode` | 结论上限 |
|------|------|-----------|------------------------|----------|
| **A** 完整准入 | `confirmed` + Level 满足 | 可选 minor | `capability_full` | pass/warn/fail |
| **B** 存量摸底 | 旧包/最小包 | 必须 `gaps.json` | `degraded` | **warn** |
| **C** 补齐中 | `draft_enriched` | 继续追问 | `degraded` | **warn** |
| **D** 完整复评 | Tab1 确认后新 run | 停止静默改包 | `capability_full` | 可 **pass** |

**硬规则**（实现层 + API 双重校验）：

```text
review_status = "pass" 仅当：
  bundle_state = "confirmed"
  AND evaluation_mode = "capability_full"
  AND 无 R1–R4 fail
  AND（R5 已人工 approve 或未触发）
```

Tab2 在 `bundle_state != confirmed` 时：Approve **disabled**；API 返回 **409** + `BUNDLE_NOT_CONFIRMED`。

**模式 D**：确认后必须 **新 run + 新包快照**；禁止用未确认 draft 污染当前评估（1.3 §4 规则 4）。

---

## 7. 运行时状态机

### 7.1 `evaluation_runs.status`

```text
pending
  → level0_checking
  → [fail: LEVEL0_* | CASE_COUNT_EXCEEDS_LIMIT | RISK_CASE_COUNT_INSUFFICIENT]
  → risk_locking
  → normalizing
  → awaiting_confirm          # 可挂起；Tab1 确认后触发模式 D 新 run
  → case_executing
  → code_asserting
  → model_judging               # DS/WB asyncio.gather
  → aggregating
  → awaiting_human_review       # Tab2；仅重算 Decision，默认不重跑模型
  → completed | failed
```

### 7.2 Case 数量闸门（Level 0，X1）

| risk_level_locked | 最小用例（1.2） | MVP 上限 | 低于最小 | 高于上限 |
|-------------------|-----------------|----------|----------|----------|
| low | 3 | 6 | `RISK_CASE_COUNT_INSUFFICIENT` | `CASE_COUNT_EXCEEDS_LIMIT` |
| medium | 5 | 8 | 同上 | 同上 |
| high | 9 | 12 | 同上 | 同上 |

- 计数：`eval_cases` 内**全部** case（含 redline）。
- **禁止**智能截断或按 happy/edge/redline 优先级丢弃。

### 7.3 降级评估 · CodeAssert 边界

- `evaluation_mode = degraded`：未确认 `draft_value` **不作为** CodeAssert 失败依据（1.3 §11）。
- 结论上限 **warn**；不得 PASS。

---

## 8. LLM 接入

### 8.1 策略：live 体验 + Provider 骨架

| 项 | 说明 |
|----|------|
| 默认 | `.env.example` 配置真实 DS + WB；`EVAL_LLM_MODE=live` |
| 抽象 | `BaseLLMProvider` → `async def judge(prompt: str) -> dict` |
| 实现 | `DeepSeekProvider`, `WorkBuddyProvider`（SDK/HTTP、超时、重试） |
| 禁止 | `core` 内硬编码 `requests.post` 或特定 SDK |

阶段二不实现 `replay`/`mock`；若后续 CI 需要，仅新增 Provider 实现类。

### 8.2 三类 Prompt 分离

| 调用 | 模块 | 禁止 |
|------|------|------|
| 规范化 Agent | `core/normalize` | 最终 pass/fail 裁决 |
| 风险复核 Agent | `core/risk_lock` | 三维质量打分 |
| 质量评审 Agent | `providers` + rubric | 改包、改 risk |

---

## 9. 沙盒（Level 2）

| 项 | 行为 |
|----|------|
| 执行 | `subprocess.run(..., timeout=180, capture_output=True)` |
| 入口 | 仅约定 Python（如 `run.py` 或 `SKILL.md` 指定 `.py`） |
| 超时 | `SANDBOX_EXEC_TIMEOUT` |
| Node/Shell | 跳过 L2 → Level 1 + `WARN` + `UNSUPPORTED_RUNTIME_ENV` |
| 信任边界 | 2.1 白名单 3–5 个内部样本；无全员上传 |

---

## 10. 持久化（SQLite）

### 10.1 表结构（最小集）

| 表 | 用途 |
|----|------|
| `evaluation_runs` | 主记录：status、modes、scores、review_status、路径引用 |
| `stage_transitions` | 阶段耗时（2.3 瓶颈分析） |
| `assertion_results` | CodeAssert 结果 |
| `case_executions` | CaseExec 证据、level_used、exit_code |
| `model_votes` | 双模型打分（方差分析） |
| `transcripts` | LLM/沙盒日志引用 |
| `gaps_snapshots` | 规范化 `gaps.json` |
| `human_reviews` | Tab2 动作；**保留** `preserved_votes_json` |
| `bundle_confirmations` | Tab1 确认审计 |
| `analytics_events` | 1.3 埋点四事件 |

### 10.2 文件落盘

| 路径 | 内容 |
|------|------|
| `data/reports/{run_id}/evaluation_report.json` | 契约全文 |
| `data/snapshots/{run_id}/` | 评估时刻包快照（只读） |
| `data/transcripts/{run_id}/*.jsonl` | 大日志；DB 存 ref |

### 10.3 Repository 端口

```text
create_run / update_status / append_stage
save_votes / save_assertions / save_human_review
get_report / list_history / get_pending_human_review
```

---

## 11. UI · 双 Tab 确认台

### 11.1 Tab1 · 作者补全台

| 类型 | 字段/内容 |
|------|-----------|
| **可确认** | `negative_prompts`, `error_handling`, 权限边界, `eval_cases` 草案 |
| **只读** | description、category 等普通缺口（红/黄灯） |

只读文案：**「请在本地 SKILL.md 中补充以上基础信息后重新提交。」**

流程：`awaiting_confirm` → `POST /bundle/confirm` → 用户触发 `POST /eval/run`（模式 D）。

### 11.2 Tab2 · 专家审核台

- 列表：`human_review_required=true`
- 展示：双模型 votes 并排、R5、`reason_codes`
- 操作：`approve_warn` / `reject` / `escalate`
- 闸门演示：未 `confirmed` 时按钮 disabled + API 409

### 11.3 实现约束

- `adapters/ui/static/`；无 Vue/React 构建链
- AJAX 轮询既有 REST；与 Swagger 共用契约

---

## 12. 1.3 §14 检查清单映射

| 检查项 | 实现落点 |
|--------|----------|
| DS/WB 同 prompt/rubric 版本 | `evaluation_runs` + Provider 入参 |
| 写入 bundle_state / evaluation_mode | DB + report |
| PASS 闸门 | `decision.py` + API 409 |
| 三类 Prompt 分离 | §8.2 |
| risk 锁定在 CaseExec 前 | `risk_locking` 阶段 |
| R1–R8；R5 优先 | `core/aggregate/` |
| R5 → `score_total=null` | `score_total_source=null_due_to_disagreement` |
| §6.4 DSL | `core/assert/dsl.py` |
| reason_code / evidence | report + DB |
| 人工抽检不删证据 | `human_reviews.preserved_votes_json` |
| 埋点四事件 | `analytics_events` |
| degraded 上限 warn | 模式 B/C |
| post_listing_health_check | 枚举预留；**2.4** 实现跑通 |

---

## 13. Backlog 任务映射

| Task | 本设计落点 |
|------|------------|
| **2.0** | 全文；对照 §14 逐项勾选 |
| **2.1** | 白名单路径；模式 B 摸底；Q-04 样本 |
| **2.1b** | Tab1 确认 → 模式 D 复评 |
| **2.2** | 对抗 case 写入 `eval_cases`；high risk 上限 12 |
| **2.3** | `model_votes` + `stage_transitions` 导出/分析 |
| **2.4** | `GET /eval/history` + 方差脚本；Prompt 校准 |

---

## 14. 待输入（不阻塞 2.0 编码）

| ID | 内容 |
|----|------|
| Q-04 | 首批 3–5 个 Skill 路径（2.1） |
| Q-03 | DS/WB 成本与并发（Provider 层 retry/限流策略） |

---

## 15. 下一步

1. **用户审阅**本文档  
2. **writing-plans** → 阶段二实现计划（分 PR / 任务顺序）  
3. **grill-me** → 压测 plan（PASS 闸门、降级 CodeAssert、R5、Case 上限）  
4. **编码 2.0** → 样本验证 2.1–2.4  

---

## 文档维护

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-02 | Brainstorm 定稿：六边形架构、异步 Job、live LLM、subprocess 沙盒、双 Tab UI、Case X1 |
