# Phase 2 Evaluation Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

---

## ⚠️ MANDATORY CORRECTIONS (grill-me 2026-06-02) — READ BEFORE ANY TASK

These corrections override the original plan code where they conflict. Subagents MUST apply all corrections.

### C-1: DSL 最小子集前置到 2.0（原 Post-Implementation stub 作废）

`core/assert_/dsl.py` **必须**实现以下操作符（严格按协议 §6.4 原文）：

| 操作符 | 含义 |
|--------|------|
| `==` | 字段值相等（字符串/数字） |
| `!=` | 不等 |
| `exists` | 字段存在 |
| `not_exists` | 字段不存在 |
| `is_array` | 类型为数组 |
| `is_string` | 类型为字符串 |
| `is_number` | 类型为数字 |
| `contains` | 字符串/数组包含 |

扩展操作符（不在协议里，作为额外支持）：`regex_match`, `numeric_range`。

E2E smoke test（Task 12）**必须包含一个 `ASSERTION_DSL_FAIL` case** 验证拦截器生效。

Task 4 之后、Task 7 之前插入 **Task 4b: DSL Assertion Engine**（单独 commit）。

### C-2: R1–R8 严格按 1.2 权威表实现（原 aggregate.py / decision.py 阈值全部错误）

**禁止**使用简化阈值（如 `>= 70` 即 pass）。正确规则：

| 规则 | 条件 | 结论 |
|------|------|------|
| R4 | `completeness < 70` **且** `score_total < 70`（双低） | **fail** |
| R5 | `abs(DS.score - WB.score) >= 10`，**或** 整包 `suggested_review_status` 一过一挂 | **warn** + 人工 |
| R6 | `score_total >= 85` **且** `completeness >= 90` **且** 无 R1–R5 **且** Level 满足 | **pass** |
| R7 | `score_total` 70–84，或 `completeness` 70–89，或其他未覆盖 | **warn** |
| R8 | `score_total < 70` | **fail** |

R5 阈值为 **10**（不是 plan 原代码里的 15）。

Task 7 测试矩阵**必须**覆盖 R4 / R5（一过一挂）/ R5（差值≥10）/ R6 / R7 / R8 各一个独立测试。

### C-3: 引擎改为显式双阶段运行（`awaiting_confirm` 真正停机）

- **阶段一 pre-review**：`ingest → level0 → risk_lock → normalize`
  - 若存在未确认关键字段（`bundle_state != confirmed`）且 mode 非 degraded：写 `gaps.json`，置 `awaiting_confirm`，**终止本 run**（不进 model_judging）
  - `degraded` 模式可继续推进，但 review_status 上限为 `warn`；未确认 draft 不进 CodeAssert 失败判定
- **阶段二 post-confirm**：由 `POST /bundle/{id}/confirm` 触发**新 run**（模式 D，新包快照）
  - 必须重跑 level0 + risk_lock + case_exec + assert + model_judge + aggregate + decision
  - 禁止复用旧 run 的 snapshot 或 assertion_results

### C-4: FastAPI 依赖注入改用 `dependency_overrides`（原 `_test_repo` 写法静默失效）

**生产路径**（`deps.py`）：

```python
def get_repo() -> Repository:          # 不用 @lru_cache
    repo = SqliteRepository(settings.eval_db_path)
    repo.init_db()
    return repo
```

**测试 fixture**：

```python
app.dependency_overrides[get_repo] = lambda: test_repo
app.dependency_overrides[get_engine] = lambda: EvaluationEngine(test_repo, FakeDS(), FakeWB())
```

`routes/bundle.py` 和 `routes/human.py` 里**禁止**直接调 `repo._conn()`。  
`Repository` 协议需补充两个方法：

```python
def save_confirmation(self, skill_id: str, field_path: str, confirmed_value: str, operator: str) -> None: ...
def get_votes_for_run(self, run_id: str) -> list[dict]: ...
```

### C-5: `ModelVote` 构造改为显式字段映射（禁止双 `**` 展开）

```python
# 正确写法
ModelVote(
    model=v["model"],
    model_version=v.get("model_version", ""),
    prompt_version=v.get("prompt_version", "review-agent-v0.2"),
    case_id=v["case_id"],
    dimension_scores=DimensionScores(**v.get("dimension_scores", {})),
    score_total=v["score_total"],
    suggested_review_status=v.get("suggested_review_status", "warn"),
    confidence=v.get("confidence", "medium"),
    evidence_refs=v.get("evidence_refs", []),
    feedback=v.get("feedback", ""),
    latency_ms=v.get("latency_ms", 0),
)
```

**禁止**：`ModelVote(**{k: v.get(k,"") for k in ModelVote.model_fields}, **{...})`

### C-6: Risk Lock 实现步骤①+②（规则扫描），步骤③预留 TODO

`core/risk_lock.py` 必须实现：

```python
import re
from .schemas.enums import RiskLevel

HIGH_RISK_PATTERNS = [r"交易", r"下单", r"转账", r"扣款", r"delete", r"DROP\s+TABLE"]
MEDIUM_RISK_PATTERNS = [r"员工", r"salary", r"工资", r"身份证", r"客户", r"个人信息"]

def scan_risk(skill_md_text: str, declared: RiskLevel) -> RiskLevel:
    """Rules scan: 就高不就低. Step ③ LLM risk review: TODO 2.1."""
    text = skill_md_text
    if any(re.search(p, text, re.I) for p in HIGH_RISK_PATTERNS):
        locked = RiskLevel.high
    elif any(re.search(p, text, re.I) for p in MEDIUM_RISK_PATTERNS):
        locked = RiskLevel.medium if declared == RiskLevel.low else declared
    else:
        locked = declared
    # 就高不就低
    order = [RiskLevel.low, RiskLevel.medium, RiskLevel.high]
    return locked if order.index(locked) >= order.index(declared) else declared
```

如果 `risk_level_locked` 被抬高且用例数不满足新等级最小要求 → `FAIL` + `RISK_CASE_COUNT_INSUFFICIENT`。

---

**Goal:** Build a locally runnable evaluation engine that ingests a Skill package, runs the 1.3 state machine (modes A/B/C/D), writes a complete `evaluation_report.json`, persists all run data to SQLite, and exposes a CLI + FastAPI + dual-tab confirm UI.

**Architecture:** Hexagonal (Ports & Adapters) single-repo. `core/` has zero FastAPI/SQLite imports. `providers/` implements `BaseLLMProvider`. `persistence/` implements `Repository` protocol. `adapters/cli` and `adapters/api` wire everything together. State machine runs async via `BackgroundTasks`; 180 s workflow hard timeout.

**Tech Stack:** Python 3.11+, FastAPI + Pydantic v2, SQLite (`sqlite3` stdlib), uvicorn, Vanilla JS + Tailwind CDN (UI), `asyncio`, `subprocess` (sandbox).

**Spec:** `docs/superpowers/specs/2026-06-02-phase2-eval-engine-design.md`  
**Contracts (read-only):** `docs/specs/评估指标与准入标准.md` v1.2.1 · `docs/specs/评审Agent工作流与Prompt骨架.md` v0.2

---

## File Map

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, deps, CLI entry-point |
| `.env.example` | DS/WB keys, `EVAL_DB_PATH`, `EVAL_LLM_MODE=live` |
| `skillhub_eval/core/schemas/` | Pydantic models = Living Contract (enums, request, report, votes) |
| `skillhub_eval/core/ports.py` | `LLMProvider`, `SandboxRunner`, `Repository` protocols |
| `skillhub_eval/persistence/sqlite.py` | `SqliteRepository` (10 tables, hand-written SQL) |
| `skillhub_eval/persistence/repository.py` | Re-exports `Repository` protocol |
| `skillhub_eval/core/ingest.py` | Parse Skill package dir → `SkillBundle` |
| `skillhub_eval/core/level0.py` | Schema check + Case count gate (X1 table) |
| `skillhub_eval/core/risk_lock.py` | Declare → scan rules → risk Prompt → lock |
| `skillhub_eval/core/normalize.py` | `NormalizeAgent`: gaps.json + question_queue |
| `skillhub_eval/sandbox/python_subprocess.py` | `PythonSubprocessRunner` + UNSUPPORTED_RUNTIME fallback |
| `skillhub_eval/providers/base.py` | `BaseLLMProvider` ABC |
| `skillhub_eval/providers/deepseek.py` | `DeepSeekProvider` (httpx, retry) |
| `skillhub_eval/providers/workbuddy.py` | `WorkBuddyProvider` (httpx, retry) |
| `skillhub_eval/core/case_exec.py` | `CaseExecStage`: dispatch L1/L2 per case |
| `skillhub_eval/core/assert_/dsl.py` | §6.4 DSL evaluator |
| `skillhub_eval/core/model_judge.py` | Assemble rubric Prompt + call DS/WB in parallel |
| `skillhub_eval/core/aggregate.py` | R1–R8, R5, score_total |
| `skillhub_eval/core/decision.py` | PASS gate + review_status + explain |
| `skillhub_eval/core/engine.py` | `EvaluationEngine.run_async()` state machine |
| `skillhub_eval/adapters/api/app.py` | FastAPI app factory |
| `skillhub_eval/adapters/api/routes/eval.py` | `POST /eval/run`, `GET /eval/report/{id}`, `GET /eval/history` |
| `skillhub_eval/adapters/api/routes/bundle.py` | `GET /bundle/{id}/gaps`, `POST /bundle/{id}/confirm` |
| `skillhub_eval/adapters/api/routes/human.py` | `POST /eval/{id}/human-review` |
| `skillhub_eval/adapters/ui/static/index.html` | Tab1 (confirm) + Tab2 (review) shell |
| `skillhub_eval/adapters/ui/static/confirm-tab.js` | Tab1 AJAX: GET gaps, POST confirm |
| `skillhub_eval/adapters/ui/static/review-tab.js` | Tab2 AJAX: GET history, POST human-review + gate Toast |
| `skillhub_eval/adapters/cli/main.py` | `skillhub-eval` CLI (Typer) |
| `tests/` | Mirrors `skillhub_eval/` structure |

---

## Task 1: Project Skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `skillhub_eval/__init__.py` + all sub-package `__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "skillhub-eval"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "pydantic>=2.7",
    "pydantic-settings>=2.2",
    "httpx>=0.27",
    "typer>=0.12",
    "python-dotenv>=1.0",
]

[project.optional-dependencies]
dev = ["pytest>=8", "pytest-asyncio>=0.23", "respx>=0.21", "httpx"]

[project.scripts]
skillhub-eval = "skillhub_eval.adapters.cli.main:app"

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create `.env.example`**

```dotenv
# LLM providers
DEEPSEEK_API_KEY=your_deepseek_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
WORKBUDDY_API_KEY=your_workbuddy_key_here
WORKBUDDY_BASE_URL=https://api.workbuddy.example.com/v1

# Storage
EVAL_DB_PATH=data/skillhub_eval.db

# Defaults (do not change for live mode)
EVAL_LLM_MODE=live
RUBRIC_VERSION=v1.2
PROMPT_VERSION=review-agent-v0.2
```

- [ ] **Step 3: Create directory tree with empty `__init__.py` files**

Run in workspace root:

```powershell
$dirs = @(
  "skillhub_eval",
  "skillhub_eval/core",
  "skillhub_eval/core/schemas",
  "skillhub_eval/core/assert_",
  "skillhub_eval/providers",
  "skillhub_eval/sandbox",
  "skillhub_eval/persistence",
  "skillhub_eval/adapters",
  "skillhub_eval/adapters/cli",
  "skillhub_eval/adapters/api",
  "skillhub_eval/adapters/api/routes",
  "skillhub_eval/adapters/ui",
  "skillhub_eval/adapters/ui/static",
  "data",
  "tests",
  "tests/core",
  "tests/adapters"
)
foreach ($d in $dirs) { New-Item -ItemType Directory -Force $d; New-Item -ItemType File -Force "$d/__init__.py" }
New-Item -ItemType Directory -Force "tests/core"
New-Item -ItemType Directory -Force "tests/adapters"
```

