# Proposal: Wave 1 — Q-08 场景分类词表

## What

为阶段三 LUI / Propagator / 集市提供统一的业务场景分类基础设施：

1. `data/category_taxonomy.yaml` — 金融业务场景词表（Level1 / Level2 slug / 中文名 / 定义 / case 模板提示）
2. `core/taxonomy.py` — 加载词表、叶子节点查询、slug 合法性校验
3. `ingest._load_cases` 升级 — 区分有效/空壳/损坏 case，产出 `malformed_cases`
4. `scan_gaps` 接入 — `case_file_malformed` gap + `category` 词表校验
5. `GET /taxonomy/categories` API
6. `testskills/` 三样本 `category` frontmatter 回填

## Why

Q-08 阻塞「场景联动 + eval_case 自动生成」。Propagator（W3）和集市（W6）都需要合法 `category` slug；损坏 case 需在 gaps 层提前暴露，而非等到 Level0 才报错。

## Non-goals

- 不改 1.2 阈值
- 不实现 Propagator / LUI（W3/W4）
- 不做 PM 工作坊 UI（词表骨架可后续扩展）

## Relation to Sprint

SPRINT `phase3-marketplace.md` Wave 1（W1-1～W1-6）。依赖 Wave 0 ✅。

## Success Criteria

1. `pytest tests/ -x` 全绿（≥235 + Wave 1 新测试）
2. `GET /taxonomy/categories` 返回完整词表树 JSON
3. 三样本 `category` frontmatter 回填且 slug 校验通过
4. 损坏 case 文件产出 `malformed_cases` + `case_file_malformed` gap
