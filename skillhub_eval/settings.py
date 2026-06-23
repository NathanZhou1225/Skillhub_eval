from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    gemini_api_key: str = ""
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai"
    gemini_model: str = "gemini-2.0-flash"
    judge_provider_a_label: str = "DeepSeek"
    judge_provider_a_api_key: str = ""
    judge_provider_a_base_url: str = ""
    judge_provider_a_model: str = ""
    judge_provider_b_label: str = "Gemini"
    judge_provider_b_api_key: str = ""
    judge_provider_b_base_url: str = ""
    judge_provider_b_model: str = ""
    eval_db_path: str = "data/skillhub_eval.db"
    staging_root: str = "data/staging"
    eval_llm_mode: str = "live"
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"
    demo_allow_local_ref: bool = Field(
        default=False,
        validation_alias=AliasChoices("SKILLHUB_DEMO_LOCAL_REF", "DEMO_ALLOW_LOCAL_REF"),
    )

    # LLM / workflow timeouts (seconds) — override via .env, e.g. PROVIDER_CALL_TIMEOUT_S=120
    provider_call_timeout_s: float = 90.0
    provider_call_timeout_high_risk_s: float = 120.0
    workflow_timeout_low_s: int = 600
    workflow_timeout_medium_s: int = 600
    workflow_timeout_high_s: int = 900
    # Local-agent case_exec budget (separate from judge workflow_timeout_* above)
    local_agent_workflow_timeout_low_s: int = 1800
    local_agent_workflow_timeout_medium_s: int = 2400
    local_agent_workflow_timeout_high_s: int = 5400
    divergence_synthesis_timeout_s: float = 120.0

    # Local agent execution bridge (W8) — default sample_io preserves pre-W8 behavior
    exec_source: str = Field(
        default="sample_io",
        validation_alias=AliasChoices("EXEC_SOURCE", "SKILLHUB_EXEC_SOURCE"),
    )
    exec_concurrency: int = Field(
        default=2,
        validation_alias=AliasChoices("EXEC_CONCURRENCY", "SKILLHUB_EXEC_CONCURRENCY"),
    )
    exec_agent: str = Field(
        default="claude",
        validation_alias=AliasChoices("EXEC_AGENT", "SKILLHUB_EXEC_AGENT"),
    )
    exec_consent_required: bool = Field(
        default=True,
        validation_alias=AliasChoices("EXEC_CONSENT_REQUIRED", "SKILLHUB_EXEC_CONSENT_REQUIRED"),
    )


settings = Settings()
