# Trae 完成态判定收尾 + 全 Agent 模型就绪诊断 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the reason a local CLI agent's *selected model* fails to run a skill evaluation legible for all agents (config vs. permission vs. CLI-unresponsive vs. never-verified), not just Trae — and let the "Test" button actually validate the selected model instead of only proving the CLI starts.

**Architecture:** Three layers. (1) A parser/runner fix so a genuinely failed Trae run is reported immediately instead of falling through to the timeout path (already implemented, this plan only verifies it). (2) A shared, bug-fixed `is_model_verified_live()` helper in `models.py` that both a Trae-specific `diagnose()` and a generic, scan-level `selected_model_status` (covering every agent, not just Trae) build on. (3) A model-aware variant of the existing agent smoke-test endpoint, so clicking "Test" on the currently-selected agent actually exercises the currently-selected model, while every other (non-active) agent card keeps the original "never leak one agent's model into another's test" protection.

**Tech Stack:** Python 3.14, FastAPI, pytest, pyyaml (already a dependency), vanilla JS (no build step) for the UI card.

---

## Context You Need

- This plan continues the **already-open, not-yet-archived** OpenSpec change `openspec/changes/local-agent-trial-hardening/`. Read `design.md`'s "Q-29 Follow-up" section (D7–D9) **and** "Q-29 Round 2: Independent Codex Review Findings" section (D10–D12) and `tasks.md`'s section "8." before starting — they contain the decisions this plan implements, including one **confirmed bug fix** (D10) found by an independent review of an earlier draft of this same plan. Do not re-litigate any of D1–D12; they are settled.
- **Task 1 below is largely already done** in the working tree (uncommitted) by a previous session: `skillhub_eval/execution/stream_parser.py`, `skillhub_eval/execution/runner.py`, `skillhub_eval/execution/adapters/trae.py`, and matching tests already contain the `is_error` detection fix and the `-c model.name=` argument fix. Your job for Task 1 is to **verify** this is complete and regression-free, not to re-implement it. If you find it's missing (e.g. a fresh checkout), implement exactly what Task 1 describes.
- Root cause on the reference test machine (already diagnosed, do not re-investigate): `~/.trae/trae_cli.yaml` only contains `model: {name: GLM-5.2}` with no `models:` provider block, so trae-cli itself refuses to run. This is the **user's local environment**, not application code — you are not fixing this file. Your job is only to make SkillHub detect and explain this condition, for Trae specifically and (via the generic status) for every other agent.
- `trae-cli doctor` is known to hang for 40+ seconds with no output on the reference machine — never shell out to it. Everything in this plan uses either direct file reads or the already-proven-bounded `trae-cli models` probe (via `discover_models()`, timeout `settings.model_discovery_timeout_s`, default 6s).
- **D10 is the most important fix in this plan.** An earlier draft's `TRAE_MODEL_NOT_IN_LIST` check was dead code because `discover_models(agent, stored_model=X)` silently re-appends `X` into its own result when `X` isn't found live — so "X not in the result" can never be true. The earlier draft's own unit test didn't catch this because it mocked out `discover_models` entirely, hiding the exact function whose internal behavior caused the bug. Task 4 below fixes this at the source with a shared helper, and includes a regression test that exercises the *real* `discover_models()` (mocking only the subprocess-level `_run_probe`) specifically so this class of bug can't silently return.

---

## Task 1: Verify the already-written stream-json completion fix

**Files:**
- Verify (no changes expected): `skillhub_eval/execution/stream_parser.py`, `skillhub_eval/execution/runner.py`, `skillhub_eval/execution/adapters/trae.py`
- Verify (no changes expected): `tests/execution/test_stream_parser.py`, `tests/execution/test_runner.py`, `tests/execution/test_adapter_trae.py`, `tests/execution/test_local_agent_source_trae.py`
- Verify (no changes expected): `skillhub_eval/core/schemas/report.py`

- [ ] **Step 1: Confirm the current state matches the expected fix**

Open `skillhub_eval/execution/stream_parser.py` and confirm the `result`/`turn.completed` branch looks like this (already present):

```python
elif event_type in ("result", "turn.completed"):
    if event.get("is_error") or event.get("subtype") == "error_during_execution":
        is_error = True
        raw_error = event.get("error") or event.get("message")
        if isinstance(raw_error, str) and raw_error:
            error_text = raw_error
    else:
        is_complete = True
```

Open `skillhub_eval/execution/runner.py` and confirm `is_run_complete` looks like this (already present):

```python
def is_run_complete(self, outcome: RunOutcome) -> bool:
    """Stream-json completion is authoritative (Codex may be killed after turn.completed)."""
    parsed = outcome.parsed_stream
    return parsed is not None and parsed.is_complete and not parsed.is_error
```

Open `skillhub_eval/execution/adapters/trae.py` and confirm `build_args` uses `-c model.name=` (not `--model`):

```python
if self.model:
    args.extend(["-c", f"model.name={self.model}"])
```

If any of these three do not match, implement them exactly as shown before continuing — do not proceed to Task 2 with a broken Task 1.

- [ ] **Step 2: Run the full test suite**

Run: `pytest tests/ -q`

