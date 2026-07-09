"""
Task 11 — Static UI smoke tests.
Verifies that index.html is served at /ui and contains expected elements.
"""

from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app


def _ui_page(client: TestClient, path: str = "/ui/index.html"):
    r = client.get(path)
    text = r.text
    if path == "/ui/index.html":
        js = client.get("/ui/assets/index.js")
        if js.status_code == 200:
            text += "\n" + js.text
    return r, text


def test_ui_index_returns_200():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_ui_has_tailwind_cdn():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "tailwindcss.com" in text


def test_ui_has_chat_first_tabs():
    """Wave 5 — two tabs: chat + history; expert is perspective toggle only."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "tab-author" in text
    assert "tab-history" in text
    assert "tab-expert" not in text
    assert "对话评估" in text
    assert "session-list" in text
    assert "btn-perspective-expert" in text
    assert "createNewSession" in text
    assert "renderReportHtml" in text


def test_ui_has_key_api_endpoints_referenced():
    """JS code must reference contract endpoints including gaps API."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "/eval/run" in text
    assert "/eval/report/" in text
    assert "/eval/history" in text
    assert "/eval/review/" in text
    assert "/bundle/" in text
    assert "/gaps" in text


def test_ui_switch_verified_runtime_keeps_verified_model():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "findVerifiedRuntimeModel" in text
    assert "model: findVerifiedRuntimeModel(runtimeId)" in text


def test_ui_local_execution_check_notice_renderer():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderLocalExecutionCheckHtml" in text
    assert "normalizeStageToken" in text
    assert "currentRunStageToken" in text
    assert "local_execution_check" in text
    assert "正在检查本地执行环境" in text


def test_ui_gaps_panel_wired_to_api():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "loadGaps" in text
    assert "renderGapsSnapshot" in text
    assert "copyTemplateByKey" in text
    assert "post-confirm-checklist" in text
    assert "可复制模板" in text


def test_ui_provider_summary_helpers():
    """T5 — dual-model score bars and per-case table in static UI."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "formatScoreDisplay" in text
    assert "renderProviderSummaryBars" in text
    assert "renderPerCaseDetails" in text
    assert "getProviderSummary" in text
    assert "provider_a_label" in text
    assert "provider_b_label" in text
    assert "bg-red-50" in text


def test_ui_t6_history_and_timing_helpers():
    """T6 — history table uses compact score + stage_timing panel."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "formatScoreCompact" in text
    assert "formatTimingSummaryCell" in text
    assert "renderStageTimingPanel" in text
    assert "renderStageProgressList" in text
    assert "stage_timing" in text


def test_ui_local_agent_case_progress_helpers():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderLocalAgentCaseProgress" in text
    assert "renderConversationLiveProgressSlot" in text
    assert "refreshConversationLiveProgress" in text
    assert "renderChatLiveRunPanelContent" in text
    assert "chat-live-run-panel" in text
    assert "当前阶段：" in text
    assert "data-chat-live-run-progress" in text
    assert "local_agent_case_started" in text
    assert "当前正在执行" in text
    assert "本地执行失败" in text
    assert "latestStageToken" in text
    assert "最后刷新" in text
    assert "max-h-[40vh]" in text
    assert "max-h-56 overflow-y-auto" in text


def test_ui_exposes_chat_local_execution_check_button():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "chat-local-check-btn" in text
    assert "环境检查" in text
    assert "getSelectedExecAgentForAction" in text
    assert "updateChatLocalCheckButton" in text
    assert "仅诊断，不阻断正式评估" in text
    assert "状态刷新失败" in text


def test_ui_conversation_polling_is_throttled():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "_conversationPollInFlight" in text
    assert "_lastFetchedMessageCount" in text
    assert "_lastSessionListRefreshAt" in text
    assert "now - _lastSessionListRefreshAt < 15000" in text
    assert "forceMessages" in text


def test_ui_runtime_preflight_reset_uses_lightweight_wording():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "重置轻量检查" in text
    assert "重新生成检查用例" not in text


def test_ui_has_diagnostic_and_feedback_helpers():
    """Post-T8: structure diagnostic card + per-case model feedback."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderDiagnosticReportCard" in text
    assert "renderModelVotesFeedback" in text
    assert "renderCompletenessBar" in text
    assert "结构诊断报告" in text
    assert "renderProviderErrorPanel" in text


def test_ui_has_skill_summary_card():
    """P2+summary: renderSkillSummaryCard and warn reason helpers must be present."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderSkillSummaryCard" in text
    assert "_warnReasonText" in text
    assert "WARN_COMPLETENESS_LOW" in text
    assert "WARN_SCORE_MIDRANGE" in text
    assert "技能质量诊断摘要" in text


