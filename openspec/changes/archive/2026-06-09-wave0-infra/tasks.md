# Tasks: Wave 0 基础设施

> 实现真源：本文件。Subagent 执行前必须读 `design.md` 确认接口细节。
> 验证命令：每任务末注明；整体门禁 `pytest tests/ -x --tb=short`。

---

## Task 1 — DDL migration（PRAGMA user_version）

**文件**：`skillhub_eval/persistence/sqlite.py`

**改动 1**：在模块顶部 `DDL` 常量之前加入两张新表的 DDL（追加到 `DDL` 字符串末尾）：

```sql
CREATE TABLE IF NOT EXISTS conversations (
    conversation_id TEXT PRIMARY KEY,
    skill_id        TEXT NOT NULL,
    source          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    active_run_id   TEXT,
    auto_run_count  INTEGER NOT NULL DEFAULT 0,
    max_auto_runs   INTEGER NOT NULL DEFAULT 5,
    created_at      TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS lui_messages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    run_id          TEXT,
    role            TEXT NOT NULL,
    content         TEXT NOT NULL,
    created_at      TEXT NOT NULL
);
```

**改动 2**：在 `SqliteRepository` 类中新增 `SCHEMA_VERSION = 1` 类变量。

**改动 3**：**完全重写 `init_db()`**，弃用 `executescript`（因其隐式 COMMIT 导致 crash 窗口），改为单事务统管建表 + 宏微观双重门控迁移：

```python
SCHEMA_VERSION = 1

def init_db(self) -> None:
    """单事务统管：建表 + migration 在同一 with 块内原子提交。"""
    with self._conn() as conn:
        cursor = conn.cursor()
        # 建表（每张表一条 cursor.execute，保持事务内）
        # [将原 DDL 字符串里的各建表语句逐条拆出，用 cursor.execute() 执行]
        # 新增两张表同样在此处建立（conversations、lui_messages）

        # 宏观版本门控
        version = cursor.execute("PRAGMA user_version").fetchone()[0]
        if version < 1:
            # 微观列检：防 crash 中间态重跑
            existing = {r[1] for r in cursor.execute(
                "PRAGMA table_info('evaluation_runs')"
            ).fetchall()}
            for col, typedef in [
                ("conversation_id",      "TEXT"),
                ("parent_run_id",        "TEXT"),
                ("superseded_by_run_id", "TEXT"),
            ]:
                if col not in existing:
                    cursor.execute(
                        f"ALTER TABLE evaluation_runs ADD COLUMN {col} {typedef}"
                    )
            cursor.execute(f"PRAGMA user_version = {self.SCHEMA_VERSION}")
        # with 结束时 sqlite3 驱动自动 COMMIT，整批原子落盘
```

> **注意**：模块顶部的 `DDL` 字符串常量保留（向后兼容现有测试引用），但 `init_db()` 不再调用 `executescript(DDL)`，改为逐句 `cursor.execute()`。

**验证**：
```bash
pytest tests/persistence/test_wave0_infra.py::test_init_db_idempotent -v
pytest tests/persistence/test_wave0_infra.py::test_migration_adds_lineage_columns -v
```

---

## Task 2 — RunStatus.superseded 枚举 + update_status 扩展

**文件 1**：`skillhub_eval/core/schemas/enums.py`

在 `RunStatus.failed = "failed"` 之后追加：
```python
superseded = "superseded"
```

**文件 2**：`skillhub_eval/persistence/sqlite.py`

`update_status` 方法内 `allowed` set 追加 `"superseded_by_run_id"`：
```python
allowed = {
    "risk_level_locked",
    "level_achieved",
    "review_status",
    "score_total",
    "score_total_source",
    "completeness_score",
    "reason_codes",
    "orchestration_mode",
    "completed_at",
    "superseded_by_run_id",   # ← 新增
}
```

`list_history` 的 SQL query 字符串追加 `WHERE status != 'superseded'`（或在已有 `WHERE human_review_required=?` 分支中用 `AND`）：

```python
# 重写 list_history 的查询基础字符串，过滤 superseded
base = (
    "SELECT run_id, skill_id, status, review_status, score_total, "
    "score_total_source, reason_codes, bundle_state, evaluation_mode, "
    "human_review_required, created_at "
    "FROM evaluation_runs WHERE status != 'superseded'"
)
if human_review_required is not None:
    base += " AND human_review_required=?"
    params.append(1 if human_review_required else 0)
base += " ORDER BY created_at DESC LIMIT ?"
```

