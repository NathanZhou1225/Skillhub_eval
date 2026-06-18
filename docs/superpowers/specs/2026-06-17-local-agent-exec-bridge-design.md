# 鏈湴 Agent 鎵ц妗?鈥?璁捐绋匡紙W8 閲嶅畾涔夛級

> 鏃ユ湡锛?026-06-17锛堝惈鍚屾棩 grill-me 淇锛?
> 鐘舵€侊細Grill 瀹氱锛?1 椤硅璁″彉鏇村凡骞跺叆锛涗笅涓€姝?OpenSpec change 鍚屾 鈫?瀹炵幇锛?
> 鑼冨洿锛氶樁娈典笁 路 Wave 8锛堥噸瀹氫箟锛屽彇浠ｅ師 W8 Level 2 涓ぎ娌欑洅 + 鍘?W9 鑷缓 Harness锛?
> 鐩稿叧锛歚RECORD.md`锛?026-06-17 鍐崇瓥缁勩€丵-19/20/21/22锛夈€乣.project_memory/active/SPRINT_phase3-eval-system.md`锛圵8.0鈥揥8.6锛夈€乣docs/guides/Skill璇勪及绯荤粺鍏ㄦ櫙璇存槑.md` 搂10.5
> 璁捐渚濇嵁锛歚nexu-io/open-design`锛坙ocal-first锛宒aemon + per-agent adapter + **stream-json 娴佽В鏋?*锛?

---

## 0. Grill 淇鎽樿锛?026-06-17锛?

鏈缁?grill-me 鍚庡鍒濈増鍋氫簡 11 椤规敼鍔紝**涓ら」鎺ㄧ炕鍒濈増鏍稿績鍋囪**锛屽姟蹇呭厛璇伙細

| # | 鍙樻洿 | 绫诲瀷 |
|---|------|------|
| G1 | **鐮嶆帀 `submit_case_output` MCP 宸ュ叿锛屾敼銆屾祦瑙ｆ瀽銆嶇粺涓€鍥炰紶**锛坥pen-design 閲屽彧鏈?claude 鏈?MCP 娉ㄥ叆锛宑ursor-agent/codex 閮芥病鏈夛紝鍏剁湡瀹炴満鍒跺氨鏄В鏋?stream-json锛夈€俙SkillHubMcpServer` 缁勪欢 v1 鍒犻櫎 | 鎺ㄧ炕 D3 |
| G2 | **judge 闈炪€屽畬鍏ㄤ笉鍔ㄣ€嶏細鏂板鎵ц妯″紡 prompt 鍒嗘敮**锛堢幇 prompt 鏄?doc-centric 璇?SKILL.md锛涚湡璺戞椂瑕佹寜鎵ц缁撴灉璇勶級銆傛祦姘寸嚎缁撴瀯涓嶅姩锛宲rompt 鍒嗕袱濂?| 淇 D5/D6 鍓嶆彁 |
| G3 | has_scripts 鎶€鑳借 **entrypoint 鎵ц璇佹嵁**锛坱ool_result 璇佹槑鐪熻窇杩囷級锛屽惁鍒欓檷绾?incomplete | 鏂板 |
| G4 | 鏂板 **`entrypoint` 鍏冩暟鎹瓧娈?*锛坔as_scripts 蹇呭～锛夛紱鏀?`docs/specs/Skill鍏冩暟鎹畾涔変笌缂栧啓瑙勮寖.md` + ingest + 鏍￠獙 | 鏂板 |
| G5 | 鏂板 **per-skill `execution_source` 瀛楁** + env `EXEC_SOURCE` 鍏滃簳榛樿 | 鏂板 |
| G6 | **寮哄埗鐢?harness prompt**锛堟槑纭懡浠?agent 鐢?cwd 鐨?skill 骞惰皟 entrypoint锛?| 鏂板 |
| G7 | **鍘熺敓 Windows 鍙锛屼笉闇€ WSL**锛坥pen-design 閫傞厤鍣ㄤ笓涓?Windows CreateProcess 闄愬埗璧?stdin锛屽凡璇绘簮鐮佺‘璁わ級 | 纭 |
| G8 | **绾㈢嚎棰?*锛歨appy/edge 涓?agent 鐪熻窇锛涚孩绾跨湡璺戝彧鏈?**codex** 鑳戒笂鍔犲浐妗ｏ紙`--sandbox workspace-write` + `network_access=false`锛夛紝**claude/cursor 绾㈢嚎闄嶇骇 doc-centric** | 鏀剁揣 D2 |
| G9 | **level_2 = 鏈湴鐪熻窇锛堟湁 entrypoint 璇佹嵁锛? source=local_agent锛泂ample_io = level_1**锛涘簾寮?`has_scripts AND self.sandbox` 鍒ゅ畾 | 淇 |
| G10 | **涓撳鎶芥绾汉宸?*锛屼絾鏈湴鐪熻窇 PASS 蹇呴』琚爣璁颁笖 history 鍙瓫 | 鏀剁揣 D6 |
| G11 | **骞跺彂榛樿 2 + 闄愭祦鑷姩閫€閬?*锛堟鍒?429 鈫?閫€骞跺彂鍒?1 + 鎸囨暟閫€閬块噸璇曪級 | 缁嗗寲 D2 |

閫傞厤瀹炵幇椤哄簭闅忎箣璋冩暣锛堢悊鐢卞彉浜嗭級锛?*claude锛坈laude-stream-json 鏈€鎴愮啛锛夆啋 codex锛堣嚜甯︽矙绠憋紝绾㈢嚎鍞竴鍙湡璺戯級鈫?cursor-agent锛坖son-event-stream + 绉佹湁 eventParser锛?*銆?

---

## 1. 鑳屾櫙涓庣洰鏍?

### 1.1 闂

褰撳墠璇勪及鍦?`case_executing` 闃舵**涓嶇湡璺?skill**锛岃€屾槸浠庣鐩樿鍙栦綔鑰呬簨鍏堟斁鍏ョ殑 `sample_io/{case}.json` 浣滀负 `actual_output`锛坋ngine.py:313/330/1010锛夈€傚悗鏋滐細

- 涓ぎ subprocess 娌欑洅锛堝師 W8 璁″垝锛?*缁撴瀯涓婅窇涓嶄簡鍐呯綉 skill**锛堟棤 VPN/DB/Token锛夆€斺€旇€屽唴缃?skill 鎭版伆鏈€闇€瑕佺湡璺戙€?
- 璇勭殑鏄€屾潗鏂欐槸鍚﹁嚜娲姐€嶏紝涓嶆槸銆岀湡瀹炰娇鐢ㄦ椂鑳藉惁璺戦€氥€嶃€?

### 1.2 鐩爣

鎶娿€岀湡瀹炴墽琛屻€?*涓嬫斁鍒板紑鍙戣€呮湰鍦板凡閰嶅ソ鐨?CLI agent**锛坈ursor-agent / codex / claude锛夛紝鐢?SkillHub 鍚屾満 spawn 椹卞姩鍏剁湡璺?skill锛?*瑙ｆ瀽鍏?stream-json 娴?*鏀堕泦鐪熷疄浜у嚭锛涜瘎鍒嗙郴缁燂紙DSL 鏂█ / 鍙屾ā鍨?/ 瀹夊叏 / 鑱氬悎 / 鍐崇瓥锛?*缁撴瀯涓嶅彉銆乸rompt 鍒嗘墽琛?鏍蜂緥涓ゅ**锛宍actual_output` 鏉ユ簮鏀逛负鐪熷疄鎵ц銆?

