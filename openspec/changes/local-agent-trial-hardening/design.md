## Context

Real-machine testing of the W8.7 local-agent adapter framework (Trae/Cursor/Codex) surfaced four issues in the same session:

1. Skill-ID confirmation shows an inconsistent optimistic loading label depending on whether the user clicked a confirm chip or typed the confirmation as text.
2. Cursor Agent's scan-card badge is permanently stuck on "待测试" (by design — its auth check is deferred to avoid a Windows hang), and Codex's long install path overflows its card (no CSS difference vs. Cursor/Trae; just missing wrap on all three).
3. The report's "Token 消耗" table is always fully expanded inline, and was suspected of excluding local-agent usage from its totals — investigation confirmed the totals logic is stage-agnostic and already correct; the actual reason no local-agent tokens appeared in a real test run is the deeper bug in item 4.
4. **The real bug**: `RoutingExecutionSource` silently substitutes `sample_io` output whenever local-agent execution fails or times out, discarding the original failure reason and returning a clean `status="ok"` result. `EvaluationReport`'s `exec_agent_label`/`exec_model_label` then fall back to reading the user's *global preference* (not actual execution), so a report can claim "Trae / GLM-5.2" ran when every case actually silently degraded to sample data. This was confirmed against a real run (`837c503c-...`): `execution_source_used=sample_io`, `case_executing` took 13s for 9 cases (impossible for real CLI round-trips), zero `local_agent` token-usage events, yet the report header showed "Trae / GLM-5.2".

The user made an explicit product decision: local-agent failure should **block** the run with the real reason surfaced, not silently downgrade to sample data. This is a deliberate behavior change (previously: automatic fallback was the documented behavior in the archived `2026-06-18-local-agent-exec-bridge` change).

## Goals / Non-Goals

**Goals:**
- Local-agent execution failure is never silently masked as a successful sample_io run; the real failure reason is preserved and queryable.
- Report/UI never attributes execution to an agent/model that did not actually run successfully.
- Skill-ID confirmation shows accurate, consistent loading feedback regardless of input method (chip vs. typed text).
- Local-agent scan cards render correctly (badge reflects a successful Test; long paths wrap instead of overflowing).
- Token-usage reporting is compact by default with full detail available on demand, without changing the underlying aggregation (already correct).

**Non-Goals:**
- Diagnosing/fixing the specific reason `trae-cli` currently fails on this machine — that follow-up investigation happens *after* this change ships, using the new failure-reason persistence this change introduces.
- Multi-agent comparison statistics (W8.4) — tracked separately in the sprint backlog.
- Any change to the DeepSeek/Gemini dual-model judging pipeline itself.
- Redesigning the exec-agent scan UI beyond the two specific defects (badge freshness, path wrap).

## Decisions

### D1: Block on local-agent failure instead of silent sample_io fallback

`RoutingExecutionSource.get_actual_output` currently falls back to `SampleIoSource` whenever the local result has `status != "ok"` or `actual_output is None`, discarding the original `ExecResult` (including its `degrade_reason`) entirely. This changes to: on local failure, return the **original** (failed) `ExecResult` unchanged — no substitution — so downstream code (case scoring, report assembly) sees the true incomplete/failed state and its reason.

Per-run behavior: if *every* case in a run ends up blocked this way (e.g. local agent unavailable or systematically failing), the run SHALL be surfaced to the user as blocked rather than silently producing a `level_1` "passing" report. This reuses the existing per-case `exec_status`/`exec_degrade_reason` surfacing added in the prior hardening round (Q-27) — because there is no more silent substitution, that existing UI badge now actually fires for this failure mode, which it previously could not reach.

**Alternative considered**: keep the automatic fallback but just add a "已降级" annotation. Rejected per explicit user decision — a passing report built on secretly-substituted sample data is worse than a run that visibly stops and asks the user to look at it, especially heading into a multi-user trial where trust in "did it really run" matters more than "did we get a report".

**Carve-out**: one existing `_incomplete()` reason, `redline_no_hardened_profile`, is *not* a failure — it is the spec'd, deliberate degrade for redline (refusal/adversarial) cases on agents without a hardened execution profile (`docs`/archived spec: claude/cursor-agent redline cases always degrade to doc-centric sample mode by design). `RoutingExecutionSource` keeps substituting `sample_io` for this specific reason only; every other `_incomplete()` reason (`consent_required`, `agent_unavailable`, `run_incomplete`, `missing_entrypoint_evidence`, `output_leak`) now blocks instead of silently substituting.

