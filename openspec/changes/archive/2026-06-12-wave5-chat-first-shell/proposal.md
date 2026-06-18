# Proposal: Wave 5 鈥?Chat-First 瀵硅瘽澹筹紙Conversational Shell锛?
## What

灏?SkillHub 浣滆€呭叆鍙ｄ粠 **銆岃〃鍗?+ 鍙屾爮浠〃鐩?+ 绗笁 Tab 涓撳鍙般€?* 閲嶆瀯涓?**銆孋hatGPT 寮忓璇濅骇鍝併€?*锛?
1. **鍏ㄥ睆瀵硅瘽涓荤晫闈?* 鈥?宸︿晶浼氳瘽鍒楄〃 + 涓ぎ娑堟伅娴?+ 搴曢儴 Composer锛?*ZIP 涓婁紶**涓轰富锛涙湰鍦拌矾寰勪粎 Demo 寮€鍏筹級
2. **涓婁紶涓庤瘎浼板叏绋嬪湪瀵硅瘽鍐呭畬鎴?* 鈥?Agent 寮曞 鈫?鎺ユ敹 bundle 鈫?鑷姩璺?pipeline 鈫?**浠?Rich Message 姘旀场鎺ㄩ€佸畬鏁存姤鍛?*
3. **浜や簰鍔ㄤ綔鍐呭祵娑堟伅** 鈥?銆愭暣鍖呯‘璁ゃ€戙€佷笓瀹舵壒鍑?椹冲洖绛変互 **娑堟伅鍐?Action Chips** 鍛堢幇
4. **鍙岃瑙掑悓涓€椤甸潰** 鈥?銆屼綔鑰?/ 涓撳銆嶆ā寮忓垏鎹紙瑙?design 搂4.5 warn 澶嶆牳娴佺▼锛?5. **浠呬袱涓《灞?Tab** 鈥?**瀵硅瘽璇勪及** | **璇勪及鍘嗗彶**锛堝巻鍙查』鑳?**鏌ヨ瀵硅瘽鎽樿 + 璺冲洖瀹屾暣浼氳瘽**锛岃 D7锛?6. **鍚庣钖勬墿灞?* 鈥?浼氳瘽鍒楄〃 API銆丷ich Message銆佺粓鎬?report 姘旀场銆乧hat 鍐?bootstrap锛?*涓嶉噸鍐?* Engine / LUI 鏍稿績

## Why

Wave 4 浜や粯浜?LUI 鍐呮牳涓?`/conversations/*` API锛屼絾 UI 浠嶆槸 **鍐呴儴杩愯惀纭鍙?* 褰㈡€侊細

- 鐢ㄦ埛蹇呴』鍏堝～琛ㄥ崟鎵嶈兘杩涘叆鑱婂ぉ
- 鎶ュ憡娓叉煋鍦ㄥ彸渚у浐瀹氬崱鐗囷紝涓庢秷鎭祦鍓茶
- 涓撳瀹℃牳鐙珛 Tab锛屼綔鑰呮棤娉曞湪鍚屼竴瀵硅瘽鏃堕棿绾块噷鐪嬪埌銆屽緟瀹?鈫?宸查€氳繃/宸查┏鍥炪€嶉棴鐜?- 鍒锋柊鍚庝細璇濅笌鍘嗗彶涓ゆ潯绾匡紝涓嶅儚杩炵画瀵硅瘽浜у搧

