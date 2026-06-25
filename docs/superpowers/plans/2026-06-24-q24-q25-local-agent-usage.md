# Q-24 / Q-25 Local Agent and Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement Q-24 local-agent execution improvements and Q-25 token usage reporting, including a five-agent registry, model selection, bounded case execution, budget UI, provider error classification, and usage summaries.

**Architecture:** Add a declarative local-agent registry consumed by preferences, scan API, adapters, runner, and UI. Keep one selected agent/model per formal evaluation run, but record agent/model metadata and usage so later multi-agent comparison can build on it. Capture provider/local-agent usage as `eval_events` and aggregate it into `EvaluationReport.usage_summary`.

**Tech Stack:** Python 3, FastAPI, Pydantic, SQLite repository, vanilla JavaScript UI in `skillhub_eval/adapters/ui/static/assets/index.js`, pytest.

---

## Scope Guard

This plan implements the approved design in `docs/superpowers/specs/2026-06-24-q24-q25-local-agent-usage-design.md`.

Do not implement:

- W5.5 script B/C.
- `docs/runbooks/phase3-eval-validation.md`.
- full Open Design adapter-layer migration.
- 20+ agent true execution.
- multi-agent comparison statistics or matrix UI.
- a dedicated usage database table.

The repository rule says not to create commits unless the user explicitly asks. The plan therefore uses review checkpoints instead of commit steps.

## File Structure

Create:

- `skillhub_eval/execution/agent_registry.py` — agent definitions, model options, adapter resolution, redline capability metadata.
- `skillhub_eval/execution/adapters/trae.py` — Trae adapter build args and parser delegation.
- `skillhub_eval/execution/adapters/antigravity.py` — Antigravity adapter build args, guarded settings update helper, parser delegation.
- `skillhub_eval/core/usage.py` — normalize usage payloads and aggregate `token_usage` events into report summary.
- `tests/execution/test_agent_registry.py` — registry and model fallback tests.
- `tests/execution/test_adapter_trae.py` — Trae adapter tests.
- `tests/execution/test_adapter_antigravity.py` — Antigravity adapter tests.
- `tests/core/test_usage_summary.py` — usage normalization and aggregation tests.

Modify:

- `skillhub_eval/core/schemas/report.py` — add `UsageRow`, `UsageSummary`, `agent_id`, `agent_label`, `model_id`, `model_label` fields where needed.
- `skillhub_eval/settings.py` — add `exec_model` and per-risk local agent case timeout settings.
- `skillhub_eval/persistence/sqlite.py` — persist `exec_model` in global execution preferences; support reading `token_usage` events.
- `skillhub_eval/execution/preferences.py` — read/save selected model and validate readiness with the registry.
- `skillhub_eval/execution/local_agent_source.py` — use registry, pass selected model, bounded parallel support helpers, rate-limit state, per-case timeouts, agent/model metadata in `ExecResult`.
- `skillhub_eval/execution/runner.py` — call adapter-specific parser, include stderr in outcome text for rate-limit detection, preserve usage.
- `skillhub_eval/execution/profile.py` — replace Codex-only redline check with registry capability.
- `skillhub_eval/adapters/api/routes/exec.py` — scan agents and models from registry; test selected agent/model.
- `skillhub_eval/core/engine.py` — parallelize case execution, log local-agent budget events, aggregate usage summary.
- `skillhub_eval/providers/openai_compatible.py`, `skillhub_eval/providers/deepseek.py`, `skillhub_eval/providers/gemini.py` — preserve latest response usage.
- `skillhub_eval/core/divergence.py`, `skillhub_eval/core/propagator.py`, `skillhub_eval/core/propagation_plan_enricher.py`, `skillhub_eval/core/skill_summary.py` or engine call sites — log usage for generate/synthesis/summary/risk-review stages when usage exists.
- `skillhub_eval/adapters/ui/static/assets/index.js` — agent/model dropdowns, budget display, token usage block, provider error classification.
- `.env.example` — document `EXEC_MODEL` and local-agent per-case timeout settings.
- `tests/adapters/test_exec_bridge_api.py`, `tests/execution/test_preferences.py`, `tests/execution/test_local_agent_source.py`, `tests/execution/test_runner.py`, `tests/core/test_engine.py` or focused equivalents — update expectations.

---

### Task 1: Agent Registry and Model Preferences

**Files:**
- Create: `skillhub_eval/execution/agent_registry.py`
- Modify: `skillhub_eval/execution/local_agent_source.py`
- Modify: `skillhub_eval/execution/preferences.py`
- Modify: `skillhub_eval/settings.py`
- Modify: `skillhub_eval/persistence/sqlite.py`
- Test: `tests/execution/test_agent_registry.py`
- Test: `tests/execution/test_preferences.py`

- [ ] **Step 1: Write failing registry tests**

Add `tests/execution/test_agent_registry.py`:

```python
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    get_agent_catalog,
    get_agent_def,
    resolve_adapter,
)


def test_catalog_contains_q24_agents():
    ids = [agent.id for agent in get_agent_catalog()]
    assert ids == ["claude", "codex", "cursor-agent", "trae", "antigravity"]


def test_codex_is_only_initial_hardened_redline_agent():
    assert get_agent_def("codex").supports_hardened_redline is True
    assert get_agent_def("claude").supports_hardened_redline is False
    assert get_agent_def("cursor-agent").supports_hardened_redline is False
    assert get_agent_def("trae").supports_hardened_redline is False
    assert get_agent_def("antigravity").supports_hardened_redline is False


def test_fallback_models_include_default():
    for agent in get_agent_catalog():
        ids = [m.id for m in agent.fallback_models]
        assert ids[0] == DEFAULT_MODEL_ID
        assert any(m.label for m in agent.fallback_models)


def test_resolve_adapter_passes_non_default_model():
    adapter = resolve_adapter("codex", model="gpt-5-codex")
    assert adapter is not None
    assert adapter.agent_id == "codex"
    assert adapter.model == "gpt-5-codex"


def test_resolve_adapter_omits_default_model():
    adapter = resolve_adapter("claude", model=DEFAULT_MODEL_ID)
    assert adapter is not None
    assert adapter.model is None


def test_unknown_agent_returns_none():
    assert get_agent_def("missing-agent") is None
    assert resolve_adapter("missing-agent") is None
```

- [ ] **Step 2: Run registry test and verify it fails**

Run:

```powershell
pytest tests/execution/test_agent_registry.py -q
```

Expected: FAIL because `skillhub_eval.execution.agent_registry` does not exist.

- [ ] **Step 3: Implement agent registry**

Create `skillhub_eval/execution/agent_registry.py`:

```python
"""Declarative local CLI agent registry for the execution bridge."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol

DEFAULT_MODEL_ID = "default"


@dataclass(frozen=True)
class ModelOption:
    id: str
    label: str
    source: str = "fallback"


class AdapterFactory(Protocol):
    def __call__(self, *, model: str | None = None):
        pass


@dataclass(frozen=True)
class AgentDef:
    id: str
    label: str
    bin: str
    aliases: tuple[str, ...] = field(default_factory=tuple)
    fallback_models: tuple[ModelOption, ...] = field(default_factory=tuple)
    supports_hardened_redline: bool = False
    adapter_factory: AdapterFactory | None = None

    @property
    def binary_names(self) -> tuple[str, ...]:
        return (self.bin, *self.aliases)


def _default_model() -> ModelOption:
    return ModelOption(DEFAULT_MODEL_ID, "默认模型")


def _claude_factory(*, model: str | None = None):
    from skillhub_eval.execution.adapters.claude import ClaudeAdapter

    return ClaudeAdapter(model=_normalize_model(model))


def _codex_factory(*, model: str | None = None):
    from skillhub_eval.execution.adapters.codex import CodexAdapter

    return CodexAdapter(model=_normalize_model(model))


def _cursor_factory(*, model: str | None = None):
    from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter

    return CursorAgentAdapter(model=_normalize_model(model))


def _trae_factory(*, model: str | None = None):
    from skillhub_eval.execution.adapters.trae import TraeAdapter

    return TraeAdapter(model=_normalize_model(model))


def _antigravity_factory(*, model: str | None = None):
    from skillhub_eval.execution.adapters.antigravity import AntigravityAdapter

    return AntigravityAdapter(model=_normalize_model(model))


AGENT_DEFS: tuple[AgentDef, ...] = (
    AgentDef(
        id="claude",
        label="Claude Code",
        bin="claude",
        fallback_models=(
            _default_model(),
            ModelOption("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ModelOption("claude-opus-4-6", "Claude Opus 4.6"),
        ),
        adapter_factory=_claude_factory,
    ),
    AgentDef(
        id="codex",
        label="Codex CLI",
        bin="codex",
        fallback_models=(
            _default_model(),
            ModelOption("gpt-5-codex", "GPT-5 Codex"),
            ModelOption("gpt-5", "GPT-5"),
        ),
        supports_hardened_redline=True,
        adapter_factory=_codex_factory,
    ),
    AgentDef(
        id="cursor-agent",
        label="Cursor Agent",
        bin="cursor-agent",
        fallback_models=(
            _default_model(),
            ModelOption("gpt-5", "GPT-5"),
            ModelOption("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ),
        adapter_factory=_cursor_factory,
    ),
    AgentDef(
        id="trae",
        label="Trae",
        bin="traecli",
        aliases=("trae",),
        fallback_models=(
            _default_model(),
            ModelOption("gpt-5", "GPT-5"),
            ModelOption("claude-sonnet-4-6", "Claude Sonnet 4.6"),
        ),
        adapter_factory=_trae_factory,
    ),
    AgentDef(
        id="antigravity",
        label="Antigravity",
        bin="agy",
        fallback_models=(
            _default_model(),
            ModelOption("gemini-3.1-pro", "Gemini 3.1 Pro"),
            ModelOption("claude-sonnet-4-6", "Claude Sonnet 4.6"),
            ModelOption("gpt-5", "GPT-5"),
        ),
        adapter_factory=_antigravity_factory,
    ),
)

_AGENT_MAP = {agent.id: agent for agent in AGENT_DEFS}
_AGENT_MAP["cursor_agent"] = _AGENT_MAP["cursor-agent"]


def get_agent_catalog() -> list[AgentDef]:
    return list(AGENT_DEFS)


def get_agent_def(agent_id: str) -> AgentDef | None:
    return _AGENT_MAP.get((agent_id or "").strip())


def resolve_adapter(agent_id: str, *, model: str | None = None):
    agent = get_agent_def(agent_id)
    if agent is None or agent.adapter_factory is None:
        return None
    return agent.adapter_factory(model=model)


def fallback_models_for(agent_id: str) -> list[ModelOption]:
    agent = get_agent_def(agent_id)
    return list(agent.fallback_models) if agent else []


def _normalize_model(model: str | None) -> str | None:
    value = (model or "").strip()
    if not value or value == DEFAULT_MODEL_ID:
        return None
    return value
```

- [ ] **Step 4: Add settings for selected model and per-case timeouts**

Modify `skillhub_eval/settings.py` in `Settings`:

```python
    local_agent_case_timeout_low_s: int = Field(
        default=600,
        validation_alias=AliasChoices(
            "LOCAL_AGENT_CASE_TIMEOUT_LOW_S",
            "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_LOW_S",
        ),
    )
    local_agent_case_timeout_medium_s: int = Field(
        default=900,
        validation_alias=AliasChoices(
            "LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S",
            "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S",
        ),
    )
    local_agent_case_timeout_high_s: int = Field(
        default=1800,
        validation_alias=AliasChoices(
            "LOCAL_AGENT_CASE_TIMEOUT_HIGH_S",
            "SKILLHUB_LOCAL_AGENT_CASE_TIMEOUT_HIGH_S",
        ),
    )
    exec_model: str = Field(
        default="default",
        validation_alias=AliasChoices("EXEC_MODEL", "SKILLHUB_EXEC_MODEL"),
    )
```

Place timeout settings after `local_agent_workflow_timeout_high_s`; place `exec_model` after `exec_agent`.

- [ ] **Step 5: Update SQLite preferences schema**

Modify `skillhub_eval/persistence/sqlite.py`:

1. Add `exec_model TEXT NOT NULL DEFAULT 'default'` to every `exec_preferences` `CREATE TABLE` statement.
2. In migration/init code, add a guarded `ALTER TABLE exec_preferences ADD COLUMN exec_model TEXT NOT NULL DEFAULT 'default'` when the column is missing.
3. Update `upsert_exec_preferences` signature:

```python
    def upsert_exec_preferences(
        self,
        *,
        exec_source: str | None = None,
        exec_agent: str | None = None,
        exec_model: str | None = None,
        consent_granted: bool | None = None,
    ) -> None:
```

4. Preserve existing model when `exec_model is None`, otherwise save the new value.
5. Include `exec_model` in returned rows from `get_exec_preferences()`.

- [ ] **Step 6: Update preferences module**

Modify `skillhub_eval/execution/preferences.py`:

```python
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    get_agent_catalog,
    resolve_adapter,
)
```

Change `ExecPreferences`:

```python
@dataclass
class ExecPreferences:
    exec_source: str
    exec_agent: str
    exec_model: str
    consent_granted: bool
    ready: bool
    ready_reason: str | None = None
```

Add:

```python
def get_exec_model(*, db_path: str | None = None) -> str:
    repo = _repo(db_path)
    repo.init_db()
    stored = repo.get_exec_preferences()
    if stored and stored.get("exec_model"):
        return str(stored["exec_model"])
    return _default_exec_model()
```

Update `get_preferences()` to read `exec_model`, include it in the dataclass, and keep `compute_ready(exec_source, exec_agent, consent_granted)` unchanged because model choice does not block readiness.

Update `set_preferences()`:

```python
def set_preferences(
    *,
    db_path: str | None = None,
    exec_source: str | None = None,
    exec_agent: str | None = None,
    exec_model: str | None = None,
    consent_granted: bool | None = None,
) -> dict:
    repo = _repo(db_path)
    repo.init_db()
    repo.upsert_exec_preferences(
        exec_source=exec_source,
        exec_agent=exec_agent,
        exec_model=exec_model,
        consent_granted=consent_granted,
    )
    return get_preferences(db_path=db_path)
```

Replace `_default_exec_agent()` candidate loop:

```python
    for candidate in [agent.id for agent in get_agent_catalog()]:
        if _is_agent_detected(candidate):
            return candidate
```

Add:

```python
def _default_exec_model() -> str:
    configured = (settings.exec_model or "").strip()
    return configured or DEFAULT_MODEL_ID
```

Replace `_is_agent_detected()` to use `resolve_adapter(agent_id)`.

- [ ] **Step 7: Add preference tests**

Update `tests/execution/test_preferences.py` with:

```python
def test_preferences_persist_exec_model(tmp_path, monkeypatch):
    from skillhub_eval.execution.preferences import get_preferences, set_preferences

    db_path = str(tmp_path / "prefs_model.db")
    monkeypatch.setattr("skillhub_eval.execution.preferences._is_agent_detected", lambda _agent: True)

    updated = set_preferences(
        db_path=db_path,
        exec_source="local",
        exec_agent="cursor-agent",
        exec_model="gpt-5",
        consent_granted=True,
    )

    assert updated["exec_model"] == "gpt-5"
    assert updated["ready"] is True
    assert get_preferences(db_path=db_path)["exec_model"] == "gpt-5"
```

- [ ] **Step 8: Run registry and preferences tests**

Run:

```powershell
pytest tests/execution/test_agent_registry.py tests/execution/test_preferences.py -q
```

Expected: PASS.

---

### Task 2: Trae and Antigravity Adapters

**Files:**
- Create: `skillhub_eval/execution/adapters/trae.py`
- Create: `skillhub_eval/execution/adapters/antigravity.py`
- Modify: `skillhub_eval/execution/runner.py`
- Test: `tests/execution/test_adapter_trae.py`
- Test: `tests/execution/test_adapter_antigravity.py`
- Test: `tests/execution/test_runner.py`

- [ ] **Step 1: Write Trae adapter tests**

Create `tests/execution/test_adapter_trae.py`:

```python
from unittest.mock import patch

from skillhub_eval.execution.adapters.trae import TraeAdapter


def test_trae_build_args_default_model():
    args = TraeAdapter().build_args(cwd="/ws")
    assert args[0] == "traecli"
    assert "acp" in args
    assert "serve" in args
    assert "--yolo" in args
    assert "--model" not in args


def test_trae_build_args_with_model():
    args = TraeAdapter(model="gpt-5").build_args(cwd="/ws")
    assert "--model" in args
    assert args[args.index("--model") + 1] == "gpt-5"


@patch("skillhub_eval.execution.adapters.trae.find_cli_binary", return_value="/bin/traecli")
def test_trae_detect(mock_find):
    adapter = TraeAdapter()
    assert adapter.detect() is True
    assert adapter.resolved_bin() == "/bin/traecli"
```

- [ ] **Step 2: Write Antigravity adapter tests**

Create `tests/execution/test_adapter_antigravity.py`:

```python
from unittest.mock import patch

from skillhub_eval.execution.adapters.antigravity import AntigravityAdapter


def test_antigravity_build_args_default_model():
    args = AntigravityAdapter().build_args(cwd="/ws")
    assert args[0] == "agy"
    assert "--model" not in args


def test_antigravity_build_args_with_model_records_model():
    adapter = AntigravityAdapter(model="gemini-3.1-pro")
    args = adapter.build_args(cwd="/ws")
    assert args[0] == "agy"
    assert adapter.model == "gemini-3.1-pro"


def test_antigravity_settings_path_uses_home(tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    adapter = AntigravityAdapter(model="gemini-3.1-pro")
    path = adapter.settings_path()
    assert path == tmp_path / ".gemini" / "antigravity-cli" / "settings.json"


@patch("skillhub_eval.execution.adapters.antigravity.find_cli_binary", return_value="/bin/agy")
def test_antigravity_detect(mock_find):
    adapter = AntigravityAdapter()
    assert adapter.detect() is True
    assert adapter.resolved_bin() == "/bin/agy"
```

- [ ] **Step 3: Run adapter tests and verify failure**

Run:

```powershell
pytest tests/execution/test_adapter_trae.py tests/execution/test_adapter_antigravity.py -q
```

Expected: FAIL because adapter modules do not exist.

- [ ] **Step 4: Implement Trae adapter**

Create `skillhub_eval/execution/adapters/trae.py`:

```python
"""Trae CLI adapter for local execution."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from skillhub_eval.execution.cli_detect import find_cli_binary


@dataclass
class TraeAdapter:
    agent_id: str = "trae"
    bin: str = "traecli"
    model: str | None = None

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None or find_cli_binary("trae") is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or find_cli_binary("trae") or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        args = ["acp", "serve", "--yolo"]
        if self.model:
            args.extend(["--model", self.model])
        return [self.resolved_bin(), *args]

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)
```

- [ ] **Step 5: Implement Antigravity adapter**

Create `skillhub_eval/execution/adapters/antigravity.py`:

```python
"""Antigravity CLI adapter for local execution."""

from __future__ import annotations

from dataclasses import dataclass

from skillhub_eval.execution.cli_detect import find_cli_binary


@dataclass
class AntigravityAdapter:
    agent_id: str = "antigravity"
    bin: str = "agy"
    model: str | None = None

    def detect(self) -> bool:
        return find_cli_binary(self.bin) is not None

    def resolved_bin(self) -> str:
        return find_cli_binary(self.bin) or self.bin

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        if self.model:
            self.write_model_setting(self.model)
        return [self.resolved_bin()]

    def settings_path(self) -> Path:
        home = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))
        return home / ".gemini" / "antigravity-cli" / "settings.json"

    def write_model_setting(self, model: str) -> None:
        path = self.settings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {}
        if path.exists():
            try:
                parsed = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    data = parsed
            except json.JSONDecodeError:
                data = {}
        data["model"] = model
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.core.schemas.report import ParsedStream
        from skillhub_eval.execution.stream_parser import parse_stream_events

        parsed = parse_stream_events(lines)
        if parsed.final_text or parsed.is_complete:
            return parsed
        text = "\n".join(line for line in lines if line.strip())
        return ParsedStream(final_text=text, is_complete=bool(text))
```

- [ ] **Step 6: Make runner use adapter-specific parser**

Modify `skillhub_eval/execution/runner.py`:

1. Extend `AgentAdapter` protocol:

```python
    def parse_stream(self, lines: list[str]):
        pass
```

2. In `run()`, replace:

```python
        parsed = parse_stream_events(lines)
```

with:

```python
        parsed = adapter.parse_stream(lines)
```

3. Preserve stderr for later rate-limit detection by extending `_stream_until_complete()` in a later task. Do not add stderr handling yet.

- [ ] **Step 7: Run adapter and runner tests**

Run:

```powershell
pytest tests/execution/test_adapter_trae.py tests/execution/test_adapter_antigravity.py tests/execution/test_runner.py -q
```

Expected: PASS.

---

### Task 3: Exec API Scan, Model Lists, and UI Preference Surface

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: `tests/adapters/test_exec_bridge_api.py`

- [ ] **Step 1: Update API tests for models and five agents**

Modify `tests/adapters/test_exec_bridge_api.py` scan test expectations:

```python
def test_agent_scan(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    class _FakeAdapter:
        def __init__(self, agent_id: str, detected: bool, model: str | None = None):
            self.agent_id = agent_id
            self.bin = "traecli" if agent_id == "trae" else ("agy" if agent_id == "antigravity" else agent_id)
            self.model = model

        def detect(self):
            return detected.get(self.agent_id, False)

        def resolved_bin(self):
            return f"/bin/{self.bin}"

    detected = {
        "claude": True,
        "codex": False,
        "cursor-agent": True,
        "trae": True,
        "antigravity": False,
    }

    def fake_resolve(agent_id: str, model: str | None = None):
        return _FakeAdapter(agent_id=agent_id, detected=detected, model=model)

    monkeypatch.setattr("skillhub_eval.adapters.api.routes.exec.resolve_adapter", fake_resolve)
    monkeypatch.setattr(
        "skillhub_eval.adapters.api.routes.exec.find_cli_binary",
        lambda name: f"/bin/{name}" if name in {"claude", "cursor-agent", "traecli"} else None,
    )

    scan_resp = client.get("/api/exec/agents/scan")
    assert scan_resp.status_code == 200
    scan = scan_resp.json()
    agents = scan["agents"]
    assert [a["id"] for a in agents] == ["claude", "codex", "cursor-agent", "trae", "antigravity"]
    assert [a["label"] for a in agents] == [
        "Claude Code",
        "Codex CLI",
        "Cursor Agent",
        "Trae",
        "Antigravity",
    ]
    assert all("models" in a for a in agents)
    assert all(a["models_source"] in {"fallback", "none"} for a in agents)
```

Also add:

```python
def test_preferences_accept_exec_model(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("skillhub_eval.execution.preferences._is_agent_detected", lambda _agent: True)
    resp = client.put(
        "/api/exec/preferences",
        json={"exec_source": "local", "exec_agent": "cursor-agent", "exec_model": "gpt-5"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["exec_model"] == "gpt-5"
```

- [ ] **Step 2: Run API tests and verify failure**

Run:

```powershell
pytest tests/adapters/test_exec_bridge_api.py -q
```

Expected: FAIL because API response schemas lack model fields and still expose three agents.

- [ ] **Step 3: Update exec route schemas and scan implementation**

Modify `skillhub_eval/adapters/api/routes/exec.py`:

1. Imports:

```python
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    ModelOption,
    get_agent_catalog,
    resolve_adapter,
)
```

2. Replace `_resolve_adapter` import with `resolve_adapter`.

3. Add schema:

```python
class AgentModelItem(BaseModel):
    id: str
    label: str
    source: str = "fallback"
```

4. Extend `AgentScanItem`:

```python
    models: list[AgentModelItem] = []
    models_source: str = "none"
    selected_model: str | None = None
```

5. Extend `ExecPreferencesResponse` and `ExecPreferencesUpdateRequest`:

```python
    exec_model: str
```

and

```python
    exec_model: str | None = None
```

6. Replace `_AGENT_CATALOG` and `_SUPPORTED_AGENT_IDS`:

```python
def _supported_agent_ids() -> set[str]:
    return {agent.id for agent in get_agent_catalog()}
```

7. Add:

```python
def _model_items(models: list[ModelOption]) -> list[AgentModelItem]:
    return [AgentModelItem(id=m.id, label=m.label, source=m.source) for m in models]
```

8. Update `scan_agents()`:

```python
    prefs = get_preferences()
    selected_model = str(prefs.get("exec_model") or DEFAULT_MODEL_ID)
    for agent in get_agent_catalog():
        adapter = resolve_adapter(agent.id, model=selected_model)
        bin_path = None
        for bin_name in agent.binary_names:
            bin_path = find_cli_binary(bin_name)
            if bin_path:
                break
        detected = bin_path is not None
        models = _model_items(list(agent.fallback_models))
        agents.append(
            AgentScanItem(
                id=agent.id,
                label=agent.label,
                detected=detected,
                auth_status="unknown" if agent.id == "cursor-agent" and detected else None,
                model_hint=selected_model,
                bin_path=bin_path,
                detect_hint=None if detected else detect_hint_zh(agent.bin),
                models=models,
                models_source="fallback" if models else "none",
                selected_model=selected_model,
            )
        )
```

9. Update `update_exec_preferences()` to pass `exec_model=body.exec_model`.

10. Update `test_agent(agent_id)`:

```python
    if agent_id not in _supported_agent_ids():
        return AgentTestResponse(ok=False, message=f"Unsupported agent id: {agent_id}.")
    prefs = get_preferences()
    adapter = resolve_adapter(agent_id, model=str(prefs.get("exec_model") or DEFAULT_MODEL_ID))
```

- [ ] **Step 4: Update UI model selectors**

Modify `skillhub_eval/adapters/ui/static/assets/index.js`:

1. Replace `EXEC_AGENT_LABELS` with a fallback map that includes five agents:

```javascript
const EXEC_AGENT_LABELS = {
  claude: 'Claude Code',
  codex: 'Codex CLI',
  'cursor-agent': 'Cursor Agent',
  trae: 'Trae',
  antigravity: 'Antigravity',
};
```

2. Add helpers:

```javascript
function getSelectedExecAgent() {
  return _execPreferences?.exec_agent || '';
}

function getSelectedExecModel() {
  return _execPreferences?.exec_model || 'default';
}

function getExecModelsForSelectedAgent() {
  const agentId = getSelectedExecAgent();
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const agent = agents.find((a) => a.id === agentId);
  return Array.isArray(agent?.models) ? agent.models : [{ id: 'default', label: '默认模型' }];
}
```

3. Add `renderExecAgentModelSelectors()` and call it from `renderExecDrawer()`:

```javascript
function renderExecAgentModelSelectors() {
  const agentSelect = document.getElementById('exec-agent-select');
  const modelSelect = document.getElementById('exec-model-select');
  if (!agentSelect || !modelSelect) return;
  const agents = Array.isArray(_execScanCache?.agents) ? _execScanCache.agents : [];
  const selectedAgent = getSelectedExecAgent();
  agentSelect.innerHTML = agents.map((agent) => {
    const disabled = agent.detected ? '' : 'disabled';
    const selected = agent.id === selectedAgent ? 'selected' : '';
    const suffix = agent.detected ? '' : '（未检测到）';
    return `<option value="${escapeHtml(agent.id)}" ${selected} ${disabled}>${escapeHtml(agent.label || agent.id)}${suffix}</option>`;
  }).join('');

  const selectedModel = getSelectedExecModel();
  const models = getExecModelsForSelectedAgent();
  const hasSelected = models.some((m) => m.id === selectedModel);
  const rows = hasSelected ? models : [{ id: selectedModel, label: `${selectedModel}（自定义）`, source: 'custom' }, ...models];
  modelSelect.innerHTML = rows.map((model) => {
    const selected = model.id === selectedModel ? 'selected' : '';
    return `<option value="${escapeHtml(model.id)}" ${selected}>${escapeHtml(model.label || model.id)}</option>`;
  }).join('');
}
```

4. Add handlers:

```javascript
async function onExecAgentSelectChange(nextAgent) {
  if (!_execPreferences || _execPreferences.exec_agent === nextAgent) return;
  await putExecPreferences({ exec_agent: nextAgent, exec_model: 'default' });
}

async function onExecModelSelectChange(nextModel) {
  if (!_execPreferences || getSelectedExecModel() === nextModel) return;
  await putExecPreferences({ exec_model: nextModel || 'default' });
}
```

5. Update `renderExecBridgeIndicator()` pill text:

```javascript
    const modelLabel = getSelectedExecModel() === 'default' ? '默认模型' : getSelectedExecModel();
    pill.textContent = `本地执行：${agentLabel} / ${modelLabel}`;
```

6. Add matching HTML controls in `skillhub_eval/adapters/ui/static/index.html` inside the exec drawer local settings block:

```html
<div class="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-3">
  <label class="block text-xs text-gray-600">
    本地 Agent
    <select id="exec-agent-select" class="mt-1 w-full border border-gray-300 bg-white px-2 py-1 text-sm"
      onchange="onExecAgentSelectChange(this.value)"></select>
  </label>
  <label class="block text-xs text-gray-600">
    运行模型
    <select id="exec-model-select" class="mt-1 w-full border border-gray-300 bg-white px-2 py-1 text-sm"
      onchange="onExecModelSelectChange(this.value)"></select>
  </label>
</div>
```

- [ ] **Step 5: Run API test and syntax smoke**

Run:

```powershell
pytest tests/adapters/test_exec_bridge_api.py -q
python -m compileall skillhub_eval/execution skillhub_eval/adapters/api/routes/exec.py
```