### D2: Persist the failure reason as an event before it can be discarded

Even without silent substitution, we still want a durable, queryable trail of *why* a local run failed (for our own debugging of adapter/CLI issues across users). `RoutingExecutionSource` logs a `token_usage`-adjacent event (reusing the existing `repo.log_event` mechanism already used for `local_agent` usage) capturing `case_id`, `degrade_reason`, and a bounded stderr excerpt when available. This does not require a new table — it rides the existing `analytics_events` mechanism.

### D3: Report exec-agent/model fields derive strictly from successful `ExecResult`s

`engine._exec_agent_report_fields` drops its "fall back to global preferences" branch for the case where no case executed successfully via `local_agent`. When no case succeeded, `exec_agent_label`/`exec_model_label` are `None`, and a separate, clearly-named pair (e.g. `exec_requested_agent_label`/`exec_requested_model_label`) carries what the user *selected*, so the UI can render "已选择 X，但未成功执行" instead of implying X ran.

**Alternative considered**: keep a single field pair and just add a boolean `exec_actually_ran: bool`. Rejected — a single overloaded field pair that sometimes means "requested" and sometimes means "executed" is exactly the ambiguity that caused this bug; splitting the fields removes the ambiguity structurally rather than by convention.

### D4: Skill-confirm loading label keyed off conversation status, not input method

`activityPhaseLabel`'s selection currently depends on whether the client used the internal chip action or a typed message. Change the client to check current conversation status (`awaiting_skill_id_confirm`) first when setting the optimistic pending label, so both chip-click and typed-confirmation show "正在分析 Skill…". The backend's "correction" branch (typed skill-id fix) also gets the same persisted agent message the confirm branch already has, for consistency.

### D5: Cursor badge freshness is client-side optimistic, not a new auth probe

Rather than running `cursor-agent auth status` during scan (documented risk: can hang on Windows — this is why `_AUTH_DEFERRED` exists), a successful `testExecAgent` call updates the cached scan entry's `auth_status` to `"ok"` client-side. This is intentionally optimistic and resets on the next full re-scan; it does not change backend detection semantics.

### D6: Token-usage summary — compact + on-demand detail, computed client-side

