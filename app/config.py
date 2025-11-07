from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "dev"
    gcp_project: str | None = None
    bq_default_location: str | None = None
    maximum_bytes_billed: int = 5_000_000_000  # 5 GB default safety
    dry_run_only: bool = True  # scaffold default
    price_per_tb_usd: float = 5.0
    # LLM settings
    llm_provider: str | None = "openai"  # "openai" | "gemini" | "claude"
    openai_api_key: str | None = None
    openai_model: str | None = None
    anthropic_api_key: str | None = None
    anthropic_model: str | None = None
    gemini_api_key: str | None = None
    gemini_model: str | None = None
    # LLM tuning
    llm_temperature: float = 0.1
    llm_max_tokens: int = 1024
    llm_system_prompt: str | None = (
        "You are an expert data analyst. Generate ONLY BigQuery SQL inside a code fence."
    )
    # LLM usage toggles
    llm_enable_repair: bool = True
    llm_repair_max_attempts: int = 1
    llm_enable_result_summary: bool = False
    # Materialization
    bq_materialize_dataset: str | None = None  # e.g., project.dataset
    bq_materialize_expiration_hours: int = 24
    # Logging to file (optional)
    log_file_path: str | None = None  # e.g., "logs/app.log" to enable
    log_max_bytes: int = 5_000_000
    log_backup_count: int = 5

    class Config:
        env_file = ".env"


settings = Settings()
