from __future__ import annotations

from typing import Any

from etlantic.authoring import pipeline_to_dict
from etlantic.service import AuthoringService, PolicyContext

from etlantic_runner.config import Settings


def service_for(
    document: dict[str, Any],
    definition_id: str,
    settings: Settings,
) -> AuthoringService:
    service = AuthoringService(
        policy=PolicyContext(
            tenant="application",
            environment="development",
            profile=settings.profile,
        )
    )
    service.put_definition(definition_id, document)
    return service


def verify_document(
    document: dict[str, Any],
    definition_id: str,
    settings: Settings,
) -> tuple[dict[str, Any], str]:
    result = service_for(document, definition_id, settings).get_definition(
        definition_id
    )
    return result["definition"], result["fingerprint"]


def apply_document_edit(
    document: dict[str, Any],
    definition_id: str,
    command: dict[str, Any],
    expected_token: str | None,
    settings: Settings,
) -> tuple[dict[str, Any], str]:
    service = service_for(document, definition_id, settings)
    result = service.apply_edit(
        definition_id,
        command,
        expected_token=expected_token,
    )
    return result["definition"], result["fingerprint"]

