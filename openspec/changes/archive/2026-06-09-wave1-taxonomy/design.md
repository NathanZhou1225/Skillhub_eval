# Design: Wave 1 — Q-08 场景分类词表

## 1. category_taxonomy.yaml 结构

```yaml
version: "1.0"
categories:
  - slug: fin-research
    name_zh: 金融核心投研
    children:
      - slug: fin-statement
        name_zh: 财务三表/审计数据
        definition: ...
        case_template_hint: ...
      - slug: macro-indicator
        ...
      - slug: quant-signal
        ...
  - slug: asset-compliance
    name_zh: 资产管理与合规
    children: [...]
  - slug: general-utility
    name_zh: 日常效能与通用
    children: [...]
```

叶子节点完整 slug 格式：`{level1_slug}/{level2_slug}`（如 `fin-research/quant-signal`）。

## 2. core/taxonomy.py

```python
@dataclass
class TaxonomyLeaf:
    full_slug: str          # "fin-research/quant-signal"
    level1_slug: str
    level2_slug: str
    name_zh: str
    definition: str
    case_template_hint: str

class Taxonomy:
    def __init__(self, path: Path | None = None): ...
    def is_valid_slug(self, slug: str) -> bool: ...
    def get_leaf(self, slug: str) -> TaxonomyLeaf | None: ...
    def list_leaves(self) -> list[TaxonomyLeaf]: ...
    def to_tree_json(self) -> dict: ...   # for API
```

默认路径：`data/category_taxonomy.yaml`。

## 3. ingest._load_cases 升级

返回结构改为：
```python
{
    "cases": list[dict],           # 有效 case
    "malformed_cases": list[dict], # {path, reason}
}
```

或保持 `load_bundle` 在 bundle dict 上挂 `malformed_cases` 字段（与现有 `eval_cases` 列表并存）。

损坏判定：
- 文件存在但 YAML/JSON 解析失败 → malformed
- 解析成功但缺少 `id` → malformed（空壳）
- 有效 case 进入 `cases` 列表

## 4. scan_gaps 扩展

- 每个 `malformed_cases` 项 → `case_file_malformed` gap（severity=warn）
- `category` 字段：若缺失 → gap；若存在但 slug 非法 → gap；合法则通过

## 5. API

`GET /taxonomy/categories` → `Taxonomy().to_tree_json()`

路由文件：`adapters/api/routes/taxonomy.py`，注册到 `app.py`。

## 6. testskills 回填

| 样本 | category |
|------|----------|
| stock-radar-V6.2 | fin-research/quant-signal |
| grill-me | general-utility/report-generator |
| tiered-memory-sprint-manager | general-utility/report-generator |
