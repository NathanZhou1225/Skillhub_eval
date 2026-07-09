# Local CLI Runtime Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the productized local CLI runtime platform so non-technical users can run local Skill evaluations without understanding preflight internals.

**Architecture:** Keep the runtime platform strict at the backend boundary, but expose it as an automatic local execution environment check in the product. Generate or select safe check cases before formal local evaluation, surface readiness per runtime, allow only explicit runtime switching, and keep scoring/reporting unchanged.

**Tech Stack:** Python 3, FastAPI, SQLite, existing `skillhub_eval` runtime modules, vanilla JS UI in `skillhub_eval/adapters/ui/static/assets/index.js`, pytest, `node --check`, document encoding guard.

## Global Constraints

- Do not change judge scoring, R1-R8, thresholds, expert review, report aggregation, or `ExecResult` semantics.
- Do not auto-switch runtimes. Switching to another verified runtime must require explicit user action.
- Do not auto-install, login, repair, or mutate third-party CLI configs.
- Do not expose `safe_preflight`, runtime fingerprints, YAML editing, or cache internals to ordinary users.
- Use user-facing Chinese actions such as "改用另一个已检查通过的本地工具" and "使用样例输出评估（非本地真跑）"; keep `runtime` and `sample_io` wording for diagnostics and runbooks only.
- Do not provide a user-facing "ignore check and continue local run" action.
- Readiness UI must split "连接测试" from "当前 Skill 检查"; a successful connection test must not imply formal local evaluation readiness.
- The automatic local execution check must appear as a visible pre-formal-evaluation stage, not a silent background pause.
- Keep preflight diagnostics available in developer logs, runbooks, and event/report evidence.
- Default tests must not require local CLIs, network/model access, quota, or logged-in accounts.
- Live CLI checks remain opt-in and must skip with readable reasons when unavailable.

---

## File Map

- `skillhub_eval/core/ingest.py`: already parses bundle metadata and eval cases. Use its output contract; avoid broad rewrites.
- `skillhub_eval/core/ingest.py`: must keep preflight cases available in `eval_cases` for `PreflightRunner`, but exclude them from formal `n_cases` / case-count semantics.
- `skillhub_eval/core/staging_writer.py`: LUI patch writer for author/assistant-created eval cases.
- `skillhub_eval/core/level0.py`, `skillhub_eval/core/case_sanitizer.py`, `skillhub_eval/core/gaps.py`: formal case completeness and validation boundaries that must exclude `type: preflight`.
- `skillhub_eval/execution/preflight_runner.py`: select authored/generated check cases and run local execution checks.
- `skillhub_eval/execution/harness_prompt.py`: use a dedicated lightweight prompt for `type: preflight` / `safe_preflight` cases.
- `skillhub_eval/core/engine.py`: auto-run local execution check before formal local evaluation blocks.
- `skillhub_eval/execution/preflight_cache.py`, `skillhub_eval/persistence/sqlite.py`: reuse existing cache table; only extend if readiness summaries require new fields.
- `skillhub_eval/adapters/api/routes/exec.py`: expose runtime readiness/check status and explicit switch/retry endpoints if not already present.
- `skillhub_eval/adapters/ui/static/assets/index.js`: runtime readiness cards, local execution check copy, retry/generate/switch actions.
- `tests/core/test_engine.py`, `tests/execution/test_preflight_runner.py`, `tests/adapters/test_exec_bridge_api.py`, UI contract tests if present: regression coverage.
- `docs/runbooks/local-agent-exec-validation.md`, `openspec/specs/skill-execution/spec.md`, `RECORD.md`, `.project_memory/active/SPRINT_phase3-eval-system.md`: docs and closure.

---

### Task 1: Automatic Safe Local Execution Check Case

**Files:**
- Create: `skillhub_eval/execution/safe_preflight_case.py`
- Modify: `skillhub_eval/core/ingest.py`
- Modify: `skillhub_eval/core/staging_writer.py`
- Modify: `skillhub_eval/core/level0.py`
- Modify: `skillhub_eval/core/case_sanitizer.py`
- Modify: `skillhub_eval/core/gaps.py`
- Test: `tests/execution/test_safe_preflight_case.py`

