# Design: Wave 0 基础设施

> 实现参考文档。Subagent 执行前必须读本文件；接口定义即合约，不允许 TBD。

---

## 1. DDL Schema（组 A + B）

### 1.1 新建表

```sql
-- conversations：每次上传/挂载创建一个会话
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    skill_id        TEXT NOT NULL,
    source          TEXT NOT NULL,           -- 'local_ref' | 'upload'
    status          TEXT NOT NULL DEFAULT 'active',  -- active | frozen | published
    active_run_id   TEXT,                    -- 当前最新 run_id（nullable）
    auto_run_count  INTEGER NOT NULL DEFAULT 0,
    max_auto_runs   INTEGER NOT NULL DEFAULT 5,
    created_at      TEXT NOT NULL
);

-- lui_messages：LUI 对话历史（run_id 可为 null，对话发生在 run 触发前）
CREATE TABLE IF NOT EXISTS lui_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    run_id          TEXT,                    -- nullable
    role            TEXT NOT NULL,           -- 'user' | 'agent'
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
```

### 1.2 evaluation_runs 新增列（migration）

```sql
ALTER TABLE evaluation_runs ADD COLUMN conversation_id TEXT;
ALTER TABLE evaluation_runs ADD COLUMN parent_run_id TEXT;
ALTER TABLE evaluation_runs ADD COLUMN superseded_by_run_id TEXT;
```

### 1.3 PRAGMA user_version 迁移策略（单事务统管 + 宏微观双重门控）

**关键约束**：Python `sqlite3.executescript()` 在执行前会强制发出隐式 COMMIT，使其脱离外层事务块，产生 crash 窗口。**禁止使用 `executescript`**；所有 DDL 和 migration 必须在同一个 `with self._conn() as conn` 块内用 `cursor.execute()` 逐句执行。

```python
SCHEMA_VERSION = 1  # Wave 0 目标版本

def init_db(self) -> None:
    """单事务统管建表 + 迁移，消除 crash 窗口。"""
    with self._conn() as conn:
        cursor = conn.cursor()

        # --- 建表（CREATE TABLE IF NOT EXISTS 幂等）---
        cursor.execute("""CREATE TABLE IF NOT EXISTS evaluation_runs (
            run_id TEXT PRIMARY KEY, skill_id TEXT NOT NULL,
            skill_bundle_path TEXT NOT NULL, bundle_state TEXT NOT NULL,
            evaluation_mode TEXT NOT NULL, orchestration_mode TEXT,
            status TEXT NOT NULL DEFAULT 'pending', risk_level_locked TEXT,
            level_achieved TEXT, review_status TEXT, score_total REAL,
            score_total_source TEXT, completeness_score REAL,
            reason_codes TEXT DEFAULT '[]', report_json TEXT,
            human_review_required INTEGER DEFAULT 0,
            human_review_trigger_codes TEXT DEFAULT '[]',
            started_at TEXT, completed_at TEXT, created_at TEXT NOT NULL
        )""")
        # ... 其余原有表（stage_transitions / model_votes / gaps_snapshots /
        #     human_reviews / bundle_confirmations / analytics_events）同样用
        #     cursor.execute() 逐句建立 ...
        cursor.execute("""CREATE TABLE IF NOT EXISTS conversations (
            conversation_id TEXT PRIMARY KEY, skill_id TEXT NOT NULL,
            source TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
            active_run_id TEXT, auto_run_count INTEGER NOT NULL DEFAULT 0,
            max_auto_runs INTEGER NOT NULL DEFAULT 5, created_at TEXT NOT NULL
        )""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS lui_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL, run_id TEXT,
            role TEXT NOT NULL, content TEXT NOT NULL, created_at TEXT NOT NULL
        )""")

        # --- 宏观版本门控 ---
        version = cursor.execute("PRAGMA user_version").fetchone()[0]

        if version < 1:
            # 微观列检（PRAGMA table_info 对抗中间态 crash）
            existing = {r[1] for r in cursor.execute(
                "PRAGMA table_info('evaluation_runs')"
            ).fetchall()}
            for col, typedef in [
                ("conversation_id",     "TEXT"),
                ("parent_run_id",       "TEXT"),
                ("superseded_by_run_id","TEXT"),
            ]:
                if col not in existing:
                    cursor.execute(
                        f"ALTER TABLE evaluation_runs ADD COLUMN {col} {typedef}"
                    )
            cursor.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        # with 块结束时 sqlite3 驱动自动 COMMIT，整批操作原子落盘
```

