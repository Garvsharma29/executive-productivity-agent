"""Application settings loaded from environment variables."""

from pathlib import Path

from pydantic_settings import BaseSettings
from pydantic import ConfigDict


# Project root — two levels up from this file (backend/app/core/config.py → project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class Settings(BaseSettings):
    """Central configuration — values come from .env or the OS environment."""

    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    app_debug: bool = True

    # PostgreSQL
    postgres_user: str = "epa_user"
    postgres_password: str = "change_me_in_production"
    postgres_db: str = "epa_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Data pack — configurable path, default is project-relative
    data_pack_path: str = str(_PROJECT_ROOT / "data" / "raw" / "executive_data_pack.md")

    # Optional direct database URL override
    db_url: str | None = None

    @property
    def database_url(self) -> str:
        import os
        if "DATABASE_URL" in os.environ and os.environ["DATABASE_URL"]:
            return os.environ["DATABASE_URL"]
        if self.db_url:
            return self.db_url
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


settings = Settings()


