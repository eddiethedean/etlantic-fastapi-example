from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    computed_field,
    model_validator,
)


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


class ApiTokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    value: str = Field(min_length=8, max_length=8192)
    allow_read: bool = True
    allow_write: bool = False

    @model_validator(mode="after")
    def require_permission(self) -> ApiTokenCreate:
        if not self.allow_read and not self.allow_write:
            raise ValueError("At least one of allow_read or allow_write is required")
        return self


class ApiTokenUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    value: str | None = Field(default=None, min_length=8, max_length=8192)
    allow_read: bool | None = None
    allow_write: bool | None = None
    is_active: bool | None = None


class ApiTokenRead(ORMModel):
    id: str
    owner_id: str
    name: str
    last_four: str
    allow_read: bool
    allow_write: bool
    is_active: bool
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TokenReference(BaseModel):
    provider: Literal["user-tokens"] = "user-tokens"
    name: str
    key: Literal["value"] = "value"
    version: Literal["current"] = "current"
    purpose: Literal["read", "write"]


class PipelineTokenGrantCreate(BaseModel):
    token_id: str
    binding: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1, max_length=100)
    location: str | None = None
    operation: Literal["read", "write"]


class PipelineTokenGrantRead(ORMModel):
    id: str
    pipeline_id: str
    token_id: str
    binding: str
    provider: str
    location: str | None
    operation: Literal["read", "write"]
    created_at: datetime
    updated_at: datetime

    @computed_field
    @property
    def secret_ref(self) -> TokenReference:
        return TokenReference(name=self.token_id, purpose=self.operation)


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
