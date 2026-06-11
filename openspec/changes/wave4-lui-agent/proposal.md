# Proposal: Wave 4 — LUI Agent + 对话/卡片 UI

## What

六个核心交付：

1. **`core/lui_agent.py`**（W4-1）— 单次结构化 LLM 调用；输出 `{intent, reply, patch}`；内置特殊 marker 拦截；只读冻结模式。
2. **`core/staging_writer.py`**（W4-3）— 全域代写（SKILL.md frontmatter / eval_cases / sample_io）；写后路由计算（degraded / capability_full）；run 谱系管理（supersede + auto_run_count）；quota 熔断 + 专家冻结。
3. **API 面扩展**（W4-2 / W4-4b / W4-6 / W4-9 / W4-10）— `POST /conversations/{id}/chat`、`GET /messages`、`GET /status`、`POST /confirm-cases`（简化）；`POST /conversations/start` 支持 zip 上传；`POST /eval/review` 扩展 conversation 联动。
4. **契约层**（W4-7）— `RUNNING_STATUSES` 常量、Session Gate 共用函数、Repository Port 扩展、`conversations` 表新增 `auto_confirmed` 字段（DB version 2）。
5. **专家冻结与 Quota 熔断**（W4-4 / W4-5）— quota 满时改当前 run 为 `awaiting_human_review` + `conversation.status=frozen`；Expert Approve/Reject 联动重置 count + 解冻。
6. **UI 双栏对话**（W4-8）— Tab1 演进为左聊天 / 右卡片布局；Tab1 入口切为 `/conversations/start`；旧 `/eval/run` 折叠进 Debug 开关。

## Why

W3 已打通「上传 → Propagator → R_101 初评 → skill_summary」链路（328 tests）。W4 将这条链路变成**作者对话闭环**：

- 作者看不懂 JSON report → LUI 用中文解释亮点/不足/缺口
- 作者不知道怎么写 adversarial case → LUI 代写落盘
- 作者不知道何时能"提交正式评审" → gap 归零后 UI 亮出【整包确认】按钮
- 专家在 Tab2 处置 R5 / quota 熔断 → Reject 解冻 + 驳回意见注入对话

## 关键设计决断（脑暴 + Q&A 已锁定）

| 编号 | 决断 | 排除方案 |
|------|------|---------|
| Q1 | gap 归零 + 用户点【整包确认】按钮 → 系统内部 auto_confirmed=True → 下次 run 用 confirmed + capability_full | LUI LLM 意图分类（误识别风险高，状态穿透不可接受） |
| Q2 | per-case `confirmed` 纯透明度标注；题型完整性是 capability_full 唯一硬卡口 | per-case confirmed 计数作门槛（W3 已废弃） |
| Q3 | staging_writer 全域代写（SKILL.md frontmatter only + eval_cases + sample_io） | 仅写 case（无法补 metadata gap） |
| Q4 | 路由：A（题型未完整）→ degraded；B（gap 未归零）→ degraded；C（题型完整 + gap 归零 + confirmed）→ capability_full | B 路由 capability_full（权限字段未确认即正式评分） |
| Q5 | UI 轮询 status；run 完成且 messages_count=0 时前端发 `__TRIGGER_AGENT_OPENING__` 唤醒开场白 | engine 内部调 LUI（破坏 engine 纯洁性） |
| Q6 | 单次结构化 LLM 调用，强制 JSON `{intent, reply, patch}` | 独立分类路由（多一次 LLM 调用） |
| Q7 | 冻结 = `conversation.status=frozen` + `/chat` 网关 403 | 仅靠 run 状态判断（竞态条件） |
| Q8 | quota 满 → 改当前 active run 为 `awaiting_human_review` + 置 frozen | 新建专门 run（语义混乱） |
| Q9 | Tab1 全切 conversation flow；旧 /eval/run 折入 Debug 开关 | 两套并行入口（用户体验割裂） |
| Q10 | `GET /conversations/{id}/messages` 全量返回 | 分页（quota 限5次，消息量极小） |
| Q11 | zip 上传支持（multipart）；解压到 staging，source 内部视为 local_ref | 仅 local_ref（服务器部署后无法上传） |
| Q12 | W4 完全不碰 publish/freeze/listing | W4 混入 W6 逻辑 |
| SQ1 | `__SYSTEM_ACTION_CONFIRM_ALL__` 精确字符串匹配触发 auto-confirm，绕过 LLM | LLM intent=confirm_all（误识别 → 状态穿透） |
| SQ2 | SKILL.md 仅改 frontmatter（`---` 块），body 原封不动 | 全文替换（丢失作者原始内容） |
| SQ3 | UI-driven opening（前端轮询 + 静默发 marker） | engine 内置 callback |
| 上架物 | 集市发布 = 用户原始文件（source_path）；staging 是评估脚手架，评估后丢弃 | 发布 staging 版本（含 LUI 改写内容，作者未确认） |

## 上架物隔离原则（影响 W6）

```
source_path（用户原文件，只读）
    ├── SKILL.md          ← W6 listing 直接来自这里
    └── eval_cases/...    ← W6 listing 直接来自这里
staging_path（沙盒，评估专用）
    ├── SKILL.md          ← LUI 改写的 frontmatter patch 版本
    └── eval_cases/...    ← Propagator + LUI 生成的 case（不上架）
```

作者可在 UI 看到 LUI 的建议，**自行**修改本地原文件后重新上传，不强制合并。

## Non-goals

- 不改 1.2 阈值（85/70/90 / R5 10 分线）
- 不实现 W6 集市 / listing / publish / freeze
- 不实现 W5 Demo 剧本 runbook
- 不新增独立 LLM 安全链路（W2 静态规则复用）
- `bundle_state=confirmed` PASS 闸门（`decision.py`）不变

## Relation to Sprint

SPRINT `phase3-marketplace.md` Wave 4（W4-1～W4-10）。依赖 W0 ✅ / W1 ✅ / W2 ✅ / W3 ✅（328 tests）。

## Success Criteria

1. Demo 剧本 A 端到端跑通：`grill-me` → `/conversations/start` → R_101 → LUI 开场 → Agent 代写 case → gap 归零 → 【整包确认】→ R_102 `capability_full` → pass/warn 结论
2. Session Lock：engine running 时 `/chat` 返回 409
3. Quota 熔断：第 6 次代写触发 frozen + awaiting_human_review
4. 专家 Reject：conversation 解冻 + auto_run_count=0 + 驳回意见出现在 lui_messages
5. zip 上传：multipart POST 解压到 staging，后续流程与 local_ref 一致
6. `confirmed=false` 合成 case 可参与 capability_full（题型完整时），不再有 per-case confirmed 计数防线
7. `pytest tests/ -x --tb=short` 全绿（≥328 + W4 新测试）
