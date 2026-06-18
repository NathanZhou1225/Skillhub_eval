# Tasks: Wave 5.2 鈥?UI 閫忔槑鍖?+ 琛ラ纭 + 鍏ㄥ璇濇緞娓?

> **鍓嶇疆**锛歚wave5.1-chat-report-split` 鉁咃紙413 tests锛夈€?*grill-me** 鉁?GQ1鈥揋Q15锛?026-06-10锛夈€?*瀹炵幇 + Task 0** 鉁咃紙447 tests锛?026-06-11锛夈€?

---

## Task 0 鈥?鏂囨。瀵归綈锛堝疄鐜板畬鎴愬悗锛?

**鏂囦欢**锛歚RECORD.md`銆乣.project_memory/active/SPRINT_phase3-marketplace.md`銆乣docs/guides/Skill璇勪及绯荤粺鍏ㄦ櫙璇存槑.md`

**瑕佺偣**锛?
- [x] FB-01锝?5 鏍囪宸茶В鍐筹紱W5.2 鍐崇瓥鍏ヨ〃
- [x] 鍏ㄦ櫙璇存槑 搂3 娴佺▼鍥撅細Propagator 鏀逛负銆岀‘璁ゅ悗銆嶏紱搂4.4 涓夋柟寮?
- [x] W5.5 smoke 澧烇細琛ラ璁″垝琛?/ 涓夋柟寮?/ Pass 寰芥爣 / 鏃犻潤榛?prop锛堣 Sprint W5.5锛?

---

## Task 1 鈥?DB v5 `clarifications_json` + 鏂?conversation status

**鏂囦欢**锛?
- `skillhub_eval/persistence/sqlite.py`
- `skillhub_eval/core/ports.py`
- `tests/persistence/test_wave5_2_clarifications.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `SCHEMA_VERSION = 5`锛沗conversations.clarifications_json`
- [x] `get_clarifications` / `merge_clarifications`
- [x] status 鏂囨。鍖栵細`awaiting_propagation_confirm`, `awaiting_propagation_clarify`, `awaiting_manual_upload`, `awaiting_clarify`

**楠屾敹**锛?
```bash
pytest tests/persistence/test_wave5_2_clarifications.py -x --tb=short
```

---

## Task 2 鈥?`propagation_plan` builder + L0 瑙﹀彂

**鏂囦欢**锛?
- `skillhub_eval/core/propagation_plan.py`锛堟柊寤猴級
- `skillhub_eval/core/case_sanitizer.py`锛坰ample_io gap 鑻ラ渶锛?
- `tests/core/test_propagation_plan.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `build_propagation_plan()` 纭畾鎬ц〃鏍?payload
- [x] `detect_l0_clarifications()` 鏈€澶?3 闂?
- [x] 澶嶇敤 `TYPE_DESCRIPTIONS`銆乣CASE_TYPE_REQUIREMENTS`銆乼axonomy `case_template_hint`

**楠屾敹**锛?
```bash
pytest tests/core/test_propagation_plan.py -x --tb=short
```

---

## Task 3 鈥?Deferred Propagator + bootstrap 鎷嗗垎

**鏂囦欢**锛?
- `skillhub_eval/adapters/api/routes/conversations.py`
- `skillhub_eval/core/propagator.py`锛坈larifications 娉ㄥ叆锛?
- `tests/adapters/test_bootstrap_wave5_2_deferred.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] security 鍚?sanitizer 鈫?plan锛涙湁缂哄彛 **涓?* propagate銆?*涓?* create run
- [x] append `propagation_plan` message锛沗propagation_deferred=true`
- [x] L0 鏈弧瓒?鈫?`awaiting_propagation_clarify`
- [x] Propagator prompt 娉ㄥ叆 `clarifications_json`

**楠屾敹**锛?
```bash
pytest tests/adapters/test_bootstrap_wave5_2_deferred.py -x --tb=short
```

---

## Task 4 鈥?Chat 涓夋柟寮忚矾鐢?+ propagation_summary

