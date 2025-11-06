from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    env: str = "dev"
    gcp_project: str | None = None
    bq_default_location: str | None = None
    maximum_bytes_billed: int = 5_000_000_000  # 5 GB default safety
    dry_run_only: bool = True  # scaffold default
    price_per_tb_usd: float = 5.0

    class Config:
        env_file = ".env"


settings = Settings()
