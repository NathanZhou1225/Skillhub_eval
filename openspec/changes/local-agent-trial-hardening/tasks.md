## 1. 本地执行失败阻断，不再静默回退 sample_io（D1/D2）

- [x] 1.1 `skillhub_eval/core/execution_source.py`：`RoutingExecutionSource.get_actual_output` 移除「本地失败 → 静默换 sample_io、status 改 ok」的替换逻辑，本地失败时直接返回原始（失败）`ExecResult`（保留其 `status`/`degrade_reason`）。失败时通过 `repo.log_event`（如传入 repo/run_id 上下文）持久化一条含 `case_id`、`degrade_reason`、可得 stderr 摘要的事件。
      验证：`pytest tests/core/test_execution_source.py -q`（新增覆盖「本地失败不再替换为 sample_io」与「失败原因被记录」的用例）
- [x] 1.2 排查并更新所有断言旧「静默回退」行为的既有测试（`tests/core/test_execution_source.py`、`tests/core/test_engine.py` 等），使其反映新的阻断语义。
      验证：`pytest tests/core -q`

## 2. 报告执行归属诚实性（D3，含 Q-27 阻断路径打通）

- [x] 2.1 `skillhub_eval/core/schemas/report.py`：新增 `exec_requested_agent_label`/`exec_requested_model_label` 字段（承载用户全局偏好选择），保留 `exec_agent_id`/`exec_agent_label`/`exec_model_id`/`exec_model_label` 但语义收紧为「仅在真有 case 成功走 `local_agent` 时才非空」。
      验证：`pytest tests/core/test_engine.py -q -k exec_agent`
- [x] 2.2 `skillhub_eval/core/engine.py`：`_exec_agent_report_fields` 去掉「无成功 case 时回退全局偏好伪装成已执行」的分支；改为无成功 case 时 `exec_agent_label`/`exec_model_label=None`，同时把用户选择填入新的 `exec_requested_*` 字段。确认第 1 组的阻断改动后，既有的 per-case `exec_status`/`exec_degrade_reason`（Q-27）确实能在这条路径上触发（此前因静默替换永远走不到）。
      验证：`pytest tests/core/test_engine.py tests/core/test_provider_summary.py -q`
- [x] 2.3 `skillhub_eval/adapters/ui/static/assets/index.js`：报告详情弹窗新增 `renderExecAttributionCard`，在 `exec_agent_label` 为空但 `exec_requested_agent_label` 非空时，展示「已选择 X / Y，但本次未成功执行」提示，不再让用户误以为选的 agent 真的跑了；成功执行时展示「本地执行：X / Y — 本次已成功执行」。[ui-only 数据来源为已收紧的后端字段，非纯视觉改动，需与 2.2 配合]
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`；已用真实 Trae/GLM-5.2 运行验证（见 7.2）

## 3. 整轮阻断的可见反馈（粒度已通过 grill-me 定案：按 case 阻断，只有「预检无 agent」或「全部 case 均本地失败」两种情况才整轮 `failed`）

- [x] 3.1 `skillhub_eval/core/engine.py`：`execution_source=local` 且预检未检测到可用 agent，或一轮内全部 case 的本地执行均失败时，复用既有 `RunStatus.failed` 收尾路径（同安全阻断等既有硬失败复用的 `reason_codes`/`evidence` 字段），新增区分性 `reason_codes`（`LOCAL_EXEC_UNAVAILABLE` / `LOCAL_EXEC_ALL_CASES_FAILED`），不再以 `level_1` 正常完成收尾；单个 case 的本地失败保持第 1/2 组已实现的按 case `incomplete` 语义，不触发整轮 failed。
      验证：`pytest tests/core/test_engine.py -q -k block`
- [x] 3.2 `index.js`：聊天/历史视图中清晰呈现这种整轮 failed（区别于普通失败、待人工复核），展示 `reason_codes` 对应的中文说明（`formatScoreDisplay` 红色阻断提示 + `formatScoreCompact` 历史表格「本地执行阻断」标签）。[ui-only，依赖 3.1 提供的 reason_codes]
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`