**幂等性保证**：
- 建表：`CREATE TABLE IF NOT EXISTS` 内生幂等
- 列 ALTER：`PRAGMA table_info` 微观检查，列已存在时跳过
- 版本升级：`if version < 1` 宏观门控，migration 已完成时整体跳过
- Crash 场景：事务未 COMMIT → 下次启动 `user_version` 仍为 0 → 微观列检发现列已存在（部分 ALTER 已提交？不会，因为整批在同一事务内）→ 安全重跑

---

## 2. RunStatus 枚举（组 B）

**文件**：`skillhub_eval/core/schemas/enums.py`

在 `RunStatus` 类的 `failed = "failed"` 之后追加：

```python
superseded = "superseded"   # 被新 run 代写顶替，状态机终态，UI 置灰不展示
```

**有效前驱状态**：任意非 `superseded` 状态均可流转到 `superseded`（由 W4 `staging_writer` 调用 `update_status(old_run_id, "superseded", superseded_by_run_id=new_run_id)` 触发）。

**list_history 过滤**：`list_history` 默认 SQL 追加 `WHERE status != 'superseded'`。

---

## 3. BundleResolver（组 C）

**文件**：`skillhub_eval/core/bundle_resolver.py`（新建）

### 3.1 数据类

```python
from dataclasses import dataclass
from pathlib import Path

@dataclass
class BundleRef:
    conversation_id: str
    source: str               # 'local_ref' | 'upload'
    source_path: Path | None  # 原始 Skill 目录（local_ref 必填；upload 为 None）
    staging_path: Path        # {STAGING_ROOT}/{conversation_id}/

class BundleNotReadyError(Exception):
    """staging 未就绪且无法从 source fallback 时抛出（upload 模式下的非法访问）。
    上层 API 捕获后返回 503，前端保持 Loading 态。"""
```

### 3.2 BundleResolver 类

```python
class BundleResolver:
    def __init__(self, ref: BundleRef) -> None: ...

    def ensure_staging(self) -> None:
        """
        local_ref：原子重命名模式（消除半复制中间态）：
            1. 若 staging_path 已存在 → 幂等跳过（内容必定完整）
            2. 清理上次 crash 残留的 tmp_dir（staging_path.with_suffix('.tmp')）
            3. shutil.copytree(source_path, tmp_dir)  ← crash 在此不影响 staging_path
            4. tmp_dir.rename(staging_path)           ← OS 原子操作，瞬间完成
            5. 异常时 rmtree(tmp_dir) 清理，raise
        upload：仅 staging_path.mkdir(parents=True, exist_ok=True)（W3 解压填充）
        任何情况下不修改 source_path。
        """

    def get_file_content(self, relative_path: str) -> str:
        """
        状态守卫模式（不做自动 fallback）：
        1. staging_path / relative_path 存在 → 读取并返回
        2. staging 不存在，且 source='local_ref'（source_path 非 None）
           → fallback 读 source_path / relative_path
        3. staging 不存在，且 source='upload'（source_path is None）
           → raise BundleNotReadyError（系统未就绪，上层返回 503）
        4. 路径存在但文件不存在 → raise FileNotFoundError(relative_path)

        语义保证：upload 模式下 ensure_staging() 执行前任何读操作均被拦截，
        不会产生 NoneType / AttributeError 的歧义报错。
        """

    def write_file_content(self, relative_path: str, content: str) -> None:
        """
        写到 staging_path / relative_path；
        自动 mkdir parents；
        调用前未 ensure_staging() 时自动调用（防止调用顺序错误导致写失败）。
        """

    def list_files(self, subdir: str = "") -> list[str]:
        """
        列举 staging_path / subdir 下所有文件的相对路径（相对于 staging_path）；
        subdir 不存在时返回空列表。
        """

    @classmethod
    def from_settings(
        cls,
        conversation_id: str,
        source: str,
        source_path: str | None = None,
    ) -> "BundleResolver":
        """
        从 settings.STAGING_ROOT 构造 BundleRef 并返回 resolver；
        source='local_ref' 时 source_path 必传，否则 ValueError。
        """
```

### 3.3 settings.py 追加

```python
# staging root：W3 Propagator 写合成 case 的沙盒根目录
STAGING_ROOT: str = os.getenv("STAGING_ROOT", "data/staging")
```

---

## 4. Repository Protocol 扩展（组 D）

### 4.1 ports.py 新增方法

```python
def create_conversation(
    self,
    skill_id: str,
    source: str,
    max_auto_runs: int = 5,
) -> str: ...                    # 返回 conversation_id

def get_conversation(
    self,
    conversation_id: str,
) -> dict | None: ...

def append_lui_message(
    self,
    conversation_id: str,
    role: str,
    content: str,
    run_id: str | None = None,
) -> None: ...
```

### 4.2 create_run 签名升级（原子回写 active_run_id）

