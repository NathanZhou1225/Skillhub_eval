# SkillHub 评估系统

> **说明**：本仓库当前交付的是 **Skill 自动评估系统**（质检流水线 + 对话式评估 UI），属于 SkillHub 平台的一部分。Skill 集市、上架运营、IAM 等能力在路线图中，**不在本 README 范围**。

面向内部 Skill 的**结构化准入质检**：按统一元数据规范检查材料、自动/半自动补题、双模型交叉打分，输出通过 / 需人工 / 不通过结论及可读报告。

## 能力概览

- **评估引擎**：Level0 结构门禁 → 缺口扫描 → 双模型（DeepSeek + Gemini）三维评分 → 专家复核台
- **对话式 UI**：Chat-First 上传 ZIP、材料补充、评估进度与报告分流（`/ui/index.html`）
- **CLI**：本地触发评估、查状态/历史、作者确认缺口字段、启动 API 服务
- **持久化**：SQLite 记录轮次、阶段日志、模型投票与人工裁定

更完整的业务说明见 [`docs/guides/Skill评估系统全景说明.md`](docs/guides/Skill评估系统全景说明.md)。

## 环境要求

- Python **3.11+**
- 可访问 DeepSeek 与 Gemini API（`EVAL_LLM_MODE=live` 时必填）

## 快速开始

### 1. 安装

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Unix:     source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. 配置环境变量

```bash
cp .env.example .env    # Windows: copy .env.example .env
```

编辑 `.env`，至少填入：

| 变量 | 说明 |
|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API 密钥 |
| `GEMINI_API_KEY` | Google AI Studio Gemini 密钥 |

其余项见 [`.env.example`](.env.example) 内注释（存储路径、超时、Demo 开关等）。

验证双模型连通：

```bash
python scripts/check_providers.py
```

### 3. 启动服务

```bash
skillhub-eval serve
```

- 评估 UI：<http://127.0.0.1:8000/ui/index.html>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

修改 `.env` 后需重启 `serve`。

### 4. CLI 评估（可选，无需 HTTP）

```bash
# 对本地 Skill 包目录触发评估
skillhub-eval run path/to/skill-bundle --bundle-state confirmed --mode capability_full

skillhub-eval status <run_id>
skillhub-eval history
skillhub-eval confirm <skill_id> --field "negative_prompts=..." --operator alice
```

## 项目结构

```
skillhub_eval/          # Python 包（core / providers / persistence / adapters）
docs/specs/             # 元数据规范、评估指标（权威协议）
docs/guides/            # 作者指南、报告规范、全景说明
tests/                  # 单元与集成测试
data/                   # 运行时 DB 与 staging（gitignore，本地生成）
.env.example            # 环境变量模板
```

## 测试

```bash
pytest
```

## 规范文档

| 文档 | 用途 |
|------|------|
| [`docs/specs/Skill元数据定义与编写规范.md`](docs/specs/Skill元数据定义与编写规范.md) | Skill 包结构与字段 |
| [`docs/specs/评估指标与准入标准.md`](docs/specs/评估指标与准入标准.md) | 评分公式与阈值（唯一权威） |
| [`docs/guides/Skill编写指南.md`](docs/guides/Skill编写指南.md) | 作者如何准备材料 |

## 许可证与贡献

内部项目。提交前勿将 `.env`、API 密钥或 `data/` 运行时产物纳入版本库。
