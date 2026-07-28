from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

from etlantic.lifecycle.runtime import PipelineRuntime
from etlantic.registry import BindingDescriptor
from etlantic.secrets import SecretRef
from sqlalchemy.orm import Session

from etlantic_runner.config import Settings
from etlantic_runner.database import SessionLocal
from etlantic_runner.etlantic_service import service_for
from etlantic_runner.models import Pipeline, PipelineRun, PipelineTokenGrant
from etlantic_runner.token_store import UserTokenProvider

logger = logging.getLogger(__name__)


class PipelineRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.executor = ThreadPoolExecutor(
            max_workers=settings.max_workers,
            thread_name_prefix="etlantic-run",
        )

    def submit(
        self,
        pipeline: Pipeline,
        *,
        schedule_id: str | None = None,
        session: Session,
    ) -> PipelineRun:
        run = PipelineRun(
            owner_id=pipeline.owner_id,
            pipeline_id=pipeline.id,
            schedule_id=schedule_id,
            status="queued",
            pipeline_version=pipeline.version,
            pipeline_fingerprint=pipeline.fingerprint,
            pipeline_document=pipeline.document,
        )
        session.add(run)
        session.commit()
        session.refresh(run)
        self.executor.submit(self._execute, run.id)
        return run

    def submit_by_pipeline_id(
        self, pipeline_id: str, schedule_id: str | None = None
    ) -> str | None:
        with SessionLocal() as session:
            pipeline = session.get(Pipeline, pipeline_id)
            if pipeline is None:
                logger.warning("Scheduled pipeline %s no longer exists", pipeline_id)
                return None
            return self.submit(
                pipeline, schedule_id=schedule_id, session=session
            ).id

    def _execute(self, run_id: str) -> None:
        with SessionLocal() as session:
            run = session.get(PipelineRun, run_id)
            if run is None:
                return
            run.status = "running"
            run.started_at = datetime.now(UTC)
            session.commit()
            try:
                runtime = self._runtime_for(run)
                service = service_for(
                    run.pipeline_document,
                    run.pipeline_id,
                    self.settings,
                    runtime=runtime,
                )
                result = service.submit_run(run.pipeline_id)
                run.status = result["status"]
                run.report = result["report"]
                run.error = result["error"]
            except Exception:
                logger.exception("Pipeline run %s failed", run_id)
                run.status = "failed"
                run.error = "Pipeline execution failed; inspect server logs"
            finally:
                run.finished_at = datetime.now(UTC)
                session.commit()

    def _runtime_for(self, run: PipelineRun) -> PipelineRuntime:
        runtime = PipelineRuntime()
        runtime.register_secret_provider(
            "user-tokens",
            UserTokenProvider(run.owner_id, self.settings),
        )
        with SessionLocal() as session:
            grants = (
                session.query(PipelineTokenGrant)
                .filter(PipelineTokenGrant.pipeline_id == run.pipeline_id)
                .all()
            )
            for grant in grants:
                runtime.registry.register_binding(
                    BindingDescriptor(
                        binding=grant.binding,
                        provider=grant.provider,
                        location=grant.location,
                        secret_ref=SecretRef(
                            provider="user-tokens",
                            name=grant.token_id,
                            key="value",
                            purpose=grant.operation,
                        ),
                    )
                )
        return runtime

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=False)
