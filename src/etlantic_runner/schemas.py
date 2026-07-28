from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    password: str | None = Field(default=None, min_length=12, max_length=128)


class UserRead(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class PipelineCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    document: dict[str, Any]


class PipelineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    document: dict[str, Any] | None = None
    expected_version: int | None = Field(default=None, ge=1)


class PipelineRead(ORMModel):
    id: str
    owner_id: str
    name: str
    description: str | None
    document: dict[str, Any]
    fingerprint: str
    version: int
    created_at: datetime
    updated_at: datetime


class PipelineEdit(BaseModel):
    command: dict[str, Any]
    expected_token: str | None = None


class ValidationResult(BaseModel):
    ok: bool
    diagnostics: list[dict[str, Any]]
    fingerprint: str


class PlanResult(BaseModel):
    ok: bool
    diagnostics: list[dict[str, Any]]
    plan: dict[str, Any] | None


class RunRead(ORMModel):
    id: str
    owner_id: str
    pipeline_id: str
    schedule_id: str | None
    status: str
    pipeline_version: int
    pipeline_fingerprint: str
    report: dict[str, Any] | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class ScheduleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    trigger_type: Literal["cron", "interval", "date"]
    trigger_args: dict[str, Any]
    enabled: bool = True

    @model_validator(mode="after")
    def validate_trigger_args(self) -> ScheduleCreate:
        if not self.trigger_args:
            raise ValueError("trigger_args must not be empty")
        if self.trigger_type == "interval" and not any(
            key in self.trigger_args
            for key in ("weeks", "days", "hours", "minutes", "seconds")
        ):
            raise ValueError("interval requires a time interval")
        if self.trigger_type == "date" and "run_date" not in self.trigger_args:
            raise ValueError("date requires trigger_args.run_date")
        return self


class ScheduleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    trigger_type: Literal["cron", "interval", "date"] | None = None
    trigger_args: dict[str, Any] | None = None
    enabled: bool | None = None


class ScheduleRead(ORMModel):
    id: str
    owner_id: str
    pipeline_id: str
    name: str
    trigger_type: str
    trigger_args: dict[str, Any]
    enabled: bool
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime

