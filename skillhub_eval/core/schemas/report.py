from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import BundleState, EvaluationMode, RiskLevel, ReviewStatus, RunStatus


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


class ProviderSummary(BaseModel):
    deepseek_score: float | None = None
    gemini_score: float | None = None
    score_gap: float | None = None
    r5_triggered: bool = False
    deepseek_bundle_status: str | None = None
    gemini_bundle_status: str | None = None
    per_case: list[CaseScoreRow] = Field(default_factory=list)


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
    stage_progress: list[str] = Field(default_factory=list)
    provider_summary: ProviderSummary | None = None
    model_votes: list[ModelVote] = Field(default_factory=list)
    assertion_results: list[AssertionResult] = Field(default_factory=list)
    human_review: HumanReview = Field(default_factory=HumanReview)
    skill_summary: dict | None = None
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_detail: str | None = None
