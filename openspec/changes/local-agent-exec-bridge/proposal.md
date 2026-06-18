# Change: local-agent-exec-bridge

> 2026-06-17 grill 淇锛氬洖浼犲绾︾敱銆孧CP submit 宸ュ叿銆嶆敼涓恒€宻tream-json 娴佽В鏋愩€嶏紙open-design 瀹炴祴浠?claude 鏈?MCP 娉ㄥ叆锛夛紱judge 鏂板鎵ц妯″紡 prompt锛涙柊澧?entrypoint/execution_source 鍏冩暟鎹紱绾㈢嚎棰樺垎鍔犲浐妗?闄嶇骇銆傝瑙?`docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md` 搂0銆?

## Why

褰撳墠璇勪及鍦?`case_executing` 闃舵涓嶇湡璺?skill锛歚skillhub_eval/core/engine.py` 鐩存帴 `load_sample_io(skill_bundle_path, case_id)` 璇诲彇浣滆€呴鏀剧殑 `sample_io/{case}.json` 浣滀负 `actual_output`锛坋ngine.py:313/330/1010锛夈€傚悗鏋滐細

- 鍘熻鍒掔殑涓ぎ subprocess 娌欑洅锛圵8 Level 2锛?*缁撴瀯涓婅窇涓嶄簡鍐呯綉 skill**锛堜腑澶棤 VPN/DB/Token锛夛紝鑰屽唴缃?skill 鎭版伆鏈€闇€瑕佺湡璺戙€?
- 璇勭殑鏄€屾潗鏂欐槸鍚﹁嚜娲姐€嶏紝涓嶆槸銆岀湡瀹炰娇鐢ㄦ椂鑳藉惁璺戦€氥€嶃€?

鏈彉鏇存妸銆岀湡瀹炴墽琛屻€嶄笅鏀惧埌寮€鍙戣€呮湰鍦板凡閰嶅ソ鐨?CLI agent锛坈laude / codex / cursor-agent锛夛紝鐢?SkillHub **鍚屾満 spawn** 椹卞姩鍏剁湡璺?skill锛?*瑙ｆ瀽鍏?stream-json 杈撳嚭**鏀堕泦鐪熷疄浜у嚭锛涜瘎鍒嗙郴缁燂紙DSL 鏂█ / 鍙屾ā鍨?/ 瀹夊叏 / 鑱氬悎 / 鍐崇瓥锛夌粨鏋勫鐢紝judge 鎸夋墽琛?鏍蜂緥鍒嗕袱濂?prompt锛宍actual_output` 鏉ユ簮鏀逛负鐪熷疄鎵ц銆?