No backend/schema change: `usage_summary.by_stage` already contains everything needed. The UI groups rows into three buckets (`local_agent` stage vs. each provider's `provider_label`) purely in JavaScript and renders a one-line summary with a "查看明细" link that reuses the existing `detail-modal` shell to show the full per-stage table. Keeping this UI-only avoids touching the eval-logic boundary the `frontend-design`/UI-only workflow rule protects.

## Risks / Trade-offs

- **[Risk]** Blocking on local-agent failure means a user who selected "local" execution and hits a flaky/misconfigured CLI now gets *zero* report instead of a degraded-but-present one. → **Mitigation**: this is the explicit trade-off the user chose; the UI must clearly explain the failure reason (from D2) and offer to switch to sample_io explicitly (a conscious user action, not an automatic one) or retry.
- **[Risk]** Splitting `exec_agent_label` into "actual" vs. "requested" pairs is a schema change that could affect any other consumer of `EvaluationReport` (e.g. history list, other adapters). → **Mitigation**: additive field names, existing `exec_agent_label`/`exec_model_label` keep their meaning (actual) but their semantics tighten (null instead of misleading fallback) — old code reading these two fields degrades gracefully to "we don't know" rather than crashing.
- **[Risk]** This change surfaces failures more visibly, which may make the local-agent feature look "broken" in the upcoming multi-user trial compared to today's falsely-green reports. → **Mitigation**: this is intentional and desired — the whole point of this change is to stop hiding that. Follow-up work (out of scope here) is to actually fix why `trae-cli` fails once we can see the real reason.

## Migration Plan

1. Implement D1/D2 in `execution_source.py` with tests (existing failure-mode tests need updating since the fallback behavior they assert changes).
2. Implement D3 in `engine.py`/`report.py` with tests, update `CaseScoreRow`/UI badge to also trigger on this now-reachable failure path.
3. Implement D4 (chat.py/conversations.py + index.js).
4. Implement D5/D6 (index.js only).
5. Re-run a real Trae/GLM-5.2 evaluation to observe the actual failure reason now surfaced, and file a follow-up issue/backlog item to fix the underlying CLI invocation problem (tracked in SPRINT, not part of this change).
6. Update `docs/runbooks/local-agent-exec-validation.md` to describe the new "blocked, not degraded" behavior and how to read the failure reason.

## Open Questions (resolved via grill-me)

- **Blocking granularity**: resolved as **per-case**. A single case's local-agent failure marks that case `incomplete` (existing Q-27 machinery, now actually reachable since D1 stops discarding it) and does not count toward pass; the run otherwise completes normally and produces a report. The run is only hard-failed via the existing `RunStatus.failed` finalize path (reusing its `reason_codes`/`evidence` fields — no new status needed) when either (a) pre-flight detects no usable local agent at all, or (b) every case in the run failed local execution. This avoids one flaky/rate-limited case nuking an entire 9-case run, while still refusing to silently launder a fully-broken local run into a "passing" `level_1` report.
- **Manual "force sample_io anyway" override**: deferred, not built in this change. A user who wants sample_io scoring despite local failure can switch `exec_source` to `sample_io` themselves in settings and re-run. Adding an in-the-moment override button would reintroduce the "looks like it ran, actually didn't" ambiguity this change exists to remove.
- **Blocked-run persistence**: resolved — no new status/table needed. A hard-failed run (case (a)/(b) above) reuses the existing `_finalize_failed`-style path already used for other terminal failures (e.g. security block), so it is persisted and queryable through the existing history mechanism with a distinguishing `reason_codes` entry (e.g. `local_exec_unavailable` / `local_exec_all_cases_failed`).

## Q-29 Follow-up: Trae Completion Detection + Config Diagnostics (2026-07-02)

Real-machine testing after D1-D6 shipped surfaced a second-order bug: Trae/GLM-5.2 runs consistently failed with `degrade_reason=run_incomplete` and an empty `stderr_excerpt`, even though D1/D2 correctly stopped masking the failure. Root cause (found via an independent Codex review + direct verification on this machine): `stream_parser.parse_stream_events()` and `runner.is_run_complete()` never recognized Trae's own `type=result`/`type=turn.completed` events carrying `is_error: true` — a genuinely failed Trae run looked identical to a hung one (no error text captured, no completion flag set), so the timeout path always fired instead of the real failure being reported immediately. Once that detection gap was fixed, the true underlying issue became visible: this machine's `~/.trae/trae_cli.yaml` only sets `model: {name: GLM-5.2}` with no `models:` provider block, so trae-cli itself refuses to run ("Models is required") — a local environment/config problem, not a SkillHub bug. `icacls` on `~/.trae` also revealed a `CodexSandboxUsers` ACL entry with read+execute only (no write), while the interactive user account has full control — meaning any SkillHub `serve` process inheriting that sandboxed identity would additionally fail to persist Trae's own config/session state.

### D7: Diagnosis computed directly by SkillHub, not by shelling out to `trae-cli doctor`

Real-machine testing found `trae-cli doctor` can hang with no output for 40+ seconds, which would make every `scan_agents()` call as slow/unreliable as its worst case if it were used as a detection dependency. Diagnosis instead reuses the already-bounded `discover_models()` probe (`trae-cli models`, bounded by the existing `MODEL_DISCOVERY_TIMEOUT_S`, default 6s) plus a direct read of `trae_cli.yaml` (via `pyyaml`, already a dependency) and a local writability probe (create+delete a temp file in the config dir). None of these can hang indefinitely.

**Alternative considered**: shell out to `trae-cli doctor` and parse its output. Rejected — unbounded external command with an undocumented output format is a worse dependency than composing SkillHub's own already-proven-reliable checks. If SkillHub's diagnosis and the user's own manual `trae-cli` commands ever disagree, the surfaced `manual_hint` text gives the user the exact commands to check for themselves, rather than the system trusting a single opaque source.

### D8: Diagnosis surfaces at scan time only, not retrofitted into post-run failure events

Diagnosis is exposed exclusively via `GET /api/exec/agents/scan` → new `AgentScanItem.diagnosis_ok` / `diagnosis_message` / `diagnosis_hint` fields, shown before the user selects an agent to run a real evaluation (pre-flight, not post-mortem). The existing per-case `local_agent_failure` event (Q-28 D2) keeps carrying its own `degrade_reason`/`stderr_excerpt` and is not cross-referenced with the scan-time diagnosis in this round.

**Alternative considered**: also enrich the failure event/report with the diagnosis. Rejected for scope discipline — catching a misconfigured agent before the user spends a run on it addresses the confusion at its source; wiring the same diagnosis into the post-failure path can be a follow-up if scan-time diagnosis alone proves insufficient in practice.

### D9: `diagnose()` is a generic, optional `AgentAdapter` extension point

`diagnose(self) -> DiagnosisResult | None` is **not** added to the `AgentAdapter` Protocol in `runner.py` (which stays minimal: `build_args`/`detect`/`parse_stream`). The scan route checks for it via `getattr(adapter, "diagnose", None)` — the same optional-attribute convention this codebase already uses for `prompt_via_stdin`. `TraeAdapter` implements it first (the only agent with an observed real-world failure); Claude/Codex/Cursor-agent/Antigravity adapters have no `diagnose` attribute at all, so `getattr` returns `None` and scan silently skips diagnosis for them — zero behavior change for agents that already work.

**Alternative considered**: add `diagnose()` with a default no-op on a shared adapter base class. Rejected — adapters only conform to `AgentAdapter` structurally today (no shared base class); introducing one solely for this optional method is more churn than the existing `getattr`-based extension point.

### Manual remediation (outside SkillHub's codebase, user-owned)

Per explicit user decision, fixing this machine's `trae_cli.yaml` (adding a `models:` provider block referencing GLM-5.2) and the `.trae` directory's ACL (ensuring the account running `skillhub-eval serve` has write access, not just the interactive login) is done by the user directly, using the `manual_hint` text this change surfaces and the exact `icacls`/config-path commands recorded in the implementation plan. This is **not** SkillHub application code and is out of scope for the Codex implementation pass; the diagnosis feature's job is only to make the failure legible, not to auto-repair the user's local CLI installation.

## Q-29 Round 2: Independent Codex Review Findings (2026-07-02)

Before implementation started, the user routed the draft plan to Codex for an independent review (the user's explicit, re-stated goal is broader than "fix Trae": **all** local CLI agents' selected models must be able to run a local skill evaluation to completion, not just start up). That review found one confirmed bug and several legitimate scope gaps in the D7–D9 plan, verified independently (not taken on faith) before being folded in below.

### D10: Fix a self-masking bug in the original `TRAE_MODEL_NOT_IN_LIST` check — extract `is_model_verified_live()`

**Confirmed bug** (verified by re-reading `models.py:92-94`, not just trusting the reviewer): `discover_models(agent, stored_model=X)` silently re-appends `X` into its own returned `models` list (with `source="stale"` or `"custom"`) whenever `X` isn't found in the live probe. The original Task 4 draft called `discover_models(agent, stored_model=configured_model)` and then checked `configured_model not in {m["id"] for m in disc.models}` — that condition can never be true, because the function it's checking against just put `configured_model` back in. `TRAE_MODEL_NOT_IN_LIST` was dead code that would never fire in production. Worse, the unit test for this branch mocked out `discover_models` entirely, which hid the bug from TDD — the test replaced the exact function whose internal behavior caused the defect, so it exercised the assertion logic but never the real interaction.

Fix: extract a shared `is_model_verified_live(agent, model_id) -> tuple[bool, str]` into `models.py` that always calls `discover_models(agent, stored_model=None)` (never passing the model being checked, so it can never be self-appended) and only trusts entries with `source == "live"`. Both `TraeAdapter.diagnose()` and the new generic scan-level `selected_model_status` (D11) use this one helper — no duplicated masking-prone logic. A dedicated regression test drives the *real* `discover_models()` (mocking only the subprocess-level `_run_probe`) to prove the self-append case is actually handled, not just mocked away.

**Alternative considered**: keep two separate ad hoc checks (one in the Trae adapter, one in the scan route) each remembering to pass `stored_model=None`. Rejected — duplicated logic is exactly how this class of bug gets reintroduced; one shared, tested helper is the DRY fix.

### D11: Generic `selected_model_status` for the currently-active agent, not just Trae

The original D9 `diagnose()` extension point only ever gets implemented for Trae in this round — Claude/Codex/Cursor-agent/Antigravity would have no model-readiness signal at all, which does not meet the user's re-stated "all CLIs" goal. Rather than writing a bespoke `diagnose()` for every adapter, `GET /api/exec/agents/scan` computes a generic `selected_model_status` (`"ok" | "default" | "stale" | "probe_unavailable"`) + `selected_model_message` from data every agent already produces (`discover_models()`'s `models_source` and per-model `source`), using the same `is_model_verified_live()` helper from D10. This is computed **only for whichever single agent is the current `exec_agent` preference** — `ExecPreferences` only tracks one global `(exec_agent, exec_model)` pair, so "selected model" is only a meaningful question for that one agent; other cards in the same scan response don't have a model selection to evaluate yet.

