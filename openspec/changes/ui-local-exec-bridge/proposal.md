# Change: ui-local-exec-bridge

> 渚濊禆鍚庣 change `local-agent-exec-bridge`锛圵8 寮曟搸宸茶惤鍦帮紝583 tests锛夈€傛湰 change 鎶?Scan / 閫?CLI / 妯″紡鍒囨崲 / Consent / 鍙岃建 UI 鏆撮湶鍒扮綉椤碉紝**闆?.env 鎵嬪伐閰嶇疆**瀹屾垚 Demo 楠屾敹銆? 
> 绾挎涓庣粍浠舵竻鍗曪紙鏉冨▉瑙嗚锛夛細`docs/superpowers/specs/2026-06-17-ui-local-exec-bridge-wireframes.md`

## Why

W8 鍚庣宸茶兘鍦?`skillhub-eval serve` 鍚屾満 spawn 鏈湴 CLI agent 鐪熻窇 skill锛屼絾缃戦〉 UI **闆舵毚闇?*锛氱敤鎴蜂粛椤绘敼 `.env`锛坄EXEC_SOURCE` / `EXEC_AGENT` / `EXEC_CONSENT_REQUIRED`锛夋垨 Python 娉ㄥ叆 consent锛涢樁娈垫枃妗堜粛鍐欍€岃繍琛屾牱渚嬮銆嶏紝鏃犳硶鍖哄垎鏍蜂緥鑷瘉 vs 鏈湴鐪熻窇銆侽pen Design 宸查獙璇併€孲can 鈫?Radio Card 鈫?鍗虫椂鍒囨崲銆嶇殑 DX锛汼killHub 闇€鍦?**鍒跺紡鍥炲崟** 瑙嗚璇█涓嬭ˉ榻愬悓绛夋劅鐭ワ紝鎵嶈兘鍋氱綉椤电 `exec-fixture-minimal` 楠屾敹骞?archive W8銆?

## What Changes

- 鏂板 **Exec Bridge API**锛歚GET /api/exec/agents/scan`銆乣GET|PUT /api/exec/preferences`銆乣POST /api/exec/consent`銆乣POST /api/exec/agents/{id}/test`锛堣繛鎺ユ祴璇曪級銆?
- **Session 绾?preferences** 鈫?**sqlite 鍏ㄥ眬鍗曡鎸佷箙鍖?*锛坄exec_preferences` 琛紝DB v10锛夛紱瑕嗙洊 env锛涙暣鍙扮數鑴戜竴浠姐€?
- **UI 缁勪欢 C01鈥揅11, C15鈥揅16**锛堣绾挎 doc锛夛細椤舵爮鐘舵€?pill銆?20px 鍙充晶璁剧疆 Drawer銆侀娆¤繘鍏?C16 妯箙銆丅ridgePromptCard锛?*8s poll 鍚屽崱鑷姩鍙樼豢**锛夈€佽瘎浼?Banner / 鎶ュ憡 / 鍘嗗彶鍙岃建鏍囩銆?
- **C16 瀹氱鏂囨**锛氶粯璁ゆ湰鍦?Agent CLI 鐪熻窇娴嬭瘯 Skill锛涘彲閫夊垏鎹㈡牱渚嬭瘎浼?sample_io銆?
- 寮曟搸 `RoutingExecutionSource` 璇诲彇 **session preferences**锛堜紭鍏堜簬 env `EXEC_SOURCE` / `EXEC_AGENT`锛夈€?
- chat 娴?**BridgePromptCard 绾墠绔?*锛坙ocal 鏈氨缁椂锛涗笉鍐?DB锛夛紱灏辩华鍚?in-place 鍙樼豢骞?**鑷姩缁窇**琚嫤鐨勬寮忚瘎浼般€?
- **姝ｅ紡璇勪及闂ㄧ**锛歭ocal 涓旀湭灏辩华 鈫?涓嶅惎鍔紱Skill 瑕佹眰 local 浣嗗叏灞€涓?sample 鈫?**Modal 纭**銆?
- **Non-breaking**锛氱敤鎴峰彲鍒囧洖 sample_io锛岃涓轰笌 W8 鍓嶄竴鑷淬€?

