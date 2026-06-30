# 本地 Agent 可扩展 adapter 框架 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **本稿为 grill-me 定稿（2026-06-30）**。原"自制 ACP JSON-RPC 传输"已废弃——实测 `trae-cli` 原生支持与 claude/codex 同形的 `--print --output-format stream-json` 模式，故 trae 改走现有 stream-json 路径。锁定决策见 §决策表 G1–G8。

**Goal:** 把执行层从"逐个写死 build_args + 写死安装位置"升级为 open-design 风格的**数据驱动可扩展框架**：注册一条数据即新增/检测一个 CLI；启动三态检测本机 CLI（可用 / 未登录 / 未安装，含 PATH 外/带版本号目录）；按 CLI 发现/选择模型；并修好 trae 让它真跑。

**Tech Stack:** Python 3.11+、pydantic、FastAPI、SQLite、pytest；前端 vanilla JS（`adapters/ui/static/assets/index.js`）。

设计依据：`docs/superpowers/specs/2026-06-30-local-agent-adapter-framework-design.md`；OpenSpec 记录：`openspec/changes/local-agent-adapter-framework/`。

---

## 决策表（grill-me 定稿）

| # | 决策 |
|---|------|
| G1 | trae 走 **stream-json**（`trae-cli -p --output-format stream-json --include-partial-messages --yolo`），丢弃自制 ACP 传输 |
| G2 | 保留 **transport 包 + 按 `stream_format` 分派**骨架；当前只实现 stream-json，`acp-json-rpc` 为未来扩展点（`NotImplementedError`，不实现） |
| G3 | **检测数据驱动**：每个 agent 在 registry 声明候选安装目录（含版本号通配），统一 `PATH→登记目录→npm→where` 解析；新增 CLI 只加数据，不改检测代码 |
| G4 | **模型发现通用 `model_probe`**：trae=`trae-cli models`（live）；cursor/codex/claude=fallback+手输；自定义保留 |
| G5 | **三态认证灯**：二进制+config 目录→可用；有二进制无 config→未登录；cursor→待测试；真认证点 Test/首跑确认 |
| G6 | trae 修正：`primary_bin=trae-cli`（别名 `traecli/trae-agent/ta`）+ stream-json build_args + 复用 claude 式解析 |
| G7 | 验收：codex+trae 先真跑极小 fixture；cursor 待重装修好后补验；抓一次 trae 真实 stream-json 锁定解析器 |
| G8 | judge/双模型/聚合/R1–R8/`ExecResult` 字段不动；现有 stream-json 行为不回归 |

**实测依据**（本机已验证）：`trae-cli` 在 `%LOCALAPPDATA%\trae-cli\bin`（不在 PATH），别名 `trae-cli/traecli/trae-agent/ta`，支持 `acp`/`models`/`--print --output-format stream-json --include-partial-messages --yolo --permission-mode bypass_permissions`；`trae-cli models` 秒回模型清单。codex 在 `%LOCALAPPDATA%\OpenAI\Codex\bin\<ver>\codex.exe`（现有解析已命中）。cursor-agent 启动器在 PATH 但 `versions\` 命名与其 `.ps1` 正则不匹配 → 当前本机不可用（需重装；属外部工具问题）。

---

## File Structure

新增：

- `skillhub_eval/execution/install_hints.py` — 每 CLI 安装指引（命令 + 链接 + 平台备注）
- `skillhub_eval/execution/detection.py` — 数据驱动二进制解析 + 三态检测 + TTL 缓存
- `skillhub_eval/execution/models.py` — 通用 `model_probe` 混合发现
- `skillhub_eval/execution/transport/__init__.py`
- `skillhub_eval/execution/transport/base.py` — `run_via_transport()` 按 `stream_format` 分派（stream-json → 现有 runner；acp-json-rpc → NotImplementedError 扩展点）
- 测试：`tests/execution/test_detection.py`、`test_models.py`、`test_install_hints.py`、`test_transport_dispatch.py`、`test_adapter_trae.py`（重写）

修改：

- `skillhub_eval/settings.py` — 新增 `model_discovery_timeout_s` / `agent_detect_cache_ttl_s`
- `skillhub_eval/execution/agent_registry.py` — `AgentDef` 增 `stream_format` / `config_dirs` / `install_dir_globs` / `version_args` / `model_probe` / `prompt_via_stdin`；修 trae 登记
- `skillhub_eval/execution/adapters/trae.py` — bin 名 + stream-json build_args + 复用解析
- `skillhub_eval/execution/local_agent_source.py` — `_execute_once` 经 `run_via_transport` 走传输 seam
- `skillhub_eval/execution/preferences.py` — `_is_agent_detected` 改走 detection
- `skillhub_eval/adapters/api/routes/exec.py` — `scan` 返回真 `auth_status` + `install_*` + 发现的 `models`
- `skillhub_eval/adapters/ui/static/assets/index.js` — 三态徽章 + 安装指引卡（`[ui-only]`）
- `.env.example` — 新增超时键

**约束（G8）**：`core/engine.py`、judge、断言、聚合、决策、`ExecResult` 字段**不改**；现有 claude/codex/cursor stream-json 行为不回归。

---

## Phase 0 — 基础设施（settings + registry）

### Task 0.1: 新增模型发现/检测缓存超时

**Files:** `skillhub_eval/settings.py`、`.env.example`、`tests/test_settings_exec_framework.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_settings_exec_framework.py
from skillhub_eval.settings import Settings


