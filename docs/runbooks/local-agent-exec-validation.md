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
- If **every** case in the run fails local execution, or no usable local agent was detected at all, the whole run is finalized as `status=failed` with `reason_codes` including `LOCAL_EXEC_UNAVAILABLE` (no agent) or `LOCAL_EXEC_ALL_CASES_FAILED` (agent ran but every case failed). No report is produced pretending the run passed.
- One exception: `redline_no_hardened_profile` (an agent without a hardened execution profile hitting a redline/adversarial case) is a **deliberate** design degrade, not a failure — it still substitutes `sample_io` for that specific case, by spec.

**How to read why a run/case failed:**

- Report (`EvaluationReport`): `exec_agent_label`/`exec_model_label` are only non-null when a case actually executed successfully via `local_agent`. `exec_requested_agent_label`/`exec_requested_model_label` always show what the user's preferences pointed at, whether or not it actually ran — so a report can never claim an agent "ran" when it didn't.
- Per-case: `CaseScoreRow.exec_status`/`exec_degrade_reason` (surfaced in the UI as a red "本地执行未完成" badge with a Chinese reason on hover).
- Event log: every local-agent failure is persisted as a `local_agent_failure` analytics event (`case_id`, `degrade_reason`, a bounded `stderr_excerpt`), queryable via `SqliteRepository.log_event`/the `analytics_events` table even after the report UI is closed.
- UI: `formatScoreDisplay`/`formatScoreCompact` render `LOCAL_EXEC_UNAVAILABLE`/`LOCAL_EXEC_ALL_CASES_FAILED` as a red "本地执行阻断" badge instead of a score.

**Real-machine confirmation (2026-07-01):** a fresh run against Trae/GLM-5.2 (`run_id=9f5ff946-...`) produced `status=failed`, `reason_codes=['LOCAL_EXEC_ALL_CASES_FAILED']`, `exec_agent_label=None` (not claimed as executed), `exec_requested_agent_label=Trae`. All 5 cases logged `local_agent_failure` events with `degrade_reason=run_incomplete` (streamed output never reached its end marker). **The specific reason `trae-cli` produces `run_incomplete` on this machine is not yet root-caused** — that is tracked as a follow-up backlog item, not fixed by this change.

**If you want `sample_io` scoring instead of blocking on local failure:** switch `exec_source` to `sample_io` in **Exec Settings** and re-run. There is intentionally no "run anyway with sample data" button in the moment of a blocked run — that would reintroduce the "looks like it ran, actually didn't" ambiguity this change removes.

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