## 4. Skill 确认 loading 文案一致性（D4）

- [x] 4.1 `skillhub_eval/adapters/ui/static/assets/index.js`：新增 `pendingPhaseForCurrentStatus`，乐观 loading 文案的选择改为优先依据当前会话状态（`awaiting_skill_id_confirm`）而非输入方式（chip vs 打字），使打字发「确认」或纠正 skill 名时也显示「正在分析 Skill…」。[ui-only]
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`；手动走一遍打字确认流程核对文案
- [x] 4.2 `skillhub_eval/adapters/api/routes/chat.py`：Branch 2（打字纠正 skill_id）补上与确认分支一致的持久化「好的，按 X 开始评估。」+「正在分析 Skill…」agent 消息，保持两条路径体验一致；最终回复文案也改为与确认分支一致的「已开始评估 Skill X。」。
      验证：`pytest tests/adapters/test_conversations_wave5.py tests/adapters/test_chat_wave5_3_actions.py tests/adapters/test_wave5_3_e2e.py tests/adapters/test_wave5_3_1_ux_patch.py tests/integration/test_wave5_chat_shell.py tests/adapters/test_chat_wave5.py tests/core/test_chat_notifications.py -q`（39 passed）

## 5. Exec agent 卡片：Cursor 徽章 + 路径换行（D5）

- [x] 5.1 `index.js`：`testExecAgent` 成功后将该 agent 在 `_execScanCache` 中的 `auth_status` 乐观置为 `"ok"`，重新扫描前保持，使 Test 成功后徽章从「待测试」变「可用」。[ui-only]
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`；手动 Test 一次 Cursor Agent 核对徽章变化
- [x] 5.2 `index.js`：`renderExecAgentCards` 中三个 agent 卡片的已检测路径文本统一加 `break-all`，避免长路径撑出卡片。[ui-only]
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`；手动核对 Codex 卡片不再溢出

## 6. Token 消耗汇总 + 弹窗明细（D6）

- [x] 6.1 `index.js`：`renderUsageSummary` 改为默认展示总计/Provider A（DeepSeek）/Provider B（Gemini）/本地 Agent 四个数字（`_bucketUsageRows` 从既有 `by_stage` 数据在前端分组计算，不改后端 schema），并提供「查看明细」链接，打开新增的 `usage-detail-modal`（独立于 `detail-modal`，可在其之上叠加打开）展示完整分阶段表格。[ui-only]
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`；手动打开一份历史报告核对汇总数字与弹窗明细一致

## 7. 回归验证与文档

- [x] 7.1 聚焦回归：`pytest tests/core tests/adapters tests/execution -q`，确认无既有用例意外回归。结果：518 passed / 6 skipped，仅 1 个已知与本变更无关的历史失败（`test_readiness_payload_contract.py::test_index_html_reads_flat_readiness_and_plan_fields`，在 clean `main` 上复现，属预置缺陷）。另跑 `pytest tests/ -q` 全量确认：700 passed，剩余 9 个失败全部是预置的 sqlite 迁移版本号断言（`PRAGMA user_version == 10` vs 实际 11）与上述同一个 UI contract 用例，均已用 `git stash` 对比 `main` 确认为本变更之前就存在。
- [x] 7.2 用 Trae/GLM-5.2 重新走一次真实评估（`run_id=9f5ff946-ccca-4e26-8ac6-d3a82fc312d1`，真实 `trae-cli` 子进程，非 mock）：`status=failed`，`reason_codes=['LOCAL_EXEC_ALL_CASES_FAILED']`，`exec_agent_label=None`（未伪装成已执行），`exec_requested_agent_label=Trae` / `exec_requested_model_label=GLM-5.2`（如实展示用户选择）。`analytics_events` 中 5 个 case 均记录 `local_agent_failure` 事件，`degrade_reason=run_incomplete`（stderr 为空，即流式输出未读到结束标记）。新失败原因（`run_incomplete`，trae-cli 具体为何流式未完成待排查）记为后续 backlog 项，不在本 change 范围内修复 trae-cli 本身。
- [x] 7.3 更新 `RECORD.md`、`.project_memory/active/SPRINT_phase3-eval-system.md`、`docs/runbooks/local-agent-exec-validation.md`，说明「阻断而非静默降级」的新行为与如何读取失败原因。
- [x] 7.4 `python scripts/check_doc_encoding.py`（涉及中文 Markdown 编辑后必跑）。

