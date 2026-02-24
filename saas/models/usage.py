"""
Usage tracking model for billing and quota management.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship

from ..database import Base


class UsageRecord(Base):
    __tablename__ = "usage_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    job_id = Column(String(36), ForeignKey("jobs.id"), nullable=True)

    # Billing period (YYYY-MM format)
    billing_period = Column(String(7), nullable=False)  # e.g., "2024-01"

    # Usage metrics
    songs_processed = Column(Integer, default=0)
    processing_seconds = Column(Integer, default=0)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="usage_records")

    def __repr__(self):
        return f"<UsageRecord user={self.user_id} period={self.billing_period}>"


def get_current_billing_period() -> str:
    """Returns current billing period in YYYY-MM format."""
    now = datetime.utcnow()
    return f"{now.year}-{now.month:02d}"