**验证**：
```bash
pytest tests/persistence/test_wave0_infra.py::test_update_status_superseded -v
pytest tests/persistence/test_wave0_infra.py::test_list_history_excludes_superseded -v
pytest tests/ -x --tb=short
```

---

## Task 3 — Repository Protocol 最小扩展

**文件**：`skillhub_eval/core/ports.py`

追加三个新方法声明，并修改 `create_run` 签名：

```python
def create_conversation(
    self,
    skill_id: str,
    source: str,
    max_auto_runs: int = 5,
) -> str: ...

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

修改 `create_run` 签名（在 `evaluation_mode: str` 后追加两个可选参数）：
```python
def create_run(
    self,
    skill_id: str,
    skill_bundle_path: str,
    bundle_state: str,
    evaluation_mode: str,
    conversation_id: str | None = None,
    parent_run_id: str | None = None,
) -> str: ...
```

**验证**：
```bash
python -c "from skillhub_eval.core.ports import Repository; print('ports ok')"
pytest tests/ -x --tb=short
```

---

## Task 4 — SqliteRepository 新 CRUD 方法

**文件**：`skillhub_eval/persistence/sqlite.py`

**4-A**：`create_conversation` 方法：
```python
def create_conversation(
    self,
    skill_id: str,
    source: str,
    max_auto_runs: int = 5,
) -> str:
    conv_id = str(uuid.uuid4())
    with self._conn() as conn:
        conn.execute(
            """
            INSERT INTO conversations
                (conversation_id, skill_id, source, max_auto_runs, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conv_id, skill_id, source, max_auto_runs, self._now()),
        )
    return conv_id
```

**4-B**：`get_conversation` 方法：
```python
def get_conversation(self, conversation_id: str) -> dict | None:
    with self._conn() as conn:
        row = conn.execute(
            "SELECT * FROM conversations WHERE conversation_id=?",
            (conversation_id,),
        ).fetchone()
    return dict(row) if row else None
```

**4-C**：`append_lui_message` 方法：
```python
def append_lui_message(
    self,
    conversation_id: str,
    role: str,
    content: str,
    run_id: str | None = None,
) -> None:
    with self._conn() as conn:
        conn.execute(
            """
            INSERT INTO lui_messages
                (conversation_id, run_id, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (conversation_id, run_id, role, content, self._now()),
        )
```

**4-D**：`create_run` 升级——单事务两步原子化（INSERT run + 回写 active_run_id）：
```python
def create_run(
    self,
    skill_id: str,
    skill_bundle_path: str,
    bundle_state: str,
    evaluation_mode: str,
    conversation_id: str | None = None,
    parent_run_id: str | None = None,
) -> str:
    run_id = str(uuid.uuid4())
    with self._conn() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO evaluation_runs (
                run_id, skill_id, skill_bundle_path, bundle_state,
                evaluation_mode, conversation_id, parent_run_id,
                started_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id, skill_id, skill_bundle_path, bundle_state,
                evaluation_mode, conversation_id, parent_run_id,
                self._now(), self._now(),
            ),
        )
        # 原子挂载 Session Lock 指针
        if conversation_id:
            cursor.execute(
                "UPDATE conversations SET active_run_id=? WHERE conversation_id=?",
                (run_id, conversation_id),
            )
    return run_id
