from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from etlantic_runner.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    pipelines: Mapped[list[Pipeline]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    api_tokens: Mapped[list[ApiToken]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    group_memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Pipeline(TimestampMixin, Base):
    __tablename__ = "pipelines"
    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_pipeline_owner_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    document: Mapped[dict[str, Any]] = mapped_column(JSON)
    fingerprint: Mapped[str] = mapped_column(String(128))
    version: Mapped[int] = mapped_column(Integer, default=1)

    owner: Mapped[User] = relationship(back_populates="pipelines")
    runs: Mapped[list[PipelineRun]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )
    schedules: Mapped[list[Schedule]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )
    token_grants: Mapped[list[PipelineTokenGrant]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )
    group_links: Mapped[list[PipelineGroup]] = relationship(
        back_populates="pipeline", cascade="all, delete-orphan"
    )


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True
    )
    schedule_id: Mapped[str | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[str] = mapped_column(String(24), default="queued")
    pipeline_version: Mapped[int] = mapped_column(Integer)
    pipeline_fingerprint: Mapped[str] = mapped_column(String(128))
    pipeline_document: Mapped[dict[str, Any]] = mapped_column(JSON)
    report: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pipeline: Mapped[Pipeline] = relationship(back_populates="runs")
    schedule: Mapped[Schedule | None] = relationship(back_populates="runs")


class Schedule(TimestampMixin, Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    trigger_type: Mapped[str] = mapped_column(String(20))
    trigger_args: Mapped[dict[str, Any]] = mapped_column(JSON)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    pipeline: Mapped[Pipeline] = relationship(back_populates="schedules")
    runs: Mapped[list[PipelineRun]] = relationship(back_populates="schedule")


class ApiToken(TimestampMixin, Base):
    __tablename__ = "api_tokens"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_token_owner_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    encrypted_value: Mapped[bytes] = mapped_column()
    last_four: Mapped[str] = mapped_column(String(4))
    allow_read: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_write: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    owner: Mapped[User] = relationship(back_populates="api_tokens")
    grants: Mapped[list[PipelineTokenGrant]] = relationship(
        back_populates="token", cascade="all, delete-orphan"
    )


class PipelineTokenGrant(TimestampMixin, Base):
    __tablename__ = "pipeline_token_grants"
    __table_args__ = (
        UniqueConstraint(
            "pipeline_id",
            "binding",
            name="uq_pipeline_binding",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True
    )
    token_id: Mapped[str] = mapped_column(
        ForeignKey("api_tokens.id", ondelete="CASCADE"), index=True
    )
    binding: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(100))
    location: Mapped[str | None] = mapped_column(Text)
    operation: Mapped[str] = mapped_column(String(10))

    pipeline: Mapped[Pipeline] = relationship(back_populates="token_grants")
    token: Mapped[ApiToken] = relationship(back_populates="grants")


class Group(TimestampMixin, Base):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_group_owner_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text)

    owner: Mapped[User] = relationship(foreign_keys=[owner_id])
    memberships: Mapped[list[GroupMembership]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    invitations: Mapped[list[GroupInvitation]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    pipeline_links: Mapped[list[PipelineGroup]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMembership(TimestampMixin, Base):
    __tablename__ = "group_memberships"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_membership"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(20), default="member")

    group: Mapped[Group] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="group_memberships")


class GroupInvitation(TimestampMixin, Base):
    __tablename__ = "group_invitations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    email: Mapped[str] = mapped_column(String(320), index=True)
    invited_by_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    group: Mapped[Group] = relationship(back_populates="invitations")
    invited_by: Mapped[User] = relationship(foreign_keys=[invited_by_id])
    accepted_by: Mapped[User | None] = relationship(foreign_keys=[accepted_by_id])


class PipelineGroup(TimestampMixin, Base):
    __tablename__ = "pipeline_groups"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "group_id", name="uq_pipeline_group"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    pipeline_id: Mapped[str] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), index=True
    )
    group_id: Mapped[str] = mapped_column(
        ForeignKey("groups.id", ondelete="CASCADE"), index=True
    )
    added_by_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    pipeline: Mapped[Pipeline] = relationship(back_populates="group_links")
    group: Mapped[Group] = relationship(back_populates="pipeline_links")
    added_by: Mapped[User] = relationship()