**鏂囦欢**锛?
- `skillhub_eval/adapters/api/routes/chat.py`
- `skillhub_eval/adapters/api/_session.py`
- `tests/adapters/test_chat_wave5_2_propagation_gate.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] 銆岀‘璁ゃ€嶁啋 propagate 鈫?summary message 鈫?create run
- [x] 銆屾垜鑷繁琛ャ€嶁啋 `awaiting_manual_upload` + 妯℃澘璇存槑
- [x] 銆屽府鎴戝湪瀵硅瘽閲岃ˉ銆嶁啋 `awaiting_draft_confirm`锛堝鐢?W5.1锛?
- [x] 閲嶄紶 ZIP 閲嶆柊 sanitizer + plan
- [x] session gate 鏂?status

**楠屾敹**锛?
```bash
pytest tests/adapters/test_chat_wave5_2_propagation_gate.py -x --tb=short
```

---

## Task 5 鈥?LuiAgent `clarify` intent + UI-S2 prompt

**鏂囦欢**锛?
- `skillhub_eval/core/lui_agent.py`
- `tests/core/test_lui_agent_clarify.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `intent=clarify`锛沗clarification_keys`锛涚姝?patch
- [x] 鍏ㄥ璇濓細Skill 璁捐涓嶇‘瀹?鈫?clarify
- [x] 鐢ㄦ埛鍥炵瓟 鈫?`merge_clarifications`
- [x] clarify 鏈熼棿 chat mutation 鈫?403

**楠屾敹**锛?
```bash
pytest tests/core/test_lui_agent_clarify.py tests/core/test_lui_agent.py -x --tb=short
```

---

## Task 6 鈥?Engine 鍒濊瘎鐦﹁韩锛圙Q12 R2锛?

**鏂囦欢**锛?
- `skillhub_eval/core/engine.py`
- `tests/core/test_engine_readiness.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `degraded` 璺緞鍦?case_gate/gaps 鍚?**early terminal**锛堣烦杩?model_judging銆丄I risk 鈶€乻kill_summary锛?
- [x] 淇濈暀 security + 瑙勫垯 risk + completeness + gaps 蹇収
- [x] 杞婚噺 readiness 鎸佷箙鍖栵紙闈炲叏閲?EvaluationReport锛?

**楠屾敹**锛?
```bash
pytest tests/core/test_engine_readiness.py -x --tb=short
```

---

## Task 7 鈥?`readiness_result` 娑堟伅锛圙Q13锛?

**鏂囦欢**锛?
- `skillhub_eval/core/chat_notifications.py`锛堟垨 `readiness_notifications.py`锛?
- `skillhub_eval/core/engine.py`锛堥挬瀛愭浛鎹㈠垵璇?rich_report锛?
- `tests/core/test_readiness_notifications.py`锛堟柊寤猴級

**瑕佺偣**锛?
- [x] `append_readiness_result_message`锛沺ayload 鑷寘鍚?gaps/瀹夊叏/椋庨櫓/闂ㄦ
- [x] 鍒濊瘎 **涓?* `append_rich_report_message`
- [x] 鍙欎簨鍏堜簬 readiness 鍗＄墖

**楠屾敹**锛?
```bash
pytest tests/core/test_readiness_notifications.py -x --tb=short
```

---

## Task 8 鈥?姝ｅ紡绠€鍗?`verdict_zh` + `next_action_zh`锛圙Q14锛?

**鏂囦欢**锛?
- `skillhub_eval/core/chat_notifications.py`
- `tests/core/test_chat_notifications.py`

**瑕佺偣**锛?
- [x] `_resolve_verdict()` + `_resolve_next_action()`锛圙Q5 鏄犲皠锛?
- [x] 浠?formal / formal_pending_review 鏈?CTA
- [ ] 鑷姩姝ｅ紡鍙欎簨鍙紩鐢?propagator summary锛圙Q8锛?

**楠屾敹**锛?
```bash
pytest tests/core/test_chat_notifications.py -x --tb=short
```

---

## Task 9 鈥?UI锛歱lan / readiness / formal 涓夊鍗＄墖

