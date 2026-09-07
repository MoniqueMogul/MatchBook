from __future__ import annotations

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.auth import supabase

# ============================================================
# AUTHENTICATION
# ============================================================

bearer_scheme = HTTPBearer(
    auto_error=False,
)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    )
) -> UUID:

    # --------------------------------------------------------
    # 1. Make sure an Authorization header exists.
    # --------------------------------------------------------

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # 2. Make sure the authentication scheme is Bearer.
    # --------------------------------------------------------

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = credentials.credentials

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # --------------------------------------------------------
    # 3. Ask Supabase to validate the access token.
    # --------------------------------------------------------

    try:
        response = supabase.auth.get_user(access_token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = response.user

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return UUID(user.id)