def test_exec_framework_timeouts_have_defaults():
    s = Settings()
    assert s.model_discovery_timeout_s == 6.0
    assert s.agent_detect_cache_ttl_s == 86400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_settings_exec_framework.py -v` → FAIL (`AttributeError`).

- [ ] **Step 3: Implement** — add to `Settings` after `divergence_synthesis_timeout_s`:

```python
    # Adapter framework (W8.7)
    model_discovery_timeout_s: float = Field(
        default=6.0,
        validation_alias=AliasChoices("MODEL_DISCOVERY_TIMEOUT_S", "SKILLHUB_MODEL_DISCOVERY_TIMEOUT_S"),
    )
    agent_detect_cache_ttl_s: int = Field(
        default=86400,
        validation_alias=AliasChoices("AGENT_DETECT_CACHE_TTL_S", "SKILLHUB_AGENT_DETECT_CACHE_TTL_S"),
    )
```

- [ ] **Step 4: Run test** → PASS.

- [ ] **Step 5: Append to `.env.example`** (local-agent section):

```bash
# Adapter framework (W8.7)
MODEL_DISCOVERY_TIMEOUT_S=6
AGENT_DETECT_CACHE_TTL_S=86400
```

- [ ] **Step 6: Commit**

```bash
git add skillhub_eval/settings.py tests/test_settings_exec_framework.py .env.example
git commit -m "feat(exec): add model-discovery and detection-cache timeouts"
```

### Task 0.2: 扩展 `AgentDef` + 数据驱动登记（含 trae 修正）

**Files:** `skillhub_eval/execution/agent_registry.py`、`tests/execution/test_agent_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_agent_registry.py (append)
from skillhub_eval.execution.agent_registry import get_agent_def


def test_defs_declare_framework_fields():
    codex = get_agent_def("codex")
    assert codex.stream_format == "stream-json"
    assert any(".codex" in d for d in codex.config_dirs)
    assert any("Codex" in g for g in codex.install_dir_globs)

    trae = get_agent_def("trae")
    assert trae.stream_format == "stream-json"          # G1: not acp
    assert trae.primary_bin == "trae-cli"               # G6
    assert "traecli" in trae.binary_aliases and "ta" in trae.binary_aliases
    assert trae.model_probe == ("models",)              # G4
    assert any("trae-cli" in g for g in trae.install_dir_globs)
```

- [ ] **Step 2: Run test** → FAIL (`AttributeError: stream_format` / trae mismatch).

- [ ] **Step 3: Implement** — extend `AgentDef` (keep existing fields + properties):

```python
@dataclass(frozen=True)
class AgentDef:
    agent_id: str
    label: str
    adapter_factory: Callable[..., AgentAdapter] | None
    fallback_models: tuple[ModelOption, ...]
    primary_bin: str | None = None
    binary_aliases: tuple[str, ...] = ()
    supports_hardened_redline: bool = False
    aliases: tuple[str, ...] = ()
    stream_format: str = "stream-json"                  # "stream-json" | "acp-json-rpc"
    config_dirs: tuple[str, ...] = ()                   # relative to USERPROFILE/HOME
    install_dir_globs: tuple[str, ...] = ()             # relative to LOCALAPPDATA/APPDATA/HOME, glob ok
    version_args: tuple[str, ...] = ("--version",)
    model_probe: tuple[str, ...] | None = None          # argv to list models, e.g. ("models",)
    prompt_via_stdin: bool = True
```

Update `_CATALOG` entries (add new kwargs; fix trae):

```python
    AgentDef(
        agent_id="claude", label="Claude", adapter_factory=_claude_adapter,
        fallback_models=(_DEFAULT_MODEL,),
        config_dirs=(".claude",),
    ),
    AgentDef(
        agent_id="codex", label="Codex", adapter_factory=_codex_adapter,
        fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5-codex", "GPT-5 Codex")),
        supports_hardened_redline=True,
        config_dirs=(".codex",),
        install_dir_globs=("OpenAI/Codex/bin/*",),
    ),
    AgentDef(
        agent_id="cursor-agent", label="Cursor Agent", adapter_factory=_cursor_agent_adapter,
        fallback_models=(_DEFAULT_MODEL, ModelOption("gpt-5", "GPT-5")),
        aliases=("cursor_agent",),
        config_dirs=(".cursor",),
        install_dir_globs=("cursor-agent/versions/*",),
    ),
    AgentDef(
        agent_id="trae", label="Trae", adapter_factory=_trae_adapter,
        fallback_models=(_DEFAULT_MODEL,),
        primary_bin="trae-cli", binary_aliases=("traecli", "trae-agent", "ta"),
        stream_format="stream-json",
        config_dirs=(".trae",),
        install_dir_globs=("trae-cli/bin",),
        model_probe=("models",),
    ),
    AgentDef(
        agent_id="antigravity", label="Antigravity", adapter_factory=_antigravity_adapter,
        fallback_models=(_DEFAULT_MODEL,),
        primary_bin="agy",
        config_dirs=(".gemini/antigravity-cli",),
    ),
```

- [ ] **Step 4: Run test** → PASS (existing registry tests still pass).

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/agent_registry.py tests/execution/test_agent_registry.py
git commit -m "feat(exec): data-driven AgentDef fields; fix trae registry (stream-json + names)"
```

---

## Phase 1 — 数据驱动检测 + 三态 + 缓存

### Task 1.1: `install_hints` 数据模块（D4）

