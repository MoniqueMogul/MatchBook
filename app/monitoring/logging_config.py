from __future__ import annotations

import logging
import os


DEFAULT_LOG_LEVEL = "INFO"


def configure_logging() -> None:
    """
    Configure application-wide logging.

    LOG_LEVEL may be overridden through the environment.
    """

    log_level_name = (
        os.getenv(
            "LOG_LEVEL",
            DEFAULT_LOG_LEVEL,
        )
        .strip()
        .upper()
    )

    log_level = getattr(
        logging,
        log_level_name,
        logging.INFO,
    )

    logging.basicConfig(
        level=log_level,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )