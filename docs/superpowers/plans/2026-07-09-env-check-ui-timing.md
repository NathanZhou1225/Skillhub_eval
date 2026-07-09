# Env-Check UI Timing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** After ZIP/bootstrap mounts a Skill, the Chat UI immediately knows `staging_path`, shows「运行环境检查」in Exec Settings, and turns the header into a status pill that opens Exec Settings — without blocking formal eval.

**Architecture:** Backend returns `staging_path` on successful ZIP/bootstrap responses. Frontend caches it per `conversation_id`, prioritizes it in `getActiveSkillBundlePath()`, refreshes agent scan, and adjusts Agent-card / header / report-card UI per `docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md`.

**Tech Stack:** FastAPI + Pydantic, Vanilla JS Chat UI (`index.js` / `index.html`), pytest + TestClient UI contract tests.

**Spec:** `docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md`

**Status:** Implemented (2026-07-09) — plan tasks complete; user confirmed in browser. Hotfixes after plan: confirm-ZIP ignore, readiness `missing` semantics, progress UI, drawer pointer-events. Design Status=Implemented (beyond original Approved).

---

## File map

| File | Responsibility |
|------|----------------|
| `skillhub_eval/adapters/api/routes/chat.py` | Add `staging_path` to `ChatResponse`; set on successful ZIP mount paths |
| `skillhub_eval/adapters/api/routes/conversations.py` | Add `staging_path` to `BootstrapResponse`; set on successful bootstrap mount paths |
| `skillhub_eval/adapters/ui/static/assets/index.js` | Path cache, path priority, post-upload scan, Agent-card button rules, header B3, remove report-card button |
| `skillhub_eval/adapters/ui/static/index.html` | Header control: button → status pill |
| `tests/adapters/test_chat_wave5.py` | Assert ZIP chat response includes `staging_path` |
| `tests/adapters/test_conversations_wave5.py` | Assert bootstrap response includes `staging_path` |
| `tests/api/test_ui.py` | UI contract strings for cache / B3 / no report-card button |
| `docs/runbooks/local-agent-exec-validation.md` | One-liner: upload then check in Exec Settings |
| `docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md` | Mark Status Approved after plan lands |

---

### Task 1: API — `ChatResponse.staging_path` on ZIP success

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/chat.py`
- Test: `tests/adapters/test_chat_wave5.py`

- [x] **Step 1: Write the failing test**

In `tests/adapters/test_chat_wave5.py`, extend the existing ZIP upload test (the one that asserts `bootstrap_status == "awaiting_skill_id_confirm"`) so the body also asserts staging path:

```python
    body = resp.json()
    assert body["bootstrap_status"] == "awaiting_skill_id_confirm"
    staging = body.get("staging_path")
    assert staging
    assert conv_id in str(staging).replace("\\", "/")
    assert Path(staging).is_dir()
```

Add `from pathlib import Path` if missing. Keep the existing `staging_root` monkeypatch so the path is under `tmp_path`.

Also add / extend the explicit-skill-id ZIP test similarly:

```python
    body = resp.json()
    assert body.get("staging_path")
    assert conv_id in str(body["staging_path"]).replace("\\", "/")
```

- [x] **Step 2: Run test to verify it fails**

```powershell
pytest tests/adapters/test_chat_wave5.py::test_chat_zip_upload_awaits_skill_id_confirm -v
```

(Use the actual test function name in that file for the awaiting-confirm ZIP case.)

Expected: FAIL — `staging_path` missing / `None`.

- [x] **Step 3: Minimal implementation**

In `skillhub_eval/adapters/api/routes/chat.py`:

1. Add field to `ChatResponse`:

```python
class ChatResponse(BaseModel):
    reply: str
    intent: str
    new_run_id: str | None = None
    auto_confirmed: bool = False
    gap_zero: bool = False
    bootstrap_status: str | None = None
    activity_phase: str | None = None
    staging_path: str | None = None
```

2. In `_handle_chat_zip_bootstrap`, after a successful `_mount_staging_for_bootstrap` (and on every successful return that still has a mounted tree — including `awaiting_skill_id_confirm`, deferred propagation, and `accepted`), pass `staging_path=str(staging_path)`.

Do **not** set `staging_path` on mount failure (`bootstrap_status="failed"` before mount succeeds).

Example for the confirm-awaiting return:

```python
        return ChatResponse(
            reply=confirm_text,
            intent="explain_only",
            bootstrap_status="awaiting_skill_id_confirm",
            staging_path=str(staging_path),
        )