璁捐渚濇嵁锛歚nexu-io/open-design`锛坙ocal-first锛宒aemon + per-agent adapter + stream-json 娴佽В鏋愶級銆傚畬鏁磋璁＄瑙?`docs/superpowers/specs/2026-06-17-local-agent-exec-bridge-design.md`銆?

## What Changes

- 鏂板 `ExecutionSource` 鎶借薄锛圥ort锛夛紝寮曟搸 `case_executing` 缁忓畠鍙?`actual_output`锛屽彇浠ｇ洿璋?`load_sample_io`銆?
- 鏂板 `SampleIoSource`锛堝寘鐜版湁琛屼负锛屼綔鍥為€€/浣滆€呭彲閫夛級涓?`LocalAgentSource`锛堥┍鍔ㄦ湰鍦?agent 鐪熻窇锛夈€?
- 鏂板 `LocalAgentRunner`锛堟妱 open-design锛夛細agent 妫€娴?/ 鍚屾満 spawn锛堝師鐢?Windows锛宲rompt 缁?stdin锛? **StreamParser 娴佽В鏋?* / 瀹屾垚鍒ゅ畾 / 浜х墿鎻愬彇 / entrypoint 鎵ц璇佹嵁鏍￠獙锛泇1 鏀寔 claude銆乧odex銆乧ursor-agent锛堝疄鐜伴『搴?claude 鈫?codex 鈫?cursor-agent锛夈€?
- **鍥炰紶璧版祦瑙ｆ瀽**锛堥潪 MCP锛夛細`actual_output` = 鏈€缁?result 鏂囨湰 + tool_result + per-run cwd 浜х墿鏂囦欢 + 鍙€夋敹灏?fenced JSON銆?
- judge 鏂板**鎵ц妯″紡 prompt**锛堢湡璺戞椂鎸夋墽琛岀粨鏋滆瘎锛夛紱鏍蜂緥妯″紡锛堢幇鏈?doc-centric锛変繚鐣欙紱娴佹按绾跨粨鏋勩€佸弻妯″瀷銆佽仛鍚堛€丷1鈥揜8 鍐崇瓥涓嶅彉銆?
- 鏂板 `PerRunWorkspace`锛氭瘡棰樻瘡娆¤繍琛屼粠 staging clone 涓存椂 cwd锛涙湁鐣屽苟鍙戯紙榛樿 2锛屽彲閰嶏級+ 闄愭祦閫€閬裤€?
- 鏂板鍏冩暟鎹瓧娈?`entrypoint`锛坔as_scripts 蹇呭～锛夈€乣execution_source`锛坧er-skill锛岄粯璁ら殢 env `EXEC_SOURCE`锛夈€?
- 绾㈢嚎棰橈細happy/edge 涓?agent 鐪熻窇锛涚孩绾跨湡璺戜粎 codex 鍔犲浐妗ｏ紙`--sandbox workspace-write` + `network_access=false`锛夛紝claude/cursor 绾㈢嚎闄嶇骇 doc-centric銆?
- 淇′换妯″瀷鍒嗛樁娈碉紙v1锛氫俊浠绘湰鍦帮紝judge pass鈫扨ASS锛屾爣 `spot_check_eligible` 涓?history 鍙瓫锛夛紱鎵ц鏉ユ簮鍙€?+ 闄嶇骇鍥為€€鐭╅樀銆?
- 瀹夊叏锛氭墽琛屽墠鍚屾剰銆佹潈闄愮害鏉熷湪 per-run 鐩綍銆佷笌鐜版湁 Security Gate 鎵撻€氥€佸洖浼犺繃 output sanitizer銆?
- `level_achieved`锛氭湰鍦扮湡璺戯紙鏈?entrypoint 璇佹嵁锛? level_2锛坰ource=local_agent锛夛紱sample_io = level_1锛涘簾寮?`has_scripts AND self.sandbox` 鍒ゅ畾銆?

## Non-Goals

- `submit_case_output` MCP 宸ュ叿 / `SkillHubMcpServer`鈥斺€攇rill 鍚庡垹闄わ紙cursor/codex 鏃?MCP 娉ㄥ叆锛屼笉閫氱敤锛夈€?
- 澶?agent 瀵圭収缁熻锛圵8.4锛夆€斺€旀湰鍙樻洿鍙繚璇佷笁 agent 鍚勮兘鍗曠嫭璺戦€氥€?
- 鍏綉涓ぎ澶嶆牳 / 鑷姩鍒嗙骇 PASS鈥斺€斿睘鐩爣鎬侊紙澶氱敤鎴?涓婁簯锛夛紝v1 涓嶅仛銆?
- 缃戠粶妗?/ 涓婁簯 transport鈥斺€攙1 鍙仛鍚屾満 spawn銆?
- claude/cursor 绾㈢嚎瀹瑰櫒鍔犲浐锛圵SL+firejail锛夆€斺€旂洰鏍囨€併€?
- hybrid 浼氳瘽鍒嗙粍鈥斺€旀祴鍑恒€屽お鎱€嶅啀璇淬€?
- 涓ぎ纭畾鎬т唬鐮佽窇 / Golden Case / 涓婃灦鍚庡仴搴锋鏌モ€斺€斿凡绉婚樁娈靛洓锛圵10锛夈€?
- 鐗╃悊鍒犻櫎 `skillhub_eval/sandbox/python_subprocess.py`鈥斺€旂暀鏋跺瓙锛屾寜瀹夊叏鍗忚鍙﹁纭銆?

## Relation to SPRINT

闃舵涓?路 Wave 8锛堥噸瀹氫箟 2026-06-17锛夛紝瑕嗙洊 W8.1鈥揥8.6锛岃 `.project_memory/active/SPRINT_phase3-eval-system.md`銆傚彇浠ｅ師 W8 Level 2 涓ぎ娌欑洅 + 鍘?W9 鑷缓 Harness銆傚彈褰卞搷瑙勮寖鏂囨。锛歚docs/specs/Skill鍏冩暟鎹畾涔変笌缂栧啓瑙勮寖.md`锛堟柊澧?`entrypoint`/`execution_source`銆乺eturns_schema / sample_io锛夈€乣docs/specs/璇勪及鎸囨爣涓庡噯鍏ユ爣鍑?md`锛堝噯鍏ヤ笌淇′换銆乴evel 璇箟锛夈€?
