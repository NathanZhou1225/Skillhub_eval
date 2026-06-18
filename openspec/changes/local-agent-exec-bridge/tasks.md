# Tasks: local-agent-exec-bridge

> 鎵ц鏂瑰紡锛歴ubagent-driven-development锛屾瘡椤逛竴涓?subagent锛孴DD锛堝厛绾㈠悗缁匡級銆?
> 楠岃瘉鍩虹嚎锛氱幇鏈?`pytest`锛?24 tests锛? fixture 涓変欢濂椾笉鍥炲綊銆?
> 瀹炵幇椤哄簭锛歐8.1 claude 鈫?codex 鈫?cursor-agent锛涘叾浣欐寜 wave 椤哄簭銆?
> grill 淇锛氬洖浼犺蛋娴佽В鏋愶紙鏃?MCP server锛夛紱judge 鍙屾ā寮忥紱鏂板 entrypoint/execution_source 鍏冩暟鎹?+ 璇佹嵁鏍￠獙锛涚孩绾垮姞鍥?闄嶇骇銆?

## W8.2-pre 鎺ョ紳涓庡绾﹂鏋讹紙鍏堢珛鎶借薄锛?

- [x] 1. `ExecutionSource` Port + `ExecResult`/`RunOutcome`/`ParsedStream` 鏁版嵁绫?
  - Files: `skillhub_eval/core/ports.py`銆乣skillhub_eval/core/schemas/report.py`
  - 瀛楁锛歚actual_output`銆乣source`(`local_agent`/`sample_io`)銆乣confidence`銆乣transcript_ref`銆乣usage`銆乣status`(`ok`/`incomplete`)銆乣level`(`level_1`/`level_2`)
  - Verify: `pytest tests/core/test_ports.py -v`

- [x] 2. `SampleIoSource`锛氬寘鐜版湁 `load_sample_io`锛屽疄鐜?`ExecutionSource`
  - Files: `skillhub_eval/core/sample_io_source.py`銆乣tests/core/test_sample_io_source.py`
  - 琛屼负椤讳笌鐜版湁 `load_sample_io` 绛変环锛堝惈 None鈫抯kip 璇箟锛夛紱source=sample_io銆乴evel=level_1
  - Verify: `pytest tests/core/test_sample_io_source.py -v`

- [x] 3. 寮曟搸鎺ョ紳鏀归€狅細`case_executing` 涓夊锛坋ngine.py:313/330/1010锛夌粡 `ExecutionSource`
  - Files: `skillhub_eval/core/engine.py`銆乣skillhub_eval/settings.py`锛堝 `EXEC_SOURCE` 榛樿 `sample_io`锛?
  - 榛樿 `sample_io` 鈫?琛屼负涓庢敼閫犲墠瀹屽叏涓€鑷?
  - Verify: `pytest tests/ -q`锛堝叏閲忓洖褰掞紝纭 0 琛屼负鍙樺寲锛?

## W8.1 鎵ц浼犺緭灞傦紙鎶?open-design锛屾祦瑙ｆ瀽锛宑laude鈫抍odex鈫抍ursor-agent锛?

- [x] 4. `Adapter` 鍗忚 + `LocalAgentRunner` 楠ㄦ灦锛坉etect/spawn/瀹屾垚鍒ゅ畾锛?
  - Files: `skillhub_eval/execution/runner.py`銆乣tests/execution/test_runner.py`
  - 鍚屾満 spawn锛堝師鐢?Windows锛宲rompt 缁?stdin锛夛紱瀹屾垚鍒ゅ畾涓ゅ眰锛氬瓙杩涚▼ exit + 娴?`{type:"result"}`
  - Verify: `pytest tests/execution/test_runner.py -v`锛坒ake 瀛愯繘绋?+ fake 娴?fixture锛?

- [x] 5. `StreamParser` + `ArtifactCollector`锛堟渶缁堟枃鏈?+ tool_result + cwd 浜х墿 + 鏀跺熬 fenced JSON锛?
  - Files: `skillhub_eval/execution/stream_parser.py`銆乣tests/execution/test_stream_parser.py`
  - 鐢?open-design 褰曞埗鐨勬祦鏍锋湰椹卞姩锛涙敹灏?JSON 瑙ｆ瀽澶辫触 鈫?鍚堟垚鍏滃簳
  - Verify: `pytest tests/execution/test_stream_parser.py -v`

