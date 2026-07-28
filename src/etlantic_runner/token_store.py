from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken
from etlantic.exceptions import PipelineExecutionError
from etlantic.secrets import (
    ProviderContext,
    SecretProviderCapabilities,
    SecretProviderDescriptor,
    SecretRef,
    SecretResolutionContext,
    SecretValue,
)

from etlantic_runner.config import Settings
from etlantic_runner.database import SessionLocal
from etlantic_runner.models import ApiToken


class TokenCipher:
    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError(
                "ETLANTIC_TOKEN_ENCRYPTION_KEY is required; generate a Fernet key"
            )
        try:
            self._fernet = Fernet(key.encode())
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "ETLANTIC_TOKEN_ENCRYPTION_KEY must be a valid Fernet key"
            ) from exc

    def encrypt(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode())

    def decrypt(self, value: bytes) -> str:
        try:
            return self._fernet.decrypt(value).decode()
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise ValueError("Stored token could not be decrypted") from exc


class UserTokenProvider:
    """Resolve encrypted tokens for one run owner without exposing their values."""

    def __init__(self, allowed_token_ids: set[str], settings: Settings) -> None:
        self.allowed_token_ids = frozenset(allowed_token_ids)
        self.cipher = TokenCipher(settings.token_encryption_key)
        self.descriptor = SecretProviderDescriptor(
            name="user-tokens",
            engine="database",
            capabilities=SecretProviderCapabilities(
                versions=False,
                in_memory_cache=True,
                async_native=True,
                revocation=True,
            ),
        )

    async def resolve(
        self,
        reference: SecretRef,
        context: SecretResolutionContext,
    ) -> SecretValue:
        purpose = reference.purpose or context.purpose
        if reference.provider != "user-tokens" or reference.key != "value":
            self._deny(context, "Invalid user token reference")
        if purpose not in {"read", "write"}:
            self._deny(context, "Token purpose must be read or write")
        with SessionLocal() as session:
            token = session.get(ApiToken, reference.name)
            if (
                token is None
                or token.id not in self.allowed_token_ids
                or not token.is_active
            ):
                self._deny(context, "Token is unavailable")
            if purpose == "read" and not token.allow_read:
                self._deny(context, "Token is not permitted for reads")
            if purpose == "write" and not token.allow_write:
                self._deny(context, "Token is not permitted for writes")
            try:
                value = self.cipher.decrypt(token.encrypted_value)
            except ValueError:
                self._deny(context, "Token is unavailable")
            token.last_used_at = datetime.now(UTC)
            session.commit()
        return SecretValue(
            _value=value,
            provider=reference.provider,
            name=reference.name,
            key=reference.key,
            version=reference.version,
        )

    async def lifespan(self, context: ProviderContext) -> AsyncIterator[None]:
        yield

    @staticmethod
    def _deny(context: SecretResolutionContext, message: str) -> None:
        raise PipelineExecutionError(
            message,
            run_id=context.run_id,
            code="PMEXEC403",
        )
