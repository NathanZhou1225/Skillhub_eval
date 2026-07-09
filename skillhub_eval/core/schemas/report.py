from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import BundleState, EvaluationMode, RiskLevel, ReviewStatus, RunStatus


class ParsedStream(BaseModel):
    final_text: str = ""
    tool_results: list[dict] = Field(default_factory=list)
    usage: dict | None = None
    duration_ms: int | None = None
    is_complete: bool = False
    is_error: bool = False
    error_text: str | None = None


class RunOutcome(BaseModel):
    exit_code: int = 0
    parsed_stream: ParsedStream | None = None
    transcript_ref: str | None = None
    duration_ms: int | None = None
    stderr_text: str | None = None
    workspace_artifacts: list[dict] = Field(default_factory=list)
    early_abort_reason: str | None = None


class ExecResult(BaseModel):
    actual_output: dict | None = None
    source: str = "sample_io"  # sample_io | local_agent
    confidence: str = "high"  # high | low
    transcript_ref: str | None = None
    usage: dict | None = None
    agent_id: str | None = None
    agent_label: str | None = None
    model_id: str | None = None
    model_label: str | None = None
    status: str = "ok"  # ok | incomplete
    level: str = "level_1"  # level_1 | level_2
    degrade_reason: str | None = None
    stderr_excerpt: str | None = None


class DimensionScores(BaseModel):
    instruction_following: float | None = None
    output_compliance: float | None = None
    business_resolution: float | None = None


class ModelVote(BaseModel):
    model: str
    model_version: str
    prompt_version: str
    case_id: str
    dimension_scores: DimensionScores
    score_total: float
    suggested_review_status: str
    confidence: str
    evidence_refs: list[str] = Field(default_factory=list)
    feedback: str = ""
    latency_ms: int = 0


class AssertionResult(BaseModel):
    case_id: str
    assertion_id: str
    passed: bool
    reason_code: str | None = None
    detail: str = ""


class HumanReview(BaseModel):
    required: bool = False
    trigger_codes: list[str] = Field(default_factory=list)
    reviewer_action: str | None = None
    operator: str | None = None
    comment: str = ""
    override_allowed: bool = True


class CaseScoreRow(BaseModel):
    case_id: str
    deepseek_score: float | None = None
    gemini_score: float | None = None
    gap: float | None = None
    ds_suggested_status: str | None = None
    gemini_suggested_status: str | None = None
    exec_status: str | None = None  # "ok" | "incomplete"; None when no local-agent exec attempted
    exec_degrade_reason: str | None = None  # ExecResult.degrade_reason, surfaced for self-diagnosis


class ReportNarrative(BaseModel):
    headline_zh: str = ""
    reasons_zh: list[str] = Field(default_factory=list)
    next_actions_zh: list[str] = Field(default_factory=list)
    score_display_zh: str | None = None


class DisagreementBrief(BaseModel):
    triggered: bool = False
    trigger_kind: str | None = None
    summary_zh: str = ""
    focused_cases: list[dict] = Field(default_factory=list)
    stage_hints_zh: list[str] = Field(default_factory=list)


class RiskLockProvenance(BaseModel):
    declared: str
    rule_scanned: str
    ai_reviewed: str | None = None
    locked: str
    ai_evidence_zh: str | None = None


class ProviderSummary(BaseModel):
    provider_a_label: str = "DeepSeek"
    provider_b_label: str = "Gemini"
    deepseek_score: float | None = None
    gemini_score: float | None = None
    score_gap: float | None = None
    r5_triggered: bool = False
    deepseek_bundle_status: str | None = None
    gemini_bundle_status: str | None = None
    per_case: list[CaseScoreRow] = Field(default_factory=list)


class TokenUsageTotals(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageSummaryRow(BaseModel):
    stage: str
    provider_label: str | None = None
    model: str | None = None
    case_id: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class UsageSummary(BaseModel):
    totals: TokenUsageTotals = Field(default_factory=TokenUsageTotals)
    by_stage: list[UsageSummaryRow] = Field(default_factory=list)
    partial: bool = False


class EvaluationReport(BaseModel):
    run_id: str
    skill_id: str
    skill_bundle_path: str
    bundle_state: BundleState
    evaluation_mode: EvaluationMode
    orchestration_mode: str | None = None
    status: RunStatus | str
    review_status: ReviewStatus | str | None = None
    risk_level_locked: RiskLevel | None = None
    level_achieved: str | None = None
    score_total: float | None = None
    score_total_source: str | None = None
    completeness_score: float | None = None
    reason_codes: list[str] = Field(default_factory=list)
    evidence: list[dict] = Field(default_factory=list)
    required_actions: list[str] = Field(default_factory=list)
    gaps: list[dict] = Field(default_factory=list)
    stage_progress: list[str | dict] = Field(default_factory=list)
    provider_summary: ProviderSummary | None = None
    model_votes: list[ModelVote] = Field(default_factory=list)
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    human_review: HumanReview = Field(default_factory=HumanReview)
    skill_summary: dict | None = None
    narrative: ReportNarrative | None = None
    disagreement_brief: DisagreementBrief | None = None
    risk_lock_provenance: RiskLockProvenance | None = None
    security_status: str | None = None       # "passed" | "warning" | "blocked"
    security_findings: list[dict] = Field(default_factory=list)
    output_sanitizer_status: str | None = None   # "passed" | "leak"
    output_sanitizer_findings: list[dict] = Field(default_factory=list)
    case_type_coverage: dict[str, int] = Field(default_factory=dict)
    spot_check_eligible: bool = False
    execution_source_used: str | None = None
    exec_agent_id: str | None = None
    exec_agent_label: str | None = None
    exec_model_id: str | None = None
    exec_model_label: str | None = None
    # What the user selected in exec preferences — populated regardless of
    # whether local execution actually succeeded. exec_agent_label/exec_model_label
    # above are ONLY populated when a case genuinely executed via local_agent;
    # never inferred from preferences alone (see local-agent-trial-hardening).
    exec_requested_agent_label: str | None = None
    exec_requested_model_label: str | None = None
    usage_summary: UsageSummary | None = None
    # e.g. {"happy_path": 3, "edge": 2, "refusal": 0, "adversarial": 0}
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_detail: str | None = None