Expected: All tests pass except a known pre-existing baseline of 9 failures unrelated to this change (documented in `RECORD.md`'s 2026-07-01 entries): sqlite `PRAGMA user_version` migration-version assertions expecting `10` where the DB is now at a later version, and one UI-contract test (`test_readiness_payload_contract.py::test_index_html_reads_flat_readiness_and_plan_fields`) with a pre-existing token drift. If you see **any other** failure, stop and investigate before continuing — do not paper over a new regression.

- [ ] **Step 3: Commit (only if Step 1 required changes)**

If Step 1 was a no-op verification, skip this commit. If you had to implement missing pieces, commit them:

```bash
git add skillhub_eval/execution/stream_parser.py skillhub_eval/execution/runner.py skillhub_eval/execution/adapters/trae.py tests/execution/test_stream_parser.py tests/execution/test_runner.py tests/execution/test_adapter_trae.py
git commit -m "fix: recognize Trae is_error result/turn.completed events as failures, not hangs"
```

---

## Task 2: Public `home_dir()` + `config_dir_path()` helper in `detection.py`

**Files:**
- Modify: `skillhub_eval/execution/detection.py`
- Test: `tests/execution/test_detection.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/execution/test_detection.py`:

```python
def test_config_dir_path_returns_existing_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".trae").mkdir()
    path = detection.config_dir_path(get_agent_def("trae"))
    assert path == tmp_path / ".trae"


def test_config_dir_path_returns_first_declared_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    path = detection.config_dir_path(get_agent_def("trae"))
    assert path == tmp_path / ".trae"
    assert not path.exists()


def test_config_dir_path_none_when_agent_declares_no_dirs(tmp_path, monkeypatch):
    from skillhub_eval.execution.agent_registry import AgentDef

    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    bare = AgentDef(agent_id="x", label="X", adapter_factory=None, fallback_models=(), config_dirs=())
    assert detection.config_dir_path(bare) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/execution/test_detection.py -k config_dir_path -v`
Expected: FAIL with `AttributeError: module 'skillhub_eval.execution.detection' has no attribute 'config_dir_path'`

- [ ] **Step 3: Implement `home_dir()` (renamed from `_home()`) and `config_dir_path()`**

In `skillhub_eval/execution/detection.py`, rename the existing `_home` function to `home_dir` (drop the leading underscore) and update its two call sites, then add `config_dir_path`:

```python
def home_dir() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _install_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("LOCALAPPDATA", "APPDATA"):
        val = os.environ.get(key)
        if val:
            roots.append(Path(val))
    roots.append(home_dir())
    return roots


def _config_dir_present(agent: AgentDef) -> bool:
    home = home_dir()
    return any((home / rel).exists() for rel in agent.config_dirs)


def config_dir_path(agent: AgentDef) -> Path | None:
    """Return the agent's config dir under HOME: the first that exists, else the first declared."""
    if not agent.config_dirs:
        return None
    home = home_dir()
    for rel in agent.config_dirs:
        candidate = home / rel
        if candidate.exists():
            return candidate
    return home / agent.config_dirs[0]
```

Place `config_dir_path` directly after `_config_dir_present` in the file (both are config-dir helpers, keep them together).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/execution/test_detection.py -q`
Expected: PASS, all tests in the file

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/detection.py tests/execution/test_detection.py
git commit -m "refactor: expose detection.config_dir_path() for diagnosis feature"
```

---

## Task 3: `DiagnosisResult` + `check_writable()` shared primitives

**Files:**
- Create: `skillhub_eval/execution/diagnostics.py`
- Test: `tests/execution/test_diagnostics.py`

- [ ] **Step 1: Write the failing test**

Create `tests/execution/test_diagnostics.py`:

```python
from skillhub_eval.execution.diagnostics import DiagnosisResult, check_writable


def test_diagnosis_result_is_a_frozen_dataclass():
    result = DiagnosisResult(ok=True, reason_code=None, message_zh="正常")
    assert result.ok is True
    assert result.manual_hint is None


def test_check_writable_true_for_writable_dir(tmp_path):
    assert check_writable(tmp_path) is True
    # the probe file must not be left behind
    assert list(tmp_path.iterdir()) == []


def test_check_writable_false_for_missing_dir(tmp_path):
    missing = tmp_path / "does-not-exist"
    assert check_writable(missing) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/execution/test_diagnostics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'skillhub_eval.execution.diagnostics'`

- [ ] **Step 3: Implement `diagnostics.py`**

Create `skillhub_eval/execution/diagnostics.py`:

```python
"""Adapter-agnostic local-agent diagnosis result + shared filesystem probes (Q-29)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DiagnosisResult:
    """Result of an optional AgentAdapter.diagnose() call, surfaced at scan time."""

    ok: bool
    reason_code: str | None
    message_zh: str
    manual_hint: str | None = None


def check_writable(dir_path: Path) -> bool:
    """Best-effort probe: can we create and delete a file inside dir_path?"""
    probe = dir_path / ".skillhub_write_probe"
    try:
        probe.write_text("ok", encoding="utf-8")
    except OSError:
        return False
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/execution/test_diagnostics.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/diagnostics.py tests/execution/test_diagnostics.py
git commit -m "feat: add DiagnosisResult + check_writable primitives for agent diagnosis"
```

---

## Task 4: `is_model_verified_live()` shared helper (D10 bug fix)

**This is the most important task in this plan — read the "Context You Need" section above before starting.**

**Files:**
- Modify: `skillhub_eval/execution/models.py`
- Test: `tests/execution/test_models.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/execution/test_models.py`:

```python
def test_is_model_verified_live_true_for_live_match():
    with patch.object(models, "_run_probe", return_value="GLM-5.2\nDeepSeek-V4-Pro\n"):
        verified, source = models.is_model_verified_live(get_agent_def("trae"), "GLM-5.2")
    assert verified is True
    assert source == "live"


def test_is_model_verified_live_not_masked_by_self_append():
    """Regression for the D10 bug: discover_models() self-appends an unseen
    stored_model as a 'stale' entry, which would defeat a naive
    `model_id in {m['id'] for m in disc.models}` check. This test drives the
    *real* discover_models() (only the subprocess-level _run_probe is mocked)
    to prove is_model_verified_live() is not fooled by that self-append."""
    with patch.object(models, "_run_probe", return_value="model-a\nmodel-b\n"):
        verified, source = models.is_model_verified_live(get_agent_def("trae"), "GLM-5.2")
    assert source == "live"
    assert verified is False


def test_is_model_verified_live_probe_unavailable():
    with patch.object(models, "_run_probe", return_value=None):
        verified, source = models.is_model_verified_live(get_agent_def("trae"), "GLM-5.2")
    assert source == "fallback"
    assert verified is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/execution/test_models.py -k is_model_verified_live -v`
Expected: FAIL with `AttributeError: module 'skillhub_eval.execution.models' has no attribute 'is_model_verified_live'`

- [ ] **Step 3: Implement `is_model_verified_live()`**

In `skillhub_eval/execution/models.py`, add this function after `discover_models`:

```python
def is_model_verified_live(agent: AgentDef, model_id: str) -> tuple[bool, str]:
    """Check model_id against an unmasked live probe.

    Always calls discover_models() with stored_model=None so a not-found
    model is never silently re-appended as a "stale"/"custom" entry —
    discover_models() does that on purpose to keep UI dropdowns populated,
    but it defeats a caller that wants to know "was this actually confirmed
    live". Returns (verified, models_source) so the caller can distinguish
    "confirmed absent from a successful live probe" (models_source == "live",
    verified == False) from "we have no live data to judge by" (models_source
    in ("fallback", "none")).
    """
    disc = discover_models(agent, stored_model=None)
    live_ids = {m["id"] for m in disc.models if m.get("source") == "live"}
    return (model_id in live_ids, disc.models_source)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/execution/test_models.py -q`
Expected: PASS (all existing tests + 3 new ones)

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/models.py tests/execution/test_models.py
git commit -m "fix: add is_model_verified_live() to stop discover_models() self-append masking a not-found model"
```

---

## Task 5: `TraeAdapter.diagnose()`

**Files:**
- Modify: `skillhub_eval/execution/adapters/trae.py`
- Test: `tests/execution/test_adapter_trae.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/execution/test_adapter_trae.py`:

```python
from unittest.mock import patch
import yaml

from skillhub_eval.execution import diagnostics, models as models_module
from skillhub_eval.execution.adapters.trae import TraeAdapter
from skillhub_eval.execution.models import ModelDiscovery


def test_diagnose_missing_config_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    result = TraeAdapter().diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_DIR_MISSING"


def test_diagnose_dir_not_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".trae").mkdir()
    with patch.object(diagnostics, "check_writable", return_value=False):
        result = TraeAdapter().diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_CONFIG_DIR_NOT_WRITABLE"


