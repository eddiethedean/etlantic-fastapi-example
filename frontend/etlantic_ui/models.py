from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class UserRead(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime


class PipelineRead(ORMModel):
    id: str
    owner_id: str
    name: str
    description: str | None
    document: dict[str, Any]
    fingerprint: str
    version: int
    access_source: Literal["owned", "group"]
    can_delete: bool
    shared_group_ids: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class PipelineDraftResult(BaseModel):
    ok: bool
    document: dict[str, Any] | None = None
    fingerprint: str | None = None
    diagnostics: list[dict[str, Any]] = Field(default_factory=list)


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
    secret_ref: TokenReference | None = None


class GroupRead(ORMModel):
    id: str
    owner_id: str
    name: str
    description: str | None
    current_user_role: Literal["owner", "member"]
    created_at: datetime
    updated_at: datetime


class GroupMemberRead(ORMModel):
    id: str
    group_id: str
    user_id: str
    role: Literal["owner", "member"]
    user: UserRead
    created_at: datetime


class GroupInvitationRead(ORMModel):
    id: str
    group_id: str
    email: EmailStr
    invited_by_id: str
    status: Literal["pending", "accepted", "revoked", "expired"]
    expires_at: datetime
    accepted_by_id: str | None
    accepted_at: datetime | None
    created_at: datetime


class GroupInvitationCreated(GroupInvitationRead):
    accept_token: str


class PipelineGroupRead(ORMModel):
    id: str
    pipeline_id: str
    group_id: str
    added_by_id: str
    created_at: datetime
