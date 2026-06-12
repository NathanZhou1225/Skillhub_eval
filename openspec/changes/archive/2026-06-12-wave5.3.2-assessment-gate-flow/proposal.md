# Proposal: Wave 5.3.2 — 评估条件体检 → 补题 → 自动正式评估

## Why

Demo 反馈：确认 Skill 后文案「生成补题计划」易误导；补题计划与「初评就绪」卡信息重复；用户期望 **先体检、再补题、条件满足后自动正式评估**，无需二次点击「开始正式评估」。

## What

- 确认 Skill ID 后：**同步评估条件体检**（`assessment_gate_result`），文案「检查是否满足评估需求」。
- 不满足题型要求时：说明需补测试用例 → **补题计划**（沿用 W5.2 三方式）。
- 满足后：**自动启动 capability_full**（无双模型初评 run、无 `awaiting_readiness_choice` 人工闸门）。
- 作者主路径移除「补题后再跑 degraded 初评」。

## Scope

- `assessment_gate.py` + `conversations.py` / `chat.py` 流程重排
- UI：`assessment_gate_result` 渲染；`checking_requirements` pending
- 测试更新；RECORD + Sprint 同步

## Out of scope

- 1.2 阈值；集市上架；专家复核流程