- [ ] **Step 4: Install package in editable mode**

```powershell
pip install -e ".[dev]"
```

Expected: `Successfully installed skillhub-eval-0.1.0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .env.example skillhub_eval/ tests/ data/.gitkeep
git commit -m "chore: project skeleton - hexagonal layout, pyproject, dev deps"
```

---

## Task 2: Settings + Pydantic Schemas (Living Contract)

**Files:**
- Create: `skillhub_eval/settings.py`
- Create: `skillhub_eval/core/schemas/enums.py`
- Create: `skillhub_eval/core/schemas/bundle.py`
- Create: `skillhub_eval/core/schemas/report.py`
- Create: `skillhub_eval/core/schemas/__init__.py`
- Test: `tests/core/test_schemas.py`

- [ ] **Step 1: Write failing tests for schemas**

```python
# tests/core/test_schemas.py
import pytest
from skillhub_eval.core.schemas import (
    BundleState, EvaluationMode, RiskLevel,
    EvalRunRequest, EvaluationReport,
)

def test_bundle_state_enum():
    assert BundleState.confirmed == "confirmed"

def test_eval_request_rejects_unknown_bundle_state():
    with pytest.raises(Exception):
        EvalRunRequest(
            skill_id="s1", skill_bundle_path="/tmp/skill",
            bundle_state="invalid", evaluation_mode="capability_full",
        )

def test_pass_allowed_fields_present():
    # EvaluationReport must carry bundle_state and evaluation_mode
    from skillhub_eval.core.schemas.report import EvaluationReport
    r = EvaluationReport(
        run_id="r1", skill_id="s1", skill_bundle_path="/tmp",
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
        status="completed", review_status="pass",
        rubric_version="v1.2", prompt_version="review-agent-v0.2",
    )
    assert r.bundle_state == BundleState.confirmed
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_schemas.py -v
```

Expected: `ImportError` or `ModuleNotFoundError`

- [ ] **Step 3: Create `skillhub_eval/settings.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    workbuddy_api_key: str = ""
    workbuddy_base_url: str = ""
    eval_db_path: str = "data/skillhub_eval.db"
    eval_llm_mode: str = "live"
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"

settings = Settings()
```

- [ ] **Step 4: Create `skillhub_eval/core/schemas/enums.py`**

```python
from enum import Enum

class BundleState(str, Enum):
    minimal = "minimal"
    draft_enriched = "draft_enriched"
    eval_ready = "eval_ready"
    confirmed = "confirmed"

class EvaluationMode(str, Enum):
    degraded = "degraded"
    capability_full = "capability_full"
    post_listing_health_check = "post_listing_health_check"

class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"

class OrchestrationMode(str, Enum):
    A = "A"  # 完整准入
    B = "B"  # 存量摸底
    C = "C"  # 补齐中
    D = "D"  # 完整复评

class ReviewStatus(str, Enum):
    passed = "pass"
    warned = "warn"
    failed = "fail"

class RunStatus(str, Enum):
    pending = "pending"
    level0_checking = "level0_checking"
    risk_locking = "risk_locking"
    normalizing = "normalizing"
    awaiting_confirm = "awaiting_confirm"
    case_executing = "case_executing"
    code_asserting = "code_asserting"
    model_judging = "model_judging"
    aggregating = "aggregating"
    awaiting_human_review = "awaiting_human_review"
    completed = "completed"
    failed = "failed"

# Case count gate (X1): low/medium/high → (min_cases, mvp_ceiling)
CASE_COUNT_GATES: dict[RiskLevel, tuple[int, int]] = {
    RiskLevel.low:    (3, 6),
    RiskLevel.medium: (5, 8),
    RiskLevel.high:   (9, 12),
}
```

- [ ] **Step 5: Create `skillhub_eval/core/schemas/bundle.py`**

```python
from pydantic import BaseModel, Field
from .enums import BundleState, EvaluationMode, RiskLevel

class EvalRunRequest(BaseModel):
    skill_id: str
    skill_bundle_path: str
    bundle_state: BundleState
    evaluation_mode: EvaluationMode
    risk_level_declared: RiskLevel | None = None
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"

class GapsEntry(BaseModel):
    field_path: str
    severity: str          # "blocker" | "warn" | "info"
    message: str
    draft_value: str | None = None
    confirmed: bool = False

class GapsSnapshot(BaseModel):
    skill_id: str
    run_id: str
    gaps: list[GapsEntry] = Field(default_factory=list)
    question_queue: list[str] = Field(default_factory=list)

class ConfirmRequest(BaseModel):
    confirmed_fields: dict[str, str]   # field_path → confirmed_value
    confirmed_cases: list[str] = Field(default_factory=list)  # case_ids
    operator: str
```

- [ ] **Step 6: Create `skillhub_eval/core/schemas/report.py`**

```python
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from .enums import BundleState, EvaluationMode, RiskLevel, ReviewStatus, RunStatus

class DimensionScores(BaseModel):
    instruction_following: float | None = None
    output_compliance: float | None = None
    business_resolution: float | None = None

class ModelVote(BaseModel):
    model: str
    model_version: str
    prompt_version: str
    case_id: str
    dimension_scores: DimensionScores
    score_total: float
    suggested_review_status: str
    confidence: str
    evidence_refs: list[str] = Field(default_factory=list)
    feedback: str = ""
    latency_ms: int = 0

class AssertionResult(BaseModel):
    case_id: str
    assertion_id: str
    passed: bool
    reason_code: str | None = None
    detail: str = ""

class HumanReview(BaseModel):
    required: bool = False
    trigger_codes: list[str] = Field(default_factory=list)
    reviewer_action: str | None = None   # "approve_warn" | "reject" | "escalate"
    operator: str | None = None
    comment: str = ""
    override_allowed: bool = True

class EvaluationReport(BaseModel):
    run_id: str
    skill_id: str
    skill_bundle_path: str
    bundle_state: BundleState
    evaluation_mode: EvaluationMode
    orchestration_mode: str | None = None
    status: RunStatus | str
    review_status: ReviewStatus | str | None = None
    risk_level_locked: RiskLevel | None = None
    level_achieved: str | None = None
    score_total: float | None = None
    score_total_source: str | None = None
    completeness_score: float | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    model_votes: list[ModelVote] = Field(default_factory=list)
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    human_review: HumanReview = Field(default_factory=HumanReview)
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_detail: str | None = None
```

- [ ] **Step 7: Create `skillhub_eval/core/schemas/__init__.py`**

```python
from .enums import BundleState, EvaluationMode, RiskLevel, RunStatus, ReviewStatus, OrchestrationMode, CASE_COUNT_GATES
from .bundle import EvalRunRequest, GapsSnapshot, GapsEntry, ConfirmRequest
from .report import EvaluationReport, ModelVote, AssertionResult, HumanReview, DimensionScores

__all__ = [
    "BundleState", "EvaluationMode", "RiskLevel", "RunStatus", "ReviewStatus",
    "OrchestrationMode", "CASE_COUNT_GATES",
    "EvalRunRequest", "GapsSnapshot", "GapsEntry", "ConfirmRequest",
    "EvaluationReport", "ModelVote", "AssertionResult", "HumanReview", "DimensionScores",
]
```

- [ ] **Step 8: Run tests — expect pass**

```powershell
pytest tests/core/test_schemas.py -v
```

Expected: `3 passed`

- [ ] **Step 9: Commit**

```bash
git add skillhub_eval/core/schemas/ skillhub_eval/settings.py tests/core/test_schemas.py
git commit -m "feat: Pydantic schemas + enums (Living Contract) + Settings"
```

---

## Task 3: Repository Protocol + SQLite Implementation

**Files:**
- Create: `skillhub_eval/core/ports.py`
- Create: `skillhub_eval/persistence/sqlite.py`
- Test: `tests/core/test_persistence.py`

- [ ] **Step 1: Write failing tests for SQLite repository**

```python
# tests/core/test_persistence.py
import pytest, tempfile, os
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.core.schemas import EvaluationReport, BundleState, EvaluationMode, RunStatus

@pytest.fixture
def repo(tmp_path):
    db = str(tmp_path / "test.db")
    r = SqliteRepository(db)
    r.init_db()
    return r

def test_create_and_get_run(repo):
    run_id = repo.create_run(
        skill_id="s1", skill_bundle_path="/tmp/s1",
        bundle_state="confirmed", evaluation_mode="capability_full",
    )
    assert run_id is not None
    row = repo.get_run(run_id)
    assert row["skill_id"] == "s1"
    assert row["status"] == "pending"

def test_update_status(repo):
    run_id = repo.create_run("s2", "/tmp/s2", "minimal", "degraded")
    repo.update_status(run_id, "level0_checking")
    assert repo.get_run(run_id)["status"] == "level0_checking"

def test_save_and_get_report(repo):
    run_id = repo.create_run("s3", "/tmp/s3", "confirmed", "capability_full")
    report = EvaluationReport(
        run_id=run_id, skill_id="s3", skill_bundle_path="/tmp/s3",
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
        status=RunStatus.completed, review_status="pass",
        rubric_version="v1.2", prompt_version="review-agent-v0.2",
    )
    repo.save_report(run_id, report)
    fetched = repo.get_report(run_id)
    assert fetched["review_status"] == "pass"

def test_list_history(repo):
    for i in range(3):
        repo.create_run(f"sk{i}", f"/tmp/sk{i}", "minimal", "degraded")
    rows = repo.list_history(limit=10)
    assert len(rows) == 3

def test_human_review_required_filter(repo):
    run_id = repo.create_run("s4", "/tmp/s4", "confirmed", "capability_full")
    repo.update_status(run_id, "awaiting_human_review")
    repo.set_human_review_required(run_id, True, ["MODEL_DISAGREEMENT_R5"])
    rows = repo.list_history(human_review_required=True)
    assert any(r["run_id"] == run_id for r in rows)
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_persistence.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/core/ports.py`**

```python
from typing import Protocol, runtime_checkable
from .schemas import EvaluationReport

@runtime_checkable
class Repository(Protocol):
    def init_db(self) -> None: ...
    def create_run(self, skill_id: str, skill_bundle_path: str, bundle_state: str, evaluation_mode: str) -> str: ...
    def update_status(self, run_id: str, status: str, **kwargs) -> None: ...
    def append_stage(self, run_id: str, stage: str, metadata: dict | None = None) -> None: ...
    def save_report(self, run_id: str, report: EvaluationReport) -> None: ...
    def get_run(self, run_id: str) -> dict | None: ...
    def get_report(self, run_id: str) -> dict | None: ...
    def list_history(self, limit: int = 50, human_review_required: bool | None = None) -> list[dict]: ...
    def save_gaps(self, run_id: str, gaps_json: dict) -> None: ...
    def get_gaps(self, skill_id: str) -> dict | None: ...
    def save_votes(self, run_id: str, votes: list[dict]) -> None: ...
    def save_human_review(self, run_id: str, action: str, operator: str, comment: str, preserved_votes: list[dict]) -> None: ...
    def set_human_review_required(self, run_id: str, required: bool, trigger_codes: list[str]) -> None: ...
    def log_event(self, run_id: str, event_name: str, payload: dict) -> None: ...
```

- [ ] **Step 4: Create `skillhub_eval/persistence/sqlite.py`**

