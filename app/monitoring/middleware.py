from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import (
    BaseHTTPMiddleware,
)
from starlette.responses import Response


logger = logging.getLogger(
    "matchbook.http"
)


class RequestLoggingMiddleware(
    BaseHTTPMiddleware
):
    """
    Log HTTP request lifecycle information.

    Each request receives a request ID which is also
    returned through the X-Request-ID response header.
    """

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        request_id = (
            request.headers.get(
                "X-Request-ID"
            )
            or str(
                uuid4()
            )
        )

        start_time = (
            time.perf_counter()
        )

        try:
            response = await call_next(
                request
            )

        except Exception:
            duration_ms = (
                (
                    time.perf_counter()
                    - start_time
                )
                * 1000
            )

            logger.exception(
                (
                    "request_failed "
                    "request_id=%s "
                    "method=%s "
                    "path=%s "
                    "duration_ms=%.2f"
                ),
                request_id,
                request.method,
                request.url.path,
                duration_ms,
            )

            raise

        duration_ms = (
            (
                time.perf_counter()
                - start_time
            )
            * 1000
        )

        response.headers[
            "X-Request-ID"
        ] = request_id

        logger.info(
            (
                "request_complete "
                "request_id=%s "
                "method=%s "
                "path=%s "
                "status_code=%s "
                "duration_ms=%.2f"
            ),
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )

        return response