def test_diagnose_missing_models_section(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_CONFIGURED"


def test_diagnose_reads_fallback_config_filename(tmp_path, monkeypatch):
    """Defensive-only: try traecli.yaml if trae_cli.yaml doesn't exist (D10
    design note — this filename is unverified, but the fallback is free)."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "traecli.yaml").write_text(
        yaml.safe_dump({"model": {"name": "GLM-5.2"}}), encoding="utf-8"
    )
    result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_CONFIGURED"  # config was read, just incomplete


def test_diagnose_probe_unavailable(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "GLM-5.2", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value=None):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_PROBE_UNAVAILABLE"


def test_diagnose_model_not_in_probe_list(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "other-model", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value="other-model\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is False
    assert result.reason_code == "TRAE_MODEL_NOT_IN_LIST"


def test_diagnose_ok_when_model_resolves(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    cfg_dir = tmp_path / ".trae"
    cfg_dir.mkdir()
    (cfg_dir / "trae_cli.yaml").write_text(
        yaml.safe_dump(
            {"model": {"name": "GLM-5.2"}, "models": [{"name": "GLM-5.2", "provider": "zhipu"}]}
        ),
        encoding="utf-8",
    )
    with patch.object(models_module, "_run_probe", return_value="GLM-5.2\n"):
        result = TraeAdapter(model="GLM-5.2").diagnose()
    assert result.ok is True
    assert result.reason_code is None
```

Note: these tests mock `_run_probe` (the actual subprocess boundary), not `discover_models`/`is_model_verified_live` — this is deliberate, matching the D10 lesson: mocking too close to the bug hides it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/execution/test_adapter_trae.py -k diagnose -v`
Expected: FAIL with `AttributeError: 'TraeAdapter' object has no attribute 'diagnose'`

- [ ] **Step 3: Implement `diagnose()` on `TraeAdapter`**

In `skillhub_eval/execution/adapters/trae.py`, add this method to the `TraeAdapter` class (after `parse_stream`):

```python
    def diagnose(self):
        from skillhub_eval.execution.agent_registry import get_agent_def
        from skillhub_eval.execution.detection import config_dir_path
        from skillhub_eval.execution.diagnostics import DiagnosisResult, check_writable
        from skillhub_eval.execution.models import is_model_verified_live
        import yaml

        agent = get_agent_def("trae")
        if agent is None:
            return None

        manual_hint = (
            "手动排查：在终端运行 `trae-cli models` 查看可用模型；"
            "检查 %USERPROFILE%\\.trae\\trae_cli.yaml（或 traecli.yaml）是否包含 models: 列表，"
            "且 model.name 与其中一项一致（参考 Trae 官方 provider 配置文档）。"
        )

        cfg_dir = config_dir_path(agent)
        if cfg_dir is None or not cfg_dir.exists():
            return DiagnosisResult(
                ok=False,
                reason_code="TRAE_CONFIG_DIR_MISSING",
                message_zh="未找到 Trae 配置目录（.trae），请先运行一次 trae-cli 完成初始化配置。",
                manual_hint=manual_hint,
            )

        if not check_writable(cfg_dir):
            return DiagnosisResult(
                ok=False,
                reason_code="TRAE_CONFIG_DIR_NOT_WRITABLE",
                message_zh=f"配置目录 {cfg_dir} 当前对运行 SkillHub 的账户不可写，Trae 可能无法保存模型/会话状态。",
                manual_hint=f'手动排查：运行 icacls "{cfg_dir}" 检查权限；确保启动 skillhub-eval serve 的账户对该目录有写权限。',
            )

        # trae_cli.yaml is the only filename observed on the reference
        # machine; traecli.yaml is an unverified, zero-cost defensive
        # fallback only (see design.md D10 note — do not treat as confirmed).
        config_path = None
        for candidate_name in ("trae_cli.yaml", "traecli.yaml"):
            candidate = cfg_dir / candidate_name
            if candidate.exists():
                config_path = candidate
                break

        has_models_section = False
        configured_model = self.model
        if config_path is not None:
            try:
                raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                raw = {}
            if isinstance(raw, dict):
                models_field = raw.get("models")
                has_models_section = isinstance(models_field, list) and bool(models_field)
                if not configured_model:
                    model_field = raw.get("model")
                    if isinstance(model_field, dict):
                        configured_model = model_field.get("name")

        if not has_models_section:
            return DiagnosisResult(
                ok=False,
                reason_code="TRAE_MODEL_NOT_CONFIGURED",
                message_zh="Trae 配置文件缺少 models: provider 定义，选定的模型无法解析（trae-cli 会报 'Models is required'）。",
                manual_hint=manual_hint,
            )

        if configured_model:
            verified, probe_source = is_model_verified_live(agent, configured_model)
            if probe_source != "live":
                return DiagnosisResult(
                    ok=False,
                    reason_code="TRAE_MODEL_PROBE_UNAVAILABLE",
                    message_zh="无法通过 trae-cli models 探测到可用模型列表，配置可能仍不完整或 CLI 无响应。",
                    manual_hint=manual_hint,
                )
            if not verified:
                return DiagnosisResult(
                    ok=False,
                    reason_code="TRAE_MODEL_NOT_IN_LIST",
                    message_zh=f"配置的模型 {configured_model} 不在 trae-cli 探测到的可用模型列表中。",
                    manual_hint=manual_hint,
                )

        return DiagnosisResult(ok=True, reason_code=None, message_zh="Trae 模型配置检测正常。")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/execution/test_adapter_trae.py -q`
Expected: PASS (all existing tests + 7 new `diagnose` tests)

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/adapters/trae.py tests/execution/test_adapter_trae.py
git commit -m "feat: TraeAdapter.diagnose() detects missing model config / unwritable config dir"
```

---

## Task 6: Surface diagnosis + generic `selected_model_status` through `GET /api/exec/agents/scan`

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Test: `tests/adapters/test_exec_bridge_api.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/adapters/test_exec_bridge_api.py`:

```python
def test_scan_surfaces_diagnosis_when_adapter_supports_it():
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from skillhub_eval.adapters.api.app import create_app
    from skillhub_eval.execution import detection
    from skillhub_eval.execution.detection import DetectionResult
    from skillhub_eval.execution.diagnostics import DiagnosisResult

    detection.clear_detection_cache()

    class _DiagnosableAdapter(_FakeAdapter):
        def diagnose(self):
            return DiagnosisResult(
                ok=False,
                reason_code="TRAE_MODEL_NOT_CONFIGURED",
                message_zh="Trae 配置文件缺少 models: provider 定义。",
                manual_hint="手动排查：运行 trae-cli models。",
            )

    def fake_detect(agent, force=False):
        if agent.agent_id == "trae":
            return DetectionResult("trae", True, "/bin/trae-cli", "ok")
        return DetectionResult(agent.agent_id, False, None, "missing", "not found")

    def fake_resolve(agent_id, model=None):
        if agent_id == "trae":
            return _DiagnosableAdapter(agent_id="trae", detected=True, model=model)
        return _FakeAdapter(agent_id=agent_id, detected=False, model=model)

    with patch("skillhub_eval.adapters.api.routes.exec.detect_agent", side_effect=fake_detect), \
         patch("skillhub_eval.adapters.api.routes.exec.resolve_adapter", side_effect=fake_resolve):
        resp = TestClient(create_app()).get("/api/exec/agents/scan")

    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    assert agents["trae"]["diagnosis_ok"] is False
    assert agents["trae"]["diagnosis_reason_code"] == "TRAE_MODEL_NOT_CONFIGURED"
    assert "models:" in agents["trae"]["diagnosis_message"]
    assert agents["trae"]["diagnosis_hint"]
    assert agents["claude"]["diagnosis_ok"] is None


def test_scan_computes_selected_model_status_stale_for_active_agent_only():
    """API-layer test: only asserts the (verified, probe_source) -> status
    mapping the route is responsible for. It patches
    routes.exec.is_model_verified_live directly rather than reaching into
    models.discover_models, because the underlying self-masking fix (D10) is
    already covered by Task 4's dedicated unit test — duplicating that check
    here would just be two tests mocking the same thing at different depths
    for no added confidence."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from skillhub_eval.adapters.api.app import create_app
    from skillhub_eval.execution import detection
    from skillhub_eval.execution.detection import DetectionResult

    detection.clear_detection_cache()

    def fake_detect(agent, force=False):
        return DetectionResult(agent.agent_id, True, f"/bin/{agent.agent_id}", "ok")

    with patch("skillhub_eval.adapters.api.routes.exec.get_preferences",
               return_value={"exec_agent": "trae", "exec_model": "GLM-5.2"}), \
         patch("skillhub_eval.adapters.api.routes.exec.detect_agent", side_effect=fake_detect), \
         patch("skillhub_eval.adapters.api.routes.exec.is_model_verified_live",
               return_value=(False, "live")):
        resp = TestClient(create_app()).get("/api/exec/agents/scan")

    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    # trae is the active (exec_agent) selection; a "live but not verified" result -> "stale"
    assert agents["trae"]["selected_model_status"] == "stale"
    assert agents["trae"]["selected_model_message"]
    # claude is not the active agent -> no opinion
    assert agents["claude"]["selected_model_status"] is None


def test_scan_selected_model_status_default_skips_live_probe():
    """When exec_model is still the unset "default" sentinel, the route must
    report status "default" without calling is_model_verified_live() at all
    — a default selection is never "stale" or "probe_unavailable"."""
    from unittest.mock import patch
    from fastapi.testclient import TestClient
    from skillhub_eval.adapters.api.app import create_app
    from skillhub_eval.execution import detection
    from skillhub_eval.execution.detection import DetectionResult

    detection.clear_detection_cache()

    def fake_detect(agent, force=False):
        return DetectionResult(agent.agent_id, True, f"/bin/{agent.agent_id}", "ok")

    with patch("skillhub_eval.adapters.api.routes.exec.get_preferences",
               return_value={"exec_agent": "trae", "exec_model": "default"}), \
         patch("skillhub_eval.adapters.api.routes.exec.detect_agent", side_effect=fake_detect), \
         patch("skillhub_eval.adapters.api.routes.exec.is_model_verified_live") as mock_verify:
        resp = TestClient(create_app()).get("/api/exec/agents/scan")

    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    assert agents["trae"]["selected_model_status"] == "default"
    mock_verify.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/adapters/test_exec_bridge_api.py -k "diagnosis or selected_model_status" -v`
Expected: FAIL with `KeyError: 'diagnosis_reason_code'` / `KeyError: 'selected_model_status'` (and the `is_model_verified_live` patch targets will fail with `AttributeError` until Task 6 Step 3 adds the import)

- [ ] **Step 3: Implement the scan-route changes**

In `skillhub_eval/adapters/api/routes/exec.py`, add `is_model_verified_live` to the existing `models` import:

```python
from skillhub_eval.execution.models import discover_models, is_model_verified_live
```

Add fields to `AgentScanItem` (after `install_note`):

```python
    diagnosis_ok: bool | None = None
    diagnosis_reason_code: str | None = None
    diagnosis_message: str | None = None
    diagnosis_hint: str | None = None
    selected_model_status: str | None = None
    selected_model_message: str | None = None
```

Then replace the body of `scan_agents()`:

```python
@router.get("/agents/scan", response_model=AgentScanResponse)
def scan_agents() -> AgentScanResponse:
    agents: list[AgentScanItem] = []
    prefs = get_preferences()
    selected_model = str(prefs.get("exec_model") or DEFAULT_MODEL_ID)
    active_agent_id = str(prefs.get("exec_agent") or "")
    for agent in get_agent_catalog():
        # Explicit user-initiated scan: bypass the TTL cache so a freshly
        # installed / authenticated CLI is picked up immediately.
        det = detect_agent(agent, force=True)
        models: list[AgentModelItem] = []
        models_source = "none"
        install_command = install_docs_url = install_note = None
        diagnosis_ok: bool | None = None
        diagnosis_reason_code: str | None = None
        diagnosis_message: str | None = None
        diagnosis_hint: str | None = None
        selected_model_status: str | None = None
        selected_model_message: str | None = None
        if det.detected:
            disc = discover_models(agent, stored_model=selected_model)
            models = [
                AgentModelItem(id=m["id"], label=m["label"], source=m.get("source", "fallback"))
                for m in disc.models
            ]
            models_source = disc.models_source

            adapter = resolve_adapter(agent.id, model=None)
            diagnose_fn = getattr(adapter, "diagnose", None)
            if callable(diagnose_fn):
                try:
                    diagnosis = diagnose_fn()
                except Exception:
                    diagnosis = None
                if diagnosis is not None:
                    diagnosis_ok = diagnosis.ok
                    diagnosis_reason_code = diagnosis.reason_code
                    diagnosis_message = diagnosis.message_zh
                    diagnosis_hint = diagnosis.manual_hint

            # Generic model-readiness signal for every agent, not just ones
            # with a bespoke diagnose(): only meaningful for whichever single
            # agent+model pair the user actually selected, since preferences
            # only track one global (exec_agent, exec_model) pair.
            if agent.id == active_agent_id:
                if selected_model == DEFAULT_MODEL_ID:
                    selected_model_status = "default"
                    selected_model_message = "使用该 CLI 的默认模型（未在 SkillHub 中显式选择具体模型）。"
                else:
                    verified, probe_source = is_model_verified_live(agent, selected_model)
                    if probe_source != "live":
                        selected_model_status = "probe_unavailable"
                        selected_model_message = "暂时无法在线探测该 Agent 的模型列表，无法确认已选模型是否有效。"
                    elif verified:
                        selected_model_status = "ok"
                        selected_model_message = "已选模型已通过在线探测确认存在。"
                    else:
                        selected_model_status = "stale"
                        selected_model_message = f"已选模型 {selected_model} 未出现在最近一次在线探测结果中，可能已失效或输入有误。"
        else:
            hint = get_install_hint(agent.id)
            if hint:
                install_command = hint.get("install_command")
                install_docs_url = hint.get("docs_url")
                install_note = hint.get("platform_note")
        agents.append(
            AgentScanItem(
                id=agent.id,
                label=agent.label,
                detected=det.detected,
                auth_status=det.auth_state,
                bin_path=det.bin_path,
                detect_hint=det.detect_hint,
                models=models,
                models_source=models_source,
                selected_model=selected_model,
                selected_model_status=selected_model_status,
                selected_model_message=selected_model_message,
                install_command=install_command,
                install_docs_url=install_docs_url,
                install_note=install_note,
                diagnosis_ok=diagnosis_ok,
                diagnosis_reason_code=diagnosis_reason_code,
                diagnosis_message=diagnosis_message,
                diagnosis_hint=diagnosis_hint,
            )
        )
    return AgentScanResponse(scanned_at=datetime.now(UTC).isoformat(), agents=agents)
```

The broad `except Exception` around `diagnose_fn()` is intentional: `diagnose()` does file I/O and subprocess calls, and a bug in one adapter's diagnosis must never break the scan response for every other agent card.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/adapters/test_exec_bridge_api.py -q`
Expected: PASS (all existing scan/preferences tests + the 3 new tests)

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/api/routes/exec.py tests/adapters/test_exec_bridge_api.py
git commit -m "feat: surface agent diagnosis + generic selected-model readiness through scan API"
```

---

## Task 7: Model-aware `POST /api/exec/agents/{agent_id}/test`

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Test: `tests/adapters/test_exec_bridge_api.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/adapters/test_exec_bridge_api.py`:

```python
def test_agent_test_accepts_explicit_model(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen: list[str | None] = []

    def fake_resolve(agent_id: str, model: str | None = None):
        seen.append(model)
        return _FakeAdapter(agent_id=agent_id, detected=True, model=model)

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve)

    class _DoneProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return ('{"type":"result","duration_ms":1}\n', "")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec._spawn_process",
        lambda *a, **k: _DoneProcess(),
    )

    resp = client.post("/api/exec/agents/trae/test", json={"model": "GLM-5.2"})
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert seen == ["GLM-5.2"]