## 8. Trae 完成态判定收尾 + 配置诊断透传 + 全 Agent 模型就绪状态 + 三 Agent 复验（Q-29，2026-07-02，含 Codex review 修订）

> 背景与决策见 `design.md` 「Q-29 Follow-up」节（D7–D9）+ 「Q-29 Round 2: Independent Codex Review Findings」节（D10–D12，含一处已确认的真实 bug 修复）。本章节由 Codex 实现（8.1–8.9）；8.10 的真机三 Agent 复验由 Cursor 在 8.1–8.9 落地后执行，不在 Codex 本轮范围内。详细代码见实现计划 `docs/superpowers/plans/2026-07-02-trae-completion-diagnostics.md`（Task 1–9 与本节 8.1–8.10 一一对应），每个子任务的具体代码、测试与验证命令以该计划为准，本表只做任务级追踪。**目标口径（用户 2026-07-02 重申）**：不只是修 Trae，是 Codex / Cursor Agent / Trae 三个本地 CLI 各自选定模型都要能真正跑通本地 skill 评估，而不只是 CLI 能启动。

- [x] 8.1（对应计划 Task 1）确认并全量回归此前已落地但未固化的 stream-json 完成态判定修正（`stream_parser.py` 识别 `is_error`、`runner.is_run_complete()` 要求 `not is_error`、`trae.py` 模型参数改为 `-c model.name=`），运行 `pytest tests/ -q` 全量回归，确认无新增失败（对照 2026-07-01 已知的 9 项既有失败基线）。
- [x] 8.2（对应计划 Task 2）`skillhub_eval/execution/detection.py`：`_home()` 更名为公开的 `home_dir()`（更新 2 处内部调用），新增 `config_dir_path(agent: AgentDef) -> Path | None`。
      验证：`pytest tests/execution/test_detection.py -q`
- [x] 8.3（对应计划 Task 3）新增 `skillhub_eval/execution/diagnostics.py`：`DiagnosisResult` dataclass + `check_writable(dir_path: Path) -> bool`。
      验证：`pytest tests/execution/test_diagnostics.py -q`
- [x] 8.4（对应计划 Task 4，**D10 修复点**）`skillhub_eval/execution/models.py`：新增 `is_model_verified_live(agent, model_id) -> tuple[bool, str]`，内部固定 `discover_models(agent, stored_model=None)` 避免自我掩盖；配套一条**不 mock `discover_models` 本身**、只 mock `_run_probe` 的回归测试，证明 D10 描述的自我掩盖 bug 被真正堵住（而不是被 mock 绕过）。
      验证：`pytest tests/execution/test_models.py -q`
- [x] 8.5（对应计划 Task 5）`skillhub_eval/execution/adapters/trae.py`：新增 `diagnose()` 方法，改用 8.4 的 `is_model_verified_live()`（不再自己直接调用 `discover_models` 做存在性判断）；配置文件名依次尝试 `trae_cli.yaml`/`traecli.yaml`（后者为未证实的防御性兜底，参见 design.md 该节说明，不作为已确认事实引用）；覆盖 `TRAE_CONFIG_DIR_MISSING` / `TRAE_CONFIG_DIR_NOT_WRITABLE` / `TRAE_MODEL_NOT_CONFIGURED` / `TRAE_MODEL_PROBE_UNAVAILABLE` / `TRAE_MODEL_NOT_IN_LIST` 五种 reason_code 及成功态。
      验证：`pytest tests/execution/test_adapter_trae.py -q`
