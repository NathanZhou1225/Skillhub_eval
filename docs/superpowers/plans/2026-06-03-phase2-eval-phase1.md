# Phase 2 路 Phase 1 Implementation Plan锛?.1-fix / 2.3b / 2.3a / testskills 闂幆锛?

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Gate:** 鏈鍒掔粡 **grill-me** 鎸戝埡閫氳繃鍚庯紝鏂瑰彲鎸夊簭鎵ц銆傛墽琛屽墠鍕挎敼 1.2 rubric 闃堝€间笌 1.3 鐘舵€侀椄闂ㄣ€?

**Goal:** 鍦?2.0 宸ョ▼鍩虹嚎涓婂畬鎴?Phase 1锛歮inimal 鍖呭紩瀵艰ˉ鍏?鈫?confirm 鈫?鍏ㄩ噺璇勯棴鐜紱鍏ㄧ粓鎬佽交閲?report锛汻5 鍙屾ā鍨?+ per-case 鍒嗘暟鍙鍖栵紱闄嶄綆 `EVAL_WORKFLOW_TIMEOUT`锛沗testskills/` 涓夋牱鏈獙鏀躲€?

**Architecture:** Level0 鎷嗕负銆岀粨鏋勯棬绂併€嶄笌銆宑ase 鏁伴棬绂併€嶄袱闃舵鈥斺€攑re-confirm锛坄bundle_state != confirmed` 涓旈潪 degraded锛変粎鍋氱粨鏋?+ risk_lock锛屽啓 gaps/report 鍚庡仠浜?`awaiting_confirm`锛?*degraded 璺宠繃 case gate**锛? case 鈫?case_exec 绌鸿窇 鈫?completeness 椹卞姩 WARN锛夛紱confirmed 璺戝畬鏁?case gate锛圶1锛夊悗璧拌瘎瀹°€俁eport 澧炶ˉ `provider_summary`锛堝寘绾?+ per-case锛? `stage_progress`锛堟潵鑷?`stage_transitions` 琛級锛沀I 涓?Tab 娑堣垂鍚屼竴 report 濂戠害銆侰ase 璇勫 `Semaphore(3)` 鍙楁帶骞惰 + risk 鍒嗙骇 workflow timeout銆?

**Tech Stack:** Python 3.11+ 路 FastAPI 路 SQLite 路 asyncio 路 Vanilla JS + Tailwind CDN 路 pytest 路 鐜版湁 `EvaluationEngine` / `AggregateStage` / `Level0Checker`

**鏍锋湰璺緞锛圦-04 棣栫増锛夛細**

| Skill | 璺緞 | 鐢ㄩ€?|
|-------|------|------|
| stock-radar-V6.2 | `testskills/stock-radar-V6.2/` | 鍏ㄩ噺璇?+ R5 浜哄伐澶嶆牳 |
| grill-me | `testskills/grill-me/` | minimal 琛ュ叏闂幆 |
| tiered-memory-sprint-manager | `testskills/tiered-memory-sprint-manager/` | minimal 琛ュ叏闂幆 |

---

## 纭害鏉燂紙缁ф壙 2.0锛岀姝㈣繚鍙嶏級

1. PASS 浠呭綋 `bundle_state=confirmed` 涓?`evaluation_mode=capability_full`銆?
2. R5 瑙﹀彂鏃?`score_total=null`锛堢姝㈢敤鍧囧垎鎺╃洊鍒嗘锛夛紱UI 椤?*棰濆**灞曠ず鍚勬ā鍨嬪垎鏁帮紝涓嶅緱鎶?null 褰撱€屾湭璇勩€嶃€?
3. 闄嶇骇/鏈‘璁?draft 涓嶅弬涓?CodeAssert 澶辫触鍒ゅ畾銆?
4. 涓嶉噸鍐?1.2 闃堝€硷紱2.2 瀵规姉闆?*涓嶅湪鏈獥鍙?*銆?

---

## 鏂囦欢缁撴瀯鍙樻洿棰勮

