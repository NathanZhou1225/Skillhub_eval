# Tasks: wave5.4-judge-trace



> grill-me GQ1–GQ7 已锁定。执行：subagent-driven-development + TDD。



- [x] 1. **DB v7 + Port**：`judge_traces`（`UNIQUE(run_id, case_id)`）+ `save_judge_trace` / `get_judge_traces` / **`has_judge_traces`**（GQ7）

  - 验证：`pytest tests/persistence/test_judge_traces.py -q`

- [x] 2. **parse + Prompt v0.5**：`core/judge_parse.py` **`parse_judge_response`**（GQ6）+ `engine._build_prompt` v0.5 + `_judge_case` 落 prompt_text

  - 验证：`pytest tests/core/test_judge_parse.py tests/core/test_judge_trace_engine.py -q`

- [x] 3. **分歧合成**：`core/divergence.py` — **`compute_max_gap_dimension`**（GQ4）；并行 gather + **`DIVERGENCE_SYNTHESIS_TIMEOUT_S` 默认 120s**（GQ2）；单侧跳过 LLM + `single_sided`（GQ1）；degraded

  - 验证：`pytest tests/core/test_divergence.py -q`

- [x] 4. **API**：`GET /eval/report/{run_id}/trace` + 报告响应 **`has_judge_trace`**（GQ7）

  - 验证：`pytest tests/api/test_trace_endpoint.py -q`

- [x] 5. **追踪页** `[ui-only]`：`trace.html` — 并排 / 分歧卡 / **单侧卡** / 「依据未返回」/ prompt 折叠

  - 验证：`pytest tests/api/test_ui.py -q` + 浏览器手查

- [x] 6. **主 UI** `[ui-only]`：`index.html` — 链接仅 **`capability_full && has_judge_trace`**（GQ5）；就地弹模态（D7）

  - 验证：`pytest tests/api/test_ui.py -q` + 浏览器手查

- [x] 7. **回归 + live + 文档**：全量 pytest；stock-radar 追踪验收；testskills **GQ3** 对比表；RECORD / Sprint / 全景说明 / runbook

  - 验证：`pytest -q`（498 passed）；live GQ3 对比待 W5.5 实机彩排一并记录