**Interfaces:**
- Produces: `ensure_safe_preflight_case(bundle_path: str | Path) -> dict | None`
- Produces: `build_safe_preflight_case(bundle: dict) -> dict | None`
- Produces: `validate_safe_preflight_candidate(candidate: dict) -> tuple[bool, list[str]]`
- Produces: `fallback_safe_preflight_case(bundle: dict) -> dict`
- Produces: `is_preflight_case(case: dict) -> bool`
- Consumes: `ingest_bundle(str(bundle_path))`
- Contract: generated case has `id: runtime_preflight_01`, `type: preflight`, `safe_preflight: true`, `origin: runtime_platform_template`, and is persisted under `eval_cases/` only when no authored safe case exists. The default product path uses the deterministic lightweight template and does not call an LLM.
- Contract: regeneration must support a force path for product actions like "重置轻量检查"; force regeneration may replace only the generated `runtime_preflight_01.yaml`, never authored eval cases.

- [ ] **Step 1: Write failing tests for generation**

Create tests proving:

- a high-risk stock-radar-like bundle without a safe case receives one generated case
- bundles with authored `safe_preflight: true` are left unchanged
- old generated LLM/heavy check cases are migrated back to the deterministic template
- preflight harness prompts forbid formal business workflow execution
- generated check cases are excluded from formal case counts
- `ingest_bundle()` keeps generated preflight cases in `eval_cases` but excludes them from `n_cases`

Run: `pytest tests/execution/test_safe_preflight_case.py -q`
Expected: FAIL because `skillhub_eval.execution.safe_preflight_case` does not exist.

- [ ] **Step 2: Implement deterministic validator and fallback**

Implement a validator that accepts only candidates with:

- `type == "preflight"`
- `safe_preflight is True`
- non-empty `id`, `user_intent`, `input_template`, `expected_behavior`
- no irreversible or real-world action request terms such as buy/sell/order/payment/delete/send/publish equivalents in Chinese or English
- explicit "environment check only" framing
- high-risk domain disclaimer requirement when applicable

Implement fallback:

```python
def fallback_safe_preflight_case(bundle: dict) -> dict:
    skill_name = str(bundle.get("name") or bundle.get("skill_id") or "当前 Skill")
    return {
        "id": "runtime_preflight_01",
        "type": "preflight",
        "safe_preflight": True,
        "origin": "runtime_platform_template",
        "user_intent": f"仅验证本地执行链路能读取 {skill_name} 指令并返回最小可评估结果，不生成真实业务结论。",
        "input_template": "请仅进行本地执行环境检查：读取当前 Skill 指令，返回最小结构化结果；必须说明这是环境检查，不输出买卖、下单、发送、删除、支付或其他真实业务建议。",
        "expected_behavior": "能读取 Skill 指令并返回符合声明输出要求的最小结果；如 Skill 需要入口脚本，应观察到入口或工具调用证据；输出包含必要免责声明。",
    }
```

- [ ] **Step 3: Implement deterministic builder**

Implement `build_safe_preflight_case(bundle)`:

```python
def build_safe_preflight_case(bundle: dict) -> dict | None:
    risk = str(bundle.get("risk_level_locked") or bundle.get("risk_level_declared") or bundle.get("risk_level") or "low").lower()
    if risk != "high":
        return None
    if any(c.get("safe_preflight") or c.get("type") == "preflight" for c in bundle.get("eval_cases") or []):
        return None
    return fallback_safe_preflight_case(bundle)
```

- [ ] **Step 4: Persist generated case**

Implement `ensure_safe_preflight_case(bundle_path)` so it writes `eval_cases/runtime_preflight_01.yaml` using the repository's existing YAML style. Use UTF-8, avoid whole-file rewrites of unrelated docs, and do not modify authored cases.

Add a `force: bool = False` parameter. When `force=True`, replace only a previously generated `runtime_preflight_01.yaml` whose `origin` starts with `runtime_platform`; refuse to overwrite authored safe cases or unrelated eval case files.

- [ ] **Step 5: Update ingest and formal case counting boundaries**

Modify `skillhub_eval/core/ingest.py` so `eval_cases` still includes authored/generated preflight cases for `PreflightRunner`, but `n_cases` and any formal count field exclude cases where `type == "preflight"` or `safe_preflight is True`.

Then update `level0.py`, `case_sanitizer.py`, and `gaps.py` so case gate, type coverage, malformed handling, and gap count logic exclude preflight cases from formal requirements.

- [ ] **Step 6: Verify generated case is excluded from formal case counts**

