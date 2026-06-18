# Proposal: Wave 5.2 鈥?UI 閫忔槑鍖?+ 琛ラ纭 + 鍏ㄥ璇濇緞娓?

## What

鍦?**Wave 5.1**锛?13 tests锛夊凡钀藉湴鍩虹涓婏紝淇 W5.5 Demo 鏆撮湶鐨?**閫忔槑鍖栦笌淇′换** 闂锛屽苟閿佸畾鏂颁竴杞氦浜掑喅绛栵細

1. **琛ラ鏆傚仠 + 璁″垝琛紙UI-B3锛?* 鈥?缂?`eval_cases` / `sample_io` 鏃?**涓嶉潤榛?Propagator**锛涘睍绀?**琛ㄦ牸鍖栬ˉ棰樿鍒?*锛堥鍨嬨€佹暟閲忋€佹祴浠€涔堛€佷笟鍔￠鏈燂級锛涚敤鎴烽€夋嫨璺緞鍚庡啀鍐?staging銆?
2. **涓夌琛ラ鏂瑰紡** 鈥?鏂瑰紡涓€锛堥粯璁わ級鑷閲嶄紶 ZIP锛涙柟寮忎簩銆屽府鎴戝湪瀵硅瘽閲岃ˉ銆嶁啋 W5.1 鑽夋娴侊紱鏂瑰紡涓夈€岀‘璁ゃ€嶁啋 绯荤粺鑷姩鍑洪锛坄prop_*`锛夈€?
3. **鍏ㄥ璇濇緞娓咃紙UI-S2锛?* 鈥?瀵?Skill 璁捐锛堢敤閫斻€佸彈浼椼€佽緭鍑哄舰鎬併€佽竟鐣屻€侀闄┿€乧ase 鎰忓浘锛?*鏈変换浣曚笉纭畾锛屽繀椤诲厛闂敤鎴?*锛汱uiAgent 鏂板 `clarify` intent锛岀姝綆缃俊 silent mutation / propagate銆?
4. **姝ｅ紡缁撹寰芥爣锛圲I-VERDICT锛?* 鈥?姝ｅ紡璇勪及绠€鍗℃樉寮?**閫氳繃 / 闇€浜哄伐澶嶆牳 / 涓嶉€氳繃**锛堜繚鐣?C2锛氬垵璇勪粛鏃犲垎鏁帮級銆?
5. **杩囩▼鍙** 鈥?`propagation_plan` / `propagation_summary` 娑堟伅绫诲瀷锛汸ropagator 鎽樿鍐欏叆瀵硅瘽锛涗慨璁?bootstrap 娴佺▼锛坉eferred propagation锛夈€?
6. **鍒濊瘎鐦﹁韩锛圙Q12鈥揋Q13锛?* 鈥?`degraded` 鍒濊瘎浠?**鍑嗗叆浣撴**锛堝畨鍏?+ 瑙勫垯椋庨櫓 + 缁撴瀯缂哄彛 + 棰樺瀷闂ㄦ + 瀹屾暣搴︼級锛?*涓嶈窇**鍙屾ā鍨嬮€愰璇勫銆?*涓嶈窇**椋庨櫓 AI 鈶紱**涓嶈惤**鍏ㄩ噺 `EvaluationReport`锛涚粨鏋?**鏁存潯娑堟伅鑷寘鍚?*锛?*鏃?*銆屾煡鐪嬪畬鏁存姤鍛娿€岰TA銆?
7. **姝ｅ紡绠€鍗″寮猴紙GQ14锛?* 鈥?缁撹 + 涓€鍙ユ憳瑕?+ **涓嬩竴姝ユ寚寮?*锛堝彲涓婃灦 / 闇€浜哄伐 / 鏈€氳繃璇蜂慨鏀癸級+ 鏌ョ湅瀹屾暣鎶ュ憡锛堜粎姝ｅ紡锛夈€?

## Why

W5.1 瑙ｅ喅浜嗐€岃亰澶?vs 鎶ュ憡鍒嗘祦銆嶅拰銆岃崏妗堢‘璁ゃ€嶏紝浣?Demo锛坓rill-me 绛夛級鏆撮湶锛?

| 鍙嶉 ID | 鐜拌薄 |
|---------|------|
| FB-01 | Pass 鍚庡璇濇棤鏄庣‘銆岄€氳繃銆嶇粨璁猴紝浠呭垎鏁?|
| FB-02 | 缂?eval_case 鏃?Propagator **闈欓粯**鎵ц锛岀敤鎴蜂笉鐭ュ師鍖呯己浠€涔堛€佺郴缁熻ˉ浜嗕粈涔?|
| FB-03 | 銆岀粨鏋勬鏌ュ凡閫氳繃銆嶈繃绮楋紝鑷姩姝ｅ紡璺緞鏃犺繃绋嬪彊浜?|
| FB-04 | 宸ヤ綔鍙颁俊鎭潡绉婚櫎鍚庯紝瀵硅瘽鍐呮棤绛変环銆屾竻鐐?/ 鏉ユ簮 / 琛ラ銆嶈妭鐐?|
| FB-05 | 銆岀郴缁熷仛浜嗕粈涔?鈫?鐢ㄦ埛鍋氫粈涔?鈫?缁撹鏄粈涔堛€嶄笁娈靛紡鏂 |

**鏍瑰洜**锛氳嚜鍔ㄥ姩浣滐紙Propagator銆乤uto formal锛変笌瀵硅瘽鍙欎簨鑴辫妭锛汣hat-First 鍋氫簡淇℃伅鍑忔硶锛屾湭閲嶅缓 **鐭ユ儏鍚屾剰** 鑺傜偣銆?

**璁捐婧?*锛歚docs/superpowers/specs/2026-06-10-chat-ui-transparency-design.md`锛坆rainstorm 2026-06-10锛岀敤鎴峰凡瀹￠槄 OK锛夈€?