- [x] 8.6（对应计划 Task 6，**含 D11**）`skillhub_eval/adapters/api/routes/exec.py`：`AgentScanItem` 新增 `diagnosis_ok`/`diagnosis_reason_code`/`diagnosis_message`/`diagnosis_hint`（补上此前漏传的 reason_code）+ `selected_model_status`/`selected_model_message`；`scan_agents()` 对已检测到的 agent 调用 `getattr(adapter, "diagnose", None)`（无此方法的 agent 保持 `None`，零行为变化），并对**当前 `exec_agent` 偏好指向的那一个 agent**用 8.4 的 `is_model_verified_live()` 计算通用就绪状态（`ok`/`default`/`stale`/`probe_unavailable`），覆盖 Codex/Cursor Agent/Claude/Antigravity，不依赖各自实现 `diagnose()`。
      验证：`pytest tests/adapters/test_exec_bridge_api.py -q`
- [x] 8.7（对应计划 Task 7，**D12**）`skillhub_eval/adapters/api/routes/exec.py`：`POST /agents/{agent_id}/test` 新增可选 `model` 请求体字段；仅当被测 agent 就是当前 `exec_agent` 偏好时才由前端带上 `exec_model`，其余 agent 卡片保持不传 `model`（沿用原本防止跨 agent 串模型的防线）。
      验证：`pytest tests/adapters/test_exec_bridge_api.py -q`
- [x] 8.8 `[ui-only]` `skillhub_eval/adapters/ui/static/assets/index.js`：`renderExecAgentCards` 在 `diagnosis_ok === false` 时展示红色诊断说明 + 手动排查提示；展示 `selected_model_status` 对应的中文提示；`testExecAgent` 测试当前选中 agent 时带上 `exec_model`（其余 agent 不带）。纯文字，不用 emoji，遵循制式回单视觉约束。
      验证：`node --check skillhub_eval/adapters/ui/static/assets/index.js`
