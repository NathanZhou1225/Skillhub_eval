# Tasks: local-agent-exec-bridge

> 执行方式：subagent-driven-development，每项一个 subagent，TDD（先红后绿）。
> 验证基线：现有 `pytest`（524+ tests），fixture 三件套不回归。
> 实现顺序：W8.1 claude → codex → cursor-agent；其余按 wave 顺序。
> grill 修订：回传走流解析（无 MCP server）；judge 双模式；新增 entrypoint/execution_source 元数据 + 证据校验；红线加固/降级。

## W8.2-pre 接缝与契约骨架（先立抽象）

- [x] 1. `ExecutionSource` Port + `ExecResult`/`RunOutcome`/`ParsedStream` 数据类
  - Files: `skillhub_eval/core/ports.py`、`skillhub_eval/core/schemas/report.py`
  - 字段：`actual_output`、`source`(`local_agent`/`sample_io`)、`confidence`、`transcript_ref`、`usage`、`status`(`ok`/`incomplete`)、`level`(`level_1`/`level_2`)
  - Verify: `pytest tests/core/test_ports.py -v`

- [x] 2. `SampleIoSource`：包现有 `load_sample_io`，实现 `ExecutionSource`
  - Files: `skillhub_eval/core/sample_io_source.py`、`tests/core/test_sample_io_source.py`
  - 行为须与现有 `load_sample_io` 等价（含 None→skip 语义）；source=sample_io、level=level_1
  - Verify: `pytest tests/core/test_sample_io_source.py -v`

- [x] 3. 引擎接缝改造：`case_executing` 三处（engine.py:313/330/1010）经 `ExecutionSource`
  - Files: `skillhub_eval/core/engine.py`、`skillhub_eval/settings.py`（增 `EXEC_SOURCE` 默认 `sample_io`）
  - 默认 `sample_io` → 行为与改造前完全一致
  - Verify: `pytest tests/ -q`（全量回归，确认 0 行为变化）

## W8.1 执行传输层（抄 open-design，流解析，claude→codex→cursor-agent）

- [x] 4. `Adapter` 协议 + `LocalAgentRunner` 骨架（detect/spawn/完成判定）
  - Files: `skillhub_eval/execution/runner.py`、`tests/execution/test_runner.py`
  - 同机 spawn（原生 Windows，prompt 经 stdin）；完成判定两层：子进程 exit + 流 `{type:"result"}`
  - Verify: `pytest tests/execution/test_runner.py -v`（fake 子进程 + fake 流 fixture）

- [x] 5. `StreamParser` + `ArtifactCollector`（最终文本 + tool_result + cwd 产物 + 收尾 fenced JSON）
  - Files: `skillhub_eval/execution/stream_parser.py`、`tests/execution/test_stream_parser.py`
  - 用 open-design 录制的流样本驱动；收尾 JSON 解析失败 → 合成兜底
  - Verify: `pytest tests/execution/test_stream_parser.py -v`

- [x] 6. claude adapter（`-p --input-format stream-json --output-format stream-json --verbose --permission-mode bypassPermissions`）+ claude-stream-json 解析
  - Files: `skillhub_eval/execution/adapters/claude.py`、`tests/execution/test_adapter_claude.py`
  - Verify: `pytest tests/execution/test_adapter_claude.py -v`

- [x] 7. codex adapter（`exec --json --sandbox workspace-write ...`）+ codex 事件流解析
  - Files: `skillhub_eval/execution/adapters/codex.py`、`tests/execution/test_adapter_codex.py`
  - Verify: `pytest tests/execution/test_adapter_codex.py -v`

- [x] 8. cursor-agent adapter（`--print --output-format stream-json ...`）+ 私有 eventParser（去重）
  - Files: `skillhub_eval/execution/adapters/cursor_agent.py`、`tests/execution/test_adapter_cursor_agent.py`
  - 参照 open-design `emitCursorTextDelta` 文本去重逻辑
  - Verify: `pytest tests/execution/test_adapter_cursor_agent.py -v`

## W8.2 元数据 + 证据 + LocalAgentSource

- [x] 9. 元数据新增 `entrypoint`/`execution_source`：规范 + ingest 解析 + 校验
  - Files: `docs/specs/Skill元数据定义与编写规范.md`、`skillhub_eval/core/ingest.py`、`tests/core/test_ingest_entrypoint.py`
  - has_scripts 必填 `entrypoint`；缺失 → 校验报错
  - Verify: `pytest tests/core/test_ingest_entrypoint.py -v`

- [x] 10. `EvidenceVerifier`：tool_result 是否跑过声明的 entrypoint
  - Files: `skillhub_eval/execution/evidence.py`、`tests/execution/test_evidence.py`
  - Verify: `pytest tests/execution/test_evidence.py -v`

