# Tasks: ui-local-exec-bridge

> 线框：`docs/superpowers/specs/2026-06-17-ui-local-exec-bridge-wireframes.md`  
> 依赖：`local-agent-exec-bridge` 后端已落地。  
> **grill-me 已闭合**（2026-06-17）→ 可 implement。

## 1. Exec Bridge API 基础

- [x] 1.1 新增 `skillhub_eval/execution/preferences.py`（**sqlite 全局单行** get/set；默认 `exec_source=local`；consent 持久化；`ready` 计算）
  - Files: `execution/preferences.py`, `persistence/sqlite.py`（DB v10 `exec_preferences`）
  - Verify: `pytest tests/execution/test_preferences.py -v`

- [x] 1.2 新增 `skillhub_eval/adapters/api/routes/exec.py` 并注册 router：`scan` / `preferences` GET+PUT / `consent` POST
  - Files: `adapters/api/routes/exec.py`, `adapters/api/app.py`（或主 router 挂载点）
  - Verify: `pytest tests/adapters/test_exec_bridge_api.py::test_scan_and_preferences -v`

- [x] 1.3 实现 `POST /api/exec/agents/{id}/test`（5s smoke，`LocalAgentRunner`）
  - Files: `routes/exec.py`, 复用 `execution/runner.py`
  - Verify: `pytest tests/adapters/test_exec_bridge_api.py::test_agent_test -v`

- [x] 1.4 `RoutingExecutionSource` / `settings` 读 preferences 优先于 env
  - Files: `core/execution_source.py`, `execution/local_agent_source.py`, `settings.py`（fallback 不变）
  - Verify: `pytest tests/core/test_execution_source_routing.py tests/execution/test_preferences_engine.py -v`

## 2. Exec Bridge UI — 全局与设置

- [x] 2.1 [ui-only] C01 ExecBridgeIndicator + C02 Drawer 骨架（420px overlay + 模式 RadioGroup）
  - Files: `adapters/ui/static/index.html`
  - Verify: 手工：打开 `/ui/index.html` 见 pill + 抽屉

- [x] 2.2 [ui-only] C04–C07：Scan 列表 Radio Card + Rescan + Consent + PUT 即时保存
  - Files: `index.html`（`fetchExecScan`, `fetchExecPreferences`, `putExecPreferences`）
  - Verify: 手工：Rescan 显示三 agent；切换模式/agent 无刷新保存

- [x] 2.3 [ui-only] C06 Agent `[Test]` 接 `POST .../test` 内联结果
  - Files: `index.html`
  - Verify: 手工：对已安装 CLI 点 Test 见 pass/fail 文案

- [x] 2.4 [ui-only] C16 Banner：`local && !ready` **每次开页显示**；「知道了」仅收起当次；「改用样例」或就绪变绿后不再显示
  - Files: `index.html`
  - Verify: 手工：local 未就绪刷新见横幅；点知道了刷新仍见；改 sample 或 consent+CLI 就绪后消失

- [x] 2.5 [ui-only] 样例模式顶栏灰字轻提示（G9）；作者+专家均可编辑 Drawer（G8）
  - Files: `index.html`
  - Verify: 手工：sample_io 见灰字；专家角色可改设置

## 3. Exec Bridge UI — 对话与报告

- [x] 3.1 [ui-only] C09 评估 Banner + `STAGE_ZH` local/sample_io 双轨文案
  - Files: `index.html`
  - Verify: 手工：mock 或真实 run 见「本地 Agent 真跑中」vs「校验样例输出」

- [x] 3.2 [ui-only] C11 BridgePromptCard：**纯前端**；local 未就绪插入 + **8s poll 同卡自动变绿** + **自动续跑**正式评估
  - Files: `index.html`（共享 `_execScanCache`）
  - Verify: 手工：local 未 consent 见卡；勾选 consent 后 ≤10s 卡变绿并自动开评

- [x] 3.3 [ui-only] **正式评估门禁**（G4）：local 未就绪不启动 formal eval
  - Files: `index.html`（assessment/chat 触发点）
  - Verify: 手工：local !ready 点评估只见 BridgePromptCard

- [x] 3.4 [ui-only] **Skill local vs sample 冲突 Modal**（G5/G10）
  - Files: `index.html`
  - Verify: 手工：bundle execution_source=local + prefs sample_io → 居中 Modal 两按钮

- [x] 3.5 [ui-only] C10 ExecOutcomeStrip + C15 历史筛选 chips
  - Files: `index.html`
  - Verify: 手工：报告见 LOCAL/SAMPLE 徽章；历史 Tab 筛选 local_agent

## 4. 验收与文档

- [x] 4.1 网页 E2E runbook 更新：`docs/runbooks/local-agent-exec-validation.md` 增 UI 路径（零 .env）
  - Files: runbook
  - Verify: 人工按 runbook 跑 `exec-fixture-minimal`

- [x] 4.2 全量回归
  - Verify: `pytest tests/ -q` → **595 passed**（已恢复 `testskills/exec-fixture-minimal/`）

- [x] 4.3 [ui-only] 更新 `meta skillhub-ui-build` tag（如 `w8-exec-bridge-ui`）
  - Files: `index.html`
  - Verify: 页面 title/meta 可见新版本

## 5. 收尾（archive 前）

- [x] 5.1 grill-me 闭合 Open Questions（`design.md`）并修订 delta specs
- [x] 5.2 RECORD + Sprint W8 UI 勾选 + 全景说明 §10 UI 一句
- [x] 5.3 `/opsx:archive` 本 change + `local-agent-exec-bridge`（网页验收通过后）

## Out of scope（v1.5 / v2）

- C12–C13 per-case 执行摘要（v1.5）
- C14 Live Terminal SSE（v2）