**Files:** `skillhub_eval/execution/install_hints.py`、`tests/execution/test_install_hints.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_install_hints.py
from skillhub_eval.execution.install_hints import get_install_hint


def test_known_agent_has_install_command_and_docs():
    hint = get_install_hint("codex")
    assert hint and hint["install_command"] and hint["docs_url"].startswith("http")


def test_unknown_agent_returns_none():
    assert get_install_hint("does-not-exist") is None
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# skillhub_eval/execution/install_hints.py
"""Static install guidance for local CLI agents (no auto-install — D4)."""

from __future__ import annotations

_HINTS: dict[str, dict[str, str]] = {
    "claude": {
        "install_command": "npm install -g @anthropic-ai/claude-code",
        "docs_url": "https://docs.anthropic.com/en/docs/claude-code",
        "platform_note": "装后需 `claude` 登录授权。",
    },
    "codex": {
        "install_command": "npm install -g @openai/codex",
        "docs_url": "https://github.com/openai/codex",
        "platform_note": "亦可用 OpenAI Codex 桌面安装；装后需登录。",
    },
    "cursor-agent": {
        "install_command": "curl https://cursor.com/install -fsS | bash",
        "docs_url": "https://www.cursor.com/cli",
        "platform_note": "Windows 见官方文档；装后 `cursor-agent login`。",
    },
    "trae": {
        "install_command": "见官方文档安装 Trae CLI",
        "docs_url": "https://docs.trae.cn/cli",
        "platform_note": "需含 `trae-cli` 的版本；装后登录。",
    },
    "antigravity": {
        "install_command": "见官方安装包",
        "docs_url": "https://antigravity.google",
        "platform_note": "装后在其 CLI 设置中配置模型与登录。",
    },
}


def get_install_hint(agent_id: str) -> dict[str, str] | None:
    return _HINTS.get((agent_id or "").strip())
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/install_hints.py tests/execution/test_install_hints.py
git commit -m "feat(exec): add static install hints for local CLIs"
```

### Task 1.2: 数据驱动解析 + 三态检测 + 缓存

**Files:** `skillhub_eval/execution/detection.py`、`tests/execution/test_detection.py`

> 解析顺序（G3）：`PATH(find_cli_binary 逐别名)` → `install_dir_globs`（在 LOCALAPPDATA/APPDATA/HOME 下展开通配，取最新目录里的二进制）→ 沿用 `find_cli_binary` 的 where.exe 兜底。codex 现有特例保留为 `find_cli_binary` 内部兜底，不冲突。

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_detection.py
from pathlib import Path
from unittest.mock import patch

from skillhub_eval.execution.agent_registry import get_agent_def
from skillhub_eval.execution import detection


def setup_function():
    detection.clear_detection_cache()


def test_resolve_via_install_dir_glob(tmp_path, monkeypatch):
    # simulate trae installed off-PATH under LOCALAPPDATA/trae-cli/bin
    bin_dir = tmp_path / "trae-cli" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "trae-cli.exe").write_text("x")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    with patch.object(detection, "find_cli_binary", return_value=None):
        path = detection.resolve_agent_binary(get_agent_def("trae"))
    assert path and path.endswith("trae-cli.exe")


def test_detected_with_config_dir_is_ok(monkeypatch):
    with patch.object(detection, "resolve_agent_binary", return_value="/bin/codex"), \
         patch.object(detection, "_config_dir_present", return_value=True):
        r = detection.detect_agent(get_agent_def("codex"))
    assert r.detected and r.auth_state == "ok"


def test_binary_without_config_dir_is_missing(monkeypatch):
    with patch.object(detection, "resolve_agent_binary", return_value="/bin/codex"), \
         patch.object(detection, "_config_dir_present", return_value=False):
        r = detection.detect_agent(get_agent_def("codex"))
    assert r.detected and r.auth_state == "missing"


def test_cursor_is_unknown_when_detected():
    with patch.object(detection, "resolve_agent_binary", return_value="/bin/cursor-agent"), \
         patch.object(detection, "_config_dir_present", return_value=True):
        r = detection.detect_agent(get_agent_def("cursor-agent"))
    assert r.detected and r.auth_state == "unknown"


def test_no_binary_not_detected():
    with patch.object(detection, "resolve_agent_binary", return_value=None):
        r = detection.detect_agent(get_agent_def("codex"))
    assert r.detected is False and r.auth_state == "missing"


