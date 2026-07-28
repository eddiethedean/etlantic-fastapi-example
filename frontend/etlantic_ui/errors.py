from __future__ import annotations

from typing import Any


class ApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: Any = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail


class AuthenticationError(ApiError):
    pass


class ForbiddenError(ApiError):
    pass


class NotFoundError(ApiError):
    pass


class ConflictError(ApiError):
    pass


class GoneError(ApiError):
    pass


class ValidationError(ApiError):
    pass


class ServerError(ApiError):
    pass


def format_detail(detail: Any) -> str:
    if detail is None:
        return "Request failed"
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts: list[str] = []
        for item in detail:
            if isinstance(item, dict):
                loc = ".".join(
                    str(part) for part in item.get("loc", []) if part != "body"
                )
                msg = item.get("msg", "Invalid value")
                parts.append(f"{loc}: {msg}" if loc else str(msg))
            else:
                parts.append(str(item))
        return "; ".join(parts) if parts else "Validation failed"
    if isinstance(detail, dict):
        return str(detail.get("msg") or detail.get("detail") or detail)
    return str(detail)


def raise_for_status(status_code: int, detail: Any) -> None:
    message = format_detail(detail)
    if status_code == 401:
        raise AuthenticationError(message, status_code=status_code, detail=detail)
    if status_code == 403:
        raise ForbiddenError(message, status_code=status_code, detail=detail)
    if status_code == 404:
        raise NotFoundError(message, status_code=status_code, detail=detail)
    if status_code == 409:
        raise ConflictError(message, status_code=status_code, detail=detail)
    if status_code == 410:
        raise GoneError(message, status_code=status_code, detail=detail)
    if status_code in {400, 422}:
        raise ValidationError(message, status_code=status_code, detail=detail)
    if status_code >= 500:
        raise ServerError(message, status_code=status_code, detail=detail)
    raise ApiError(message, status_code=status_code, detail=detail)


def render_error(exc: Exception) -> None:
    import streamlit as st

    if isinstance(exc, AuthenticationError):
        st.error("Your session expired. Please sign in again.")
        return
    if isinstance(exc, ForbiddenError):
        st.error("You do not have permission for that action.")
        return
    if isinstance(exc, NotFoundError):
        st.error("Resource unavailable. It may have been deleted or access removed.")
        return
    if isinstance(exc, ConflictError):
        st.warning(f"Conflict: {exc.message}")
        return
    if isinstance(exc, GoneError):
        st.error(exc.message or "Invitation has expired.")
        return
    if isinstance(exc, ValidationError):
        st.error(f"Validation error: {exc.message}")
        return
    if isinstance(exc, ServerError):
        st.error(f"Server error: {exc.message}")
        return
    if isinstance(exc, ApiError):
        st.error(exc.message)
        return
    st.error("Something went wrong. Please try again.")
