"""
Subscription model for managing user billing plans.
"""

import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import relationship

from ..database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False, unique=True)

    # Plan details
    plan = Column(String(50), default="free")  # free | starter | pro | enterprise
    status = Column(String(50), default="active")  # active | canceled | past_due | trialing | inactive

    # Stripe
    stripe_subscription_id = Column(String(100), nullable=True, unique=True)
    stripe_price_id = Column(String(100), nullable=True)

    # Billing period
    current_period_start = Column(DateTime, nullable=True)
    current_period_end = Column(DateTime, nullable=True)
    cancel_at_period_end = Column(Boolean, default=False)

    # Trial
    trial_end = Column(DateTime, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    user = relationship("User", back_populates="subscription")

    @property
    def is_active(self) -> bool:
        return self.status in ("active", "trialing")

    @property
    def is_in_trial(self) -> bool:
        if self.trial_end and self.status == "trialing":
            return datetime.utcnow() < self.trial_end
        return False

    def __repr__(self):
        return f"<Subscription user={self.user_id} plan={self.plan} status={self.status}>"