## 宸查攣瀹氬喅绛栵紙2026-06-10锛?

| 缂栧彿 | 鍐虫柇 |
|------|------|
| **UI-B3** | 缂洪 **鏆傚仠**锛涜ˉ棰樿鍒掕〃 + **涓夋柟寮?*锛涢粯璁よ嚜琛ラ噸浼狅紱銆屽府鎴戝湪瀵硅瘽閲岃ˉ銆嶁啋 鑽夋锛涖€岀‘璁ゃ€嶁啋 Propagator |
| **UI-TBL** | 琛ㄦ牸鍒楋細棰樺瀷 / 闇€琛ヂ峰凡鏈?/ 娴嬩粈涔?/ 涓氬姟棰勬湡锛坄case_template_hint`锛? sample_io 琛?|
| **UI-S2** | **鍏ㄥ璇濈敓鍛藉懆鏈?*涓嶇‘瀹氬垯闂紱`clarify` intent锛汱0 瑙勫垯 + L1 LLM |
| **UI-CLARIFY-L0** | category 缂哄け銆乨escription 杩囩煭銆乺isk 涓嶇銆佸寘杩囩┖绛?鈫?鏈€澶?3 闂紝闃诲鍐欑洏 |
| **UI-CLARIFY-L1** | 姝т箟 / 浣庣疆淇?鈫?`clarify`锛岀姝?mutation / Propagator |
| **UI-VERDICT** | 姝ｅ紡绠€鍗?`verdict_zh` + 寰芥爣锛涘垵璇勪粛鏃犲垎锛圵5.1 C2 淇濇寔锛?|
| **UI-3WAY** | 姣忔潯璁″垝娑堟伅璇存槑涓夋柟寮?+ 銆屼篃鍙洿鎺ヨ亰浣跨敤鍦烘櫙銆?|

## Non-goals

- 绗笁 Tab銆屽寘鐘舵€併€?
- 淇敼 1.2 闃堝€?/ R5 10 鍒嗙嚎锛堟寮忚瘎浼颁粛鐢ㄧ幇鏈?DecisionStage锛?
- Propagator 鍑洪绠楁硶澶ф敼锛堜粎瑙﹀彂鏃舵満 + clarifications 娉ㄥ叆锛?
- W6 闆嗗競 / publish / IAM
- 鏈?change 涓嶅啓 W5.5 runbook 鍏ㄦ枃锛堝彲鏇存柊 smoke 鏉＄洰锛?

## Relation to Sprint / prior changes

- **渚濊禆**锛歚wave5.1-chat-report-split` 鉁咃紙413 tests锛?
- **淇**锛歐3 Propagator銆屼笂浼犲嵆闈欓粯鍑洪銆嶁啋 **鐢ㄦ埛纭鍚庡嚭棰?*锛涘叏鏅鏄?搂3 / 搂4.4 娴佺▼鍥鹃渶鍚屾
- **Sprint**锛歚.project_memory/active/SPRINT_phase3-marketplace.md` Wave 5.2 鏉＄洰
- **鍙傝€?spec**锛歚docs/superpowers/specs/2026-06-10-chat-ui-transparency-design.md`

