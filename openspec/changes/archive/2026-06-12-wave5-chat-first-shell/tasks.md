# Tasks: Wave 5 鈥?Chat-First 瀵硅瘽澹?
> **鎵ц椤哄簭锛堢敤鎴?2026-06-10 璋冩暣锛?*锛歚grill-me` 宸查棴鍚?鈫?**Task 1鈥? 瀹炵幇** 鈫?**Task 0 鏂囨。鍚屾**锛堝疄鐜板悗鍐嶅榻?RECORD/Sprint锛岄伩鍏嶆枃妗ｄ笌浠ｇ爜鑴辫妭锛?
---

## Task 0 鈥?鏂囨。瀵归綈锛?*瀹炵幇瀹屾垚鍚?* 路 褰掓。鍓嶏級

**鐩爣**锛氬疄鐜拌惤鍦板悗鍚屾 RECORD / Sprint锛?*涓嶅啓浠ｇ爜**銆?
**鏃舵満**锛歍ask 7 鍏ㄧ豢涔嬪悗銆丱penSpec 褰掓。涔嬪墠銆?
**鏂囦欢**锛?- `RECORD.md` 鈥?鍐崇瓥琛?+ 褰撳墠鐘舵€侊紙W5 Chat-First锛沇5.5 Demo锛汥8 Demo 寮€鍏筹紱grill-me EQ*锛?- `.project_memory/active/SPRINT_phase3-marketplace.md` 鈥?Wave 5 鏇挎崲涓?Chat-First锛涘師 Demo 鈫?**W5.5**锛沇4 T7銆岃 W5 鍙栦唬銆?
**蹇呴』瀵归綈鐨勬潯鐩?*锛?- [ ] 浠?2 Tab锛堝璇?+ 鍘嗗彶锛夛紱鍘嗗彶鍚璇濇煡璇紙D7锛?- [ ] 涓婁紶榛樿 ZIP锛沗SKILLHUB_DEMO_LOCAL_REF` 鎺у埗 local_ref锛圖8锛?- [ ] 涓撳瑙嗚 搂4.5锛汼kill ID 搂4.8锛圗Q2/2b/2c锛?- [ ] Wave 4锛氬疄鐜板畬鎴?+ OpenSpec 褰掓。鐘舵€?- [ ] **绂佹** Sprint 浠嶅啓銆屼笁 Tab 涓撳鍙般€嶄负褰撳墠鐩爣

**楠屾敹**锛氱敤鎴风‘璁?RECORD + Sprint 涓庝唬鐮佸強 `openspec/changes/wave5-chat-first-shell/` 涓€鑷淬€?
## Task 1 鈥?娑堟伅妯″瀷 + 浼氳瘽鍒楄〃锛圖B v3 + Port锛?
**鐩爣**锛歚lui_messages.message_type` / `payload_json`锛沗list_conversations`锛況ich_report 骞傜瓑鏌ヨ銆?
**鏂囦欢**锛?- `skillhub_eval/core/ports.py`
- `skillhub_eval/persistence/sqlite.py`
- `tests/persistence/test_wave5_messages.py`锛堟柊寤猴級

