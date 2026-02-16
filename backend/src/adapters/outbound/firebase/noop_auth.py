"""No-op authentication adapter for development mode.

Always returns a fixed anonymous user so the app runs without Firebase.
"""
from __future__ import annotations

import logging
from typing import Optional

from backend.src.core.entities.user import User

logger = logging.getLogger(__name__)

_ANON_USER = User(
    id="dev-user-000",
    firebase_uid="dev-user-000",
    email="dev@localhost",
    display_name="Developer",
    is_anonymous=True,
)


class NoopAuthAdapter:
    """Development stub — accepts any token and returns a fixed user."""

    async def verify_token(self, id_token: str) -> Optional[User]:
        logger.debug("NoopAuth: accepting token (dev mode)")
        return _ANON_USER

    async def get_user_by_uid(self, uid: str) -> Optional[User]:
        return _ANON_USER