def test_agent_test_without_body_still_defaults_to_none(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    seen: list[str | None] = []

    def fake_resolve(agent_id: str, model: str | None = None):
        seen.append(model)
        return _FakeAdapter(agent_id=agent_id, detected=True, model=model)

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve)

    class _DoneProcess:
        returncode = 0

        def communicate(self, input=None, timeout=None):
            return ('{"type":"result","duration_ms":1}\n', "")

        def wait(self, timeout=None):
            return 0

    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec._spawn_process",
        lambda *a, **k: _DoneProcess(),
    )

    resp = client.post("/api/exec/agents/codex/test")
    assert resp.status_code == 200
    assert seen == [None]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/adapters/test_exec_bridge_api.py -k agent_test_accepts_explicit_model -v`
Expected: FAIL with `assert seen == ['GLM-5.2']` actually being `seen == [None]` (the endpoint currently ignores any body content)

- [ ] **Step 3: Implement the model-aware test endpoint**

In `skillhub_eval/adapters/api/routes/exec.py`, update the `fastapi` import to also bring in `Body`:

```python
from fastapi import APIRouter, Body
```

`Body(default=None)` was verified empirically against the pinned FastAPI version (0.136.3) before writing this step: a plain `body: AgentTestRequest | None = None` annotation already returns 200 for no-body, empty-JSON, and populated-JSON requests on this version, so this is not fixing a live bug on the current pin — it is the officially-recommended, explicit way to declare an optional body param, and removes any ambiguity on a future FastAPI upgrade. Use it anyway, since it's a zero-cost, drop-in choice.

Add a request model near the other request/response models:

```python
class AgentTestRequest(BaseModel):
    model: str | None = None