## Success Criteria

1. 缂?eval_case 鐨?ZIP锛?*鏃?run_id**锛涘璇濆嚭鐜?`propagation_plan`锛泂taging **鏃?* `prop_*` 鐩磋嚦鐢ㄦ埛銆岀‘璁ゃ€?
2. 璁″垝琛ㄥ惈 sample_io 琛?+ 涓夋柟寮忚鏄?+ 浜ゆ祦寮曞
3. L0 瑙﹀彂鏃跺厛婢勬竻鍐嶅睍绀哄畬鏁磋〃锛汱1 `clarify` 鏈熼棿 mutation 鈫?403
4. 銆屽府鎴戝湪瀵硅瘽閲岃ˉ銆嶈繘鍏?W5.1 `awaiting_draft_confirm`锛涖€屾垜鑷繁琛ャ€嶅彲閲嶄紶 ZIP 閲嶆柊娓呯偣
5. Propagator 鎵ц鍚?`propagation_summary` 娑堟伅鍒楀嚭鍐欏叆鏂囦欢
6. 姝ｅ紡绠€鍗★細`verdict_zh` + `next_action_zh` + 鎽樿 + CTA 瀹屾暣鎶ュ憡锛涘垵璇?**鏃?* rich_report銆?*鏃?* 鎶ュ憡 CTA
7. 鍒濊瘎 run锛氬紩鎿?**鏃?* `model_judging` 闃舵锛涘璇?`readiness_result` 鍚?gaps/瀹夊叏/椋庨櫓/闂ㄦ/瀹屾暣搴?涓嬩竴姝?
8. `pytest tests/ -x --tb=short` 鍏ㄧ豢锛堚墺413 + W5.2 鏂版祴璇曪級

## grill-me 宸查棴鍚堬紙2026-06-10锛?