```

Apply the same `staging_path=str(staging_path)` to the other success returns in that function (deferred / accepted / explicit start).

- [x] **Step 4: Run tests to verify they pass**

```powershell
pytest tests/adapters/test_chat_wave5.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/api/routes/chat.py tests/adapters/test_chat_wave5.py
git commit -m "feat(api): return staging_path on chat ZIP bootstrap success"
```

---

### Task 2: API — `BootstrapResponse.staging_path`

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/conversations.py`
- Test: `tests/adapters/test_conversations_wave5.py`

- [x] **Step 1: Write the failing test**

In `tests/adapters/test_conversations_wave5.py`, pick an existing successful bootstrap test (e.g. `test_bootstrap_auto_identify_requires_confirm` or explicit skill_id). After `assert resp.status_code == 202`, add:

```python
    body = resp.json()
    assert body.get("staging_path")
    assert conversation_id in str(body["staging_path"]).replace("\\", "/")
```

(Use the local `conv_id` / `conversation_id` variable name from that test.)

- [x] **Step 2: Run test to verify it fails**

```powershell
pytest tests/adapters/test_conversations_wave5.py::test_bootstrap_auto_identify_requires_confirm -v
```

Expected: FAIL — missing `staging_path`.

- [x] **Step 3: Minimal implementation**

In `conversations.py`:

```python
class BootstrapResponse(BaseModel):
    conversation_id: str
    run_id: str | None = None
    status: str
    skill_id: str | None = None
    skill_id_source: str | None = None
    security_status: str | None = None
    security_findings: list[dict] = []
    propagator_used: bool = False
    propagator_fallback: bool = False
    propagation_deferred: bool = False
    staging_path: str | None = None
```

In `bootstrap_conversation`, every successful return after `_mount_staging_for_bootstrap` (including `awaiting_skill_id_confirm`, deferred, accepted) must include `staging_path=str(staging_path)`.

- [x] **Step 4: Run tests**

```powershell
pytest tests/adapters/test_conversations_wave5.py -q
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/api/routes/conversations.py tests/adapters/test_conversations_wave5.py
git commit -m "feat(api): return staging_path on conversation bootstrap success"
```

---

### Task 3: Frontend — staging path cache + `getActiveSkillBundlePath` priority

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: `tests/api/test_ui.py`

- [x] **Step 1: Write the failing UI contract test**

Add to `tests/api/test_ui.py`:

```python
def test_ui_caches_staging_path_from_bootstrap():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "_stagingPathByConversation" in text
    assert "rememberStagingPath" in text
    assert "getActiveSkillBundlePath" in text
    # Priority: cache before hidden input / message payload
    cache_idx = text.find("_stagingPathByConversation")
    fn_idx = text.find("function getActiveSkillBundlePath")
    assert cache_idx != -1 and fn_idx != -1
    # Function body must read cache first
    body = text[fn_idx : fn_idx + 800]
    assert "getCachedStagingPath" in body or "_stagingPathByConversation" in body
    assert body.find("getCachedStagingPath") < body.find("inp-bundle-path") or (
        "_stagingPathByConversation" in body and "inp-bundle-path" in body
    )
```

- [x] **Step 2: Run test to verify it fails**

```powershell
pytest tests/api/test_ui.py::test_ui_caches_staging_path_from_bootstrap -v
```

Expected: FAIL — symbols missing.

- [x] **Step 3: Implement cache helpers + path priority**

Near other module-level state in `index.js` (around `_activeConversationId`):

```javascript
const _stagingPathByConversation = Object.create(null);

function getCachedStagingPath(conversationId = _activeConversationId) {
  if (!conversationId) return '';
  return String(_stagingPathByConversation[conversationId] || '').trim();
}

function rememberStagingPath(conversationId, stagingPath) {
  const path = String(stagingPath || '').trim();
  if (!conversationId || !path) return;
  _stagingPathByConversation[conversationId] = path;
}
```

Replace `getActiveSkillBundlePath`:

```javascript
function getActiveSkillBundlePath() {
  const cached = getCachedStagingPath();
  if (cached) return cached;
  const inp = document.getElementById('inp-bundle-path');
  const fromInput = inp && inp.value ? inp.value.trim() : '';
  if (fromInput) return fromInput;
  const messages = Array.isArray(_messagesCache) ? _messagesCache : [];
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const payload = messages[i].payload_json || messages[i].payload || {};
    if (payload.skill_bundle_path) return payload.skill_bundle_path;
  }
  return '';
}
```

In `sendConversationMessage`, after a successful `apiFetch` that returns `chatResp`, before/alongside `pollConversation`:

```javascript
    if (chatResp?.staging_path && _activeConversationId) {
      rememberStagingPath(_activeConversationId, chatResp.staging_path);
      await fetchExecScan(true);
      updateChatLocalCheckButton();
      renderExecAgentCards();
    }
```

When switching conversations (`selectConversation` / equivalent that sets `_activeConversationId`), call `updateChatLocalCheckButton()` and `renderExecAgentCards()` so the new session’s cached path applies. Do **not** clear other conversations’ cache entries on switch.

- [x] **Step 4: Run UI contract test**

```powershell
pytest tests/api/test_ui.py::test_ui_caches_staging_path_from_bootstrap -v
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/ui/static/assets/index.js tests/api/test_ui.py
git commit -m "feat(ui): cache staging_path after ZIP/bootstrap for env check"
```

---

### Task 4: Frontend — Agent card: always show check control when path + detected

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js` (`renderExecAgentCards`)
- Test: `tests/api/test_ui.py`

Spec rules:
- Show「运行环境检查」when Agent `detected` **and** session has a known skill path.
- If `can_run_local_check === false`, show **disabled** button + short reason (or「重置轻量检查」if that path already exists) — **do not hide** the button when path is ready.
- Status line: with path → never silent blank; without path →「上传 ZIP 后可检查当前 Skill」.

- [x] **Step 1: Write failing contract assertions**

```python
def test_ui_env_check_button_visible_when_path_ready():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "上传 ZIP 后可检查当前 Skill" in text
    # Must not require can_run_local_check to emit the button markup
    assert "运行环境检查" in text
    fn_idx = text.find("function renderExecAgentCards")
    assert fn_idx != -1
    # Look at checkBtn construction region
    region = text[fn_idx : fn_idx + 4500]
    assert "can_run_local_check" in region
    assert "disabled" in region
    assert "上传 ZIP 后可检查当前 Skill" in region
```

- [x] **Step 2: Run to verify fail / then implement**

Replace the `localCheckLine` / `checkBtn` block in `renderExecAgentCards` roughly with:

```javascript
    const skillPath = getActiveSkillBundlePath();
    const localCheckLine = !skillPath
      ? '<div class="mt-1 text-[11px] text-gray-400">上传 ZIP 后可检查当前 Skill</div>'
      : (agent.local_check_status && agent.local_check_status !== 'not_applicable'
        ? `<div class="mt-1 text-[11px] text-indigo-800 bg-indigo-50 border border-indigo-100 rounded px-2 py-1">
             <span class="font-medium">当前 Skill 检查：</span>${escapeHtml(formatLocalCheckStatus(agent))}
             ${agent.local_check_message_zh ? `<span class="text-indigo-600"> — ${escapeHtml(agent.local_check_message_zh)}</span>` : ''}
           </div>`
        : '<div class="mt-1 text-[11px] text-gray-500">当前 Skill 检查：尚未检查（可选诊断）</div>');

    let checkBtn = '';
    if (skillPath && detected) {
      if (agent.can_run_local_check) {
        checkBtn = `<button type="button" class="shrink-0 text-xs px-2 py-1 border border-indigo-300 text-indigo-800 hover:bg-indigo-50"
          onclick="event.stopPropagation(); runLocalExecutionCheck('${escapeHtml(agent.id)}')">
          ${agent.local_check_status === 'passed' ? '重新检查' : '运行环境检查'}
        </button>`;
      } else {
        const blockedHint = escapeHtml(agent.local_check_message_zh || '当前无法自动生成检查用例');
        checkBtn = `<button type="button" disabled title="${blockedHint}"
          class="shrink-0 text-xs px-2 py-1 border border-gray-200 text-gray-400 cursor-not-allowed">
          运行环境检查
        </button>`;
      }
    }