**瑕佺偣**锛?- `SCHEMA_VERSION = 3`锛沵igration 杩藉姞涓ゅ垪
- `append_lui_message` 鎵╁睍 `message_type`, `payload_json`锛圝SON serialize锛?- `list_conversations(limit)`锛欽OIN 鏈€杩戜竴鏉?message 浣?preview锛沗human_review_pending` 鐢?active_run 璁＄畻
-  helper `has_rich_report_for_run(conv_id, run_id) -> bool`

**楠屾敹**锛?```bash
pytest tests/persistence/test_wave5_messages.py -x --tb=short
```

---

## Task 2 鈥?Rich Report 鏈嶅姟绔啓鍏?
**鐩爣**锛歳un 缁堟€佽嚜鍔ㄥ啓鍏?`rich_report` 姘旀场銆?
**鏂囦欢**锛?- `skillhub_eval/core/chat_notifications.py`锛堟柊寤猴級
- `skillhub_eval/core/engine.py`锛堢粓鎬侀挬瀛愶級
- `tests/core/test_chat_notifications.py`锛堟柊寤猴級

**瑕佺偣**锛?- `build_rich_report_payload(run_id, repo)` 鈥?瀵归綈 `GET /eval/report` 褰㈢姸
- `append_rich_report_message(conv_id, run_id, repo)` 鈥?骞傜瓑
- 鍦?`_park_awaiting_confirm` 涓?finalize 璺緞璋冪敤锛堥渶 `run.conversation_id`锛?- `actions` 鏁扮粍鍚?confirm_all / expert_* 鍏冩暟鎹紙enabled/visible_in锛?
**楠屾敹**锛?```bash
pytest tests/core/test_chat_notifications.py tests/core/test_engine.py -x --tb=short
```

---

## Task 3 鈥?API锛氫細璇濆垪琛?+ Bootstrap

**鐩爣**锛氬璇濆唴鍚姩璇勪及锛屾棤闇€鐙珛琛ㄥ崟銆?
**鏂囦欢**锛?- `skillhub_eval/adapters/api/routes/conversations.py`
- `tests/adapters/test_conversations_wave5.py`锛堟柊寤猴級

**瑕佺偣**锛?- `GET /conversations` 鈥?list + optional `pending_review=true`
- `POST /conversations/{id}/bootstrap` 鈥?**upload 榛樿**锛沗local_ref` 浠?`settings.demo_allow_local_ref`
- `POST /conversations/new` 鈥?绌轰細璇?+ welcome
- `GET /eval/history` 鎵╁睍 conversation 瀛楁 + `GET /eval/history/{run_id}/conversation`锛圖7锛?- bootstrap 鎴愬姛/澶辫触鍐?system 娑堟伅

**楠屾敹**锛?```bash
pytest tests/adapters/test_conversations_wave5.py -x --tb=short
```

---

## Task 4 鈥?API锛欳hat Multipart + Review 娑堟伅闂幆

**鐩爣**锛欳omposer 鍙?ZIP锛涗笓瀹舵搷浣滃洖鍐欏璇濄€?
**鏂囦欢**锛?- `skillhub_eval/adapters/api/routes/chat.py`
- `skillhub_eval/adapters/api/routes/eval.py`
- `tests/adapters/test_chat_wave5.py`锛堟柊寤猴級

**瑕佺偣**锛?- `POST /conversations/{id}/chat` multipart锛坢essage + bundle_zip锛?- 鏃?Demo 鏃舵嫆缁濈函鏂囨湰璺緞 bootstrap
- `settings.demo_allow_local_ref` + `.env.example`锛圖8锛?- review approve/reject 鈫?system 娑堟伅锛況eject 鍚庝綔鑰呭彲缁х画

**楠屾敹**锛?```bash
pytest tests/adapters/test_chat_wave5.py -x --tb=short
```

---

## Task 5 鈥?UI 閲嶅啓锛欳hat-First 澹?
**鐩爣**锛氬垹闄や笁 Tab 杩愯惀甯冨眬锛涘疄鐜?proposal 搂Success Criteria 1鈥?銆?
**鏂囦欢**锛?- `skillhub_eval/adapters/ui/static/index.html`锛堥噸鍐欙級

**瑕佺偣**锛?- 涓?Tab锛氬璇濊瘎浼?| 璇勪及鍘嗗彶
- Composer锛?*ZIP 榛樿**锛汥emo env 鏃舵樉绀烘湰鍦拌矾寰勬
- 搂4.5 瑙嗚鍒囨崲锛氬緟瀹′綔鑰呭彧璇?+ 涓撳 badge + chip锛涜瀹氬悗 **鑷姩鍒囧洖浣滆€?*
- 鍘嗗彶 Tab锛氬璇濆垪 + 璇︽儏瀵硅瘽鎽樿 +銆屾墦寮€瀹屾暣瀵硅瘽銆?- 鍒犻櫎涓撳 Tab銆佸彸鏍?report銆侀粯璁?Debug