def test_cache_avoids_second_probe():
    calls = {"n": 0}

    def fake_resolve(_def):
        calls["n"] += 1
        return "/bin/codex"

    with patch.object(detection, "resolve_agent_binary", side_effect=fake_resolve), \
         patch.object(detection, "_config_dir_present", return_value=True):
        detection.detect_agent(get_agent_def("codex"))
        detection.detect_agent(get_agent_def("codex"))
    assert calls["n"] == 1
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# skillhub_eval/execution/detection.py
"""Data-driven binary resolution + three-state detection with TTL cache."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path

from skillhub_eval.execution.agent_registry import AgentDef
from skillhub_eval.execution.cli_detect import detect_hint_zh, find_cli_binary
from skillhub_eval.settings import settings

_AUTH_DEFERRED = frozenset({"cursor-agent"})
_EXE_SUFFIXES = (".exe", ".cmd", ".bat", "")


@dataclass(frozen=True)
class DetectionResult:
    agent_id: str
    detected: bool
    bin_path: str | None
    auth_state: str  # "ok" | "missing" | "unknown"
    detect_hint: str | None = None


_cache: dict[str, tuple[float, DetectionResult]] = {}


def clear_detection_cache() -> None:
    _cache.clear()


def _home() -> Path:
    return Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or str(Path.home()))


def _install_roots() -> list[Path]:
    roots: list[Path] = []
    for key in ("LOCALAPPDATA", "APPDATA"):
        val = os.environ.get(key)
        if val:
            roots.append(Path(val))
    roots.append(_home())
    return roots


def _config_dir_present(agent: AgentDef) -> bool:
    home = _home()
    return any((home / rel).exists() for rel in agent.config_dirs)


def resolve_agent_binary(agent: AgentDef) -> str | None:
    # 1) PATH / npm / where.exe (existing resolver), per alias
    for name in agent.binary_names:
        path = find_cli_binary(name)
        if path:
            return path
    # 2) data-driven install dir globs (handles off-PATH / versioned installs)
    for pattern in agent.install_dir_globs:
        for root in _install_roots():
            try:
                matches = sorted(root.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
            except OSError:
                matches = []
            for d in matches:
                if not d.is_dir():
                    continue
                for name in agent.binary_names:
                    for suffix in _EXE_SUFFIXES:
                        candidate = d / f"{name}{suffix}"
                        if candidate.is_file():
                            return str(candidate.resolve())
    return None


def detect_agent(agent: AgentDef, *, force: bool = False) -> DetectionResult:
    now = time.monotonic()
    ttl = float(settings.agent_detect_cache_ttl_s)
    cached = _cache.get(agent.agent_id)
    if not force and cached and (now - cached[0]) < ttl:
        return cached[1]

    bin_path = resolve_agent_binary(agent)
    if bin_path is None:
        result = DetectionResult(
            agent.agent_id, False, None, "missing", detect_hint_zh(agent.bin),
        )
    elif agent.agent_id in _AUTH_DEFERRED:
        result = DetectionResult(agent.agent_id, True, bin_path, "unknown")
    elif _config_dir_present(agent):
        result = DetectionResult(agent.agent_id, True, bin_path, "ok")
    else:
        result = DetectionResult(agent.agent_id, True, bin_path, "missing")

    _cache[agent.agent_id] = (now, result)
    return result
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/detection.py tests/execution/test_detection.py
git commit -m "feat(exec): data-driven three-state detection with TTL cache"
```

### Task 1.3: trae adapter 走数据驱动解析（顺带让 trae.detect 生效）

**Files:** `skillhub_eval/execution/adapters/trae.py`（解析部分）、随 Task 3.1 一并完成；此处仅登记依赖关系。

- [ ] 在 Task 3.1 重写 trae adapter 时，其 `detect()`/`resolved_bin()` 委托 `detection.resolve_agent_binary(get_agent_def("trae"))`（见 Phase 3）。

### Task 1.4: `preferences._is_agent_detected` 改走 detection

**Files:** `skillhub_eval/execution/preferences.py`、`tests/execution/test_preferences_detection.py`

- [ ] **Step 1: Write the test**

```python
# tests/execution/test_preferences_detection.py
from unittest.mock import patch
from skillhub_eval.execution import preferences


def test_compute_ready_uses_detection_ok():
    with patch.object(preferences, "_is_agent_detected", return_value=True):
        ready, reason = preferences.compute_ready("local", "codex", True)
    assert ready is True and reason is None
```

- [ ] **Step 2: Run** → PASS after refactor (guards the change).

- [ ] **Step 3: Implement** — replace `_is_agent_detected`:

```python
def _is_agent_detected(agent_id: str) -> bool:
    from skillhub_eval.execution.agent_registry import get_agent_def
    from skillhub_eval.execution.detection import detect_agent

    agent = get_agent_def(agent_id)
    return bool(agent and detect_agent(agent).detected)
```

- [ ] **Step 4: Run** `pytest tests/execution/test_preferences_detection.py tests/execution/test_agent_registry.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/preferences.py tests/execution/test_preferences_detection.py
git commit -m "refactor(exec): route readiness detection through detection module"
```

---

## Phase 2 — 通用 model_probe 混合发现

### Task 2.1: `models.discover_models`

**Files:** `skillhub_eval/execution/models.py`、`tests/execution/test_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_models.py
from unittest.mock import patch

from skillhub_eval.execution.agent_registry import get_agent_def
from skillhub_eval.execution import models


def test_fallback_when_no_probe():
    disc = models.discover_models(get_agent_def("codex"))  # codex has no model_probe
    assert "default" in [m["id"] for m in disc.models]
    assert disc.models_source == "fallback"


def test_trae_live_probe_used():
    out = "GLM-5.2\nDeepSeek-V4-Pro\n"
    with patch.object(models, "_run_probe", return_value=out):
        disc = models.discover_models(get_agent_def("trae"))
    ids = [m["id"] for m in disc.models]
    assert "GLM-5.2" in ids and "DeepSeek-V4-Pro" in ids
    assert disc.models_source == "live"


def test_trae_probe_failure_falls_back():
    with patch.object(models, "_run_probe", return_value=None):
        disc = models.discover_models(get_agent_def("trae"))
    assert disc.models_source == "fallback"


def test_stored_custom_model_preserved():
    disc = models.discover_models(get_agent_def("codex"), stored_model="my/gpt-x")
    custom = next(m for m in disc.models if m["id"] == "my/gpt-x")
    assert custom["source"] in ("custom", "stale")
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# skillhub_eval/execution/models.py
"""Hybrid model discovery: generic model_probe + fallback + custom retention (D3/G4)."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field

