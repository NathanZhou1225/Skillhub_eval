# Q-24 / Q-25 Local Agent and Usage Design

> Date: 2026-06-24
> Status: Draft for user review
> Scope: Q-24 local agent execution optimization + Q-25 usage summary
> Out of scope: W5.5 script B/C, phase3 validation runbook, full Open Design adapter-layer migration, multi-agent comparison statistics

## Goal

This window improves the existing W8 local-agent execution bridge without changing the phase-three boundary: SkillHub still runs one selected local CLI agent for formal evaluation, then reuses the existing judge, assertion, aggregate, and expert-review pipeline.

The work covers:

- Q-24 local execution performance and UX: parallel case execution, visible local-agent budget, rate-limit backoff, risk-based per-case timeout, provider-error copy fixes, and broader agent/model selection.
- Q-25 token usage summary: provider and local-agent usage captured as event details and summarized into evaluation reports.

The work does not implement multi-agent comparison statistics in this window. It records enough agent/model metadata to make that later work straightforward.

## Agent Registry

Replace the current hardcoded agent references in `_resolve_adapter()`, `_AGENT_CATALOG`, and UI label maps with a declarative local agent registry.

The first supported execution set is:

| Agent ID | Label | Primary CLI | Notes |
|----------|-------|-------------|-------|
| `claude` | Claude Code | `claude` | Existing adapter, model passed with `--model` when selected |
| `codex` | Codex CLI | `codex` | Existing adapter, only current hardened redline-capable agent |
| `cursor-agent` | Cursor Agent | `cursor-agent` | Existing adapter, model passed with `--model` when selected |
| `trae` | Trae | `traecli` | New adapter, using a minimal Trae ACP prompt/run transport for this use case |
| `antigravity` | Antigravity | `agy` | New adapter, prompt via stdin; non-default model selection writes Antigravity's CLI settings before spawn |

Each registry entry should describe:

- `id`, label, binary names, detection hints.
- stream format and prompt delivery strategy.
- fallback models and optional live model discovery.
- whether the agent supports hardened redline execution.
- adapter factory/build-args behavior.

This registry is intentionally smaller than Open Design's full runtime catalog. Full migration of Open Design's adapter layer remains a follow-up phase-three optimization.

## Model Selection

Execution preferences expand from:

- `exec_source`
- `exec_agent`
- `consent_granted`

to:

- `exec_source`
- `exec_agent`
- `exec_model`
- `consent_granted`

`exec_model="default"` means no explicit model argument/config is passed, so the CLI uses its own configured default.

`GET /api/exec/agents/scan` returns, per agent:

- detected state and binary path.
- auth status when available.
- `models[]`.
- `models_source`: `live`, `fallback`, or `none`.
- selected model, if relevant.

Live model discovery is preferred when a CLI exposes a stable command or handshake. If discovery fails, the agent remains selectable with fallback model options. If a stored model is not present in the current list, preserve it and surface it as a custom/stale model rather than silently replacing it.

Fallback behavior by agent:

- Claude, Codex, Cursor: include `default` plus common model ids; pass `--model` only for non-default.
- Trae: attempt a non-interactive ACP/model probe with a short timeout; if it fails, use `default` and common Trae-supported fallback choices.
- Antigravity: use a static label list similar to Open Design; non-default selection uses Antigravity's supported configuration path.

## UI Design

The existing Exec Settings drawer remains the main configuration surface.

The top of the drawer becomes a two-step selector:

```text
本地 Agent:  [ Cursor Agent   v ]
运行模型:    [ GPT-5          v ]
```

The scan result cards remain below as status and smoke-test affordances, not as the primary selection mechanism.

UI details:

- Agent dropdown lists detected agents first and can show unavailable agents as disabled/status-only entries.
- Model dropdown updates when the selected agent changes.
- "重新扫描 / 刷新模型" refreshes both detection and model lists.
- Test runs the current selected agent/model.
- Header pill includes model context, for example `本地执行：Cursor Agent / GPT-5` or `本地执行：Trae / 默认模型`.
- Existing readiness and consent flows stay intact.

The report detail view adds a compact Token Usage section:

- total prompt/completion/total tokens.
- grouped rows by stage, provider, model, and optional case id.
- local-agent usage when the CLI reports it.
- no price estimation and no operations dashboard in this window.

## Case Execution Optimization

`case_executing` changes from serial case execution to bounded parallel execution.

Rules:

- Default concurrency is `EXEC_CONCURRENCY=2`.
- Each case still gets an isolated per-run workspace.
- `_case_exec_results` writes must be protected from concurrent mutation.
- The run still uses exactly one selected agent/model.
- Multi-agent comparison is explicitly out of scope.

Budgeting has two layers:

1. Whole local-agent phase timeout continues to use `LOCAL_AGENT_WORKFLOW_TIMEOUT_LOW_S`, `LOCAL_AGENT_WORKFLOW_TIMEOUT_MEDIUM_S`, and `LOCAL_AGENT_WORKFLOW_TIMEOUT_HIGH_S`.
2. Per-case local-agent timeout is risk-based, using new settings: `LOCAL_AGENT_CASE_TIMEOUT_LOW_S`, `LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S`, and `LOCAL_AGENT_CASE_TIMEOUT_HIGH_S`.

The UI should show local-agent phase budget during `case_executing`:

```text
本地 Agent 真跑中
已用 120s / 总预算 1800s / 剩余 1680s
```

The backend can expose a lightweight budget field in stage progress or report/run detail. If only stage start time and total budget are available, the frontend can compute elapsed and remaining time locally.

Rate-limit handling:

- Detect markers such as `429`, `rate limit`, and `too many requests` from parsed output or error text.
- On first rate-limit hit in the current run, reduce effective local-agent concurrency to 1.
- Retry the affected case with exponential backoff.
- If retry still fails, follow the existing degradation matrix: fall back to sample_io, or mark incomplete when no sample exists.

## Redline Safety Capability

Move the redline execution rule into agent capability metadata.

Current behavior:

- `codex` supports hardened redline execution.
- `claude`, `cursor-agent`, `trae`, and `antigravity` do not.

When `supports_hardened_redline=false`, redline cases degrade to doc-centric/sample handling and the report records the degradation reason. This is the same effective behavior as the previous Codex-only rule, but no longer hardcoded to a fixed list.

## Provider Error Copy

Provider B unavailable banners must not always say "API 限流".

Classify provider errors into at least:

- rate limit.
- region or service unavailable.
- auth/key/model configuration error.
- timeout.
- unknown provider failure.

The UI should show one concise Chinese sentence based on the classification.

## Usage Summary

Q-25 uses two persistence layers:

1. `eval_events` detail events, for audit and debugging.
2. `EvaluationReport.usage_summary`, for report/UI display.

Report shape:

```json
{
  "usage_summary": {
    "totals": {
      "prompt_tokens": 123,
      "completion_tokens": 45,
      "total_tokens": 168
    },
    "by_stage": [
      {
        "stage": "model_judging",
        "provider_label": "DeepSeek",
        "model": "deepseek-chat",
        "case_id": "happy_001",
        "prompt_tokens": 80,
        "completion_tokens": 20,
        "total_tokens": 100
      }
    ],
    "partial": false
  }
}
```

Covered stages:

- `model_judging`: dual judge calls per case/provider.
- `propagation_enrich` or equivalent generate/enrich calls.
- `divergence_synthesis`.
- `skill_summary`.
- `risk_review`.
- `local_agent`: from `ExecResult.usage` when available.

Provider changes:

- OpenAI-compatible providers must preserve response `usage` instead of returning only text/content.
- Provider calls should log `token_usage` events after each successful call when usage exists.
- Missing usage is non-fatal and should mark the summary as partial.

Aggregation:

- Build `usage_summary` from `eval_events` plus local-agent `ExecResult.usage`.
- Normalize common usage keys: `prompt_tokens`, `completion_tokens`, `total_tokens`.
- Keep provider label and model in every row when known.

## Testing and Verification

This window is allowed to add and run relevant tests, but not the full suite by default.

Planned test coverage:

- agent registry resolution and labels.
- adapter build args for Claude, Codex, Cursor, Trae, and Antigravity.
- fallback model list and stored `exec_model` preferences.
- scan API returns models and model source.
- case execution bounded parallelism and concurrency downgrade on rate limit.
- per-case timeout selection by risk.
- usage event logging and `usage_summary` aggregation.
- provider error classification.

Local CLI end-to-end tests for Trae and Antigravity remain marked `requires_local_agent` and skipped by default.

## Follow-Up Phase-Three Optimizations

The following are intentionally not part of this window:

- full Open Design adapter-layer migration.
- all 20+ Open Design agents as true execution adapters.
- generic ACP transport abstraction.
- prompt budget guards for Windows command-line length.
- richer auth diagnostics for every agent.
- cross-agent fallback chain.
- multi-agent comparison statistics and matrix UI.
