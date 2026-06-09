# Tasks: Wave 1 — Q-08 场景分类词表

> 验证门禁：`python -m pytest tests/ -x --tb=short`

---

## Task 1 — category_taxonomy.yaml + core/taxonomy.py

**文件**：
- `data/category_taxonomy.yaml`（新建，Sprint W1-1 骨架）
- `skillhub_eval/core/taxonomy.py`（新建）
- `tests/core/test_taxonomy.py`（新建）

**验证**：
```bash
python -m pytest tests/core/test_taxonomy.py -v
```

---

## Task 2 — ingest._load_cases 升级 + malformed_cases

**文件**：`skillhub_eval/core/ingest.py`、`tests/core/test_ingest.py`（新建或扩展）

**验证**：
```bash
python -m pytest tests/core/test_ingest.py -v
```

---

## Task 3 — scan_gaps 接入 malformed_cases + category 校验

**文件**：`skillhub_eval/core/gaps.py`、`tests/core/test_gaps.py`（扩展）

**验证**：
```bash
python -m pytest tests/core/test_gaps.py -v
```

---

## Task 4 — GET /taxonomy/categories API

**文件**：
- `skillhub_eval/adapters/api/routes/taxonomy.py`（新建）
- `skillhub_eval/adapters/api/app.py`（注册路由）
- `tests/api/test_taxonomy.py`（新建）

**验证**：
```bash
python -m pytest tests/api/test_taxonomy.py -v
```

---

## Task 5 — testskills 三样本 category 回填

**文件**：`testskills/*/SKILL.md` frontmatter

**验证**：Task 1 slug 校验 + ingest 通过

---

## Task 6 — 全量门禁

```bash
python -m pytest tests/ -x --tb=short
```

## 完成门禁

- [x] taxonomy 加载 + slug 校验测试通过
- [x] malformed_cases 解析测试通过
- [x] category gap 检测测试通过
- [x] API 返回词表树 JSON
- [x] 全量 pytest 全绿（250 passed）
