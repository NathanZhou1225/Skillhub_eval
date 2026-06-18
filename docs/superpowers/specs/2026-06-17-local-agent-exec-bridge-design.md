# 本地 Agent 执行桥 — 设计稿（W8 重定义）

> 日期：2026-06-17（含同日 grill-me 修订）
> 状态：Grill 定稿；11 项设计变更已并入；OpenSpec change `local-agent-exec-bridge` 已落地（583 tests）
> 范围：阶段三 · Wave 8（重定义，取代原 W8 Level 2 中台沙盒 + 原 W9 自建 Harness）
> 相关：`RECORD.md`（2026-06-17 决策组、Q-19/20/21/22）、`.project_memory/active/SPRINT_phase3-eval-system.md`（W8.0–W8.6）、`docs/guides/Skill评估系统全景说明.md` §10
> 设计依据：`nexu-io/open-design`（local-first，daemon + per-agent adapter + **stream-json 流解析**）
> 模块映射（实现权威）：`openspec/changes/local-agent-exec-bridge/design.md`

---

## 0. Grill 修订摘要（2026-06-17）

本稿经 grill-me 后对初版做了 11 项改动，**两项推翻初版核心假设**，务必先读：

| # | 变更 | 类型 |
|---|------|------|
| G1 | **砍掉 `submit_case_output` MCP 工具，改「流解析」统一回传**（open-design 里只有 claude 有 MCP 注入，cursor-agent/codex 都没有，其真实机制就是解析 stream-json）。`SkillHubMcpServer` 组件 v1 删除 | 推翻 D3 |
| G2 | **judge 非「完全不动」：新增执行模式 prompt 分支**（现 prompt 是 doc-centric 评 SKILL.md；真跑时要按执行结果评）。流水线结构不动，prompt 分两套 | 修正 D5/D6 前提 |
| G3 | has_scripts 技能要 **entrypoint 执行证据**（tool_result 证明真跑过），否则降级 incomplete | 新增 |
| G4 | 新增 **`entrypoint` 元数据字段**（has_scripts 必填）；改 `docs/specs/Skill元数据定义与编写规范.md` + ingest + 校验 | 新增 |
| G5 | 新增 **per-skill `execution_source` 字段** + env `EXEC_SOURCE` 兜底默认 | 新增 |
| G6 | **强制用 harness prompt**（明确命令 agent 用 cwd 的 skill 并调 entrypoint） | 新增 |
| G7 | **原生 Windows 可行，不需 WSL**（open-design 适配器专为 Windows CreateProcess 限制走 stdin，已读源码确认） | 确认 |
| G8 | **红线题**：happy/edge 由 agent 真跑；红线真跑只有 **codex** 能上加固档（`--sandbox workspace-write` + `network_access=false`），**claude/cursor 红线降级 doc-centric** | 收紧 D2 |
| G9 | **level_2 = 本地真跑（有 entrypoint 证据，source=local_agent）；sample_io = level_1**；废弃 `has_scripts AND self.sandbox` 判定 | 修正 |
| G10 | **专家抽检纯人工**，但本地真跑 PASS 必须被标记且 history 可筛 | 收紧 D6 |
| G11 | **并发默认 2 + 限流自动退避**（检测到 429 → 退并发到 1 + 指数退避重试） | 细化 D2 |

适配实现顺序随之调整：**claude（claude-stream-json 最成熟）→ codex（自带沙箱，红线唯一可真跑）→ cursor-agent（json-event-stream + 私有 eventParser）**。

---

## 1. 背景与目标

### 1.1 问题

当前评估在 `case_executing` 阶段**不真跑 skill**，而是从磁盘读取作者事先放入的 `sample_io/{case}.json` 作为 `actual_output`（engine.py:313/330/1010）。后果：

- 中台 subprocess 沙盒（原 W8 计划）**结构上跑不了内网 skill**（无 VPN/DB/Token），而内网 skill 恰恰最需要真跑。
- 评的是「材料是否自洽」，不是「真实使用时能否跑通」。

### 1.2 目标

把「真实执行」**下放到开发者本地已配好的 CLI agent**（cursor-agent / codex / claude），由 SkillHub 同机 spawn 驱动其真跑 skill，**解析其 stream-json 流**收集真实产出；评分系统（DSL 断言 / 双模型 / 安全 / 聚合 / 决策）**结构不变、prompt 分执行/样例两套**，`actual_output` 来源改为真实执行。

### 1.3 取代关系

- 取代原 **W8 Level 2 中台沙盒**：本地 agent 跑任务时已执行 skill 脚本，中台再独立 `python run.py` 冗余。
- 取代原 **W9 自建 Agent Harness**：开发者本地已配好的 CLI agent 即「分布式 Harness」。
- 原 **W10 Golden Case + 上架后健康检查** 移至阶段四（与上架联动）。
- `PythonSubprocessRunner` 留架子，仅阶段四 Golden Case 需「精确断言 + 确定性复跑」时按需接最小版；**不物理删除**。

---

## 2. 已锁定决策（brainstorm + grill 2026-06-17）

