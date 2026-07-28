from __future__ import annotations

import hashlib
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

from alembic import command
from alembic.config import Config
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from etlantic_runner.config import Settings, get_settings
from etlantic_runner.database import get_db
from etlantic_runner.etlantic_service import (
    apply_document_edit,
    service_for,
    verify_document,
)
from etlantic_runner.models import (
    ApiToken,
    Group,
    GroupInvitation,
    GroupMembership,
    Pipeline,
    PipelineGroup,
    PipelineRun,
    PipelineTokenGrant,
    Schedule,
    User,
)
from etlantic_runner.runner import PipelineRunner
from etlantic_runner.scheduler import ScheduleManager
from etlantic_runner.schemas import (
    ApiTokenCreate,
    ApiTokenRead,
    ApiTokenUpdate,
    GroupCreate,
    GroupInvitationAccept,
    GroupInvitationCreate,
    GroupInvitationCreated,
    GroupInvitationRead,
    GroupMemberRead,
    GroupRead,
    GroupUpdate,
    PipelineCreate,
    PipelineEdit,
    PipelineGroupRead,
    PipelineRead,
    PipelineTokenGrantCreate,
    PipelineTokenGrantRead,
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
from etlantic_runner.token_store import TokenCipher

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


def accessible_pipeline(db: Session, pipeline_id: str, user: User) -> Pipeline:
    pipeline = db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise not_found("Pipeline")
    if pipeline.owner_id == user.id:
        return pipeline
    membership = db.scalar(
        select(GroupMembership.id)
        .join(PipelineGroup, PipelineGroup.group_id == GroupMembership.group_id)
        .where(
            PipelineGroup.pipeline_id == pipeline.id,
            GroupMembership.user_id == user.id,
        )
        .limit(1)
    )
    if membership is None:
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


def owned_token(db: Session, token_id: str, user: User) -> ApiToken:
    token = db.scalar(
        select(ApiToken).where(
            ApiToken.id == token_id,
            ApiToken.owner_id == user.id,
        )
    )
    if token is None:
        raise not_found("Token")
    return token


def group_membership(db: Session, group_id: str, user: User) -> GroupMembership:
    membership = db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == user.id,
        )
    )
    if membership is None:
        raise not_found("Group")
    return membership


def etlantic_bad_request(exc: Exception) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


auth = APIRouter(prefix="/auth", tags=["auth"])
users = APIRouter(prefix="/users", tags=["users"])
pipelines = APIRouter(prefix="/pipelines", tags=["pipelines"])
runs = APIRouter(prefix="/runs", tags=["runs"])
schedules = APIRouter(prefix="/schedules", tags=["schedules"])
tokens = APIRouter(prefix="/tokens", tags=["tokens"])
groups = APIRouter(prefix="/groups", tags=["groups"])
group_invitations = APIRouter(prefix="/group-invitations", tags=["groups"])


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
        raise HTTPException(
            status_code=409, detail="Email is already registered"
        ) from exc
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


@groups.post("", response_model=GroupRead, status_code=status.HTTP_201_CREATED)
def create_group(body: GroupCreate, user: CurrentUser, db: DbSession) -> Group:
    group = Group(owner_id=user.id, name=body.name, description=body.description)
    db.add(group)
    try:
        db.flush()
        db.add(
            GroupMembership(group_id=group.id, user_id=user.id, role="owner")
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="You already own a group with this name"
        ) from exc
    db.refresh(group)
    return group


@groups.get("", response_model=list[GroupRead])
def list_groups(user: CurrentUser, db: DbSession) -> list[Group]:
    return list(
        db.scalars(
            select(Group)
            .join(GroupMembership)
            .where(GroupMembership.user_id == user.id)
            .order_by(Group.updated_at.desc())
        )
    )


@groups.get("/{group_id}", response_model=GroupRead)
def get_group(group_id: str, user: CurrentUser, db: DbSession) -> Group:
    group_membership(db, group_id, user)
    group = db.get(Group, group_id)
    if group is None:
        raise not_found("Group")
    return group


@groups.patch("/{group_id}", response_model=GroupRead)
def update_group(
    group_id: str,
    body: GroupUpdate,
    user: CurrentUser,
    db: DbSession,
) -> Group:
    group = db.get(Group, group_id)
    if group is None or group.owner_id != user.id:
        raise not_found("Group")
    if body.name is not None:
        group.name = body.name
    if "description" in body.model_fields_set:
        group.description = body.description
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="You already own a group with this name"
        ) from exc
    db.refresh(group)
    return group


