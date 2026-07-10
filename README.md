# SkillHub 评估系统

> **说明**：本仓库当前交付的是 **Skill 自动评估系统**（质检流水线 + 对话式评估 UI + 可选本地 CLI Agent 真跑），属于 SkillHub 平台的一部分。Skill 集市、上架运营、服务器多人部署、IAM 等能力在**阶段四**路线图中，**不在本 README 实现范围**。

面向内部 Skill 的**结构化准入质检**：按统一元数据规范检查材料、自动/半自动补题、双模型交叉打分，输出通过 / 需人工 / 不通过结论及可读报告；可选穿透本机 Codex / Cursor Agent / Trae 等 CLI 真跑用例后再评审。

## 当前阶段（2026-07-09）

| 项 | 状态 |
|----|------|
| **阶段一** 规范文档 | ✅ |
| **阶段二** 评估引擎 | ✅ |
| **阶段三** 评估系统（对话评估；本地真跑为可选） | 🟢 **主链路已实机验收，可交接继续增强**；尚未正式完结 |
| **阶段四** 服务器 / 集市 / 立项 | ⬜ 待启动 |

下一任同学或 agent：先读根目录 [`RECORD.md`](RECORD.md) 顶部 **「交接快照」**，再读本 README 启动服务。当前**无活跃 OpenSpec change**（`local-cli-runtime-platform` 已归档）。

## 能力概览

- **评估引擎**：Level0 结构门禁 → 缺口扫描 / 补题 → 双模型三维评分 → 专家复核
- **对话式 UI**：Chat-First 上传 ZIP、材料补充、评估进度、报告分流、会话归档（`/ui/index.html`）
- **本地 Agent 真跑（可选）**：选择本机 CLI → 环境检查（诊断，非硬门禁）→ 真跑 case → 回传产出 → 复用 judge
- **CLI**：本地触发评估、查状态/历史、启动 API 服务
- **持久化**：SQLite 记录轮次、阶段日志、模型投票与人工裁定

更完整的业务说明见 [`docs/guides/Skill评估系统全景说明.md`](docs/guides/Skill评估系统全景说明.md)。本地真跑见 [`docs/guides/本地CLI Agent真跑机制说明.md`](docs/guides/本地CLI%20Agent真跑机制说明.md) 与 [`docs/runbooks/local-agent-exec-validation.md`](docs/runbooks/local-agent-exec-validation.md)。

## 环境要求

- Python **3.11+**
- 可访问双模型 API（默认 DeepSeek + Gemini；由 `.env` 中 `JUDGE_PROVIDER_A/B_*` 配置）
- （可选）本机已安装并登录 Codex / Cursor Agent / Trae 等 CLI，用于本地真跑

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

编辑 `.env`，至少配置双评审槽位的 API Key / base URL / model（见 `.env.example` 中 `JUDGE_PROVIDER_A_*` / `JUDGE_PROVIDER_B_*`）。

验证连通：

```bash
python scripts/check_providers.py
```

### 3. 启动服务

```bash
skillhub-eval serve
# 或: python -m skillhub_eval.adapters.cli.main serve --host 127.0.0.1 --port 8000
```

- 评估 UI：<http://127.0.0.1:8000/ui/index.html>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

修改 `.env` 后需重启 `serve`。多人试用时请**各自启动** `serve`（执行偏好目前为进程级全局状态）。

### 3.1 新机器启动检查清单

新机器拉取仓库后，按下面顺序确认：

1. **Python 与依赖**：Python 3.11+；已创建虚拟环境并执行 `pip install -e ".[dev]"`。
2. **`.env`**：从 `.env.example` 复制，不要复用旧电脑的 `.env`；至少填好 `JUDGE_PROVIDER_A/B_*`。
3. **模型连通**：执行 `python scripts/check_providers.py`。如果失败，服务可以启动，但正式评估会在双模型阶段失败。
4. **本机启动**：执行 `skillhub-eval serve`，在同一台机器打开 `http://127.0.0.1:8000/ui/index.html` 和 `http://127.0.0.1:8000/docs`。
5. **跨机器访问**：如果 A 机器运行 server、B 机器浏览器访问，A 机器必须用 `skillhub-eval serve --host 0.0.0.0 --port 8000` 启动；B 机器访问 `http://<A机器IP>:8000/ui/index.html`，不能用 B 自己的 `127.0.0.1`。
6. **本地 Agent 真跑（可选）**：如果需要 Codex / Cursor Agent / Trae 真跑，在运行 `serve` 的机器上重新安装、登录，并在 UI 执行设置里 scan/test。默认 `sample_io` 路径不要求本地 Agent。

常见问题：

