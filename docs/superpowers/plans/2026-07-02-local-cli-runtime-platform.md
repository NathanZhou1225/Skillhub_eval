# Local CLI Runtime Platform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a reusable product-grade local CLI runtime platform for Codex, Cursor Agent, Trae, Claude, and Antigravity while keeping SkillHub's existing scoring and review pipeline unchanged.

**Architecture:** Add a runtime layer below `LocalAgentSource` and above per-CLI adapters. The runtime layer owns runtime metadata, readiness, preflight, skill injection, event normalization, and failure taxonomy; the existing engine still consumes `ExecResult` and runs the current judge/report/expert flow.

**Rollout rule:** This is one productized runtime-platform change. Implementation is staged and compatibility-first, but final delivery routes formal local evaluation through the new runtime platform after all five runtime adapter equivalence tests pass.

**Tech Stack:** Python 3, FastAPI routes under `skillhub_eval/adapters/api/routes`, Pydantic schemas, pytest, existing vanilla JS UI in `skillhub_eval/adapters/ui/static/assets/index.js`, SQLite-backed existing persistence/event logs.

---

## Current Status (2026-07-07)

This plan guided the implementation, while `openspec/changes/local-cli-runtime-platform/tasks.md` is the current task-tracking source of truth.

Completed platform foundation:

- Runtime catalog/contract and compatibility bridge for Codex, Cursor Agent, Trae, Claude, and Antigravity.
- Normalized `AgentEvent` path for all five adapters, with `ExecResult` built from normalized events.
- Runtime fingerprinting and SQLite-backed `runtime_preflight_cache` with 24-hour TTL and invalidation.
- Skill injection strategies with prompt fallback and argv prompt-size guard.
- Preflight runner, API action, cached status, and formal local-evaluation gate.
- Runtime failure taxonomy persisted through events/report rows and surfaced in basic UI labels.
- Basic report-detail preflight action and Q-28 requested-vs-actual runtime attribution preserved.

Verified so far:

- `pytest tests/execution tests/core tests/adapters/test_exec_bridge_api.py -q --basetemp .tmp/pytest-runtime-platform-broad1` → `589 passed, 6 skipped`.
- `node --check skillhub_eval/adapters/ui/static/assets/index.js` passed.
- `python scripts/check_doc_encoding.py` passed before this status update and should be rerun after documentation edits.

Not yet claimed complete:

- User website/live workflow test is pending.
- Real sanitized stream fixtures for all five runtimes are not yet fixed into tests.
- Raw stream capture and sanitizer workflow are not yet productized.
- Full readiness/preflight UI cards and explicit "switch to verified runtime and rerun" are not complete.
- Runbook update and OpenSpec archive are still pending.

---

## Implementation Rules

- Do not change judge scoring, R1-R8, thresholds, expert review, or report aggregation semantics.
- Do not auto-switch runtimes. Only explicit user action can switch runtime/model.
- Do not auto-install, login, repair, or mutate third-party CLI configs.
- Do not create git commits unless the user explicitly asks.
- Preserve existing Q-28 report attribution semantics: requested runtime/model and actual successful runtime/model remain distinct.
- Keep live CLI tests opt-in. Default test suite must not require local CLIs or network/model access.

## File Structure

### New Files

- `skillhub_eval/execution/runtime_defs.py`  
  Runtime contract dataclasses, builtin runtime catalog, compatibility bridge from existing `AgentDef`.

- `skillhub_eval/execution/runtime_fingerprint.py`  
  Stable fingerprint builders for runtime id, model id, skill fingerprint, CLI path, CLI version, runtime definition, and SkillHub version.

- `skillhub_eval/execution/events.py`  
  Normalized `AgentEvent` models and helper conversion utilities.

- `skillhub_eval/execution/exec_result_builder.py`  
  Builds `ParsedStream`/`ExecResult` from normalized events and workspace artifacts.

- `skillhub_eval/execution/skill_injection.py`  
  Native, file-placed, and prompt injection strategy selection and preparation.

- `skillhub_eval/execution/preflight.py`  
  `PreflightRunner`, preflight result schema, failure mapping, and fixture validation.

- `skillhub_eval/execution/preflight_cache.py`  
  Repository-facing helpers for reading SQLite-backed preflight pass/fail state with 24-hour TTL and fingerprint invalidation.

- `tests/execution/test_runtime_defs.py`
- `tests/execution/test_runtime_fingerprint.py`
- `tests/execution/test_events.py`
- `tests/execution/test_exec_result_builder.py`
- `tests/execution/test_skill_injection.py`
- `tests/execution/test_preflight.py`
- `tests/persistence/test_runtime_preflight_cache.py`
- `tests/fixtures/runtime_streams/cursor_agent_fixture.jsonl`
- `tests/fixtures/runtime_streams/trae_fixture.jsonl`
- `tests/fixtures/runtime_streams/codex_fixture.jsonl`
- `tests/fixtures/runtime_streams/claude_fixture.jsonl`
- `tests/fixtures/runtime_streams/antigravity_fixture.txt`

### Existing Files To Modify

- `skillhub_eval/execution/agent_registry.py`  
  Keep public compatibility while moving richer runtime metadata to `runtime_defs.py`.

- `skillhub_eval/execution/detection.py`  
  Return runtime readiness details and version/invocation status.

- `skillhub_eval/execution/models.py`  
  Preserve live/fallback/stale/custom model behavior and expose readiness mapping.

- `skillhub_eval/execution/runner.py`  
  Distinguish process timeout, CLI crash, and completion-event missing.

- `skillhub_eval/execution/local_agent_source.py`  
  Gate formal local execution on preflight and route execution through runtime contract.

- `skillhub_eval/persistence/sqlite.py`  
  Add `runtime_preflight_cache` table and repository methods. Bump schema version through the existing `PRAGMA user_version` migration pattern.

- `skillhub_eval/execution/stream_parser.py`  
  Consume normalized `AgentEvent` for generic stream assembly while preserving compatibility wrappers.

- `skillhub_eval/execution/adapters/cursor_agent.py`
- `skillhub_eval/execution/adapters/trae.py`
- `skillhub_eval/execution/adapters/codex.py`
- `skillhub_eval/execution/adapters/claude.py`
- `skillhub_eval/execution/adapters/antigravity.py`  
  Add or adapt event normalizers.

- `skillhub_eval/adapters/api/routes/exec.py`  
  Expand scan/test API, add preflight endpoint/action, and expose readiness/preflight status.

- `skillhub_eval/adapters/ui/static/assets/index.js`  
  Render runtime readiness cards, preflight action, explicit switch/retry action, and failure messages.

- `docs/runbooks/local-agent-exec-validation.md`  
  Document runtime platform usage and troubleshooting.

---

## Task 1: Runtime Contract Foundation

**Files:**
- Create: `skillhub_eval/execution/runtime_defs.py`
- Create: `tests/execution/test_runtime_defs.py`
- Modify: `skillhub_eval/execution/agent_registry.py`
- Modify: existing local execution preference persistence tests if present.

- [ ] **Step 1: Write runtime definition tests**

Add `tests/execution/test_runtime_defs.py`:

```python
from skillhub_eval.execution.runtime_defs import (
    PromptTransport,
    SkillInjectionStrategy,
    get_runtime_catalog,
    get_runtime_def,
)


def test_builtin_runtime_catalog_contains_five_productized_runtimes():
    ids = {rt.runtime_id for rt in get_runtime_catalog()}

    assert {"codex", "cursor-agent", "trae", "claude", "antigravity"} <= ids


def test_runtime_def_has_required_contract_fields():
    trae = get_runtime_def("trae")

    assert trae is not None
    assert trae.label == "Trae"
    assert trae.binary.primary
    assert trae.launch.prompt_transport in {
        PromptTransport.STDIN,
        PromptTransport.ARGV,
        PromptTransport.PROMPT_FILE,
    }
    assert SkillInjectionStrategy.PROMPT in trae.skill_injection.fallbacks
    assert trae.preflight.fixture_id == "exec-fixture-minimal"


def test_runtime_alias_lookup_preserves_existing_agent_ids():
    assert get_runtime_def("cursor_agent").runtime_id == "cursor-agent"
    assert get_runtime_def("ta").runtime_id == "trae"


def test_runtime_catalog_has_unique_ids():
    ids = [rt.runtime_id for rt in get_runtime_catalog()]

    assert len(ids) == len(set(ids))
```

Run: `pytest tests/execution/test_runtime_defs.py -q`  
Expected: FAIL because `runtime_defs.py` does not exist.

- [ ] **Step 2: Add runtime contract implementation**

Create `skillhub_eval/execution/runtime_defs.py`:

```python
"""Declarative local CLI runtime definitions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Callable

from skillhub_eval.execution.agent_registry import DEFAULT_MODEL_ID, ModelOption


class PromptTransport(StrEnum):
    STDIN = "stdin"
    ARGV = "argv"
    PROMPT_FILE = "prompt_file"


class SkillInjectionStrategy(StrEnum):
    NATIVE = "native"
    FILE_PLACED = "file_placed"
    PROMPT = "prompt"


@dataclass(frozen=True)
class RuntimeBinary:
    primary: str
    aliases: tuple[str, ...] = ()
    install_dir_globs: tuple[str, ...] = ()
    version_args: tuple[str, ...] = ("--version",)

    @property
    def names(self) -> tuple[str, ...]:
        return (self.primary, *self.aliases)


@dataclass(frozen=True)
class RuntimeModels:
    fallback_models: tuple[ModelOption, ...]
    model_probe: tuple[str, ...] | None = None
    fallback_model_probes: tuple[tuple[str, ...], ...] = ()


@dataclass(frozen=True)
class RuntimeLaunch:
    prompt_transport: PromptTransport = PromptTransport.STDIN
    stream_format: str = "stream-json"
    supports_hardened_redline: bool = False


@dataclass(frozen=True)
class RuntimeSkillInjection:
    preferred: SkillInjectionStrategy
    fallbacks: tuple[SkillInjectionStrategy, ...] = (SkillInjectionStrategy.PROMPT,)

    def ordered(self) -> tuple[SkillInjectionStrategy, ...]:
        seen: set[SkillInjectionStrategy] = set()
        ordered: list[SkillInjectionStrategy] = []
        for item in (self.preferred, *self.fallbacks, SkillInjectionStrategy.PROMPT):
            if item not in seen:
                ordered.append(item)
                seen.add(item)
        return tuple(ordered)


@dataclass(frozen=True)
class RuntimePreflightProfile:
    fixture_id: str = "exec-fixture-minimal"
    requires_entrypoint_evidence: bool = True
    requires_structured_output: bool = True


@dataclass(frozen=True)
class RuntimeDef:
    runtime_id: str
    label: str
    binary: RuntimeBinary
    models: RuntimeModels
    launch: RuntimeLaunch = field(default_factory=RuntimeLaunch)
    skill_injection: RuntimeSkillInjection = field(
        default_factory=lambda: RuntimeSkillInjection(SkillInjectionStrategy.PROMPT)
    )
    preflight: RuntimePreflightProfile = field(default_factory=RuntimePreflightProfile)
    config_dirs: tuple[str, ...] = ()
    aliases: tuple[str, ...] = ()
    install_docs_url: str | None = None
    install_command: str | None = None


_DEFAULT_MODEL = ModelOption(DEFAULT_MODEL_ID, "Default")


_RUNTIMES: tuple[RuntimeDef, ...] = (
    RuntimeDef(
        runtime_id="claude",
        label="Claude",
        binary=RuntimeBinary(primary="claude"),
        models=RuntimeModels(fallback_models=(_DEFAULT_MODEL,)),
        config_dirs=(".claude",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.NATIVE),
    ),
    RuntimeDef(
        runtime_id="codex",
        label="Codex",
        binary=RuntimeBinary(primary="codex", install_dir_globs=("OpenAI/Codex/bin/*",)),
        models=RuntimeModels(fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5-codex", "GPT-5 Codex"))),
        config_dirs=(".codex",),
        launch=RuntimeLaunch(supports_hardened_redline=True),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.NATIVE),
    ),
    RuntimeDef(
        runtime_id="cursor-agent",
        label="Cursor Agent",
        binary=RuntimeBinary(primary="cursor-agent", install_dir_globs=("cursor-agent/versions/*",)),
        models=RuntimeModels(
            fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5", "GPT-5")),
            model_probe=("models",),
            fallback_model_probes=(("--list-models",),),
        ),
        config_dirs=(".cursor",),
        aliases=("cursor_agent",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.FILE_PLACED),
    ),
    RuntimeDef(
        runtime_id="trae",
        label="Trae",
        binary=RuntimeBinary(
            primary="trae-cli",
            aliases=("traecli", "trae-agent", "ta"),
            install_dir_globs=("trae-cli/bin",),
        ),
        models=RuntimeModels(fallback_models=(_DEFAULT_MODEL,), model_probe=("models",)),
        launch=RuntimeLaunch(prompt_transport=PromptTransport.ARGV),
        config_dirs=(".trae",),
        aliases=("ta",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.PROMPT),
    ),
    RuntimeDef(
        runtime_id="antigravity",
        label="Antigravity",
        binary=RuntimeBinary(primary="agy"),
        models=RuntimeModels(fallback_models=(_DEFAULT_MODEL,)),
        config_dirs=(".gemini/antigravity-cli",),
        skill_injection=RuntimeSkillInjection(SkillInjectionStrategy.PROMPT),
    ),
)


def get_runtime_catalog() -> list[RuntimeDef]:
    return list(_RUNTIMES)


def get_runtime_def(runtime_id: str) -> RuntimeDef | None:
    raw = (runtime_id or "").strip()
    for runtime in _RUNTIMES:
        if raw == runtime.runtime_id or raw in runtime.aliases:
            return runtime
    return None
```

- [ ] **Step 3: Run runtime definition tests**

Run: `pytest tests/execution/test_runtime_defs.py -q`  
Expected: PASS.

- [ ] **Step 4: Bridge existing `AgentDef` users without behavior change**

Modify `skillhub_eval/execution/agent_registry.py` only if needed to expose runtime ids consistently. Keep existing `get_agent_def`, `resolve_adapter`, and `fallback_models_for` signatures unchanged. Add a small test later if any compatibility behavior changes.

Run: `pytest tests/execution/test_runtime_defs.py tests/execution/test_detection.py tests/execution/test_models.py -q`  
Expected: PASS.