**楠屾敹**锛氭墜宸?smoke锛堣 Task 7 checklist锛?
---

## Task 6 鈥?闆嗘垚娴嬭瘯 E2E

**鐩爣**锛氳嚜鍔ㄥ寲瑕嗙洊 Chat-First 涓昏矾寰勩€?
**鏂囦欢**锛?- `tests/integration/test_wave5_chat_shell.py`锛堟柊寤猴級

**鍓ф湰**锛?1. 鍒涘缓绌轰細璇?鈫?welcome 娑堟伅
2. bootstrap **ZIP**锛坱est fixture zip锛夆啋 rich_report
2b. 锛堝彲閫夛級Demo env bootstrap local_ref
3. awaiting_human_review 鈫?浣滆€呭彧璇?鈫?鍒囦笓瀹?鈫?approve 鈫?鑷姩鍥炰綔鑰?4. history API 鍚?conversation 瀛楁 + conversation 绔偣

**楠屾敹**锛?```bash
pytest tests/integration/test_wave5_chat_shell.py -x --tb=short
```

---

## Task 7 鈥?鍏ㄩ噺鍥炲綊 + 褰掓。鍓嶇粓妫€

**鐩爣**锛歱ytest 鍏ㄧ豢锛涙墜宸?smoke銆?
**鏂囦欢**锛?- `docs/runbooks/phase3-lui-validation.md`锛堝崰浣嶏細W5.5 鍐嶅啓锛?
**楠屾敹**锛?```bash
pytest tests/ -x --tb=short
```

**鎵嬪伐 smoke checklist**锛?- [ ] ZIP 涓婁紶 鈫?rich_report 鍦ㄦ秷鎭祦
- [ ] Demo env锛氭湰鍦拌矾寰勫彲鐢紱榛樿 env 璺緞妗嗕笉鍙
- [ ] warn + 浜哄伐澶嶆牳锛氫綔鑰呭彧璇?鈫?鍒囦笓瀹?鈫?鎵瑰噯 鈫?鑷姩鍥炰綔鑰?+ system 娑堟伅
- [ ] 璇勪及鍘嗗彶锛氬璇濇憳瑕?+ 鎵撳紑瀹屾暣瀵硅瘽
- [ ] 鍒锋柊 鈫?浼氳瘽鍒楄〃 + 娑堟伅浠嶅湪

---

## 渚濊禆鍥?
```
grill-me 鉁?鈫?Task1 鈫?Task2 鈫?Task3 鈭?Task4 鈫?Task5 鈫?Task6 鈫?Task7 鈫?Task0 (RECORD/Sprint)
```

## grill-me 鐘舵€侊細**宸查棴鍚?*锛?026-06-10锛?
| ID | 鍐宠 |
|----|------|
| EQ1 | MVP **鍏佽鑷壒**锛涘鎵?IAM 闃舵鍥涚粏鍖?|
| EQ2 | **绾璇?*鏀堕泦 ID锛涙棤甯搁┗杈撳叆妗?|
| EQ2b | 闈欓粯涓婁紶锛?*SKILL.md > zip 鍚?*锛涜瘑鍒悗 **鍚戠敤鎴风‘璁?* |
| EQ2c | **浠呰嚜鍔ㄨ瘑鍒?*椤荤‘璁わ紱鐢ㄦ埛娑堟伅宸叉槑璇?ID 鈫?**璺宠繃纭**鐩存帴寮€璇?|

**褰撳墠**锛歍ask 1 璧?subagent 瀹炵幇锛汿ask 0 鍦?Task 7 涔嬪悗銆?