| # | 决策 | 取舍 |
|---|------|------|
| D1 部署/传输 | **同机 spawn**：后端直接 spawn 子进程，无网络桥 | 排除网络桥 / MCP-over-network（先本地，上云再换 transport） |
| D2 执行粒度 | **每题隔离 + 有界并发**（默认 2，可配）+ risk 分级超时 + 限流退避（G11） | 排除单会话全串行（慢、红线被污染）；hybrid 待测出太慢再议 |
| D3 输出契约 | ~~MCP submit 工具~~ → **【G1 改】流解析统一契约**：解析 stream-json 取最终 result 文本 + tool_result + per-run cwd 产物文件 + 可选收尾 fenced JSON | 排除 MCP submit（cursor/codex 无 MCP 注入，仅 claude 有；不通用） |
| D4 工作目录 | **每次运行临时 clone**：从 staging 克隆 per-run 目录作 cwd | 排除共享 staging（并行写冲突）、只读 staging（写中间文件跑不起来） |
| D5 路径关系 | **增量 + 回退 + 来源可选**：作者选执行来源（per-skill 字段，G5）；agent 缺失/失败 → 自动回退 sample_io | 排除完全替代、并行对照（W8.4） |
| D6 信任（分阶段） | **v1 信任本地**：judge pass→PASS；抽检纯人工但可筛（G10）。**目标态**：公网中台复核 / 内网专家签收 | 排除 v1 建中台复核（过早）、一律签收（慢）、永久信任（多用户漏洞） |
| D7 断言策略 | **结构性 + 语义为主**，容忍 agent 非确定 | 排除精确值断言（换 agent/模型 flaky） |
| D8 v1 agent 集 | **claude → codex → cursor-agent**（G1 后按解析器复杂度/红线能力排序）；多 agent 对照 → W8.4 | 排除 v1 只打通 1 个；全量 agent（YAGNI） |
| D9 判子模式（G2） | **执行模式 prompt 分支**：真跑→执行结果 rubric；sample_io→现有 doc-centric prompt | 排除「prompt 不动直接填 actual_output」（红线口径自相矛盾） |
| D10 执行证据（G3） | has_scripts 技能要 tool_result 证明 entrypoint 真跑；无证据→降级 incomplete | 排除只信文本输出（agent 可绕 pipeline 手写） |
| D11 红线隔离（G8） | 红线真跑仅在加固档下；codex 用原生沙箱，claude/cursor 无加固档→红线降级 doc-centric | 排除原生 Windows 防火墙 ACL（脆弱）、强行全 WSL（工程量大） |

---

## 3. 架构概览

```
┌─ 引擎（core/engine.py，server-side async）────────────────────────┐
│  gate 通过 → capability_full → case_executing                      │
│        │                                                           │
│        ▼  经 ExecutionSource 取 actual_output（替换直调 load_sample_io）│
│  ┌─ ExecutionSource ─────────────────────────────────────────┐   │
│  │  SampleIoSource（回退/可选）  LocalAgentSource（真跑）      │   │
│  └───────────────────────────────────────────────────────────┘   │
│        │                                                           │
│        ▼  judge 双模式 prompt → 双模型 → DSL → 聚合 → 决策（不变）   │
└────────────────────────────────────────────────────────────────────┘

LocalAgentSource 内部：
  PerRunWorkspace（staging→临时 cwd）
    → harness_prompt
    → LocalAgentRunner（spawn + StreamParser + ArtifactCollector）
    → EvidenceVerifier（entrypoint 证据）
    → output sanitizer
```

各 agent 流格式（实读 open-design）：claude=`claude-stream-json`；codex=`json-event-stream`；cursor-agent=`json-event-stream`（私有 parser，文本去重见 `emitCursorTextDelta`）。

---

## 4. 降级矩阵

| 情况 | 行为 |
|------|------|
| 无 agent / 作者选 sample_io | 整轮 `SampleIoSource`（样例模式，低置信，level_1） |
| 未登录 | 回退 + 提示去 CLI 登录 |
| 红线 + claude/cursor（无加固档） | 该红线题降级 doc-centric，报告标原因 |
| has_scripts 无 entrypoint 证据 | 回退该题 sample_io；无样例 → `incomplete` |
| 单题超时/失败 | 回退该题 sample_io；无样例 → `incomplete` |
| 限流持续失败 | 退并发到 1 + 退避后仍失败 → 同上失败分支 |
| 全失败 | 等同现有 sample_io 路径，不额外退化 |

---

## 5. 信任（分阶段）

**v1**（同机/内部/作者本人）：judge（含双模型读 transcript）pass → PASS，标 `spot_check_eligible` 且 history 可筛；warn/R5 仍进 human_review。伪造风险记「已知暂受」。

**目标态**（多用户/上云）：公网题中台 agent 复跑高风险子集 + 双模型读 transcript；内网题双模型 + **专家签收**（复用现有专家流）。断言以结构性 + 语义为主（容忍 agent 非确定）。不改 R1–R8。

---

## 6. 实现与验收

- OpenSpec change：`openspec/changes/local-agent-exec-bridge/`（proposal / design / tasks）
- Runbook：`docs/runbooks/local-agent-exec-validation.md`
- Fixture：`testskills/exec-fixture-minimal/`
- 本地 E2E：`pytest -m requires_local_agent`（默认 skip）

模块级文件清单、接口签名与引擎改动点见 **`openspec/changes/local-agent-exec-bridge/design.md`**（不与本文重复）。
