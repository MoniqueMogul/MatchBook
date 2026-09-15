from __future__ import annotations

import contextvars
import json
import logging
import os
import re
import sys
import time

from datetime import datetime, timezone
from uuid import UUID, uuid4


request_id_var = contextvars.ContextVar(
    "request_id",
    default=None,
)

ALLOWED_LOG_FIELDS = frozenset({
    "event",
    "method",
    "route",
    "status_code",
    "duration_ms",
    "task_name",
    "task_id",
    "retries",
    "correlation_id",
    "event_id",
    "document_id",
    "business_id",
    "attempt_count",
    "error_type",
    "state",
    "count",
})

SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")


def safe_id(value: object) -> str | None:
    if (
        isinstance(value, str)
        and SAFE_ID_PATTERN.fullmatch(value)
    ):
        return value

    return None


def correlation_id(value: object) -> str:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return str(uuid4())


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        is_matchbook_log = record.name.startswith(
            "matchbook."
        )

        payload = {
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": (
                record.msg
                if is_matchbook_log
                and isinstance(record.msg, str)
                else "third_party_log"
            ),
            "environment": os.getenv(
                "APP_ENV",
                "local",
            ),
            "request_id": request_id_var.get(),
        }

        # Never serialize exception messages, log arguments,
        # unknown extra fields, headers, or request bodies.
        if is_matchbook_log:
            for field in ALLOWED_LOG_FIELDS:
                value = getattr(record, field, None)

                if isinstance(
                    value,
                    (str, int, float, bool),
                ):
                    payload[field] = value

        return json.dumps(
            payload,
            separators=(",", ":"),
        )


def configure_logging() -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers[:] = [handler]

    level = os.getenv("LOG_LEVEL", "INFO").upper()

    if level not in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }:
        level = "INFO"

    root_logger.setLevel(level)


class RequestLogMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(
        self,
        scope,
        receive,
        send,
    ):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming_id = next(
            (
                value
                for name, value in scope.get(
                    "headers",
                    [],
                )
                if name.lower() == b"x-request-id"
            ),
            None,
        )

        request_id = correlation_id(
            incoming_id.decode(
                "ascii",
                errors="ignore",
            )
            if incoming_id
            else None
        )

        token = request_id_var.set(request_id)
        started_at = time.monotonic()
        status_code = 500
        error_type = None

        async def send_with_request_id(message):
            nonlocal status_code

            if message["type"] == "http.response.start":
                status_code = message["status"]

                headers = [
                    (name, value)
                    for name, value in message.get(
                        "headers",
                        [],
                    )
                    if name.lower() != b"x-request-id"
                ]

                headers.append(
                    (
                        b"x-request-id",
                        request_id.encode("ascii"),
                    )
                )

                message["headers"] = headers

            await send(message)

        try:
            await self.app(
                scope,
                receive,
                send_with_request_id,
            )

        except Exception as exc:
            # Record the class, never str(exc).
            error_type = type(exc).__name__
            raise

        finally:
            route = scope.get("route")

            # For example: /buyers/{buyer_id}.
            # Never log /buyers/<actual-id> or query strings.
            route_template = getattr(
                route,
                "path",
                "unmatched",
            )

            method = scope.get(
                "method",
                "OTHER",
            )

            if method not in {
                "GET",
                "POST",
                "PUT",
                "PATCH",
                "DELETE",
                "HEAD",
                "OPTIONS",
            }:
                method = "OTHER"

            log_fields = {
                "event": "request_completed",
                "method": method,
                "route": route_template,
                "status_code": status_code,
                "duration_ms": round(
                    (
                        time.monotonic()
                        - started_at
                    ) * 1000,
                    2,
                ),
            }

            if error_type:
                log_fields["error_type"] = (
                    error_type
                )

            logging.getLogger(
                "matchbook.http"
            ).log(
                logging.ERROR
                if status_code >= 500
                else logging.INFO,
                "request_completed",
                extra=log_fields,
            )

            request_id_var.reset(token)