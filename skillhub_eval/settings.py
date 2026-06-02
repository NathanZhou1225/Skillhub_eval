from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    workbuddy_api_key: str = ""
    workbuddy_base_url: str = ""
    eval_db_path: str = "data/skillhub_eval.db"
    eval_llm_mode: str = "live"
    rubric_version: str = "v1.2"
    prompt_version: str = "review-agent-v0.2"


settings = Settings()