### 1.3 鍙栦唬鍏崇郴

- 鍙栦唬鍘?**W8 Level 2 涓ぎ娌欑洅**锛氭湰鍦?agent 璺戜换鍔℃椂宸叉墽琛?skill 鑴氭湰锛屼腑澶啀鐙珛 `python run.py` 鍐椾綑銆?
- 鍙栦唬鍘?**W9 鑷缓 Agent Harness**锛氬紑鍙戣€呮湰鍦板凡閰嶅ソ鐨?CLI agent 鍗炽€屽垎甯冨紡 Harness銆嶃€?
- 鍘?**W10 Golden Case + 涓婃灦鍚庡仴搴锋鏌?*锛氱Щ鑷抽樁娈靛洓锛堜笌涓婃灦鑱斿姩锛夈€?
- `PythonSubprocessRunner`锛坄skillhub_eval/sandbox/python_subprocess.py`锛夌暀鏋跺瓙锛屼粎闃舵鍥?Golden Case 闇€銆岀簿纭柇瑷€ + 纭畾鎬у璺戙€嶆椂鎸夐渶鎺ユ渶灏忕増锛?*涓嶇墿鐞嗗垹闄?*銆?

---

## 2. 宸查攣瀹氬喅绛栵紙brainstorm + grill 2026-06-17锛?

| # | 鍐崇瓥 | 鍙栬垗 |
|---|------|------|
| D1 閮ㄧ讲/浼犺緭 | **鍚屾満 spawn**锛氬悗绔洿鎺?spawn 瀛愯繘绋嬶紝鏃犵綉缁滄ˉ | 鎺掗櫎缃戠粶妗?MCP-over-network锛堝厛鏈湴锛屼笂浜戝啀鎹?transport锛?|
| D2 鎵ц绮掑害 | **姣忛闅旂 + 鏈夌晫骞跺彂**锛堥粯璁?2锛屽彲閰嶏級+ risk 鍒嗙骇瓒呮椂 + 闄愭祦閫€閬匡紙G11锛?| 鎺掗櫎鍗曚細璇濆叏涓茶锛堟參銆佺孩绾胯姹℃煋锛夛紱hybrid 寰呮祴鍑哄お鎱㈠啀涓?|
| D3 杈撳嚭濂戠害 | ~~MCP submit 宸ュ叿~~ 鈫?**銆怗1 鏀广€戞祦瑙ｆ瀽缁熶竴濂戠害**锛氳В鏋?stream-json 鍙栨渶缁?result 鏂囨湰 + tool_result + per-run cwd 浜х墿鏂囦欢 + 鍙€夋敹灏?fenced JSON | 鎺掗櫎 MCP submit锛坈ursor/codex 鏃?MCP 娉ㄥ叆锛屼粎 claude 鏈夛紱涓嶉€氱敤锛?|
| D4 宸ヤ綔鐩綍 | **姣忔杩愯涓存椂 clone**锛氫粠 staging 鍏嬮殕 per-run 鐩綍浣?cwd | 鎺掗櫎鍏变韩 staging锛堝苟琛屽啓鍐茬獊锛夈€佸彧璇?staging锛堝啓涓棿鏂囦欢璺戜笉璧锋潵锛?|
| D5 璺緞鍏崇郴 | **澧為噺 + 鍥為€€ + 鏉ユ簮鍙€?*锛氫綔鑰呴€夋墽琛屾潵婧愶紙per-skill 瀛楁锛孏5锛夛紱agent 缂哄け/澶辫触 鈫?鑷姩鍥為€€ sample_io | 鎺掗櫎瀹屽叏鏇夸唬銆佸苟璺戝鐓э紙W8.4锛?|
| D6 淇′换锛堝垎闃舵锛?| **v1 淇′换鏈湴**锛歫udge pass鈫扨ASS锛涙娊妫€绾汉宸ヤ絾鍙瓫锛圙10锛夈€?*鐩爣鎬?*锛氬叕缃戜腑澶鏍?/ 鍐呯綉涓撳绛炬敹 | 鎺掗櫎 v1 寤轰腑澶鏍革紙杩囨棭锛夈€佷竴寰嬬鏀讹紙鎱級銆佹案涔呬俊浠伙紙澶氱敤鎴锋紡娲烇級 |
| D7 鏂█绛栫暐 | **缁撴瀯鎬?+ 璇箟涓轰富**锛屽蹇?agent 闈炵‘瀹?| 鎺掗櫎绮剧‘鍊兼柇瑷€锛堟崲 agent/妯″瀷 flaky锛?|
| D8 v1 agent 闆?| **claude 鈫?codex 鈫?cursor-agent**锛圙1 鍚庢寜瑙ｆ瀽鍣ㄥ鏉傚害/绾㈢嚎鑳藉姏鎺掑簭锛夛紱澶?agent 瀵圭収 鈫?W8.4 | 鎺掗櫎 v1 鍙墦閫?1 涓紱鍏ㄩ噺 agent锛圷AGNI锛?|
| D9 鍒ゅ瓙妯″紡锛圙2锛?| **鎵ц妯″紡 prompt 鍒嗘敮**锛氱湡璺戔啋鎵ц缁撴灉 rubric锛泂ample_io鈫掔幇鏈?doc-centric prompt | 鎺掗櫎銆宲rompt 涓嶅姩鐩存帴濉?actual_output銆嶏紙绾㈢嚎鍙ｅ緞鑷浉鐭涚浘锛?|
| D10 鎵ц璇佹嵁锛圙3锛?| has_scripts 鎶€鑳借 tool_result 璇佹槑 entrypoint 鐪熻窇锛涙棤璇佹嵁鈫掗檷绾?incomplete | 鎺掗櫎鍙俊鏂囨湰杈撳嚭锛坅gent 鍙粫 pipeline 鎵嬬紪锛?|
| D11 绾㈢嚎闅旂锛圙8锛?| 绾㈢嚎鐪熻窇浠呭湪鍔犲浐妗ｄ笅锛沜odex 鐢ㄥ師鐢熸矙绠憋紝claude/cursor 鏃犲姞鍥烘。鈫掔孩绾块檷绾?doc-centric | 鎺掗櫎鍘熺敓 Windows 闃茬伀澧?ACL锛堣剢寮憋級銆佸己琛屽叏 WSL锛堝伐绋嬮噺澶э級 |

---

## 3. 鏋舵瀯涓庣粍浠?

```
鈹屸攢 寮曟搸锛坈ore/engine.py锛宻erver-side async锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹? 鈥?gate 閫氳繃 鈫?capability_full 鈫?case_executing                       鈹?
鈹?        鈹?                                                             鈹?
鈹?        鈻? 閫氳繃 ExecutionSource 鎶借薄鍙?actual_output锛堟浛鎹㈢洿璋?load_sample_io锛?
鈹? 鈹屸攢 ExecutionSource 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?
鈹? 鈹? LocalAgentSource   鈫愨啋  SampleIoSource锛堝洖閫€/鍙€夛級             鈹?  鈹?
鈹? 鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?  鈹?
鈹?         鈻?                                                           鈹?
鈹? judge锛堟墽琛屾ā寮?/ 鏍蜂緥妯″紡 鍙?prompt锛夆啋 aggregate 鈫?decision           鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
            鈹?LocalAgentSource 璋冪敤
            鈻?