**Alternative considered**: require every adapter to implement `diagnose()` so all agents get equally rich diagnosis. Rejected for this round — over-scoped relative to the concrete problem (only Trae has an observed real failure); the generic status gives every agent *some* signal cheaply, while `diagnose()` stays available for future agent-specific detail (e.g., if Codex or Cursor-agent surface their own config gaps later).

### D12: `POST /api/exec/agents/{agent_id}/test` accepts an explicit `model`, scoped to the active agent only

The existing smoke-test endpoint intentionally hardcodes `model=None` to prevent one agent's selected model leaking into another agent's Test click (e.g. Trae's `GLM-5.2` accidentally passed to Codex) — this protection (Q-24/Q-26 era) stays. It was, however, too blunt: it also means clicking Test for the *currently selected* agent+model pairing never actually validates that pairing, only the CLI's own default. Fix: the request body gains an optional `model` field; the UI only populates it when the card being tested is the currently-active `exec_agent` (using `_execPreferences.exec_model`, which naturally normalizes `"default"` to `None` server-side) — for any other, non-active agent card, the UI keeps sending no model, preserving the original leak protection unchanged.

**Alternative considered**: read `exec_model` from global preferences directly inside the test endpoint whenever it matches `agent_id`. Rejected — doing the "is this the active agent" check server-side duplicates state the UI already has to render the button correctly, and couples the endpoint to a specific client-side selection model; keeping the endpoint a dumb "test this agent with this optional model" primitive and letting the UI decide what to pass is simpler to reason about and test in isolation.

### Deferred (explicitly out of scope this round): `diagnose()` success is lenient when no model name is configured at all

A second Codex grill-me pass on the revised plan flagged that `TraeAdapter.diagnose()` returns `ok=True` whenever the config file has a non-empty `models:` block, even if neither `self.model` nor `trae_cli.yaml`'s `model.name` names a specific model — i.e., "some provider is configured" is treated as sufficient, without checking that *something* is actually selected. In practice the exec pipeline always resolves a concrete model or `None` before calling `diagnose()`, so this gap only matters for a config that has providers defined but truly no default model name anywhere, which is itself a niche local-config state. Adding a `TRAE_MODEL_NAME_MISSING` reason code for this was considered and explicitly deferred — it would grow this round's scope for a case with no observed real occurrence, matching the "avoid over-engineering" principle. Track it as a candidate reason code if it's ever actually seen in the wild.

### Unverified, defensive-only addition: `traecli.yaml` fallback filename

The reviewer suggested `TraeAdapter.diagnose()` should also look for `traecli.yaml` (no underscore) alongside `trae_cli.yaml`, citing "Trae's docs". This claim was checked and **not corroborated** — a web search for `trae_cli.yaml`/`traecli.yaml` documentation surfaced only `bytedance/trae-agent`, a same-named but unrelated open-source project whose config file is `trae_config.yaml` in the project working directory, not `~/.trae/`. Direct inspection of this machine's actual `~/.trae/` directory shows exactly one file, `trae_cli.yaml`. The fallback check is kept anyway because it's a one-line, zero-risk defensive addition (try the second name only if the first doesn't exist), but it must not be cited elsewhere as a confirmed fact about trae-cli's behavior — it is a hedge against an unverified claim, nothing more.