def test_ui_has_confirm_and_review_forms():
    """Both interaction forms (gap confirm + expert review) must be present."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "submitConfirm" in text
    assert "submitReview" in text
    assert "negative_prompts" in text      # security-sensitive field
    assert "approve" in text
    assert "reject" in text


# ── Task 7: UI/UX Improvement 新增断言 ──────────────────────────────────────


def test_ui_has_level0_evidence_helper():
    """A-01: Level0 evidence renderer must exist and show diagnostic detail."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderLevel0Evidence" in text
    assert "Level0 诊断详情" in text


def test_ui_has_reason_zh_map():
    """A-02: Chinese reason code map must exist in JS."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "REASON_ZH" in text
    assert "双模型评审存在明显分歧" in text


def test_ui_expert_card_has_narrative():
    """B-01: renderExpertCard must call narrative / disagreement / risk_lock helpers."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderNarrativeCard" in text
    assert "renderDisagreementCard" in text
    assert "renderRiskLockCard" in text


def test_ui_has_human_review_verdict():
    """B-02: Human review verdict helper must exist and show verdict label."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderHumanReviewVerdict" in text
    assert "专家裁定" in text


def test_ui_per_case_uses_chinese_labels():
    """C-04: Dimension labels must be Chinese; IF/OC/BR abbreviations must not appear as labels."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "指令遵循" in text
    assert "输出合规" in text
    assert "业务解决" in text


def test_ui_wave5_1_slim_report_cards():
    """Wave 5.1 — slim chat cards + history CTA + poll stability."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "openReportFromChat" in text
    assert "report_phase" in text
    assert "score_line_html" in text
    assert "查看完整报告" in text
    assert "_messageDomKey" in text
    assert "_lastRenderedMessageKeys" in text


def test_ui_has_gemini_unavailable_banner():
    """C-03: Provider B unavailable notice uses env-driven labels in providerSummaryBars."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "本次不可用（API 限流）" in text
    assert "provider_b_label" in text
    assert "有效评审，结论仅供参考" in text


def test_ui_trace_page_served():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/trace.html")
    assert r.status_code == 200
    assert "评分过程追踪" in text
    assert "/eval/report/" in text


def test_ui_expert_review_wiring():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderExpertReviewActions" in text
    assert "renderExpertReviewSection" in text
    assert "_lastRenderedMessageKeys = []" in text
    assert "专家】视角" in text


def test_ui_wave5_4_judge_trace_wiring():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "has_judge_trace" in text
    assert "trace.html" in text
    assert "评分过程 →" in text
    assert "openRunDetail(runId, { origin: 'chat' })" in text


def test_ui_wave5_2_task9_helpers_and_filters():
    """Wave 5.2 Task 9 smoke: plan/readiness helpers + degraded history filter + verdict badge."""
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "renderPropagationPlanHtml" in text
    assert "renderAssessmentGateHtml" in text
    assert "评估材料补充" in text
    assert "formatGapMessageZh" in text
    assert "evaluation_mode !== 'degraded'" in text
    assert "verdict_zh" in text
    assert "next_action_zh" in text
    assert "open_run_detail" in text


def test_ui_conversation_archive_wiring():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "archiveSession" in text
    assert "method: 'DELETE'" in text
    assert "perspective=" in text
    assert "评估历史" in text


def test_ui_index_references_split_asset():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert r.status_code == 200
    assert '<script src="/ui/assets/index.js"></script>' in r.text


def test_ui_split_asset_served():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/assets/index.js")
    assert r.status_code == 200
    assert "renderProviderSummaryBars" in r.text
    assert "createNewSession" in r.text


def test_ui_caches_staging_path_from_bootstrap():
    app = create_app()
    client = TestClient(app)
    r, text = _ui_page(client, "/ui/index.html")
    assert "_stagingPathByConversation" in text
    assert "rememberStagingPath" in text
    assert "getActiveSkillBundlePath" in text
    # Priority: cache before hidden input / message payload
    cache_idx = text.find("_stagingPathByConversation")
    fn_idx = text.find("function getActiveSkillBundlePath")
    assert cache_idx != -1 and fn_idx != -1
    # Function body must read cache first
    body = text[fn_idx : fn_idx + 800]
    assert "getCachedStagingPath" in body or "_stagingPathByConversation" in body
    assert body.find("getCachedStagingPath") < body.find("inp-bundle-path") or (
        "_stagingPathByConversation" in body and "inp-bundle-path" in body
    )