鈹屸攢 LocalAgentRunner锛堟妱 open-design锛夆攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
鈹? 鈥?detect锛氭娴嬫湰鍦板凡瑁?宸茬櫥褰?agent锛坈laude/codex/cursor-agent锛夆攤
鈹? 鈥?per-agent adapter锛歜uildArgs + stdin 鎶曞杺 prompt              鈹?
鈹? 鈥?spawn 瀛愯繘绋嬶紙鍚屾満锛屽師鐢?Windows锛?                           鈹?
鈹? 鈥?StreamParser锛氭寜 streamFormat 瑙ｆ瀽 stream-json               鈹?
鈹? 鈥?瀹屾垚鍒ゅ畾锛氬瓙杩涚▼ exit + 娴佺粓缁?result 浜嬩欢                    鈹?
鈹? 鈥?ArtifactCollector锛氭渶缁堟枃鏈?+ tool_result + cwd 浜х墿 + usage  鈹?
鈹? 鈥?EvidenceVerifier锛歵ool_result 鏄惁璺戣繃澹版槑鐨?entrypoint       鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
        鈻?
鈹屸攢 PerRunWorkspace 鈹€鈹?鈹屸攢 HardenedProfile 鈹€鈹€鈹€鈹€鈹€鈹?鈹屸攢 骞跺彂 Semaphore 鈹€鈹?
鈹? staging鈫抍lone     鈹?鈹?codex: workspace-write 鈹?鈹?榛樿 2锛屽彲閰?     鈹?
鈹? 璺戝悗娓呯悊/鐣欒瘉      鈹?鈹?+ network_access=false 鈹?鈹?闄愭祦鈫掗€€ 1 + 閫€閬? 鈹?
鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?鈹?claude/cursor: 鏃犫啋闄嶇骇 鈹?鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
                       鈹斺攢鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹?