Add/adjust tests where case completeness or formal eval case selection ignores `type: preflight`. The generated case must not satisfy or inflate happy/edge/refusal/adversarial requirements.

Run: `pytest tests/core tests/execution/test_safe_preflight_case.py -q -k "preflight or case or gate"`
Expected: PASS.

---

### Task 2: Optional Local Execution Check Diagnostic

**Files:**
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/execution/preflight_runner.py`
- Modify: `skillhub_eval/core/eval_stage_messages.py` or existing stage/message notification path
- Test: `tests/core/test_engine.py`, `tests/execution/test_preflight_runner.py`

**Interfaces:**
- Consumes: `ensure_safe_preflight_case(bundle_path)`
- Consumes: `PreflightRunner.run(skill_bundle_path, runtime_id, model_id, locked_risk_level)`
- Produces: manual/API behavior where the user can run a local execution check and inspect diagnostic results.
- Produces: engine behavior where missing/failed/expired preflight cache does not block formal local evaluation; formal results rely on real case execution.

- [x] **Step 1: Write failing engine tests**

Add a test where local execution is selected, no cache exists, and formal evaluation proceeds into case execution without calling `PreflightRunner.run()`.

Add a second test where a failed/expired preflight cache exists, and the run still enters formal case execution without returning `LOCAL_RUNTIME_PREFLIGHT_REQUIRED`.

Run: `pytest tests/core/test_engine.py -q -k "preflight or local_runtime"`
Expected: PASS after optional-diagnostic implementation (historical note: earlier drafts expected FAIL while the hard gate still existed).

- [x] **Step 2: Implement optional diagnostic path**

In `EvaluationEngine`, remove the formal-eval hard gate:

1. Do **not** call `_ensure_valid_runtime_preflight` (or equivalent) when starting formal local evaluation.
2. Proceed from `normalizing` directly to `case_executing`.
3. Keep `PreflightRunner` / cache / `POST /api/exec/runtimes/{id}/preflight` for **manual** diagnostics only.
4. Manual check may ensure/generate the lightweight template, run the probe, and write cache; failed/blocked results are warnings only.
5. Formal trust: failed local cases are not scored; all-local-failed runs fail with the local execution reason.

Do not run judge providers or formal eval cases during the optional diagnostic.

- [x] **Step 3: Add UI-visible check stage signal**

Manual environment check uses toast / Exec Settings status (and optional chat header button). Formal eval no longer emits an automatic `local_execution_check` stage before `case_executing`.

- [x] **Step 4: Preserve diagnostics**

Manual check and legacy reports may show "本地执行环境检查未通过/未完成" as **diagnostic** copy (not "正式评估已阻止"). Developer fields keep `failure_reason`, `runtime_id`, `model_id`, `checked_at`, and cache evidence.

- [x] **Step 5: Verify**

Run: `pytest tests/core/test_engine.py tests/execution/test_preflight_runner.py -q -k "preflight or local_runtime"`
Expected: PASS.

---

### Task 3: Runtime Readiness Contract

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Modify: `skillhub_eval/execution/detection.py`
- Modify: `skillhub_eval/execution/models.py`
- Modify: `skillhub_eval/execution/preflight_cache.py` if needed
- Test: `tests/adapters/test_exec_bridge_api.py`

**Interfaces:**
- Produces API readiness fields per runtime:
  - `install_status`
  - `invocation_status`
  - `auth_status`
  - `model_status`
  - `capability_status`
  - `local_check_status`
  - `local_check_checked_at`
  - `local_check_expires_at`
  - `local_check_message_zh`
  - `can_run_local_check`
  - `can_switch_and_rerun`

- [ ] **Step 1: Write API tests for readiness states**

Cover installed/missing, auth missing, selected model ok/stale/probe-unavailable, preflight missing/passed/failed/expired, and high-risk check-generatable.

Run: `pytest tests/adapters/test_exec_bridge_api.py -q -k "runtime or readiness or preflight"`
Expected: FAIL for missing readiness fields.

- [ ] **Step 2: Extend scan/readiness response**

Keep `GET /api/exec/agents/scan` compatible, but add runtime readiness fields. If a new runtime endpoint is added, keep the old endpoint as an adapter so current UI does not break.

- [ ] **Step 3: Map technical states to product copy**

Use product wording:

- `local_check_status=missing`: "尚未检查"
- `passed`: "已通过"
- `failed`: "检查失败"
- `expired`: "已过期"
- `blocked`: "需要生成检查用例或修复环境"

- [ ] **Step 4: Verify**

Run: `pytest tests/adapters/test_exec_bridge_api.py -q -k "runtime or readiness or preflight"`
Expected: PASS.

---

### Task 4: Product Runtime Readiness UI

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: UI contract tests if present; always run `node --check`

**Interfaces:**
- Consumes readiness fields from Task 3.
- Produces one card per runtime showing install/auth/model/capability/local execution check status.
- Product copy uses "本地执行环境检查"; "preflight" appears only in debug/detail text.

- [ ] **Step 1: Add card rendering tests or focused fixture checks**

If existing JS tests exist, add fixture coverage for runtime card states. If not, add small pure rendering helper functions and cover them from available UI contract tests.

- [ ] **Step 2: Replace old scan-card emphasis**

Show the user:

- runtime name/model
- install/login/model readiness
- local execution check status and expiry as diagnostics
- primary action: "运行环境检查" / "重新检查" / "重置轻量检查"
- warning copy that failed diagnostics do not block formal local evaluation

- [ ] **Step 3: Fix blocked report UX**

When a legacy report has `LOCAL_RUNTIME_PREFLIGHT_REQUIRED`, explain:

"本地执行环境检查是诊断结果；新版正式评估会以真实 case 执行为准，不再因该检查失败直接阻断。"

For ordinary users, replace raw terms in actions:

- `switch runtime` -> "改用另一个已检查通过的本地工具"
- `sample_io` -> "使用样例输出评估（非本地真跑）"

- [ ] **Step 4: Verify**

Run: `node --check skillhub_eval/adapters/ui/static/assets/index.js`
Expected: no syntax errors.

---

### Task 5: Explicit Switch to Verified Runtime and Rerun

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Modify: `skillhub_eval/execution/preferences.py`
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: `tests/adapters/test_exec_bridge_api.py`, UI check

**Interfaces:**
- Produces endpoint/action that updates local runtime/model preference only after user clicks.
- Consumes readiness list from Task 3 to show only preflight/local-check passed runtimes as switch candidates.
- Does not mutate runtime definitions or automatically switch during a run.
- Prefer a dedicated action such as `POST /api/exec/runtimes/switch` or an equivalent explicit endpoint over silently reusing a generic preferences update, because the API must validate current skill fingerprint readiness before offering switch candidates.

- [ ] **Step 1: Write API tests**

Test that explicit switch updates local preferences and does not change runtime catalog definitions.

- [ ] **Step 2: Implement switch action**

Use existing preference persistence where possible. Return the updated selected runtime/model and a product message.

- [ ] **Step 3: Add UI action**

On a blocked/failed runtime, show "改用已检查通过的 X 重跑" only when another runtime has valid local check pass for the same skill fingerprint.

- [ ] **Step 4: Verify**

Run: `pytest tests/adapters/test_exec_bridge_api.py -q -k "switch or preference or runtime"`
Run: `node --check skillhub_eval/adapters/ui/static/assets/index.js`
Expected: PASS.

---

### Task 6: Real Stream Fixture and Sanitizer Foundation

**Files:**
- Create: `scripts/sanitize_runtime_stream.py`
- Create/modify: `tests/fixtures/runtime_streams/`
- Test: `tests/execution/test_runtime_stream_fixtures.py`

**Interfaces:**
- Produces CLI:
  - input: `.tmp/raw_runtime_streams/<runtime>.jsonl`
  - output: `tests/fixtures/runtime_streams/<runtime>_fixture.jsonl`
- Sanitizer removes usernames, absolute paths, tokens, long prompt text, and unrelated transcript content while preserving event shape.

- [ ] **Step 1: Add sanitizer unit tests**

Use synthetic raw stream containing username, absolute Windows path, fake token, long prompt, and tool event shape. Expected fixture keeps event fields needed by normalizers and replaces sensitive fields.

- [ ] **Step 2: Implement sanitizer**

Support JSONL and plain text fallback. Do not require network or real CLI.

- [ ] **Step 3: Wire fixture parser tests**

Codex/Cursor/Trae fixtures can use existing known real shapes. Claude/Antigravity can start with sanitized minimal fixture once captured; until then, tests should document skip/xfail boundary rather than pretending live coverage exists.

- [ ] **Step 4: Verify**

Run: `pytest tests/execution -q -k "fixture or sanitize or adapter"`
Expected: PASS or documented skips for missing live captures.

---

### Task 7: Docs, Runbook, Spec Sync, and Archive Readiness

**Files:**
- Modify: `docs/runbooks/local-agent-exec-validation.md`
- Modify: `openspec/specs/skill-execution/spec.md` during archive/sync
- Modify: `RECORD.md`
- Modify: `.project_memory/active/SPRINT_phase3-eval-system.md`
- Modify: `openspec/changes/local-cli-runtime-platform/tasks.md`

**Interfaces:**
- Produces user-facing runbook language: "本地执行环境检查".
- Keeps developer-facing appendix for preflight cache, fingerprint, SQLite, and raw stream sanitizer.

- [ ] **Step 1: Update runbook**

Add:

- what Test means
- what local execution environment check means
- why high-risk skills need a safe system check
- how auto-generation works
- how to retry/check/switch runtime
- how to capture and sanitize streams

- [ ] **Step 2: Sync OpenSpec main spec after implementation**

Do this only after tests and user acceptance. Use the accepted delta requirements from `openspec/changes/local-cli-runtime-platform/specs/skill-execution/spec.md`.

- [ ] **Step 3: Update RECORD and Sprint**

Add a short status entry. Do not duplicate the full task checklist into `RECORD.md`.

- [ ] **Step 4: Run docs guard**

Run: `python scripts/check_doc_encoding.py`
Expected: `doc encoding OK`.

- [ ] **Step 5: Archive change**

Only archive after:

- offline tests pass
- user completes website live test
- live feedback is handled or recorded as future work
- OpenSpec tasks are accurately checked

---

## Verification Set

Run after implementation:

```powershell
& '.tmp\test-venv\Scripts\python.exe' -m pytest tests\execution tests\core tests\adapters\test_exec_bridge_api.py -q --basetemp .tmp\pytest-runtime-productization
node --check skillhub_eval\adapters\ui\static\assets\index.js
& '.tmp\test-venv\Scripts\python.exe' scripts\check_doc_encoding.py
```

Manual website test after offline verification:

1. Upload high-risk stock-radar skill.
2. Select local runtime Trae / GLM-5.2.
3. Start formal local evaluation without manually editing eval cases.
4. Confirm UI shows automatic "本地执行环境检查".
5. Confirm generated check passes or fails with a human-readable reason.
6. Confirm formal `case_executing` starts only after the check passes.
7. Confirm blocked report offers retry/check/switch actions.

---

## Archive Criteria

Archive `openspec/changes/local-cli-runtime-platform` only after all of the following are true:

- Automatic local execution check generation, deterministic template fallback, old heavy/LLM check migration, persistence, and exclusion from scoring are implemented.
- The default product path does not call Provider A / LLM for preflight generation; authored safe preflight cases remain silently compatible.
- Preflight execution uses a dedicated lightweight harness prompt and does not instruct the local agent to run the Skill's formal business workflow.
- Formal local evaluation automatically runs the local execution check before local case execution and blocks without a bypass when the check fails.
- Runtime readiness UI splits connection test and current Skill check status.
- Failed checks show non-technical recovery actions: retry check, regenerate check case, switch to another checked local tool, or use sample outputs with explicit "not local real run" wording.
- Explicit switch updates local preferences only after user action and never auto-switches during a run.
- Explicit switch preserves the checked runtime+model pair, instead of forcing `default`.
- Offline tests pass for execution/core/API/UI, and document encoding guard passes.
- Website live validation covers Trae, Cursor Agent, and Codex, either passing or producing an explained product-readable failure.
- Claude and Antigravity live coverage may remain documented gaps if the local machine lacks working CLI conditions, provided fixture/sanitizer mechanisms exist for future capture.
- Runbook, main spec sync, RECORD, and Sprint are updated.
- Sanitizer redacts Windows absolute paths with spaces and non-ASCII segments before fixtures enter Git.

---

## Self-Review

- Spec coverage: covers OpenSpec tasks 2.1-2.4, 5.6-5.8, 7.1, 7.3, 7.4, 7.6, 7.7, 8.1-8.3, and 9.1-9.5.
- Non-goals preserved: no scoring changes, no auto-switching, no CLI install/repair mutation.
- Main residual dependency: Claude/Antigravity live fixtures require real CLI access and may remain documented until the user can run those environments.