```

Update the route signature and the `resolve_adapter` call:

```python
@router.post("/agents/{agent_id}/test", response_model=AgentTestResponse)
def test_agent(agent_id: str, body: AgentTestRequest | None = Body(default=None)) -> AgentTestResponse:
    if agent_id not in _supported_agent_ids():
        return AgentTestResponse(ok=False, message=f"Unsupported agent id: {agent_id}.")

    # D12: only pass a model when the caller explicitly names one for this
    # exact agent (the UI only does this for the currently-active exec_agent
    # card). Omitting it keeps the original protection: never let one agent's
    # selected model leak into another agent's smoke test.
    requested_model = body.model if body else None
    adapter = resolve_adapter(agent_id, model=requested_model)
    if not adapter or not adapter.detect():
        return AgentTestResponse(ok=False, message=f"Agent '{agent_id}' not detected.")

    started = time.perf_counter()
    runner = LocalAgentRunner(spawn_fn=_spawn_process)
    smoke_cwd = tempfile.mkdtemp(prefix="skillhub_agent_test_")
    timeout_s = 90.0 if agent_id == "trae" else 60.0
    try:
        outcome = runner.run(
            adapter,
            "Reply OK",
            cwd=smoke_cwd,
            timeout_s=timeout_s,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError) as exc:
        return AgentTestResponse(
            ok=False,
            message=f"Agent smoke test failed: {exc}",
        )

    if not runner.is_run_complete(outcome):
        return AgentTestResponse(ok=False, message="Agent smoke test did not complete.")

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    return AgentTestResponse(
        ok=True,
        message=f"Agent '{agent_id}' smoke test passed.",
        duration_ms=outcome.duration_ms if outcome.duration_ms is not None else elapsed_ms,
    )
