from __future__ import annotations

from typing import Any

import httpx

from etlantic_ui.config import UiSettings, get_ui_settings
from etlantic_ui.errors import raise_for_status
from etlantic_ui.models import (
    ApiTokenRead,
    GroupInvitationCreated,
    GroupInvitationRead,
    GroupMemberRead,
    GroupRead,
    PipelineDraftResult,
    PipelineGroupRead,
    PipelineRead,
    PipelineTokenGrantRead,
    PlanResult,
    RunRead,
    ScheduleRead,
    Token,
    UserRead,
    ValidationResult,
)


class EtlanticApiClient:
    """HTTP client for the ETLantic Runner API. One method per backend operation."""

    COVERED_PATHS: frozenset[tuple[str, str]] = frozenset(
        {
            ("GET", "/health"),
            ("POST", "/users"),
            ("POST", "/auth/token"),
            ("GET", "/users/me"),
            ("PATCH", "/users/me"),
            ("DELETE", "/users/me"),
            ("GET", "/users"),
            ("POST", "/pipelines"),
            ("POST", "/pipelines/verify-draft"),
            ("GET", "/pipelines"),
            ("GET", "/pipelines/{pipeline_id}"),
            ("PATCH", "/pipelines/{pipeline_id}"),
            ("POST", "/pipelines/{pipeline_id}/edits"),
            ("POST", "/pipelines/{pipeline_id}/verify-draft"),
            ("DELETE", "/pipelines/{pipeline_id}"),
            ("POST", "/pipelines/{pipeline_id}/validate"),
            ("POST", "/pipelines/{pipeline_id}/plan"),
            ("POST", "/pipelines/{pipeline_id}/runs"),
            ("POST", "/pipelines/{pipeline_id}/schedules"),
            ("POST", "/pipelines/{pipeline_id}/token-grants"),
            ("GET", "/pipelines/{pipeline_id}/token-grants"),
            ("DELETE", "/pipelines/{pipeline_id}/token-grants/{grant_id}"),
            ("GET", "/runs"),
            ("GET", "/runs/{run_id}"),
            ("GET", "/schedules"),
            ("GET", "/schedules/{schedule_id}"),
            ("PATCH", "/schedules/{schedule_id}"),
            ("DELETE", "/schedules/{schedule_id}"),
            ("POST", "/tokens"),
            ("GET", "/tokens"),
            ("GET", "/tokens/{token_id}"),
            ("PATCH", "/tokens/{token_id}"),
            ("DELETE", "/tokens/{token_id}"),
            ("POST", "/groups"),
            ("GET", "/groups"),
            ("GET", "/groups/{group_id}"),
            ("PATCH", "/groups/{group_id}"),
            ("DELETE", "/groups/{group_id}"),
            ("GET", "/groups/{group_id}/members"),
            ("DELETE", "/groups/{group_id}/members/{member_user_id}"),
            ("POST", "/groups/{group_id}/invitations"),
            ("GET", "/groups/{group_id}/invitations"),
            ("DELETE", "/groups/{group_id}/invitations/{invitation_id}"),
            ("POST", "/group-invitations/accept"),
            ("PUT", "/groups/{group_id}/pipelines/{pipeline_id}"),
            ("GET", "/groups/{group_id}/pipelines"),
            ("DELETE", "/groups/{group_id}/pipelines/{pipeline_id}"),
        }
    )

    def __init__(
        self,
        settings: UiSettings | None = None,
        *,
        access_token: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self.settings = settings or get_ui_settings()
        self.access_token = access_token
        self._client = httpx.Client(
            base_url=self.settings.api_url.rstrip("/"),
            timeout=self.settings.request_timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        try:
            self._client.close()
        except AttributeError:
            # httpx ASGITransport is async-only and may lack sync close().
            pass

    def __enter__(self) -> EtlanticApiClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def with_token(self, access_token: str | None) -> EtlanticApiClient:
        self.access_token = access_token
        return self

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: Any | None = None,
        data: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        response = self._client.request(
            method,
            path,
            headers=self._headers(),
            json=json,
            data=data,
            params=params,
        )
        if response.status_code == 204:
            return None
        detail: Any
        try:
            detail = response.json()
        except ValueError:
            detail = response.text
        if response.is_error:
            payload = (
                detail.get("detail", detail) if isinstance(detail, dict) else detail
            )
            raise_for_status(response.status_code, payload)
        return detail

    # --- system ---
    def health(self) -> dict[str, str]:
        return self._request("GET", "/health")

    # --- auth / users ---
    def register_user(
        self, *, email: str, display_name: str, password: str
    ) -> UserRead:
        return UserRead.model_validate(
            self._request(
                "POST",
                "/users",
                json={
                    "email": email,
                    "display_name": display_name,
                    "password": password,
                },
            )
        )

    def login(self, *, email: str, password: str) -> Token:
        return Token.model_validate(
            self._request(
                "POST",
                "/auth/token",
                data={"username": email, "password": password},
            )
        )

    def get_me(self) -> UserRead:
        return UserRead.model_validate(self._request("GET", "/users/me"))

    def update_me(
        self,
        *,
        display_name: str | None = None,
        password: str | None = None,
    ) -> UserRead:
        body: dict[str, Any] = {}
        if display_name is not None:
            body["display_name"] = display_name
        if password is not None:
            body["password"] = password
        return UserRead.model_validate(self._request("PATCH", "/users/me", json=body))

    def deactivate_me(self) -> None:
        self._request("DELETE", "/users/me")

    def list_users(self, *, limit: int = 100, offset: int = 0) -> list[UserRead]:
        rows = self._request("GET", "/users", params={"limit": limit, "offset": offset})
        return [UserRead.model_validate(row) for row in rows]

    # --- pipelines ---
    def create_pipeline(
        self,
        *,
        name: str,
        document: dict[str, Any],
        description: str | None = None,
    ) -> PipelineRead:
        return PipelineRead.model_validate(
            self._request(
                "POST",
                "/pipelines",
                json={
                    "name": name,
                    "description": description,
                    "document": document,
                },
            )
        )

    def verify_draft(
        self, document: dict[str, Any], *, pipeline_id: str | None = None
    ) -> PipelineDraftResult:
        path = (
            f"/pipelines/{pipeline_id}/verify-draft"
            if pipeline_id
            else "/pipelines/verify-draft"
        )
        return PipelineDraftResult.model_validate(
            self._request("POST", path, json={"document": document})
        )

    def list_pipelines(
        self, *, limit: int = 100, offset: int = 0
    ) -> list[PipelineRead]:
        rows = self._request(
            "GET", "/pipelines", params={"limit": limit, "offset": offset}
        )
        return [PipelineRead.model_validate(row) for row in rows]

    def get_pipeline(self, pipeline_id: str) -> PipelineRead:
        return PipelineRead.model_validate(
            self._request("GET", f"/pipelines/{pipeline_id}")
        )

    def update_pipeline(
        self,
        pipeline_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        document: dict[str, Any] | None = None,
        expected_version: int | None = None,
        clear_description: bool = False,
    ) -> PipelineRead:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if clear_description:
            body["description"] = None
        elif description is not None:
            body["description"] = description
        if document is not None:
            body["document"] = document
        if expected_version is not None:
            body["expected_version"] = expected_version
        return PipelineRead.model_validate(
            self._request("PATCH", f"/pipelines/{pipeline_id}", json=body)
        )

    def edit_pipeline(
        self,
        pipeline_id: str,
        *,
        command: dict[str, Any],
        expected_token: str | None = None,
    ) -> PipelineRead:
        return PipelineRead.model_validate(
            self._request(
                "POST",
                f"/pipelines/{pipeline_id}/edits",
                json={"command": command, "expected_token": expected_token},
            )
        )

    def delete_pipeline(self, pipeline_id: str) -> None:
        self._request("DELETE", f"/pipelines/{pipeline_id}")

    def validate_pipeline(self, pipeline_id: str) -> ValidationResult:
        return ValidationResult.model_validate(
            self._request("POST", f"/pipelines/{pipeline_id}/validate")
        )

    def plan_pipeline(self, pipeline_id: str) -> PlanResult:
        return PlanResult.model_validate(
            self._request("POST", f"/pipelines/{pipeline_id}/plan")
        )

    def submit_run(self, pipeline_id: str) -> RunRead:
        return RunRead.model_validate(
            self._request("POST", f"/pipelines/{pipeline_id}/runs")
        )

    # --- runs ---
    def list_runs(
        self,
        *,
        pipeline_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[RunRead]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        rows = self._request("GET", "/runs", params=params)
        return [RunRead.model_validate(row) for row in rows]

    def get_run(self, run_id: str) -> RunRead:
        return RunRead.model_validate(self._request("GET", f"/runs/{run_id}"))

    # --- schedules ---
    def create_schedule(
        self,
        pipeline_id: str,
        *,
        name: str,
        trigger_type: str,
        trigger_args: dict[str, Any],
        enabled: bool = True,
    ) -> ScheduleRead:
        return ScheduleRead.model_validate(
            self._request(
                "POST",
                f"/pipelines/{pipeline_id}/schedules",
                json={
                    "name": name,
                    "trigger_type": trigger_type,
                    "trigger_args": trigger_args,
                    "enabled": enabled,
                },
            )
        )

    def list_schedules(self) -> list[ScheduleRead]:
        rows = self._request("GET", "/schedules")
        return [ScheduleRead.model_validate(row) for row in rows]

    def get_schedule(self, schedule_id: str) -> ScheduleRead:
        return ScheduleRead.model_validate(
            self._request("GET", f"/schedules/{schedule_id}")
        )

    def update_schedule(
        self,
        schedule_id: str,
        *,
        name: str | None = None,
        trigger_type: str | None = None,
        trigger_args: dict[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> ScheduleRead:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if trigger_type is not None:
            body["trigger_type"] = trigger_type
        if trigger_args is not None:
            body["trigger_args"] = trigger_args
        if enabled is not None:
            body["enabled"] = enabled
        return ScheduleRead.model_validate(
            self._request("PATCH", f"/schedules/{schedule_id}", json=body)
        )

    def delete_schedule(self, schedule_id: str) -> None:
        self._request("DELETE", f"/schedules/{schedule_id}")

    # --- tokens ---
    def create_token(
        self,
        *,
        name: str,
        value: str,
        allow_read: bool = True,
        allow_write: bool = False,
    ) -> ApiTokenRead:
        return ApiTokenRead.model_validate(
            self._request(
                "POST",
                "/tokens",
                json={
                    "name": name,
                    "value": value,
                    "allow_read": allow_read,
                    "allow_write": allow_write,
                },
            )
        )

    def list_tokens(self) -> list[ApiTokenRead]:
        rows = self._request("GET", "/tokens")
        return [ApiTokenRead.model_validate(row) for row in rows]

    def get_token(self, token_id: str) -> ApiTokenRead:
        return ApiTokenRead.model_validate(self._request("GET", f"/tokens/{token_id}"))

    def update_token(
        self,
        token_id: str,
        *,
        name: str | None = None,
        value: str | None = None,
        allow_read: bool | None = None,
        allow_write: bool | None = None,
        is_active: bool | None = None,
    ) -> ApiTokenRead:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if value is not None:
            body["value"] = value
        if allow_read is not None:
            body["allow_read"] = allow_read
        if allow_write is not None:
            body["allow_write"] = allow_write
        if is_active is not None:
            body["is_active"] = is_active
        return ApiTokenRead.model_validate(
            self._request("PATCH", f"/tokens/{token_id}", json=body)
        )

    def delete_token(self, token_id: str) -> None:
        self._request("DELETE", f"/tokens/{token_id}")

    def create_token_grant(
        self,
        pipeline_id: str,
        *,
        token_id: str,
        binding: str,
        provider: str,
        operation: str,
        location: str | None = None,
    ) -> PipelineTokenGrantRead:
        return PipelineTokenGrantRead.model_validate(
            self._request(
                "POST",
                f"/pipelines/{pipeline_id}/token-grants",
                json={
                    "token_id": token_id,
                    "binding": binding,
                    "provider": provider,
                    "location": location,
                    "operation": operation,
                },
            )
        )

    def list_token_grants(self, pipeline_id: str) -> list[PipelineTokenGrantRead]:
        rows = self._request("GET", f"/pipelines/{pipeline_id}/token-grants")
        return [PipelineTokenGrantRead.model_validate(row) for row in rows]

    def delete_token_grant(self, pipeline_id: str, grant_id: str) -> None:
        self._request("DELETE", f"/pipelines/{pipeline_id}/token-grants/{grant_id}")

    # --- groups ---
    def create_group(self, *, name: str, description: str | None = None) -> GroupRead:
        return GroupRead.model_validate(
            self._request(
                "POST",
                "/groups",
                json={"name": name, "description": description},
            )
        )

    def list_groups(self) -> list[GroupRead]:
        rows = self._request("GET", "/groups")
        return [GroupRead.model_validate(row) for row in rows]

    def get_group(self, group_id: str) -> GroupRead:
        return GroupRead.model_validate(self._request("GET", f"/groups/{group_id}"))

    def update_group(
        self,
        group_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
    ) -> GroupRead:
        body: dict[str, Any] = {}
        if name is not None:
            body["name"] = name
        if clear_description:
            body["description"] = None
        elif description is not None:
            body["description"] = description
        return GroupRead.model_validate(
            self._request("PATCH", f"/groups/{group_id}", json=body)
        )

    def delete_group(self, group_id: str) -> None:
        self._request("DELETE", f"/groups/{group_id}")

    def list_group_members(self, group_id: str) -> list[GroupMemberRead]:
        rows = self._request("GET", f"/groups/{group_id}/members")
        return [GroupMemberRead.model_validate(row) for row in rows]

    def remove_group_member(self, group_id: str, member_user_id: str) -> None:
        self._request("DELETE", f"/groups/{group_id}/members/{member_user_id}")

    def create_invitation(self, group_id: str, *, email: str) -> GroupInvitationCreated:
        return GroupInvitationCreated.model_validate(
            self._request(
                "POST",
                f"/groups/{group_id}/invitations",
                json={"email": email},
            )
        )

    def list_invitations(self, group_id: str) -> list[GroupInvitationRead]:
        rows = self._request("GET", f"/groups/{group_id}/invitations")
        return [GroupInvitationRead.model_validate(row) for row in rows]

    def revoke_invitation(self, group_id: str, invitation_id: str) -> None:
        self._request("DELETE", f"/groups/{group_id}/invitations/{invitation_id}")

    def accept_invitation(self, token: str) -> GroupRead:
        return GroupRead.model_validate(
            self._request("POST", "/group-invitations/accept", json={"token": token})
        )

    def add_pipeline_to_group(
        self, group_id: str, pipeline_id: str
    ) -> PipelineGroupRead:
        return PipelineGroupRead.model_validate(
            self._request("PUT", f"/groups/{group_id}/pipelines/{pipeline_id}")
        )

    def list_group_pipelines(self, group_id: str) -> list[PipelineRead]:
        rows = self._request("GET", f"/groups/{group_id}/pipelines")
        return [PipelineRead.model_validate(row) for row in rows]

    def remove_pipeline_from_group(self, group_id: str, pipeline_id: str) -> None:
        self._request("DELETE", f"/groups/{group_id}/pipelines/{pipeline_id}")