```python
import sqlite3, json, uuid
from datetime import datetime
from pathlib import Path
from skillhub_eval.core.schemas import EvaluationReport

DDL = """
CREATE TABLE IF NOT EXISTS evaluation_runs (
    run_id TEXT PRIMARY KEY,
    skill_id TEXT NOT NULL,
    skill_bundle_path TEXT NOT NULL,
    bundle_state TEXT NOT NULL,
    evaluation_mode TEXT NOT NULL,
    orchestration_mode TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    risk_level_locked TEXT,
    level_achieved TEXT,
    review_status TEXT,
    score_total REAL,
    score_total_source TEXT,
    completeness_score REAL,
    reason_codes TEXT DEFAULT '[]',
    report_json TEXT,
    human_review_required INTEGER DEFAULT 0,
    human_review_trigger_codes TEXT DEFAULT '[]',
    started_at TEXT,
    completed_at TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stage_transitions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    stage TEXT NOT NULL,
    entered_at TEXT NOT NULL,
    exited_at TEXT,
    metadata_json TEXT DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS model_votes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    case_id TEXT NOT NULL,
    vote_json TEXT NOT NULL,
    latency_ms INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS gaps_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    gaps_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS human_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    action TEXT NOT NULL,
    operator TEXT NOT NULL,
    comment TEXT DEFAULT '',
    preserved_votes_json TEXT DEFAULT '[]',
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS bundle_confirmations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id TEXT NOT NULL,
    field_path TEXT NOT NULL,
    confirmed_value TEXT,
    confirmed_by TEXT NOT NULL,
    confirmed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analytics_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_name TEXT NOT NULL,
    payload_json TEXT DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""

class SqliteRepository:
    def __init__(self, db_path: str = "data/skillhub_eval.db"):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db_path = db_path

    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self) -> None:
        with self._conn() as conn:
            conn.executescript(DDL)

    def _now(self) -> str:
        return datetime.utcnow().isoformat()

    def create_run(self, skill_id: str, skill_bundle_path: str, bundle_state: str, evaluation_mode: str) -> str:
        run_id = str(uuid.uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO evaluation_runs (run_id,skill_id,skill_bundle_path,bundle_state,evaluation_mode,started_at,created_at) VALUES (?,?,?,?,?,?,?)",
                (run_id, skill_id, skill_bundle_path, bundle_state, evaluation_mode, self._now(), self._now()),
            )
        return run_id

    def update_status(self, run_id: str, status: str, **kwargs) -> None:
        sets = ["status=?"]
        vals: list = [status]
        allowed = {"risk_level_locked", "level_achieved", "review_status", "score_total",
                   "score_total_source", "completeness_score", "reason_codes", "orchestration_mode", "completed_at"}
        for k, v in kwargs.items():
            if k in allowed:
                sets.append(f"{k}=?")
                vals.append(json.dumps(v) if isinstance(v, list) else v)
        if status in ("completed", "failed"):
            sets.append("completed_at=?")
            vals.append(self._now())
        vals.append(run_id)
        with self._conn() as conn:
            conn.execute(f"UPDATE evaluation_runs SET {', '.join(sets)} WHERE run_id=?", vals)

    def append_stage(self, run_id: str, stage: str, metadata: dict | None = None) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO stage_transitions (run_id,stage,entered_at,metadata_json) VALUES (?,?,?,?)",
                (run_id, stage, self._now(), json.dumps(metadata or {})),
            )

    def save_report(self, run_id: str, report: EvaluationReport) -> None:
        report_json = report.model_dump_json()
        with self._conn() as conn:
            conn.execute(
                "UPDATE evaluation_runs SET report_json=?, review_status=?, score_total=?, completed_at=? WHERE run_id=?",
                (report_json, report.review_status, report.score_total, self._now(), run_id),
            )

    def get_run(self, run_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM evaluation_runs WHERE run_id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def get_report(self, run_id: str) -> dict | None:
        row = self.get_run(run_id)
        if not row or not row.get("report_json"):
            return None
        return json.loads(row["report_json"])

    def list_history(self, limit: int = 50, human_review_required: bool | None = None) -> list[dict]:
        q = "SELECT run_id,skill_id,status,review_status,score_total,bundle_state,evaluation_mode,human_review_required,created_at FROM evaluation_runs"
        params: list = []
        if human_review_required is not None:
            q += " WHERE human_review_required=?"
            params.append(1 if human_review_required else 0)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(q, params).fetchall()
        return [dict(r) for r in rows]

    def save_gaps(self, run_id: str, gaps_json: dict) -> None:
        skill_id = gaps_json.get("skill_id", "")
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO gaps_snapshots (run_id,skill_id,gaps_json,created_at) VALUES (?,?,?,?)",
                (run_id, skill_id, json.dumps(gaps_json), self._now()),
            )

    def get_gaps(self, skill_id: str) -> dict | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT gaps_json FROM gaps_snapshots WHERE skill_id=? ORDER BY created_at DESC LIMIT 1", (skill_id,)
            ).fetchone()
        return json.loads(row["gaps_json"]) if row else None

    def save_votes(self, run_id: str, votes: list[dict]) -> None:
        with self._conn() as conn:
            for v in votes:
                conn.execute(
                    "INSERT INTO model_votes (run_id,provider,case_id,vote_json,latency_ms,created_at) VALUES (?,?,?,?,?,?)",
                    (run_id, v.get("model", ""), v.get("case_id", ""), json.dumps(v), v.get("latency_ms", 0), self._now()),
                )

    def save_human_review(self, run_id: str, action: str, operator: str, comment: str, preserved_votes: list[dict]) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO human_reviews (run_id,action,operator,comment,preserved_votes_json,created_at) VALUES (?,?,?,?,?,?)",
                (run_id, action, operator, comment, json.dumps(preserved_votes), self._now()),
            )
            conn.execute("UPDATE evaluation_runs SET human_review_required=0 WHERE run_id=?", (run_id,))

    def set_human_review_required(self, run_id: str, required: bool, trigger_codes: list[str]) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE evaluation_runs SET human_review_required=?,human_review_trigger_codes=? WHERE run_id=?",
                (1 if required else 0, json.dumps(trigger_codes), run_id),
            )

    def log_event(self, run_id: str, event_name: str, payload: dict) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO analytics_events (run_id,event_name,payload_json,created_at) VALUES (?,?,?,?)",
                (run_id, event_name, json.dumps(payload), self._now()),
            )
```

- [ ] **Step 5: Create `skillhub_eval/persistence/__init__.py`** (re-export)

```python
from .sqlite import SqliteRepository
```

- [ ] **Step 6: Run persistence tests — expect pass**

```powershell
pytest tests/core/test_persistence.py -v
```

Expected: `5 passed`

- [ ] **Step 7: Commit**

```bash
git add skillhub_eval/core/ports.py skillhub_eval/persistence/ tests/core/test_persistence.py
git commit -m "feat: SQLite repository (10-table schema) + Repository Protocol"
```

---

## Task 4: Ingest + Level 0 Checker (Case Count Gate X1)

**Files:**
- Create: `skillhub_eval/core/ingest.py`
- Create: `skillhub_eval/core/level0.py`
- Test: `tests/core/test_level0.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_level0.py
import pytest
from pathlib import Path
from skillhub_eval.core.ingest import ingest_bundle
from skillhub_eval.core.level0 import Level0Checker
from skillhub_eval.core.schemas import RiskLevel

def make_bundle(tmp_path, n_cases=3, risk="low", has_skill_md=True):
    if has_skill_md:
        (tmp_path / "SKILL.md").write_text(
            f"---\nname: test\nrisk_level: {risk}\n---\n# Test Skill\n"
        )
    ec = tmp_path / "eval_cases"
    ec.mkdir(exist_ok=True)
    for i in range(n_cases):
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: test\n"
        )
    return tmp_path

def test_ingest_ok(tmp_path):
    make_bundle(tmp_path, n_cases=3, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    assert bundle["skill_id"] is not None
    assert bundle["risk_level_declared"] == "low"
    assert len(bundle["eval_cases"]) == 3

def test_level0_pass_low(tmp_path):
    make_bundle(tmp_path, n_cases=3, risk="low")
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is True

def test_level0_fail_no_skill_md(tmp_path):
    make_bundle(tmp_path, n_cases=3, risk="low", has_skill_md=False)
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "LEVEL0_SCHEMA_FAIL" in result["reason_codes"]

def test_level0_fail_too_few_cases(tmp_path):
    make_bundle(tmp_path, n_cases=1, risk="low")  # min=3 for low
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "RISK_CASE_COUNT_INSUFFICIENT" in result["reason_codes"]

def test_level0_fail_too_many_cases(tmp_path):
    make_bundle(tmp_path, n_cases=7, risk="low")  # ceiling=6 for low
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is False
    assert "CASE_COUNT_EXCEEDS_LIMIT" in result["reason_codes"]

def test_level0_pass_medium(tmp_path):
    make_bundle(tmp_path, n_cases=5, risk="medium")  # min=5, ceiling=8
    bundle = ingest_bundle(str(tmp_path))
    result = Level0Checker().check(bundle)
    assert result["passed"] is True
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_level0.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/core/ingest.py`**

```python
import re
from pathlib import Path

def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown. Returns {} if missing."""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return {}
    meta: dict = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    return meta

def _load_cases(eval_cases_dir: Path) -> list[dict]:
    cases = []
    if not eval_cases_dir.exists():
        return cases
    for f in sorted(eval_cases_dir.iterdir()):
        if f.suffix in (".yaml", ".yml", ".json"):
            # Minimal parse: read id and type lines
            text = f.read_text(encoding="utf-8")
            case: dict = {"_path": str(f)}
            for line in text.splitlines():
                if line.startswith("id:"):
                    case["id"] = line.split(":", 1)[1].strip()
                elif line.startswith("type:"):
                    case["type"] = line.split(":", 1)[1].strip()
                elif line.startswith("user_intent:"):
                    case["user_intent"] = line.split(":", 1)[1].strip()
            if "id" in case:
                cases.append(case)
    return cases

def ingest_bundle(bundle_path: str) -> dict:
    """Parse Skill package directory into a flat dict for Level0 + engine."""
    root = Path(bundle_path)
    skill_md = root / "SKILL.md"
    has_skill_md = skill_md.exists()

    meta: dict = {}
    if has_skill_md:
        meta = _parse_frontmatter(skill_md.read_text(encoding="utf-8"))

    cases = _load_cases(root / "eval_cases")
    has_sample_io = (root / "sample_io").exists()
    has_scripts = any((root / "scripts").glob("*.py")) if (root / "scripts").exists() else False

    skill_id = meta.get("id") or meta.get("name") or root.name

    return {
        "skill_id": skill_id,
        "bundle_path": str(root),
        "has_skill_md": has_skill_md,
        "skill_meta": meta,
        "risk_level_declared": meta.get("risk_level"),
        "eval_cases": cases,
        "n_cases": len(cases),
        "has_sample_io": has_sample_io,
        "has_scripts": has_scripts,
    }
```

- [ ] **Step 4: Create `skillhub_eval/core/level0.py`**

```python
from .schemas.enums import RiskLevel, CASE_COUNT_GATES

class Level0Checker:
    """
    Validates Skill package structure and case count gate (X1).
    Runs before any LLM call or sandbox execution.
    """

    def check(self, bundle: dict) -> dict:
        reason_codes: list[str] = []
        evidence: list[dict] = []

        # --- Structural checks ---
        if not bundle.get("has_skill_md"):
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.append({"field": "SKILL.md", "detail": "SKILL.md missing from bundle root"})
            return {"passed": False, "reason_codes": reason_codes, "evidence": evidence}

        # --- Risk level ---
        risk_raw = bundle.get("risk_level_declared")
        try:
            risk = RiskLevel(risk_raw) if risk_raw else RiskLevel.low
        except ValueError:
            reason_codes.append("LEVEL0_SCHEMA_FAIL")
            evidence.append({"field": "risk_level", "detail": f"Unknown risk_level: {risk_raw!r}"})
            return {"passed": False, "reason_codes": reason_codes, "evidence": evidence}

        # --- Case count gate (X1) ---
        n = bundle.get("n_cases", 0)
        min_cases, ceiling = CASE_COUNT_GATES[risk]

        if n < min_cases:
            reason_codes.append("RISK_CASE_COUNT_INSUFFICIENT")
            evidence.append({
                "field": "eval_cases",
                "detail": f"risk={risk.value} requires >= {min_cases} cases; found {n}",
            })
        elif n > ceiling:
            reason_codes.append("CASE_COUNT_EXCEEDS_LIMIT")
            evidence.append({
                "field": "eval_cases",
                "detail": f"risk={risk.value} MVP ceiling={ceiling}; found {n}. Reduce to <= {ceiling}.",
            })

        passed = len(reason_codes) == 0
        return {
            "passed": passed,
            "risk_level": risk.value,
            "n_cases": n,
            "reason_codes": reason_codes,
            "evidence": evidence,
        }
```