## Capabilities

### New Capabilities

- `exec-bridge-api`: HTTP API for CLI scan, session preferences, consent grant, and agent connection test; wires into existing `LocalAgentSource` / `consent` / adapters.
- `exec-bridge-ui`: Eval UI (`index.html`) components for indicator, settings drawer, onboarding banner, bridge prompt card with poll, dual-track labels in banner/report/history.

### Modified Capabilities

- 锛堟棤锛塦openspec/specs/` 涓昏鑼冪洰褰曚负绌猴紱鍚庣鎵ц璇箟宸插湪 change `local-agent-exec-bridge` 鐨?`specs/skill-execution/spec.md` 瀹氫箟銆傛湰 change 浠呭 UI/API 鏆撮湶灞傘€?

## Non-Goals

- 鐙珛 `skillhub-cli bridge` daemon 鎴栨祻瑙堝櫒鐩磋繛 CLI锛堟灦鏋勪粛涓?serve 鍚屾満 spawn锛夈€?
- Open Design 娣辫壊涓婚 / 涓夋爮 case 渚ф爮閲嶆瀯銆?
- Live Terminal 娴佸紡 log锛圕14锛寁2锛夈€?
- per-case 鎵ц鎽樿鎶樺彔锛圕12鈥揅13锛寁1.5锛夈€?
- W8.4 澶?agent 瀵圭収缁熻銆?
- 淇敼 1.2 闃堝€?/ R1鈥揜8 鍐崇瓥閫昏緫銆?

## Relation to Sprint

闃舵涓?路 Wave 8 UI 灞傦紙`.project_memory/active/SPRINT_phase3-eval-system.md`锛夈€傚悗绔?W8.1鈥揥8.6 鉁咃紱鏈?change = **W8 缃戦〉楠屾敹闂ㄧ**銆傚畬鎴愬悗锛氱綉椤佃窇閫?fixture 鈫?grill-me 鈫?implement 鈫?archive `local-agent-exec-bridge` + `ui-local-exec-bridge` 鈫?W7 鏈嶅姟鍣ㄥ僵鎺掋€?

## Success Criteria

1. 鏂扮敤鎴烽娆¤繘鍏ヨ C16锛涢粯璁?local锛涘彲涓€閿敼 sample_io銆?
2. 璁剧疆 Drawer Rescan 鍒楀嚭 claude/codex/cursor-agent PATH 鐘舵€侊紱Test 鎸夐挳鍙?smoke銆?
3. 涓嶉厤 `.env` EXEC_* 鍗冲彲 local + consent + 閫?agent 璺戦€?`testskills/exec-fixture-minimal`銆?
4. BridgePromptCard 鍦?CLI 灏辩华鍚?**鍚屾皵娉¤嚜鍔ㄥ彉缁?*锛堚墹10s锛夈€?
5. 鎶ュ憡/鍘嗗彶鍙 `execution_source_used` / `spot_check_eligible` 鏍囩锛涘巻鍙茬瓫閫夊彲鐢ㄣ€?
6. `pytest tests/ -q` 鍏ㄧ豢锛堝惈鏂?API + UI smoke 濂戠害娴嬭瘯锛夈€?

## Impact

| 鍖哄煙 | 璺緞 |
|------|------|
| API 璺敱 | `skillhub_eval/adapters/api/routes/exec.py`锛堟柊锛?|
| 鍋忓ソ瀛樺偍 | `skillhub_eval/execution/preferences.py`锛堟柊锛宻ession 浣滅敤鍩燂級 |
| 寮曟搸鎺ョ嚎 | `skillhub_eval/core/execution_source.py`銆乣engine.py`锛堣 preferences锛?|
| UI | `skillhub_eval/adapters/ui/static/index.html` |
| 娴嬭瘯 | `tests/adapters/test_exec_bridge_api.py`銆乣tests/ui/` 鎴?JS 濂戠害 stub |
| 鏂囨。 | `.env.example` 娉ㄦ槑 UI 鍙鐩栵紱鍏ㄦ櫙璇存槑 搂10 涓€鍙?UI 宸叉毚闇?|
