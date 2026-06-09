"""
Task 11 — Static UI smoke tests.
Verifies that index.html is served at /ui and contains expected elements.
"""

from fastapi.testclient import TestClient

from skillhub_eval.adapters.api.app import create_app


def test_ui_index_returns_200():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]


def test_ui_has_tailwind_cdn():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "tailwindcss.com" in r.text


def test_ui_has_both_tabs():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "tab-author" in r.text
    assert "tab-expert" in r.text
    assert "tab-history" in r.text


def test_ui_has_key_api_endpoints_referenced():
    """JS code must reference contract endpoints including gaps API."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "/eval/run" in r.text
    assert "/eval/report/" in r.text
    assert "/eval/history" in r.text
    assert "/eval/review/" in r.text
    assert "/bundle/" in r.text
    assert "/gaps" in r.text


def test_ui_gaps_panel_wired_to_api():
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "loadGaps" in r.text
    assert "renderGapsSnapshot" in r.text
    assert "copyTemplateByKey" in r.text
    assert "post-confirm-checklist" in r.text
    assert "可复制模板" in r.text


def test_ui_provider_summary_helpers():
    """T5 — dual-model score bars and per-case table in static UI."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "formatScoreDisplay" in r.text
    assert "renderProviderSummaryBars" in r.text
    assert "renderPerCaseDetails" in r.text
    assert "getProviderSummary" in r.text
    assert "bg-red-50" in r.text


def test_ui_t6_history_and_timing_helpers():
    """T6 — history table uses compact score + stage_timing panel."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "formatScoreCompact" in r.text
    assert "formatTimingSummaryCell" in r.text
    assert "renderStageTimingPanel" in r.text
    assert "renderStageProgressList" in r.text
    assert "stage_timing" in r.text


def test_ui_has_diagnostic_and_feedback_helpers():
    """Post-T8: structure diagnostic card + per-case model feedback."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "renderDiagnosticReportCard" in r.text
    assert "renderModelVotesFeedback" in r.text
    assert "renderCompletenessBar" in r.text
    assert "结构诊断报告" in r.text
    assert "renderProviderErrorPanel" in r.text


def test_ui_has_skill_summary_card():
    """P2+summary: renderSkillSummaryCard and warn reason helpers must be present."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "renderSkillSummaryCard" in r.text
    assert "_warnReasonText" in r.text
    assert "WARN_COMPLETENESS_LOW" in r.text
    assert "WARN_SCORE_MIDRANGE" in r.text
    assert "技能质量诊断摘要" in r.text


def test_ui_has_confirm_and_review_forms():
    """Both interaction forms (gap confirm + expert review) must be present."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "submitConfirm" in r.text
    assert "submitReview" in r.text
    assert "negative_prompts" in r.text      # security-sensitive field
    assert "approve" in r.text
    assert "reject" in r.text


# ── Task 7: UI/UX Improvement 新增断言 ──────────────────────────────────────


def test_ui_has_level0_evidence_helper():
    """A-01: Level0 evidence renderer must exist and show diagnostic detail."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "renderLevel0Evidence" in r.text
    assert "Level0 诊断详情" in r.text


def test_ui_has_reason_zh_map():
    """A-02: Chinese reason code map must exist in JS."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "REASON_ZH" in r.text
    assert "双模型评审存在明显分歧" in r.text


def test_ui_expert_card_has_narrative():
    """B-01: renderExpertCard must call narrative / disagreement / risk_lock helpers."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "renderNarrativeCard" in r.text
    assert "renderDisagreementCard" in r.text
    assert "renderRiskLockCard" in r.text


def test_ui_has_human_review_verdict():
    """B-02: Human review verdict helper must exist and show verdict label."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "renderHumanReviewVerdict" in r.text
    assert "专家裁定" in r.text


def test_ui_per_case_uses_chinese_labels():
    """C-04: Dimension labels must be Chinese; IF/OC/BR abbreviations must not appear as labels."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "指令遵循" in r.text
    assert "输出合规" in r.text
    assert "业务解决" in r.text


def test_ui_has_gemini_unavailable_banner():
    """C-03: Gemini unavailable notice must be wired in providerSummaryBars."""
    app = create_app()
    client = TestClient(app)
    r = client.get("/ui/index.html")
    assert "Gemini 本次不可用" in r.text