```

This only changes the first few lines of the function (the docstring comment and the `resolve_adapter` call source); everything from `started = time.perf_counter()` onward is unchanged from the current implementation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/adapters/test_exec_bridge_api.py -q`
Expected: PASS (all existing + 2 new tests). Specifically re-check `test_agent_smoke_uses_default_model_not_global_prefs` (existing test) still passes — it posts with no JSON body, so `body` is `None` and `requested_model` stays `None`, unchanged from before.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/api/routes/exec.py tests/adapters/test_exec_bridge_api.py
git commit -m "feat: allow agent test endpoint to validate an explicit model"
```

---

## Task 8: `[ui-only]` Show diagnosis + selected-model status; Test button uses active model

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`

- [ ] **Step 1: Add the diagnosis + model-status blocks to `renderExecAgentCards`**

Inside `renderExecAgentCards()`, immediately after the `installBlock` computation, add:

```js
    const diagnosisBlock = (detected && agent.diagnosis_ok === false)
      ? `<div class="mt-1 text-[11px] text-red-700 leading-relaxed">
           诊断：${escapeHtml(agent.diagnosis_message || '模型配置检测未通过')}
           ${agent.diagnosis_hint ? `<div class="text-gray-500 mt-0.5">${escapeHtml(agent.diagnosis_hint)}</div>` : ''}
         </div>`
      : '';
    const MODEL_STATUS_CLS = {
      ok: 'text-emerald-700',
      default: 'text-gray-500',
      stale: 'text-amber-700',
      probe_unavailable: 'text-gray-500',
    };
    const modelStatusBlock = (detected && agent.selected_model_status && agent.selected_model_message)
      ? `<div class="mt-0.5 text-[11px] ${MODEL_STATUS_CLS[agent.selected_model_status] || 'text-gray-500'}">已选模型：${escapeHtml(agent.selected_model_message)}</div>`
      : '';
```