- [x] 8.9（对应计划 Task 9）更新 `docs/runbooks/local-agent-exec-validation.md` 与 `.project_memory/active/SPRINT_phase3-eval-system.md`（Q-29 的 N1/N2 勾选，注明诊断透传已实现、真机根因已定位为本机 Trae 配置/权限问题）；把本节 8.1–8.8 复选框改为 `[x]`（8.10 不要改，那是 Cursor 负责的收尾项）；`python scripts/check_doc_encoding.py`。
- [ ] 8.10 **（Cursor 执行，非 Codex 本轮范围）** 用户按诊断提示修复本机 `trae_cli.yaml`（补 `models:` provider 定义）与 `.trae` 目录权限后，Cursor 依次对 Codex CLI、Cursor Agent、Trae 三个本地 agent 各自真机跑一次 `testskills/exec-fixture-minimal`（或 stock-radar），确认三者均能选定模型并跑出 Pass/Warn/Fail，而非 `run_incomplete`/静默失败；结果记入 RECORD.md。
  - **进展（2026-07-02，Cursor 已做，未全部通过，故整项暂不勾选）**：①**Trae/GLM-5.2 已实测跑通**——直接用 `TraeAdapter.build_args()` 同款参数手动跑 `trae-cli`，拿到真实 `is_error:false` 成功完成事件；`.tmp/check_real_agents.py` 复测一致（`complete=True, final_text='OK'`）。**原诊断提示是错的**：这台机器 `trae_cli.yaml` 根本没有 `models:` 字段，GLM-5.2 是 Trae 内置模型走账号鉴权，不需要这个字段——不需要手改 YAML。②顺带在验证中发现并修复了 `TraeAdapter.diagnose()` 的一处真实假阳性 bug（`TRAE_MODEL_NOT_CONFIGURED` 在模型明明能跑时仍报错，因为判断顺序上先看 `models:` 字段、后看在线探测）：改为先信任 `is_model_verified_live()`，`models:` 字段只在探测不到时作为兜底信号；详见 `design.md` 新增的 D13 节；已按 TDD 补 2 条回归测试 + 修正 2 条依赖"本机没装 trae-cli"这一隐含假设的旧测试；全量回归 728 passed/6 skipped/9 failed（既有基线 +2 新测试）。③**Codex CLI 本次卡在账号额度**（`turn.failed`: "You've hit your usage limit...try again at 2:36 PM"），非 SkillHub 代码问题，`is_run_complete()` 判它为未完成是正确行为，额度恢复后需重测。④**Cursor Agent** smoke test `complete=True` 但极简 prompt 下 `final_text` 为空（`CursorAgentAdapter.parse_stream()` 只从 `text/assistant/content` 事件类型攒文本，未触发不代表失败），仍需跑一次真实 `exec-fixture-minimal` 而非一句话 smoke test 才能算完整验证。剩余：Codex 额度恢复后重测 + Cursor Agent 与 Trae 都补一次真实 fixture 全流程 Pass/Warn/Fail。
  - **进展（2026-07-02 续，真实 `exec-fixture-minimal` 全流程结果，仍未全部收口）**：直接跑 `LocalAgentSource.get_actual_output()`（非 smoke prompt）对 Trae/GLM-5.2 与 Cursor Agent 各测一次，两者都报 `missing_entrypoint_evidence`，但导出原始 stream-json 对比后根因完全不同，详见 `design.md` 新增节「Q-29 exec-fixture-minimal Full Run」：⑤**Cursor Agent 其实真的执行成功**（`shellToolCall` 显示 `python scripts/run.py` `exitCode:0` 输出正确），是 `CursorAgentAdapter.parse_stream()` 的真实 bug——从未识别真实的 `tool_call` 事件形状（只找不存在的扁平 `tool_result`），也从未把终态 `result` 事件里的完整文本并入 `final_text`。**已按 TDD 修复**（D14）：`cursor_agent.py` 新增 `_normalize_tool_call_event()`、`assistant` 事件改读 `message.content[].text`、`final_text` 优先取终态 `result` 文本；`tests/execution/test_adapter_cursor_agent.py` 新增 4 条基于真实事件形状的回归测试，全部通过；全量回归 731 passed/6 skipped/9 failed（既有基线不变，净增 5）。⑥**Trae/GLM-5.2 这次是真的没执行任何东西**（原始 stream 全程无 `run.py`/`SKILL.md`/`Bash` 字样，靠 prompt 里透露的断言直接编答案）——session 初始化事件显示 Bash 白名单只有 `cat/find/grep/head/ls/rg/tail/awk/cut/diff/sort/uniq/wc/git.../cd/date/echo/env/pwd/which`，没有 `python`，即使加了 `bypass_permissions --yolo` 也一样；`trae_cli.yaml` 里没有任何 `tools:` 配置，说明这是 Trae CLI 自身默认策略，不是本机误配置，已超出"读配置文件+探活"的诊断范围（D15，暂开放）。用户已改为直接向 Trae CLI 询问如何解锁完整命令执行权限，等待反馈。剩余：Codex 额度恢复后重测；Trae 等用户从 Trae CLI 侧拿到解锁方式后再复测一次 `exec-fixture-minimal`。
  - **进展（2026-07-02 再续，D14 修复后网页真机复测，交接下一窗口）**：先重启了 `skillhub-eval serve`（此前从中午 12:10 就没重启过，D14 代码尚未生效）。用户在网页上用 Cursor Agent 跑了一次 stock-radar，`prop_happy_01/02/03` 三个 case 仍 `run_incomplete`；查 `analytics_events` 发现 `stderr_excerpt` 都是 `Cannot find module './2240.index.js'`；手动跑 `cursor-agent models` 复现同类崩溃但缺失编号不同（`./2289.index.js`），确认是本机 `cursor-agent` 安装目录（`versions\2026.07.01-41b2de7\`）大批缺失 JS chunk，安装本身损坏，不是 D14 没修好或有新 bug；同一根因也解释了模型下拉框退化成写死 `Default`/`GPT-5`（`discover_models()` 的在线探测子进程崩溃，兜底逻辑本身没问题）。已确认 `cursor-agent update` 是官方自带修复命令，详见 `design.md` D16（暂开放）。**下一窗口开场先确认**：①用户是否已跑 `cursor-agent update` 并重测过；②Trae CLI 那边的权限解锁回复是什么；③Codex 额度是否恢复——三者都确认后再继续排查/收尾 8.10，不要重新排查已经定位清楚的部分。
  - **进展（2026-07-02 收尾，Cursor Agent 确认收口 + D15/D17/D18/D19 全部解决，Trae 确认收口）**：本机核实 `cursor-agent` 版本已从损坏的 `2026.07.01-41b2de7` 变为 `2026.06.29-2ad2186`（说明用户已跑过 `cursor-agent update`），`cursor-agent models` 恢复正常列出完整模型列表；`RUN_LOCAL_AGENT=1 pytest tests/execution/test_e2e_local_exec.py::test_e2e_local_agent_runs_fixture[cursor-agent]` 41s 后 **1 passed**，**Cursor Agent 收口**。随后用户带回 Trae CLI 自诊断的确定性结论（见 `design.md` D17）：`--allowed-tool`/`allowed_tools` 是**叠加**在模型默认 tool 集之上的，不是被其锁死——D15 的只读白名单可以被 `--allowed-tool Bash` 解锁，不是硬编码策略。据此在 `TraeAdapter.build_args()` 无条件加上 `--allowed-tool Bash`（红线题对 Trae 从不走到这里，见 D17 说明，故不影响 redline 刻意降级路径），补 `test_build_args_unlocks_bash_tool` 回归测试。真机复测后发现两个新的真实 bug 并按 TDD 修复：**D18** 模型第一反应是 `cd "<含空格+中文的绝对路径>" && python ...`，命中一个独立于 Trae/SkillHub 的 Windows `cmd.exe` 嵌套引号解析缺陷（直接用 `cmd /c` 复现同样报错），且该 shell 本来就已经在正确 cwd——修复方式是在 `harness_prompt.py` 里明确告诉模型"已经在正确工作目录，直接用相对路径，不要 cd 绝对路径"（跨 agent 通用，非 Trae 专属代码），补 `test_harness_prompt_tells_agent_not_to_cd_to_absolute_path`。**D19** 修完 D18 后 Bash 真的跑通 `python scripts/run.py` 且输出正确，但 `get_actual_output()` 仍报 `missing_entrypoint_evidence`——根因是通用 `stream_parser.parse_stream_events()` 只认扁平 `type:"tool_result"`，Trae 真实事件是 `type:"user",subtype:"tool_result"`（且不回显命令本身，需按 `tool_use_id` 关联 assistant 的 `tool_calls`），和 D14 是同一类 bug；仿照 D14 的模式在 `TraeAdapter.parse_stream()` 里补归一化（`_extract_bash_commands` + `_normalize_tool_result_event`），补 2 条基于真实事件形状的回归测试。三个修复叠加后，`python .tmp/run_fixture_real.py`（真实 `LocalAgentSource.get_actual_output()`，非 smoke prompt）对 Trae/GLM-5.2 和 Cursor Agent **均返回 `status=ok`**，`actual_output={'status': 'success', 'ok': True}` 与 fixture 期望完全一致。全量回归 **742 passed/9 failed**（既有基线不变，净增 4）。**Codex CLI** 本机当前 shell 里 `codex` 不在 PATH（此前诊断是账号额度耗尽），未在本轮验证，留待下个窗口确认额度/安装路径后补测——**8.10 的 Cursor Agent + Trae 两项已收口，Codex 一项待补，故整项仍暂不勾选**。
