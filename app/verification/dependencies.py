from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.intake.dependencies import get_db_session


def get_db() -> Generator[Session, None, None]:
    yield from get_db_session()


def get_current_user() -> None:
    """
    Placeholder until Supabase Auth wiring lands (owned by the core team).

    Routes using this dependency currently receive None until real auth
    is implemented.
    """
    return None