```

**验证**：
```bash
pytest tests/persistence/test_wave0_infra.py::test_create_conversation -v
pytest tests/persistence/test_wave0_infra.py::test_append_lui_message -v
pytest tests/persistence/test_wave0_infra.py::test_create_run_with_conversation_id -v
pytest tests/ -x --tb=short
```

---

## Task 5 — settings.py STAGING_ROOT + core/bundle_resolver.py

**文件 1**：`skillhub_eval/settings.py`

在现有 settings 末尾追加：
```python
STAGING_ROOT: str = os.getenv("STAGING_ROOT", "data/staging")
```

**文件 2**：`skillhub_eval/core/bundle_resolver.py`（新建）

完整实现 `BundleRef` dataclass、`BundleNotReadyError` 异常类和 `BundleResolver` 类（见 design.md §3）：

- `ensure_staging()`：**原子重命名模式**（消除半复制中间态）：
  ```python
  staging_dir = Path(self.ref.staging_path)
  if staging_dir.exists():        # 只有完整拷贝后才存在，幂等跳过
      return
  tmp_dir = staging_dir.with_suffix('.tmp')
  try:
      if tmp_dir.exists():
          shutil.rmtree(tmp_dir)  # 清理上次 crash 残留
      shutil.copytree(Path(self.ref.source_path), tmp_dir)
      tmp_dir.rename(staging_dir) # OS 原子操作
  except Exception:
      if tmp_dir.exists():
          shutil.rmtree(tmp_dir)
      raise
  ```
  `upload` 模式：仅 `staging_dir.mkdir(parents=True, exist_ok=True)`（W3 解压填充）
- `BundleRef.source_path` 类型为 `Path | None`（upload 时为 None，local_ref 必填）
- `BundleNotReadyError(Exception)`：状态守卫异常，upload 模式 staging 未就绪时抛出
- `get_file_content(relative_path)`：状态守卫模式：
  ```python
  def get_file_content(self, relative_path: str) -> str:
      target = self.ref.staging_path / relative_path
      if target.exists():
          return target.read_text(encoding="utf-8")
      # fallback 仅限 local_ref
      if self.ref.source_path is not None:
          src = self.ref.source_path / relative_path
          if src.exists():
              return src.read_text(encoding="utf-8")
          raise FileNotFoundError(relative_path)
      # upload 模式：staging 未就绪，上层返回 503
      raise BundleNotReadyError(
          f"staging not ready and no source fallback for: {relative_path}"
      )
  ```
- `write_file_content(relative_path, content)`：自动调 `ensure_staging()`；`(staging_path / relative_path).parent.mkdir(parents=True, exist_ok=True)`；写入 UTF-8
- `list_files(subdir="")`：`glob("**/*", recursive=True)` 过滤文件，返回相对路径字符串列表
- `from_settings(cls, conversation_id, source, source_path=None)`：类方法，从 `skillhub_eval.settings.STAGING_ROOT` 构造

**验证**：
```bash
pytest tests/persistence/test_wave0_infra.py -k "bundle_resolver" -v
```

---

## Task 6 — pytest：tests/persistence/test_wave0_infra.py

**文件**：`tests/persistence/test_wave0_infra.py`（新建）

实现 design.md §5 定义的 13 个测试函数，全部使用 `tmp_path` fixture：

- DDL 幂等：`test_init_db_idempotent`
- 旧 DB migration：`test_migration_adds_lineage_columns`
  - 构造不含新列的旧 DB（手动创建旧版 DDL），执行 `init_db()`，检查三列存在且 `user_version=1`
- Lineage 列读写：`test_create_run_with_conversation_id`
- superseded 状态：`test_update_status_superseded`、`test_list_history_excludes_superseded`
- Conversation CRUD：`test_create_conversation`
- LUI messages：`test_append_lui_message`
- BundleResolver（8 个，包含 grill-me Q4 新增）：见 design.md §5
  - `test_bundle_resolver_upload_unready_raises`：upload 模式未调 `ensure_staging`，`get_file_content` 抛 `BundleNotReadyError`（不是 TypeError）
  - `test_bundle_resolver_local_ref_fallback_before_staging`：local_ref 未调 `ensure_staging`，`get_file_content("SKILL.md")` fallback 读 source_path 成功

**验证（整体门禁）**：
```bash
pytest tests/persistence/test_wave0_infra.py -v
pytest tests/ -x --tb=short
# 期望：原 220 + 新增 Wave 0 测试全部通过
```

---

## 执行顺序与依赖

```
Task 1 (DDL migration)
    ↓
Task 2 (RunStatus.superseded + list_history 过滤)
    ↓
Task 3 (ports.py Protocol 扩展)
    ↓
Task 4 (SqliteRepository 新 CRUD)
    ↓
Task 5 (settings + BundleResolver)         ← 可与 Task 3/4 并行
    ↓
Task 6 (pytest)
```

Task 3、4、5 无循环依赖，可由两个 subagent 并行执行（Task 3+4 一组，Task 5 独立）。

## 完成门禁

- [x] `pytest tests/ -x --tb=short` 全绿（235 passed = 220 + 15 Wave 0 新测试）
- [x] `python -c "from skillhub_eval.core.schemas.enums import RunStatus; assert RunStatus.superseded"`
- [x] 旧 DB migration 测试：`test_migration_adds_lineage_columns` 通过
- [x] BundleResolver 写文件后源目录不变：`test_bundle_resolver_source_readonly` 通过
- [x] `list_history()` 不返回 superseded runs：`test_list_history_excludes_superseded` 通过