- [x] 11. `PerRunWorkspace`：staging→per-run clone / 清理 / 留证
  - Files: `skillhub_eval/execution/workspace.py`、`tests/execution/test_workspace.py`
  - Verify: `pytest tests/execution/test_workspace.py -v`（clone 隔离 + 并行无冲突 + 清理）

- [x] 12. `harness_prompt`：强制用 skill + 调 entrypoint + 收尾 JSON
  - Files: `skillhub_eval/execution/harness_prompt.py`、`tests/execution/test_harness_prompt.py`
  - Verify: `pytest tests/execution/test_harness_prompt.py -v`

- [x] 13. `LocalAgentSource`：编排 runner + workspace + 证据校验，产出 `ExecResult`
  - Files: `skillhub_eval/execution/local_agent_source.py`、`tests/execution/test_local_agent_source.py`
  - `Semaphore` 有界并发（`EXEC_CONCURRENCY` 默认 2）+ 限流退避 + per-risk 超时
  - Verify: `pytest tests/execution/test_local_agent_source.py -v`（fake adapter 驱动）

## W8.2 judge 双模式

- [x] 14. `_build_case_prompt` 加执行/样例双模式（按 `ExecResult.source`）
  - Files: `skillhub_eval/core/engine.py`、`tests/core/test_judge_dual_mode.py`
  - 执行模式 rubric 评执行结果；样例模式保持现有 doc-centric（含红线 doc 口径）
  - Verify: `pytest tests/core/test_judge_dual_mode.py -v`

## W8.3 来源路由 + 降级 + 信任 v1 + level

- [x] 15. 执行来源路由（per-skill `execution_source` > env）+ 降级矩阵
  - Files: `skillhub_eval/core/execution_source.py`、`tests/core/test_execution_source_routing.py`
  - 无 agent/未登录→整轮 sample_io；单题失败/无证据→回退 sample_io，无样例→incomplete
  - Verify: `pytest tests/core/test_execution_source_routing.py -v`

- [x] 16. `level_achieved` 改看执行证据 + 信任 v1 接线
  - Files: `skillhub_eval/core/engine.py`（废弃 :296 `has_scripts AND self.sandbox`；level_2=有证据真跑；pass→PASS 标 `spot_check_eligible`）、`tests/core/test_level_and_trust.py`
  - Verify: `pytest tests/core/test_level_and_trust.py -v`

- [x] 17. history 可筛：`spot_check_eligible` / `source` 持久化 + 筛选
  - Files: `skillhub_eval/persistence/sqlite.py`、`skillhub_eval/persistence/repository.py`、`tests/persistence/test_spotcheck_filter.py`
  - Verify: `pytest tests/persistence/test_spotcheck_filter.py -v`

## W8.5 安全 + 红线加固

- [x] 18. 执行前同意 + 权限目录约束 + 与 Security Gate 打通
  - Files: `skillhub_eval/execution/local_agent_source.py`、`skillhub_eval/core/engine.py`、`tests/execution/test_exec_consent_and_gate.py`
  - blocked bundle 不 spawn；未同意不 spawn；权限仅限 per-run 目录
  - Verify: `pytest tests/execution/test_exec_consent_and_gate.py -v`

- [x] 19. `HardenedProfile`：codex 红线加固档；claude/cursor 红线降级 doc-centric
  - Files: `skillhub_eval/execution/profile.py`、`skillhub_eval/execution/local_agent_source.py`、`tests/execution/test_hardened_profile.py`
  - codex 红线：禁外联 + 限 fs；claude/cursor 红线：降级 + 报告标原因
  - Verify: `pytest tests/execution/test_hardened_profile.py -v`

- [x] 20. 回传过 output sanitizer（复用 `run_output_sanitizer`）
  - Files: `skillhub_eval/execution/local_agent_source.py`、`tests/execution/test_exec_sanitizer.py`
  - Verify: `pytest tests/execution/test_exec_sanitizer.py -v`

## W8.6 端到端验收

- [x] 21. 可执行 fixture skill（含 `entrypoint`，写中间文件 + 结构化产出）
  - Files: `testskills/exec-fixture-minimal/`（SKILL.md + frontmatter `entrypoint` + 脚本 + eval_cases + returns_schema）
  - Verify: `pytest tests/ -q`（fixture 被 ingest/校验接受）

- [x] 22. 端到端：三 agent 各跑通同一 fixture 一次 + runbook
  - Files: `docs/runbooks/local-agent-exec-validation.md`、`tests/execution/test_e2e_local_exec.py`（标 `@pytest.mark.requires_local_agent`，默认 skip）
  - Verify: 本地手动 `pytest -m requires_local_agent -v`（三 agent）+ `pytest tests/ -q`（全量不回归）

## 收尾

- [x] 23. 文档对齐：全景说明 §10 执行层现状、RECORD 流水、Sprint W8 勾选
  - Files: `docs/guides/Skill评估系统全景说明.md`、`RECORD.md`、`.project_memory/active/SPRINT_phase3-eval-system.md`
  - Verify: 人工 review + `pytest tests/ -q`