- [ ] **Step 6: Assert project definitions do not store machine state**

Add a test that loads the runtime catalog, simulates a resolved CLI path and selected runtime/model preference, then reloads the catalog and asserts the catalog still contains only project-level defaults.

Machine/user state includes:

- resolved CLI path
- selected runtime/model
- auth/readiness probe result
- preflight cache
- one-click switch preference

These values must live in existing local storage/preferences/SQLite, not in `RuntimeDef`.

Run: relevant preference persistence tests plus `pytest tests/execution/test_runtime_defs.py -q`  
Expected: PASS.

---

## Task 2: Runtime Fingerprint and SQLite Preflight Cache

**Files:**
- Create: `skillhub_eval/execution/runtime_fingerprint.py`
- Create: `skillhub_eval/execution/preflight_cache.py`
- Create: `tests/execution/test_runtime_fingerprint.py`
- Create/modify: `tests/persistence/test_runtime_preflight_cache.py`
- Modify: `skillhub_eval/persistence/sqlite.py`

- [ ] **Step 1: Write fingerprint tests**

Add `tests/execution/test_runtime_fingerprint.py`:

```python
from skillhub_eval.execution.runtime_defs import get_runtime_def
from skillhub_eval.execution.runtime_fingerprint import runtime_fingerprint, skill_fingerprint


def test_runtime_fingerprint_is_stable_for_same_inputs():
    runtime = get_runtime_def("cursor-agent")

    first = runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="C:/cli/cursor-agent.exe",
        cli_version="cursor-agent 1.2.3",
        skillhub_version="0.1-test",
    )
    second = runtime_fingerprint(
        runtime,
        model_id="gpt-5",
        cli_path="C:/cli/cursor-agent.exe",
        cli_version="cursor-agent 1.2.3",
        skillhub_version="0.1-test",
    )

    assert first == second


def test_runtime_fingerprint_changes_when_model_changes():
    runtime = get_runtime_def("cursor-agent")

    first = runtime_fingerprint(runtime, model_id="gpt-5", cli_path="p", cli_version="v", skillhub_version="s")
    second = runtime_fingerprint(runtime, model_id="default", cli_path="p", cli_version="v", skillhub_version="s")

    assert first != second


def test_skill_fingerprint_changes_when_skill_content_changes(tmp_path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text("v1", encoding="utf-8")
    first = skill_fingerprint(skill_dir)

    skill_md.write_text("v2", encoding="utf-8")
    second = skill_fingerprint(skill_dir)

    assert first != second
```

Run: `pytest tests/execution/test_runtime_fingerprint.py -q`  
Expected: FAIL because module does not exist.

- [ ] **Step 2: Implement fingerprint builder**

Create `skillhub_eval/execution/runtime_fingerprint.py`:

```python
"""Stable fingerprinting for runtime and skill preflight cache entries."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from skillhub_eval.execution.runtime_defs import RuntimeDef


def runtime_fingerprint(
    runtime: RuntimeDef,
    *,
    model_id: str,
    cli_path: str | None,
    cli_version: str | None,
    skillhub_version: str,
) -> str:
    payload = {
        "runtime": asdict(runtime),
        "model_id": model_id or "default",
        "cli_path": cli_path or "",
        "cli_version": cli_version or "",
        "skillhub_version": skillhub_version or "",
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def skill_fingerprint(skill_dir: str | Path) -> str:
    root = Path(skill_dir)
    hasher = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if any(part in {".git", "__pycache__", ".pytest_cache"} for part in path.parts):
            continue
        hasher.update(rel.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(path.read_bytes())
        hasher.update(b"\0")
    return hasher.hexdigest()
```

Run: `pytest tests/execution/test_runtime_fingerprint.py -q`  
Expected: PASS.

- [ ] **Step 3: Write SQLite preflight cache persistence tests**

Add `tests/persistence/test_runtime_preflight_cache.py`:

```python
import sqlite3

from skillhub_eval.persistence.sqlite import SqliteRepository


def test_init_db_migration_to_v12_creates_runtime_preflight_cache(tmp_path):
    db_path = str(tmp_path / "v12.db")
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA user_version = 11")

    repo = SqliteRepository(db_path)
    repo.init_db()

    with sqlite3.connect(db_path) as conn:
        version = conn.execute("PRAGMA user_version").fetchone()[0]
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='runtime_preflight_cache'"
        ).fetchone()

    assert version >= 12
    assert table is not None


def test_upsert_and_get_runtime_preflight_cache_survives_new_repo(tmp_path):
    db_path = str(tmp_path / "preflight.db")
    repo = SqliteRepository(db_path)
    repo.init_db()

    repo.upsert_runtime_preflight(
        runtime_id="cursor-agent",
        model_id="gpt-5",
        skill_fingerprint="skill-123",
        fingerprint="abc",
        status="passed",
        cli_path="C:/cursor-agent.exe",
        cli_version="cursor-agent 1.0",
        checked_at="2026-07-02T00:00:00+00:00",
        expires_at="2026-07-03T00:00:00+00:00",
        failure_reason=None,
        message_zh="预检通过。",
        manual_hint=None,
        evidence={"command_observed": True},
    )

    loaded = SqliteRepository(db_path).get_runtime_preflight(
        runtime_id="cursor-agent",
        model_id="gpt-5",
        skill_fingerprint="skill-123",
    )

    assert loaded["fingerprint"] == "abc"
    assert loaded["evidence"]["command_observed"] is True
```

Run: `pytest tests/persistence/test_runtime_preflight_cache.py -q`  
Expected: FAIL because table/repository methods do not exist.

- [ ] **Step 4: Implement SQLite table and repository methods**

In `skillhub_eval/persistence/sqlite.py`:

1. Bump `SCHEMA_VERSION` from 11 to 12.
2. Add `CREATE TABLE IF NOT EXISTS runtime_preflight_cache`.
3. Add migration branch `if version < 12`.
4. Add repository methods `upsert_runtime_preflight()` and `get_runtime_preflight()`.

Use this table shape:

```sql
CREATE TABLE IF NOT EXISTS runtime_preflight_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    runtime_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    skill_fingerprint TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    cli_path TEXT,
    cli_version TEXT,
    checked_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    failure_reason TEXT,
    message_zh TEXT,
    manual_hint TEXT,
    evidence_json TEXT DEFAULT '{}',
    UNIQUE(runtime_id, model_id, skill_fingerprint)
)
```

Run: `pytest tests/persistence/test_runtime_preflight_cache.py -q`  
Expected: PASS.

- [ ] **Step 5: Add repository-facing preflight cache helper**

Create `skillhub_eval/execution/preflight_cache.py` as a thin helper over `SqliteRepository`, not an in-memory authority:

```python
"""SQLite-backed runtime preflight cache helpers."""

from __future__ import annotations

from datetime import datetime, timezone

from skillhub_eval.persistence.sqlite import SqliteRepository


def get_valid_runtime_preflight(
    repo: SqliteRepository,
    *,
    runtime_id: str,
    model_id: str,
    skill_fingerprint: str,
    fingerprint: str,
    now: datetime | None = None,
) -> dict | None:
    row = repo.get_runtime_preflight(
        runtime_id=runtime_id,
        model_id=model_id,
        skill_fingerprint=skill_fingerprint,
    )
    if row is None:
        return None
    if row.get("fingerprint") != fingerprint:
        return None
    expires_at = datetime.fromisoformat(row["expires_at"])
    current = now or datetime.now(timezone.utc)
    if current >= expires_at:
        return None
    return row if row.get("status") == "passed" else None
```

