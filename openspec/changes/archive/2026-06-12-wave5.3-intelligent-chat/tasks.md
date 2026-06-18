# Tasks: Wave 5.3 鈥?鏅鸿兘瀵硅瘽 + LLM 琛ラ璁″垝 + 浜や簰浣撻獙

> **鍓嶇疆**锛歚wave5.2-ui-transparency` 鉁咃紙447 tests锛夈€?*鐢ㄦ埛鍐崇瓥** 鉁?GQ-W53-1锝?2锛?026-06-10锛屽惈 grill-me锛夈€?

---

## Task 0 鈥?鏂囨。瀵归綈锛堝疄鐜板畬鎴愬悗锛?

**鏂囦欢**锛歚RECORD.md`銆乣.project_memory/active/SPRINT_phase3-marketplace.md`銆乣docs/guides/Skill璇勪及绯荤粺鍏ㄦ櫙璇存槑.md`

**瑕佺偣**锛?
- [x] FB-06锝?2 鍏ヨ〃锛汧B-01锝?5 鏍囨敞銆學5.3 鍥炲綊淇銆峸here applicable
- [x] 鍏ㄦ櫙璇存槑 搂3.4锛歜ootstrap LLM enrich锛汭ntentRouter锛涢樁娈垫彁绀?
- [x] W5.5 runbook 鏇存柊 smoke 鏉＄洰

---

## Task 1 鈥?P0 鐑慨锛歳eadiness / plan 瀛楁 + composer 娓呯┖

**鏂囦欢**锛?
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/adapters/test_readiness_payload_contract.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `renderReadinessResultHtml` 璇?`completeness_score` / `security_status` / `risk_level_locked` / `case_gate.passed`
- [x] `renderPropagationPlanHtml` 璇?`gap_count`锛坒allback `gap`锛夛紱琛ㄥご GQ-W53-8b锛沗flow_step` 姝ラ鏉″湪鍗＄墖椤?
- [x] readiness 鍗★細GQ-W53-8 鐧借瘽锛堣瘎浼版潯浠堕棬妲涚瓑锛?
- [x] `sendConversationMessage` 鎴愬姛鍚?**濮嬬粓** `input.value = ''`

**楠屾敹**锛?
```bash
pytest tests/adapters/test_readiness_payload_contract.py -x --tb=short
```

---

## Task 2 鈥?缁熶竴纭璇?`confirm_lexicon`

**鏂囦欢**锛?
- `skillhub_eval/core/confirm_lexicon.py`锛堟柊寤猴級
- `skillhub_eval/core/skill_id_resolver.py`
- `skillhub_eval/core/lui_agent.py`
- `tests/core/test_confirm_lexicon.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `is_confirm_message()` 鍚€岀‘瀹氥€?
- [x] `skill_id_resolver.is_confirm_reply` 濮旀墭 lexicon
- [x] `LuiAgent.is_draft_confirmation` 濮旀墭 lexicon + 淇濈暀銆屾寜杩欎釜琛ャ€嶅墠缂€

**楠屾敹**锛?
```bash
pytest tests/core/test_confirm_lexicon.py -x --tb=short
```

---

## Task 3 鈥?LLM 琛ラ璁″垝 enricher + bootstrap 姣忔璋冪敤

**鏂囦欢**锛?
- `skillhub_eval/core/propagation_plan_enricher.py`锛堟柊寤猴級
- `skillhub_eval/core/propagation_plan.py`锛坄gap` 鍒悕銆乣enrichment_status` 瀛楁锛?
- `skillhub_eval/adapters/api/routes/conversations.py`
- `skillhub_eval/adapters/api/routes/chat.py`锛坄_refresh_propagation_plan` re-enrich锛?
- `tests/core/test_propagation_plan_enricher.py`锛堟柊寤猴級
- `tests/adapters/test_bootstrap_wave5_3_enrich.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `enrich_propagation_plan()` mock 娴嬭瘯锛氬洓琛?business_expectation 鍙笉鍚?
- [x] 澶辫触闄嶇骇 `enrichment_status=degraded`
- [x] **姣忔 bootstrap** 璋冪敤 enrich锛涙棤缂哄彛鏃?`set_plan_enrichment` 缂撳瓨
- [x] clarify 鍒锋柊 plan 鍚?re-enrich

**楠屾敹**锛?
```bash
pytest tests/core/test_propagation_plan_enricher.py tests/adapters/test_bootstrap_wave5_3_enrich.py -x --tb=short
```

---

## Task 4 鈥?DB v6 `plan_enrichment_json`

**鏂囦欢**锛?
- `skillhub_eval/persistence/sqlite.py`
- `skillhub_eval/core/ports.py`
- `tests/persistence/test_wave5_3_plan_enrichment.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `SCHEMA_VERSION = 6`
- [x] `get_plan_enrichment` / `set_plan_enrichment`

**楠屾敹**锛?
```bash
pytest tests/persistence/test_wave5_3_plan_enrichment.py -x --tb=short
```

---

## Task 5 鈥?IntentRouter + Action 鐧藉悕鍗?

**鏂囦欢**锛?
- `skillhub_eval/core/intent_router.py`锛堟柊寤猴級
- `skillhub_eval/adapters/api/routes/chat.py`
- `tests/core/test_intent_router.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `__ACTION_CONFIRM_SKILL__` / `__ACTION_PROPAGATE__` / `__ACTION_MANUAL_UPLOAD__` / `__ACTION_DRAFT_MODE__` / `__ACTION_DRAFT_CONFIRM__`
- [x] GQ-W53-6锛氥€屽璇濋噷琛ャ€嶅厛鍒嗗弶闂?+ Chip锛汫Q-W53-6b 鍐欐枃浠?vs Propagator 浜岄€変竴
- [x] GQ-W53-9锛氳瘝琛?confirm 蹇嵎 + IntentRouter 鈮?.85 妯＄硦鍙?
- [x] `ChatResponse.activity_phase` 瀛楁

