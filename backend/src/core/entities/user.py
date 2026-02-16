"""User entity for Firebase authentication."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class User:
    """Authenticated user entity.

    ``firebase_uid`` is the authoritative identifier from Firebase Auth.
    ``id`` is an internal UUID used for DB relations.
    """

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    firebase_uid: str = ""
    email: str = ""
    display_name: str = ""
    photo_url: str = ""
    provider: str = ""  # e.g. "google.com", "password"
    is_anonymous: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_login_at: Optional[datetime] = None
    preferences: dict = field(default_factory=dict)

    @property
    def username(self) -> str:
        return self.display_name or self.email.split("@")[0] if self.email else ""