**鏂囦欢**锛?
- `skillhub_eval/adapters/ui/static/index.html`
- `tests/api/test_ui.py`

**瑕佺偣**锛?
- [x] `renderPropagationPlanHtml` / `renderPropagationSummaryHtml`
- [x] 涓?Action Chip锛圙Q10锛? `handlePropagationAction`
- [x] 璁″垝琛ㄥ崟鏉℃洿鏂帮紙GQ9 `plan_version`锛?
- [x] `renderMessages` 鍒嗘敮鏂?message_type
- [x] `renderReadinessResultHtml`锛堟棤鎶ュ憡 CTA锛孏Q13锛?
- [x] 姝ｅ紡绠€鍗?`verdict_zh` + `next_action_zh`锛圙Q14锛?
- [x] 鍘嗗彶 Tab锛?*涓嶅垪鍑?* `degraded` 鍒濊瘎 run锛圙Q15 B锛夛紱API 鎴栧墠绔繃婊?
- [x] Composer 鎻愮ず锛坅waiting_propagation_confirm锛?

**楠屾敹**锛?
```bash
pytest tests/api/test_ui.py -x --tb=short
```

---

## Task 10 鈥?闆嗘垚娴嬭瘯 E2E 鉁?

**鏂囦欢**锛歚tests/integration/test_wave5_2_transparency.py`锛堟柊寤猴級

**鍓ф湰**锛?
1. grill-me 绫?ZIP锛堜粎 SKILL.md锛夆啋 plan 琛ㄣ€佹棤 prop銆佹棤 run
2. 銆岀‘璁ゃ€嶁啋 prop 鏂囦欢 + summary + 鍒濊瘎 run
3. 銆屽府鎴戝湪瀵硅瘽閲岃ˉ銆嶁啋 draft_confirm 閾?
4. L0 category 缂哄け 鈫?clarify 鍏堜簬 plan
5. 鍒濊瘎 run 鏃?model_judging锛涙湁 readiness_result銆佹棤 rich_report
6. 姝ｅ紡 Pass 鈫?verdict_zh + next_action_zh + 鎶ュ憡 CTA
7. 鍘嗗彶鍒楄〃 **涓嶅惈** degraded 鍒濊瘎 run锛圙Q15 B锛?

**楠屾敹**锛?
```bash
pytest tests/integration/test_wave5_2_transparency.py -x --tb=short
```

---

## Task 11 鈥?鍏ㄩ噺鍥炲綊 鉁?

**楠屾敹**锛?
```bash
pytest tests/ -x --tb=short
```

**鎵嬪伐 smoke**锛圵5.5锛夛細
- [ ] 缂洪 ZIP锛氳琛?鈫?閫夋柟寮?鈫?鏃犻潤榛樿ˉ棰?
- [ ] Pass 鍚庣畝鍗℃樉绀恒€岄€氳繃銆?
- [ ] 涓嶇‘瀹氭椂 Agent 涓诲姩鎻愰棶

---

## 渚濊禆鍥?

```
Task1 鈫?Task2 鈫?Task3 鈫?Task4
              鈫?Task5 鈫?
Task3 鈫?Task6 鈫?Task7 鈫?Task8 鈫?Task9 鈫?Task10 鈫?Task11 鈫?Task0
```

## 宸查棴鍚堝喅绛?

| ID | 鍐宠 |
|----|------|
| UI-B3 | 缂洪鏆傚仠锛涗笁鏂瑰紡锛涢粯璁よ嚜琛?|
| UI-S2 | 鍏ㄥ璇?clarify |
| UI-TBL | propagation_plan 琛?|
| UI-VERDICT | 姝ｅ紡 Pass/Warn/Fail 寰芥爣 |

## Workflow 涓嬩竴姝?

1. **grill-me** 鉁?GQ1鈥揋Q15
2. **瀹炵幇 + Task 0** 鉁?
3. **寰呭姙**锛歚/opsx:archive` + W5.5 Demo smoke

## grill-me 宸查棴鍚?

瑙?`proposal.md` GQ1鈥揋Q11銆?