**楠屾敹**锛?
```bash
pytest tests/core/test_intent_router.py tests/adapters/test_chat_wave5_3_actions.py -x --tb=short
```

---

## Task 6 鈥?UI Action Chips锛圫kill ID + draft + __ACTION_*__锛?

**鏂囦欢**锛?
- `skillhub_eval/adapters/ui/static/index.html`

**瑕佺偣**锛?
- [x] `awaiting_skill_id_confirm` 娓叉煋纭/鍚嶇О涓嶅 Chip
- [x] propagation Chips 鏀瑰彂 `__ACTION_*__`
- [x] `draft_preview` 鍗＄墖 + 纭鍐欏叆 Chip
- [x] Chip 鐐瑰嚮鏄犲皠鍙鐢ㄦ埛姘旀场鏂囨

**楠屾敹**锛氭墜宸?+ 鐜版湁 E2E 鎵╁睍锛圱ask 10锛?

---

## Task 7 鈥?`draft_preview` + 寮哄埗浠ｅ啓璺緞

**鏂囦欢**锛?
- `skillhub_eval/core/lui_agent.py`
- `skillhub_eval/adapters/api/routes/chat.py`
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/adapters/test_wave5_3_draft_flow.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `_generate_draft_patch` 娉ㄥ叆 SKILL.md excerpt锛涚己鐩綍鏃?prompt 寮哄埗 eval_cases
- [x] 鎴愬姛鍚?append `draft_preview` + `set_pending_patch`
- [x] GQ-W53-11锛歚draft_failed` 娑堟伅 + 鍐嶈瘯/鎵嬪姩涓婁紶/鑷姩鍑洪 Chip锛涙渶澶?2 娆?generate
- [x] GQ-W53-7锛歚next_hint_zh` + 鍗＄墖椤?`flow_step`
- [x] 纭鍚?`StagingWriter.apply_patch` 鍐欏叆 eval_cases + sample_io

**楠屾敹**锛?
```bash
pytest tests/adapters/test_wave5_3_draft_flow.py -x --tb=short
```

---

## Task 8 鈥?浜や簰锛歰ptimistic 姘旀场 + 闃舵 pending + 璇勪及闃舵鏂囨

**鏂囦欢**锛?
- `skillhub_eval/adapters/ui/static/index.html`
- `skillhub_eval/adapters/api/routes/chat.py`锛坙ong op 杩斿洖 `activity_phase`锛?
- `skillhub_eval/adapters/api/routes/conversations.py`锛坆ootstrap/propagate phase锛?

**瑕佺偣**锛?
- [x] 鍙戦€佸悗绔嬪嵆 user bubble + agent pending锛坄activityPhaseLabel`锛?
- [x] poll / chat 鍝嶅簲鍚庣Щ闄?pending
- [x] RUNNING 鏃?chat 鍐?stage 涓枃涓€琛岋紙璇?status API锛?
- [x] GQ-W53-10锛氭棤缂哄彛 system銆岃瘎浼版潯浠跺凡杈炬爣锛屽紑濮嬪垵璇勨€︺€?
- [x] GQ-W53-12锛氳瘎浼颁腑 409 淇濇寔锛泂tage 鐧借瘽鏄犲皠

**楠屾敹**锛氭墜宸?smoke锛涘崟鍏冩祴璇?pending 閫昏緫锛堝彲閫?js 鍏嶆祴锛岄潬 Task 10锛?

---

## Task 9 鈥?Clarify LLM 瑙ｆ瀽

**鏂囦欢**锛?
- `skillhub_eval/core/clarification_parser.py`锛堟柊寤猴級
- `skillhub_eval/adapters/api/routes/chat.py`
- `tests/core/test_clarification_parser.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `awaiting_clarify` / `awaiting_propagation_clarify` 澶?key 瑙ｆ瀽
- [x] fallback 鐜版湁鍚彂寮?

**楠屾敹**锛?
```bash
pytest tests/core/test_clarification_parser.py -x --tb=short
```

---

## Task 10 鈥?LuiAgent 涓婁笅鏂?+ E2E 闆嗘垚

**鏂囦欢**锛?
- `skillhub_eval/core/lui_agent.py`
- `tests/adapters/test_wave5_3_e2e.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] prompt 娉ㄥ叆 skill_md_excerpt + plan_enrichment
- [x] E2E锛歜ootstrap 鈫?enrich plan 鈫?confirm 鈫?readiness 鏈夊€?鈫?draft 娴侊紙mock LLM锛?

**楠屾敹**锛?
```bash
pytest tests/adapters/test_wave5_3_e2e.py -x --tb=short
```

---

## Task 11 鈥?鍏ㄩ噺鍥炲綊

**楠屾敹**锛?
```bash
pytest tests/ -x --tb=short
```

鐩爣锛氣墺447 鍏ㄧ豢 + W5.3 鏂板娴嬭瘯銆?*鉁?472 passed**

---

## 寤鸿瀹炵幇椤哄簭

```
Task 1 鈫?Task 2 鈫?Task 4 鈫?Task 3 鈫?Task 5 鈫?Task 6 鈫?Task 7 鈫?Task 8 鈫?Task 9 鈫?Task 10 鈫?Task 11 鈫?Task 0
```

**grill-me 宸查棴鍚?* 鈥?鏃犲紑鏀捐棰樸€傚疄鐜板悗 Task 0 鏇存柊 RECORD + Sprint銆?
