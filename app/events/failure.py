from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OutboxFailureCode(str, Enum):
    TIMEOUT = "TIMEOUT"
    CONNECTION_FAILURE = "CONNECTION_FAILURE"
    DATABASE_FAILURE = "DATABASE_FAILURE"
    INVALID_EVENT = "INVALID_EVENT"
    PUBLISH_FAILURE = "PUBLISH_FAILURE"


SAFE_EXCEPTION_TYPES = frozenset({
    "TimeoutError",
    "ConnectionError",
    "OperationalError",
    "SQLAlchemyError",
    "OutboxNotFoundError",
    "ValueError",
    "KeyError",
    "TypeError",
    "OSError",
})


@dataclass(frozen=True)
class OutboxFailure:
    code: OutboxFailureCode
    exception_type: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, OutboxFailureCode):
            raise ValueError(
                "Outbox failure code must be a defined enum value"
            )

        if self.exception_type not in (
            SAFE_EXCEPTION_TYPES | {"OtherException"}
        ):
            raise ValueError(
                "Outbox exception type must be an approved name"
            )

    @classmethod
    def from_exception(
        cls,
        exc: Exception,
    ) -> "OutboxFailure":
        from kombu.exceptions import (
            OperationalError as BrokerOperationalError,
        )
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(exc, TimeoutError):
            code = OutboxFailureCode.TIMEOUT

        elif isinstance(exc, BrokerOperationalError):
            code = OutboxFailureCode.CONNECTION_FAILURE

        elif isinstance(exc, SQLAlchemyError):
            code = OutboxFailureCode.DATABASE_FAILURE

        elif isinstance(exc, (ConnectionError, OSError)):
            code = OutboxFailureCode.CONNECTION_FAILURE

        elif isinstance(exc, (ValueError, KeyError, TypeError)):
            code = OutboxFailureCode.INVALID_EVENT

        else:
            code = OutboxFailureCode.PUBLISH_FAILURE

        exception_type = type(exc).__name__

        if exception_type not in SAFE_EXCEPTION_TYPES:
            exception_type = "OtherException"

        return cls(
            code=code,
            exception_type=exception_type,
        )

    def to_storage_value(self) -> str:
        return f"{self.code.value}:{self.exception_type}"