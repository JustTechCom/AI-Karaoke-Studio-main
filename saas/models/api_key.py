"""
API Key model for programmatic access.
"""

import uuid
import secrets
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from ..database import Base


class APIKey(Base):
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)

    # Key details
    name = Column(String(200), nullable=False)  # User-friendly name
    key_prefix = Column(String(10), nullable=False)  # First 8 chars for display
    hashed_key = Column(String(255), nullable=False)  # Hashed for security

    # Permissions
    is_active = Column(Boolean, default=True)
    read_only = Column(Boolean, default=False)

    # Usage tracking
    last_used_at = Column(DateTime, nullable=True)
    request_count = Column(String(20), default="0")

    # Expiry
    expires_at = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="api_keys")

    @staticmethod
    def generate_key() -> tuple[str, str]:
        """Generate a new API key. Returns (raw_key, prefix)."""
        raw_key = f"ksk_{secrets.token_urlsafe(32)}"
        prefix = raw_key[:8]
        return raw_key, prefix

    def __repr__(self):
        return f"<APIKey {self.key_prefix}... user={self.user_id}>"