```python
def create_run(
    self,
    skill_id: str,
    skill_bundle_path: str,
    bundle_state: str,
    evaluation_mode: str,
    conversation_id: str | None = None,   # 新增（可选，向后兼容）
    parent_run_id: str | None = None,     # 新增（可选，向后兼容）
) -> str: ...
```

**SqliteRepository 实现要点（单事务两步原子化）**：
```python
def create_run(self, ..., conversation_id=None, parent_run_id=None) -> str:
    run_id = str(uuid.uuid4())
    with self._conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO evaluation_runs (..., conversation_id, parent_run_id) VALUES (...)",
            (..., conversation_id, parent_run_id),
        )
        # 原子挂载 Session Lock 指针：只要有关联 conversation，立即回写
        if conversation_id:
            cursor.execute(
                "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
                (run_id, conversation_id),
            )
    return run_id
```

**保证**：`evaluation_runs` 行插入与 `conversations.active_run_id` 更新在同一 SQLite 事务内原子提交——无幽灵 run，无 NULL 指针窗口。

### 4.3 update_status 扩展 allowed 集合

`update_status` 的 `allowed` set 追加：`"superseded_by_run_id"`。

### 4.4 SqliteRepository 实现

**create_conversation**：
```python
conv_id = str(uuid.uuid4())
conn.execute(
    "INSERT INTO conversations (conversation_id, skill_id, source, created_at) VALUES (?,?,?,?)",
    (conv_id, skill_id, source, self._now()),
)
return conv_id
```

**get_conversation**：
```python
row = conn.execute("SELECT * FROM conversations WHERE conversation_id=?", (conv_id,)).fetchone()
return dict(row) if row else None
```

**append_lui_message**：
```python
conn.execute(
    "INSERT INTO lui_messages (conversation_id, run_id, role, content, created_at) VALUES (?,?,?,?,?)",
    (conversation_id, run_id, role, content, self._now()),
)
```

---

## 5. 测试策略（组 E）

**文件**：`tests/persistence/test_wave0_infra.py`（新建）

所有测试使用临时 SQLite DB（`tmp_path` fixture）。

| 测试函数 | 覆盖场景 |
|---------|---------|
| `test_init_db_idempotent` | 二次 `init_db()` 不抛异常 |
| `test_migration_adds_lineage_columns` | 旧 DB（无 lineage 列）执行 `init_db()` 后 `user_version=1`，三列存在 |
| `test_create_run_with_conversation_id` | `create_run(..., conversation_id=cid)` 写入后 `get_run` 可读回 `conversation_id` |
| `test_update_status_superseded` | `update_status(run_id, "superseded", superseded_by_run_id=new_id)` 后 `get_run` status 为 "superseded" |
| `test_list_history_excludes_superseded` | 含 superseded run 的 DB，`list_history()` 不返回该 run |
| `test_create_conversation` | create → get 读回 skill_id / source / status / auto_run_count |
| `test_append_lui_message` | append user + agent → 查询返回有序两条记录 |
| `test_bundle_resolver_local_ref_ensure_staging` | `ensure_staging()` 拷贝文件到 staging；源目录不变 |
| `test_bundle_resolver_ensure_staging_idempotent` | 二次 `ensure_staging()` 不报错，内容不变 |
| `test_bundle_resolver_get_file_content` | `ensure_staging()` 后 `get_file_content("SKILL.md")` 返回内容 |
| `test_bundle_resolver_write_file_content` | `write_file_content("eval_cases/c1.yaml", "...")` 后文件存在于 staging |
| `test_bundle_resolver_list_files` | `list_files("eval_cases")` 返回 staging 内文件相对路径列表 |
| `test_bundle_resolver_source_readonly` | `write_file_content` 后，source_path 对应文件内容不变 |
| `test_bundle_resolver_upload_unready_raises` | upload 模式未调用 `ensure_staging`，`get_file_content` 抛出 `BundleNotReadyError`（而非 TypeError） |
| `test_bundle_resolver_local_ref_fallback_before_staging` | local_ref 模式未调用 `ensure_staging`，`get_file_content("SKILL.md")` fallback 读 source_path 成功 |

---

## 6. 模块依赖关系

```
settings.py
    └── core/bundle_resolver.py   (读 STAGING_ROOT)
core/schemas/enums.py             (RunStatus.superseded)
    └── persistence/sqlite.py     (update_status allowed set)
core/ports.py                     (Protocol 扩展)
    └── persistence/sqlite.py     (实现新方法)
tests/persistence/test_wave0_infra.py
    └── persistence/sqlite.py + core/bundle_resolver.py
```

现有文件均不引入新循环依赖。`bundle_resolver.py` 不依赖 `persistence` 层。
