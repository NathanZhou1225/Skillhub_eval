## Why

Real-machine testing of the local-agent adapter framework (W8.7) surfaced four gaps before opening the tool to more users. The most serious: when a local CLI agent (e.g. Trae/GLM-5.2) fails or times out mid-run, `RoutingExecutionSource` silently substitutes sample_io output and discards the original failure reason — the run still completes with `status="ok"` per case, and the report/UI header can even display the *requested* agent/model label as if it had actually executed. A user cannot tell "the eval scored real local-agent behavior" from "the eval silently scored canned sample data" without querying the database directly. The other three gaps are UX friction discovered in the same session: an inconsistent loading-state label during skill-ID confirmation, a permanently-stuck "待测试" badge for Cursor Agent plus an overflowing path string for Codex, and a token-usage table that is always fully expanded inline (and was suspected, incorrectly, of omitting local-agent usage from its totals).

## What Changes

- **BREAKING (behavior change)**: local-agent execution failure/timeout no longer silently falls back to sample_io scoring. The run is marked blocked/incomplete with the real failure reason surfaced, instead of quietly downgrading to canned data. (Per user decision: honesty over convenience — no automatic masking of failures.)
- Local-agent failure reasons (`degrade_reason`, and where available a short stderr excerpt) are captured and persisted via an event log instead of being discarded before they reach the report/UI.
- `EvaluationReport`'s exec agent/model fields are corrected so they only claim an agent/model actually executed when a case genuinely ran through `local_agent`; they no longer echo the user's *selected* preference as if it were the *executed* outcome.
- Skill-ID confirmation loading label ("正在分析 Skill…") is now driven by conversation status rather than by input method (chip click vs typed text), so typing "确认" or a corrected skill name shows the same accurate loading state as clicking the confirm chip.
- Cursor Agent's scan-card badge updates to "可用" after a successful manual Test (client-side, until next re-scan), instead of staying on "待测试" forever due to the deferred-auth-check design.
- All local-agent scan cards get consistent path text wrapping so long install paths (e.g. Codex's hashed install dir) no longer overflow their card.
- The report's "Token 消耗" section becomes a compact summary (grand total / Provider A / Provider B / local agent) with a "查看明细" link that opens the full itemized breakdown in a modal, instead of always rendering the full table inline.

## Capabilities

### New Capabilities

(none — this is a hardening pass over existing capabilities)

### Modified Capabilities

- `skill-execution`: local-agent execution failure handling changes from silent sample_io fallback to blocking with a surfaced failure reason; report schema fields for "which agent/model executed" must reflect actual per-case execution outcome, not just the requested preference.

## Impact

- Backend: `skillhub_eval/core/execution_source.py` (`RoutingExecutionSource`), `skillhub_eval/core/schemas/report.py` (`ExecResult`, `CaseScoreRow`, `EvaluationReport` exec fields), `skillhub_eval/core/engine.py` (`_exec_agent_report_fields`, `_log_local_agent_usage`, run-blocking path), `skillhub_eval/core/provider_summary.py`.
- Frontend: `skillhub_eval/adapters/ui/static/assets/index.js` (skill-confirm optimistic loading, `renderExecAgentCards`, `renderUsageSummary`, new usage-detail modal), `skillhub_eval/adapters/ui/static/index.html` (new modal shell if needed).
- Backend chat flow: `skillhub_eval/adapters/api/routes/chat.py`, `conversations.py` (activity_phase / persisted loading message consistency).
- Tests: `tests/core/test_provider_summary.py`, `tests/execution/test_local_agent_source.py`, new tests for `execution_source.py` blocking behavior, `tests/adapters/test_exec_bridge_api.py`.
- Docs: `RECORD.md`, `.project_memory/active/SPRINT_phase3-eval-system.md`, `openspec/specs/skill-execution/spec.md` (delta), `docs/runbooks/local-agent-exec-validation.md`.
- No changes to `skillhub_eval/adapters/ui/static/index.html` business logic beyond the new modal shell — UI text/badge/layout changes only for items 1/2/3, consistent with the UI-only workflow boundary (visual layer, no eval-logic changes).
