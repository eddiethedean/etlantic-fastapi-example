from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from etlantic_runner.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    return str(uuid.uuid4())


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)

    pipelines: Mapped[list[Pipeline]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Pipeline(TimestampMixin, Base):
    __tablename__ = "pipelines"

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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
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