Run: `pytest tests/persistence/test_runtime_preflight_cache.py tests/execution/test_runtime_fingerprint.py -q`  
Expected: PASS.

---

## Task 3: Unified AgentEvent Schema and ExecResult Builder

**Files:**
- Create: `skillhub_eval/execution/events.py`
- Create: `skillhub_eval/execution/exec_result_builder.py`
- Create: `tests/execution/test_events.py`
- Create: `tests/execution/test_exec_result_builder.py`
- Modify: `skillhub_eval/execution/stream_parser.py`

- [ ] **Step 1: Write event schema tests**

Add `tests/execution/test_events.py`:

```python
from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload


def test_tool_result_event_has_flat_evidence_shape():
    event = AgentEvent(
        type=AgentEventType.TOOL_RESULT,
        payload=ToolResultPayload(
            tool="Bash",
            command="python scripts/run.py",
            stdout='{"ok": true}',
            stderr="",
            exit_code=0,
            is_error=False,
            correlation_id="call-1",
        ),
    )

    assert event.payload.command == "python scripts/run.py"
    assert event.payload.exit_code == 0
```

Run: `pytest tests/execution/test_events.py -q`  
Expected: FAIL because module does not exist.

- [ ] **Step 2: Implement `events.py`**

Create `skillhub_eval/execution/events.py`:

```python
"""Normalized agent event model used by local CLI runtimes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AgentEventType(StrEnum):
    TEXT_DELTA = "text_delta"
    THINKING = "thinking"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    FILE_WRITE = "file_write"
    USAGE = "usage"
    DONE = "done"
    ERROR = "error"
    RAW_UNSUPPORTED = "raw_unsupported"


@dataclass(frozen=True)
class ToolResultPayload:
    tool: str | None = None
    command: str | None = None
    stdout: str | None = None
    stderr: str | None = None
    exit_code: int | None = None
    is_error: bool = False
    correlation_id: str | None = None


@dataclass(frozen=True)
class AgentEvent:
    type: AgentEventType
    payload: Any = None
```

Run: `pytest tests/execution/test_events.py -q`  
Expected: PASS.

- [ ] **Step 3: Write event-to-ParsedStream tests**

Add `tests/execution/test_exec_result_builder.py`:

```python
from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload
from skillhub_eval.execution.exec_result_builder import parsed_stream_from_events


def test_parsed_stream_from_events_collects_text_usage_and_tool_results():
    parsed = parsed_stream_from_events([
        AgentEvent(AgentEventType.TEXT_DELTA, "hello "),
        AgentEvent(AgentEventType.TOOL_RESULT, ToolResultPayload(
            tool="Bash",
            command="python scripts/run.py",
            stdout='{"ok": true}',
            stderr="",
            exit_code=0,
            is_error=False,
        )),
        AgentEvent(AgentEventType.USAGE, {"input_tokens": 1, "output_tokens": 2}),
        AgentEvent(AgentEventType.DONE, {"duration_ms": 123}),
    ])

    assert parsed.final_text == "hello "
    assert parsed.is_complete is True
    assert parsed.usage == {"input_tokens": 1, "output_tokens": 2}
    assert parsed.tool_results[0]["command"] == "python scripts/run.py"


def test_parsed_stream_from_error_event_is_not_complete():
    parsed = parsed_stream_from_events([
        AgentEvent(AgentEventType.ERROR, "usage limit"),
    ])

    assert parsed.is_complete is False
    assert parsed.is_error is True
    assert parsed.error_text == "usage limit"
```

Run: `pytest tests/execution/test_exec_result_builder.py -q`  
Expected: FAIL because module does not exist.

- [ ] **Step 4: Implement event-to-ParsedStream builder**

Create `skillhub_eval/execution/exec_result_builder.py`:

```python
"""Build SkillHub execution results from normalized agent events."""

from __future__ import annotations

from dataclasses import asdict

from skillhub_eval.core.schemas.report import ParsedStream
from skillhub_eval.execution.events import AgentEvent, AgentEventType, ToolResultPayload


def parsed_stream_from_events(events: list[AgentEvent]) -> ParsedStream:
    text_parts: list[str] = []
    tool_results: list[dict] = []
    usage: dict | None = None
    duration_ms: int | None = None
    is_complete = False
    is_error = False
    error_text: str | None = None

    for event in events:
        if event.type == AgentEventType.TEXT_DELTA and isinstance(event.payload, str):
            text_parts.append(event.payload)
        elif event.type == AgentEventType.TOOL_RESULT:
            payload = event.payload
            if isinstance(payload, ToolResultPayload):
                tool_results.append(asdict(payload))
            elif isinstance(payload, dict):
                tool_results.append(payload)
        elif event.type == AgentEventType.USAGE and isinstance(event.payload, dict):
            usage = event.payload
        elif event.type == AgentEventType.DONE:
            is_complete = True
            if isinstance(event.payload, dict) and event.payload.get("duration_ms") is not None:
                duration_ms = int(event.payload["duration_ms"])
        elif event.type == AgentEventType.ERROR:
            is_error = True
            error_text = str(event.payload or "")

    return ParsedStream(
        final_text="".join(text_parts),
        tool_results=tool_results,
        usage=usage,
        duration_ms=duration_ms,
        is_complete=is_complete,
        is_error=is_error,
        error_text=error_text,
    )
```

Run: `pytest tests/execution/test_events.py tests/execution/test_exec_result_builder.py -q`  
Expected: PASS.

---

## Task 4: Adapter Event Normalizers (Compatibility-First)

**Files:**
- Modify: `skillhub_eval/execution/adapters/cursor_agent.py`
- Modify: `skillhub_eval/execution/adapters/trae.py`
- Modify: `skillhub_eval/execution/adapters/codex.py`
- Modify: `skillhub_eval/execution/adapters/claude.py`
- Modify: `skillhub_eval/execution/adapters/antigravity.py`
- Create fixtures under `tests/fixtures/runtime_streams/`
- Modify tests under `tests/execution/test_adapter_*.py`

- [ ] **Step 1: Add Cursor fixture test**

Add or extend `tests/execution/test_adapter_cursor_agent.py`:

```python
from skillhub_eval.execution.adapters.cursor_agent import CursorAgentAdapter
from skillhub_eval.execution.events import AgentEventType


def test_cursor_agent_normalize_events_from_real_tool_call_shape():
    lines = [
        '{"type":"tool_call","subtype":"completed","tool_call":{"shellToolCall":{"args":{"command":"python scripts/run.py"},"result":{"success":{"exitCode":0,"stdout":"{\\"ok\\": true}\\n","stderr":""}}}}}',
        '{"type":"result","subtype":"success","is_error":false,"result":"```json\\n{\\"ok\\": true}\\n```","usage":{"input_tokens":1},"duration_ms":42}',
    ]

    events = CursorAgentAdapter().normalize_events(lines)

    assert any(e.type == AgentEventType.TOOL_RESULT and e.payload.command == "python scripts/run.py" for e in events)
    assert any(e.type == AgentEventType.DONE for e in events)
```