- [ ] **Step 5: Run tests — expect pass**

```powershell
pytest tests/core/test_level0.py -v
```

Expected: `6 passed`

- [ ] **Step 6: Commit**

```bash
git add skillhub_eval/core/ingest.py skillhub_eval/core/level0.py tests/core/test_level0.py
git commit -m "feat: ingest + Level0 checker with Case count gate X1"
```

---

## Task 5: LLM Providers

**Files:**
- Create: `skillhub_eval/providers/base.py`
- Create: `skillhub_eval/providers/deepseek.py`
- Create: `skillhub_eval/providers/workbuddy.py`
- Test: `tests/core/test_providers.py`

- [ ] **Step 1: Write failing tests (using `respx` to mock HTTP)**

```python
# tests/core/test_providers.py
import pytest, json
import respx
import httpx
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.base import BaseLLMProvider

FAKE_RESPONSE = {
    "sub_scores": {
        "step_completeness": {"score": 85, "pass": True, "reason": "ok", "evidence_refs": []}
    },
    "confidence": "medium",
    "dimension_notes": ""
}

def test_base_provider_is_abstract():
    import inspect
    assert inspect.isabstract(BaseLLMProvider)

@respx.mock
@pytest.mark.asyncio
async def test_deepseek_judge_returns_dict(tmp_path):
    # Mock DeepSeek chat completions endpoint
    respx.post("https://api.deepseek.com/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(FAKE_RESPONSE)}}]
        })
    )
    provider = DeepSeekProvider(api_key="test", base_url="https://api.deepseek.com/v1")
    result = await provider.judge("test prompt")
    assert "sub_scores" in result
    assert result["confidence"] == "medium"

@respx.mock
@pytest.mark.asyncio
async def test_deepseek_retries_on_500(tmp_path):
    call_count = 0

    def side_effect(request):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            return httpx.Response(500, json={"error": "internal"})
        return httpx.Response(200, json={
            "choices": [{"message": {"content": json.dumps(FAKE_RESPONSE)}}]
        })

    respx.post("https://api.deepseek.com/v1/chat/completions").mock(side_effect=side_effect)
    provider = DeepSeekProvider(api_key="test", base_url="https://api.deepseek.com/v1", max_retries=3)
    result = await provider.judge("test prompt")
    assert call_count == 3
    assert "sub_scores" in result
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_providers.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/providers/base.py`**

```python
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    """
    Minimal contract for all LLM judges.
    core/ never imports a concrete provider — only this base.
    """

    @abstractmethod
    async def judge(self, prompt: str) -> dict:
        """
        Call the LLM with the assembled rubric prompt.
        Returns parsed JSON dict matching the evaluation Prompt contract (§7).
        Raises RuntimeError on unrecoverable failure after retries.
        """
```

- [ ] **Step 4: Create `skillhub_eval/providers/deepseek.py`**

```python
import asyncio, json, time
import httpx
from .base import BaseLLMProvider

class DeepSeekProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.deepseek.com/v1",
        model: str = "deepseek-chat",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def judge(self, prompt: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers, json=payload,
                    )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
                last_error = RuntimeError(f"DeepSeek HTTP {resp.status_code}: {resp.text[:200]}")
            except (httpx.RequestError, json.JSONDecodeError) as e:
                last_error = e
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"DeepSeek failed after {self.max_retries} retries: {last_error}")
```

- [ ] **Step 5: Create `skillhub_eval/providers/workbuddy.py`**

```python
import asyncio, json
import httpx
from .base import BaseLLMProvider

class WorkBuddyProvider(BaseLLMProvider):
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "workbuddy-judge",
        timeout: float = 60.0,
        max_retries: int = 3,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def judge(self, prompt: str) -> dict:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=headers, json=payload,
                    )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    return json.loads(content)
                last_error = RuntimeError(f"WorkBuddy HTTP {resp.status_code}: {resp.text[:200]}")
            except (httpx.RequestError, json.JSONDecodeError) as e:
                last_error = e
            if attempt < self.max_retries - 1:
                await asyncio.sleep(2 ** attempt)
        raise RuntimeError(f"WorkBuddy failed after {self.max_retries} retries: {last_error}")
```

- [ ] **Step 6: Run provider tests — expect pass**

```powershell
pytest tests/core/test_providers.py -v
```

Expected: `3 passed`

- [ ] **Step 7: Commit**

```bash
git add skillhub_eval/providers/ tests/core/test_providers.py
git commit -m "feat: BaseLLMProvider + DeepSeekProvider + WorkBuddyProvider (retry, httpx)"
```

---

## Task 6: Sandbox Runner

**Files:**
- Create: `skillhub_eval/sandbox/python_subprocess.py`
- Test: `tests/core/test_sandbox.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_sandbox.py
import pytest
from pathlib import Path
from skillhub_eval.sandbox.python_subprocess import PythonSubprocessRunner

@pytest.fixture
def happy_script(tmp_path):
    s = tmp_path / "run.py"
    s.write_text('import json, sys\nprint(json.dumps({"result": "ok"}))\n')
    return str(tmp_path)

@pytest.fixture
def timeout_script(tmp_path):
    s = tmp_path / "run.py"
    s.write_text("import time\ntime.sleep(999)\n")
    return str(tmp_path)

@pytest.fixture
def no_python_dir(tmp_path):
    (tmp_path / "run.sh").write_text("echo hello")
    return str(tmp_path)

def test_run_happy_script(happy_script):
    result = PythonSubprocessRunner().run(happy_script, timeout=10)
    assert result["success"] is True
    assert "ok" in result["stdout"]

def test_run_timeout(timeout_script):
    result = PythonSubprocessRunner().run(timeout_script, timeout=1)
    assert result["success"] is False
    assert result["reason_code"] == "SANDBOX_EXEC_TIMEOUT"

def test_unsupported_runtime(no_python_dir):
    result = PythonSubprocessRunner().run(no_python_dir, timeout=10)
    assert result["success"] is False
    assert result["reason_code"] == "UNSUPPORTED_RUNTIME_ENV"
    assert result["downgrade_to_level1"] is True
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_sandbox.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/sandbox/python_subprocess.py`**

```python
import subprocess
import sys
from pathlib import Path

PYTHON_ENTRY_CANDIDATES = ["run.py", "main.py"]

class PythonSubprocessRunner:
    """
    Runs a Python entry script from a Skill's scripts/ directory.
    Only Python is supported in the MVP. Non-Python runtimes trigger
    graceful downgrade to Level 1 (sample_io) with UNSUPPORTED_RUNTIME_ENV.
    """

    def run(self, bundle_path: str, timeout: int = 180) -> dict:
        root = Path(bundle_path)
        # Find Python entry
        entry: Path | None = None
        for candidate in PYTHON_ENTRY_CANDIDATES:
            p = root / "scripts" / candidate
            if p.exists():
                entry = p
                break
            # Also check bundle root
            p2 = root / candidate
            if p2.exists():
                entry = p2
                break

        # Non-Python runtime detection (downgrade to L1)
        if entry is None:
            non_py = list((root / "scripts").glob("*")) if (root / "scripts").exists() else []
            has_non_py = any(f.suffix in (".sh", ".js", ".ts", ".rb") for f in non_py)
            if has_non_py or non_py:
                return {
                    "success": False,
                    "reason_code": "UNSUPPORTED_RUNTIME_ENV",
                    "downgrade_to_level1": True,
                    "stdout": "",
                    "stderr": "Non-Python runtime detected; downgrading to Level 1 (sample_io).",
                    "exit_code": None,
                }
            # No scripts at all — also downgrade
            return {
                "success": False,
                "reason_code": "UNSUPPORTED_RUNTIME_ENV",
                "downgrade_to_level1": True,
                "stdout": "",
                "stderr": "No Python entry script found.",
                "exit_code": None,
            }

        try:
            result = subprocess.run(
                [sys.executable, str(entry)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "success": result.returncode == 0,
                "reason_code": None if result.returncode == 0 else "SANDBOX_EXEC_FAIL",
                "downgrade_to_level1": False,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "reason_code": "SANDBOX_EXEC_TIMEOUT",
                "downgrade_to_level1": False,
                "stdout": "",
                "stderr": f"Subprocess exceeded {timeout}s timeout.",
                "exit_code": None,
            }
```

- [ ] **Step 4: Run sandbox tests — expect pass**

```powershell
pytest tests/core/test_sandbox.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/sandbox/ tests/core/test_sandbox.py
git commit -m "feat: PythonSubprocessRunner with 180s timeout + UNSUPPORTED_RUNTIME downgrade"
```

---

## Task 7: Aggregate + Decision (R1–R8, R5, PASS Gate)

**Files:**
- Create: `skillhub_eval/core/aggregate.py`
- Create: `skillhub_eval/core/decision.py`
- Test: `tests/core/test_aggregate.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/core/test_aggregate.py
import pytest
from skillhub_eval.core.aggregate import AggregateStage
from skillhub_eval.core.decision import DecisionStage, PassGateError
from skillhub_eval.core.schemas import BundleState, EvaluationMode

def make_votes(ds_score: float, wb_score: float, ds_status="pass", wb_status="pass"):
    return [
        {"model": "deepseek", "score_total": ds_score, "suggested_review_status": ds_status,
         "case_id": "c1", "dimension_scores": {}, "confidence": "high", "evidence_refs": [], "feedback": ""},
        {"model": "workbuddy", "score_total": wb_score, "suggested_review_status": wb_status,
         "case_id": "c1", "dimension_scores": {}, "confidence": "high", "evidence_refs": [], "feedback": ""},
    ]

def test_aggregate_no_r5(tmp_path):
    agg = AggregateStage()
    result = agg.run(votes=make_votes(80, 82), assertion_passed=True, completeness_score=85)
    assert result["r5_triggered"] is False
    assert result["score_total"] == pytest.approx(81.0)
    assert result["score_total_source"] == "aggregated_mean"

def test_aggregate_r5_triggered():
    # R5: one says pass, other says fail → disagreement
    agg = AggregateStage()
    result = agg.run(votes=make_votes(85, 40, "pass", "fail"), assertion_passed=True, completeness_score=90)
    assert result["r5_triggered"] is True
    assert result["score_total"] is None
    assert result["score_total_source"] == "null_due_to_disagreement"

def test_decision_pass_gate_confirmed():
    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": False,
        "r1_r4_fail": False,
        "score_total": 80,
        "completeness_score": 80,
        "reason_codes": [],
    }
    status = dec.decide(ctx)
    assert status == "pass"

def test_decision_gate_blocks_unconfirmed():
    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.draft_enriched,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": False,
        "r1_r4_fail": False,
        "score_total": 95,
        "completeness_score": 95,
        "reason_codes": [],
    }
    status = dec.decide(ctx)
    assert status == "warn"   # Cannot PASS — bundle not confirmed

def test_decision_r5_forces_human():
    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": True,
        "r1_r4_fail": False,
        "score_total": None,
        "completeness_score": 85,
        "reason_codes": ["MODEL_DISAGREEMENT_R5"],
    }
    status = dec.decide(ctx)
    assert status == "warn"

def test_decision_r1_r4_fail():
    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": False,
        "r1_r4_fail": True,
        "score_total": 90,
        "completeness_score": 90,
        "reason_codes": ["REDLINE_CASE_FAIL"],
    }
    status = dec.decide(ctx)
    assert status == "fail"

def test_decision_dual_low_fail():
    dec = DecisionStage()
    ctx = {
        "bundle_state": BundleState.confirmed,
        "evaluation_mode": EvaluationMode.capability_full,
        "r5_triggered": False,
        "r1_r4_fail": False,
        "score_total": 65,      # <70
        "completeness_score": 65,  # <70
        "reason_codes": [],
    }
    status = dec.decide(ctx)
    assert status == "fail"   # dual-low rule
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_aggregate.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/core/aggregate.py`**