| 缂栧彿 | 鍐宠 |
|------|------|
| **GQ1** | **A**锛氬彧瑕佺己浠讳綍棰樺瀷鏁伴噺锛堝惈銆屽凡鏈?1 缂?2銆嶏級锛屼竴寰嬫殏鍋滃嚭琛?+ 涓夐€変竴 |
| **GQ2** | **A**锛氥€岀‘璁ゃ€嶇瓑鑷劧璇█闈?**conversation.status 纭垎娴?* + **LLM 杞瘑鍒?*鍚屼箟琛ㄨ堪锛涘啓鐩?Propagator 浠?status 鍏佽鏃舵墽琛?|
| **GQ3** | **C**锛氳ˉ棰樿〃涓?L0 婢勬竻 **鍚屼竴鏉℃秷鎭?*锛涚瓟鍚?**鍒锋柊** 琛紙涓氬姟棰勬湡鍒楁洿鏂帮級 |
| **GQ4** | **A+B**锛氶€夈€屾垜鑷繁琛ャ€嶅悗鍙瓟鐤?妯℃澘涓嶅啓鍏ワ紱鐢ㄦ埛鎻忚堪鍏蜂綋棰樼洰鏃跺彲 **鎻愯** 鍒囨柟寮忎簩 |
| **GQ5** | **B**锛氫粎 `awaiting_human_review`/鍐荤粨鏃剁畝鍗°€岄渶浜哄伐澶嶆牳銆嶏紱warn 鏃犱笓瀹?鈫?**銆岄€氳繃锛堟湁鏀硅繘寤鸿锛夈€?* |
| **GQ6** | **A**锛歀0 婢勬竻 **鍙烦杩?*锛涜烦杩囧悗涓氬姟棰勬湡鐢ㄩ€氱敤妯℃澘骞舵爣鏄?|
| **GQ7** | **A**锛氶噸浼?ZIP = **鏁村寘閲嶈浇** staging 鍚庨噸鏂版竻鐐?|
| **GQ8** | **A**锛氳嚜鍔ㄥ嚭棰樺悗鍒濊瘎鍓嶅彊浜?**蹇呴』** 鎻愬強宸茶ˉ N 閬撻 + 涓嬩竴姝?|
| **GQ9** | **B**锛氳鍒掕〃 **鍙繚鐣欐渶鏂颁竴鏉?*锛堝悓娑堟伅閫昏緫鏇存柊锛夛紝涓嶅爢澶氬紶琛?|
| **GQ10** | **B**锛氳鍒掑崱 **涓変釜 Action Chip** + 鑷劧璇█浠嶆湁鏁?|
| **GQ11** | **A**锛歨igh 椋庨櫓 refusal/adversarial **涓?* 鍦ㄦ寜閽浜屾纭锛涜〃鍐呯孩绾胯鏄庡嵆鍙?|
| **GQ12** | **R2**锛氬垵璇?= 瀹夊叏鎵弿 + **瑙勫垯**椋庨櫓閿佸畾 + gaps + case_gate + **completeness_score**锛?*璺宠繃** model_judging銆侀闄?AI 鈶€乻kill_summary LLM |
| **GQ13** | 鍒濊瘎 **涓嶅嚭鎶ュ憡**锛沗readiness_result` 娑堟伅 **鑷寘鍚叏閮ㄥ彲璇荤粨璁?*锛?*鏃?* `openRunDetail` / 鏃犲垵璇?rich_report |
| **GQ14** | 姝ｅ紡绠€鍗★細`verdict_zh` + `summary_one_liner` + `next_action_zh`锛堝彲杩涘叆涓婃灦娴佺▼ / 闇€浜哄伐 / 璇蜂慨鏀归噸璇勶級+ **浠呮寮?*淇濈暀銆屾煡鐪嬪畬鏁存姤鍛?鈫掋€?|
| **GQ15** | **B**锛氬巻鍙?Tab **涓嶅睍绀?*鍒濊瘎锛坄degraded`锛塺un锛涘垵璇勭粨璁?**浠呭湪瀵硅瘽** `readiness_result` 鍙锛涘巻鍙蹭粎鍒?`capability_full` 姝ｅ紡璇勪及 |

## Workflow 涓嬩竴姝?

1. 鐢ㄦ埛纭鏈?proposal锛?*宸插畬鎴?*锛?
2. **grill-me** 鉁?GQ1鈥揋Q11锛?026-06-10锛?
3. **subagent-driven-development** 鈥?鎸?`tasks.md`
4. Task 0 鍚屾 RECORD + Sprint + `Skill璇勪及绯荤粺鍏ㄦ櫙璇存槑.md` 搂3锛堝疄鐜板悗锛?