Run: `pytest tests/execution/test_adapter_cursor_agent.py -q`  
Expected: FAIL until `normalize_events` exists.

- [ ] **Step 2: Implement Cursor `normalize_events` and preserve `parse_stream`**

In `skillhub_eval/execution/adapters/cursor_agent.py`, add `normalize_events(self, lines)` while preserving the current `parse_stream()` output. Add a compatibility test comparing the current `parse_stream(lines)` output to `parsed_stream_from_events(adapter.normalize_events(lines))`. Only after that test passes should `parse_stream()` delegate to the normalized event path. Preserve the current D14 behavior. The implementation should reuse `_normalize_tool_call_event()` and emit:

```python
AgentEvent(AgentEventType.TOOL_RESULT, ToolResultPayload(...))
AgentEvent(AgentEventType.TEXT_DELTA, text)
AgentEvent(AgentEventType.USAGE, usage)
AgentEvent(AgentEventType.DONE, {"duration_ms": duration_ms})
AgentEvent(AgentEventType.ERROR, error_text)
```

Run: `pytest tests/execution/test_adapter_cursor_agent.py tests/execution/test_exec_result_builder.py -q`  
Expected: PASS.

- [ ] **Step 3: Add Trae fixture test**

Add or extend `tests/execution/test_adapter_trae.py`:

```python
from skillhub_eval.execution.adapters.trae import TraeAdapter
from skillhub_eval.execution.events import AgentEventType


def test_trae_normalize_events_correlates_tool_call_and_tool_result():
    lines = [
        '{"type":"assistant","message":{"tool_calls":[{"id":"call-1","function":{"name":"Bash","arguments":"{\\"command\\": \\"python scripts/run.py\\"}"}}]}}',
        '{"type":"user","subtype":"tool_result","tool_use_id":"call-1","tool_name":"Bash","content":{"structured_content":{"stdout":"{\\"ok\\": true}\\n","stderr":"","exit_code":0},"is_error":false}}',
        '{"type":"result","subtype":"success","is_error":false,"result":"```json\\n{\\"ok\\": true}\\n```","duration_ms":50}',
    ]

    events = TraeAdapter().normalize_events(lines)

    assert any(e.type == AgentEventType.TOOL_RESULT and e.payload.command == "python scripts/run.py" for e in events)
    assert any(e.type == AgentEventType.DONE for e in events)
```

Run: `pytest tests/execution/test_adapter_trae.py -q`  
Expected: FAIL until `normalize_events` exists.

- [ ] **Step 4: Implement Trae `normalize_events` and preserve `parse_stream`**

In `skillhub_eval/execution/adapters/trae.py`, keep current `_extract_bash_commands()` and `_normalize_tool_result_event()` behavior, but emit `AgentEvent`s first. Add a compatibility test comparing current `parse_stream(lines)` output to `parsed_stream_from_events(adapter.normalize_events(lines))`. Only after that test passes should `parse_stream()` delegate to the normalized event path.

Run: `pytest tests/execution/test_adapter_trae.py tests/execution/test_exec_result_builder.py -q`  
Expected: PASS.

- [ ] **Step 5: Add compatibility normalizers for Codex, Claude, Antigravity**

For each of `codex.py`, `claude.py`, and `antigravity.py`:

1. Add `normalize_events(self, lines: list[str]) -> list[AgentEvent]`.
2. Add an equivalence test proving `parse_stream(lines)` and `parsed_stream_from_events(normalize_events(lines))` match on final text, tool results, usage, duration, completion, and error flags.
3. Only after the equivalence test passes, wrap current parser behavior so `parse_stream` returns the same `ParsedStream` through the normalized event path.

Run: `pytest tests/execution/test_adapter_codex.py tests/execution/test_adapter_claude.py tests/execution/test_adapter_antigravity.py -q`  
Expected: PASS.

---

## Task 5: Skill Injection Layer

**Files:**
- Create: `skillhub_eval/execution/skill_injection.py`
- Create: `tests/execution/test_skill_injection.py`
- Modify: `skillhub_eval/execution/harness_prompt.py` only if prompt composition needs a hook.

- [ ] **Step 1: Write skill injection tests**

Add `tests/execution/test_skill_injection.py`:

```python
from pathlib import Path

from skillhub_eval.execution.runtime_defs import SkillInjectionStrategy, get_runtime_def
from skillhub_eval.execution.skill_injection import choose_injection_strategy, prepare_prompt_injection


def test_choose_injection_strategy_falls_back_to_prompt():
    runtime = get_runtime_def("trae")

    assert choose_injection_strategy(runtime, available={SkillInjectionStrategy.PROMPT}) == SkillInjectionStrategy.PROMPT


def test_prepare_prompt_injection_reads_skill_md(tmp_path: Path):
    skill_dir = tmp_path / "skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("# Demo Skill\n\nUse the script.", encoding="utf-8")

    text = prepare_prompt_injection(skill_dir)

    assert "# Demo Skill" in text
```

Run: `pytest tests/execution/test_skill_injection.py -q`  
Expected: FAIL because module does not exist.

- [ ] **Step 2: Implement skill injection**

Create `skillhub_eval/execution/skill_injection.py`:

```python
"""Skill instruction injection strategies for local runtimes."""

from __future__ import annotations

from pathlib import Path

from skillhub_eval.execution.runtime_defs import RuntimeDef, SkillInjectionStrategy


def choose_injection_strategy(
    runtime: RuntimeDef,
    *,
    available: set[SkillInjectionStrategy],
) -> SkillInjectionStrategy:
    for strategy in runtime.skill_injection.ordered():
        if strategy in available:
            return strategy
    return SkillInjectionStrategy.PROMPT


def prepare_prompt_injection(skill_dir: Path) -> str:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return ""
    return skill_md.read_text(encoding="utf-8")
```

Run: `pytest tests/execution/test_skill_injection.py -q`  
Expected: PASS.

- [ ] **Step 3: Wire injection into harness prompt only through a narrow hook**

Add a small hook in the execution path so `build_harness_prompt()` can receive injected skill context without duplicating prompt composition. Keep `harness_prompt.py` current "start in cwd, use relative path" guidance.

Run: `pytest tests/execution/test_harness_prompt.py tests/execution/test_skill_injection.py -q`  
Expected: PASS.

---

## Task 6: Preflight Runner

**Files:**
- Create: `skillhub_eval/execution/preflight.py`
- Create: `tests/execution/test_preflight.py`
- Modify: `skillhub_eval/execution/local_agent_source.py`

- [ ] **Step 1: Write preflight runner tests with fake executor**

Add `tests/execution/test_preflight.py`:

```python
from dataclasses import dataclass

from skillhub_eval.core.schemas.report import ExecResult
from skillhub_eval.execution.preflight import PreflightRunner, PreflightStatus
from skillhub_eval.execution.runtime_defs import get_runtime_def


@dataclass
class _FakeSource:
    result: ExecResult

    def get_actual_output(self, bundle_path, case_id, *, case=None, bundle=None, ctx=None):
        return self.result


def test_preflight_passes_when_fixture_exec_result_is_ok(tmp_path):
    runtime = get_runtime_def("cursor-agent")
    source = _FakeSource(ExecResult(
        actual_output={"status": "success", "ok": True},
        source="local_agent",
        status="ok",
        confidence="high",
    ))
    runner = PreflightRunner(source=source)

    result = runner.run(runtime=runtime, model_id="gpt-5", skill_path=str(tmp_path), skill_fingerprint="skill-123")

    assert result.status == PreflightStatus.PASSED
    assert result.failure_reason is None


def test_preflight_fails_when_entrypoint_did_not_run(tmp_path):
    runtime = get_runtime_def("cursor-agent")
    source = _FakeSource(ExecResult(source="local_agent", status="incomplete", degrade_reason="missing_entrypoint_evidence"))
    runner = PreflightRunner(source=source)

    result = runner.run(runtime=runtime, model_id="gpt-5", skill_path=str(tmp_path), skill_fingerprint="skill-123")

    assert result.status == PreflightStatus.FAILED
    assert result.failure_reason == "runtime_entrypoint_not_called"


def test_high_risk_skill_without_safe_preflight_probe_is_blocked(tmp_path):
    runtime = get_runtime_def("cursor-agent")
    source = _FakeSource(ExecResult(
        actual_output={"status": "success", "ok": True},
        source="local_agent",
        status="ok",
        confidence="high",
    ))
    runner = PreflightRunner(source=source)

    result = runner.run(
        runtime=runtime,
        model_id="gpt-5",
        skill_path=str(tmp_path),
        skill_fingerprint="skill-123",
        bundle={"skill_id": "risk-skill", "risk_level": "high", "has_scripts": True, "entrypoint": "scripts/run.py"},
    )

    assert result.status == PreflightStatus.BLOCKED
    assert result.failure_reason == "runtime_safe_preflight_required"
```

Run: `pytest tests/execution/test_preflight.py -q`  
Expected: FAIL because module does not exist.

- [ ] **Step 2: Implement preflight runner**

Create `skillhub_eval/execution/preflight.py`:

```python
"""Runtime preflight execution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import StrEnum

from skillhub_eval.execution.runtime_defs import RuntimeDef


class PreflightStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class PreflightResult:
    runtime_id: str
    model_id: str
    status: PreflightStatus
    checked_at: datetime
    expires_at: datetime
    failure_reason: str | None
    message_zh: str


_REASON_MAP = {
    "missing_entrypoint_evidence": "runtime_entrypoint_not_called",
    "agent_unavailable": "runtime_not_invocable",
    "run_incomplete": "runtime_completion_event_missing",
    "output_leak": "runtime_output_leak",
}


class PreflightRunner:
    def __init__(self, source, now_fn=None):
        self._source = source
        self._now = now_fn or (lambda: datetime.now(timezone.utc))

    def run(
        self,
        *,
        runtime: RuntimeDef,
        model_id: str,
        skill_path: str,
        skill_fingerprint: str,
        bundle: dict | None = None,
    ) -> PreflightResult:
        now = self._now()
        bundle = bundle or {"skill_id": "preflight-skill", "has_scripts": True, "entrypoint": "scripts/run.py"}
        probe = _select_safe_preflight_probe(bundle)
        if probe is None:
            return PreflightResult(
                runtime_id=runtime.runtime_id,
                model_id=model_id,
                status=PreflightStatus.BLOCKED,
                checked_at=now,
                expires_at=now + timedelta(hours=24),
                failure_reason="runtime_safe_preflight_required",
                message_zh="该 Skill 需要补充安全预检用例后才能运行本地 runtime 预检。",
            )
        result = self._source.get_actual_output(
            skill_path,
            probe["case_id"],
            case=probe["case"],
            bundle=bundle,
            ctx={
                "preflight": True,
                "runtime_id": runtime.runtime_id,
                "model_id": model_id,
                "skill_fingerprint": skill_fingerprint,
            },
        )
        if result.status == "ok" and result.actual_output:
            return PreflightResult(
                runtime_id=runtime.runtime_id,
                model_id=model_id,
                status=PreflightStatus.PASSED,
                checked_at=now,
                expires_at=now + timedelta(hours=24),
                failure_reason=None,
                message_zh="本地 runtime 预检通过。",
            )
        mapped = _REASON_MAP.get(result.degrade_reason or "", "runtime_preflight_failed")
        return PreflightResult(
            runtime_id=runtime.runtime_id,
            model_id=model_id,
            status=PreflightStatus.FAILED,
            checked_at=now,
            expires_at=now + timedelta(hours=24),
            failure_reason=mapped,
            message_zh="本地 runtime 预检未通过。",
        )


def _select_safe_preflight_probe(bundle: dict) -> dict | None:
    preflight = bundle.get("preflight_case") or bundle.get("runtime_preflight_case")
    if isinstance(preflight, dict):
        case_id = str(preflight.get("id") or "preflight")
        return {"case_id": case_id, "case": preflight}

    risk = str(bundle.get("risk_level_locked") or bundle.get("risk_level") or "low").lower()
    if risk in {"high", "redline"}:
        return None

    return {
        "case_id": "preflight_probe",
        "case": {"id": "preflight_probe", "case_type": "happy", "preflight": True},
    }
```

Run: `pytest tests/execution/test_preflight.py -q`  
Expected: PASS.

- [ ] **Step 3: Add compatibility integration point**

Modify `local_agent_source.py` so preflight mode can reuse the same execution code but bypass formal-evaluation preflight gating. Use `ctx={"preflight": True}` as the explicit escape hatch for the preflight runner only.

Run: `pytest tests/execution/test_local_agent_source.py tests/execution/test_preflight.py -q`  
Expected: PASS.

---

## Task 7: API Readiness and Preflight Endpoint

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Modify: tests in `tests/adapters/test_exec_bridge_api.py`

- [ ] **Step 1: Add API tests for runtime scan fields**

Extend `tests/adapters/test_exec_bridge_api.py` with assertions that `/api/exec/agents/scan` items include:

```python
assert "runtime_id" in item
assert "install_status" in item
assert "auth_status" in item
assert "selected_model_status" in item
assert "preflight_status" in item
assert "capability_status" in item
```

Run: `pytest tests/adapters/test_exec_bridge_api.py -q`  
Expected: FAIL until route schema expands.

- [ ] **Step 2: Expand scan response schema**

In `exec.py`, add fields to `AgentScanItem` or equivalent response model:

```python
runtime_id: str
install_status: str
invocation_status: str | None = None
auth_status: str | None = None
selected_model_status: str | None = None
capability_status: str | None = None
preflight_status: str | None = None
preflight_expires_at: str | None = None
runtime_failure_reason: str | None = None
manual_hint: str | None = None
```

Map existing scan data into these fields without removing old fields yet.

Run: `pytest tests/adapters/test_exec_bridge_api.py -q`  
Expected: PASS after updating expected contracts.

- [ ] **Step 3: Add preflight action tests**

Add tests for `POST /api/exec/agents/{agent_id}/preflight` or the existing route style if this codebase uses a different prefix:

```python
def test_preflight_endpoint_returns_status(client):
    response = client.post("/api/exec/agents/cursor-agent/preflight", json={"model": "default"})

    assert response.status_code in {200, 409, 422}
    assert "status" in response.json()
```

