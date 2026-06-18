# Tasks: Wave 5.1 鈥?鑱婂ぉ绠€鍗?+ 鎶ュ憡鍒嗘祦 + 鍒濊瘎璇濇湳娴?

> **鍓嶇疆**锛歚wave5-chat-first-shell` 宸茶惤鍦帮紙400 tests锛夈€?*grill-me** 鉁?GQ1鈥揋Q7锛?026-06-10锛夈€?

---

## Task 0 鈥?鏂囨。瀵归綈锛堝疄鐜板畬鎴愬悗锛?

**鏂囦欢**锛歚RECORD.md`銆乣.project_memory/active/SPRINT_phase3-marketplace.md`

**瑕佺偣**锛?
- [x] 鏂板 Wave 5.1 鍐崇瓥锛氬彇娑堜富璺緞鏁村寘纭銆丆2銆佹柟鍚?A銆佽崏妗堢‘璁ゆ祦
- [x] 淇 W5 Success Criteria #3 鎻忚堪锛堝凡琚?W5.1 鍙栦唬锛?
- [x] W5.5 Demo smoke 澧炪€屽垵璇勬棤鍒?/ 鑷姩姝ｅ紡 / 鍘嗗彶璇︽儏銆嶆潯鐩?

---

## Task 1 鈥?DB v4 `pending_patch_json` + quota 浠呰 capability_full

**鏂囦欢**锛?
- `skillhub_eval/persistence/sqlite.py`
- `skillhub_eval/core/ports.py`
- `skillhub_eval/core/staging_writer.py`
- `tests/persistence/test_wave5_1_pending_patch.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `SCHEMA_VERSION = 4`锛沗conversations.pending_patch_json`
- [x] `increment_auto_run_count` 浠?capability_full 璺緞璋冪敤锛圙Q6锛?
- [x] get/set/clear `pending_patch_json`

**楠屾敹**锛?
```bash
pytest tests/persistence/test_wave5_1_pending_patch.py -x --tb=short
```

---

## Task 2 鈥?rich_report 鍒嗛樁娈?payload + 鑷姩姝ｅ紡璇勪及閽╁瓙

**鐩爣**锛歚report_phase`銆佺畝鍗″瓧娈碉紱鍒濊瘎鏃犵己鍙ｈ嚜鍔?`auto_confirmed` + `capability_full`銆?

**鏂囦欢**锛?
- `skillhub_eval/core/chat_notifications.py`
- `skillhub_eval/core/engine.py`锛堟垨 notifications 鍐呴挬瀛愶級
- `tests/core/test_chat_notifications.py`

**瑕佺偣**锛?
- [x] `initial` / `formal` / `formal_pending_review`
- [x] `headline_zh`, `summary_one_liner`, `score_line_html`锛堝垵璇?null锛?
- [x] `maybe_auto_start_formal_eval` 鈥?浠?degraded 缁堟€?+ gap_zero + case_gate
- [x] 绉婚櫎 payload `actions` 涓?`confirm_all`锛堜富璺緞锛?

**楠屾敹**锛?
```bash
pytest tests/core/test_chat_notifications.py -x --tb=short
```

---

## Task 3 鈥?浼氳瘽鐘舵€?`awaiting_draft_confirm` + session gate

**鐩爣**锛氳崏妗堝睍绀哄悗銆佺敤鎴风‘璁ゅ墠绂佹鍐?staging銆?

**鏂囦欢**锛?
- `skillhub_eval/adapters/api/_session.py`
- `skillhub_eval/adapters/api/routes/chat.py`
- `tests/adapters/test_chat_wave5_1_draft_gate.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `awaiting_draft_confirm` 鍏佽 explain锛沵utation 闇€纭鎰忓浘
- [x] 鏈‘璁?mutation 鈫?403 + 鐧借瘽 detail

**楠屾敹**锛?
```bash
pytest tests/adapters/test_chat_wave5_1_draft_gate.py -x --tb=short
```

---

## Task 4 鈥?LuiAgent 鍒濊瘎/姝ｅ紡鍙欎簨 + 鑽夋娴侊紙pending_patch锛?

**鐩爣**锛歀LM 鐧借瘽璇存槑锛涜崏妗?explain_only锛涚‘璁ゅ悗鎵?patch銆?

**鏂囦欢**锛?
- `skillhub_eval/core/lui_agent.py`
- `tests/core/test_lui_agent.py`

**瑕佺偣**锛?
- [x] `compose_post_initial_narrative` / `compose_post_formal_narrative`
- [x] gaps vs case_gate prompt 鍒嗗弶锛坉esign 搂3.3锛?
- [x] 鐢熸垚鐧借瘽 + **鍚屾鍐欏叆 `pending_patch_json`**
- [x] 纭 鈫?apply 瀛樼洏 patch锛?*涓?*浜屾 LLM
- [x] 淇敼鎰忚 鈫?鏇存柊鐧借瘽 + pending_patch
- [x] 娑堟伅椤哄簭锛氬彊浜?**鍏堜簬** rich_report锛圙Q4锛?

**楠屾敹**锛?
```bash
pytest tests/core/test_lui_agent.py -x --tb=short
```

---

## Task 5 鈥?UI 涓夊绠€鍗?+ 鎶ュ憡 CTA + 杞淇

**鐩爣**锛氳亰澶╃畝鍗★紱璺宠浆鍘嗗彶璇︽儏锛涚Щ闄ゆ暣鍖呯‘璁?chip锛涗慨澶嶇鏀躲€?

**鏂囦欢**锛?
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/api/test_ui.py`