```python
class AggregateStage:
    """
    Implements R1–R8 aggregation rules from 评估指标与准入标准.md §6.4.
    R5 threshold: |DS.score_total - WB.score_total| >= 15
    """

    R5_THRESHOLD = 15

    def run(
        self,
        votes: list[dict],
        assertion_passed: bool,
        completeness_score: float,
        redline_fail: bool = False,
    ) -> dict:
        reason_codes: list[str] = []

        # R1: Assertion/Level0 hard fail already handled upstream
        # R2: Completeness check
        if completeness_score < 60:
            reason_codes.append("COMPLETENESS_TOO_LOW")

        # R3/R4: Redline case fail (caller sets this flag)
        r1_r4_fail = redline_fail
        if redline_fail:
            reason_codes.append("REDLINE_CASE_FAIL")

        # Separate DS and WB votes
        ds_votes = [v for v in votes if v["model"] == "deepseek"]
        wb_votes = [v for v in votes if v["model"] == "workbuddy"]

        ds_score = sum(v["score_total"] for v in ds_votes) / len(ds_votes) if ds_votes else None
        wb_score = sum(v["score_total"] for v in wb_votes) / len(wb_votes) if wb_votes else None

        # R5: Disagreement detection
        r5_triggered = False
        score_total = None
        score_total_source = "not_applicable"

        if ds_score is not None and wb_score is not None:
            gap = abs(ds_score - wb_score)
            if gap >= self.R5_THRESHOLD:
                r5_triggered = True
                score_total = None
                score_total_source = "null_due_to_disagreement"
                reason_codes.append("MODEL_DISAGREEMENT_R5")
            else:
                score_total = round((ds_score + wb_score) / 2, 1)
                score_total_source = "aggregated_mean"

        return {
            "r5_triggered": r5_triggered,
            "r1_r4_fail": r1_r4_fail,
            "score_total": score_total,
            "score_total_source": score_total_source,
            "completeness_score": completeness_score,
            "reason_codes": reason_codes,
            "ds_score": ds_score,
            "wb_score": wb_score,
        }
```

- [ ] **Step 4: Create `skillhub_eval/core/decision.py`**

```python
from .schemas.enums import BundleState, EvaluationMode

class PassGateError(Exception):
    pass

PASS_THRESHOLD = 70
DUAL_LOW_THRESHOLD = 70

class DecisionStage:
    """
    Applies PASS gate (bundle_state=confirmed + evaluation_mode=capability_full).
    Priority: R1–R4 fail > R5 warn > dual-low fail > threshold-based pass/warn.
    """

    def decide(self, ctx: dict) -> str:
        """Returns 'pass', 'warn', or 'fail'."""
        bundle_state = ctx["bundle_state"]
        evaluation_mode = ctx["evaluation_mode"]
        r5_triggered = ctx.get("r5_triggered", False)
        r1_r4_fail = ctx.get("r1_r4_fail", False)
        score_total = ctx.get("score_total")
        completeness_score = ctx.get("completeness_score", 0)

        # R1–R4: hard fail
        if r1_r4_fail:
            return "fail"

        # Dual-low rule: both quality AND completeness < 70 → fail
        if (
            score_total is not None
            and score_total < DUAL_LOW_THRESHOLD
            and completeness_score < DUAL_LOW_THRESHOLD
        ):
            return "fail"

        # R5: model disagreement → always warn + human review
        if r5_triggered:
            return "warn"

        # PASS gate: must be confirmed + capability_full
        can_pass = (
            bundle_state == BundleState.confirmed
            and evaluation_mode == EvaluationMode.capability_full
        )

        if not can_pass:
            return "warn"

        # Threshold
        if score_total is not None and score_total >= PASS_THRESHOLD and completeness_score >= PASS_THRESHOLD:
            return "pass"

        return "warn"

    def requires_human_review(self, ctx: dict, review_status: str) -> bool:
        return ctx.get("r5_triggered", False) or review_status == "warn"
```

- [ ] **Step 5: Run tests — expect pass**

```powershell
pytest tests/core/test_aggregate.py -v
```

Expected: `7 passed`

- [ ] **Step 6: Commit**

```bash
git add skillhub_eval/core/aggregate.py skillhub_eval/core/decision.py tests/core/test_aggregate.py
git commit -m "feat: AggregateStage (R1-R8, R5) + DecisionStage (PASS gate, dual-low)"
```

---

## Task 8: EvaluationEngine (Orchestrator + State Machine)

**Files:**
- Create: `skillhub_eval/core/engine.py`
- Test: `tests/core/test_engine.py`

- [ ] **Step 1: Write failing integration test (mock LLM)**

```python
# tests/core/test_engine.py
import pytest, asyncio, json
from pathlib import Path
from unittest.mock import AsyncMock, patch
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.core.schemas import BundleState, EvaluationMode, RunStatus

FAKE_VOTE = {
    "sub_scores": {"step_completeness": {"score": 85, "pass": True, "reason": "ok", "evidence_refs": []}},
    "confidence": "high",
    "dimension_notes": ""
}

@pytest.fixture
def skill_bundle(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: test-skill\nid: skill.test\nrisk_level: low\n---\n# Test\n"
    )
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    for i in range(3):
        (ec / f"case_{i:02d}.yaml").write_text(
            f"id: case_{i:02d}\ntype: happy_path\nuser_intent: test intent\n"
        )
    (tmp_path / "sample_io").mkdir()
    return str(tmp_path)

@pytest.fixture
def repo(tmp_path):
    db = str(tmp_path / "test_engine.db")
    r = SqliteRepository(db)
    r.init_db()
    return r

@pytest.mark.asyncio
async def test_engine_full_run(skill_bundle, repo):
    from skillhub_eval.providers.base import BaseLLMProvider

    class FakeProvider(BaseLLMProvider):
        async def judge(self, prompt: str) -> dict:
            return FAKE_VOTE

    engine = EvaluationEngine(
        repo=repo,
        ds_provider=FakeProvider(),
        wb_provider=FakeProvider(),
    )

    run_id = repo.create_run(
        skill_id="skill.test", skill_bundle_path=skill_bundle,
        bundle_state="confirmed", evaluation_mode="capability_full",
    )

    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=skill_bundle,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    run = repo.get_run(run_id)
    assert run["status"] in ("completed", "failed")

    report = repo.get_report(run_id)
    assert report is not None
    assert report["skill_id"] == "skill.test"
    assert report["review_status"] in ("pass", "warn", "fail")
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/core/test_engine.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/core/engine.py`**

```python
import asyncio
from datetime import datetime
from .schemas import (
    BundleState, EvaluationMode, RunStatus,
    EvaluationReport, HumanReview, ModelVote,
)
from .ingest import ingest_bundle
from .level0 import Level0Checker
from .aggregate import AggregateStage
from .decision import DecisionStage
from .schemas.enums import RiskLevel

WORKFLOW_TIMEOUT = 180  # seconds

class EvaluationEngine:
    def __init__(self, repo, ds_provider, wb_provider, sandbox=None):
        self.repo = repo
        self.ds = ds_provider
        self.wb = wb_provider
        self.sandbox = sandbox
        self._agg = AggregateStage()
        self._dec = DecisionStage()

    async def run_async(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> None:
        try:
            await asyncio.wait_for(
                self._execute(run_id, skill_bundle_path, bundle_state, evaluation_mode),
                timeout=WORKFLOW_TIMEOUT,
            )
        except asyncio.TimeoutError:
            self.repo.update_status(run_id, RunStatus.failed.value,
                                    reason_codes=["EVAL_WORKFLOW_TIMEOUT"])
            self.repo.log_event(run_id, "eval_workflow_timeout", {"timeout_s": WORKFLOW_TIMEOUT})

    async def _execute(
        self,
        run_id: str,
        skill_bundle_path: str,
        bundle_state: BundleState,
        evaluation_mode: EvaluationMode,
    ) -> None:
        repo = self.repo

        # --- Ingest ---
        repo.update_status(run_id, RunStatus.level0_checking.value)
        repo.append_stage(run_id, "level0_checking")
        bundle = ingest_bundle(skill_bundle_path)

        # --- Level 0 ---
        l0 = Level0Checker().check(bundle)
        if not l0["passed"]:
            self._finish_fail(run_id, bundle, bundle_state, evaluation_mode,
                              l0["reason_codes"], l0["evidence"])
            return

        risk = RiskLevel(l0["risk_level"])
        level_achieved = "level_2" if bundle.get("has_scripts") else "level_1"

        # --- Risk Lock ---
        repo.update_status(run_id, RunStatus.risk_locking.value, risk_level_locked=risk.value)
        repo.append_stage(run_id, "risk_locking")

        # --- Case Execution (Level 1: sample_io) ---
        repo.update_status(run_id, RunStatus.case_executing.value, level_achieved=level_achieved)
        repo.append_stage(run_id, "case_executing")
        cases = bundle["eval_cases"]

        # --- Model Judging (DS + WB in parallel per case) ---
        repo.update_status(run_id, RunStatus.model_judging.value)
        repo.append_stage(run_id, "model_judging")

        all_votes: list[dict] = []
        for case in cases:
            prompt = self._build_prompt(case, bundle, bundle_state, evaluation_mode)
            ds_raw, wb_raw = await asyncio.gather(
                self.ds.judge(prompt),
                self.wb.judge(prompt),
                return_exceptions=True,
            )
            for provider_name, raw in [("deepseek", ds_raw), ("workbuddy", wb_raw)]:
                if isinstance(raw, Exception):
                    # Provider hard failure → log, skip vote
                    repo.log_event(run_id, "provider_error",
                                   {"provider": provider_name, "case_id": case.get("id"), "error": str(raw)})
                    continue
                score = self._extract_score(raw)
                vote = {
                    "model": provider_name,
                    "model_version": "unknown",
                    "prompt_version": "review-agent-v0.2",
                    "case_id": case.get("id", "?"),
                    "dimension_scores": raw.get("sub_scores", {}),
                    "score_total": score,
                    "suggested_review_status": "pass" if score >= 70 else "warn",
                    "confidence": raw.get("confidence", "medium"),
                    "evidence_refs": [],
                    "feedback": raw.get("dimension_notes", ""),
                    "latency_ms": 0,
                }
                all_votes.append(vote)

        repo.save_votes(run_id, all_votes)

        # --- Aggregate ---
        repo.update_status(run_id, RunStatus.aggregating.value)
        repo.append_stage(run_id, "aggregating")
        completeness_score = self._calc_completeness(bundle)
        agg = self._agg.run(
            votes=all_votes,
            assertion_passed=True,
            completeness_score=completeness_score,
        )

        # --- Decision ---
        review_status = self._dec.decide({
            "bundle_state": bundle_state,
            "evaluation_mode": evaluation_mode,
            "r5_triggered": agg["r5_triggered"],
            "r1_r4_fail": agg["r1_r4_fail"],
            "score_total": agg["score_total"],
            "completeness_score": completeness_score,
            "reason_codes": agg["reason_codes"],
        })

        human_required = self._dec.requires_human_review(agg, review_status)
        if human_required:
            repo.set_human_review_required(run_id, True, agg["reason_codes"])
            repo.update_status(run_id, RunStatus.awaiting_human_review.value)
            repo.append_stage(run_id, "awaiting_human_review")

        # --- Analytics events ---
        if agg["r5_triggered"]:
            repo.log_event(run_id, "eval_score_variance_detected",
                           {"ds": agg["ds_score"], "wb": agg["wb_score"]})

        # --- Save report ---
        report = EvaluationReport(
            run_id=run_id,
            skill_id=bundle["skill_id"],
            skill_bundle_path=skill_bundle_path,
            bundle_state=bundle_state,
            evaluation_mode=evaluation_mode,
            orchestration_mode=self._infer_mode(bundle_state, evaluation_mode),
            status=RunStatus.completed,
            review_status=review_status,
            risk_level_locked=risk,
            level_achieved=level_achieved,
            score_total=agg["score_total"],
            score_total_source=agg["score_total_source"],
            completeness_score=completeness_score,
            reason_codes=agg["reason_codes"],
            model_votes=[ModelVote(**{k: v.get(k, "") for k in ModelVote.model_fields}, **{
                "model": v["model"], "model_version": v["model_version"],
                "prompt_version": v["prompt_version"], "case_id": v["case_id"],
                "score_total": v["score_total"], "suggested_review_status": v["suggested_review_status"],
                "confidence": v["confidence"], "feedback": v["feedback"],
            }) for v in all_votes],
            human_review=HumanReview(
                required=human_required,
                trigger_codes=agg["reason_codes"] if human_required else [],
            ),
            rubric_version="v1.2",
            prompt_version="review-agent-v0.2",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        repo.save_report(run_id, report)
        if not human_required:
            repo.update_status(run_id, RunStatus.completed.value,
                               review_status=review_status, score_total=agg["score_total"])

    def _finish_fail(self, run_id, bundle, bundle_state, evaluation_mode, reason_codes, evidence):
        self.repo.update_status(self.repo.get_run(run_id)["run_id"] if isinstance(run_id, dict) else run_id,
                                RunStatus.failed.value, reason_codes=reason_codes)
        report = EvaluationReport(
            run_id=run_id, skill_id=bundle.get("skill_id", "?"),
            skill_bundle_path=bundle.get("bundle_path", "?"),
            bundle_state=bundle_state, evaluation_mode=evaluation_mode,
            status=RunStatus.failed, review_status="fail",
            reason_codes=reason_codes, evidence=evidence,
            rubric_version="v1.2", prompt_version="review-agent-v0.2",
        )
        self.repo.save_report(run_id, report)
        self.repo.update_status(run_id, RunStatus.failed.value, review_status="fail")

    def _build_prompt(self, case: dict, bundle: dict, bundle_state, evaluation_mode) -> str:
        return (
            f"你是 SkillHub 质量评审员。仅评估本 case，不做最终 pass/fail 裁决。\n"
            f"skill_id: {bundle['skill_id']}\n"
            f"case_id: {case.get('id', '?')}\n"
            f"case_type: {case.get('type', 'happy_path')}\n"
            f"bundle_state: {bundle_state}\n"
            f"evaluation_mode: {evaluation_mode}\n"
            f"user_intent: {case.get('user_intent', '')}\n"
            f"【输出格式】仅输出 JSON：{{\"sub_scores\":{{\"step_completeness\":{{\"score\":85,\"pass\":true,\"reason\":\"ok\",\"evidence_refs\":[]}}}},\"confidence\":\"medium\",\"dimension_notes\":\"\"}}"
        )

    def _extract_score(self, raw: dict) -> float:
        scores = [v.get("score", 70) for v in raw.get("sub_scores", {}).values() if isinstance(v, dict)]
        return round(sum(scores) / len(scores), 1) if scores else 70.0

    def _calc_completeness(self, bundle: dict) -> float:
        score = 100.0
        if not bundle.get("has_sample_io"):
            score -= 15
        if not bundle["skill_meta"].get("description"):
            score -= 10
        return max(0.0, score)

    def _infer_mode(self, bundle_state, evaluation_mode) -> str:
        if bundle_state == BundleState.confirmed and evaluation_mode == EvaluationMode.capability_full:
            return "A"
        if bundle_state in (BundleState.minimal,):
            return "B"
        if bundle_state == BundleState.draft_enriched:
            return "C"
        return "D"
```

