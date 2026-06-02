import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
_DEFAULT_FRONTEND = PROJECT_ROOT / "frontend"
DATABASE_DIR = BACKEND_ROOT / "data"
DEFAULT_DATABASE_FILE = DATABASE_DIR / "commitments.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=tuple(
            p for p in (PROJECT_ROOT / ".env", BACKEND_ROOT / ".env") if p.exists()
        )
        or None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Status Check"
    debug: bool = False

    database_url: str = ""

    secret_key: str = "change-me-in-production-use-openssl-rand-hex-32"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24

    scheduler_interval_minutes: int = 5

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    frontend_dir: Path = Path(
        os.getenv("FRONTEND_DIR", str(_DEFAULT_FRONTEND))
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def default_sqlite_url(cls, v: str) -> str:
        if v:
            return v
        DATABASE_DIR.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{DEFAULT_DATABASE_FILE.resolve()}"

    @property
    def templates_dir(self) -> Path:
        return self.frontend_dir / "templates"

    @property
    def static_dir(self) -> Path:
        return self.frontend_dir / "static"


@lru_cache
def get_settings() -> Settings:
    return Settings()
