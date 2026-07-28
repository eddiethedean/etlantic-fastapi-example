from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from etlantic_runner.config import Settings, get_settings
from etlantic_runner.database import get_db
from etlantic_runner.etlantic_service import (
    apply_document_edit,
    service_for,
    verify_document,
)
from etlantic_runner.models import Pipeline, PipelineRun, Schedule, User
from etlantic_runner.runner import PipelineRunner
from etlantic_runner.scheduler import ScheduleManager
from etlantic_runner.schemas import (
    PipelineCreate,
    PipelineEdit,
    PipelineRead,
    PipelineUpdate,
    PlanResult,
    RunRead,
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
    Token,
    UserCreate,
    UserRead,
    UserUpdate,
    ValidationResult,
)
from etlantic_runner.security import (
    AdminUser,
    CurrentUser,
    create_access_token,
    hash_password,
    verify_password,
)

DbSession = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def not_found(kind: str) -> HTTPException:
    return HTTPException(status_code=404, detail=f"{kind} not found")


def owned_pipeline(db: Session, pipeline_id: str, user: User) -> Pipeline:
    pipeline = db.scalar(
        select(Pipeline).where(
            Pipeline.id == pipeline_id,
            Pipeline.owner_id == user.id,
        )
    )
    if pipeline is None:
        raise not_found("Pipeline")
    return pipeline


def owned_schedule(db: Session, schedule_id: str, user: User) -> Schedule:
    schedule = db.scalar(
        select(Schedule).where(
            Schedule.id == schedule_id,
            Schedule.owner_id == user.id,
        )
    )
    if schedule is None:
        raise not_found("Schedule")
    return schedule


def etlantic_bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


auth = APIRouter(prefix="/auth", tags=["auth"])
users = APIRouter(prefix="/users", tags=["users"])
pipelines = APIRouter(prefix="/pipelines", tags=["pipelines"])
runs = APIRouter(prefix="/runs", tags=["runs"])
schedules = APIRouter(prefix="/schedules", tags=["schedules"])


