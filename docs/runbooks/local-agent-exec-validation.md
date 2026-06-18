# Local Agent Execution Bridge — Manual Validation Runbook

Validate Wave 8 local execution against `testskills/exec-fixture-minimal/`.

## Prerequisites

- Python env with `skillhub_eval` installed (`pip install -e .`)
- At least one CLI agent on `PATH`: `claude`, `codex`, or `cursor-agent`
- `.env` with DeepSeek + Gemini keys (full formal eval still needs LLM judges)
- **`serve` 与 CLI agent 须同机**（服务端 spawn 子进程，非浏览器直连 CLI）

For the **CLI / pytest path** only (optional): set `EXEC_SOURCE=local` and `EXEC_AGENT=claude|codex|cursor-agent`, or grant consent via Python (see [Consent gate](#consent-gate-cli--fallback)).

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
| Scan | **重新扫描** | `GET /api/exec/agents/scan` — lists `claude`, `codex`, `cursor-agent` with PATH/auth hints |
| Mode | Confirm **本地真跑** selected (default) | `PUT /api/exec/preferences` `{ "exec_source": "local" }` (instant save, no Save button) |
| Agent | Select a **detected** radio card | `PUT /api/exec/preferences` `{ "exec_agent": "<id>" }` |
| Consent | Check **我同意本机执行** | `POST /api/exec/consent` |
| Smoke | Click **[Test]** on agent card (optional; works without consent) | `POST /api/exec/agents/{id}/test` — inline pass/fail |

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

See [Spot-check queue filter](#spot-check-queue-filter) for history API verification.

### Exec Bridge API reference

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/exec/agents/scan` | Detect local CLI agents |
| GET | `/api/exec/preferences` | `{ exec_source, exec_agent, consent_granted, ready, ready_reason }` |
| PUT | `/api/exec/preferences` | Update `exec_source` / `exec_agent` |
| POST | `/api/exec/consent` | Grant execution consent (global) |
| POST | `/api/exec/agents/{id}/test` | ~60s smoke via `LocalAgentRunner` |

OpenAPI: <http://127.0.0.1:8000/docs> (tag `exec`).

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