Expected: tests PASS and compileall reports no syntax errors.

---

### Task 4: Redline Capability and LocalAgentSource Metadata

**Files:**
- Modify: `skillhub_eval/execution/profile.py`
- Modify: `skillhub_eval/execution/local_agent_source.py`
- Modify: `skillhub_eval/core/schemas/report.py`
- Test: `tests/execution/test_hardened_profile.py`
- Test: `tests/execution/test_local_agent_source.py`
- Test: `tests/core/test_ports.py`

- [ ] **Step 1: Write schema/metadata tests**

Update `tests/core/test_ports.py`:

```python
def test_exec_result_accepts_agent_model_metadata():
    from skillhub_eval.core.schemas.report import ExecResult

    result = ExecResult(
        source="local_agent",
        agent_id="cursor-agent",
        agent_label="Cursor Agent",
        model_id="gpt-5",
        model_label="GPT-5",
    )

    assert result.agent_id == "cursor-agent"
    assert result.model_id == "gpt-5"
```

Update `tests/execution/test_hardened_profile.py` to assert Trae/Antigravity degrade through capability:

```python
class _TraeAdapter:
    agent_id = "trae"


class _AntigravityAdapter:
    agent_id = "antigravity"


def test_new_agents_do_not_support_redline_hardened_profile():
    from skillhub_eval.execution.profile import HardenedProfile

    assert HardenedProfile.supports_redline(_TraeAdapter()) is False
    assert HardenedProfile.supports_redline(_AntigravityAdapter()) is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```powershell
pytest tests/core/test_ports.py tests/execution/test_hardened_profile.py -q
```

Expected: FAIL because metadata fields and capability lookup are not implemented.

- [ ] **Step 3: Add metadata fields**

Modify `skillhub_eval/core/schemas/report.py` `ExecResult`:

```python
    agent_id: str | None = None
    agent_label: str | None = None
    model_id: str | None = None
    model_label: str | None = None
```

- [ ] **Step 4: Update hardened profile**

Modify `skillhub_eval/execution/profile.py`:

```python
from skillhub_eval.execution.agent_registry import get_agent_def
```

Replace Codex-only support check with:

```python
    @staticmethod
    def supports_redline(adapter) -> bool:
        agent = get_agent_def(getattr(adapter, "agent_id", ""))
        return bool(agent and agent.supports_hardened_redline)
```

Keep existing `redline_degrade_reason()` text but make it capability-based:

```python
        if HardenedProfile.supports_redline(adapter):
            return None
        return "redline_requires_hardened_agent"
```

- [ ] **Step 5: Update LocalAgentSource adapter resolution and metadata**

Modify `skillhub_eval/execution/local_agent_source.py`:

1. Imports:

```python
from skillhub_eval.execution.agent_registry import (
    DEFAULT_MODEL_ID,
    get_agent_def,
    resolve_adapter,
)
```

2. In `get_actual_output()`:

```python
        from skillhub_eval.execution.preferences import get_exec_agent, get_exec_model

        selected_agent = get_exec_agent()
        selected_model = get_exec_model()
        adapter = self._adapter or resolve_adapter(selected_agent, model=selected_model)
```

3. Replace old `_resolve_adapter` with a compatibility wrapper:

```python
def _resolve_adapter(agent_id: str) -> AgentAdapter | None:
    return resolve_adapter(agent_id)
```

4. In `_outcome_to_exec_result()`, derive labels:

```python
        agent = get_agent_def(getattr(adapter, "agent_id", ""))
        model_id = getattr(adapter, "model", None) or DEFAULT_MODEL_ID
        model_label = model_id if model_id != DEFAULT_MODEL_ID else "默认模型"
```

Change method signature to accept `adapter`:

```python
    def _outcome_to_exec_result(
        self,
        outcome: RunOutcome,
        case: dict,
        bundle: dict,
        case_id: str,
        adapter: AgentAdapter,
    ) -> ExecResult:
```

Return:

```python
            agent_id=getattr(adapter, "agent_id", None),
            agent_label=agent.label if agent else getattr(adapter, "agent_id", None),
            model_id=model_id,
            model_label=model_label,
```

5. Update call site:

```python
        return self._outcome_to_exec_result(outcome, case, bundle, case_id, adapter)
```

- [ ] **Step 6: Run focused tests**

Run:

```powershell
pytest tests/core/test_ports.py tests/execution/test_hardened_profile.py tests/execution/test_local_agent_source.py -q
```

Expected: PASS.

---

### Task 5: Bounded Parallel Case Execution and Rate-Limit Downgrade

**Files:**
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/execution/local_agent_source.py`
- Modify: `skillhub_eval/execution/runner.py`
- Modify: `skillhub_eval/core/latency.py`
- Test: `tests/core/test_latency.py`
- Test: `tests/core/test_engine.py` or `tests/core/test_execution_source_routing.py`
- Test: `tests/execution/test_local_agent_source.py`

- [ ] **Step 1: Add latency tests for per-case timeout**

Modify `tests/core/test_latency.py`:

```python
def test_local_agent_case_timeout_by_risk(monkeypatch):
    from skillhub_eval.core.latency import local_agent_case_timeout_seconds
    from skillhub_eval.core.schemas.enums import RiskLevel

    assert local_agent_case_timeout_seconds(RiskLevel.low) == 600
    assert local_agent_case_timeout_seconds(RiskLevel.medium) == 900
    assert local_agent_case_timeout_seconds(RiskLevel.high) == 1800
```

- [ ] **Step 2: Add local source rate-limit test**

Modify `tests/execution/test_local_agent_source.py`:

```python
def test_rate_limit_retries_and_downgrades_concurrency(tmp_path):
    from skillhub_eval.core.schemas.report import ParsedStream, RunOutcome
    from skillhub_eval.execution.local_agent_source import LocalAgentSource

    class _Adapter:
        agent_id = "codex"

        def detect(self):
            return True

        def build_args(self, *, cwd=None, hardened=False):
            return ["codex"]

        def parse_stream(self, lines):
            return ParsedStream(final_text="", is_complete=True)

    class _Runner:
        def __init__(self):
            self.calls = 0

        def run(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return RunOutcome(parsed_stream=ParsedStream(final_text="429 rate limit", is_complete=True))
            return RunOutcome(parsed_stream=ParsedStream(final_text='{"ok": true}', is_complete=True))

        def is_run_complete(self, outcome):
            return True

    class _Workspace:
        def acquire(self, bundle_path, case_id):
            return tmp_path

        def release(self, run_dir):
            pass

    src = LocalAgentSource(
        runner=_Runner(),
        workspace=_Workspace(),
        adapter=_Adapter(),
        concurrency=2,
        timeout_s=30,
    )
    result = src.get_actual_output(
        str(tmp_path),
        "happy_001",
        case={"id": "happy_001", "type": "happy_path"},
        bundle={"skill_id": "s1"},
    )

    assert result.status == "ok"
    assert src.current_concurrency == 1
```

If consent blocks this test, grant consent in the test:

```python
from skillhub_eval.execution.consent import grant_exec_consent
grant_exec_consent("s1")
```

- [ ] **Step 3: Run tests and verify failure**

Run:

```powershell
pytest tests/core/test_latency.py tests/execution/test_local_agent_source.py -q
```

Expected: FAIL because per-case timeout helper and concurrency downgrade are missing.

- [ ] **Step 4: Add latency helper**

Modify `skillhub_eval/core/latency.py`:

```python
def local_agent_case_timeout_seconds(risk: RiskLevel | str) -> int:
    level = RiskLevel(risk) if isinstance(risk, str) else risk
    if level == RiskLevel.high:
        return int(settings.local_agent_case_timeout_high_s)
    if level == RiskLevel.medium:
        return int(settings.local_agent_case_timeout_medium_s)
    return int(settings.local_agent_case_timeout_low_s)
```

- [ ] **Step 5: Add rate-limit state to LocalAgentSource**

Modify `skillhub_eval/execution/local_agent_source.py`:

1. Add instance fields in `__init__`:

```python
        self._rate_limited = False
```

2. Add property:

```python
    @property
    def current_concurrency(self) -> int:
        return 1 if self._rate_limited else self._concurrency
```

3. Change `_get_semaphore()` to use `self.current_concurrency`.

4. Update `_run_with_retry()`:

```python
        outcome = self._execute_once(bundle_path, case_id, case, bundle, adapter)
        if self._is_rate_limited(outcome):
            self._rate_limited = True
            for delay_s in (1.0, 2.0):
                time.sleep(delay_s)
                outcome = self._execute_once(bundle_path, case_id, case, bundle, adapter)
                if not self._is_rate_limited(outcome):
                    break
        return self._outcome_to_exec_result(outcome, case, bundle, case_id, adapter)
```

- [ ] **Step 6: Make runner preserve stderr text for rate-limit detection**

Modify `skillhub_eval/core/schemas/report.py` `RunOutcome`:

```python
    stderr_text: str | None = None
```

Modify `LocalAgentRunner.run()`:

```python
        stderr_text = ""
```

For fake/non-stream path:

```python
            stdout, stderr_text = proc.communicate(input=prompt, timeout=timeout_s)
```

For stream path, update `_stream_until_complete()` to return `(lines, exit_code, stderr_text)` by reading `proc.stderr.read()` after process exit if available.

Return:

```python
            stderr_text=stderr_text or None,
```

Modify `_is_rate_limited()`:

```python
        blob = f"{text}\n{outcome.stderr_text or ''}".lower()
```

- [ ] **Step 7: Parallelize `_run_case_exec_phase`**

Modify `skillhub_eval/core/engine.py`:

1. Import `threading` if needed:

```python
import concurrent.futures
import threading
```

2. Add lock in `__init__`:

```python
        self._case_exec_lock = threading.Lock()
```

3. Modify `_resolve_exec_for_case()`:

```python
        with self._case_exec_lock:
            if case_id in self._case_exec_results:
                return self._case_exec_results[case_id]
        result = self._execution_source.get_actual_output(
            bundle_path,
            case_id,
            case=case,
            bundle=bundle or self._current_bundle,
        )
        with self._case_exec_lock:
            self._case_exec_results[case_id] = result
        return result
```

4. Replace `_run_case_exec_phase()` body:

```python
        if not cases:
            return
        max_workers = max(1, int(getattr(settings, "exec_concurrency", 2) or 2))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [
                pool.submit(
                    self._resolve_exec_for_case,
                    skill_bundle_path,
                    case.get("id", ""),
                    case=case,
                    bundle=bundle,
                )
                for case in cases
            ]
            for future in concurrent.futures.as_completed(futures):
                future.result()
```

- [ ] **Step 8: Pass risk-based per-case timeout into LocalAgentSource**

Where `RoutingExecutionSource` or `LocalAgentSource` is constructed, pass `timeout_s=local_agent_case_timeout_seconds(risk_locked)`. If risk is only locked after ingest/gate, update the source before case execution:

```python
        if isinstance(self._execution_source, RoutingExecutionSource):
            self._execution_source.set_local_timeout(self._local_agent_case_timeout)
```

If `RoutingExecutionSource` lacks a setter, add a focused setter that updates its internal `LocalAgentSource`.

- [ ] **Step 9: Run focused execution tests**

Run:

```powershell
pytest tests/core/test_latency.py tests/execution/test_local_agent_source.py tests/core/test_execution_source_routing.py -q
```

Expected: PASS.

---

### Task 6: Budget Progress for Local Agent UI

**Files:**
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: focused API/report tests if existing stage progress tests cover it

- [ ] **Step 1: Log local-agent budget event**

Modify `skillhub_eval/core/engine.py` just before entering `case_executing` local execution:

```python
        if self._uses_local_execution(bundle):
            repo.log_event(run_id, "stage_budget", {
                "stage": "case_executing",
                "budget_s": self._local_agent_workflow_timeout,
                "started_at": datetime.now(UTC).isoformat(),
                "agent_phase": "local_agent",
            })
```

- [ ] **Step 2: Ensure report/detail exposes budget through existing stage progress**

If `repo.get_stage_progress(run_id)` already includes eval events by stage, no schema change is needed. If it only includes `stage_timing`, add `stage_budget` handling in `SqliteRepository.get_stage_progress()`:

```python
if event_name == "stage_budget":
    progress.append({"event": "stage_budget", **payload})
```

- [ ] **Step 3: Add UI formatter**

Modify `skillhub_eval/adapters/ui/static/assets/index.js`:

```javascript
function findLocalAgentBudget(report) {
  const progress = Array.isArray(report?.stage_progress) ? report.stage_progress : [];
  return progress.find((item) => item.event === 'stage_budget' && item.stage === 'case_executing') || null;
}

function renderLocalAgentBudget(report) {
  const budget = findLocalAgentBudget(report);
  if (!budget || !budget.budget_s) return '';
  const started = budget.started_at ? Date.parse(budget.started_at) : NaN;
  const elapsed = Number.isFinite(started) ? Math.max(0, Math.floor((Date.now() - started) / 1000)) : 0;
  const total = Number(budget.budget_s) || 0;
  const remaining = Math.max(0, total - elapsed);
  return `<div class="text-xs text-blue-800 bg-blue-50 border border-blue-200 px-2 py-1 mt-2">
    本地 Agent 真跑中：已用 ${elapsed}s / 总预算 ${total}s / 剩余 ${remaining}s
  </div>`;
}
```

Call this in the active run/status rendering block that already displays formal evaluation stage cards.

- [ ] **Step 4: Run UI syntax smoke**

Run:

```powershell
node --check skillhub_eval/adapters/ui/static/assets/index.js
```

Expected: no syntax errors.

---

### Task 7: Usage Capture and Summary

**Files:**
- Create: `skillhub_eval/core/usage.py`
- Modify: `skillhub_eval/core/schemas/report.py`
- Modify: `skillhub_eval/providers/openai_compatible.py`
- Modify: `skillhub_eval/providers/deepseek.py`
- Modify: `skillhub_eval/providers/gemini.py`
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/core/divergence.py`
- Modify: `skillhub_eval/core/propagator.py`
- Modify: `skillhub_eval/core/propagation_plan_enricher.py`
- Test: `tests/core/test_usage_summary.py`

- [ ] **Step 1: Write usage summary tests**

Create `tests/core/test_usage_summary.py`:

```python
from skillhub_eval.core.usage import (
    UsageRecord,
    build_usage_summary,
    normalize_usage,
)