**瑕佺偣**锛?
- [x] `renderReportHtml` 鎸?`report_phase` 鍒嗘敮锛圕2锛?
- [x] `openReportFromChat(runId)` 鈫?history + modal
- [x] 鍒犻櫎鑱婂ぉ鍐呴暱鎶樺彔鍧?/ confirm_all chip
- [x] 杞锛氬閲忔洿鏂版垨鍘绘帀鑱婂ぉ `<details>`

**楠屾敹**锛?
```bash
pytest tests/api/test_ui.py -x --tb=short
```

---

## Task 6 鈥?闆嗘垚娴嬭瘯 E2E

**鏂囦欢**锛歚tests/integration/test_wave5_1_report_split.py`锛堟柊寤猴級

**鍓ф湰**锛?
1. ZIP 鍒濊瘎鏃犵己鍙?鈫?鏃?confirm chip 鈫?鑷姩绗簩涓?run `capability_full`
2. 鏈夌己鍙?fixture 鈫?鑽夋娑堟伅 鈫?鏈‘璁?mutation 403 鈫?纭鍚?patch 鈫?鍐嶅垵璇?
3. 姝ｅ紡璇勪及绠€鍗″惈鍒嗘暟琛岋紱鍒濊瘎涓嶅惈
4. CTA `openRunDetail` 鏁版嵁閾撅紙API 灞?assert conversation + report锛?

**楠屾敹**锛?
```bash
pytest tests/integration/test_wave5_1_report_split.py -x --tb=short
```

---

## Task 7 鈥?鍏ㄩ噺鍥炲綊

**楠屾敹**锛?
```bash
pytest tests/ -x --tb=short
```

**鎵嬪伐 smoke**锛?
- [ ] grill-me ZIP锛氬垵璇勭畝鍗℃棤鍒嗘暟锛汱LM 璇存槑缁撴瀯閫氳繃锛涜嚜鍔ㄦ寮忚瘎浼帮紙W5.5 鎵ц锛?
- [ ] 鏈夌己鍙ｆ牱鏈細鍏堢湅鑽夋鏂囧瓧锛屽洖澶嶇‘璁ゅ悗鎵嶅啓鍏ワ紙W5.5 鎵ц锛?
- [ ] 姝ｅ紡瀹屾垚锛氱畝鍗℃湁鍒?+ 鐐瑰嚮璺宠浆鍘嗗彶璇︽儏鍏ㄩ噺鎶ュ憡锛圵5.5 鎵ц锛?
- [ ] 寰呬笓瀹讹細浣滆€呭彧璇?+ 涓撳鎵瑰噯锛圵5 搂4.5锛夛紙W5.5 鎵ц锛?

---

## 渚濊禆鍥?

```
Task1 鈫?Task2 鈫?Task3 鈭?Task4 鈫?Task5 鈫?Task6 鈫?Task7 鈫?Task0
```

## 宸查棴鍚堝喅绛?

| ID | 鍐宠 |
|----|------|
| R1鈥揜8 | 瑙?proposal |
| GQ1 | 鍥哄畾 pending_patch锛岀‘璁ゅ師鏍峰啓鍏?|
| GQ2 | warn 涓嶆嫤鑷姩姝ｅ紡 |
| GQ3 | pending_patch 钀藉簱 |
| GQ4 | 鍏?LLM 鍚庣畝鍗?|
| GQ5 | 棰濆害闈?badge |
| GQ6 | 浠?capability_full 璁￠搴?|
| GQ7 | 鍒濊瘎 = degraded 缁堟€?|
