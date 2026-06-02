from pydantic import BaseModel, Field

from .enums import BundleState, EvaluationMode, RiskLevel


class EvalRunRequest(BaseModel):
    skill_id: str
    skill_bundle_path: str
    bundle_state: BundleState
    evaluation_mode: EvaluationMode
    risk_level_declared: RiskLevel | None = None
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"


class GapsEntry(BaseModel):
    field_path: str
    severity: str
    message: str
    draft_value: str | None = None
    confirmed: bool = False


class GapsSnapshot(BaseModel):
    skill_id: str
    run_id: str
    gaps: list[GapsEntry] = Field(default_factory=list)
    question_queue: list[str] = Field(default_factory=list)


class ConfirmRequest(BaseModel):
    confirmed_fields: dict[str, str]
    confirmed_cases: list[str] = Field(default_factory=list)
    operator: str