@groups.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(group_id: str, user: CurrentUser, db: DbSession) -> None:
    group = db.get(Group, group_id)
    if group is None or group.owner_id != user.id:
        raise not_found("Group")
    db.delete(group)
    db.commit()


@groups.get("/{group_id}/members", response_model=list[GroupMemberRead])
def list_group_members(
    group_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[GroupMembership]:
    group_membership(db, group_id, user)
    return list(
        db.scalars(
            select(GroupMembership)
            .where(GroupMembership.group_id == group_id)
            .order_by(GroupMembership.created_at)
        )
    )


@groups.delete(
    "/{group_id}/members/{member_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_group_member(
    group_id: str,
    member_user_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    caller = group_membership(db, group_id, user)
    target = db.scalar(
        select(GroupMembership).where(
            GroupMembership.group_id == group_id,
            GroupMembership.user_id == member_user_id,
        )
    )
    if target is None:
        raise not_found("Group member")
    if caller.role != "owner" and target.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the group owner can remove others",
        )
    if target.role == "owner":
        raise HTTPException(
            status_code=409,
            detail="The group owner cannot leave; delete the group instead",
        )
    db.delete(target)
    db.commit()


@groups.post(
    "/{group_id}/invitations",
    response_model=GroupInvitationCreated,
    status_code=status.HTTP_201_CREATED,
)
def invite_to_group(
    group_id: str,
    body: GroupInvitationCreate,
    user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    group_membership(db, group_id, user)
    email = str(body.email).lower()
    existing_user = db.scalar(select(User).where(User.email == email))
    if existing_user is not None:
        existing_member = db.scalar(
            select(GroupMembership.id).where(
                GroupMembership.group_id == group_id,
                GroupMembership.user_id == existing_user.id,
            )
        )
        if existing_member is not None:
            raise HTTPException(status_code=409, detail="User is already a member")
    pending = db.scalar(
        select(GroupInvitation).where(
            GroupInvitation.group_id == group_id,
            GroupInvitation.email == email,
            GroupInvitation.status == "pending",
        )
    )
    if pending is not None:
        raise HTTPException(status_code=409, detail="An invitation is already pending")
    accept_token = secrets.token_urlsafe(32)
    invitation = GroupInvitation(
        group_id=group_id,
        email=email,
        invited_by_id=user.id,
        token_hash=hashlib.sha256(accept_token.encode()).hexdigest(),
        status="pending",
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(invitation)
    db.commit()
    db.refresh(invitation)
    return {
        **GroupInvitationRead.model_validate(invitation).model_dump(),
        "accept_token": accept_token,
    }


@groups.get(
    "/{group_id}/invitations",
    response_model=list[GroupInvitationRead],
)
def list_group_invitations(
    group_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[GroupInvitation]:
    group_membership(db, group_id, user)
    return list(
        db.scalars(
            select(GroupInvitation)
            .where(GroupInvitation.group_id == group_id)
            .order_by(GroupInvitation.created_at.desc())
        )
    )


@groups.delete(
    "/{group_id}/invitations/{invitation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_group_invitation(
    group_id: str,
    invitation_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    group_membership(db, group_id, user)
    invitation = db.scalar(
        select(GroupInvitation).where(
            GroupInvitation.id == invitation_id,
            GroupInvitation.group_id == group_id,
            GroupInvitation.status == "pending",
        )
    )
    if invitation is None:
        raise not_found("Invitation")
    invitation.status = "revoked"
    db.commit()


@group_invitations.post("/accept", response_model=GroupRead)
def accept_group_invitation(
    body: GroupInvitationAccept,
    user: CurrentUser,
    db: DbSession,
) -> Group:
    token_hash = hashlib.sha256(body.token.encode()).hexdigest()
    invitation = db.scalar(
        select(GroupInvitation).where(
            GroupInvitation.token_hash == token_hash,
            GroupInvitation.status == "pending",
        )
    )
    if invitation is None:
        raise HTTPException(status_code=404, detail="Invitation not found")
    expires_at = invitation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        invitation.status = "expired"
        db.commit()
        raise HTTPException(status_code=410, detail="Invitation has expired")
    if invitation.email != user.email.lower():
        raise HTTPException(
            status_code=403,
            detail="Invitation belongs to another email",
        )
    db.add(
        GroupMembership(
            group_id=invitation.group_id,
            user_id=user.id,
            role="member",
        )
    )
    invitation.status = "accepted"
    invitation.accepted_by_id = user.id
    invitation.accepted_at = datetime.now(UTC)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="User is already a member") from exc
    group = db.get(Group, invitation.group_id)
    if group is None:
        raise not_found("Group")
    return group


@groups.put(
    "/{group_id}/pipelines/{pipeline_id}",
    response_model=PipelineGroupRead,
    status_code=status.HTTP_201_CREATED,
)
def add_pipeline_to_group(
    group_id: str,
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
) -> PipelineGroup:
    group_membership(db, group_id, user)
    pipeline = owned_pipeline(db, pipeline_id, user)
    link = PipelineGroup(
        group_id=group_id,
        pipeline_id=pipeline.id,
        added_by_id=user.id,
    )
    db.add(link)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="Pipeline is already in this group"
        ) from exc
    db.refresh(link)
    return link


@groups.get("/{group_id}/pipelines", response_model=list[PipelineRead])
def list_group_pipelines(
    group_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[Pipeline]:
    group_membership(db, group_id, user)
    return list(
        db.scalars(
            select(Pipeline)
            .join(PipelineGroup)
            .where(PipelineGroup.group_id == group_id)
            .order_by(Pipeline.updated_at.desc())
        )
    )


@groups.delete(
    "/{group_id}/pipelines/{pipeline_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_pipeline_from_group(
    group_id: str,
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    group_membership(db, group_id, user)
    pipeline = owned_pipeline(db, pipeline_id, user)
    link = db.scalar(
        select(PipelineGroup).where(
            PipelineGroup.group_id == group_id,
            PipelineGroup.pipeline_id == pipeline.id,
        )
    )
    if link is None:
        raise not_found("Shared pipeline")
    db.delete(link)
    db.commit()


@tokens.post("", response_model=ApiTokenRead, status_code=status.HTTP_201_CREATED)
def create_api_token(
    body: ApiTokenCreate,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> ApiToken:
    cipher = TokenCipher(settings.token_encryption_key)
    token = ApiToken(
        owner_id=user.id,
        name=body.name,
        encrypted_value=cipher.encrypt(body.value),
        last_four=body.value[-4:],
        allow_read=body.allow_read,
        allow_write=body.allow_write,
    )
    db.add(token)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A token with this name already exists"
        ) from exc
    db.refresh(token)
    return token


@tokens.get("", response_model=list[ApiTokenRead])
def list_api_tokens(user: CurrentUser, db: DbSession) -> list[ApiToken]:
    return list(
        db.scalars(
            select(ApiToken)
            .where(ApiToken.owner_id == user.id)
            .order_by(ApiToken.created_at.desc())
        )
    )


@tokens.get("/{token_id}", response_model=ApiTokenRead)
def get_api_token(token_id: str, user: CurrentUser, db: DbSession) -> ApiToken:
    return owned_token(db, token_id, user)


@tokens.patch("/{token_id}", response_model=ApiTokenRead)
def update_api_token(
    token_id: str,
    body: ApiTokenUpdate,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> ApiToken:
    token = owned_token(db, token_id, user)
    allow_read = body.allow_read if body.allow_read is not None else token.allow_read
    allow_write = (
        body.allow_write if body.allow_write is not None else token.allow_write
    )
    if not allow_read and not allow_write:
        raise HTTPException(
            status_code=422,
            detail="At least one of allow_read or allow_write is required",
        )
    if body.name is not None:
        token.name = body.name
    if body.value is not None:
        token.encrypted_value = TokenCipher(settings.token_encryption_key).encrypt(
            body.value
        )
        token.last_four = body.value[-4:]
    token.allow_read = allow_read
    token.allow_write = allow_write
    if body.is_active is not None:
        token.is_active = body.is_active
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409, detail="A token with this name already exists"
        ) from exc
    db.refresh(token)
    return token


@tokens.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_api_token(token_id: str, user: CurrentUser, db: DbSession) -> None:
    db.delete(owned_token(db, token_id, user))
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
        .outerjoin(PipelineGroup, PipelineGroup.pipeline_id == Pipeline.id)
        .outerjoin(
            GroupMembership,
            and_(
                GroupMembership.group_id == PipelineGroup.group_id,
                GroupMembership.user_id == user.id,
            ),
        )
        .where(
            or_(
                Pipeline.owner_id == user.id,
                GroupMembership.user_id == user.id,
            )
        )
        .distinct()
        .order_by(Pipeline.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@pipelines.get("/{pipeline_id}", response_model=PipelineRead)
def get_pipeline(pipeline_id: str, user: CurrentUser, db: DbSession) -> Pipeline:
    return accessible_pipeline(db, pipeline_id, user)


@pipelines.patch("/{pipeline_id}", response_model=PipelineRead)
def update_pipeline(
    pipeline_id: str,
    body: PipelineUpdate,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> Pipeline:
    pipeline = accessible_pipeline(db, pipeline_id, user)
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
    pipeline = accessible_pipeline(db, pipeline_id, user)
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


@pipelines.post(
    "/{pipeline_id}/token-grants",
    response_model=PipelineTokenGrantRead,
    status_code=status.HTTP_201_CREATED,
)
def grant_pipeline_token(
    pipeline_id: str,
    body: PipelineTokenGrantCreate,
    user: CurrentUser,
    db: DbSession,
) -> PipelineTokenGrant:
    pipeline = accessible_pipeline(db, pipeline_id, user)
    token = owned_token(db, body.token_id, user)
    if not token.is_active:
        raise HTTPException(status_code=422, detail="Token is inactive")
    if body.operation == "read" and not token.allow_read:
        raise HTTPException(status_code=422, detail="Token does not allow reads")
    if body.operation == "write" and not token.allow_write:
        raise HTTPException(status_code=422, detail="Token does not allow writes")
    assets = {
        node.get("asset")
        for node in pipeline.document.get("nodes", [])
        if isinstance(node, dict)
    }
    if body.binding not in assets:
        raise HTTPException(
            status_code=422,
            detail="Binding must match an asset in the pipeline document",
        )
    grant = PipelineTokenGrant(
        pipeline_id=pipeline.id,
        token_id=token.id,
        binding=body.binding,
        provider=body.provider,
        location=body.location,
        operation=body.operation,
    )
    db.add(grant)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This pipeline binding already has a token grant",
        ) from exc
    db.refresh(grant)
    return grant


@pipelines.get(
    "/{pipeline_id}/token-grants",
    response_model=list[PipelineTokenGrantRead],
)
def list_pipeline_token_grants(
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
) -> list[PipelineTokenGrant]:
    pipeline = accessible_pipeline(db, pipeline_id, user)
    return list(
        db.scalars(
            select(PipelineTokenGrant).where(
                PipelineTokenGrant.pipeline_id == pipeline.id
            )
        )
    )


@pipelines.delete(
    "/{pipeline_id}/token-grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def revoke_pipeline_token(
    pipeline_id: str,
    grant_id: str,
    user: CurrentUser,
    db: DbSession,
) -> None:
    pipeline = accessible_pipeline(db, pipeline_id, user)
    grant = db.scalar(
        select(PipelineTokenGrant).where(
            PipelineTokenGrant.id == grant_id,
            PipelineTokenGrant.pipeline_id == pipeline.id,
        )
    )
    if grant is None:
        raise not_found("Token grant")
    token = db.get(ApiToken, grant.token_id)
    if pipeline.owner_id != user.id and (
        token is None or token.owner_id != user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="Only the pipeline or token owner can revoke this grant",
        )
    db.delete(grant)
    db.commit()


@pipelines.post("/{pipeline_id}/validate", response_model=ValidationResult)
def validate_pipeline(
    pipeline_id: str,
    user: CurrentUser,
    db: DbSession,
    settings: AppSettings,
) -> dict[str, Any]:
    pipeline = accessible_pipeline(db, pipeline_id, user)
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
    pipeline = accessible_pipeline(db, pipeline_id, user)
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
    pipeline = accessible_pipeline(db, pipeline_id, user)
    return request.app.state.runner.submit(
        pipeline,
        run_owner_id=user.id,
        session=db,
    )


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
    pipeline = accessible_pipeline(db, pipeline_id, user)
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
        TokenCipher(resolved_settings.token_encryption_key)
        if resolved_settings.auto_migrate:
            config_path = Path(__file__).resolve().parents[2] / "alembic.ini"
            alembic = Config(str(config_path))
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
    app.include_router(tokens)
    app.include_router(groups)
    app.include_router(group_invitations)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
