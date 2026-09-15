from __future__ import annotations

import logging
import time
from uuid import UUID

from celery.signals import (
    before_task_publish,
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
)

from app.core.observability import request_id_var


log = logging.getLogger("matchbook.tasks")

task_start_times: dict[str, float] = {}
task_context_tokens: dict[str, object] = {}


def valid_uuid(value: object) -> str | None:
    try:
        return str(UUID(str(value)))
    except (ValueError, TypeError, AttributeError):
        return None


@before_task_publish.connect
def attach_request_id(
    sender=None,
    headers=None,
    **kwargs,
) -> None:
    """
    Runs where the task is published: usually FastAPI.

    The header travels with the task through RabbitMQ.
    """
    if headers is None:
        return

    request_id = request_id_var.get()

    if request_id:
        headers["matchbook_request_id"] = request_id


@task_prerun.connect
def log_task_start(
    task_id=None,
    task=None,
    **kwargs,
) -> None:
    if not task_id or task is None:
        return

    headers = getattr(
        task.request,
        "headers",
        None,
    ) or {}

    originating_request_id = valid_uuid(
        headers.get("matchbook_request_id")
    )

    # Beat jobs have no originating API request.
    correlation_id = (
        originating_request_id
        or valid_uuid(task_id)
    )

    task_context_tokens[task_id] = (
        request_id_var.set(correlation_id)
    )

    task_start_times[task_id] = (
        time.monotonic()
    )

    log.info(
        "task_started",
        extra={
            "event": "task_started",
            "task_id": task_id,
            "task_name": task.name,
            "retries": task.request.retries,
        },
    )


@task_retry.connect
def log_task_retry(
    request=None,
    reason=None,
    **kwargs,
) -> None:
    if request is None:
        return

    log.warning(
        "task_retry",
        extra={
            "event": "task_retry",
            "task_id": request.id,
            "task_name": request.task,
            "error_type": (
                type(reason).__name__
                if reason is not None
                else "Unknown"
            ),
        },
    )


@task_failure.connect
def log_task_failure(
    task_id=None,
    exception=None,
    sender=None,
    **kwargs,
) -> None:
    log.error(
        "task_failed",
        extra={
            "event": "task_failed",
            "task_id": task_id,
            "task_name": getattr(
                sender,
                "name",
                None,
            ),
            "error_type": (
                type(exception).__name__
                if exception is not None
                else "Unknown"
            ),
        },
    )


@task_postrun.connect
def log_task_end(
    task_id=None,
    task=None,
    state=None,
    **kwargs,
) -> None:
    if not task_id:
        return

    started_at = task_start_times.pop(
        task_id,
        None,
    )

    duration_ms = (
        round(
            (
                time.monotonic()
                - started_at
            ) * 1000,
            2,
        )
        if started_at is not None
        else None
    )

    log.info(
        "task_completed",
        extra={
            "event": "task_completed",
            "task_id": task_id,
            "task_name": getattr(
                task,
                "name",
                None,
            ),
            "state": state,
            "duration_ms": duration_ms,
        },
    )

    token = task_context_tokens.pop(
        task_id,
        None,
    )

    if token is not None:
        request_id_var.reset(token)