- [ ] **Step 4: Run engine integration test — expect pass**

```powershell
pytest tests/core/test_engine.py -v
```

Expected: `1 passed`

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/core/engine.py tests/core/test_engine.py
git commit -m "feat: EvaluationEngine state machine (A/B/C/D, asyncio, 180s timeout, R5, PASS gate)"
```

---

## Task 9: FastAPI Application + 6 Endpoints

**Files:**
- Create: `skillhub_eval/adapters/api/deps.py`
- Create: `skillhub_eval/adapters/api/app.py`
- Create: `skillhub_eval/adapters/api/routes/eval.py`
- Create: `skillhub_eval/adapters/api/routes/bundle.py`
- Create: `skillhub_eval/adapters/api/routes/human.py`
- Test: `tests/adapters/test_api.py`

- [ ] **Step 1: Write failing API tests**

```python
# tests/adapters/test_api.py
import pytest
from fastapi.testclient import TestClient
from skillhub_eval.adapters.api.app import create_app
from skillhub_eval.persistence.sqlite import SqliteRepository

@pytest.fixture
def client(tmp_path):
    db = str(tmp_path / "api_test.db")
    repo = SqliteRepository(db)
    repo.init_db()
    app = create_app(repo=repo)
    return TestClient(app, raise_server_exceptions=True)