```

> **G1锛氭棤 `SkillHubMcpServer`**銆傚洖浼犱笉闈?MCP锛岄潬 `StreamParser` 瑙ｆ瀽瀛愯繘绋?stdout 鐨?stream-json銆傞闈紙user_intent / 杈撳叆 / entrypoint 瑕佹眰锛夌洿鎺ュ啓杩?harness prompt銆?

### 缁勪欢鑱岃矗涓庤竟鐣?

| 缁勪欢 | 鍋氫粈涔?| 鎬庝箞鐢?| 渚濊禆 |
|------|--------|--------|------|
| `ExecutionSource`锛堟娊璞?Port锛?| 缁欏畾 case + bundle锛岃繑鍥?`ExecResult`锛坅ctual_output + 璇佹嵁 + source + level锛?| 寮曟搸 `case_executing` 鍞竴璋冪敤鐐?| 涓や釜瀹炵幇 |
| `SampleIoSource` | 鐜版湁琛屼负锛氳 `sample_io/{case}.json` | 鍥為€€ / 浣滆€呴€?sample_io | `ingest.load_sample_io` |
| `LocalAgentSource` | 椹卞姩鏈湴 agent 鐪熻窇銆佹敹闆嗗洖浼犮€佸苟鍙?闄愭祦 | 浣滆€呴€夈€屾湰鍦扮湡璺戙€嶄笖 agent 鍙敤 | Runner + Workspace + HardenedProfile |
| `LocalAgentRunner` | detect / spawn / StreamParser / 瀹屾垚鍒ゅ畾 / ArtifactCollector / EvidenceVerifier | 姣忎釜 per-run 璋冧竴娆?| 鍚屾満 CLI agent锛沘dapter registry |
| `StreamParser`锛坧er-agent锛?| 鎸?`streamFormat`/`eventParser` 瑙ｆ瀽 stream-json | Runner 鍐?| 鈥?|
| `EvidenceVerifier` | tool_result 鏄惁鎵ц浜嗗０鏄?entrypoint | has_scripts 鎶€鑳?| entrypoint 鍏冩暟鎹?|
| `PerRunWorkspace` | clone staging鈫抪er-run 涓存椂鐩綍锛涙竻鐞?鐣欒瘉 | 姣忛姣忔杩愯 | staging |
| `HardenedProfile` | codex 娌欑妗ｏ紙绂佺綉/闄?fs锛夛紱claude/cursor 鏃犫啋绾㈢嚎闄嶇骇 | 绾㈢嚎棰?| adapter 鑳藉姏 |
| 骞跺彂鎺у埗 | `Semaphore`锛堥粯璁?2锛? 闄愭祦閫€閬?| 鍖呰９姣忛杩愯 | settings/.env |

---

## 4. 鏁版嵁娴?

```mermaid
flowchart TD
    G["assessment_gate 閫氳繃 鈫?capability_full"] --> SRC{鎵ц鏉ユ簮? per-skill 瀛楁/env 榛樿}
    SRC -->|鏈湴鐪熻窇 涓?agent 鍙敤| RT{case 绫诲瀷?}
    SRC -->|浣滆€呴€?sample_io / 鏃?agent| FB["SampleIoSource(鏍囦綆缃俊, level_1)"]
    RT -->|happy/edge| CE["涓?agent 浠讳竴鐪熻窇(鏈夌晫骞跺彂 2)"]
    RT -->|refusal/adversarial| HARD{鏈夊姞鍥烘。?}
    HARD -->|codex 娌欑| CE
    HARD -->|claude/cursor 鏃犲姞鍥簗 FB
    CE --> CL["姣忛:PerRunWorkspace clone staging鈫掍复鏃?cwd"]
    CL --> SP["spawn 鏈湴 agent(harness prompt:寮哄埗鐢?skill+璋?entrypoint)"]
    SP --> RUN["agent 鎵ц(璋冭剼鏈?宸ュ叿)"]
    RUN --> PARSE["StreamParser 瑙ｆ瀽 stream-json"]
    PARSE --> DONE["瀹屾垚鍒ゅ畾:瀛愯繘绋?exit + 娴?result 浜嬩欢"]
    DONE --> EV{has_scripts? entrypoint 璇佹嵁?}
    EV -->|鏈夎瘉鎹畖 AO["actual_output = 鏈€缁堟枃鏈?+ tool_result + cwd 浜х墿; level_2"]
    EV -->|鏃犺瘉鎹畖 FB
    AO --> SAN["output sanitizer(PII/瀵嗛挜)"]
    SAN --> J["judge 鎵ц妯″紡 prompt(鍙屾ā鍨嬫寜鎵ц缁撴灉璇?"]
    FB --> JS["judge 鏍蜂緥妯″紡 prompt(doc-centric)"]
    J --> AGG["aggregate 鈫?decision(R1鈥揜8 涓嶅彉)"]
    JS --> AGG
    AGG --> V1["v1:pass鈫扨ASS(鏍?spot_check_eligible, history 鍙瓫);warn/R5鈫掍笓瀹?]
```

---

## 5. 鎵ц鍗曞厓涓庡苟鍙戯紙D2 / G11锛?

- **姣忛涓€娆＄嫭绔嬭繍琛?*锛氭瘡閬?case spawn 骞插噣 agent 浼氳瘽锛涜緭鍏ラ殧绂汇€佷骇鐗╀竴涓€瀵瑰簲锛涚孩绾块涓嶈涓婁笅鏂囨薄鏌撱€?
- **鏈夌晫骞跺彂**锛歚Semaphore(N)`锛?*榛樿 N=2**锛堟斁 `.env` 鍙厤锛夈€傚苟琛屾槸鍘嬬缉 high-risk 澶氶澧欓挓鏃堕棿鐨勪富鏉犳潌銆?
- **闄愭祦閫€閬匡紙G11锛?*锛歋treamParser 妫€鍒?rate-limit/429 鈫?鑷姩閫€骞跺彂鍒?1 + 鎸囨暟閫€閬块噸璇曡棰橈紱鎸佺画澶辫触 鈫?璇ラ杩涢檷绾х煩闃点€?
- **per-case 瓒呮椂**锛氭部鐢?risk 鍒嗙骇瓒呮椂棰勭畻锛涘崟棰樿秴鏃惰繘闄嶇骇鐭╅樀銆?
- **鑰楁椂瀹炴祴鍏堣**锛歷1 涓嶉寤?hybrid 鍒嗙粍锛沇8.6 鐢ㄧ湡瀹?high-risk skill 娴嬪閽熸椂闂达紝瓒呴槇鍊煎啀鑰冭檻銆?

---

## 6. 宸ヤ綔鐩綍涓庨殧绂伙紙D4锛?

- 姣忛姣忔杩愯浠?**staging 缁冧範鍖?* clone 鍑虹嫭绔?per-run 涓存椂鐩綍浣滀负 agent `cwd`銆?
- 骞惰杩愯鍚勬湁鐙珛鐩綍锛岄伩鍏嶆枃浠跺啓鍐茬獊銆?
- 鏉冮檺锛歨appy/edge 娌跨敤 open-design 鍏ㄨ嚜鍔ㄥЭ鎬侊紙claude `bypassPermissions`銆乧ursor `--force --trust`銆乧odex `workspace-write`锛夛紝绾︽潫鍦ㄤ复鏃剁洰褰?+ 璇勪及鏈燂紱涓嶅姩 `originals` 鍘熺鍖恒€佷笉鍔?staging 姣嶆湰銆?
- 绾㈢嚎棰樿 搂11 鍔犲浐妗ｃ€?
- 璺戝悗榛樿娓呯悊锛涘彲閰嶇疆淇濈暀浣滆瘉鎹?瀹¤锛堜笌 transcript 涓€骞跺瓨 run 鐩綍锛夈€?

---

## 7. 鍥炰紶濂戠害锛氭祦瑙ｆ瀽锛圖3 / G1锛?

> **涓嶇敤 MCP submit**銆俹pen-design 瀹炴祴锛氬彧鏈?claude 鏈?`externalMcpInjection`锛堝啓 cwd `.mcp.json`锛夛紝cursor-agent / codex 閮芥病鏈夛紱瀹冧滑鐨勪骇鍑哄叏闈?*瑙ｆ瀽 stream-json**銆?

### 7.1 瀹屾垚鍒ゅ畾锛堜袱灞傦紝瀹炶 open-design daemon锛?

1. **杩涚▼灞?*锛氬瓙杩涚▼ `exit`锛坈ode/signal锛夆€斺€旂‖瀹屾垚銆?
2. **娴佸眰**锛歴tream-json 缁堢粨 `{type:"result"}` 浜嬩欢锛堝甫 `usage`/`duration_ms`/閿欒鐘舵€侊級鈥斺€旇涔夊畬鎴愩€?

### 7.2 浜х墿鎻愬彇锛圓rtifactCollector锛?

| 绫诲埆 | 鏉ユ簮 | 鐢ㄩ€?|
|------|------|------|
| 鏈€缁堟枃鏈?| 鍚?`streamFormat` 鐨?result/assistant 鏂囨湰 | 璇箟璇勫涓昏緭鍏?|
| `tool_result` | agent 璋冭剼鏈?宸ュ叿鐨?stdout + exit_code/isError | **鎵ц璇佹嵁锛圙3锛?*锛涚粨鏋勫寲 DSL 鏉ユ簮 |
| cwd 浜х墿鏂囦欢 | per-run 涓存椂鐩綍鏂板/鏀瑰姩鏂囦欢锛堝 pipeline 鐢熸垚鐨?HTML/JSON锛?| 浜や粯鐗╄瘉鎹?|
| 鏀跺熬 fenced JSON | harness prompt 瑕佹眰 agent 鏈熬鎵撳嵃鐨勭粨鏋勫寲鍧楋紙best-effort锛?| 鍖归厤 returns_schema 鐨勭粨鏋勫寲 actual_output |
| usage/duration | result 浜嬩欢 | 鎴愭湰/鑰楁椂鍙娴?|

**actual_output 缁勮**锛氫紭鍏堟敹灏?fenced JSON锛堣嫢瑙ｆ瀽鎴愬姛涓斿尮閰?returns_schema锛夛紱鍚﹀垯鐢ㄦ渶缁堟枃鏈?+ tool_result + cwd 浜х墿鐨勫悎鎴愩€倀hree 璺瘉鎹竴骞跺瓨鍏?transcript_ref 渚涘弻妯″瀷璇汇€?

### 7.3 鍚?agent 娴佹牸寮忥紙瀹炶婧愮爜锛?

| agent | streamFormat | eventParser | 澶囨敞 |
|-------|--------------|-------------|------|
| claude | `claude-stream-json` | 鍐呯疆 | `-p --input-format stream-json --output-format stream-json --verbose` |
| codex | `json-event-stream` | `codex` | `exec --json ...`锛涘甫鍘熺敓娌欑 |
| cursor-agent | `json-event-stream` | `cursor-agent`锛堢鏈夛紝鏂囨湰鍘婚噸閫昏緫瑙?`emitCursorTextDelta`锛?| `--print --output-format stream-json --stream-partial-output` |

---

## 8. 寮曟搸鎺ョ紳涓?v1 agent 閫傞厤锛圖1/D8/G7锛?

### 8.1 鎺ョ紳

寮曟搸 `case_executing` 鐜扮姸鐩磋皟 `load_sample_io`锛坋ngine.py:313/330锛宩udge prompt:1010锛夈€傛敼涓虹粡 `ExecutionSource.get_actual_output(case, bundle, ctx) -> ExecResult`锛?

- 榛樿瀹炵幇鎸夈€屾墽琛屾潵婧愩€嶏紙per-skill 瀛楁 > env 榛樿锛孏5锛夎矾鐢卞埌 `LocalAgentSource` 鎴?`SampleIoSource`銆?
- **judge 娴佹按绾跨粨鏋勪笉鍔?*锛屼絾**鎸?ExecResult.source 閫?prompt 妯″紡**锛堟墽琛?/ 鏍蜂緥锛岃 搂10锛夈€?

### 8.2 v1 涓?agent 閫傞厤锛堟妱 open-design锛汫1 鍚庢棤 MCP 娉ㄥ叆椤癸級

姣忎釜 agent 绉绘锛氣憼 妫€娴?鐧诲綍鎺㈡祴锛涒憽 `buildArgs` + **stdin 鎶曞杺**锛堥伩寮€ Windows CreateProcess ~32KB 闄愬埗锛孏7锛夛紱鈶?StreamParser銆?

| 椤哄簭 | agent | buildArgs锛堝疄璇伙級 | 瑙ｆ瀽 | 娌欑鑳藉姏 |
|---|-------|-------------------|------|----------|
| 1 | claude | `-p --input-format stream-json --output-format stream-json --verbose --permission-mode bypassPermissions` | claude-stream-json锛堟渶鎴愮啛锛屽厛鍋氾級 | 鏃狅紙鍏ㄤ俊浠伙級鈫?绾㈢嚎闄嶇骇 |
| 2 | codex | `exec --json --skip-git-repo-check --sandbox workspace-write -c sandbox_workspace_write.network_access=<bool> -c default_permissions=":workspace" -C <cwd>` | json-event-stream + codex parser | **鍘熺敓娌欑**锛堢孩绾垮敮涓€鍙湡璺戯級 |
| 3 | cursor-agent | `--print --output-format stream-json --stream-partial-output --force --trust --workspace <cwd>` | json-event-stream + cursor parser锛堢鏈夛級 | 鏃狅紙鍏ㄤ俊浠伙級鈫?绾㈢嚎闄嶇骇 |

- 鐧诲綍鎺㈡祴锛歝laude/codex 鍚勮嚜 CLI锛沜ursor-agent 鐢?`cursor-agent status`锛坅uth required 鏃剁粰寮曞锛夈€?
- prompt 鍏ㄩ儴缁?stdin锛圙7锛歰pen-design 娉ㄩ噴鏄庣‘涓?Windows `spawn ENAMETOOLONG` 鑰岃璁★級銆?

### 8.3 Harness prompt锛堝己鍒剁敤锛孏6锛?

鏍囧噯 harness prompt 妯℃澘瀵规瘡涓?case 娉ㄥ叆锛?

- skill 鍦?cwd锛?*蹇呴』鎸夊叾 SKILL.md 浣跨敤鏈?skill**锛?
- has_scripts 鎶€鑳斤細**蹇呴』璋冪敤澹版槑鐨?entrypoint**锛堣 搂9锛夊鐞嗘湰杈撳叆锛?*绂佹鎵嬬紪/缁曡繃 pipeline**锛?
- 鏈?case 鐨?user_intent / input_template锛?
- 鏀跺熬**鎵撳嵃涓€涓?fenced JSON**锛堝尮閰?returns_schema锛変綔缁撴瀯鍖栦骇鍑猴紙best-effort锛夈€?

---

## 9. 鍏冩暟鎹柊澧炲瓧娈碉紙G4 / G5锛?

鏀?`docs/specs/Skill鍏冩暟鎹畾涔変笌缂栧啓瑙勮寖.md` + `core/ingest.py` 瑙ｆ瀽 + 鏍￠獙锛?

| 瀛楁 | 蹇呭～ | 鍚箟 |
|------|------|------|
| `entrypoint` | has_scripts 鎶€鑳藉繀濉?| 鐪熷疄鎵ц鍏ュ彛锛堝 `scripts/run_diagnosis_pipeline.sh`锛夈€侲videnceVerifier 鐢ㄥ畠姣斿 tool_result 鎵ц鐨勫懡浠わ紙G3锛夈€傛敮鎾?a02 绫汇€屽繀椤昏蛋 pipeline 鑰岄潪鍒嗘銆嶇敤渚?|
| `execution_source` | 鍚︼紙榛樿闅?env锛?| 浣滆€呴€夋墽琛屾潵婧愶細`local`锛堟湰鍦扮湡璺戯級/ `sample_io`銆俻er-skill 浼樺厛浜?env `EXEC_SOURCE`锛圙5锛?|

---

## 10. 鍒ゅ瓙鍙屾ā寮忥紙D9 / G2锛?

鐜?`_build_case_prompt`锛坋ngine.py:983-1060锛夋槸 **doc-centric**锛堣瘎 SKILL.md 鎽樺綍 + 鍙€?sample_io锛夈€傛敼涓烘寜 `ExecResult.source` 閫夛細

| 妯″紡 | 瑙﹀彂 | rubric 鍙栧悜 |
|------|------|-------------|
| **鏍蜂緥妯″紡**锛堢幇鏈夛紝淇濈暀锛?| source=sample_io锛堝洖閫€/浣滆€呴€夛級 | 璇?SKILL.md 瀹氫箟鏄惁娓呮櫚鑷唇锛堝惈鐜版湁绾㈢嚎 doc 鍙ｅ緞锛?|
| **鎵ц妯″紡**锛堟柊澧烇級 | source=local_agent锛堢湡璺戯級 | 璇?*鎵ц缁撴灉**锛氫骇鍑烘槸鍚︾鍚?user_intent/returns_schema銆佹槸鍚︾湡璺戦€氾紙璇?tool_result/浜х墿锛夈€佺孩绾块鐪嬬湡瀹炴嫆绛旇涓?|

- 鍙屾ā鍨嬶紙DeepSeek + Gemini锛夎皟鐢ㄧ粨鏋勩€佽仛鍚堛€佸喅绛?R1鈥揜8銆乭uman_review 璺敱**鍧囦笉鍔?*銆?
- 绾㈢嚎棰樺湪鎵ц妯″紡涓嬩粎瀵?*鐪熻窇浜嗙殑**锛坈odex 鍔犲浐妗ｏ級璇勭湡瀹炶涓猴紱claude/cursor 绾㈢嚎璧版牱渚嬫ā寮忥紙G8锛夈€?

---

## 11. 瀹夊叏涓庣孩绾垮姞鍥烘。锛圵8.5 / G8锛?

- **鎵ц鍓嶅悓鎰?*锛歴pawn 鍓嶄綔鑰呮槑纭悓鎰忥紙涓€娆℃€?浼氳瘽绾э級锛屽憡鐭ャ€屽皢浠ュ叏鑷姩鏉冮檺鍦ㄦ湰鏈轰复鏃剁洰褰曡繍琛岃 skill 浠ｇ爜銆嶏紱鏈悓鎰忎笉 spawn銆?
- **鐩綍绾︽潫**锛氬叏鑷姩鏉冮檺浠呭湪 per-run clone 鐩綍锛涗笉瑙?originals / staging 姣嶆湰 / 浠撳簱鍏跺畠璺緞銆?
- **涓庣幇鏈?Security Gate 鎵撻€?*锛氳繘鍏ユ湰鍦版墽琛屽墠宸茶繃 intake 瀹夊叏鎵弿锛坄core/bundle_security.py`/`security_scan.py`锛夛紱blocked 涓嶈繘鎵ц妗ャ€?
- **鍥炰紶鏍￠獙**锛氳В鏋愬嚭鐨?actual_output 杩?output sanitizer锛堝鐢?`core/output_sanitizer.py`锛孭II/瀵嗛挜锛夈€?
- **绾㈢嚎鍔犲浐妗ｏ紙G8锛?*锛?
  - **codex**锛歚--sandbox workspace-write` + `network_access=false` + `default_permissions=":workspace"` 鈫?绂佸鑱?+ 闄?fs锛岀孩绾块鐪熻窇銆?
  - **claude / cursor-agent**锛氬師鐢熸棤缃戠粶/fs 绾︽潫锛坄bypassPermissions` / `--force --trust`锛夛紝鍘熺敓 Windows 鏃犲鍣?鈫?**绾㈢嚎棰樿嚜鍔ㄩ檷绾?doc-centric**锛屾姤鍛婃爣鏄庡師鍥犮€?
  - happy/edge 涓?agent 鍧囩湡璺戙€?

---

## 12. 淇′换妯″瀷锛圖6 / G10锛屽垎闃舵锛?

| | v1锛堢幇鍦級 | 鐩爣鎬侊紙澶氱敤鎴?涓婁簯鍚庯級 |
|--|-----------|------------------------|
| 鍦烘櫙 | 鍚屾満銆佸唴閮ㄥ憳宸ャ€佷綔鑰呮湰浜哄湪鑷繁鏈哄櫒璺?| 寮曞叆涓嶅彲淇＄涓夋柟 |
| 淇′换 | **淇′换鏈湴**锛歫udge锛堝弻妯″瀷璇?transcript锛塸ass鈫扨ASS锛?*鎶芥绾汉宸ヤ絾 PASS 鏍?`spot_check_eligible` 涓?history 鍙瓫**锛圙10锛?| 鍏綉棰樹腑澶?agent 澶嶈窇楂橀闄╁瓙闆嗭紱鍐呯綉棰樹笓瀹剁鏀?|
| 浼€犻闄?| 銆屽凡鐭ユ殏鍙椼€嶏紙鍚屾満/浣滆€呰瘎鑷繁 skill锛屽姩鏈轰綆锛夛紱闈犺涔夋牎楠?+ 瀹夊叏 gate + 鍙瓫鎶芥缂撹В | 涓ぎ澶嶆牳/绛炬敹鏀剁揣 |

- v1 涓嶆敼 R1鈥揜8 涓?human_review 璺敱锛歸arn / R5 浠嶈繘涓撳銆?
- v1 鏂板鍙槸銆屾湰鍦扮湡璺戜骇鍑?+ 鎵ц妯″紡璇勫垎銆嶅杺缁?judge锛沺ass 璧扮幇鏈夌粓鎬併€?

---

## 13. 闄嶇骇鐭╅樀锛圖5锛?

| 鎯呭喌 | 琛屼负 |
|------|------|
| 鏈娴嬪埌鏈湴 agent / 浣滆€呴€?sample_io | 鏁磋疆璧?`SampleIoSource`锛堟牱渚嬫ā寮忚瘎锛屾爣浣庣疆淇★紝level_1锛?|
| agent 鏈櫥褰曪紙auth 缂哄け锛?| 鍥為€€ + 鎻愮ず浣滆€呭幓 CLI 鐧诲綍鍚庨噸璇?|
| 绾㈢嚎棰?+ claude/cursor锛堟棤鍔犲浐妗ｏ紝G8锛?| 璇ョ孩绾块闄嶇骇 doc-centric锛堟牱渚嬫ā寮忥級锛屾姤鍛婃爣鍘熷洜 |
| has_scripts 浣嗘棤 entrypoint 鎵ц璇佹嵁锛圙3锛?| 璇ラ鍥為€€ sample_io锛堣嫢鏈夛級锛涘惁鍒欐爣 `incomplete` 涓嶈 pass |
| 鍗曢瓒呮椂 / exec fail | 鍥為€€璇ラ sample_io锛堣嫢鏈夛級锛涘惁鍒?`incomplete`锛?*宸查攣锛屄?6 鈶?鍏抽棴**锛?|
| 闄愭祦鎸佺画澶辫触锛圙11锛?| 閫€骞跺彂鍒?1 + 閫€閬垮悗浠嶅け璐?鈫?璇ラ杩涗笂杩板け璐ュ垎鏀?|
| 鍏ㄩ儴澶辫触 | 绛夊悓鐜版湁 sample_io 璺緞锛屽姛鑳戒笉閫€鍖?|

---

## 14. v1 鑼冨洿涓?YAGNI

**鍋?*锛氬悓鏈哄師鐢?Windows spawn锛涗笁 agent锛坈laude鈫抍odex鈫抍ursor-agent锛夛紱娴佽В鏋愬洖浼狅紱姣忛闅旂 + 骞跺彂 2 + 闄愭祦閫€閬匡紱per-run clone锛汦xecutionSource 鎺ョ紳 + 鍥為€€ + per-skill 鏉ユ簮锛涙墽琛屾ā寮?prompt锛沞ntrypoint/execution_source 鍏冩暟鎹?+ 璇佹嵁鏍￠獙锛涚孩绾垮姞鍥烘。锛坈odex锛?闄嶇骇锛坈laude/cursor锛夛紱v1 淇′换鏈湴 + 鍙瓫鎶芥锛涙墽琛屽墠鍚屾剰銆?

**涓嶅仛锛堟帹鍚庯級**锛?
- ~~`submit_case_output` MCP 宸ュ叿 / `SkillHubMcpServer`~~ 鈫?G1 鍒犻櫎
- 澶?agent 瀵圭収缁熻 鈫?W8.4
- 鍏綉涓ぎ澶嶆牳 / 鑷姩鍒嗙骇 PASS 鈫?鐩爣鎬?
- 缃戠粶妗?/ 涓婁簯 transport 鈫?鐩爣鎬?
- claude/cursor 绾㈢嚎瀹瑰櫒鍔犲浐锛圵SL+firejail锛夆啋 鐩爣鎬?
- hybrid 浼氳瘽鍒嗙粍 鈫?娴嬪嚭澶參鍐嶈
- 涓ぎ纭畾鎬т唬鐮佽窇 / Golden Case 鈫?闃舵鍥?W10

---

## 15. Wave 鍒嗚В锛堝榻?Sprint锛?

- **W8.0** 鏈璁＄锛坓rill 瀹氱锛夆啋 OpenSpec change
- **W8.1** 浼犺緭灞傦細claude 鈫?codex 鈫?cursor-agent锛坉etect / spawn / stdin / StreamParser锛涙棤 MCP 娉ㄥ叆锛?
- **W8.2** `ExecutionSource` 鎺ョ紳 + 娴佽В鏋愬洖浼狅紙ArtifactCollector锛? judge 鍙屾ā寮忔帴绾?
- **W8.3** per-skill 鎵ц鏉ユ簮 + 闄嶇骇鍥為€€ + 淇′换 v1锛坧ass鈫扨ASS 鏍囪鍙瓫锛? 鎺ョ幇鏈変笓瀹?缁堟€?
- **W8.4** 澶?agent 瀵圭収缁熻
- **W8.5** 瀹夊叏锛氭墽琛屽墠鍚屾剰 + 鐩綍绾︽潫 + Security Gate 鎵撻€?+ output sanitizer + 绾㈢嚎鍔犲浐妗ｏ紙codex锛?闄嶇骇锛坈laude/cursor锛?
- **W8.6** 鍙墽琛?fixture + entrypoint 璇佹嵁鏍￠獙 + 涓?agent 绔埌绔獙鏀?+ `docs/runbooks/local-agent-exec-validation.md`

> 鍏冩暟鎹瓧娈碉紙entrypoint / execution_source锛孏4/G5锛? 鍒ゅ瓙鍙屾ā寮忥紙G2锛? EvidenceVerifier锛圙3锛夌┛鎻掑湪 W8.2/W8.3 钀藉湴銆?

---

## 16. 椋庨櫓涓庢湭鍐?

| # | 鏈喅/椋庨櫓 | 澶勭悊 |
|---|-----------|------|
| 鈶?| ~~鍗曢澶辫触鍥為€€ vs incomplete~~ | **宸查攣**锛氭湁 sample_io 鍥為€€锛屾棤鍒?incomplete锛埪?3锛?|
| 鈶?| cursor-agent 绉佹湁 eventParser 瑙ｆ瀽澶嶆潅搴?| 鏀炬渶鍚庡仛锛涘弬鐓?open-design `emitCursorTextDelta` 鍘婚噸閫昏緫 |
| 鈶?| agent 涓嶆寜 harness prompt 璋?entrypoint | 寮哄埗 prompt + EvidenceVerifier 妫€娴嬫棤璇佹嵁 鈫?retry 涓€娆?鈫?闄嶇骇 |
| 鈶?| 鏀跺熬 fenced JSON 瑙ｆ瀽澶辫触 | best-effort锛涘け璐ュ垯鐢ㄦ枃鏈?+ tool_result + cwd 浜х墿鍚堟垚 actual_output |
| 鈶?| 闈炵‘瀹氭€у鑷?judge 澶嶈窇娉㈠姩 | 鏂█璧扮粨鏋勬€?+ 璇箟锛涘娆?澶?agent 缁熻鐣?W8.4 |
| 鈶?| 浼€?report锛坴1 淇′换鏈湴锛?| 宸茬煡鏆傚彈锛涜涔夋牎楠?+ 瀹夊叏 gate + 鍙瓫浜哄伐鎶芥锛涚洰鏍囨€佹敹绱?|
| 鈶?| claude/cursor 绾㈢嚎 v1 鏃犳硶鐪熻窇 | 鎺ュ彈锛歷1 绾㈢嚎鐪熻窇浠?codex锛涘叾浣欓檷绾?doc-centric锛岀洰鏍囨€佸鍣ㄥ姞鍥?|

---

## 17. 楠屾敹鏍囧噯

- 鏈湴 CLI agent锛坈laude/codex/cursor-agent 浠讳竴锛夌湡璺?鈮? 涓?skill锛堝惈 1 涓彲鎵ц fixture锛屽甫 `entrypoint`锛夆啋 **娴佽В鏋?*鍥炰紶鐪熷疄浜у嚭 鈫?judge **鎵ц妯″紡** 鍑?Pass/Warn/Fail銆?
- has_scripts 鎶€鑳斤細鏈?entrypoint 鎵ц璇佹嵁鎵嶈鐪熸墽琛岋紙level_2锛夛紱鏃犺瘉鎹寜闄嶇骇鐭╅樀銆?
- 浣滆€呭彲鍦?per-skill銆屾湰鍦扮湡璺?/ sample_io銆嶉棿閫夋嫨锛涙棤 agent/澶辫触鏃惰嚜鍔ㄥ洖閫€銆佸姛鑳戒笉閫€鍖栥€?
- 绾㈢嚎棰橈細codex 鍔犲浐妗ｇ湡璺戯紱claude/cursor 闄嶇骇 doc-centric 涓旀姤鍛婃爣鍘熷洜銆?
- v1锛歫udge pass 鈫?PASS锛堟爣 `spot_check_eligible`锛宧istory 鍙瓫锛夛紱warn/R5 鈫?涓撳銆?
- 鐜版湁 524 tests + fixture 涓変欢濂椾笉鍥炲綊銆?
- 涓?agent 鍚勮窇閫氫竴娆″悓涓€ fixture锛圵8.4 鍐嶅仛瀵圭収缁熻锛夈€?
