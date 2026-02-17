"""Firebase Authentication adapter.

Verifies Firebase ID tokens and manages user records.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import firebase_admin
from firebase_admin import auth, credentials

from backend.src.core.entities.user import User

logger = logging.getLogger(__name__)


class FirebaseAuthAdapter:
    """Verifies Firebase ID tokens and converts them to User entities."""

    def __init__(self, credentials_path: str, project_id: str = "") -> None:
        if not firebase_admin._apps:
            cred = credentials.Certificate(credentials_path)
            options = {"projectId": project_id} if project_id else {}
            firebase_admin.initialize_app(cred, options)
            logger.info("Firebase Admin SDK initialized (project=%s)", project_id)

    async def verify_token(self, id_token: str) -> Optional[User]:
        """Verify a Firebase ID token and return a User entity.

        Returns None if the token is invalid or expired.
        """
        try:
            logger.info("Verifying token (first 20 chars): %s...", id_token[:20] if len(id_token) > 20 else id_token)
            decoded = auth.verify_id_token(id_token)
            logger.info("Token decoded OK: uid=%s, email=%s", decoded.get("uid"), decoded.get("email"))
            return User(
                id=decoded["uid"],
                firebase_uid=decoded["uid"],
                email=decoded.get("email", ""),
                display_name=decoded.get("name", ""),
                photo_url=decoded.get("picture", ""),
                provider=decoded.get("firebase", {}).get("sign_in_provider", ""),
                is_anonymous=decoded.get("firebase", {}).get("sign_in_provider") == "anonymous",
                last_login_at=datetime.utcnow(),
            )
        except auth.ExpiredIdTokenError as e:
            logger.warning("Expired Firebase token: %s", e)
            return None
        except auth.InvalidIdTokenError as e:
            logger.warning("Invalid Firebase token: %s", e)
            return None
        except Exception as e:
            logger.error("Firebase token verification failed: %s (type=%s)", e, type(e).__name__)
            return None

    async def get_user_by_uid(self, uid: str) -> Optional[User]:
        """Fetch a Firebase user record by UID."""
        try:
            record = auth.get_user(uid)
            return User(
                id=record.uid,
                firebase_uid=record.uid,
                email=record.email or "",
                display_name=record.display_name or "",
                photo_url=record.photo_url or "",
            )
        except auth.UserNotFoundError:
            return None
        except Exception as e:
            logger.error("Failed to get Firebase user %s: %s", uid, e)
            return None
