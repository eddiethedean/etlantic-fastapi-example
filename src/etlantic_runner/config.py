from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ETLANTIC_",
        extra="ignore",
    )

    database_url: str = "sqlite:///./etlantic_runner.db"
    jwt_secret: str = Field(
        default="development-only-change-this-secret-key",
        min_length=32,
    )
    jwt_algorithm: Literal["HS256", "HS384", "HS512"] = "HS256"
    token_encryption_key: str = Field(
        default="",
        description="URL-safe base64-encoded 32-byte Fernet key.",
    )
    access_token_minutes: int = Field(default=30, gt=0)
    max_workers: int = Field(default=4, ge=1, le=64)
    profile: str = "development"
    auto_migrate: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