| 鏂囦欢 | 鑱岃矗 |
|------|------|
| `skillhub_eval/core/level0.py` | 鏂板 `check_structure()` / `check_case_gate()` 鎴?`skip_case_gate` 鍙傛暟 |
| `skillhub_eval/core/gaps.py` | **鏂板缓** 鈥?缂哄彛鎵弿娓呭崟锛圱2锛?|
| `skillhub_eval/core/schemas/report.py` | 鏂板 `ProviderSummary`銆乣CaseScoreRow` |
| `skillhub_eval/core/engine.py` | 缂栨帓鍒嗗弶銆佸叏缁堟€?report銆佸苟琛?case銆乼imeout 鍒嗙骇 |
| `skillhub_eval/core/aggregate.py` | 瀵煎嚭 per-case 鑱氬悎渚?report锛堝彲閫?helper锛?|
| `skillhub_eval/adapters/api/routes/eval.py` | report 鍝嶅簲 enrich |
| `skillhub_eval/adapters/ui/static/index.html` | gaps 鑱斿姩銆佹ā鏉裤€丷5/per-case UI |
| `testskills/_templates/` | **鏂板缓** 鈥?eval_case / sample_io / frontmatter 妯℃澘锛圱3/T8锛?|
| `tests/core/test_level0.py` | 缁撴瀯 vs case gate 鎷嗗垎娴嬭瘯 |
| `tests/core/test_gaps.py` | **鏂板缓** |
| `tests/core/test_engine.py` | minimal鈫抋waiting_confirm銆乺eport 缁堟€?|
| `tests/test_e2e_smoke.py` | 鎵╁睍 S3 minimal 璺緞 + provider_summary |

---

## Task 1锛圱1锛夛細2.1-fix 缂栨帓 鈥?pre-confirm 璺宠繃 case gate

**Files:**
- Modify: `skillhub_eval/core/level0.py`
- Modify: `skillhub_eval/core/engine.py`
- Test: `tests/core/test_level0.py`, `tests/core/test_engine.py`

**琛屼负瑙勬牸锛坓rill-me Q1/Q5 宸查攣锛夛細**

```
ingest 鈫?check_structure(SKILL.md 瀛樺湪銆乺isk_level 鍙В鏋?
  鈫?鑻?fail 鈫?failed + report
  鈫?risk_lock
  鈫?鑻?NOT confirmed AND NOT degraded:
       鈫?gaps + awaiting_confirm + 杞婚噺 report锛圱4 瀛楁鍗犱綅锛孴2 鎺?gaps锛?
       鈫?return锛堜笉璺?case gate銆佷笉璋?LLM锛?
  鈫?鑻?degraded:
       鈫?瀹屽叏璺宠繃 case gate锛? case 鈫?case_exec 绌鸿窇 鈫?no assertions 鈫?agg completeness 椹卞姩 WARN锛?
       鈫?鍚庣画鐜版湁娴佺▼
  鈫?鑻?confirmed:
       鈫?check_case_gate锛圶1锛夆啋 fail 鑻ヤ笉婊¤冻
       鈫?鍚庣画鐜版湁娴佺▼
```

- [ ] **Step 1:** 鍐?failing test 鈥?`minimal + capability_full`锛? cases 鈫?`awaiting_confirm`锛堥潪 `RISK_CASE_COUNT_INSUFFICIENT` failed锛?
- [ ] **Step 2:** 瀹炵幇 `Level0Checker.check_structure()` 涓?`check_case_gate()` 鍒嗙
- [ ] **Step 3:** `engine._execute` 鍦?C-3 鍒嗘敮鍓嶄粎璋?structure check锛沜ase gate 绉诲埌 confirm 鍚庣户缁矾寰?
- [ ] **Step 4:** 璺?`pytest tests/core/test_level0.py tests/core/test_engine.py -q`

**楠屾敹锛?* `grill-me` 鐩綍 `minimal + capability_full` 鈫?status=`awaiting_confirm`

---

## Task 2锛圱2锛夛細Gaps 寮曟搸 鈥?缂哄彛娓呭崟

**Files:**
- Create: `skillhub_eval/core/gaps.py`
- Modify: `skillhub_eval/core/engine.py` (`_build_gaps_snapshot` 濮旀墭 gaps 妯″潡)
- Test: `tests/core/test_gaps.py`

**娓呭崟椤癸紙姣忛」 鈫?gap 瀵硅薄 + required_action 鏂囨锛夛細**

| 妫€鏌?| severity | 璇存槑 |
|------|----------|------|
| `description` 绌?| warn | frontmatter |
| `risk_level` 鏈０鏄?| info | 榛樿 low锛屾彁绀烘樉寮忓０鏄?|
| `eval_cases/` 缂哄け | block | 鍏ㄩ噺璇勯樆鏂?|
| case 鏁?< X1 min | block | 鍚?risk銆佺己鍑犱釜 |
| case 鏁?> X1 ceiling | block | |
| 鏃犺剼鏈笖鏃?`sample_io/` | block | L1 璺緞 |
| 瀹夊叏瀛楁鏈‘璁?| warn | negative_prompts 绛?4 椤?|

- [ ] **Step 1:** 鍐?`test_gaps_detects_missing_eval_cases`
- [ ] **Step 2:** 瀹炵幇 `scan_gaps(bundle, bundle_state) -> GapsSnapshot`
- [ ] **Step 3:** engine 鍦?awaiting_confirm 璺緞璋冪敤骞?`save_gaps`
- [ ] **Step 4:** pytest 鍏ㄧ豢

**楠屾敹锛?* gaps JSON 鍚粨鏋勫寲 `gaps[]` + `required_actions[]`锛?*涓嶅惈**鍙鍒舵ā鏉挎鏂囷紙妯℃澘褰?T3锛?

---

## Task 3锛圱3锛夛細UI 琛ュ叏鍙?鈥?API 鑱斿姩 + 妯℃澘

**Files:**
- Modify: `skillhub_eval/adapters/api/routes/eval.py` 鎴栨柊澧?gaps route锛堣嫢闇€ `GET /bundle/{id}/gaps`锛?
- Modify: `skillhub_eval/adapters/ui/static/index.html`
- Create: `testskills/_templates/eval_case.yaml.tpl`
- Create: `testskills/_templates/sample_io.json.tpl`
- Create: `testskills/_templates/frontmatter_snippet.yaml.tpl`

**UI 琛屼负锛?*

1. `loadGaps(skill_id)` 璋冪敤 API 璇诲彇鏈€鏂?gaps snapshot锛堟寜 skill_id 鎴?run_id锛?
2. 鎸?gap severity 鍒嗗尯娓叉煋娓呭崟锛坆lock / warn / info锛?
3. 瀵?block 绫荤己鍙ｅ睍绀?*鍙鍒舵ā鏉?*锛堜粠 `_templates/` 鎴栧唴鑱?JS 甯搁噺锛夛細
   - eval_case 鏈€灏?YAML锛坕d / type / user_intent锛?
   - sample_io 鏈€灏?JSON
   - frontmatter `risk_level: low` 鐗囨
4. 瀹夊叏瀛楁浠嶄繚鐣?confirm 琛ㄥ崟锛涙彁浜?`POST /bundle/{id}/confirm`
5. 鎻愮ず锛?*缁撴瀯鏂囦欢椤讳繚瀛樺埌 Bundle 璺緞**鍚庯紝浠?`confirmed + capability_full` 閲嶆柊鍙戣捣璇勪及

**缁撴瀯鏂囦欢璇存槑锛圱8 闂幆鍓嶆彁锛夛細**  
褰撳墠 confirm API **鍙寔涔呭寲鍏冩暟鎹瓧娈?*锛屼笉鍐?`eval_cases/` 鍒扮鐩樸€備綔鑰呮寜 UI 妯℃澘鍦?`testskills/<skill>/` 涓嬫墜鍔ㄥ垱寤烘枃浠讹紙鎴栧悗缁彲閫?scaffold CLI锛屾湰璁″垝涓嶅己鍒讹級銆?

- [ ] **Step 1:** 纭/琛?`GET` gaps 绔偣杩斿洖鏈€鏂?snapshot
- [ ] **Step 2:** 鍐?`_templates/` 涓夋枃浠?
- [ ] **Step 3:** 閲嶅啓 `loadGaps()` + 妯℃澘澶嶅埗鎸夐挳锛坈lipboard锛?
- [ ] **Step 4:** awaiting_confirm 杞缁撴潫鏃惰嚜鍔ㄥ～鍏?skill_id 骞舵彁绀恒€屾煡璇?Gaps銆?

**楠屾敹锛?* grill-me minimal run 鍚?UI 鏄剧ず銆岀己 3 涓?case銆? 鍙鍒剁殑 case 妯℃澘

---

## Task 4锛圱4锛夛細2.3b 杞婚噺 report 鈥?鍏ㄧ粓鎬佸啓鍏?

**Files:**
- Modify: `skillhub_eval/core/schemas/report.py`
- Modify: `skillhub_eval/core/engine.py`
- Test: `tests/core/test_engine.py`

**缁堟€?report 鏈€灏忓瓧娈甸泦锛?*

```python
# awaiting_confirm / timeout / failed(level0)
{
  "status", "risk_level_locked", "orchestration_mode",
  "completeness_score",  # 鑻ュ凡绠?
  "reason_codes", "evidence", "required_actions",
  "gaps": [...],           # 鎴栧紩鐢?gaps snapshot id
  "stage_progress": ["level0_checking", "risk_locking", "awaiting_confirm"],
  "score_total": null,
  "score_total_source": "not_applicable" | ...
}
```

- [ ] **Step 1:** test 鈥?awaiting_confirm run 鐨?`GET /eval/report/{id}` 杩斿洖闈炵┖ `report`
- [ ] **Step 2:** `_park_awaiting_confirm()` helper锛氬啓 report + gaps + status
- [ ] **Step 3:** timeout 璺緞锛坄run_async` except TimeoutError锛夊啓 report + stage_progress + reason
- [ ] **Step 4:** Level0 structure fail 宸叉湁 `_save_fail`锛岃ˉ `stage_progress`

---

## Task 5锛圱5锛夛細R5 鍙鍖?鈥?provider_summary + per-case

**Files:**
- Modify: `skillhub_eval/core/schemas/report.py` 鈥?鏂板妯″瀷锛?

```python
class CaseScoreRow(BaseModel):
    case_id: str
    deepseek_score: float | None
    gemini_score: float | None
    gap: float | None
    ds_suggested_status: str | None
    gemini_suggested_status: str | None

class ProviderSummary(BaseModel):
    deepseek_score: float | None      # 鍖呯骇鍧囧€?
    gemini_score: float | None
    score_gap: float | None
    r5_triggered: bool
    deepseek_bundle_status: str | None
    gemini_bundle_status: str | None
    per_case: list[CaseScoreRow]
```

- Modify: `skillhub_eval/core/engine.py` 鈥?浠?`all_votes` + `agg` 鏋勫缓骞跺啓鍏?report
- Modify: `skillhub_eval/adapters/api/routes/eval.py` 鈥?椤跺眰 `provider_summary` 渚夸簬 UI
- Modify: `skillhub_eval/adapters/ui/static/index.html`

**UI 瑙勬牸锛?*

| 浣嶇疆 | 灞曠ず |
|------|------|
| 浣滆€呭彴 run-status | 鍖呯骇 DS / Gemini 鍒嗘暟鏉?+ 螖锛汻5 鏃舵枃妗堛€屾ā鍨嬪垎姝э紝缁煎悎鍒嗘殏涓嶅彲鐢ㄣ€?|
| 涓撳瀹℃牳鍙板崱鐗?| 鍚屼笂 + **per-case 琛ㄦ牸**锛坈ase_id / DS / Gemini / 螖 / 寤鸿鐘舵€侊級 |
| 鍘嗗彶璇︽儏 | 鏇挎崲 `alert()` 涓烘ā鎬佹垨鍐呰仈鎶樺彔锛堣嚦灏戝睍绀?provider_summary锛?|

- [ ] **Step 1:** test 鈥?R5 run report 鍚?`provider_summary.per_case` 闀垮害 = n_cases
- [ ] **Step 2:** 瀹炵幇 `_build_provider_summary(votes, agg)`
- [ ] **Step 3:** 浣滆€呭彴 + 涓撳鍙?UI锛堜笓瀹跺崱 fetch `/eval/report/{run_id}`锛?
- [ ] **Step 4:** 浜哄伐 approve 鍚庡崱鐗囦繚鐣?per-case 蹇収 + 銆屼笓瀹惰瀹氥€嶆爣娉?

---

## Task 6锛圱6锛夛細缁堟€佹枃妗堝垎鍙?

**Files:**
- Modify: `skillhub_eval/adapters/ui/static/index.html`

| 鏉′欢 | 鏂囨 |
|------|------|
| `status=awaiting_confirm` | 銆屽緟浣滆€呰ˉ鍏紝灏氭湭杩涘叆妯″瀷璇勫銆?|
| `score_total_source=null_due_to_disagreement` | 銆屾ā鍨嬪垎姝э紙R5锛夛紝缁煎悎鍒嗘殏涓嶅彲鐢ㄣ€? 灞曠ず鍙屾ā鍨嬪垎 |
| `reason_codes` 鍚?`EVAL_WORKFLOW_TIMEOUT` | 銆岃瘎浼拌秴鏃躲€? stage_progress |
| 姝ｅ父 completed | `score_total/100` |

- [ ] **Step 1:** 鎶藉彇 `formatScoreDisplay(d)` 鍑芥暟
- [ ] **Step 2:** 浣滆€呭彴 + 涓撳鍙?+ 鍘嗗彶缁熶竴璋冪敤

---

## Task 7锛圱7锛夛細2.3a 鏃跺欢浼樺寲

**Files:**
- Modify: `skillhub_eval/core/engine.py`
- Modify: `skillhub_eval/providers/deepseek.py`, `skillhub_eval/providers/gemini.py`锛坱imeout/retry 鍙傛暟锛?
- Modify: `skillhub_eval/core/schemas/enums.py` 鎴?`settings` 鈥?risk 鈫?workflow_timeout 鏄犲皠

**瑙勬牸锛坓rill-me Q2 宸查攣锛夛細**

| 椤?| 鍊?| 璇存槑 |
|----|------|------|
| workflow timeout | low/medium: 300s锛沨igh: 600s | 鎸?risk_level_locked 鍒嗙骇 |
| case 骞跺彂 | `asyncio.Semaphore(3)`锛圖S + Gemini 鍏变韩锛?| 浠樿垂妗?DS ~120 RPM 瀹瑰繊锛涘嘲鍊?6 骞跺彂 |
| provider 鍗?call timeout | **45s** | DS 瀹炴祴 15鈥?5s锛?5s 鐣欎綑閲?|
| 閲嶈瘯绛栫暐 | 503/429 鈫?鎸囨暟閫€閬?max 3脳锛宐ase 1s | 鏈嶅姟绔?burst 鑷剤锛涢潪 RPM 鎷︽埅 |
| 鍩嬬偣 | `repo.log_event(run_id, "stage_timing", {stage, ms})` | 姣忛樁娈佃€楁椂锛涙參 case top-N |

- [ ] **Step 1:** test 鈥?mock provider 寤惰繜锛岄獙璇佸苟琛屾瘮涓茶蹇紙鍗曞厓绾э級
- [ ] **Step 2:** 瀹炵幇 case 骞惰 + semaphore
- [ ] **Step 3:** `_workflow_timeout` 鎸?`risk_level_locked` 鍒嗙骇
- [ ] **Step 4:** stage_timing 鍩嬬偣
- [ ] **Step 5:** live 澶嶆祴 `stock-radar-V6.2` confirmed full 涓?timeout

---

## Task 8锛圱8锛夛細testskills 涓夋牱鏈窇閫氱煩闃?

**Files:**
- Create: `docs/runbooks/testskills-phase1-validation.md`锛堟垨 Sprint 鍐呭祵楠屾敹琛級
- Create/Modify: `testskills/grill-me/eval_cases/*.yaml` 绛夛紙**琛ュ叏鍚?*鐢ㄤ簬闂幆楠屾敹锛屽彲鎻愪氦鏈€灏?3 case锛?
- Create/Modify: `testskills/tiered-memory-sprint-manager/eval_cases/*.yaml` 鍚屼笂

**楠屾敹鐭╅樀锛堝繀椤诲叏閮ㄩ€氳繃锛夛細**

| # | 鏍锋湰 | 姝ラ | 棰勬湡缁堟€?|
|---|------|------|----------|
| 1 | grill-me | minimal + capability_full | `awaiting_confirm` + gaps 鍚?case/sample_io |
| 2 | grill-me | 鎸?UI 妯℃澘琛?3 case + sample_io + risk_level + confirm 瀛楁 鈫?confirmed + full | `completed` / `warn` / `awaiting_human_review`锛堜换涓€鍚堟硶缁堟€侊紝闈?failed/timeout锛?|
| 3 | tiered-memory | 鍚?#1鈥?2 | 鍚?|
| 4 | stock-radar | confirmed + capability_full | 瀹屾垚璇勫锛涜嫢 R5 鈫?涓撳鍙板彲瑙?per-case 鍒嗘暟 |
| 5 | stock-radar | minimal 鈫?gaps 鈫?琛ュ叏 鈫?confirm 鈫?full | 鍙€夊洖褰?|

**grill-me / tiered-memory 鏈€灏忚ˉ鍏ㄥ寘锛圱8 鍙傝€冿級锛?*

```
testskills/<skill>/
  SKILL.md          # 鍔?risk_level: low
  eval_cases/
    c01.yaml        # happy_path
    c02.yaml        # edge
    c03.yaml        # happy_path 鎴?refusal锛坙ow 涓嶈姹?adversarial锛?
  sample_io/
    c01.json        # 鏈€灏?actual 瀛楁渚?L1
    c02.json
    c03.json
```

- [ ] **Step 1:** 鏂囨。鍖?runbook锛圕LI + UI 姝ラ锛?
- [ ] **Step 2:** 涓轰袱 minimal skill 鍒涘缓涓婅堪鏈€灏忚ˉ鍏ㄦ枃浠讹紙鐢ㄤ簬鑷姩鍖?鎵嬪伐楠屾敹锛?
- [ ] **Step 3:** 璺戦€氱煩闃靛苟璁板綍缁堟€併€佽€楁椂銆乺eason_codes 鍒?runbook

---

## Task 9锛圱9锛夛細鏂囨。鍚屾

**Files:**
- Modify: `RECORD.md`
- Modify: `.project_memory/active/SPRINT_skillhub-mvp.md`

- [ ] 鏇存柊 Q-04 涓?testskills 涓夋牱鏈?
- [ ] In-Progress 鈫?Phase 1 浠诲姟 T1鈥揟8
- [ ] 鍐崇瓥琛細Level0 鎷嗗垎銆乸rovider_summary銆佺粨鏋勬枃浠舵墜鍔ㄨ惤鐩?
- [ ] 鍙樻洿娴佹按涓€鏉?

---

## 鎵ц椤哄簭

```
T1 鈫?T2 鈫?T3 鈫?T4 鈫?T5 鈫?T6 鈫?T7 鈫?T8 鈫?T9
         鈫?gaps 娓呭崟    鈫?report 鍩虹
              鈫?妯℃澘渚濊禆 T2 娓呭崟椤?
T5/T6 鍙儴鍒嗗苟琛岋紱T7 鍦?T5 report 瀛楁绋冲畾鍚庯紱T8 鏈€鍚?live 楠屾敹
```

---

## grill-me 鍐崇瓥璁板綍锛堝凡鍏ㄩ儴閿佸畾 鉁咃級

| Q | 闂 | 鍐冲畾 |
|---|------|------|
| Q1 | degraded + minimal case gate | **B**锛氳烦杩?case gate锛? case 鈫?绌鸿窇 鈫?completeness WARN |
| Q2 | Semaphore + Provider 閲嶈瘯 | **B 鍙樹綋**锛歋emaphore(3)锛?5s timeout锛?03/429 鎸囨暟閫€閬?max 3脳 base 1s |
| Q3 | Gaps API 绔偣 | **A**锛歚GET /bundle/{skill_id}/gaps`锛況eport 鍐呰仈 gaps |
| Q4 | per-case UI 鎶樺彔 + 楂樹寒 | **B**锛歚<details>` 鎶樺彔锛浳斺墺15 娴呯孩楂樹寒 |
| Q5 | 钀界洏妫€娴嬩笌 bundle_state 鍒囨崲 | **B**锛歎I 杞彁绀?checklist + Mode D case gate 纭姤閿欙紱涓嶅姞 422 |
| Q6 | approve 鍚?report 鍥炲啓 | **A**锛歚submit_review` 鍚庨噸鏂?save_report锛宧uman_review 瀛楁鍐欏叆 report_json |
| Q7 | sample_io 鍐呭 | **A**锛歚{"response":"ok","status":"completed"}` 鍗犱綅绗?|
| Q8 | 澶?reason_code 鏂囨浼樺厛绾?| **A**锛歀EVEL0 > TIMEOUT > R5锛涘凡绠楀垎鐓у父灞曠ず + 銆屼粎渚涘弬鑰冦€?|

---

## 涓嶅湪鏈鍒掕寖鍥?

- 2.2 瀵规姉鎬х敤渚嬮泦
- 2.3 Prompt 鏍″噯 / 2.4 涓婃灦鍚庡仴搴锋鏌?
- Portal / PDF 瀵煎嚭
- 鑷姩 scaffold 鍐欑洏 API锛堣嫢 grill-me 寮虹儓闇€瑕侊紝鍙檷涓?T3 鍙€夊瓙浠诲姟锛?

---

## 鍙傝€冭祫鏂?

- `docs/specs/璇勫Agent宸ヤ綔娴佷笌Prompt楠ㄦ灦.md` v0.2 鈥?C-3 鍙岄樁娈?
- `docs/specs/璇勪及鎸囨爣涓庡噯鍏ユ爣鍑?md` v1.2.1 鈥?R5 / X1
- `docs/superpowers/plans/2026-06-02-phase2-eval-engine.md` 鈥?2.0 鍩虹嚎
- `RECORD.md` 路 `.project_memory/active/SPRINT_skillhub-mvp.md`
