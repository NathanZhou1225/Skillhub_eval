# Tasks: local-agent-adapter-framework

> 执行真相以实施计划为准：`docs/superpowers/plans/2026-06-30-local-agent-adapter-framework.md`（每步含 TDD 红→绿与精确代码）。本文件为 OpenSpec 记录，task 编号与计划 Phase/Task 对应。
> 执行方式：subagent-driven-development，每项一个 subagent，TDD（先红后绿）。
> grill-me 已完成（2026-06-30）：ACP→stream-json；检测数据驱动；通用 model_probe。
> 验证基线：现有全量 `pytest` 不回归；新模块各自单测先红后绿。

## Phase 0 — 基础设施

- [ ] 0.1 模型发现/检测缓存超时设置（plan Task 0.1）
  - Files: `skillhub_eval/settings.py`、`.env.example`、`tests/test_settings_exec_framework.py`
  - Verify: `pytest tests/test_settings_exec_framework.py -v`

- [ ] 0.2 扩展 `AgentDef` 数据字段 + 修 trae 登记（stream-json + 名字 + install_dir_globs + model_probe）（plan Task 0.2）
  - Files: `skillhub_eval/execution/agent_registry.py`、`tests/execution/test_agent_registry.py`
  - Verify: `pytest tests/execution/test_agent_registry.py -v`

## Phase 1 — 数据驱动检测 + 三态 + 缓存

- [ ] 1.1 `install_hints` 数据模块（D4）（plan Task 1.1）
  - Files: `skillhub_eval/execution/install_hints.py`、`tests/execution/test_install_hints.py`
  - Verify: `pytest tests/execution/test_install_hints.py -v`

- [ ] 1.2 `detection`：数据驱动解析（PATH→install_dir_globs→npm→where）+ 三态 + TTL 缓存（plan Task 1.2）
  - Files: `skillhub_eval/execution/detection.py`、`tests/execution/test_detection.py`
  - Verify: `pytest tests/execution/test_detection.py -v`

- [ ] 1.3 `preferences._is_agent_detected` 改走 detection（plan Task 1.4）
  - Files: `skillhub_eval/execution/preferences.py`、`tests/execution/test_preferences_detection.py`
  - Verify: `pytest tests/execution/test_preferences_detection.py tests/execution/test_agent_registry.py -v`

## Phase 2 — 通用 model_probe 混合发现

- [ ] 2.1 `models.discover_models`（通用 model_probe + fallback + custom 保留）（plan Task 2.1）
  - Files: `skillhub_eval/execution/models.py`、`tests/execution/test_models.py`
  - Verify: `pytest tests/execution/test_models.py -v`

## Phase 3 — trae 修成 stream-json adapter（替代原 ACP 阶段）

- [ ] 3.1 重写 trae adapter（bin 名 `trae-cli` + stream-json build_args + 复用解析；detect 走 resolve_agent_binary）（plan Task 3.1）
  - Files: `skillhub_eval/execution/adapters/trae.py`、`tests/execution/test_adapter_trae.py`
  - Verify: `pytest tests/execution/test_adapter_trae.py -v`

## Phase 4 — 传输 seam + 执行入口接线

- [ ] 4.1 `transport` 分派包（stream-json → 现有 runner；acp-json-rpc → NotImplementedError 扩展点）（plan Task 4.1）
  - Files: `skillhub_eval/execution/transport/__init__.py`、`transport/base.py`、`tests/execution/test_transport_dispatch.py`
  - Verify: `pytest tests/execution/test_transport_dispatch.py -v`

- [ ] 4.2 `LocalAgentSource._execute_once` 走 `run_via_transport`（trae 经现有 stream-json 真跑）（plan Task 4.2）
  - Files: `skillhub_eval/execution/local_agent_source.py`、`tests/execution/test_local_agent_source_trae.py`
  - Verify: `pytest tests/execution -v`（含回归）

## Phase 5 — API scan 充实

- [ ] 5.1 `GET /api/exec/agents/scan` 返回真三态 + 安装指引 + 发现模型（plan Task 5.1）
  - Files: `skillhub_eval/adapters/api/routes/exec.py`、`tests/adapters/test_exec_bridge_api.py`
  - Verify: `pytest tests/adapters/test_exec_bridge_api.py -v`

## Phase 6 — UI 接线 [ui-only]

- [ ] 6.1 三态徽章 + 模型来源 + 安装指引卡（plan Task 6.1）
  - Files: `skillhub_eval/adapters/ui/static/assets/index.js`
  - Verify: `node --check skillhub_eval/adapters/ui/static/assets/index.js` + 手动 UI 冒烟

## Phase 7 — fixture、文档、验收（放最后）

- [ ] 7.1 真机 E2E（默认 skip）codex+trae，并抓 trae 真实 stream-json 校准解析器（plan Task 7.1）
  - Files: `tests/execution/test_local_exec_e2e.py`、`tests/execution/test_adapter_trae.py`
  - Verify: `pytest tests/execution/test_local_exec_e2e.py -v`（默认 SKIPPED）

- [ ] 7.2 文档登记：RECORD Q-26 + SPRINT W8.7 勾选（plan Task 7.2）
  - Files: `RECORD.md`（section patch only）、`.project_memory/active/SPRINT_phase3-eval-system.md`
  - Verify: `python scripts/check_doc_encoding.py`

- [ ] 7.3 全量回归 + 验收（codex+trae 真跑；cursor 待重装补验）（plan Task 7.3）
  - Files: 必要修补
  - Verify: `pytest -q` 全绿 + `node --check ...` + 真机 codex/trae 冒烟
