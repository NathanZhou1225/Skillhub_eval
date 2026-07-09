# Local Agent Execution Bridge — Manual Validation Runbook

Validate Wave 8 local execution against `testskills/exec-fixture-minimal/`.

## Prerequisites

- Python env with `skillhub_eval` installed (`pip install -e .`)
- At least one supported CLI agent: `claude`, `codex`, `cursor-agent`, `trae-cli`/`trae`, or `antigravity` (`agy`). Trae installs under `%LOCALAPPDATA%\trae-cli\bin` (detection resolves PATH-external installs).
- `.env` with DeepSeek + Gemini keys (full formal eval still needs LLM judges)
- **`serve` 与 CLI agent 须同机**（服务端 spawn 子进程，非浏览器直连 CLI）

For the **CLI / pytest path** only (optional): set `EXEC_SOURCE=local`, `EXEC_AGENT=claude|codex|cursor-agent|trae|antigravity`, and optionally `EXEC_MODEL=<model-id>`, or grant consent via Python (see [Consent gate](#consent-gate-cli--fallback)).

## UI path (zero `.env` EXEC_*)

Primary acceptance path for `ui-local-exec-bridge`. Do **not** set `EXEC_SOURCE`, `EXEC_AGENT`, or `EXEC_CONSENT_REQUIRED` in `.env`; global preferences in SQLite override env when present.

### 1. Start server

```bash
skillhub-eval serve
```

UI: <http://127.0.0.1:8000/ui/index.html>

### 2. First load — default local mode + C16 banner

- Fresh DB / no prior preferences → `GET /api/exec/preferences` returns `exec_source=local` (default).
- While `exec_source=local` and `ready=false`, the **C16 onboarding banner** appears on **every page load**:
  - Copy states default is local Agent CLI execution for testing Skills.
  - **「知道了」** hides the banner for the current session only; hard refresh → banner returns until resolved.
  - **「改用样例评估」** calls `PUT /api/exec/preferences` with `sample_io` → banner stops; header pill shows sample mode.
  - When CLI + agent + consent make `ready=true`, the banner auto-hides (no dismiss required).

Header **ExecBridgeIndicator** (C01): red/disabled when local && !ready; green with agent label when ready; muted「样例自证」when `exec_source=sample_io`.

### 3. Exec Settings drawer (C02–C07)

Open via header pill or **「执行设置」**.

| Step | UI action | API |
|------|-----------|-----|
| Scan | **重新扫描** | `GET /api/exec/agents/scan` — lists registered agents (`claude`, `codex`, `cursor-agent`, `trae`, `antigravity`) with detect/auth/models/install hints |
| Mode | Confirm **本地真跑** selected (default) | `PUT /api/exec/preferences` `{ "exec_source": "local" }` (instant save, no Save button) |
| Agent | Select a **detected** radio card | `PUT /api/exec/preferences` `{ "exec_agent": "<id>" }` |
| Consent | Check **我同意本机执行** | `POST /api/exec/consent` |
| Smoke | Click **[Test]** on agent card (optional; works without consent) | `POST /api/exec/agents/{id}/test` — the UI passes the selected model only for the currently active agent card; other cards keep testing the CLI default; ~8–90s depending on CLI |

Verify readiness: `GET /api/exec/preferences` → `ready=true`, `consent_granted=true`, chosen `exec_agent`. Preferences persist across `serve` restarts (sqlite global row, DB v10).

### 4. Run `exec-fixture-minimal` through the web UI

Fixture: `testskills/exec-fixture-minimal/` (`execution_source: local`, `entrypoint: scripts/run.py`, confirmed bundle).

1. **新对话** → upload the fixture as ZIP **or** (dev panel) set `skill_bundle_path` to the fixture directory, `bundle_state=confirmed`, `evaluation_mode=capability_full`.
2. If local is not ready when formal eval would start:
   - Formal eval is **blocked** (G4); **BridgePromptCard** (C11) appears instead.
   - Complete drawer steps above, or wait ≤10s for poll → card turns green and **auto-resumes** formal eval.
3. If global prefs are `sample_io` but bundle requires local → **conflict Modal** (G5); choose local or sample before proceeding.
4. During eval, stage banner (C09) shows **「本地 Agent 真跑中」** (not「校验样例输出」).
5. On completion, check report **ExecOutcomeStrip** (C10): `LOCAL` badge, `execution_source_used=local_agent`, `spot_check_eligible=1` when PASS.
6. If the agent creates or modifies small text files in the per-case workspace, the report payload includes them under `actual_output.artifacts` (`path`, `size_bytes`, `content`). This is intended for JSON/Markdown/log/report outputs produced by the skill run; binary files and unchanged bundle files are skipped.

See [Spot-check queue filter](#spot-check-queue-filter) for history API verification.

## Local execution failure is blocked, not silently degraded (2026-07-01, `local-agent-trial-hardening`)

Before this change, a local-agent failure (agent unavailable, consent missing, CLI timeout, etc.) was **silently replaced** by `sample_io` sample data: the run finished as if it had passed, and the report claimed the originally-selected agent/model had executed. This is no longer the case.

**Current behavior:**

- A single case's local execution failure marks that case `incomplete` (does not count toward pass) — the run otherwise proceeds and produces a report.
- A case with `status != ok` or no `actual_output` is **not sent to DeepSeek/Gemini for semantic judging**. It appears in the per-case table with empty model scores and the red "本地执行未完成" badge.
- Bundle `score_total` is calculated only from cases that successfully produced `actual_output`. Failed local cases are execution diagnostics, not scoring inputs.
- If **every** case in the run fails local execution, or no usable local agent was detected at all, the whole run is finalized as `status=failed` with `reason_codes` including `LOCAL_EXEC_UNAVAILABLE` (no agent) or `LOCAL_EXEC_ALL_CASES_FAILED` (agent ran but every case failed). No report is produced pretending the run passed.
- One exception: `redline_no_hardened_profile` (an agent without a hardened execution profile hitting a redline/adversarial case) is a **deliberate** design degrade, not a failure — it still substitutes `sample_io` for that specific case, by spec.

**How to read why a run/case failed:**

- Report (`EvaluationReport`): `exec_agent_label`/`exec_model_label` are only non-null when a case actually executed successfully via `local_agent`. `exec_requested_agent_label`/`exec_requested_model_label` always show what the user's preferences pointed at, whether or not it actually ran — so a report can never claim an agent "ran" when it didn't.
- Per-case: `CaseScoreRow.exec_status`/`exec_degrade_reason` (surfaced in the UI as a red "本地执行未完成" badge with a Chinese reason on hover).
- Event log: each local-agent case lifecycle is persisted through `local_agent_case_started`, `local_agent_case_succeeded`, and `local_agent_case_failed` analytics events. Failures are also persisted as `local_agent_failure` (`case_id`, `degrade_reason`, a bounded `stderr_excerpt`), queryable via `SqliteRepository.list_events`/the `analytics_events` table even after the report UI is closed.
- UI: `formatScoreDisplay`/`formatScoreCompact` render `LOCAL_EXEC_UNAVAILABLE`/`LOCAL_EXEC_ALL_CASES_FAILED` as a red "本地执行阻断" badge instead of a score.
- UI: during a running evaluation, the chat/report poll renders **本地 Agent case 进度** from `stage_progress`, including running/succeeded/failed cases, elapsed time, selected agent/model, and stderr excerpts when available. The chat live panel is capped at `max-h-[40vh]`, the case list scrolls internally, and the panel shows the last refresh time so operators can distinguish a live poll from a stalled UI.

**Real-machine confirmation (2026-07-01):** a fresh run against Trae/GLM-5.2 (`run_id=9f5ff946-...`) produced `status=failed`, `reason_codes=['LOCAL_EXEC_ALL_CASES_FAILED']`, `exec_agent_label=None` (not claimed as executed), `exec_requested_agent_label=Trae`. All 5 cases logged `local_agent_failure` events with `degrade_reason=run_incomplete` (streamed output never reached its end marker). **The specific reason `trae-cli` produces `run_incomplete` on this machine is not yet root-caused** — that is tracked as a follow-up backlog item, not fixed by this change.

**If you want `sample_io` scoring instead of blocking on local failure:** switch `exec_source` to `sample_io` in **Exec Settings** and re-run. There is intentionally no "run anyway with sample data" button in the moment of a blocked run — that would reintroduce the "looks like it ran, actually didn't" ambiguity this change removes.

### Complex-skill timeout diagnosis (2026-07-08 stock-radar)

The stock-radar real-machine trial is the current reference for a complex Skill that reaches real local execution but still fails:

- Example run: `2d981732-601b-40c0-be3e-ad0625393a04` (`stock-radar-cursorauto`, Cursor Agent / Auto).
- The run entered `case_executing`; it did **not** stop at preflight.
- The run ended `status=failed` with `reason_codes=["LOCAL_EXEC_ALL_CASES_FAILED"]` after about 914s in local case execution.
- Several cases each failed after roughly the configured per-case timeout (`LOCAL_AGENT_CASE_TIMEOUT_HIGH_S=300`) with `degrade_reason=run_incomplete` and no stderr.

Interpretation:

- This is a real local-execution failure for the selected runtime/model on this Skill, not a judge/scoring failure and not a `LOCAL_RUNTIME_PREFLIGHT_REQUIRED` gate.
- A green connection test only proves the CLI can answer a minimal probe; it does not prove the selected model can finish a long business workflow.
- For comparisons, first rerun a simpler Skill or `testskills/exec-fixture-minimal/`; then compare Cursor/Codex/Trae on the same Skill with the same case timeout/concurrency settings.
- Deferred optimization: first-case canary can stop later cases after process-level local runtime failures. This is intentionally not part of the P0 preflight downgrade.

## Selected-model diagnosis and model-aware Test (2026-07-02, Q-29)

This follow-up makes local CLI model readiness visible before a formal run:

- Trae stream-json `type=result` / `type=turn.completed` events with `is_error: true` or `subtype=error_during_execution` are now treated as real failures, not successful completion and not a silent hang. The error text is preserved for the local execution failure path.
- `GET /api/exec/agents/scan` now returns Trae-specific diagnosis fields when available: `diagnosis_ok`, `diagnosis_reason_code`, `diagnosis_message`, and `diagnosis_hint`. Current Trae reason codes include missing config dir, config dir not writable, missing `models:` provider config, model probe unavailable, and selected model not present in the live model list.
- The same scan response also returns a generic `selected_model_status` / `selected_model_message` for the currently selected `(exec_agent, exec_model)` pair across all registered agents. Status values are `default`, `ok`, `stale`, and `probe_unavailable`.
- `POST /api/exec/agents/{id}/test` accepts an optional JSON body: `{ "model": "..." }`. The UI only sends this body when testing the currently selected agent card; non-selected agent cards still send no model to avoid cross-agent model leakage.

Reference-machine example: `C:\Users\19430\.trae\trae_cli.yaml` selected `GLM-5.2` but had no `models:` provider block, so `trae-cli` could not know which provider/endpoint/key should serve that model. ACL inspection also showed `CodexSandboxUsers` had read/execute but not write access to `.trae`, while the interactive user had full control. Those are local Trae environment issues; SkillHub now surfaces them instead of masking them.

**Update (2026-07-02, real-machine verification):** the `models:`-missing example above turned out to be a false alarm on this machine — GLM-5.2 is a **built-in** Trae model that authenticates via account login and needs no local `models:` provider block at all (`trae-cli models` lists it, and a real run completes successfully, with no `models:` key present in `trae_cli.yaml`). `TraeAdapter.diagnose()` previously checked the static `models:` field before ever consulting the live probe, so it reported `TRAE_MODEL_NOT_CONFIGURED` even when the model demonstrably worked. This has been fixed: `diagnose()` now trusts `is_model_verified_live()` first whenever a model is configured, and only falls back to the `models:` field as a secondary signal when the live probe itself is unavailable. The manual `models:` YAML edit below is only relevant if you are wiring up a **custom** (self-hosted API key) model, not a built-in one.

Manual remediation example:

```powershell
# 1) Edit C:\Users\<you>\.trae\trae_cli.yaml and add a real models: provider entry.
#    The exact provider fields depend on your Trae/GLM provider.

# 2) Make sure the account running skillhub-eval serve can write Trae config.
icacls "$env:USERPROFILE\.trae"
icacls "$env:USERPROFILE\.trae" /grant "$env:USERNAME:(OI)(CI)(M)"
```

## Deployment note: exec preferences are process-global, not per-user

`consent_granted`, `exec_agent`, and `exec_model` are stored as a single global row (`SqliteRepository.get_exec_preferences`/`set_preferences`), not scoped per browser session or user. If multiple people share one running `skillhub-eval serve` instance, one person's agent/model selection and consent affects everyone's next run. **Each person should run their own local `skillhub-eval serve` instance** rather than sharing one process for a multi-user trial.

### Exec Bridge API reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/exec/agents/scan` | Detect local CLI agents |
| GET | `/api/exec/preferences` | `{ exec_source, exec_agent, consent_granted, ready, ready_reason }` |
| PUT | `/api/exec/preferences` | Update `exec_source` / `exec_agent` |
| POST | `/api/exec/consent` | Grant execution consent (global) |
| POST | `/api/exec/agents/{id}/test` | Smoke via `LocalAgentRunner`; optional `{ "model": "..." }` body, used by the UI only for the active agent |

OpenAPI: <http://127.0.0.1:8000/docs> (tag `exec`).

Model discovery note: Cursor is probed with `models` first and `--list-models` as fallback; login or "no models" status text is ignored and falls back to built-in model options.

## Automated E2E (CLI / pytest, skipped by default)

```bash
# Run all three agents against the fixture (skip if CLI missing)
set RUN_LOCAL_AGENT=1
python -m pytest tests/execution/test_e2e_local_exec.py -v
```

Uses env + Python consent (`grant_exec_consent`); does not exercise the web UI.

## Timeout tuning (`.env`)

Judge and local-agent phases use **separate** budgets (2026-06-18). See `.env.example` for names. Demo starting points:

| Variable | Demo value | Phase |
|----------|------------|--------|
| `WORKFLOW_TIMEOUT_HIGH_S` | 1200 | Dual-model judge only |
| `LOCAL_AGENT_WORKFLOW_TIMEOUT_HIGH_S` | 7200 | Local CLI `case_executing` only |
| `PROVIDER_CALL_TIMEOUT_HIGH_RISK_S` | 300 | Per judge LLM call |

Local-execution debugging profile (useful when comparing Cursor/Codex/Trae on the same skill and avoiding 30-minute failed-case waits):

| Variable | Debug value | Purpose |
|----------|-------------|---------|
| `LOCAL_AGENT_WORKFLOW_TIMEOUT_MEDIUM_S` | 900 | Medium-risk local exec wall-clock budget |
| `LOCAL_AGENT_WORKFLOW_TIMEOUT_HIGH_S` | 1200 | High-risk local exec wall-clock budget |
| `LOCAL_AGENT_CASE_TIMEOUT_LOW_S` | 180 | Per low-risk case timeout |
| `LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S` | 240 | Per medium-risk case timeout |
| `LOCAL_AGENT_CASE_TIMEOUT_HIGH_S` | 300 | Per high-risk case timeout |
| `EXEC_CONCURRENCY` | 2 | Parallel local cases; raise only after the selected CLI/model is stable |

Restart `serve` after edits. Future: parallel multi-case local exec — see `RECORD.md` Q-24.

## Full regression (no local agents required)

```bash
python -m pytest tests/ -q
```

## Spot-check queue filter

After a PASS run with local execution, history should expose:

- `spot_check_eligible=1`
- `execution_source_used=local_agent`

API: `GET /api/eval/history?spot_check_only=true&execution_source=local_agent`

History tab: filter chip **local_agent** (C15).

## Consent gate (CLI / fallback)

When not using the UI drawer, local spawn still requires consent:

```python
from skillhub_eval.execution.consent import grant_exec_consent
grant_exec_consent("<skill_id>")
```

Or disable gate: `EXEC_CONSENT_REQUIRED=false`

Web UI path: use **Exec Settings → 我同意本机执行** (`POST /api/exec/consent`) instead.

## Local execution environment check (2026-07-07, runtime productization)

Product-facing term: **本地执行环境检查**. Developer docs may still say *preflight* / *runtime*.

### What「连接测试」means vs environment check

| Action | Proves | Does NOT prove |
|--------|--------|----------------|
| **连接测试** (`POST /api/exec/agents/{id}/test`) | CLI binary resolves, responds to a minimal probe, optional model hint | Current Skill can be read; formal local eval will succeed |
| **本地执行环境检查** (`POST /api/exec/runtimes/{id}/preflight`) | Selected runtime+model can execute a **safe check case** for the **current skill fingerprint** (diagnostic only) | Judge scores, formal eval cases, or that formal local eval is blocked |

UI: Exec Settings Agent cards are the primary entry for **本地执行环境检查**. After a successful ZIP upload / bootstrap, the API returns `staging_path`; the Chat UI caches it and can run the check immediately (no need to wait for补题). The chat header shows an **环境：未检查 / 检查中… / 已通过 / 未通过** status pill when `exec_source=local`; clicking it opens Exec Settings and does **not** POST preflight. Before any check runs, status is **未检查** — never「失败」or「需要生成检查用例」. While a check is in flight, the Agent card and header show **检查中…** and keep the final result after completion (not toast-only). The Exec Settings drawer overlay must not block chat chips such as「确认继续」(overlay `pointer-events-none`, drawer panel `pointer-events-auto`). While awaiting skill-id confirm, internal actions (e.g.「确认继续」) must **not** re-attach a lingering ZIP — otherwise the session remounts and loops on `awaiting_skill_id_confirm`. Clicking **运行环境检查** auto-runs the diagnostic (high-risk may auto-write a lightweight check case; low-risk uses happy_path / synthetic input). A green connection test must not imply formal local evaluation readiness. A failed environment check is a warning only — formal local eval may still proceed and is judged by real case execution.

Optional follow-up (P1): `GET /conversations/{id}/status` always returning `staging_path` so a hard refresh still has a path without relying on the in-memory cache.

### Optional check before formal local eval

The local execution environment check is now an optional diagnostic. Formal local eval does not automatically run it and does not require a passed preflight cache. Real trust is enforced by formal case execution: failed local cases are not judged or scored, and a run where all local cases fail ends as a local-exec failure.

When the user clicks **本地执行环境检查**:

1. The runtime preflight API may auto-generate `eval_cases/runtime_preflight_01.yaml` for **high-risk** bundles without an authored safe case (`ensure_safe_preflight_case_with_provider`).
   - Generation uses a deterministic lightweight template by default; it does **not** call Provider A / LLM.
   - Deterministic validation remains the safety boundary: `type: preflight`, `safe_preflight: true`, environment-check framing, and no real-world buy/sell/payment/delete/send/publish actions.
   - Existing generated heavy/LLM check cases (`origin: runtime_platform_llm`, or generated cases failing validation) are automatically reset to the lightweight template.
   - Low-risk bundles or bundles that already have an authored safe check case do not create a generated check case.
2. Preflight execution uses a dedicated lightweight harness prompt. The agent may read `SKILL.md` and check files/entrypoint visibility, but it is explicitly told not to follow the Skill's formal business workflow, fetch business data, diagnose, or run a full pipeline.
3. `PreflightRunner` runs once and writes/reads the runtime preflight cache.
4. Passed/failed/blocked results are shown as diagnostics. Failed checks do **not** create a formal failed report and do **not** block `case_executing` when the user starts formal local eval.

Preflight cases (`type: preflight`, `safe_preflight: true`) are excluded from formal case counts and judge scoring.

### Manual retry / switch / sample_io fallback

- **重新检查**: `POST /api/exec/runtimes/{id}/preflight` with `force=true`.
- **重置轻量检查**: same endpoint with `regenerate_check_case=true` (replaces only system-generated `runtime_preflight_01.yaml` with the deterministic lightweight template).
- **改用另一个已检查通过的本地工具**: `POST /api/exec/runtimes/switch` — updates SQLite preferences only after verifying `local_check_status=passed` for the current skill fingerprint. The switch should preserve the checked runtime+model pair. Does not auto-switch during a run.
- **使用样例输出评估（非本地真跑）**: set `exec_source=sample_io` via Exec Settings.

`GET /api/exec/agents/scan?skill_bundle_path=...` returns readiness fields: `install_status`, `invocation_status`, `local_check_status`, `can_run_local_check`, `can_switch_and_rerun`, etc.

## UI polling and performance notes (2026-07-08)

During long local-agent runs, avoid making the chat page poll heavy endpoints unnecessarily:

- `pollConversation()` should have a single in-flight request at a time; overlapping polls can make **新对话** and session switching feel unresponsive.
- High-frequency polling should use `/conversations/{id}/status` for run status and `stage_progress`.
- Full messages should be fetched only when `lui_messages_count` changes, when switching conversations, after sending a message, or when a run reaches a terminal state.
- Session list refresh is throttled during background polling (15s by default) and forced only after user actions such as create/select/archive/review.
- While an active run is in a running status, `/conversations/{id}/status` skips bundle re-ingest and case-gate scanning. Complex bundles such as stock-radar should not be re-read every 3s just to update live progress.

If the UI appears stuck:

1. Check the live panel's **最后刷新** timestamp.
2. If it keeps updating, inspect `analytics_events` for `local_agent_case_started` / `local_agent_case_failed` / `local_agent_case_succeeded`; the run may simply be waiting on CLI case timeouts.
3. If the timestamp stops updating or the banner says 状态刷新失败, verify `skillhub-eval serve` is still running and responsive.
4. A terminal DB status of `failed` + `LOCAL_EXEC_ALL_CASES_FAILED` means local execution really failed all cases; refresh the page if the old live panel did not pick up the terminal state.

### Capture and sanitize stream fixtures

1. Save raw CLI stdout lines under `.tmp/raw_runtime_streams/<runtime>.jsonl` (gitignored).
2. Sanitize:

```bash
python scripts/sanitize_runtime_stream.py .tmp/raw_runtime_streams/cursor_agent.jsonl
```

3. Commit output under `tests/fixtures/runtime_streams/`. Sanitizer redacts usernames, absolute paths including Windows paths with spaces/non-ASCII segments, tokens, and truncates long prompts while preserving event shapes.
4. Regression: `pytest tests/execution/test_runtime_stream_fixtures.py -q`

Live CLI E2E remains opt-in (`RUN_LOCAL_AGENT=1`); default pytest must not require installed CLIs.
