from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class UiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ETLANTIC_UI_",
        extra="ignore",
    )

    api_url: str = "http://127.0.0.1:8000"
    request_timeout_seconds: float = Field(default=15.0, gt=0)
    run_poll_seconds: float = Field(default=2.0, gt=0)


def get_ui_settings() -> UiSettings:
    return UiSettings()