Then add both blocks into the card template, directly after `${installBlock}` inside the `<div class="min-w-0">` block:

```js
              <div class="mt-1 flex flex-wrap gap-x-2 gap-y-0.5">${auth}${model}</div>
              ${installBlock}
              ${diagnosisBlock}
              ${modelStatusBlock}
```

No emoji or icon glyphs — plain text only, per the repo's UI-only visual constraints (`.cursor/rules` `integrated-ai-workflow.mdc` §UI 层: 制式回单风格无 emoji).

- [ ] **Step 2: Make `testExecAgent` pass the model when testing the active agent**

Find `async function testExecAgent(agentId)` and change the body from:

```js
async function testExecAgent(agentId) {
  _execAgentTestStatus[agentId] = '测试中…';
  renderExecAgentCards();
  try {
    const data = await apiFetch(`/api/exec/agents/${encodeURIComponent(agentId)}/test`, {
      method: 'POST',
      body: JSON.stringify({}),
    });
```

to:

```js
async function testExecAgent(agentId) {
  _execAgentTestStatus[agentId] = '测试中…';
  renderExecAgentCards();
  try {
    // D12: only validate the currently-selected model when testing the
    // currently-active agent card — every other card keeps testing the CLI
    // default, since SkillHub only tracks one global (agent, model) pair.
    const isActiveAgent = getSelectedExecAgent() === agentId;
    const modelToTest = isActiveAgent ? (_execPreferences?.exec_model || null) : null;
    const data = await apiFetch(`/api/exec/agents/${encodeURIComponent(agentId)}/test`, {
      method: 'POST',
      body: JSON.stringify(modelToTest ? { model: modelToTest } : {}),
    });
```

The rest of the function body is unchanged. Note `_execPreferences.exec_model` may be the literal string `"default"` when unset — this is fine to send as-is, the backend's `resolve_adapter` → `_normalize_model` already treats `"default"` the same as `None`.

- [ ] **Step 3: Verify syntax**

Run: `node --check skillhub_eval/adapters/ui/static/assets/index.js`
Expected: no output (success)

- [ ] **Step 4: Manual smoke check**