@users.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(body: UserCreate, db: DbSession) -> User:
    user = User(
        email=str(body.email).lower(),
        display_name=body.display_name,
        password_hash=hash_password(body.password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email is already registered") from exc
    db.refresh(user)
    return user


@auth.post("/token", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
    settings: AppSettings,
) -> Token:
    user = db.scalar(select(User).where(User.email == form.username.lower()))
    if (
        user is None
        or not user.is_active
        or not verify_password(form.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=401,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(user, settings)
    return Token(access_token=token, expires_in=expires_in)


@users.get("/me", response_model=UserRead)
def read_me(user: CurrentUser) -> User:
    return user


@users.patch("/me", response_model=UserRead)
def update_me(body: UserUpdate, user: CurrentUser, db: DbSession) -> User:
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.password is not None:
        user.password_hash = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user


@users.get("", response_model=list[UserRead])
def list_users(
    _: AdminUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[User]:
    return list(db.scalars(select(User).offset(offset).limit(limit)))


@users.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_me(user: CurrentUser, db: DbSession) -> None:
    user.is_active = False
    db.commit()


@pipelines.post("", response_model=PipelineRead, status_code=status.HTTP_201_CREATED)
def create_pipeline(
    body: PipelineCreate,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> Pipeline:
    try:
        document, fingerprint = verify_document(body.document, "new", settings)
    except Exception as exc:
        raise etlantic_bad_request(exc) from exc
    pipeline = Pipeline(
        owner_id=user.id,
        name=body.name,
        description=body.description,
        document=document,
        fingerprint=fingerprint,
    )
    db.add(pipeline)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A pipeline with this name already exists"
        ) from exc
    db.refresh(pipeline)
    return pipeline


@pipelines.get("", response_model=list[PipelineRead])
def list_pipelines(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Pipeline]:
    stmt = (
        select(Pipeline)
        .where(Pipeline.owner_id == user.id)
        .order_by(Pipeline.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@pipelines.get("/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(pipeline_id: str, user: CurrentUser, db: DbSession) -> Pipeline:
    return owned_pipeline(db, pipeline_id, user)


@pipelines.patch("/{pipeline_id}", response_model=PipelineRead)
def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> Pipeline:
    pipeline = owned_pipeline(db, pipeline_id, user)
    if body.expected_version is not None and body.expected_version != pipeline.version:
        raise HTTPException(status_code=409, detail="Pipeline version conflict")
    if body.name is not None:
        pipeline.name = body.name
    if "description" in body.model_fields_set:
        pipeline.description = body.description
    if body.document is not None:
        try:
            document, fingerprint = verify_document(
                body.document, pipeline.id, settings
            )
        except Exception as exc:
            raise etlantic_bad_request(exc) from exc
        pipeline.document = document
        pipeline.fingerprint = fingerprint
    pipeline.version += 1
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A pipeline with this name already exists"
        ) from exc
    db.refresh(pipeline)
    return pipeline


@pipelines.post("/{pipeline_id}/edits", response_model=PipelineRead)
def edit_pipeline(
    pipeline_id: str,
    body: PipelineEdit,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> Pipeline:
    pipeline = owned_pipeline(db, pipeline_id, user)
    try:
        document, fingerprint = apply_document_edit(
            pipeline.document,
            pipeline.id,
            body.command,
            body.expected_token,
            settings,
        )
    except Exception as exc:
        raise etlantic_bad_request(exc) from exc
    pipeline.document = document
    pipeline.fingerprint = fingerprint
    pipeline.version += 1
    db.commit()
    db.refresh(pipeline)
    return pipeline


@pipelines.delete("/{pipeline_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pipeline(pipeline_id: str, user: CurrentUser, db: DbSession) -> None:
    db.delete(owned_pipeline(db, pipeline_id, user))
    db.commit()


@pipelines.post("/{pipeline_id}/validate", response_model=ValidationResult)
def validate_pipeline(
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    pipeline = owned_pipeline(db, pipeline_id, user)
    try:
        return service_for(pipeline.document, pipeline.id, settings).validate(
            pipeline.id
        )
    except Exception as exc:
        raise etlantic_bad_request(exc) from exc


@pipelines.post("/{pipeline_id}/plan", response_model=PlanResult)
def plan_pipeline(
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    pipeline = owned_pipeline(db, pipeline_id, user)
    try:
        return service_for(pipeline.document, pipeline.id, settings).plan(pipeline.id)
    except Exception as exc:
        raise etlantic_bad_request(exc) from exc


@pipelines.post(
    "/{pipeline_id}/runs",
    response_model=RunRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_pipeline(
    request: Request,
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
) -> PipelineRun:
    pipeline = owned_pipeline(db, pipeline_id, user)
    return request.app.state.runner.submit(pipeline, session=db)


@runs.get("", response_model=list[RunRead])
def list_runs(
    user: CurrentUser,
    db: DbSession,
    pipeline_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[PipelineRun]:
    stmt = (
        select(PipelineRun)
        .where(PipelineRun.owner_id == user.id)
        .order_by(PipelineRun.created_at.desc())
    )
    if pipeline_id is not None:
        stmt = stmt.where(PipelineRun.pipeline_id == pipeline_id)
    return list(db.scalars(stmt.offset(offset).limit(limit)))


@runs.get("/{run_id}", response_model=RunRead)
def get_run(run_id: str, user: CurrentUser, db: DbSession) -> PipelineRun:
    run = db.scalar(
        select(PipelineRun).where(
            PipelineRun.id == run_id,
            PipelineRun.owner_id == user.id,
        )
    )
    if run is None:
        raise not_found("Run")
    return run


@pipelines.post(
    "/{pipeline_id}/schedules",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    request: Request,
    pipeline_id: str,
    body: ScheduleCreate,
    user: CurrentUser,
    db: DbSession,
) -> Schedule:
    pipeline = owned_pipeline(db, pipeline_id, user)
    manager: ScheduleManager = request.app.state.schedule_manager
    try:
        manager.validate(body.trigger_type, body.trigger_args)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    schedule = Schedule(
        owner_id=user.id,
        pipeline_id=pipeline.id,
        name=body.name,
        trigger_type=body.trigger_type,
        trigger_args=body.trigger_args,
        enabled=body.enabled,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    manager.sync(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@schedules.get("", response_model=list[ScheduleRead])
def list_schedules(user: CurrentUser, db: DbSession) -> list[Schedule]:
    return list(
        db.scalars(
            select(Schedule)
            .where(Schedule.owner_id == user.id)
            .order_by(Schedule.created_at.desc())
        )
    )


@schedules.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(schedule_id: str, user: CurrentUser, db: DbSession) -> Schedule:
    return owned_schedule(db, schedule_id, user)


@schedules.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    request: Request,
    schedule_id: str,
    body: ScheduleUpdate,
    user: CurrentUser,
    db: DbSession,
) -> Schedule:
    schedule = owned_schedule(db, schedule_id, user)
    trigger_type = body.trigger_type or schedule.trigger_type
    trigger_args = body.trigger_args or schedule.trigger_args
    manager: ScheduleManager = request.app.state.schedule_manager
    try:
        manager.validate(trigger_type, trigger_args)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if body.name is not None:
        schedule.name = body.name
    schedule.trigger_type = trigger_type
    schedule.trigger_args = trigger_args
    if body.enabled is not None:
        schedule.enabled = body.enabled
    manager.sync(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@schedules.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    request: Request,
    schedule_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    schedule = owned_schedule(db, schedule_id, user)
    request.app.state.schedule_manager.remove(schedule.id)
    db.delete(schedule)
    db.commit()


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if resolved_settings.auto_migrate:
            alembic = Config("alembic.ini")
            alembic.set_main_option("sqlalchemy.url", resolved_settings.database_url)
            command.upgrade(alembic, "head")
        runner = PipelineRunner(resolved_settings)
        schedule_manager = ScheduleManager(runner)
        app.state.runner = runner
        app.state.schedule_manager = schedule_manager
        schedule_manager.start()
        try:
            yield
        finally:
            schedule_manager.shutdown()
            runner.shutdown()

    app = FastAPI(
        title="ETLantic Runner API",
        version="0.1.0",
        description="Create, edit, run, and schedule ETLantic pipelines.",
        lifespan=lifespan,
    )
    app.include_router(auth)
    app.include_router(users)
    app.include_router(pipelines)
    app.include_router(runs)
    app.include_router(schedules)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

