# Design: Wave 5.4 judge-trace

> 决策：D1–D7（脑暴）+ **GQ1–GQ7（grill-me 2026-06-12）** — 全文见 `docs/superpowers/specs/2026-06-12-judge-trace-design.md`

## Journey

```mermaid
flowchart TD
    A[capability_full 评审 case] --> B[prompt v0.5 + parse_judge_response]
    B --> C[vote_json 落库 + judge_traces 存 prompt]
    C --> D{双侧有效?}
    D -->|否| E[追踪页: 单侧确定性卡 GQ1]
    D -->|是| F{gap >= 15?}
    F -->|是| G[并行 generate 分歧解读 GQ2]
    F -->|否| H[divergence null]
    G --> I[代码算 max_gap_dimension GQ4]
    I --> J[写 divergence_json]
    E & H & J --> K[has_judge_trace on report API GQ7]
    K --> L[UI 链接 + trace.html]
```

## 模块映射

| 模块 | 路径 | 变更 |
|------|------|------|
| 解析 | `skillhub_eval/core/judge_parse.py`（新） | `parse_judge_response(raw)` — fence 剥离；`sub_scores.*.score` 必填；analysis 等可选（GQ6） |
| Prompt | `skillhub_eval/core/engine.py::_build_prompt` | v0.5 字段 + 先分析后打分；`review-agent-v0.5` |
| 投票 | `engine._judge_case` | 经 `parse_judge_response`；落 `judge_traces.prompt_text` |
| 分歧 | `skillhub_eval/core/divergence.py`（新） | `compute_max_gap_dimension(ds, gm)`；`build_synthesis_prompt`；`parse_synthesis`；并行 gather + 120s 超时（GQ2） |
| Settings | `skillhub_eval/settings.py` | `divergence_synthesis_timeout_s: float = 120.0`（env: `DIVERGENCE_SYNTHESIS_TIMEOUT_S`） |
| DDL | `persistence/sqlite.py` | v7 `judge_traces` + **UNIQUE(run_id, case_id)**；`has_judge_traces(run_id)` |
| API | `adapters/api/routes/eval.py` | `GET .../trace`；报告响应 **`has_judge_trace: bool`**（GQ7） |
| 追踪页 | `adapters/ui/static/trace.html` | 并排对照 / 分歧卡 / 单侧卡 / prompt 折叠 |
| 主 UI | `adapters/ui/static/index.html` | 链接条件 `capability_full && has_judge_trace`（GQ5）；就地弹模态（D7） |

## 接口契约

### divergence_json

```json
{
  "gap": 37.5,
  "max_gap_dimension": "output_compliance",
  "synthesis_zh": "<=300字，仅 LLM 产出>",
  "degraded": false,
  "single_sided": false
}
```

- `max_gap_dimension`：**代码计算**（GQ4），写入时机在 LLM 调用前/后均可，以代码为准。
- `single_sided: true` 时无 `synthesis_zh`，追踪页展示 `provider_error` 摘要（GQ1）。

### GET /eval/report/{run_id}（扩展）

新增字段：`has_judge_trace: boolean` — `EXISTS(SELECT 1 FROM judge_traces WHERE run_id=?)`。

### GET /eval/report/{run_id}/trace

（结构同 brainstorm spec §4.4；cases 含 `single_sided` / `provider_errors` 当适用。）

行为（Given/When/Then）：

- Given 双侧有效且 gap≥15，When 评估完成，Then divergence 含 `synthesis_zh` + 代码 `max_gap_dimension`。
- Given 仅单侧有效，When GET trace，Then `single_sided=true`，无 synthesis，有 provider 错误摘要。
- Given 旧 run 无 judge_traces，When GET report，Then `has_judge_trace=false`，UI 无链接。
- Given synthesis 超时 120s，When 评估完成，Then run 正常终态，`divergence.degraded=true`。
- Given v0.5 JSON 缺 analysis 但有 score，When 评估完成，Then vote 入库、聚合正常，trace 页显示「依据未返回」。

### v0.5 上线闸门（GQ3 · T7 live）

- 包级 `score_total` 变化 ≤ **5** 分；
- pass/warn/fail **终态不因 v0.5 单独翻转**；
- **refusal/adversarial** case per-case 分数大幅波动**豁免**记录。

## Visual direction（trace.html · ui-only）

（同原 design；增补：**单侧确定性卡**灰底；**依据未返回**占位文案；`max_gap_dimension` 行 amber-50 与专家台 Δ≥15 一致。）

## 测试映射

| 层 | 文件 |
|----|------|
| parse | `tests/core/test_judge_parse.py` |
| migration + has_judge_traces | `tests/persistence/test_judge_traces.py` |
| engine + divergence 并行/超时/单侧 | `tests/core/test_judge_trace_engine.py`、`tests/core/test_divergence.py` |
| trace API + has_judge_trace | `tests/api/test_trace_endpoint.py` |
| UI | `tests/api/test_ui.py` |
| live GQ3 | runbook + testskills 对比表 |