Start the server (`python -m skillhub_eval.adapters.cli.main serve --host 127.0.0.1 --port 8000`), open the UI, open the exec-agent drawer, and confirm:
- Agents without a `diagnose()` method (Claude/Codex/Cursor-agent/Antigravity) render exactly as before for the diagnosis line — no new red text appears for them.
- The currently-selected agent's card shows a "已选模型：…" line reflecting its `selected_model_status`.
- If Trae is detected but its `trae_cli.yaml` still lacks a `models:` block, its card shows the new red diagnosis line with the manual-hint text underneath.
- Clicking "Test" on the currently-selected agent sends its selected model; clicking "Test" on a different (non-selected) agent card does not.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/ui/static/assets/index.js
git commit -m "feat(ui): show agent diagnosis + selected-model status; Test validates active model"
```

---

## Task 9: Docs closeout (Codex scope) + real 3-agent re-verification (Cursor scope, separate)

**Files:**
- Modify: `docs/runbooks/local-agent-exec-validation.md`
- Modify: `.project_memory/active/SPRINT_phase3-eval-system.md`
- Modify: `openspec/changes/local-agent-trial-hardening/tasks.md`

- [ ] **Step 1: Update the runbook**

Append a section to `docs/runbooks/local-agent-exec-validation.md` describing: (a) Trae's `type=result`/`turn.completed` with `is_error: true` is now recognized as a real failure, not a hang; (b) `GET /api/exec/agents/scan` now returns `diagnosis_ok`/`diagnosis_reason_code`/`diagnosis_message`/`diagnosis_hint` for agents that implement `diagnose()` (currently only Trae) and `selected_model_status`/`selected_model_message` for whichever agent is currently selected (all agents); (c) `POST /api/exec/agents/{agent_id}/test` now accepts an optional `model` field, used by the UI only for the active agent's card; (d) the specific root cause found on the reference test machine (missing `models:` block in `trae_cli.yaml`, and a `CodexSandboxUsers` ACL entry without write access on `.trae`) as a worked example, together with the exact manual fix commands (edit `trae_cli.yaml` to add a `models:` list; `icacls` grant for the account running `serve`).

- [ ] **Step 2: Tick off the Sprint backlog items this closes**

In `.project_memory/active/SPRINT_phase3-eval-system.md`, under the Q-29 section, mark **N1** and **N2** as done (`- [x]`) with a one-line note referencing this change's commits. Leave **N3–N5** as-is — they are not addressed by this plan.

- [ ] **Step 3: Tick off the OpenSpec tasks.md checkboxes**

In `openspec/changes/local-agent-trial-hardening/tasks.md`, section "8.", change items **8.1 through 8.9** from `- [ ]` to `- [x]` (one line each, matching the Task 1–9 numbering in this plan). **Do not** check off **8.10** — that is explicitly Cursor's real-machine verification step, not part of this implementation pass.

- [ ] **Step 4: Encoding check**

Run: `python scripts/check_doc_encoding.py`
Expected: no errors reported.

- [ ] **Step 5: Commit**

```bash
git add docs/runbooks/local-agent-exec-validation.md .project_memory/active/SPRINT_phase3-eval-system.md openspec/changes/local-agent-trial-hardening/tasks.md
git commit -m "docs: close out Q-29 stream-parser fix + diagnosis/model-readiness surfacing"
```

- [ ] **Step 6 (Cursor, not Codex — do not attempt this step):** After the user manually fixes `trae_cli.yaml` and `.trae` ACL permissions on their machine per the diagnosis hint, Cursor re-runs a real evaluation against Codex CLI, Cursor Agent, and Trae (each with a real model selected) using `testskills/exec-fixture-minimal` (or `stock-radar`), confirms all three complete with a real Pass/Warn/Fail (not `run_incomplete` or a silent block), and records the result in `RECORD.md`.

---

## Self-Review Checklist (already applied while writing this plan)

- **Spec coverage**: D7 (bounded, non-`doctor` detection) → Task 5. D8 (scan-time only) → Task 6. D9 (generic optional `diagnose()`, no Protocol change) → Task 5/6 (uses `getattr`, no `runner.py` Protocol edit). D10 (fix the self-masking bug + regression test that doesn't hide it) → Task 4, reused by Task 5 and Task 6. D11 (generic `selected_model_status` for all agents) → Task 6. D12 (model-aware test endpoint, scoped to the active agent) → Task 7/8. Task 1 covers the already-diagnosed completion-detection root cause. Task 9 covers the doc/tasks.md closeout and hands off real-machine 3-agent verification explicitly to Cursor.
- **Placeholder scan**: no TBD/TODO; every step has literal code or an exact command.
- **Type consistency**: `DiagnosisResult` fields (`ok`, `reason_code`, `message_zh`, `manual_hint`) are used identically across Task 3 (definition), Task 5 (construction in `TraeAdapter.diagnose()`), and Task 6 (`diagnosis.ok`/`diagnosis.reason_code`/`diagnosis.message_zh`/`diagnosis.manual_hint` read in `exec.py`). `is_model_verified_live(agent, model_id) -> tuple[bool, str]` (Task 4) is called with the same two positional args and the same `(verified, probe_source)` unpacking in both Task 5 and Task 6 — no renamed fields or reordered tuple elements between call sites.
- **D10 regression coverage double-checked**: Task 4's `test_is_model_verified_live_not_masked_by_self_append` and Task 5's `test_diagnose_model_not_in_probe_list` both mock only `_run_probe` (the subprocess boundary), never `discover_models`/`is_model_verified_live` themselves — this is the specific TDD mistake the D10 finding called out, and both new tests are written to not repeat it.