浜у搧鐩爣锛圧ECORD / 闃舵涓夛級寮鸿皟 **LUI 闄嶄綆闈炴妧鏈憳宸ラ棬妲?*锛汣hat-First 澹虫槸鎶婂凡鏈夊紩鎿庤兘鍔涘寘瑁呮垚 **鍗曚竴瀵硅瘽鏅鸿兘浣?* 浣撻獙銆?
## 宸查攣瀹氬喅绛栵紙2026-06-10 鐢ㄦ埛纭锛?
| 缂栧彿 | 鍐虫柇 |
|------|------|
| D1 | 椤跺眰浠?**2 Tab**锛氬璇濊瘎浼?+ 璇勪及鍘嗗彶锛?*绉婚櫎鐙珛涓撳瀹℃牳 Tab** |
| D2 | 鍚屼竴椤甸潰 **浣滆€?/ 涓撳瑙嗚鍒囨崲**锛堥潪绗笁 Tab锛夛紱warn / 浜哄伐寰呭鐢卞悗绔褰曪紝UI 鍦ㄤ笓瀹惰瑙掑憟鐜版搷浣?|
| D3 | **宸︿晶浼氳瘽鍒楄〃**锛堝彲鏂板缓 / 鍒囨崲澶氫釜 Skill 涓婁紶瀵硅瘽锛?|
| D4 | Composer **榛樿浠?ZIP 涓婁紶**锛堭煋?闄勪欢锛夛紱**鏈湴璺緞浠?Demo**锛堣 D8锛?|
| D5 | 璇勪及鎶ュ憡浠?**鍗曟潯 Rich Message 姘旀场** 鍐呭祵瀹屾暣鍗＄墖锛堝彲鎶樺彔锛?|
| D6 | **鎻掗槦涓?Sprint 鏂?W5**锛涘師 Demo runbook 椤哄欢 **W5.5** |
| D7 | **璇勪及鍘嗗彶 Tab 蹇呴』鑳芥煡瀵硅瘽**锛氭瘡鏉?run 灞曠ず `conversation_id`銆佹秷鎭潯鏁般€佹渶杩戦瑙堬紱璇︽儏妯℃€佸惈 **瀵硅瘽鎽樿鍖?* +銆屾墦寮€瀹屾暣瀵硅瘽銆?|
| D8 | **姝ｅ紡浜у搧鍙 ZIP**锛沗local_ref` 浠呭紑鍙?Demo锛歚SKILLHUB_DEMO_LOCAL_REF=true` 鏃?UI 闇插嚭璺緞妗?+ API 鎺ュ彈 bootstrap local_ref锛涚敓浜?榛樿 **鍏抽棴** |
| D9 | **warn + 浜哄伐澶嶆牳** 鐨勮瑙掑垏鎹㈣鍒欒 design 搂4.5锛堥潪 grill-me 闃诲锛屽凡缁欏嚭榛樿鏂规锛?|

## 鏂囨。鍚屾 Gate锛坓rill-me 涔嬪悗銆乻ubagent 涔嬪墠锛?
**纭『搴?*锛堥伩鍏?RECORD/Sprint 涓?OpenSpec 瀹炶返鍐茬獊锛夛細

```
grill-me 闂悎 EQ* 鈫?Task 0 鍚屾 RECORD + Sprint 鈫?Task 1鈥? 瀹炵幇 鈫?褰掓。鍓?Task 7 缁堟
```

- **Task 0**锛堜粎鏂囨。锛夛細鎸夊凡瀹氱鐨?`proposal/design/tasks` 鏇存柊 `RECORD.md` + `SPRINT_phase3-marketplace.md`锛圵ave 5 鏇挎崲銆乄5.5 Demo銆佸垹闄?鍙栦唬 W4 鍙屾爮 UI 鎻忚堪銆丏8 Demo 寮€鍏筹級
- **绂佹**锛氬湪 grill-me 鏈畬鎴愭椂鏀?RECORD 鍐崇瓥琛紱鍦?Task 0 鏈畬鎴愭椂鍚姩 Task 1 浠ｇ爜