Use monkeypatches/fakes so the default test suite does not call real CLIs.

Run: `pytest tests/adapters/test_exec_bridge_api.py -q`  
Expected: FAIL until endpoint exists.

- [ ] **Step 4: Implement preflight endpoint with fakeable runner dependency**

Add endpoint that:

1. resolves runtime
2. resolves model
3. computes fingerprint
4. runs `PreflightRunner`
5. writes cache entry
6. returns status/message/failure reason/expires_at

Run: `pytest tests/adapters/test_exec_bridge_api.py tests/execution/test_preflight.py tests/persistence/test_runtime_preflight_cache.py -q`  
Expected: PASS.

---

## Task 8: Formal Evaluation Gate

**Files:**
- Modify: `skillhub_eval/core/execution_source.py`
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/execution/local_agent_source.py`
- Modify: `tests/core/test_engine.py`
- Modify: `tests/core/test_execution_source_routing.py`

- [ ] **Step 1: Add tests for missing preflight blocking**

Add a focused engine or routing test:

```python
def test_local_execution_blocks_when_preflight_missing(monkeypatch):
    # Arrange an execution_source=local run with no preflight cache entry.
    # Assert run ends failed/blocked with LOCAL_RUNTIME_PREFLIGHT_REQUIRED.
```

Use existing test helpers in `tests/core/test_engine.py` for run finalization and reason codes.

Run: `pytest tests/core/test_engine.py -q -k preflight`  
Expected: FAIL.

- [ ] **Step 2: Assert runtime-platform path is active before gate**

Add an integration test proving formal local execution resolves the selected runtime through the runtime platform rather than bypassing it through a legacy adapter-only path. This should use fake executors and must not require live CLIs.

The test should also assert the adapter equivalence tests for Codex, Cursor Agent, Trae, Claude, and Antigravity are part of the required focused suite before the gate can be considered complete.

Run: focused execution source/runtime tests.  
Expected: FAIL until the runtime-platform integration point is wired.

- [ ] **Step 3: Implement preflight gate before formal local case execution**

In execution source or engine path, check:

```python
if execution_source == "local" and not ctx.get("preflight"):
    entry = get_valid_runtime_preflight(
        repo,
        runtime_id=agent_id,
        model_id=model_id,
        skill_fingerprint=skill_fingerprint,
        fingerprint=fingerprint,
    )
    if entry is None:
        return ExecResult(
            actual_output=None,
            source="local_agent",
            confidence="low",
            status="incomplete",
            degrade_reason="runtime_preflight_required",
        )
```

Then reuse existing Q-28 all-cases-failed path to surface a hard block when no case can run.

Run: `pytest tests/core/test_engine.py tests/core/test_execution_source_routing.py -q -k "preflight or local_exec"`  
Expected: PASS.

- [ ] **Step 4: Preserve sample_io and redline behavior**

Run existing tests:

`pytest tests/core/test_execution_source_routing.py tests/core/test_level_and_trust.py tests/core/test_judge_dual_mode.py -q`

Expected: PASS. Redline `redline_no_hardened_profile` remains the only intentional sample_io degrade path.

---

## Task 9: Runtime Failure Taxonomy

**Files:**
- Create or modify: `skillhub_eval/execution/failure_reasons.py`
- Modify: `skillhub_eval/execution/local_agent_source.py`
- Modify: `skillhub_eval/execution/runner.py`
- Modify: `skillhub_eval/core/provider_summary.py`
- Modify: UI reason maps in `skillhub_eval/adapters/ui/static/assets/index.js`
- Add tests under `tests/execution/` and `tests/core/`

- [ ] **Step 1: Add failure mapping tests**

Create `tests/execution/test_failure_reasons.py`:

```python
from skillhub_eval.execution.failure_reasons import normalize_runtime_failure_reason


def test_maps_legacy_run_incomplete_to_completion_missing():
    assert normalize_runtime_failure_reason("run_incomplete") == "runtime_completion_event_missing"


def test_maps_missing_entrypoint_to_runtime_entrypoint_not_called():
    assert normalize_runtime_failure_reason("missing_entrypoint_evidence") == "runtime_entrypoint_not_called"


def test_preserves_new_runtime_reason():
    assert normalize_runtime_failure_reason("runtime_cli_crashed") == "runtime_cli_crashed"
```

Run: `pytest tests/execution/test_failure_reasons.py -q`  
Expected: FAIL until module exists.

- [ ] **Step 2: Implement failure reason mapping**

Create `skillhub_eval/execution/failure_reasons.py`:

```python
"""Stable local runtime failure reason taxonomy."""

from __future__ import annotations


LEGACY_RUNTIME_REASON_MAP = {
    "agent_unavailable": "runtime_not_invocable",
    "run_incomplete": "runtime_completion_event_missing",
    "missing_entrypoint_evidence": "runtime_entrypoint_not_called",
    "output_leak": "runtime_output_leak",
    "consent_required": "runtime_preflight_required",
}


def normalize_runtime_failure_reason(reason: str | None) -> str | None:
    if not reason:
        return None
    if reason.startswith("runtime_"):
        return reason
    return LEGACY_RUNTIME_REASON_MAP.get(reason, reason)
```

Run: `pytest tests/execution/test_failure_reasons.py -q`  
Expected: PASS.

- [ ] **Step 3: Map runner failures more precisely**

Modify `runner.py` so:

- timeout kill returns a reason that can map to `runtime_process_timeout`
- nonzero exit with stderr and no completion can map to `runtime_cli_crashed`
- process exits cleanly but no completion event can map to `runtime_completion_event_missing`

Add tests in `tests/execution/test_runner.py` or existing runner tests.

Run: `pytest tests/execution/test_runner.py tests/execution/test_failure_reasons.py -q`  
Expected: PASS.

- [ ] **Step 4: Surface normalized reasons in report/UI**

Use `normalize_runtime_failure_reason()` before storing `exec_degrade_reason` and local-agent failure events. Extend JS reason map with:

```javascript
runtime_preflight_required: '本地 Runtime 预检未通过或已过期',
runtime_entrypoint_not_called: '本地 Runtime 未调用 Skill 入口脚本',
runtime_cli_crashed: '本地 CLI 进程崩溃',
runtime_process_timeout: '本地 CLI 执行超时',
runtime_completion_event_missing: '未识别到本地 CLI 完成事件',
runtime_tool_permission_denied: '本地 CLI 工具权限不足',
runtime_prompt_too_large: '本地 Runtime 提示词过长',
```

Run:

`pytest tests/core/test_provider_summary.py tests/core/test_engine.py -q -k "exec or local"`  
`node --check skillhub_eval/adapters/ui/static/assets/index.js`

Expected: PASS.

---

## Task 10: Runtime Readiness UI and Explicit Switching

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/assets/index.js`
- Modify: `skillhub_eval/adapters/api/routes/exec.py`
- Modify/add tests in `tests/adapters/test_exec_bridge_api.py`

- [ ] **Step 1: Add API test for explicit switch action**

Add test:

```python
def test_switch_runtime_requires_explicit_request(client):
    response = client.post("/api/exec/preferences", json={"exec_agent": "claude", "exec_model": "default"})

    assert response.status_code in {200, 204}
```