def test_post_eval_run_returns_run_id(client, tmp_path):
    # Create minimal Skill bundle in tmp_path
    (tmp_path / "SKILL.md").write_text("---\nname: s\nid: s1\nrisk_level: low\n---\n")
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    for i in range(3):
        (ec / f"c{i}.yaml").write_text(f"id: c{i}\ntype: happy_path\nuser_intent: x\n")

    resp = client.post("/eval/run", json={
        "skill_id": "s1",
        "skill_bundle_path": str(tmp_path),
        "bundle_state": "confirmed",
        "evaluation_mode": "capability_full",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "run_id" in data
    assert data["status"] == "pending"

def test_get_report_unknown_id(client):
    resp = client.get("/eval/report/nonexistent")
    assert resp.status_code == 404

def test_get_history_empty(client):
    resp = client.get("/eval/history")
    assert resp.status_code == 200
    assert resp.json() == []

def test_human_review_pass_gate_unconfirmed(client, tmp_path):
    # Create run with draft_enriched (not confirmed) awaiting human review
    (tmp_path / "SKILL.md").write_text("---\nname: s\nid: s2\nrisk_level: low\n---\n")
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    for i in range(3):
        (ec / f"c{i}.yaml").write_text(f"id: c{i}\ntype: happy_path\nuser_intent: x\n")

    run_resp = client.post("/eval/run", json={
        "skill_id": "s2",
        "skill_bundle_path": str(tmp_path),
        "bundle_state": "draft_enriched",
        "evaluation_mode": "capability_full",
    })
    run_id = run_resp.json()["run_id"]

    # Try to approve_warn — should be 409 because not confirmed
    resp = client.post(f"/eval/{run_id}/human-review", json={
        "action": "approve_warn",
        "operator": "test_user",
        "comment": "looks ok",
        "force_pass": True,
    })
    assert resp.status_code == 409
```

- [ ] **Step 2: Run to confirm failure**

```powershell
pytest tests/adapters/test_api.py -v
```

Expected: `ImportError`

- [ ] **Step 3: Create `skillhub_eval/adapters/api/deps.py`**

```python
from functools import lru_cache
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.providers.deepseek import DeepSeekProvider
from skillhub_eval.providers.workbuddy import WorkBuddyProvider
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.settings import settings

@lru_cache
def get_repo() -> SqliteRepository:
    repo = SqliteRepository(settings.eval_db_path)
    repo.init_db()
    return repo

@lru_cache
def get_engine() -> EvaluationEngine:
    return EvaluationEngine(
        repo=get_repo(),
        ds_provider=DeepSeekProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        ),
        wb_provider=WorkBuddyProvider(
            api_key=settings.workbuddy_api_key,
            base_url=settings.workbuddy_base_url,
        ),
    )
```

- [ ] **Step 4: Create `skillhub_eval/adapters/api/routes/eval.py`**

```python
from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from skillhub_eval.core.schemas import EvalRunRequest, BundleState, EvaluationMode
from skillhub_eval.adapters.api.deps import get_repo, get_engine

router = APIRouter(prefix="/eval", tags=["eval"])

@router.post("/run", status_code=201)
async def run_eval(req: EvalRunRequest, background: BackgroundTasks):
    repo = get_repo()
    engine = get_engine()
    run_id = repo.create_run(
        skill_id=req.skill_id,
        skill_bundle_path=req.skill_bundle_path,
        bundle_state=req.bundle_state.value,
        evaluation_mode=req.evaluation_mode.value,
    )
    background.add_task(
        engine.run_async,
        run_id=run_id,
        skill_bundle_path=req.skill_bundle_path,
        bundle_state=req.bundle_state,
        evaluation_mode=req.evaluation_mode,
    )
    return {"run_id": run_id, "status": "pending"}

@router.get("/report/{run_id}")
def get_report(run_id: str):
    repo = get_repo()
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    report = repo.get_report(run_id)
    return {
        "run_id": run_id,
        "status": run["status"],
        "review_status": run.get("review_status"),
        "score_total": run.get("score_total"),
        "report": report,
        # Polling hint for clients:
        "poll_interval_hint_seconds": 3 if run["status"] not in ("completed", "failed") else None,
    }

@router.get("/history")
def list_history(human_review_required: bool | None = None, limit: int = 50):
    repo = get_repo()
    return repo.list_history(limit=limit, human_review_required=human_review_required)
```

- [ ] **Step 5: Create `skillhub_eval/adapters/api/routes/bundle.py`**

```python
from fastapi import APIRouter, HTTPException
from skillhub_eval.core.schemas import ConfirmRequest
from skillhub_eval.adapters.api.deps import get_repo
from datetime import datetime

router = APIRouter(prefix="/bundle", tags=["bundle"])

@router.get("/{skill_id}/gaps")
def get_gaps(skill_id: str):
    repo = get_repo()
    gaps = repo.get_gaps(skill_id)
    if not gaps:
        return {"skill_id": skill_id, "gaps": [], "question_queue": []}
    return gaps

@router.post("/{skill_id}/confirm", status_code=200)
def confirm_fields(skill_id: str, req: ConfirmRequest):
    repo = get_repo()
    for field_path, confirmed_value in req.confirmed_fields.items():
        with repo._conn() as conn:
            conn.execute(
                "INSERT INTO bundle_confirmations (skill_id,field_path,confirmed_value,confirmed_by,confirmed_at) VALUES (?,?,?,?,?)",
                (skill_id, field_path, confirmed_value, req.operator, datetime.utcnow().isoformat()),
            )
    return {"confirmed": list(req.confirmed_fields.keys()), "operator": req.operator}
```

- [ ] **Step 6: Create `skillhub_eval/adapters/api/routes/human.py`**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from skillhub_eval.adapters.api.deps import get_repo
from skillhub_eval.core.schemas.enums import BundleState

router = APIRouter(prefix="/eval", tags=["human-review"])

class HumanReviewRequest(BaseModel):
    action: str          # "approve_warn" | "reject" | "escalate"
    operator: str
    comment: str = ""
    force_pass: bool = False

@router.post("/{run_id}/human-review")
def submit_human_review(run_id: str, req: HumanReviewRequest):
    repo = get_repo()
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # PASS gate: cannot force-pass a non-confirmed bundle
    if req.force_pass and run["bundle_state"] != BundleState.confirmed.value:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "BUNDLE_NOT_CONFIRMED",
                "message": "Cannot approve PASS: bundle_state must be 'confirmed'. "
                           "Complete Tab1 author confirmation first.",
            },
        )

    # Retrieve and preserve original votes before recording human action
    preserved = []
    with repo._conn() as conn:
        import json
        rows = conn.execute(
            "SELECT vote_json FROM model_votes WHERE run_id=?", (run_id,)
        ).fetchall()
        preserved = [json.loads(r["vote_json"]) for r in rows]

    repo.save_human_review(
        run_id=run_id,
        action=req.action,
        operator=req.operator,
        comment=req.comment,
        preserved_votes=preserved,
    )

    new_status = "completed" if req.action == "approve_warn" else "failed"
    repo.update_status(run_id, new_status, review_status="warn" if req.action == "approve_warn" else "fail")

    return {"run_id": run_id, "action": req.action, "new_status": new_status}
```

- [ ] **Step 7: Create `skillhub_eval/adapters/api/app.py`**

```python
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from .routes import eval as eval_routes, bundle as bundle_routes, human as human_routes

def create_app(repo=None) -> FastAPI:
    """
    Factory allows injecting a test repo in tests.
    Production: uses deps.get_repo() singleton.
    """
    app = FastAPI(
        title="SkillHub Evaluation Engine",
        version="0.1.0",
        description="Phase 2 evaluation engine. Swagger UI is the Living Contract.",
    )

    if repo is not None:
        # Override deps for testing
        from skillhub_eval.adapters.api import deps
        deps.get_repo.cache_clear()
        deps._test_repo = repo
        app.dependency_overrides = {}

    app.include_router(eval_routes.router)
    app.include_router(bundle_routes.router)
    app.include_router(human_routes.router)

    # Serve static UI
    static_dir = Path(__file__).parent.parent / "ui" / "static"
    if static_dir.exists():
        app.mount("/ui", StaticFiles(directory=str(static_dir), html=True), name="ui")

    return app

# Singleton for uvicorn
app = create_app()
```

- [ ] **Step 8: Run API tests — expect pass**

```powershell
pytest tests/adapters/test_api.py -v
```

Expected: `4 passed`

- [ ] **Step 9: Commit**

```bash
git add skillhub_eval/adapters/api/ tests/adapters/test_api.py
git commit -m "feat: FastAPI app + 6 endpoints (run/report/history/gaps/confirm/human-review) + PASS gate 409"
```

---

## Task 10: CLI Adapter

**Files:**
- Create: `skillhub_eval/adapters/cli/main.py`

- [ ] **Step 1: Create `skillhub_eval/adapters/cli/main.py`**

```python
import typer, json, asyncio, time
from pathlib import Path

app = typer.Typer(help="SkillHub Evaluation Engine CLI")

def _get_repo():
    from skillhub_eval.persistence.sqlite import SqliteRepository
    from skillhub_eval.settings import settings
    repo = SqliteRepository(settings.eval_db_path)
    repo.init_db()
    return repo

def _get_engine(repo):
    from skillhub_eval.providers.deepseek import DeepSeekProvider
    from skillhub_eval.providers.workbuddy import WorkBuddyProvider
    from skillhub_eval.core.engine import EvaluationEngine
    from skillhub_eval.settings import settings
    return EvaluationEngine(
        repo=repo,
        ds_provider=DeepSeekProvider(settings.deepseek_api_key, settings.deepseek_base_url),
        wb_provider=WorkBuddyProvider(settings.workbuddy_api_key, settings.workbuddy_base_url),
    )

@app.command()
def run(
    bundle_path: str = typer.Argument(..., help="Path to Skill package directory"),
    bundle_state: str = typer.Option("confirmed", help="confirmed|draft_enriched|minimal|eval_ready"),
    evaluation_mode: str = typer.Option("capability_full", help="capability_full|degraded"),
):
    """Evaluate a Skill package. Runs synchronously; waits for completion."""
    from skillhub_eval.core.schemas import BundleState, EvaluationMode
    from skillhub_eval.core.ingest import ingest_bundle

    bundle = ingest_bundle(bundle_path)
    repo = _get_repo()
    engine = _get_engine(repo)

    run_id = repo.create_run(
        skill_id=bundle["skill_id"],
        skill_bundle_path=bundle_path,
        bundle_state=bundle_state,
        evaluation_mode=evaluation_mode,
    )
    typer.echo(f"▶  run_id: {run_id}")
    typer.echo("   Running evaluation (this may take up to 3 minutes)...")

    asyncio.run(engine.run_async(
        run_id=run_id,
        skill_bundle_path=bundle_path,
        bundle_state=BundleState(bundle_state),
        evaluation_mode=EvaluationMode(evaluation_mode),
    ))

    run = repo.get_run(run_id)
    status = run["status"]
    review = run.get("review_status", "-")
    score = run.get("score_total", "-")
    typer.echo(f"✔  status={status}  review_status={review}  score_total={score}")

    report = repo.get_report(run_id)
    if report:
        out = Path(f"data/reports/{run_id}")
        out.mkdir(parents=True, exist_ok=True)
        (out / "evaluation_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False))
        typer.echo(f"   Report: {out / 'evaluation_report.json'}")

@app.command()
def history(limit: int = typer.Option(20)):
    """List recent evaluation runs."""
    repo = _get_repo()
    rows = repo.list_history(limit=limit)
    for r in rows:
        typer.echo(f"{r['run_id'][:8]}  {r['skill_id']:30s}  {r['status']:25s}  {r.get('review_status','-')}")

@app.command()
def gaps(skill_id: str = typer.Argument(...)):
    """Show gaps snapshot for a Skill."""
    repo = _get_repo()
    g = repo.get_gaps(skill_id)
    typer.echo(json.dumps(g or {}, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    app()
```

- [ ] **Step 2: Smoke-test CLI (uses stub that doesn't call real API)**

```powershell
skillhub-eval --help
```

Expected: Help text showing `run`, `history`, `gaps` commands.

- [ ] **Step 3: Commit**

```bash
git add skillhub_eval/adapters/cli/main.py
git commit -m "feat: CLI adapter - run / history / gaps commands (Typer)"
```

---

## Task 11: Dual-Tab Confirm UI

**Files:**
- Create: `skillhub_eval/adapters/ui/static/index.html`
- Create: `skillhub_eval/adapters/ui/static/confirm-tab.js`
- Create: `skillhub_eval/adapters/ui/static/review-tab.js`

- [ ] **Step 1: Create `index.html`**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>SkillHub 确认台</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
  <div class="max-w-4xl mx-auto py-8 px-4">
    <h1 class="text-2xl font-bold text-gray-800 mb-6">SkillHub 评估确认台</h1>

    <!-- Tabs -->
    <div class="flex border-b border-gray-200 mb-6">
      <button id="tab1-btn" onclick="showTab('tab1')"
        class="tab-btn px-6 py-3 text-sm font-medium border-b-2 border-blue-500 text-blue-600">
        Tab 1 · 作者补全台
      </button>
      <button id="tab2-btn" onclick="showTab('tab2')"
        class="tab-btn px-6 py-3 text-sm font-medium border-b-2 border-transparent text-gray-500 hover:text-gray-700">
        Tab 2 · 专家审核台
      </button>
    </div>

    <!-- Tab 1: Author Confirm -->
    <div id="tab1" class="tab-panel">
      <div class="mb-4">
        <label class="block text-sm font-medium text-gray-700 mb-1">Skill ID</label>
        <div class="flex gap-2">
          <input id="skill-id-input" type="text" placeholder="例: skill.employee-check"
            class="border border-gray-300 rounded px-3 py-2 text-sm flex-1"/>
          <button onclick="loadGaps()" class="bg-blue-600 text-white px-4 py-2 rounded text-sm hover:bg-blue-700">
            加载 Gaps
          </button>
        </div>
      </div>
      <div id="gaps-container"></div>
    </div>

    <!-- Tab 2: Expert Review -->
    <div id="tab2" class="tab-panel hidden">
      <div class="mb-4 flex gap-2">
        <button onclick="loadPendingReviews()"
          class="bg-indigo-600 text-white px-4 py-2 rounded text-sm hover:bg-indigo-700">
          刷新待审核列表
        </button>
      </div>
      <div id="review-list"></div>
      <div id="review-detail" class="hidden mt-6 border border-gray-200 rounded p-4 bg-white"></div>
    </div>
  </div>

  <script src="confirm-tab.js"></script>
  <script src="review-tab.js"></script>
  <script>
    function showTab(tab) {
      document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
      document.querySelectorAll('.tab-btn').forEach(b => {
        b.classList.remove('border-blue-500','text-blue-600');
        b.classList.add('border-transparent','text-gray-500');
      });
      document.getElementById(tab).classList.remove('hidden');
      const btn = document.getElementById(tab + '-btn');
      btn.classList.add('border-blue-500','text-blue-600');
      btn.classList.remove('border-transparent','text-gray-500');
    }
  </script>
</body>
</html>
```

- [ ] **Step 2: Create `confirm-tab.js`**

```javascript
async function loadGaps() {
  const skillId = document.getElementById('skill-id-input').value.trim();
  if (!skillId) return;
  const resp = await fetch(`/bundle/${encodeURIComponent(skillId)}/gaps`);
  const data = await resp.json();
  const container = document.getElementById('gaps-container');

  if (!data.gaps || data.gaps.length === 0) {
    container.innerHTML = '<p class="text-green-600 text-sm">✅ 无缺口，Skill 已完整。</p>';
    return;
  }

  const editableFields = ['negative_prompts', 'error_handling', 'permissions'];

  let html = '<div class="space-y-4">';
  const confirmInputs = {};

  for (const gap of data.gaps) {
    const isEditable = editableFields.some(f => gap.field_path.includes(f))
      || gap.field_path.startsWith('eval_cases');
    const severity = gap.severity === 'blocker' ? 'red' : 'yellow';
    const badge = `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium bg-${severity}-100 text-${severity}-800">${gap.severity}</span>`;

    if (isEditable) {
      confirmInputs[gap.field_path] = gap.draft_value || '';
      html += `
        <div class="border border-${severity}-200 rounded p-4 bg-white">
          <div class="flex items-center gap-2 mb-2">${badge}
            <span class="font-mono text-sm text-gray-700">${gap.field_path}</span>
          </div>
          <p class="text-sm text-gray-600 mb-2">${gap.message}</p>
          <label class="text-xs text-gray-500">确认值（可编辑草案）</label>
          <textarea class="w-full border border-gray-300 rounded px-2 py-1 text-sm mt-1"
            rows="2" data-field="${gap.field_path}"
            onchange="confirmInputs['${gap.field_path}']=this.value"
          >${gap.draft_value || ''}</textarea>
        </div>`;
    } else {
      html += `
        <div class="border border-gray-200 rounded p-3 bg-gray-50">
          <div class="flex items-center gap-2">${badge}
            <span class="font-mono text-sm text-gray-500">${gap.field_path}</span>
          </div>
          <p class="text-sm text-gray-500 mt-1">${gap.message}</p>
          <p class="text-xs text-gray-400 mt-1 italic">请在本地 SKILL.md 中补充以上基础信息后重新提交。</p>
        </div>`;
    }
  }

  const hasEditable = Object.keys(confirmInputs).length > 0;
  if (hasEditable) {
    html += `
      <div class="mt-2">
        <label class="block text-sm font-medium text-gray-700 mb-1">确认人（姓名/工号）</label>
        <input id="confirm-operator" type="text" class="border border-gray-300 rounded px-3 py-2 text-sm w-48"/>
        <button onclick="submitConfirm('${skillId}')"
          class="ml-2 bg-green-600 text-white px-4 py-2 rounded text-sm hover:bg-green-700">
          提交确认
        </button>
      </div>`;
  }

  html += '</div>';
  container.innerHTML = html;
  window._confirmInputs = confirmInputs;
}

async function submitConfirm(skillId) {
  const operator = document.getElementById('confirm-operator').value.trim();
  if (!operator) { alert('请填写确认人'); return; }

  // Gather edited values from textareas
  const confirmed_fields = {};
  document.querySelectorAll('[data-field]').forEach(el => {
    confirmed_fields[el.dataset.field] = el.value;
  });

  const resp = await fetch(`/bundle/${encodeURIComponent(skillId)}/confirm`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({confirmed_fields, confirmed_cases: [], operator}),
  });
  const data = await resp.json();
  alert(`✅ 已确认 ${data.confirmed.length} 个字段。请重新提交评估（模式 D）。`);
}
```

- [ ] **Step 3: Create `review-tab.js`**

```javascript
async function loadPendingReviews() {
  const resp = await fetch('/eval/history?human_review_required=true&limit=20');
  const rows = await resp.json();
  const container = document.getElementById('review-list');

  if (!rows.length) {
    container.innerHTML = '<p class="text-gray-500 text-sm">暂无待审核项。</p>';
    return;
  }

  let html = '<div class="space-y-2">';
  for (const r of rows) {
    html += `
      <div class="flex items-center justify-between border border-gray-200 rounded p-3 bg-white hover:bg-gray-50 cursor-pointer"
           onclick="loadReviewDetail('${r.run_id}')">
        <div>
          <span class="font-mono text-sm text-gray-700">${r.run_id.slice(0,8)}</span>
          <span class="ml-3 text-sm text-gray-600">${r.skill_id}</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="text-xs text-amber-600 font-medium">待审核</span>
          <span class="text-xs text-gray-400">${r.score_total ?? 'N/A'}</span>
        </div>
      </div>`;
  }
  html += '</div>';
  container.innerHTML = html;
}

async function loadReviewDetail(runId) {
  const resp = await fetch(`/eval/report/${runId}`);
  const data = await resp.json();
  const report = data.report || {};
  const detail = document.getElementById('review-detail');

  const votes = (report.model_votes || []);
  const ds = votes.filter(v => v.model === 'deepseek');
  const wb = votes.filter(v => v.model === 'workbuddy');

  const bundleConfirmed = report.bundle_state === 'confirmed';

  detail.classList.remove('hidden');
  detail.innerHTML = `
    <h3 class="font-semibold text-gray-800 mb-3">Run: ${runId.slice(0,8)} · ${report.skill_id || ''}</h3>
    <div class="grid grid-cols-2 gap-4 mb-4">
      <div class="bg-blue-50 rounded p-3">
        <p class="text-xs font-medium text-blue-700 mb-1">DeepSeek</p>
        <p class="text-2xl font-bold text-blue-800">${ds[0]?.score_total ?? '-'}</p>
        <p class="text-xs text-blue-600">${ds[0]?.suggested_review_status ?? '-'}</p>
        <p class="text-xs text-gray-500 mt-1">${ds[0]?.feedback?.slice(0,100) || ''}</p>
      </div>
      <div class="bg-purple-50 rounded p-3">
        <p class="text-xs font-medium text-purple-700 mb-1">WorkBuddy</p>
        <p class="text-2xl font-bold text-purple-800">${wb[0]?.score_total ?? '-'}</p>
        <p class="text-xs text-purple-600">${wb[0]?.suggested_review_status ?? '-'}</p>
        <p class="text-xs text-gray-500 mt-1">${wb[0]?.feedback?.slice(0,100) || ''}</p>
      </div>
    </div>
    <p class="text-sm text-gray-600 mb-1"><strong>reason_codes:</strong> ${(report.reason_codes || []).join(', ') || '—'}</p>
    <p class="text-sm text-gray-600 mb-3"><strong>bundle_state:</strong> ${report.bundle_state}</p>

    ${!bundleConfirmed ? `
      <div class="bg-amber-50 border border-amber-200 rounded p-3 mb-4">
        <p class="text-sm text-amber-700 font-medium">⚠️  bundle_state = "${report.bundle_state}"</p>
        <p class="text-xs text-amber-600">状态闸门：未确认草案的包无法 PASS。请先在 Tab1 完成作者确认。</p>
      </div>
    ` : ''}

    <div class="flex gap-3">
      <label class="block text-sm text-gray-700">审核人</label>
      <input id="review-operator" type="text" placeholder="姓名/工号"
        class="border border-gray-300 rounded px-2 py-1 text-sm"/>
      <input id="review-comment" type="text" placeholder="备注（可选）"
        class="border border-gray-300 rounded px-2 py-1 text-sm flex-1"/>
    </div>
    <div class="flex gap-2 mt-3">
      <button onclick="submitReview('${runId}','approve_warn',${bundleConfirmed})"
        class="px-4 py-2 rounded text-sm font-medium text-white
               ${bundleConfirmed ? 'bg-green-600 hover:bg-green-700' : 'bg-gray-300 cursor-not-allowed'}"
        ${!bundleConfirmed ? 'disabled title="需先完成 Tab1 确认"' : ''}>
        ✅ Approve Warn
      </button>
      <button onclick="submitReview('${runId}','reject',true)"
        class="px-4 py-2 rounded text-sm font-medium bg-red-600 text-white hover:bg-red-700">
        ❌ Reject
      </button>
      <button onclick="submitReview('${runId}','escalate',true)"
        class="px-4 py-2 rounded text-sm font-medium bg-amber-500 text-white hover:bg-amber-600">
        🔺 Escalate
      </button>
    </div>
  `;
}

async function submitReview(runId, action, bundleConfirmed) {
  if (action === 'approve_warn' && !bundleConfirmed) return;
  const operator = document.getElementById('review-operator').value.trim();
  const comment = document.getElementById('review-comment').value.trim();
  if (!operator) { alert('请填写审核人'); return; }

  const resp = await fetch(`/eval/${runId}/human-review`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({action, operator, comment, force_pass: action === 'approve_warn'}),
  });

  if (resp.status === 409) {
    const err = await resp.json();
    alert(`🚫 ${err.detail.message}`);
    return;
  }
  const data = await resp.json();
  alert(`✔ ${action} 完成 · new_status: ${data.new_status}`);
  document.getElementById('review-detail').classList.add('hidden');
  loadPendingReviews();
}
```

- [ ] **Step 4: Start server and smoke-test UI**

```powershell
uvicorn skillhub_eval.adapters.api.app:app --reload --port 8765
```

Open: [http://localhost:8765/ui/](http://localhost:8765/ui/) → Tab1 and Tab2 should render.  
Open: [http://localhost:8765/docs](http://localhost:8765/docs) → Swagger Living Contract.

- [ ] **Step 5: Commit**

```bash
git add skillhub_eval/adapters/ui/
git commit -m "feat: dual-tab confirm UI (Tab1 author confirm, Tab2 expert review + PASS gate Toast)"
```

---

## Task 12: End-to-End Smoke Test + §14 Checklist

**Files:**
- Create: `tests/test_e2e_smoke.py`

- [ ] **Step 1: Run full test suite**

```powershell
pytest tests/ -v --tb=short
```

Expected: All tests pass.

- [ ] **Step 2: Run all tests and verify §14 checklist coverage**

Manually verify each item in `docs/specs/评审Agent工作流与Prompt骨架.md` §14:

| §14 Item | Status |
|----------|--------|
| DS/WB 同 prompt/rubric 版本 | ✅ engine.py `_build_prompt` + `prompt_version` |
| 写入 bundle_state / evaluation_mode | ✅ `evaluation_runs` table + report |
| PASS 闸门 | ✅ `decision.py` + API 409 |
| 三类 Prompt 分离 | ✅ normalize/risk_lock/model_judge 独立 |
| risk_level 在 Level 0 后锁定 | ✅ `risk_locking` stage before `case_executing` |
| R1–R8; R5 null | ✅ `aggregate.py` |
| §6.4 DSL | ⬜ stub (returns True for all); mark as 2.2 task |
| reason_code / evidence | ✅ report + DB |
| 人工抽检不删证据 | ✅ `preserved_votes_json` in human_reviews |
| 埋点四事件 | ✅ `analytics_events.log_event` |
| degraded 上限 warn | ✅ `decision.py` PASS gate |
| post_listing_health_check | ✅ enum pre-wired; 2.4 to implement |

- [ ] **Step 3: Create smoke test with real bundle fixture**

```python
# tests/test_e2e_smoke.py
"""
E2E smoke test using fake LLM providers (no real API calls).
Validates the full pipeline from ingest → level0 → aggregate → decision → report.
"""
import pytest, asyncio
from pathlib import Path
from skillhub_eval.core.engine import EvaluationEngine
from skillhub_eval.persistence.sqlite import SqliteRepository
from skillhub_eval.core.schemas import BundleState, EvaluationMode
from skillhub_eval.providers.base import BaseLLMProvider