from skillhub_eval.execution.agent_registry import AgentDef, DEFAULT_MODEL_ID
from skillhub_eval.execution.detection import resolve_agent_binary
from skillhub_eval.settings import settings


@dataclass(frozen=True)
class ModelDiscovery:
    models: list[dict] = field(default_factory=list)  # {id,label,source}
    models_source: str = "none"  # "live" | "fallback" | "none"


def _fallback_models(agent: AgentDef) -> list[dict]:
    return [{"id": m.id, "label": m.label, "source": "fallback"} for m in agent.fallback_models]


def _run_probe(agent: AgentDef) -> str | None:
    """Run `<bin> <model_probe...>` and return stdout, or None on failure."""
    if not agent.model_probe:
        return None
    bin_path = resolve_agent_binary(agent)
    if not bin_path:
        return None
    try:
        proc = subprocess.run(
            [bin_path, *agent.model_probe],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=float(settings.model_discovery_timeout_s), check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _parse_model_lines(stdout: str) -> list[str]:
    ids: list[str] = []
    for raw in stdout.splitlines():
        line = raw.strip()
        if line and not line.startswith(("=", "-", "#")):
            ids.append(line)
    return ids


def discover_models(agent: AgentDef, *, stored_model: str | None = None) -> ModelDiscovery:
    live_ids = _parse_model_lines(_run_probe(agent) or "") if agent.model_probe else []
    if live_ids:
        models = [{"id": DEFAULT_MODEL_ID, "label": "默认模型", "source": "live"}]
        models += [{"id": mid, "label": mid, "source": "live"} for mid in live_ids]
        source = "live"
    else:
        models = _fallback_models(agent)
        source = "fallback" if agent.fallback_models else "none"

    sm = (stored_model or "").strip()
    if sm and sm != DEFAULT_MODEL_ID and sm not in {m["id"] for m in models}:
        models = [*models, {"id": sm, "label": sm, "source": "stale" if source == "live" else "custom"}]

    return ModelDiscovery(models=models, models_source=source)
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/models.py tests/execution/test_models.py
git commit -m "feat(exec): generic model_probe hybrid discovery (trae live + fallback)"
```

---

## Phase 3 — trae 修成 stream-json adapter（替代原 ACP 阶段）

### Task 3.1: 重写 trae adapter（bin 名 + stream-json build_args + 解析）

**Files:** `skillhub_eval/execution/adapters/trae.py`、`tests/execution/test_adapter_trae.py`（重写）

> 参数依据本机 `trae-cli --help` 实测。prompt 默认走 stdin（`prompt_via_stdin=True`，与现有 runner 一致）；真跑若空输出，回退位置参（Task 7.x 校准）。

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_adapter_trae.py
from unittest.mock import patch

from skillhub_eval.execution.adapters.trae import TraeAdapter


def test_build_args_stream_json():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model=None).build_args(cwd="/tmp")
    assert args[0] == "trae-cli"
    assert "-p" in args or "--print" in args
    assert "--output-format" in args and "stream-json" in args
    assert "--yolo" in args
    assert "acp" not in args  # G1: no longer ACP


def test_build_args_includes_model():
    with patch("skillhub_eval.execution.adapters.trae._resolved_bin", return_value="trae-cli"):
        args = TraeAdapter(model="GLM-5.2").build_args(cwd="/tmp")
    assert "--model" in args and "GLM-5.2" in args


def test_parse_stream_reuses_generic_parser():
    a = TraeAdapter()
    parsed = a.parse_stream(['{"type":"result","result":"ok"}'])
    assert parsed.is_complete is True
```

- [ ] **Step 2: Run** → FAIL (current trae adapter emits `acp serve`).

- [ ] **Step 3: Implement**

```python
# skillhub_eval/execution/adapters/trae.py
"""Trae CLI adapter — stream-json print mode (G1/G6)."""

from __future__ import annotations

from dataclasses import dataclass


def _resolved_bin() -> str:
    from skillhub_eval.execution.agent_registry import get_agent_def
    from skillhub_eval.execution.detection import resolve_agent_binary

    agent = get_agent_def("trae")
    return (resolve_agent_binary(agent) if agent else None) or "trae-cli"


@dataclass
class TraeAdapter:
    agent_id: str = "trae"
    model: str | None = None

    def detect(self) -> bool:
        from skillhub_eval.execution.agent_registry import get_agent_def
        from skillhub_eval.execution.detection import resolve_agent_binary

        agent = get_agent_def("trae")
        return bool(agent and resolve_agent_binary(agent))

    def build_args(self, *, cwd: str | None = None, hardened: bool = False) -> list[str]:
        args = [
            _resolved_bin(),
            "-p",
            "--output-format", "stream-json",
            "--include-partial-messages",
            "--permission-mode", "bypass_permissions",
            "--yolo",
        ]
        if self.model:
            args.extend(["--model", self.model])
        return args

    def parse_stream(self, lines: list[str]):
        from skillhub_eval.execution.stream_parser import parse_stream_events

        return parse_stream_events(lines)
```

- [ ] **Step 4: Run** `pytest tests/execution/test_adapter_trae.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/adapters/trae.py tests/execution/test_adapter_trae.py
git commit -m "feat(exec): rewrite trae adapter to stream-json print mode"
```

---

## Phase 4 — 传输 seam + 执行入口接线

### Task 4.1: `transport` 分派包（stream-json 实现；acp 扩展点）

**Files:** `skillhub_eval/execution/transport/__init__.py`、`transport/base.py`、`tests/execution/test_transport_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_transport_dispatch.py
import pytest
from unittest.mock import MagicMock

from skillhub_eval.core.schemas.report import ParsedStream, RunOutcome
from skillhub_eval.execution.agent_registry import get_agent_def
from skillhub_eval.execution.transport import base


def test_dispatch_stream_json_calls_runner():
    runner = MagicMock()
    runner.run.return_value = RunOutcome(exit_code=0, parsed_stream=ParsedStream(final_text="x", is_complete=True))
    adapter = MagicMock(agent_id="trae")
    outcome = base.run_via_transport(
        adapter, get_agent_def("trae"), "p", cwd="/tmp",
        timeout_s=5, hardened=False, runner=runner,
    )
    assert outcome.parsed_stream.final_text == "x"
    runner.run.assert_called_once()


def test_dispatch_acp_is_extension_point():
    adapter = MagicMock(agent_id="x")
    fake_def = get_agent_def("trae").__class__(
        agent_id="x", label="X", adapter_factory=None, fallback_models=(),
        stream_format="acp-json-rpc",
    )
    with pytest.raises(NotImplementedError):
        base.run_via_transport(adapter, fake_def, "p", cwd="/tmp", timeout_s=5,
                               hardened=False, runner=MagicMock())
```

- [ ] **Step 2: Run** → FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

```python
# skillhub_eval/execution/transport/__init__.py
```

```python
# skillhub_eval/execution/transport/base.py
"""Transport dispatch by AgentDef.stream_format.

stream-json → existing LocalAgentRunner. acp-json-rpc → future extension point.
"""

from __future__ import annotations

from skillhub_eval.core.schemas.report import RunOutcome
from skillhub_eval.execution.agent_registry import AgentDef
from skillhub_eval.execution.runner import AgentAdapter, LocalAgentRunner


def run_via_transport(
    adapter: AgentAdapter,
    agent: AgentDef,
    prompt: str,
    *,
    cwd: str,
    timeout_s: float,
    hardened: bool,
    runner: LocalAgentRunner | None = None,
) -> RunOutcome:
    fmt = getattr(agent, "stream_format", "stream-json")
    if fmt == "stream-json":
        runner = runner or LocalAgentRunner()
        return runner.run(adapter, prompt, cwd=cwd, timeout_s=timeout_s, hardened=hardened)
    if fmt == "acp-json-rpc":
        raise NotImplementedError(
            f"stream_format 'acp-json-rpc' not implemented for {agent.agent_id}; "
            "this is a documented extension point (see design G2)."
        )
    raise ValueError(f"unknown stream_format: {fmt}")
```

- [ ] **Step 4: Run** → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/transport/ tests/execution/test_transport_dispatch.py
git commit -m "feat(exec): transport dispatch seam (stream-json impl, acp extension point)"
```

### Task 4.2: `LocalAgentSource._execute_once` 走 transport seam

**Files:** `skillhub_eval/execution/local_agent_source.py`、`tests/execution/test_local_agent_source.py`（回归）

> 这是把现有 `self._runner.run(adapter, ...)` 换成 `run_via_transport(adapter, def, ...)`。trae 因此自动经现有 stream-json 路径真跑；claude/codex/cursor 行为不变。

- [ ] **Step 1: Add a focused test (trae routed via transport)**

```python
# tests/execution/test_local_agent_source_trae.py
from unittest.mock import patch

from skillhub_eval.core.schemas.report import ParsedStream, RunOutcome
from skillhub_eval.execution.local_agent_source import LocalAgentSource


def test_trae_case_runs_via_transport(tmp_path):
    bundle = {"skill_id": "demo", "has_scripts": False}
    case = {"id": "happy_001", "type": "happy_path", "risk_level": "low"}
    outcome = RunOutcome(exit_code=0, parsed_stream=ParsedStream(
        final_text='{"ok": true}', is_complete=True, usage={"total_tokens": 5}))

    with patch("skillhub_eval.execution.local_agent_source.has_exec_consent", return_value=True), \
         patch("skillhub_eval.execution.preferences.get_exec_agent", return_value="trae"), \
         patch("skillhub_eval.execution.preferences.get_exec_model", return_value="default"), \
         patch("skillhub_eval.execution.adapters.trae.TraeAdapter.detect", return_value=True), \
         patch("skillhub_eval.execution.local_agent_source.run_via_transport", return_value=outcome) as rv:
        src = LocalAgentSource(timeout_s=5)
        result = src.get_actual_output(str(tmp_path), "happy_001", case=case, bundle=bundle)

    assert rv.called
    assert result.source == "local_agent" and result.status == "ok"
    assert result.usage == {"total_tokens": 5}
    assert result.agent_id == "trae"
```

- [ ] **Step 2: Run** → FAIL (`run_via_transport` not imported/used).

- [ ] **Step 3: Implement** — in `local_agent_source.py`:

1. Import:

```python
from skillhub_eval.execution.transport.base import run_via_transport
```

2. Replace `_execute_once` body's runner call:

```python
    def _execute_once(self, bundle_path, case_id, case, bundle, adapter) -> RunOutcome:
        run_dir = self._workspace.acquire(bundle_path, case_id)
        try:
            prompt = build_harness_prompt(case, bundle)
            hardened = HardenedProfile.use_hardened(adapter, case)
            agent = get_agent_def(getattr(adapter, "agent_id", ""))
            return run_via_transport(
                adapter, agent, prompt,
                cwd=str(run_dir),
                timeout_s=self._case_timeout_s(case, bundle),
                hardened=hardened,
                runner=self._runner,
            )
        finally:
            self._workspace.release(run_dir)
```

(`get_agent_def` is already imported. `run_via_transport` for stream-json delegates to `self._runner.run`, so `is_run_complete`/usage/level/sanitizer paths downstream are unchanged.)

- [ ] **Step 4: Run** `pytest tests/execution -v` → PASS (full execution regression).

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/execution/local_agent_source.py tests/execution/test_local_agent_source_trae.py
git commit -m "feat(exec): route case execution through transport seam"
```

---

## Phase 5 — API scan 充实

### Task 5.1: `GET /api/exec/agents/scan` 返回真三态 + 安装指引 + 发现模型

**Files:** `skillhub_eval/adapters/api/routes/exec.py`、`tests/adapters/test_exec_bridge_api.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/adapters/test_exec_bridge_api.py (append)
from unittest.mock import patch
from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import app
from skillhub_eval.execution import detection
from skillhub_eval.execution.detection import DetectionResult


def test_scan_returns_authstate_models_install_hint():
    detection.clear_detection_cache()

    def fake_detect(agent, force=False):
        if agent.agent_id == "codex":
            return DetectionResult("codex", True, "/bin/codex", "ok")
        return DetectionResult(agent.agent_id, False, None, "missing", "not found")

    with patch("skillhub_eval.adapters.api.routes.exec.detect_agent", side_effect=fake_detect):
        resp = TestClient(app).get("/api/exec/agents/scan")
    assert resp.status_code == 200
    agents = {a["id"]: a for a in resp.json()["agents"]}
    assert agents["codex"]["detected"] is True
    assert agents["codex"]["auth_status"] == "ok"
    assert agents["codex"]["models"]
    assert agents["claude"]["detected"] is False
    assert agents["claude"]["install_command"]
```

- [ ] **Step 2: Run** → FAIL (no `install_command`; auth not real).

- [ ] **Step 3: Implement** — in `exec.py`:

1. Imports:

```python
from skillhub_eval.execution.detection import detect_agent
from skillhub_eval.execution.models import discover_models
from skillhub_eval.execution.install_hints import get_install_hint
```

2. Extend `AgentScanItem` with `install_command` / `install_docs_url` / `install_note` (all `str | None = None`).

3. Rewrite `scan_agents` loop to use `detect_agent` (three-state), `discover_models` (per agent, with `stored_model=selected_model`), and `get_install_hint` for undetected agents. Remove the cursor `auth_status="unknown"` special-case (detection now owns it).

- [ ] **Step 4: Run** `pytest tests/adapters/test_exec_bridge_api.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/api/routes/exec.py tests/adapters/test_exec_bridge_api.py
git commit -m "feat(api): scan returns three-state auth, discovered models, install hints"
```

---

## Phase 6 — UI 接线 `[ui-only]`

### Task 6.1: 三态徽章 + 模型来源 + 安装指引卡

**Files:** `skillhub_eval/adapters/ui/static/assets/index.js`

- [ ] **Step 1: 三态徽章** — 把 agent 卡片里原 `认证：${auth_status}` 文本替换为映射徽章：

```javascript
const AUTH_LABELS = { ok: '可用', missing: '未登录', unknown: '待测试' };
const authState = agent.auth_status || (agent.detected ? 'unknown' : 'missing');
const authBadge = agent.detected
  ? `<span class="text-[11px] px-1.5 py-0.5 rounded ${authState==='ok'?'bg-emerald-900 text-emerald-200':authState==='missing'?'bg-amber-900 text-amber-200':'bg-gray-700 text-gray-300'}">${AUTH_LABELS[authState]||authState}</span>`
  : `<span class="text-[11px] px-1.5 py-0.5 rounded bg-gray-800 text-gray-400">未安装</span>`;
```

- [ ] **Step 2: 安装指引卡** — 未检测到的 agent 显示可复制安装命令 + 文档链接：

```javascript
const installBlock = agent.install_command
  ? `<div class="mt-1 text-[11px] text-gray-400">
       <code class="bg-gray-900 px-1 rounded">${escapeHtml(agent.install_command)}</code>
       <button data-copy="${escapeHtml(agent.install_command)}" class="ml-2 underline">复制</button>
       ${agent.install_docs_url ? `<a href="${escapeHtml(agent.install_docs_url)}" target="_blank" class="ml-2 underline">官方文档</a>` : ''}
       <div class="text-gray-500 mt-0.5">${escapeHtml(agent.install_note || '')}</div>
       <div class="text-gray-500">装好后点「重新扫描」。</div>
     </div>`
  : '';
```

为 `[data-copy]` 绑定 `navigator.clipboard.writeText` 点击处理。

- [ ] **Step 3: 模型下拉** — 确认选中 agent 的模型下拉用 scan 返回的 `models[]` 填充，并含「自定义…」选项（写 `exec_model`）。

- [ ] **Step 4: Syntax check** — `node --check skillhub_eval/adapters/ui/static/assets/index.js` → 无输出。

- [ ] **Step 5: Manual smoke** — `serve` 后开执行模式抽屉，重新扫描：codex 可用、trae 可用/未登录、未装 CLI 显示安装命令；选 trae 见其 `trae-cli models` 模型下拉。

- [ ] **Step 6: Commit**

```bash
git add skillhub_eval/adapters/ui/static/assets/index.js
git commit -m "feat(ui): three-state badges, install hints, model dropdown wiring [ui-only]"
```

---

## Phase 7 — fixture、文档、验收（放最后）

### Task 7.1: 真机 E2E（默认 skip）— codex + trae

**Files:** `tests/execution/test_local_exec_e2e.py`

- [ ] **Step 1: Write env-guarded E2E**

```python
# tests/execution/test_local_exec_e2e.py
import os
import pytest

from skillhub_eval.execution.agent_registry import get_agent_def, resolve_adapter
from skillhub_eval.execution.runner import LocalAgentRunner

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_LOCAL_AGENT") != "1",
    reason="requires local CLI (set RUN_LOCAL_AGENT=1)",
)


@pytest.mark.parametrize("agent_id", ["codex", "trae"])
def test_real_agent_runs(agent_id, tmp_path):
    adapter = resolve_adapter(agent_id)
    assert adapter and adapter.detect()
    outcome = LocalAgentRunner().run(
        adapter, "Reply with the single word OK.", cwd=str(tmp_path), timeout_s=120,
    )
    assert outcome.parsed_stream is not None
```

- [ ] **Step 2: Run** (default) → SKIPPED.

- [ ] **Step 3: Real run on this machine** — `$env:RUN_LOCAL_AGENT=1; pytest tests/execution/test_local_exec_e2e.py -v`. **抓 trae stdout 一段 stream-json**，若 `parse_stream_events`/prompt-via-stdin 与实际不符，在此校准 trae adapter（位置参 vs stdin、事件字段）。补一条 trae 录制样本回归用例到 `tests/execution/test_adapter_trae.py`。

- [ ] **Step 4: Commit**

```bash
git add tests/execution/test_local_exec_e2e.py tests/execution/test_adapter_trae.py
git commit -m "test(exec): real-CLI e2e (codex+trae, skipped without RUN_LOCAL_AGENT) + trae sample"
```

### Task 7.2: 文档登记（RECORD / SPRINT）

**Files:** `RECORD.md`（section patch only）、`.project_memory/active/SPRINT_phase3-eval-system.md`

- [ ] **Step 1** Patch RECORD Q-26 状态 + 2026 流水（grill 定稿：ACP→stream-json、数据驱动检测、cursor 待重装）。
- [ ] **Step 2** 勾选 SPRINT W8.7 对应项。
- [ ] **Step 3** `python scripts/check_doc_encoding.py` → `doc encoding OK`.
- [ ] **Step 4: Commit**

```bash
git add RECORD.md .project_memory/active/SPRINT_phase3-eval-system.md
git commit -m "docs: record W8.7 adapter framework progress (grill-finalized)"
```

### Task 7.3: 全量回归 + 验收

- [ ] **Step 1** `pytest -q` 全绿（现有 + 新增；无回归）。
- [ ] **Step 2** `python scripts/check_doc_encoding.py` + `node --check skillhub_eval/adapters/ui/static/assets/index.js` 均干净。
- [ ] **Step 3** 真机：`$env:RUN_LOCAL_AGENT=1; pytest tests/execution/test_local_exec_e2e.py -v`（codex+trae 通过）；UI 选 trae → 选模型 → Test → 跑一个 fixture skill 出 Pass/Warn/Fail。
- [ ] **Step 4** cursor-agent 重装修好后，把 `["codex","trae"]` 扩到含 `"cursor-agent"` 复跑一次。
- [ ] **Step 5: Commit** 任何修补。

```bash
git add -A
git commit -m "chore(exec): adapter framework verification fixups"
```

---

## Self-Review

**决策覆盖：** G1（Task 3.1 trae stream-json）✅ G2（Task 4.1 dispatch + acp 扩展点）✅ G3（Task 1.2 数据驱动解析）✅ G4（Task 2.1 通用 model_probe）✅ G5（Task 1.2 三态）✅ G6（Task 0.2/3.1 trae 名+参数）✅ G7（Task 7.1/7.3）✅ G8（Task 4.2 经 seam 不改 ExecResult/judge）✅

**Placeholder scan:** 无 TODO/TBD；新模块给完整代码；"修改现有"步骤给确切替换体与导入。

**Type consistency:** `ParsedStream`/`RunOutcome`（report.py 现有）贯穿 transport；`AgentDef` 新字段在 0.2 定义后于 detection/models/transport/adapter 一致引用；`DetectionResult`/`ModelDiscovery` 各自定义并在 API/preferences 复用。

**风险点（执行时注意）：**
1. **trae 真实 stream-json 形状 / prompt 投递**：唯一需真机校准项（Task 7.1）——事件字段是否被 `parse_stream_events` 正确识别、prompt 走 stdin 还是位置参。其余全部可离线测。
2. `local_agent_source._execute_once` 改动牵动现有 `tests/execution`：Phase 4 必跑全量执行回归（注意以 `adapter=` 构造 `LocalAgentSource` 的用例仍兼容——seam 仍接收 adapter）。
3. 检测缓存进程内（serve 期 24h）；scan 如需强制刷新可加 `?force=1`（执行时若需要再补，非本计划必需项）。
4. cursor-agent 本机当前损坏（外部工具版本目录命名问题），不影响框架交付，仅延后其真机验收。