def test_normalize_usage_standard_keys():
    usage = normalize_usage({"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13})
    assert usage == {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}


def test_normalize_usage_legacy_keys():
    usage = normalize_usage({"input_tokens": 5, "output_tokens": 7})
    assert usage == {"prompt_tokens": 5, "completion_tokens": 7, "total_tokens": 12}


def test_build_usage_summary_groups_rows_and_totals():
    summary = build_usage_summary([
        UsageRecord(stage="model_judging", provider_label="DeepSeek", model="deepseek-chat", case_id="h1", usage={"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}),
        UsageRecord(stage="local_agent", provider_label="Cursor Agent", model="gpt-5", case_id="h1", usage={"prompt_tokens": 4, "completion_tokens": 1, "total_tokens": 5}),
    ])

    assert summary.totals.prompt_tokens == 14
    assert summary.totals.completion_tokens == 3
    assert summary.totals.total_tokens == 17
    assert summary.partial is False
    assert len(summary.by_stage) == 2
```

- [ ] **Step 2: Run usage tests and verify failure**

Run:

```powershell
pytest tests/core/test_usage_summary.py -q
```

Expected: FAIL because `skillhub_eval.core.usage` does not exist.

- [ ] **Step 3: Add report usage schemas**

Modify `skillhub_eval/core/schemas/report.py`:

```python
class TokenUsageTotals(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageSummaryRow(BaseModel):
    stage: str
    provider_label: str | None = None
    model: str | None = None
    case_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageSummary(BaseModel):
    totals: TokenUsageTotals = Field(default_factory=TokenUsageTotals)
    by_stage: list[UsageSummaryRow] = Field(default_factory=list)
    partial: bool = False
```

Add to `EvaluationReport`:

```python
    usage_summary: UsageSummary | None = None
```

- [ ] **Step 4: Implement usage module**

Create `skillhub_eval/core/usage.py`:

```python
"""Token usage normalization and report aggregation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from skillhub_eval.core.schemas.report import (
    TokenUsageTotals,
    UsageSummary,
    UsageSummaryRow,
)


@dataclass(frozen=True)
class UsageRecord:
    stage: str
    usage: dict[str, Any] | None
    provider_label: str | None = None
    model: str | None = None
    case_id: str | None = None


def normalize_usage(usage: dict[str, Any] | None) -> dict[str, int] | None:
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens", usage.get("input_tokens", 0))
    completion = usage.get("completion_tokens", usage.get("output_tokens", 0))
    total = usage.get("total_tokens")
    try:
        prompt_i = int(prompt or 0)
        completion_i = int(completion or 0)
        total_i = int(total if total is not None else prompt_i + completion_i)
    except (TypeError, ValueError):
        return None
    if prompt_i == 0 and completion_i == 0 and total_i == 0:
        return None
    return {
        "prompt_tokens": prompt_i,
        "completion_tokens": completion_i,
        "total_tokens": total_i,
    }


def build_usage_summary(records: list[UsageRecord]) -> UsageSummary:
    rows: list[UsageSummaryRow] = []
    totals = TokenUsageTotals()
    partial = False
    for record in records:
        normalized = normalize_usage(record.usage)
        if normalized is None:
            partial = True
            continue
        rows.append(
            UsageSummaryRow(
                stage=record.stage,
                provider_label=record.provider_label,
                model=record.model,
                case_id=record.case_id,
                **normalized,
            )
        )
        totals.prompt_tokens += normalized["prompt_tokens"]
        totals.completion_tokens += normalized["completion_tokens"]
        totals.total_tokens += normalized["total_tokens"]
    return UsageSummary(totals=totals, by_stage=rows, partial=partial)
```

- [ ] **Step 5: Preserve provider usage**

Modify `skillhub_eval/providers/openai_compatible.py`:

1. Add field in `__init__`:

```python
        self.last_usage: dict | None = None
```

2. Change `_chat()`:

```python
        data = resp.json()
        self.last_usage = data.get("usage") if isinstance(data.get("usage"), dict) else None
        return data["choices"][0]["message"]["content"]
```

Apply the same `self.last_usage` pattern to `DeepSeekProvider` and `GeminiProvider` in their chat/generate methods.

- [ ] **Step 6: Log judge usage in engine**

Modify `skillhub_eval/core/engine.py` in `_judge_case()` after `asyncio.gather()`:

```python
            for provider_name, provider in [("deepseek", self.ds), ("gemini", self.wb)]:
                usage = getattr(provider, "last_usage", None)
                if usage:
                    self.repo.log_event(run_id, "token_usage", {
                        "stage": "model_judging",
                        "provider": provider_name,
                        "provider_label": getattr(provider, "label", provider_name),
                        "model": getattr(provider, "model", None),
                        "case_id": case_id,
                        "usage": usage,
                    })
```

- [ ] **Step 7: Log local-agent usage and build summary**

Modify `skillhub_eval/core/engine.py` after case execution completes:

```python
        for case_id, exec_result in self._case_exec_results.items():
            if exec_result.usage:
                repo.log_event(run_id, "token_usage", {
                    "stage": "local_agent",
                    "provider_label": exec_result.agent_label,
                    "model": exec_result.model_id,
                    "case_id": case_id,
                    "usage": exec_result.usage,
                })
```

Before creating final `EvaluationReport`, aggregate:

```python
        usage_summary = self._build_usage_summary(run_id)
```

Add helper:

```python
    def _build_usage_summary(self, run_id: str):
        from skillhub_eval.core.usage import UsageRecord, build_usage_summary

        records = []
        for event in self.repo.list_events(run_id, event_name="token_usage"):
            payload = event.get("payload") or {}
            records.append(
                UsageRecord(
                    stage=str(payload.get("stage") or "unknown"),
                    provider_label=payload.get("provider_label"),
                    model=payload.get("model"),
                    case_id=payload.get("case_id"),
                    usage=payload.get("usage"),
                )
            )
        return build_usage_summary(records)
```

Add `list_events()` to `SqliteRepository`:

```python
    def list_events(self, run_id: str, event_name: str | None = None) -> list[dict]:
        query = "SELECT event_name, event_json, created_at FROM eval_events WHERE run_id=?"
        params: list[object] = [run_id]
        if event_name is not None:
            query += " AND event_name=?"
            params.append(event_name)
        query += " ORDER BY id"
        with self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        events: list[dict] = []
        for row in rows:
            payload = json.loads(row["event_json"] or "{}")
            events.append({
                "event_name": row["event_name"],
                "payload": payload,
                "created_at": row["created_at"],
            })
        return events
```

using existing `eval_events` JSON payload structure.

Set `usage_summary=usage_summary` in final reports and timeout/provider failure reports where useful.

- [ ] **Step 8: Log generate/synthesis usage**

For `propagator`, `propagation_plan_enricher`, `divergence`, `skill_summary`, and `risk_review`, use the call site that has `repo` and `run_id` when available. After provider generate/judge call:

```python
usage = getattr(provider, "last_usage", None)
if usage:
    repo.log_event(run_id, "token_usage", {
        "stage": "divergence_synthesis",
        "provider_label": getattr(provider, "label", None),
        "model": getattr(provider, "model", None),
        "case_id": case_id,
        "usage": usage,
    })
```

Use exact stage names from the design:

- `propagation_enrich`
- `divergence_synthesis`
- `skill_summary`
- `risk_review`

If a call path has no `repo/run_id`, leave it unlogged and rely on partial usage. Do not introduce broad plumbing just for non-critical paths.

- [ ] **Step 9: Run usage tests**

Run:

```powershell
pytest tests/core/test_usage_summary.py tests/core/test_engine.py -q
```

Expected: PASS or only unrelated existing failures; investigate any failure touching report schema or engine usage.

---

### Task 8: Provider Error Classification UI

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: if JS tests do not exist, use `node --check`

- [ ] **Step 1: Add classifier functions**

Modify `skillhub_eval/adapters/ui/static/assets/index.js` near provider error rendering helpers:

```javascript
function classifyProviderError(errorText) {
  const text = String(errorText || '').toLowerCase();
  if (/429|rate limit|too many requests|quota/.test(text)) return 'rate_limit';
  if (/region|country|unavailable|unsupported location|not available/.test(text)) return 'region_unavailable';
  if (/api key|apikey|unauthorized|401|403|model.*not found|invalid.*model|permission/.test(text)) return 'auth_or_model';
  if (/timeout|timed out|deadline/.test(text)) return 'timeout';
  return 'unknown';
}

function providerErrorZh(errorText) {
  const kind = classifyProviderError(errorText);
  if (kind === 'rate_limit') return '模型服务限流或配额不足，请稍后重试。';
  if (kind === 'region_unavailable') return '模型服务在当前地区或网络环境不可用，请更换可用服务或网络。';
  if (kind === 'auth_or_model') return '模型密钥、权限或模型名称配置有误，请检查 Provider 设置。';
  if (kind === 'timeout') return '模型响应超时，请稍后重试或调大超时配置。';
  return '模型服务暂不可用，请查看错误详情。';
}
```

- [ ] **Step 2: Replace hardcoded API-limit copy**

Find UI blocks that say Provider B unavailable because of API limit. Replace with:

```javascript
const errorText = providerError.error || providerError.message || '';
const copy = providerErrorZh(errorText);
```

Keep raw error details in a smaller text line if already present.

- [ ] **Step 3: Run JS syntax check**

Run:

```powershell
node --check skillhub_eval/adapters/ui/static/assets/index.js
```

Expected: no syntax errors.

---

### Task 9: Token Usage Report UI

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Test: `node --check`

- [ ] **Step 1: Add usage render helper**

Modify `skillhub_eval/adapters/ui/static/assets/index.js`:

```javascript
function renderUsageSummary(report) {
  const summary = report?.usage_summary;
  if (!summary || !summary.totals) return '';
  const rows = Array.isArray(summary.by_stage) ? summary.by_stage : [];
  const total = summary.totals.total_tokens || 0;
  const prompt = summary.totals.prompt_tokens || 0;
  const completion = summary.totals.completion_tokens || 0;
  const partial = summary.partial ? '<span class="text-amber-700 ml-2">部分调用未返回 usage</span>' : '';
  const body = rows.length
    ? rows.map((row) => `
      <tr class="border-t border-gray-100">
        <td class="py-1 pr-2">${escapeHtml(row.stage || '-')}</td>
        <td class="py-1 pr-2">${escapeHtml(row.provider_label || '-')}</td>
        <td class="py-1 pr-2">${escapeHtml(row.model || '-')}</td>
        <td class="py-1 pr-2">${escapeHtml(row.case_id || '-')}</td>
        <td class="py-1 text-right">${row.prompt_tokens || 0}</td>
        <td class="py-1 text-right">${row.completion_tokens || 0}</td>
        <td class="py-1 text-right">${row.total_tokens || 0}</td>
      </tr>`).join('')
    : '<tr><td colspan="7" class="py-2 text-gray-400">暂无分阶段 usage 明细</td></tr>';
  return `
    <section class="mt-4 border border-gray-200 bg-white">
      <div class="px-3 py-2 border-b border-gray-200 flex items-center justify-between">
        <h4 class="text-sm font-semibold text-gray-900">Token 消耗</h4>
        <div class="text-xs text-gray-600">总计 ${total}（输入 ${prompt} / 输出 ${completion}）${partial}</div>
      </div>
      <div class="px-3 py-2 overflow-x-auto">
        <table class="w-full text-xs text-left">
          <thead class="text-gray-500">
            <tr>
              <th class="py-1 pr-2">阶段</th>
              <th class="py-1 pr-2">Provider</th>
              <th class="py-1 pr-2">模型</th>
              <th class="py-1 pr-2">Case</th>
              <th class="py-1 text-right">输入</th>
              <th class="py-1 text-right">输出</th>
              <th class="py-1 text-right">总计</th>
            </tr>
          </thead>
          <tbody>${body}</tbody>
        </table>
      </div>
    </section>`;
}
```

- [ ] **Step 2: Insert usage block into report detail**

In report detail/modal rendering, after provider summary or model vote feedback, insert:

```javascript
${renderUsageSummary(detail || report)}
```

Use the same payload object used by `renderModelVotesFeedback()`.

- [ ] **Step 3: Run JS syntax check**

Run:

```powershell
node --check skillhub_eval/adapters/ui/static/assets/index.js
```

Expected: no syntax errors.

---

### Task 10: Env Docs and Focused Verification

**Files:**
- Modify: `.env.example`
- Optional modify: `docs/runbooks/local-agent-exec-validation.md`

- [ ] **Step 1: Update `.env.example`**

Add:

```dotenv
# Local agent selection
EXEC_MODEL=default

# Per-case local-agent timeout budgets, separate from whole local-agent workflow budgets.
LOCAL_AGENT_CASE_TIMEOUT_LOW_S=600
LOCAL_AGENT_CASE_TIMEOUT_MEDIUM_S=900
LOCAL_AGENT_CASE_TIMEOUT_HIGH_S=1800
```

- [ ] **Step 2: Update local agent runbook if it still names only three agents**

Modify `docs/runbooks/local-agent-exec-validation.md`:

Replace:

```markdown
At least one CLI agent on `PATH`: `claude`, `codex`, or `cursor-agent`
```

with:

```markdown
At least one supported CLI agent on `PATH`: `claude`, `codex`, `cursor-agent`, `traecli`/`trae`, or `agy`.
```

Replace preference line:

```markdown
set `EXEC_SOURCE=local` and `EXEC_AGENT=claude|codex|cursor-agent`
```

with:

```markdown
set `EXEC_SOURCE=local`, `EXEC_AGENT=claude|codex|cursor-agent|trae|antigravity`, and optionally `EXEC_MODEL=<model-id>`.
```

- [ ] **Step 3: Run focused backend tests**

Run:

```powershell
pytest tests/execution/test_agent_registry.py tests/execution/test_adapter_trae.py tests/execution/test_adapter_antigravity.py tests/execution/test_preferences.py tests/execution/test_local_agent_source.py tests/adapters/test_exec_bridge_api.py tests/core/test_usage_summary.py tests/core/test_latency.py -q
```

Expected: PASS.

- [ ] **Step 4: Run frontend syntax check**

Run:

```powershell
node --check skillhub_eval/adapters/ui/static/assets/index.js
```

Expected: no syntax errors.

- [ ] **Step 5: Run encoding guard**

Run:

```powershell
python scripts/check_doc_encoding.py
```

Expected: `doc encoding OK`.

- [ ] **Step 6: Inspect git diff**

Run:

```powershell
git status --short
git diff --stat
```

Expected:

- Only planned files changed plus the already-existing untracked Chinese guide file from before this work.
- No generated cache, DB, report JSON, or local secrets included.

---

## Self-Review Checklist

- [ ] Agent registry covers Claude, Codex, Cursor Agent, Trae, and Antigravity.
- [ ] UI can choose agent and model separately.
- [ ] `default` model means no model argument/config override.
- [ ] Formal eval still runs only one selected agent/model per run.
- [ ] Multi-agent comparison is not implemented.
- [ ] Redline hardening is capability-based and currently true only for Codex.
- [ ] `case_executing` uses bounded concurrency and per-case timeout.
- [ ] Rate-limit detection downgrades current-run concurrency to 1 and retries.
- [ ] Provider B unavailable copy is classified by cause.
- [ ] Provider usage and local-agent usage aggregate into report `usage_summary`.
- [ ] Usage details are persisted as `eval_events` with `event_name='token_usage'`.
- [ ] Focused backend tests and JS syntax check pass.
- [ ] Documentation encoding guard passes.
