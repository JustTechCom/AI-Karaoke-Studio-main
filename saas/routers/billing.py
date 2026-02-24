"""
Billing router: subscription management, Stripe integration, pricing.
"""

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models.user import User
from ..models.subscription import Subscription
from ..models.usage import UsageRecord, get_current_billing_period
from ..auth import get_current_active_user
from ..config import settings, SUBSCRIPTION_PLANS

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/billing", tags=["billing"])


# ─── Stripe helpers ───────────────────────────────────────────────────────────

def get_stripe():
    """Get Stripe module with API key set."""
    try:
        import stripe
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return stripe
    except ImportError:
        raise HTTPException(status_code=501, detail="Stripe entegrasyonu aktif değil")


# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateCheckoutRequest(BaseModel):
    plan: str
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


class CreatePortalRequest(BaseModel):
    return_url: Optional[str] = None


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/plans")
async def get_plans():
    """Get all available subscription plans."""
    return {
        "plans": [
            {
                "id": plan_id,
                **plan_data,
                "stripe_price_id": getattr(settings, f"STRIPE_PRICE_{plan_id.upper()}", ""),
            }
            for plan_id, plan_data in SUBSCRIPTION_PLANS.items()
        ]
    }


@router.get("/subscription")
async def get_subscription(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Get current user's subscription details."""
    plan = current_user.current_plan
    plan_config = SUBSCRIPTION_PLANS.get(plan, SUBSCRIPTION_PLANS["free"])

    # Get current usage
    period = get_current_billing_period()
    usage_count = db.query(func.count(UsageRecord.id)).filter(
        UsageRecord.user_id == current_user.id,
        UsageRecord.billing_period == period,
    ).scalar() or 0

    songs_limit = plan_config["songs_per_month"]
    songs_remaining = max(0, songs_limit - usage_count) if songs_limit != -1 else -1

    subscription_data = {
        "plan": plan,
        "plan_name": plan_config["name"],
        "status": "active",
        "songs_used_this_month": usage_count,
        "songs_limit": songs_limit,
        "songs_remaining": songs_remaining,
        "features": plan_config["features"],
    }

    if current_user.subscription:
        sub = current_user.subscription
        subscription_data.update({
            "status": sub.status,
            "current_period_end": sub.current_period_end,
            "cancel_at_period_end": sub.cancel_at_period_end,
            "is_in_trial": sub.is_in_trial,
        })

    return subscription_data


@router.post("/create-checkout-session")
async def create_checkout_session(
    request: CreateCheckoutRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create a Stripe checkout session for subscription upgrade."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(
            status_code=501,
            detail="Stripe henüz yapılandırılmadı. Lütfen STRIPE_SECRET_KEY ayarlayın.",
        )

    if request.plan not in SUBSCRIPTION_PLANS or request.plan == "free":
        raise HTTPException(status_code=400, detail="Geçersiz plan seçimi")

    price_id = getattr(settings, f"STRIPE_PRICE_{request.plan.upper()}", "")
    if not price_id:
        raise HTTPException(
            status_code=501,
            detail=f"Stripe fiyat ID'si yapılandırılmadı: STRIPE_PRICE_{request.plan.upper()}",
        )

    stripe = get_stripe()

    try:
        # Get or create Stripe customer
        customer_id = current_user.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.full_name or current_user.username,
                metadata={"user_id": current_user.id},
            )
            customer_id = customer.id
            current_user.stripe_customer_id = customer_id
            db.commit()

        success_url = request.success_url or f"{settings.APP_URL}/dashboard?upgraded=true"
        cancel_url = request.cancel_url or f"{settings.APP_URL}/pricing"

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=cancel_url,
            metadata={
                "user_id": current_user.id,
                "plan": request.plan,
            },
        )

        return {"checkout_url": session.url, "session_id": session.id}

    except Exception as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Ödeme oturumu oluşturulamadı: {str(e)}")


@router.post("/create-portal-session")
async def create_portal_session(
    request: CreatePortalRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Create Stripe Customer Portal session for subscription management."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=501, detail="Stripe yapılandırılmadı")

    if not current_user.stripe_customer_id:
        raise HTTPException(status_code=400, detail="Aktif abonelik bulunamadı")

    stripe = get_stripe()

    try:
        return_url = request.return_url or f"{settings.APP_URL}/dashboard"
        session = stripe.billing_portal.Session.create(
            customer=current_user.stripe_customer_id,
            return_url=return_url,
        )
        return {"portal_url": session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """Handle Stripe webhook events."""
    if not settings.STRIPE_SECRET_KEY:
        raise HTTPException(status_code=501, detail="Stripe yapılandırılmadı")

    payload = await request.body()
    stripe = get_stripe()

    try:
        event = stripe.Webhook.construct_event(
            payload,
            stripe_signature,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook doğrulama hatası: {str(e)}")

    event_type = event["type"]
    data = event["data"]["object"]

    logger.info(f"Stripe webhook: {event_type}")

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, db)

    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, db)

    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, db)

    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, db)

    return {"status": "ok"}


async def _handle_checkout_completed(session_data: dict, db: Session):
    """Handle successful checkout - activate subscription."""
    user_id = session_data.get("metadata", {}).get("user_id")
    plan = session_data.get("metadata", {}).get("plan")
    stripe_sub_id = session_data.get("subscription")

    if not user_id or not plan:
        return

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return

    # Update or create subscription
    sub = user.subscription
    if not sub:
        sub = Subscription(user_id=user.id)
        db.add(sub)

    sub.plan = plan
    sub.status = "active"
    sub.stripe_subscription_id = stripe_sub_id
    db.commit()
    logger.info(f"Subscription activated: user={user_id} plan={plan}")


async def _handle_subscription_updated(sub_data: dict, db: Session):
    """Handle subscription update from Stripe."""
    stripe_sub_id = sub_data.get("id")
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()
    if not sub:
        return

    sub.status = sub_data.get("status", sub.status)
    sub.cancel_at_period_end = sub_data.get("cancel_at_period_end", False)

    import datetime as dt
    if sub_data.get("current_period_start"):
        sub.current_period_start = dt.datetime.fromtimestamp(sub_data["current_period_start"])
    if sub_data.get("current_period_end"):
        sub.current_period_end = dt.datetime.fromtimestamp(sub_data["current_period_end"])

    db.commit()


async def _handle_subscription_deleted(sub_data: dict, db: Session):
    """Handle subscription cancellation."""
    stripe_sub_id = sub_data.get("id")
    sub = db.query(Subscription).filter(
        Subscription.stripe_subscription_id == stripe_sub_id
    ).first()
    if sub:
        sub.status = "canceled"
        sub.plan = "free"
        db.commit()
        logger.info(f"Subscription canceled: {stripe_sub_id}")


async def _handle_payment_failed(invoice_data: dict, db: Session):
    """Handle failed payment."""
    customer_id = invoice_data.get("customer")
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if user and user.subscription:
        user.subscription.status = "past_due"
        db.commit()
        logger.warning(f"Payment failed for user: {user.id}")
