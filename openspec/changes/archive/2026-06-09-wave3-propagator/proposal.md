# Proposal: Wave 3 — Staging Case Propagator + 题型完整性门槛 + POST /conversations/start

## What

四个核心交付：

1. **`core/case_sanitizer.py`**（W3-2）— 在 Propagator 前运行；分析当前 staging 的 case 类型覆盖缺口；将损坏 case 移至 `_broken/`；若已完整则跳过 Propagator。
2. **`core/propagator.py`**（W3-1）— 按 risk_level + category 生成分型 case 套餐写入 staging `eval_cases/`；每条 case 标记 `origin: staging_propagator`；LLM（ds_provider）失败降级为最小占位 case。
3. **`POST /conversations/start`**（W3-3）— 一次性启动入口：创建 conversation → BundleResolver → Security Scan → Sanitizer → Propagator → R_101 `degraded` BackgroundTask；返回 `{conversation_id, run_id, security_status}`。
4. **题型完整性门槛**（W3-4）— `check_case_gate` 增加类型覆盖检查（`MISSING_REQUIRED_CASE_TYPES`）；`EvaluationReport` 新增 `case_type_coverage: dict`。

## Why

W0~W2 已打通基础设施 / 词表 / 安全门禁（292 tests）。W3 将「上传 Skill → 拿到初评 skill_summary」这条主链路联通，解锁 W4 LUI 对话。

**核心设计变更**（上一窗口脑暴已锁定）：废弃「`confirmed=true` 计数门槛」。

原方案问题：
- high-risk 作者需手写 9 道 YAML 才能上架，摩擦极高；
- adversarial/refusal case 内容高度专业，非 AI 很难写够质量；
- `confirmed` 字段在现有代码中从未被 PASS 门禁实际检查（`decision.py` 检查的是 `BundleState.confirmed`，即整包确认状态，与每条 case 的 `confirmed` 字段无关）。

新方案：**题型完整性门槛**——

| risk | happy_path | edge | refusal | adversarial | 合计 |
|------|-----------|------|---------|-------------|------|
| low | 3 | 0 | 0 | 0 | 3 |
| medium | 3 | 2 | 0 | 0 | 5 |
| high | 3 | 2 | 2 | 2 | 9 |

adversarial/refusal case 本身是天然反向压力：AI 生成出一道「试图让 Skill 输出非法内容」的 adversarial 题，然后双模型评审该题是否拒绝——这个信号比人工写 `confirmed: true` 更客观。

`confirmed` 字段降级为可选透明度标注（listing 展示「N 道作者已审阅」），不再是 PASS 门槛。

## Non-goals

- 不改 1.2 阈值（85/70/90）
- 不实现 W4 LUI 对话 UI 与代写流程
- 不实现 W6 集市 / listing
- `confirmed` 字段不从 YAML schema 中删除（保留兼容性，仅降级为透明度标注）
- 不新增独立 LLM 安全链路（Security Gate 复用 W2 静态规则）

## Relation to Sprint

SPRINT `phase3-marketplace.md` Wave 3（W3-1～W3-5）。依赖 Wave 0 ✅ / Wave 1 ✅ / Wave 2 ✅。

## Success Criteria

1. `POST /conversations/start` 返回 `{conversation_id, run_id, security_status}`
2. R_101 `degraded` 评估后 `skill_summary` 非 null
3. high-risk 缺 adversarial case → `check_case_gate` 返回 `MISSING_REQUIRED_CASE_TYPES`
4. Propagator 对 `grill-me`（low risk）生成 3 条 happy_path case 写入 staging
5. `pytest tests/ -x --tb=short` 全绿（≥292 + Wave 3 新测试）
