# Tasks: Wave 3 — Staging Case Propagator + 题型完整性门槛 + POST /conversations/start

> 验证门禁：`python -m pytest tests/ -x --tb=short`
> 执行方式：subagent-driven-development，每个 Task 一个 subagent。
> **grill-me 通过后再执行**。

---

## Task 1 — CASE_TYPE_REQUIREMENTS 常量 + check_case_gate 类型覆盖检查（W3-4 核心）

**文件**：
- `skillhub_eval/core/schemas/enums.py`（扩展，新增 `CASE_TYPE_REQUIREMENTS`）
- `skillhub_eval/core/level0.py`（修改 `check_case_gate`，新增类型覆盖检查）
- `skillhub_eval/core/schemas/report.py`（`EvaluationReport` 新增 `case_type_coverage: dict`）
- `tests/core/test_level0.py`（扩展，覆盖类型覆盖检查路径）

**要点**：
- `CASE_TYPE_REQUIREMENTS = {low: {"happy_path": 3}, medium: {"happy_path": 3, "edge": 2}, high: {"happy_path": 3, "edge": 2, "refusal": 2, "adversarial": 2}}`
- `check_case_gate` 在数量检查通过后，遍历 `bundle["eval_cases"]` 统计 `type` 分布，缺口→ `MISSING_REQUIRED_CASE_TYPES`
- `EvaluationReport.case_type_coverage` 默认 `{}`，引擎 ingest 后填充

**验证**：
```bash
python -m pytest tests/core/test_level0.py -v
```

---

## Task 2 — core/case_sanitizer.py（W3-2）

**文件**：
- `skillhub_eval/core/case_sanitizer.py`（新建）
- `tests/core/test_case_sanitizer.py`（新建）

**要点**：
- `SanitizerResult(broken_moved, invalid_type_count, gap_by_type, needs_propagation, existing_counts)`
- 调用 `ingest._load_cases(staging_path / "eval_cases")`
- 损坏 case → `(staging_path / "_broken").mkdir(exist_ok=True)`；`shutil.move`
- `VALID_CASE_TYPES = frozenset({"happy_path", "edge", "refusal", "adversarial"})` 加入 enums.py
- `existing_counts` 只统计 type in VALID_CASE_TYPES 的 case；`invalid_type_count` 统计其余
- `gap_by_type = {t: max(0, req - current) for t, req in CASE_TYPE_REQUIREMENTS[risk].items()}`
- `needs_propagation = any(v > 0 for v in gap_by_type.values())`
- 边界：staging/eval_cases/ 不存在 → 按 0 existing 处理
- **测试必须覆盖**：有 type 缺失 case 时，不计入 existing_counts 且不移走

**验证**：
```bash
python -m pytest tests/core/test_case_sanitizer.py -v
```

---

## Task 3 — core/propagator.py（W3-1）

**文件**：
- `skillhub_eval/core/propagator.py`（新建）
- `tests/core/test_propagator.py`（新建，使用 mock ds_provider）

**要点**：
- `CasePropagator(ds_provider, taxonomy=None)`
- `async propagate(skill_md_text, risk_level, category_slug, staging_path, gap_by_type) → PropagatorResult`
- 对每个 `gap_by_type` 中 `count > 0` 的类型，单独 LLM 调用
- 解析 JSON 响应；写 `eval_cases/prop_{type}_{n:02d}.yaml` + `sample_io/prop_{type}_{n:02d}.json`
- 异常/解析失败 → 降级写占位 case（`origin: staging_propagator_fallback`）
- `PropagatorResult(cases_written, cases_failed, used_fallback)`

**测试覆盖**：
- mock ds_provider 返回合法 JSON → 验证文件写入
- mock ds_provider 抛出异常 → 验证占位降级写入
- gap_by_type 为空 → 不调用 LLM，`PropagatorResult` 空列表

**验证**：
```bash
python -m pytest tests/core/test_propagator.py -v
```

---

## Task 4 — POST /conversations/start（W3-3）

**文件**：
- `skillhub_eval/adapters/api/routes/conversations.py`（新建）
- `skillhub_eval/adapters/api/app.py`（注册路由 `/conversations`）
- `tests/api/test_conversations_start.py`（新建）

**要点**：
- Request: `{skill_id, skill_bundle_path, source="local_ref"}`
- 同步：DB create_conversation → BundleResolver.ensure_staging → ingest → security_scan
- `blocked` → raise HTTPException 422，body 含 `{security_status, security_findings}`；conversation.status 更新为 "security_blocked"
- 同步：CaseSanitizer.run → CasePropagator.propagate（若 needs_propagation）
- 同步：create_run(conv_id, mode=degraded)
- BackgroundTask：engine.run_async(run_id)
- Response: `ConversationStartResponse(conversation_id, run_id, security_status, propagator_used, propagator_fallback)`

**测试覆盖**：
- `local_ref` source → staging copy + R_101 触发
- security blocked → 422 + no run_id
- Propagator called when gap > 0（mock Propagator）
- Propagator skipped when already complete（mock Sanitizer）

**验证**：
```bash
python -m pytest tests/api/test_conversations_start.py -v
```

---

## Task 5 — engine case_type_coverage 填充 + 全量门禁（W3-5）

**文件**：
- `skillhub_eval/core/engine.py`（修改，ingest 后填充 `report.case_type_coverage`）
- `tests/` 全量回归

**要点**：
- 在 engine ingest 步骤后（run 开始时）统计 `eval_cases` 的 type 分布，写入 `report.case_type_coverage`
- 验证零回归（292 + Wave 3 新测试全绿）

**验证**：
```bash
python -m pytest tests/ -x --tb=short
```

---

## 完成门禁

- [x] `check_case_gate` 对 high-risk 缺 adversarial → `MISSING_REQUIRED_CASE_TYPES`
- [x] `CaseSanitizer` 移动损坏 case + 正确计算 gap
- [x] `CasePropagator` LLM 成功路径写 YAML 文件
- [x] `CasePropagator` LLM 失败降级路径写占位 YAML
- [x] `POST /conversations/start` 返回 `{conversation_id, run_id, security_status}`
- [x] security blocked → 422，不创建 run
- [x] `EvaluationReport.case_type_coverage` 非空
- [x] `pytest tests/ -x --tb=short` 全绿（325 passed，含 Wave 3 新测试）
