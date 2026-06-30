# Design: local-agent-adapter-framework

> 完整设计稿见 `docs/superpowers/specs/2026-06-30-local-agent-adapter-framework-design.md`。
> 实施计划（执行真相）见 `docs/superpowers/plans/2026-06-30-local-agent-adapter-framework.md`（含决策表 G1–G8 与逐步 TDD 代码）。
> 本文件仅做模块→路径映射与接口锚点。

## 决策表（grill-me 定稿 2026-06-30）

| # | 决策 |
|---|------|
| G1 | trae 走 **stream-json**（`trae-cli -p --output-format stream-json --include-partial-messages --yolo`），丢弃自制 ACP 传输 |
| G2 | 保留 transport 包 + 按 `stream_format` 分派；当前只实现 stream-json，`acp-json-rpc` 为未来扩展点（`NotImplementedError`） |
| G3 | 检测数据驱动：registry 声明候选安装目录（含版本号通配），统一 `PATH→登记目录→npm→where` 解析；新增 CLI 只加数据 |
| G4 | 模型发现通用 `model_probe`：trae=`trae-cli models`（live）；cursor/codex/claude=fallback+手输；自定义保留 |
| G5 | 三态认证灯：二进制+config 目录→可用；有二进制无 config→未登录；cursor→待测试；真认证点 Test/首跑确认 |
| G6 | trae 修正：`primary_bin=trae-cli`（别名 `traecli/trae-agent/ta`）+ stream-json build_args + 复用 claude 式解析 |
| G7 | 验收：codex+trae 先真跑极小 fixture；cursor 待重装修好后补验；抓一次 trae 真实 stream-json 锁定解析器 |
| G8 | judge/双模型/聚合/R1–R8/`ExecResult` 字段不动；现有 stream-json 行为不回归 |

## 架构（进程内）

```
core/engine.py（不变）
  └─ ExecutionSource 取 actual_output（不变）
        └─ LocalAgentSource（编排）
              ├─ agent_registry.AgentDef        数据驱动登记表（含 install_dir_globs / model_probe）
              ├─ detection.resolve_agent_binary  PATH→install_dir_globs→npm→where（数据驱动）
              ├─ detection.detect_agent          + config-dir → DetectionResult(auth_state) + TTL 缓存
              ├─ models.discover_models          通用 model_probe（live）+ fallback + custom 保留
              └─ transport.base.run_via_transport 按 stream_format 分派
                    ├─ stream-json → 现有 LocalAgentRunner（claude/codex/cursor/trae）
                    └─ acp-json-rpc → NotImplementedError（扩展点）
                          ↓ 产出 RunOutcome/ParsedStream
                    └─ collect → ExecResult（结构不变）
```

## 模块 → 路径映射

| 模块 | 路径 | 接口锚点 |
|---|---|---|
| 登记表 | `skillhub_eval/execution/agent_registry.py` | `AgentDef` 增 `stream_format`/`config_dirs`/`install_dir_globs`/`version_args`/`model_probe`/`prompt_via_stdin`；修 trae 登记 |
| 检测 | `skillhub_eval/execution/detection.py` | `resolve_agent_binary(def) -> str|None`；`detect_agent(def, *, force) -> DetectionResult(detected, bin_path, auth_state, detect_hint)`；`clear_detection_cache()` |
| 可安装 | `skillhub_eval/execution/install_hints.py` | `get_install_hint(agent_id) -> {install_command, docs_url, platform_note} | None` |
| 模型发现 | `skillhub_eval/execution/models.py` | `discover_models(def, *, stored_model) -> ModelDiscovery(models[], models_source)`；`_run_probe(def)` 跑 `<bin> *model_probe` |
| 传输分派 | `skillhub_eval/execution/transport/base.py` | `run_via_transport(adapter, def, prompt, *, cwd, timeout_s, hardened, runner) -> RunOutcome` |
| trae adapter | `skillhub_eval/execution/adapters/trae.py` | stream-json build_args；`detect`/`resolved_bin` 委托 `resolve_agent_binary` |
| 执行入口 | `skillhub_eval/execution/local_agent_source.py` | `_execute_once` 改走 `run_via_transport` |
| API | `skillhub_eval/adapters/api/routes/exec.py` | `GET /agents/scan` 增 `auth_status`/`models[]`/`models_source`/`install_*` |
| UI [ui-only] | `skillhub_eval/adapters/ui/static/assets/index.js` | 三态徽章 + 安装卡 + 模型下拉 |
| settings | `skillhub_eval/settings.py` | `model_discovery_timeout_s` / `agent_detect_cache_ttl_s` |

## 实测依据（本机已验证）

- `trae-cli` 在 `%LOCALAPPDATA%\trae-cli\bin`（不在 PATH），别名 `trae-cli/traecli/trae-agent/ta`，支持 `--print --output-format stream-json --include-partial-messages --yolo --permission-mode bypass_permissions`；`trae-cli models` 秒回模型清单。
- codex 在 `%LOCALAPPDATA%\OpenAI\Codex\bin\<ver>\codex.exe`（现有 `find_cli_binary` 已命中；改造后由 `install_dir_globs="OpenAI/Codex/bin/*"` 数据化）。
- cursor-agent 启动器在 PATH，但其 `.ps1` 的版本目录正则与实际 `versions\` 命名不匹配 → 当前本机不可用（外部工具问题，需重装；G7 延后其真机验收）。

## 唯一需真机校准项

trae 实际 stream-json 事件字段是否被现有 `parse_stream_events` 正确识别、prompt 走 stdin 还是位置参——在 G7 真跑时确认并补一条录制样本回归。其余全部可离线测。

## Visual direction（[ui-only]）

沿用现有执行模式抽屉暗色风格（Tailwind CDN），不引入新设计语言。三态徽章配色：`ok` 绿（emerald-900/200）、`missing` 琥珀（amber-900/200）、`unknown` 灰（gray-700/300）、未安装 深灰。安装卡用等宽 `code` + 「复制」「官方文档」内联链接。无新增页面或布局结构。
