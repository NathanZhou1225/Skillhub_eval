---
name: filesystem-mcp-server
display_name: 文件系统 MCP 服务
version: 0.6.3
owner: skillhub-testskills
category: 工程效率/本地工具
description: >-
  指导 Agent 通过官方 Filesystem MCP Server（@modelcontextprotocol/server-filesystem）
  在白名单目录内完成读/写/列目录/搜索等文件系统操作。适用于需要受控本地文件访问、
  并且客户端已配置 MCP filesystem 服务或需要按其工具契约调用的场景。
execution_mode: sample_only
risk_level: medium
permissions:
  data_scope: allowed_directories_only
  requires_user_identity: false
  has_side_effects: true
input_schema:
  type: object
  required:
    - intent
  properties:
    intent:
      type: string
      description: 用户要对本地文件做什么（读、列目录、搜索、写/改等）。
    path:
      type: string
      description: 目标路径；必须落在已允许（allowed）目录内。
    content:
      type: string
      description: 写入或替换时的文本内容（仅写类操作需要）。
returns_schema:
  type: object
  required:
    - status
    - summary
  properties:
    status:
      type: string
      enum: [ok, denied, not_found, invalid_input, error]
    summary:
      type: string
      description: 面向用户的简短结果说明。
    tool_used:
      type: string
      description: 实际选用的 MCP 工具名（如 read_text_file）。
    details:
      type: object
      description: 工具返回的结构化摘要（可选）。
negative_prompts:
  - 不得访问未列入 allowed directories / roots 的路径。
  - 不得通过 ..、符号链接逃逸、绝对路径伪造等方式绕过目录沙箱。
  - 不得在未得到用户明确确认时执行破坏性写操作（覆盖写、批量删除语义的移动/覆盖）。
  - 不得把密钥、令牌、私钥或个人隐私文件内容复制到对话外或不相关目录。
  - 不得臆造「已完成写入」；写类操作必须以工具真实返回为准。
error_handling:
  outside_allowed: 返回 denied，说明路径不在允许目录内，并提示 list_allowed_directories。
  not_found: 返回 not_found，不得编造文件内容。
  invalid_input: 返回 invalid_input（例如同时指定 head 与 tail）。
  tool_error: 返回 error，附上工具错误信息摘要，不得静默忽略。
---

# Filesystem MCP Server

本 Skill 对应 npm 包 [`@modelcontextprotocol/server-filesystem`](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem)
（仓库内源码版本见 `package.json`）。它不是纯指令型工作流 Skill，而是 **MCP 文件系统服务端** 的使用与安全约束说明，供评估与本地联调时统一契约。

## 何时使用

- 用户需要在 **已授权目录** 内读文件、列目录、搜索、查看元数据。
- 用户需要受控写入 / 编辑 / 移动，且愿意接受沙箱与确认规则。
- 客户端（Cursor / Claude Desktop / VS Code 等）已配置本 MCP server，或评估场景要求 Agent 按下列工具契约作答。

## 目录访问控制（必须遵守）

所有操作只能落在 **allowed directories** 内，来源二选一或并存：

1. **启动参数**：`mcp-server-filesystem <dir1> [dir2 ...]`
2. **MCP Roots**（推荐）：客户端通过 `roots/list` / `roots/list_changed` 下发根目录；若客户端提供 roots，将 **完全替换** 服务端当前允许目录。

若既无 CLI 目录、客户端又不提供有效 roots，服务无法安全工作——应拒绝操作并说明原因。
可用工具 `list_allowed_directories` 核对当前白名单。

## 工具选型

| 意图 | 优先工具 | 只读? | 备注 |
|------|----------|-------|------|
| 读文本 | `read_text_file` | 是 | 可选 `head` / `tail`；二者不可同时用 |
| 读媒体/二进制 | `read_media_file` | 是 | 返回带 MIME 的内容块 |
| 批量读 | `read_multiple_files` | 是 | 单个失败不阻断其余 |
| 列目录 | `list_directory` / `list_directory_with_sizes` | 是 | 后者可排序并含体积汇总 |
| 目录树 | `directory_tree` | 是 | 支持 `excludePatterns` |
| 搜索 | `search_files` | 是 | glob；可 exclude |
| 元数据 | `get_file_info` | 是 | size / 时间 / 权限等 |
| 白名单 | `list_allowed_directories` | 是 | 操作前不确定范围时先调用 |
| 建目录 | `create_directory` | 否 | 幂等；已存在则成功 |
| 整文件写 | `write_file` | 否 | **破坏性**；覆盖已有文件 |
| 片段编辑 | `edit_file` | 否 | 建议先 `dryRun: true` 预览 diff |
| 移动/重命名 | `move_file` | 否 | 目标已存在则失败 |

读类操作为默认；写 / 编辑 / 移动前应向用户确认目标路径与影响范围。

## 执行步骤

1. 澄清用户意图（读 / 搜 / 写 / 改 / 移）与目标路径。
2. 若不确定沙箱范围，先调用 `list_allowed_directories`。
3. 校验路径语义：拒绝明显逃逸（`..` 跳出白名单、访问白名单外绝对路径）。
4. 选择上表中最小权限工具；写操作优先 `edit_file` + `dryRun`，再正式应用。
5. 根据工具真实结果整理输出：`status` + `summary` + `tool_used`；失败时映射到 `error_handling` 策略。
6. 不要在对话中粘贴无关的大文件全文或疑似密钥内容；必要时只给摘要或行号范围。

## 本地启动参考（非评估必需）

NPX 示例（将目录换成实际白名单路径）：

```bash
npx -y @modelcontextprotocol/server-filesystem /path/to/allowed-dir
```

Windows 上客户端配置常用 `cmd /c npx ...`。Docker 场景见包内 `README.md`（目录挂载至 `/projects`）。

本文档目录含 TypeScript 源码与 Vitest；**SkillHub 评估默认按 `execution_mode: sample_only` 对待**——以本 `SKILL.md` 契约与（补齐后的）`eval_cases` / `sample_io` 为准，不要求评估引擎直接拉起 Node MCP 进程。

## 评估友好边界

- Happy：在允许目录内读文件、列目录、搜索并返回合规摘要。
- Edge：`head`+`tail` 同时指定、目标不存在、路径在白名单外 → 明确拒绝或 `invalid_input` / `denied` / `not_found`。
- 拒绝：用户要求读取白名单外路径、或未确认即覆盖写关键配置 → 拒绝并说明原因。
