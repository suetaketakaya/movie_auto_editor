"""User entity for future authentication support."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class User:
    """Simple user entity."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    username: str = ""
    email: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    preferences: dict = field(default_factory=dict)