## 寰?grill-me 鏄庣‘锛堝疄鐜板墠蹇呴』闂悎锛?
| 缂栧彿 | 闂 | 榛樿鍊惧悜锛堝彲鎺ㄧ炕锛?|
|------|------|-------------------|
| **EQ1** | 涓撳瀹℃牳鏄惁鍏佽 **涓婁紶鑰呮湰浜?* 鍦ㄤ笓瀹惰瑙掕嚜鎵癸紵 | **鍏佽鑷壒**锛圡VP锛夛紱`human_review.operator` 璁板綍鎿嶄綔鑰咃紱**闃舵鍥?IAM 鍐嶇粏鍖栧鎵硅鍒?*锛堢敤鎴?2026-06-10锛?|
| **EQ2** | Skill ID 鏉ユ簮 | **绾璇濓紙B锛?* + 鑷姩璇嗗埆锛埪?.8锛夛紱**EQ2b**锛氱敤鎴锋湭璇存槑鏃?**SKILL.md 浼樺厛**锛寊ip 鍚嶅厹搴曪紱璇嗗埆鎴愬姛鍚?**Agent 鍚戠敤鎴风‘璁ゅ悕绉?*锛岀敤鎴疯偗瀹氬悗鍐嶅紑璇?|
| **EQ3** | Rich Report 娑堟伅鐢?**鏈嶅姟绔?* 鍦?run 缁堟€佸啓鍏?`lui_messages`锛岃繕鏄?**鍓嶇** 娓叉煋鍚庡洖鍐欙紵 | **鏈嶅姟绔啓鍏?*锛堝埛鏂?澶氱涓€鑷达紱鍘嗗彶 Tab 璺冲洖瀵硅瘽鍙鐜帮級 |
| **EQ4** | 鍘?Debug 闈㈡澘锛坄/eval/run` 鎵嬪伐瑙﹀彂锛?| **鍒犻櫎榛樿 UI**锛涗繚鐣?Swagger/CLI 渚涘紑鍙戯紝涓嶅湪 Chat 澹虫毚闇?|
| **EQ5** | 涓撳瑙嗚涓嬪緟瀹￠槦鍒楋細浠呭綋鍓嶄細璇?vs 鍏ㄥ眬寰呭鍒楄〃宓屽叆渚ф爮 | **渚ф爮銆屽緟浜哄伐銆嶅垎缁?*锛堣法浼氳瘽 badge + 鐐瑰嚮璺宠浆璇ュ璇濓級 |

## Non-goals

- 涓嶆敼 1.2 闃堝€硷紙85/70/90 / R5 10 鍒嗙嚎锛?- 涓嶉噸鍐?`EvaluationEngine`銆乣LuiAgent` 鎰忓浘/patch 鍗忚銆乣StagingWriter` 璺敱
- 涓嶅疄鐜?W6 闆嗗競 / publish / listing
- 涓嶅仛 IAM / SSO / 鐪熷疄涓撳鏉冮檺浣撶郴锛堜粎 UI 瑙嗚鍒囨崲 + operator 瀛楃涓诧級
- 涓嶅仛澶?Skill 鍚屼竴浼氳瘽
- 涓嶅湪鏈?change 鍐?Demo runbook锛堥『寤?W5.5锛?
## Relation to Sprint

- **渚濊禆**锛歐ave 4 鉁咃紙367 tests锛宍wave4-lui-agent` 搴斿厛褰掓。鎴栦笌鏈?change 骞惰鍚堝苟锛?- **鍙栦唬**锛歐ave 4 **T7 鍙屾爮 UI** 鐨勪骇鍝佸舰鎬侊紙鍚庣 API 澶嶇敤锛?- **椤哄欢**锛歚.project_memory/active/SPRINT_phase3-marketplace.md` 鍘?Wave 5 Demo 鈫?**Wave 5.5**
- **涓嶉噸澶?*锛歋print W0鈥揥4 鍚庣娓呭崟锛汷penSpec tasks 浠呰鐩?Chat Shell + 蹇呰 API/DB 鎵╁睍

## Success Criteria

1. 鎵撳紑銆屽璇濊瘎浼般€嶅嵆瑙?**浼氳瘽鍒楄〃 + 鑱婂ぉ鍖?*锛屾棤銆屽厛濉〃鍐嶅紑濮嬨€嶉棬妲?2. 鏂颁細璇濓細Agent 娆㈣繋 鈫?鐢ㄦ埛鎻愪緵 Skill ID + 璺緞鎴?ZIP 鈫?鑷姩 `start` + 鍒濊瘎 鈫?**Rich Report 姘旀场**鍑虹幇鍦ㄦ秷鎭祦
3. gap 鏈竻闆?/ 闇€琛ュ叏锛欰gent 鏂囧瓧璇存槑 + 鐢ㄦ埛缁х画鑱婏紱婊¤冻闂ㄧ鍚庢秷鎭唴鍑虹幇 **銆愭暣鍖呯‘璁ゃ€?* chip
4. `human_review_required` + warn锛氫綔鑰呰瑙掑彧璇?+ 绯荤粺娑堟伅锛?*鎸?搂4.5 鍒囨崲涓撳瑙嗚** 瀹屾垚鎵瑰噯/椹冲洖锛涚粨鏋滄秷鎭洖鍒?**鍚屼竴浼氳瘽**锛涙搷浣滃悗鍙嚜鍔ㄥ垏鍥炰綔鑰?5. 銆岃瘎浼板巻鍙层€峊ab锛歳un 琛屽惈瀵硅瘽瀛楁锛涜鎯呭惈 **瀵硅瘽鎽樿** + **鎵撳紑瀹屾暣瀵硅瘽**锛堣烦 Tab1 骞堕€変腑浼氳瘽锛?6. 榛樿 Composer **浠?ZIP**锛沗SKILLHUB_DEMO_LOCAL_REF=true` 鏃跺彲閫夋湰鍦拌矾寰勶紙Demo 鍔犻€燂級
7. `pytest tests/ -x --tb=short` 鍏ㄧ豢锛堚墺367 + W5 鏂版祴璇曪級

## Workflow 涓嬩竴姝?
1. **grill-me** 鈥?闂悎 EQ1鈥揈Q2 绛夋湭鍐抽」锛圖7/D8/D9 宸查攣瀹氾紝涓嶈繘 grill-me锛?2. **Task 0** 鈥?鍚屾 RECORD + Sprint锛?*subagent 浠ｇ爜鍓嶅繀鍋?*锛?3. **subagent-driven-development** 鈥?Task 1鈥?
4. Wave 4 褰掓。 + 鏈?change 褰掓。鍚?鈫?**W5.5 Demo runbook**锛堝叏瀵硅瘽璺緞 + Demo 鏈湴璺緞鍓ф湰锛?