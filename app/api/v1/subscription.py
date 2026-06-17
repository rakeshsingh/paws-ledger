"""Subscription routes — Stripe checkout, webhooks, tier management."""

import os
import logging
from datetime import datetime, timezone
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlmodel import Session, select
from ...database import get_session
from ...models import User, Pet, Subscription, _utc_now
from ...services.stripe_service import StripeService
from .common import get_current_user

logger = logging.getLogger("pawsledger.subscription")
router = APIRouter()


class CheckoutRequest(BaseModel):
    tier: str  # "verified" or "guardian"
    billing_period: str = "monthly"  # "monthly" or "yearly"


def _get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    return get_current_user(request, session)


def get_user_tier(user: User, session: Session) -> str:
    """Get the active subscription tier for a user."""
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()
    if not sub or sub.status != "active":
        return "free"
    return sub.tier


def require_verified_tier(request: Request, session: Session = Depends(get_session)) -> User:
    """Dependency that requires at least Verified tier."""
    user = get_current_user(request, session)
    tier = get_user_tier(user, session)
    if tier not in ("verified", "guardian"):
        raise HTTPException(
            status_code=403,
            detail="This feature requires a Verified or Guardian subscription.",
        )
    return user


@router.post("/subscription/checkout")
async def create_checkout(
    payload: CheckoutRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    """Create a Stripe Checkout session for subscription purchase."""
    user = _get_current_user(request, session)

    if payload.tier not in ("verified",):
        raise HTTPException(status_code=400, detail="Invalid tier. Only 'verified' is available.")

    if payload.tier == "guardian":
        raise HTTPException(status_code=400, detail="Guardian tier is not yet available.")

    if payload.billing_period not in ("monthly", "yearly"):
        raise HTTPException(status_code=400, detail="Invalid billing_period. Use 'monthly' or 'yearly'.")

    # Get or create subscription record
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()

    if sub and sub.status == "active":
        raise HTTPException(status_code=409, detail="You already have an active subscription.")

    # Create Stripe customer if needed
    if sub and sub.stripe_customer_id:
        customer_id = sub.stripe_customer_id
    else:
        customer_id = StripeService.create_customer(
            email=user.email,
            name=user.name,
            user_id=str(user.id),
        )
        if not sub:
            sub = Subscription(
                user_id=user.id,
                stripe_customer_id=customer_id,
                tier="free",
                status="inactive",
            )
            session.add(sub)
            session.commit()
        else:
            sub.stripe_customer_id = customer_id
            session.add(sub)
            session.commit()

    base_url = os.getenv("BASE_URL", "https://www.pawsledger.com")
    checkout_url = StripeService.create_checkout_session(
        customer_id=customer_id,
        tier=payload.tier,
        billing_period=payload.billing_period,
        success_url=f"{base_url}/subscription/success?tier={payload.tier}&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}/pricing",
    )

    return {"checkout_url": checkout_url}


def _activate_from_checkout_session(session_id: str, request: Request, session: Session):
    """Verify a Stripe Checkout session and activate the subscription in the DB.

    Can be called directly (from the success page) or via the API endpoint.
    """
    from .common import serializer
    raw_cookie = request.cookies.get("paws_user_id")
    if not raw_cookie:
        return None
    try:
        user_id = serializer.loads(raw_cookie)
        user = session.get(User, UUID(user_id))
    except Exception:
        return None
    if not user:
        return None

    checkout = StripeService.retrieve_checkout_session(session_id)
    if not checkout:
        return None

    if checkout.get("payment_status") not in ("paid", "no_payment_required"):
        return None

    customer_id = checkout.get("customer")
    subscription_id = checkout.get("subscription")
    tier = checkout.get("metadata", {}).get("tier", "verified")

    # Fetch period dates from Stripe subscription
    period_start = None
    period_end = None
    if subscription_id:
        stripe_sub = StripeService.get_subscription(subscription_id)
        if stripe_sub:
            period_start = datetime.fromtimestamp(
                stripe_sub["current_period_start"], tz=timezone.utc
            ).replace(tzinfo=None)
            period_end = datetime.fromtimestamp(
                stripe_sub["current_period_end"], tz=timezone.utc
            ).replace(tzinfo=None)

    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()

    if not sub:
        sub = Subscription(
            user_id=user.id,
            stripe_customer_id=customer_id,
            tier=tier,
            status="active",
            stripe_subscription_id=subscription_id,
            current_period_start=period_start,
            current_period_end=period_end,
        )
        session.add(sub)
    else:
        sub.stripe_customer_id = customer_id or sub.stripe_customer_id
        sub.stripe_subscription_id = subscription_id or sub.stripe_subscription_id
        sub.tier = tier
        sub.status = "active"
        sub.cancel_at_period_end = False
        sub.current_period_start = period_start or sub.current_period_start
        sub.current_period_end = period_end or sub.current_period_end
        sub.updated_at = _utc_now()
        session.add(sub)

    for pet in user.pets:
        pet.identity_status = "VERIFIED"
        session.add(pet)

    session.commit()
    logger.info("Subscription verified via checkout session: user=%s tier=%s", user.id, tier)
    return {"tier": tier, "status": "active"}


@router.post("/subscription/verify-session")
async def verify_checkout_session(
    request: Request,
    session: Session = Depends(get_session),
):
    """Verify a completed Stripe Checkout session and activate subscription."""
    body = await request.json()
    session_id = body.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing session_id")

    result = _activate_from_checkout_session(session_id, request, session)
    if not result:
        raise HTTPException(status_code=400, detail="Could not verify checkout session")

    return result


@router.post("/subscription/cancel")
async def cancel_subscription(
    request: Request,
    session: Session = Depends(get_session),
):
    """Cancel subscription at end of current billing period."""
    user = _get_current_user(request, session)

    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()
    if not sub or sub.status != "active":
        raise HTTPException(status_code=404, detail="No active subscription found.")
    if not sub.stripe_subscription_id:
        raise HTTPException(status_code=400, detail="No Stripe subscription to cancel.")
    if sub.cancel_at_period_end:
        raise HTTPException(status_code=409, detail="Subscription is already scheduled to cancel.")

    success = StripeService.cancel_subscription(sub.stripe_subscription_id)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to cancel subscription with Stripe.")

    sub.cancel_at_period_end = True
    sub.updated_at = _utc_now()
    session.add(sub)
    session.commit()

    logger.info("Subscription cancel requested: user=%s", user.id)
    return {
        "status": "canceling",
        "cancel_at_period_end": True,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.post("/subscription/reactivate")
async def reactivate_subscription(
    request: Request,
    session: Session = Depends(get_session),
):
    """Undo a pending cancellation — resume subscription."""
    user = _get_current_user(request, session)

    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()
    if not sub or sub.status != "active":
        raise HTTPException(status_code=404, detail="No active subscription found.")
    if not sub.cancel_at_period_end:
        raise HTTPException(status_code=409, detail="Subscription is not scheduled to cancel.")

    success = StripeService.reactivate_subscription(sub.stripe_subscription_id)
    if not success:
        raise HTTPException(status_code=502, detail="Failed to reactivate subscription with Stripe.")

    sub.cancel_at_period_end = False
    sub.updated_at = _utc_now()
    session.add(sub)
    session.commit()

    logger.info("Subscription reactivated: user=%s", user.id)
    return {"status": "active", "cancel_at_period_end": False}


@router.post("/subscription/portal")
async def create_portal_session(
    request: Request,
    session: Session = Depends(get_session),
):
    """Create a Stripe Billing Portal session for managing subscription."""
    user = _get_current_user(request, session)

    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()
    if not sub or not sub.stripe_customer_id:
        raise HTTPException(status_code=404, detail="No subscription found.")

    base_url = os.getenv("BASE_URL", "https://www.pawsledger.com")
    portal_url = StripeService.create_billing_portal_session(
        customer_id=sub.stripe_customer_id,
        return_url=f"{base_url}/dashboard",
    )

    return {"portal_url": portal_url}


@router.get("/subscription/status")
async def get_subscription_status(
    request: Request,
    session: Session = Depends(get_session),
):
    """Get current user's subscription status."""
    user = _get_current_user(request, session)

    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()

    if not sub:
        return {"tier": "free", "status": "inactive", "is_verified": False}

    return {
        "tier": sub.tier,
        "status": sub.status,
        "is_verified": sub.tier in ("verified", "guardian") and sub.status == "active",
        "cancel_at_period_end": sub.cancel_at_period_end,
        "current_period_end": sub.current_period_end.isoformat() if sub.current_period_end else None,
    }


@router.post("/subscription/webhook")
async def stripe_webhook(request: Request, session: Session = Depends(get_session)):
    """Handle Stripe webhook events for subscription lifecycle."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    event = StripeService.construct_webhook_event(payload, sig_header)
    if not event:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data, session)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data, session)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data, session)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data, session)

    return {"status": "ok"}


async def _handle_checkout_completed(data: dict, session: Session):
    """Activate subscription after successful checkout."""
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    tier = data.get("metadata", {}).get("tier", "verified")

    sub = session.exec(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    ).first()

    if not sub:
        logger.error("No subscription record for customer %s", customer_id)
        return

    sub.stripe_subscription_id = subscription_id
    sub.tier = tier
    sub.status = "active"
    sub.updated_at = _utc_now()

    # Fetch period dates from Stripe
    stripe_sub = StripeService.get_subscription(subscription_id)
    if stripe_sub:
        sub.current_period_start = datetime.fromtimestamp(
            stripe_sub["current_period_start"], tz=timezone.utc
        ).replace(tzinfo=None)
        sub.current_period_end = datetime.fromtimestamp(
            stripe_sub["current_period_end"], tz=timezone.utc
        ).replace(tzinfo=None)

    session.add(sub)
    session.commit()

    # Update user identity status for verified badge
    user = session.get(User, sub.user_id)
    if user:
        for pet in user.pets:
            pet.identity_status = "VERIFIED"
            session.add(pet)
        session.commit()

    logger.info("Subscription activated: user=%s tier=%s", sub.user_id, tier)


async def _handle_subscription_updated(data: dict, session: Session):
    """Handle subscription updates (renewals, plan changes)."""
    subscription_id = data.get("id")
    status = data.get("status")

    sub = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()
    if not sub:
        return

    sub.status = status
    sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
    sub.updated_at = _utc_now()

    period_start = data.get("current_period_start")
    period_end = data.get("current_period_end")
    if period_start:
        sub.current_period_start = datetime.fromtimestamp(period_start, tz=timezone.utc).replace(tzinfo=None)
    if period_end:
        sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc).replace(tzinfo=None)

    session.add(sub)
    session.commit()


async def _handle_subscription_deleted(data: dict, session: Session):
    """Handle subscription cancellation."""
    subscription_id = data.get("id")

    sub = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()
    if not sub:
        return

    sub.status = "canceled"
    sub.tier = "free"
    sub.updated_at = _utc_now()
    session.add(sub)

    # Revert verified badge on all pets
    user = session.get(User, sub.user_id)
    if user:
        for pet in user.pets:
            pet.identity_status = "UNVERIFIED"
            session.add(pet)

    session.commit()

    logger.info("Subscription canceled: user=%s", sub.user_id)


async def _handle_payment_failed(data: dict, session: Session):
    """Handle failed payment — mark subscription as past_due and notify user."""
    subscription_id = data.get("subscription")
    if not subscription_id:
        return

    sub = session.exec(
        select(Subscription).where(Subscription.stripe_subscription_id == subscription_id)
    ).first()
    if not sub:
        return

    sub.status = "past_due"
    sub.updated_at = _utc_now()
    session.add(sub)
    session.commit()

    # Notify user via email
    user = session.get(User, sub.user_id)
    if user:
        from ...services.integrations import EmailService
        await EmailService.send_payment_failed_notification(user.email, user.name)

    logger.warning("Payment failed for user=%s", sub.user_id)
