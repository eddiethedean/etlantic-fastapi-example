from __future__ import annotations

import logging
from datetime import UTC
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from etlantic_runner.database import SessionLocal
from etlantic_runner.models import Schedule
from etlantic_runner.runner import PipelineRunner

logger = logging.getLogger(__name__)


class ScheduleManager:
    def __init__(self, runner: PipelineRunner) -> None:
        self.runner = runner
        self.scheduler = BackgroundScheduler(timezone=UTC)

    def start(self) -> None:
        self.scheduler.start()
        with SessionLocal() as session:
            schedules = session.query(Schedule).filter(Schedule.enabled.is_(True)).all()
            for schedule in schedules:
                try:
                    self.sync(schedule)
                except Exception:
                    logger.exception("Could not restore schedule %s", schedule.id)
            session.commit()

    def build_trigger(self, trigger_type: str, args: dict[str, Any]):
        trigger_args = dict(args)
        timezone = trigger_args.pop("timezone", UTC)
        try:
            if trigger_type == "cron":
                return CronTrigger(**trigger_args, timezone=timezone)
            if trigger_type == "interval":
                return IntervalTrigger(**trigger_args, timezone=timezone)
            if trigger_type == "date":
                return DateTrigger(**trigger_args, timezone=timezone)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid {trigger_type} trigger: {exc}") from exc
        raise ValueError(f"Unsupported trigger type: {trigger_type}")

    def validate(self, trigger_type: str, args: dict[str, Any]) -> None:
        self.build_trigger(trigger_type, args)

    def sync(self, schedule: Schedule) -> None:
        job_id = self.job_id(schedule.id)
        if not schedule.enabled:
            self.remove(schedule.id)
            schedule.next_run_at = None
            return
        trigger = self.build_trigger(schedule.trigger_type, schedule.trigger_args)
        job = self.scheduler.add_job(
            self.runner.submit_by_pipeline_id,
            trigger=trigger,
            args=[schedule.pipeline_id, schedule.id],
            id=job_id,
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=300,
        )
        schedule.next_run_at = job.next_run_time

    def remove(self, schedule_id: str) -> None:
        job = self.scheduler.get_job(self.job_id(schedule_id))
        if job is not None:
            self.scheduler.remove_job(job.id)

    @staticmethod
    def job_id(schedule_id: str) -> str:
        return f"schedule:{schedule_id}"

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