- [x] 6. claude adapter锛坄-p --input-format stream-json --output-format stream-json --verbose --permission-mode bypassPermissions`锛? claude-stream-json 瑙ｆ瀽
  - Files: `skillhub_eval/execution/adapters/claude.py`銆乣tests/execution/test_adapter_claude.py`
  - Verify: `pytest tests/execution/test_adapter_claude.py -v`

- [x] 7. codex adapter锛坄exec --json --sandbox workspace-write -c sandbox_workspace_write.network_access=<bool> -c default_permissions=":workspace" -C <cwd>`锛? codex 浜嬩欢娴佽В鏋?
  - Files: `skillhub_eval/execution/adapters/codex.py`銆乣tests/execution/test_adapter_codex.py`
  - Verify: `pytest tests/execution/test_adapter_codex.py -v`

- [x] 8. cursor-agent adapter锛坄--print --output-format stream-json --stream-partial-output --force --trust --workspace <cwd>`锛? 绉佹湁 eventParser锛堝幓閲嶏級
  - Files: `skillhub_eval/execution/adapters/cursor_agent.py`銆乣tests/execution/test_adapter_cursor_agent.py`
  - 鍙傜収 open-design `emitCursorTextDelta` 鏂囨湰鍘婚噸閫昏緫
  - Verify: `pytest tests/execution/test_adapter_cursor_agent.py -v`

## W8.2 鍏冩暟鎹?+ 璇佹嵁 + LocalAgentSource

- [x] 9. 鍏冩暟鎹柊澧?`entrypoint`/`execution_source`锛氳鑼?+ ingest 瑙ｆ瀽 + 鏍￠獙
  - Files: `docs/specs/Skill鍏冩暟鎹畾涔変笌缂栧啓瑙勮寖.md`銆乣skillhub_eval/core/ingest.py`銆乣tests/core/test_ingest_entrypoint.py`
  - has_scripts 蹇呭～ `entrypoint`锛涚己澶?鈫?鏍￠獙鎶ラ敊
  - Verify: `pytest tests/core/test_ingest_entrypoint.py -v`

- [x] 10. `EvidenceVerifier`锛歵ool_result 鏄惁璺戣繃澹版槑鐨?entrypoint
  - Files: `skillhub_eval/execution/evidence.py`銆乣tests/execution/test_evidence.py`
  - Verify: `pytest tests/execution/test_evidence.py -v`

- [x] 11. `PerRunWorkspace`锛歴taging鈫抪er-run clone / 娓呯悊 / 鐣欒瘉
  - Files: `skillhub_eval/execution/workspace.py`銆乣tests/execution/test_workspace.py`
  - Verify: `pytest tests/execution/test_workspace.py -v`锛坈lone 闅旂 + 骞惰鏃犲啿绐?+ 娓呯悊锛?

- [x] 12. `harness_prompt`锛氬己鍒剁敤 skill + 璋?entrypoint + 鏀跺熬 JSON
  - Files: `skillhub_eval/execution/harness_prompt.py`銆乣tests/execution/test_harness_prompt.py`
  - Verify: `pytest tests/execution/test_harness_prompt.py -v`

- [x] 13. `LocalAgentSource`锛氱紪鎺?runner + workspace + 璇佹嵁鏍￠獙锛屼骇鍑?`ExecResult`
  - Files: `skillhub_eval/execution/local_agent_source.py`銆乣tests/execution/test_local_agent_source.py`
  - `Semaphore` 鏈夌晫骞跺彂锛坄EXEC_CONCURRENCY` 榛樿 2锛? 闄愭祦閫€閬?+ per-risk 瓒呮椂
  - Verify: `pytest tests/execution/test_local_agent_source.py -v`锛坒ake adapter 椹卞姩锛?

## W8.2 judge 鍙屾ā寮?

- [x] 14. `_build_case_prompt` 鍔犳墽琛?鏍蜂緥鍙屾ā寮忥紙鎸?`ExecResult.source`锛?
  - Files: `skillhub_eval/core/engine.py`銆乣tests/core/test_judge_dual_mode.py`
  - 鎵ц妯″紡 rubric 璇勬墽琛岀粨鏋滐紱鏍蜂緥妯″紡淇濇寔鐜版湁 doc-centric锛堝惈绾㈢嚎 doc 鍙ｅ緞锛?
  - Verify: `pytest tests/core/test_judge_dual_mode.py -v`

## W8.3 鏉ユ簮璺敱 + 闄嶇骇 + 淇′换 v1 + level