Also assert failure paths do not change preferences automatically by inspecting existing preference getters after a fake runtime failure.
Also assert the switch updates only local preference storage and does not mutate `get_runtime_catalog()` output.

Run: `pytest tests/adapters/test_exec_bridge_api.py -q -k "switch or preferences"`  
Expected: FAIL if API contract needs update.

- [ ] **Step 2: Implement explicit switch by reusing preferences endpoint**

Prefer reusing the existing exec preference update endpoint. If no clean endpoint exists, add a small explicit endpoint that only updates selected runtime/model and returns the updated scan state. Do not trigger evaluation automatically inside the endpoint.

Run: `pytest tests/adapters/test_exec_bridge_api.py -q -k "switch or preferences"`  
Expected: PASS.

- [ ] **Step 3: Update runtime cards**

In `index.js`, render each runtime card with:

- runtime label
- install/auth/model/capability/preflight status
- preflight expiry if present
- "运行预检" button
- "改用此 Runtime" button only when preflight passed and it is not the selected runtime
- manual hint text when blocked

Run: `node --check skillhub_eval/adapters/ui/static/assets/index.js`  
Expected: PASS.

- [ ] **Step 4: Add no-auto-switch UI guard**

Ensure UI handlers only call the switch endpoint from the explicit button click. Runtime failure display must not mutate selected runtime automatically.

Run: `node --check skillhub_eval/adapters/ui/static/assets/index.js`  
Expected: PASS.

---

## Task 11: Real Stream Fixtures and Opt-in Live Tests

**Files:**
- Create: `tests/fixtures/runtime_streams/*`
- Create: `scripts/sanitize_runtime_stream_fixture.py`
- Modify: `.gitignore` only if `.tmp/` or `.tmp/raw_runtime_streams/` is not already ignored.
- Modify: adapter tests under `tests/execution/`
- Modify: `tests/execution/test_e2e_local_exec.py` if needed.

- [ ] **Step 1: Add sanitized stream fixture files**

Create fixture files:

- `tests/fixtures/runtime_streams/cursor_agent_fixture.jsonl`
- `tests/fixtures/runtime_streams/trae_fixture.jsonl`
- `tests/fixtures/runtime_streams/codex_fixture.jsonl`
- `tests/fixtures/runtime_streams/claude_fixture.jsonl`
- `tests/fixtures/runtime_streams/antigravity_fixture.txt`

Each fixture must be small and sanitized. It must include at least one successful completion and, where supported, one entrypoint tool evidence shape.

Full raw captures from live runs must stay local-only under `.tmp/raw_runtime_streams/` and must not be committed. If `.tmp/` is not already ignored, add the narrowest ignore rule needed.

- [ ] **Step 2: Add fixture loader helper in tests**

In the relevant test file, use:

```python
from pathlib import Path


def _fixture_lines(name: str) -> list[str]:
    path = Path("tests/fixtures/runtime_streams") / name
    return path.read_text(encoding="utf-8").splitlines()
```

Run adapter fixture tests.  
Expected: PASS.

- [ ] **Step 3: Add raw capture sanitizer**

Create `scripts/sanitize_runtime_stream_fixture.py`.

The sanitizer should:

1. Read a raw capture from `.tmp/raw_runtime_streams/`.
2. Remove usernames, absolute local paths, tokens/API keys, long transcripts, unrelated model prose, and volatile timestamps where they do not affect parsing.
3. Preserve runtime id, CLI version if present, event type names, tool call/tool result shape, exit code, stdout/stderr shape, usage shape, completion/error shape.
4. Write a small fixture under `tests/fixtures/runtime_streams/`.

Add tests for the sanitizer with representative sensitive inputs.
Expected: PASS.

- [ ] **Step 4: Keep live E2E opt-in**

Ensure live tests continue to require `RUN_LOCAL_AGENT=1` and skip missing local CLIs. Add runtime ids for all five runtimes if the existing parametrization does not include them.

Live E2E must be explicit opt-in. The default suite should use fixtures, fake executors, and temp SQLite databases only. It must not depend on installed CLIs, login state, network/model access, or quota.

Run: `pytest tests/execution/test_e2e_local_exec.py -q`  
Expected: SKIP or PASS without requiring local CLIs.

Run when explicitly validating locally: `RUN_LOCAL_AGENT=1 pytest tests/execution/test_e2e_local_exec.py -q`  
Expected: installed and preflight-passed runtimes PASS; missing runtimes SKIP with readable reason.

---

## Task 12: Docs, Encoding, and Regression

**Files:**
- Modify: `docs/runbooks/local-agent-exec-validation.md`
- Propose update only after implementation: `RECORD.md`
- Modify if needed: `.project_memory/active/SPRINT_phase3-eval-system.md`

- [ ] **Step 1: Update runbook**

Add sections to `docs/runbooks/local-agent-exec-validation.md`:

- Runtime platform overview
- Runtime readiness statuses
- How to run preflight
- Why formal local evaluation requires preflight
- Explicit runtime switching
- Failure reason troubleshooting table
- Notes that scoring still uses existing judge/R1-R8/expert flow

- [ ] **Step 2: Run focused tests**

Run:

```powershell
pytest tests/execution tests/core tests/adapters -q
node --check skillhub_eval/adapters/ui/static/assets/index.js
```

Expected: PASS except known unrelated baseline failures already documented in `RECORD.md`. Any new failures from this change must be fixed before proceeding.

- [ ] **Step 3: Run doc encoding guard**

Run:

```powershell
python scripts/check_doc_encoding.py
```

Expected: `doc encoding OK`.

- [ ] **Step 4: Prepare project ledger update proposal**

Do not silently edit `RECORD.md` unless the user asks. Prepare a concise update noting:

- `local-cli-runtime-platform` implementation status
- tests run
- live runtime validation status for five runtimes
- any runtime still blocked by local environment

---

## Self-Review Checklist

- Completion standard:
  - OpenSpec artifacts and this plan are complete and aligned.
  - Codex, Cursor Agent, Trae, Claude, and Antigravity are all in the runtime catalog.
  - Default tests do not require live CLIs, login state, network/model access, or quota.
  - Formal local evaluation routes through the runtime platform after all five adapter equivalence tests pass.
  - Mandatory skill-specific runtime preflight is enforced and persisted in SQLite with fingerprint invalidation.
  - UI shows readiness/preflight state and supports explicit one-click switching without automatic fallback.
  - Existing scoring, R1-R8, thresholds, expert review, report aggregation, and attribution semantics remain unchanged.
  - Live runtime E2E validation remains explicit opt-in with `RUN_LOCAL_AGENT=1`.
- Spec coverage:
  - Runtime contract: Tasks 1, 2, 7
  - Unified AgentEvent: Tasks 3, 4, 11
  - Mandatory preflight: Tasks 5, 6, 7, 8
  - Skill-specific preflight cache/fingerprint: Task 2
  - Skill injection: Task 5
  - Explicit switching: Task 10
  - Failure taxonomy: Task 9
  - Existing scoring unchanged: Tasks 8 and 12 verification
- Placeholder scan: no open implementation placeholders are intentional in this plan.
- Type consistency: `RuntimeDef`, `AgentEvent`, `PreflightRunner`, and cache names are introduced before later tasks use them.
- Git rule check: plan intentionally does not include commit steps because repository instructions require explicit user request before committing.
