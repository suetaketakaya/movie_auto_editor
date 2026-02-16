"""FastAPI dependencies for authentication and authorization."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, Request

from backend.src.core.entities.user import User


async def get_current_user(request: Request) -> User:
    """Extract and verify the authenticated user from the request.

    The user is attached by the Bearer token middleware in fastapi_app.py.
    If Firebase auth is disabled, the noop adapter always provides a dev user.
    """
    user: Optional[User] = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


async def get_optional_user(request: Request) -> Optional[User]:
    """Return the authenticated user or None (for public endpoints)."""
    return getattr(request.state, "user", None)