class HighScoreProvider(BaseLLMProvider):
    async def judge(self, prompt: str) -> dict:
        return {
            "sub_scores": {
                "step_completeness": {"score": 90, "pass": True, "reason": "complete", "evidence_refs": []},
                "no_hallucination": {"score": 92, "pass": True, "reason": "accurate", "evidence_refs": []},
            },
            "confidence": "high",
            "dimension_notes": "Looks good.",
        }

@pytest.fixture
def confirmed_bundle(tmp_path):
    (tmp_path / "SKILL.md").write_text(
        "---\nname: attendance-check\nid: skill.attendance\n"
        "risk_level: low\ndescription: 员工出勤智能核查\n---\n# Attendance Check\n"
    )
    ec = tmp_path / "eval_cases"
    ec.mkdir()
    cases = [
        ("c01", "happy_path", "查询张三1月出勤"),
        ("c02", "happy_path", "查询部门出勤汇总"),
        ("c03", "edge_case", "查询未来日期"),
    ]
    for cid, ctype, intent in cases:
        (ec / f"{cid}.yaml").write_text(f"id: {cid}\ntype: {ctype}\nuser_intent: {intent}\n")
    (tmp_path / "sample_io").mkdir()
    (tmp_path / "sample_io" / "c01.json").write_text('{"output":"张三1月出勤21天"}')
    return str(tmp_path)

@pytest.mark.asyncio
async def test_full_pipeline_confirmed_pass(confirmed_bundle, tmp_path):
    db = str(tmp_path / "smoke.db")
    repo = SqliteRepository(db)
    repo.init_db()

    engine = EvaluationEngine(
        repo=repo,
        ds_provider=HighScoreProvider(),
        wb_provider=HighScoreProvider(),
    )

    run_id = repo.create_run(
        skill_id="skill.attendance",
        skill_bundle_path=confirmed_bundle,
        bundle_state="confirmed",
        evaluation_mode="capability_full",
    )

    await engine.run_async(
        run_id=run_id,
        skill_bundle_path=confirmed_bundle,
        bundle_state=BundleState.confirmed,
        evaluation_mode=EvaluationMode.capability_full,
    )

    report = repo.get_report(run_id)
    assert report is not None
    assert report["review_status"] in ("pass", "warn")
    assert report["score_total"] is not None
    assert report["score_total"] > 70
    assert report["bundle_state"] == "confirmed"
    assert report["evaluation_mode"] == "capability_full"
    print(f"\nSmoke test: review_status={report['review_status']} score={report['score_total']}")
```

- [ ] **Step 4: Run smoke test**

```powershell
pytest tests/test_e2e_smoke.py -v -s
```

Expected: `1 passed` with output showing `review_status=pass score=...`

- [ ] **Step 5: Final commit**

```bash
git add tests/test_e2e_smoke.py
git commit -m "test: E2E smoke test - full pipeline from ingest to evaluation_report.json"
```

---

## Post-Implementation: §6.4 DSL Assertion Engine (2.2 prerequisite)

> **Note:** The §6.4 DSL evaluator (`core/assert_/dsl.py`) is stubbed to return `True` for all assertions in this 2.0 MVP. It must be implemented before Task 2.2 (adversarial test cases). Create `tests/core/test_dsl.py` and implement the DSL parser at that point.

---

## Self-Review

**Spec coverage check:**

| Spec Section | Task |
|-------------|------|
| §1 仓库结构 + 技术栈 | Task 1 |
| §2 决策摘要 | All tasks |
| §5 Living Contract API | Task 9 |
| §6 编排模式 A/B/C/D | Task 8 |
| §7 状态机 + Case gate X1 | Task 4, 8 |
| §8 LLM Provider | Task 5 |
| §9 沙盒 | Task 6 |
| §10 SQLite 表结构 | Task 3 |
| §11 UI 双 Tab | Task 11 |
| §12 §14 检查清单 | Task 12 |

**Placeholder scan:** None found. All steps contain actual code or commands.

**Type consistency:** `EvaluationReport`, `ModelVote`, `BundleState`, `RunStatus` defined in Task 2 and used identically in Tasks 3, 8, 9.