- [x] 15. 鎵ц鏉ユ簮璺敱锛坧er-skill `execution_source` > env锛? 闄嶇骇鐭╅樀
  - Files: `skillhub_eval/core/execution_source.py`銆乣tests/core/test_execution_source_routing.py`
  - 鏃?agent/鏈櫥褰曗啋鏁磋疆 sample_io锛涘崟棰樺け璐?鏃犺瘉鎹啋鍥為€€ sample_io锛屾棤鏍蜂緥鈫抈incomplete`
  - Verify: `pytest tests/core/test_execution_source_routing.py -v`

- [x] 16. `level_achieved` 鏀圭湅鎵ц璇佹嵁 + 淇′换 v1 鎺ョ嚎
  - Files: `skillhub_eval/core/engine.py`锛堝簾寮?:296 `has_scripts AND self.sandbox`锛沴evel_2=鏈夎瘉鎹湡璺戯紱pass鈫扨ASS 鏍?`spot_check_eligible`锛夈€乣tests/core/test_level_and_trust.py`
  - Verify: `pytest tests/core/test_level_and_trust.py -v`

- [x] 17. history 鍙瓫锛歚spot_check_eligible` / `source` 鎸佷箙鍖?+ 绛涢€?
  - Files: `skillhub_eval/persistence/sqlite.py`銆乣skillhub_eval/persistence/repository.py`銆乣tests/persistence/test_spotcheck_filter.py`
  - Verify: `pytest tests/persistence/test_spotcheck_filter.py -v`

## W8.5 瀹夊叏 + 绾㈢嚎鍔犲浐

- [x] 18. 鎵ц鍓嶅悓鎰?+ 鏉冮檺鐩綍绾︽潫 + 涓?Security Gate 鎵撻€?
  - Files: `skillhub_eval/execution/local_agent_source.py`銆乣skillhub_eval/core/engine.py`銆乣tests/execution/test_exec_consent_and_gate.py`
  - blocked bundle 涓?spawn锛涙湭鍚屾剰涓?spawn锛涙潈闄愪粎闄?per-run 鐩綍
  - Verify: `pytest tests/execution/test_exec_consent_and_gate.py -v`

- [x] 19. `HardenedProfile`锛歝odex 绾㈢嚎鍔犲浐妗ｏ紱claude/cursor 绾㈢嚎闄嶇骇 doc-centric
  - Files: `skillhub_eval/execution/profile.py`銆乣skillhub_eval/execution/local_agent_source.py`銆乣tests/execution/test_hardened_profile.py`
  - codex 绾㈢嚎锛氱澶栬仈 + 闄?fs锛沜laude/cursor 绾㈢嚎锛氶檷绾?+ 鎶ュ憡鏍囧師鍥?
  - Verify: `pytest tests/execution/test_hardened_profile.py -v`

- [x] 20. 鍥炰紶杩?output sanitizer锛堝鐢?`run_output_sanitizer`锛?
  - Files: `skillhub_eval/execution/local_agent_source.py`銆乣tests/execution/test_exec_sanitizer.py`
  - Verify: `pytest tests/execution/test_exec_sanitizer.py -v`

## W8.6 绔埌绔獙鏀?

- [x] 21. 鍙墽琛?fixture skill锛堝惈 `entrypoint`锛屽啓涓棿鏂囦欢 + 缁撴瀯鍖栦骇鍑猴級
  - Files: `testskills/<exec-fixture>/...`锛圫KILL.md + frontmatter `entrypoint` + 鑴氭湰 + eval_cases + returns_schema锛?
  - Verify: `pytest tests/ -q`锛坒ixture 琚?ingest/鏍￠獙鎺ュ彈锛?

- [x] 22. 绔埌绔細涓?agent 鍚勮窇閫氬悓涓€ fixture 涓€娆?+ runbook
  - Files: `docs/runbooks/local-agent-exec-validation.md`銆乣tests/execution/test_e2e_local_exec.py`锛堟爣 `@pytest.mark.requires_local_agent`锛岄粯璁?skip锛?
  - Verify: 鏈湴鎵嬪姩 `pytest -m requires_local_agent -v`锛堜笁 agent锛? `pytest tests/ -q`锛堝叏閲忎笉鍥炲綊锛?

## 鏀跺熬

- [x] 23. 鏂囨。瀵归綈锛氬叏鏅鏄?搂10 鎵ц灞傜幇鐘躲€丷ECORD 娴佹按銆丼print W8 鍕鹃€?
  - Files: `docs/guides/Skill璇勪及绯荤粺鍏ㄦ櫙璇存槑.md`銆乣RECORD.md`銆乣.project_memory/active/SPRINT_phase3-eval-system.md`
  - Verify: 浜哄伐 review + `pytest tests/ -q`