| 现象 | 原因 | 处理 |
|------|------|------|
| 新机器 IP 变了，本机打不开 `127.0.0.1:8000` | server 没启动、端口被占用、虚拟环境没激活 | 重新激活 venv 后执行 `skillhub-eval serve`；必要时换 `--port` |
| 本机能打开，别的机器打不开 | server 绑定在默认 `127.0.0.1`，只监听本机 | 用 `--host 0.0.0.0 --port 8000` 启动，并检查防火墙/网络策略 |
| 别的机器打开 `127.0.0.1:8000` 不通 | `127.0.0.1` 永远指“当前浏览器所在机器自己” | 改访问 `http://<运行server的机器IP>:8000/...` |
| 页面打开但正式评估失败 | 双模型 API Key / base URL / model 配错，或网络不可达 | 检查 `.env`，跑 `python scripts/check_providers.py` |
| 上传 ZIP 后路径/缓存异常 | 复用了旧机器的 `EVAL_DB_PATH`、`STAGING_ROOT` 或运行时数据 | 新机器使用相对路径默认值，必要时清空本地 `data/` 后重试 |
| 本地 Agent 显示不可用 | CLI 没装、没登录、不在 PATH，或模型未配置 | 在运行 `serve` 的同一终端确认 CLI 可用，再到 UI scan/test |
| 改了 `.env` 但没变化 | 设置在进程启动时读取 | 重启 `skillhub-eval serve` |

### 3.2 换电脑 / 服务器承接注意

当前 Demo 默认是**单机本地服务**：`serve` 默认绑定 `127.0.0.1`，只能从运行服务的那台电脑访问。迁移到新电脑或临时服务器时，主要检查这些位置：

| 位置 | 需要确认 / 修改 |
|------|------------------|
| [`skillhub_eval/adapters/cli/main.py`](skillhub_eval/adapters/cli/main.py) | `serve` 默认 `host="127.0.0.1"`。只给本机用可不改；需要局域网访问时用 `--host 0.0.0.0 --port 8000` 启动，或把默认 host 改成目标绑定地址。 |
| `.env` / [`.env.example`](.env.example) | 重新配置 `JUDGE_PROVIDER_A/B_*`、`EVAL_DB_PATH`、`STAGING_ROOT`、`EXEC_SOURCE`、`EXEC_AGENT`、`EXEC_MODEL`、超时参数。不要复用旧电脑的绝对路径或密钥文件。 |
| [`skillhub_eval/settings.py`](skillhub_eval/settings.py) | 环境变量读取口径在这里；若要新增服务器级配置项，应先在这里加字段，再同步 `.env.example`。 |
| [`skillhub_eval/adapters/ui/static/assets/index.js`](skillhub_eval/adapters/ui/static/assets/index.js) | 前端当前 `API=''`，即同源调用后端。若未来把静态 UI 和 API 分开部署，需要改成后端地址，例如 `http://<server-ip>:8000`，并同步处理 CORS。 |
| 本地 CLI Agent | Codex / Cursor Agent / Trae 等是**运行 `serve` 的机器本地环境**。换电脑后必须重新安装、登录，并在 UI 执行设置里重新 scan/test；旧电脑的 `C:\Users\...` 路径、Trae/Cursor 配置和 runtime preflight cache 不能直接当作可用状态。 |
| 网络与防火墙 | 如果用 `--host 0.0.0.0`，浏览器访问 `http://<server-ip>:8000/ui/index.html`；Windows 防火墙 / 公司网络策略可能还需放行端口。 |

目前没有发现业务代码写死某个局域网 IP；主要限制来自启动绑定地址、`.env` 路径/API Key、本地 Agent 安装状态和进程级执行偏好。

### 4. CLI 评估（可选，无需 HTTP）

```bash
skillhub-eval run path/to/skill-bundle --bundle-state confirmed --mode capability_full
skillhub-eval status <run_id>
skillhub-eval history
```

## 项目结构

```
skillhub_eval/          # Python 包（core / execution / providers / persistence / adapters）
docs/specs/             # 元数据规范、评估指标（权威协议）
docs/guides/            # 作者指南、报告规范、全景说明、本地 CLI 说明
docs/runbooks/          # 验收与运维 runbook
openspec/               # 变更契约与主 spec（含 skill-execution）
.project_memory/        # Sprint / Backlog / 架构记忆
tests/                  # 单元与集成测试
testskills/             # 样例与 fixture Skill
data/                   # 运行时 DB 与 staging（gitignore，本地生成）
.env.example            # 环境变量模板
RECORD.md               # 项目总账（开场读「交接快照」）
```

## 测试

```bash
pytest
```

本地 Agent 真机 E2E（需本机 CLI，默认 skip）：

```bash
# 见 docs/runbooks/local-agent-exec-validation.md
set RUN_LOCAL_AGENT=1
pytest tests/execution -q
```

## 规范与接手文档

| 文档 | 用途 |
|------|------|
| [`RECORD.md`](RECORD.md) | 交接快照、时间线、已完成/未完成、决策 |
| [`.project_memory/active/SPRINT_phase3-eval-system.md`](.project_memory/active/SPRINT_phase3-eval-system.md) | 阶段三任务真源 |
| [`.project_memory/active/SPRINT_phase4-marketplace-biz.md`](.project_memory/active/SPRINT_phase4-marketplace-biz.md) | 阶段四（待启动） |
| [`docs/specs/评估指标与准入标准.md`](docs/specs/评估指标与准入标准.md) | 评分公式与阈值（唯一权威） |
| [`docs/specs/Skill元数据定义与编写规范.md`](docs/specs/Skill元数据定义与编写规范.md) | Skill 包结构与字段 |
| [`docs/guides/Skill编写指南.md`](docs/guides/Skill编写指南.md) | 作者如何准备材料 |

## 许可证与贡献

内部项目。提交前勿将 `.env`、API 密钥或 `data/` 运行时产物纳入版本库。