```

Keep existing「重置轻量检查」elsewhere if already present; do not remove it.

- [x] **Step 3: Run tests**

```powershell
pytest tests/api/test_ui.py::test_ui_env_check_button_visible_when_path_ready -v
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add skillhub_eval/adapters/ui/static/assets/index.js tests/api/test_ui.py
git commit -m "fix(ui): keep env-check button visible when staging path is ready"
```

---

### Task 5: Header B3 — status pill opens Exec Settings

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/index.html`
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: `tests/api/test_ui.py`

- [x] **Step 1: Update failing contract for header**

Replace / rewrite `test_ui_exposes_chat_local_execution_check_button` to match B3:

```python
def test_ui_exposes_chat_local_execution_check_button():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "chat-local-check-btn" in text
    assert "环境：" in text or "环境：未检查" in text
    assert "openExecSettingsDrawer" in text
    assert "updateChatLocalCheckButton" in text
    assert "仅诊断，不阻断正式评估" in text
    # Header must NOT directly call runLocalExecutionCheck as primary action
    html = client.get("/ui/index.html").text  # if _ui_page already inlines JS, use combined text
    # Prefer asserting the button onclick opens drawer:
    assert "openExecSettingsFromLocalCheckStatus" in text or (
        'id="chat-local-check-btn"' in text and "openExecSettingsDrawer" in text
    )
```

Adjust assertions to whatever helper name you introduce; keep them exact.

- [x] **Step 2: Change HTML control**

In `index.html`, replace the header button with a status control:

```html
            <button id="chat-local-check-btn" type="button" onclick="openExecSettingsFromLocalCheckStatus()"
              class="hidden text-xs px-2 py-1 border border-gray-300 text-gray-700 bg-white hover:bg-gray-50"
              title="打开执行设置查看本地执行环境检查（仅诊断，不阻断正式评估）">
              环境：未检查
            </button>
```

- [x] **Step 3: Implement JS**

```javascript
function getSelectedAgentLocalCheckStatus() {
  const agentId = getSelectedExecAgentForAction?.() || getSelectedExecAgent();
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const agent = agents.find((a) => a.id === agentId);
  return agent?.local_check_status || '';
}

function openExecSettingsFromLocalCheckStatus() {
  openExecSettingsDrawer();
  document.getElementById('exec-local-settings')?.scrollIntoView?.({ block: 'nearest' });
}

function updateChatLocalCheckButton() {
  const btn = document.getElementById('chat-local-check-btn');
  if (!btn) return;
  const shouldShow = getExecSource() === 'local';
  btn.classList.toggle('hidden', !shouldShow);
  btn.disabled = false;
  const status = getSelectedAgentLocalCheckStatus();
  let label = '环境：未检查';
  if (!getActiveSkillBundlePath()) label = '环境：未检查';
  else if (status === 'passed') label = '环境：已通过';
  else if (status === 'failed' || status === 'blocked') label = '环境：失败';
  else if (status === 'expired') label = '环境：已过期';
  else label = '环境：未检查';
  btn.textContent = label;
  btn.title = '打开执行设置 · 本地执行环境检查为可选诊断，不阻断正式评估';
}
```

Remove any header path that calls `runLocalExecutionCheck(...)` directly.

Call `updateChatLocalCheckButton()` after `fetchExecScan` / `runLocalExecutionCheck` success so the pill updates.

- [x] **Step 4: Run tests**

```powershell
pytest tests/api/test_ui.py::test_ui_exposes_chat_local_execution_check_button -v
```

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/ui/static/index.html skillhub_eval/adapters/ui/static/assets/index.js tests/api/test_ui.py
git commit -m "feat(ui): header env status pill opens exec settings"
```

---

### Task 6: Remove report-card env-check button (R2)

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js` (`renderExecAttributionCard`)
- Test: `tests/api/test_ui.py`

- [x] **Step 1: Write contract test**

```python
def test_ui_report_card_has_no_env_check_button():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    fn_idx = text.find("function renderExecAttributionCard")
    assert fn_idx != -1
    region = text[fn_idx : fn_idx + 1200]
    assert "运行环境检查" not in region
    assert "runRuntimePreflightFromDetail" not in region
```

- [x] **Step 2: Implement**

Simplify `renderExecAttributionCard` — keep attribution copy, drop `preflightButton` entirely:

```javascript
function renderExecAttributionCard(d) {
  const report = getReportPayload(d);
  const agentLabel = report.exec_agent_label;
  const requestedAgentLabel = report.exec_requested_agent_label;
  if (!agentLabel && !requestedAgentLabel) return '';
  if (agentLabel) {
    return `<div class="mt-2 text-xs text-emerald-800 bg-emerald-50 border border-emerald-200 rounded px-2 py-1">
      本地执行：<strong>${escapeHtml(agentLabel)}</strong> / ${escapeHtml(report.exec_model_label || '默认模型')} — 本次已成功执行
    </div>`;
  }
  return `<div class="mt-2 text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-2 py-1">
    已选择 <strong>${escapeHtml(requestedAgentLabel)}</strong> / ${escapeHtml(report.exec_requested_model_label || '默认模型')}，但本次未成功执行（详见下方失败原因）
  </div>`;
}
```

If `runRuntimePreflightFromDetail` becomes unused, leave the function in place only if other callers exist; otherwise remove dead helper in the same commit (grep first).

- [x] **Step 3: Run tests**

```powershell
pytest tests/api/test_ui.py::test_ui_report_card_has_no_env_check_button -v
```

Expected: PASS.

- [x] **Step 4: Commit**

```bash
git add skillhub_eval/adapters/ui/static/assets/index.js tests/api/test_ui.py
git commit -m "fix(ui): remove env-check button from report attribution card"
```

---

### Task 7: Runbook + design status + regression

**Files:**
- Modify: `docs/runbooks/local-agent-exec-validation.md`
- Modify: `docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md` (Status → Implemented)
- Verify: pytest suites above + encoding check

- [x] **Step 1: Patch runbook**

In the section「What「连接测试」means vs environment check」, replace the chat-header paragraph with:

```markdown
UI: Exec Settings Agent cards are the primary entry for **本地执行环境检查**. After a successful ZIP upload / bootstrap, the API returns `staging_path`; the Chat UI caches it and can run the check immediately (no need to wait for补题). The chat header shows an **环境：未检查 / 检查中… / 已通过 / 未通过** status pill when `exec_source=local`; clicking it opens Exec Settings and does **not** POST preflight. A green connection test must not imply formal local evaluation readiness. A failed environment check is a warning only — formal local eval may still proceed and is judged by real case execution.
```

- [x] **Step 2: Mark design Approved**

In the design doc header: `Status: Implemented` (user-confirmed).

- [x] **Step 3: Full verification**

```powershell
pytest tests/adapters/test_chat_wave5.py tests/adapters/test_conversations_wave5.py tests/api/test_ui.py -q
python scripts/check_doc_encoding.py docs/runbooks/local-agent-exec-validation.md docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md docs/superpowers/plans/2026-07-09-env-check-ui-timing.md
```

Expected: all green; encoding OK.

- [x] **Step 4: Manual smoke (serve already on :8000 — restart after code change)**

1. New conversation → upload a Skill ZIP.
2. Open Exec Settings → local source → detected Agent shows「运行环境检查」**before**补题 finishes.
3. Header shows「环境：未检查」; click opens drawer; does not toast a preflight run by itself.
4. Run check → card/header show 检查中… then 已通过/未通过; start formal eval still reaches `case_executing` even if check failed.
5. Report attribution card has no「运行环境检查」button.

- [x] **Step 5: Commit docs**

```bash
git add docs/runbooks/local-agent-exec-validation.md docs/superpowers/specs/2026-07-09-env-check-ui-timing-design.md docs/superpowers/plans/2026-07-09-env-check-ui-timing.md
git commit -m "docs: approve env-check UI timing and update runbook entry"
```

---

## Self-review

| Spec requirement | Task |
|------------------|------|
| ZIP success → immediately checkable | 1–4 |
| Main entry = Exec Settings Agent card | 4 |
| Header B3 status → open settings | 5 |
| P2 `staging_path` + cache + scan | 1–3 |
| Report card R2 remove button | 6 |
| Optional diagnostic / no formal block | unchanged backend gate; runbook Task 7 |
| Non-goals (hard gate, canary, P3 guess) | not in plan |

Placeholder scan: no TBD / “similar to Task N” without code.  
Type consistency: field name is always `staging_path` (string); helpers `rememberStagingPath` / `getCachedStagingPath` / `getActiveSkillBundlePath`.

---

## Out of this plan (follow-ups)

- P1: `GET /conversations/{id}/status` always returns `staging_path` for refresh survival
- P3: frontend hard-guess `data/staging/<id>`
- Weak pre-eval reminder modal
