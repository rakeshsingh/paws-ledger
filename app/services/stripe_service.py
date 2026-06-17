"""Stripe payment processing service for PawsLedger subscriptions."""

import os
import logging
import stripe
from typing import Optional, Dict

logger = logging.getLogger("pawsledger.stripe")


def _ensure_stripe_configured():
    """Set Stripe API key from environment on first use."""
    if not stripe.api_key:
        stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def _get_price_id(tier: str, billing_period: str = "monthly") -> str:
    """Resolve tier + billing period to Stripe price ID at call time."""
    if billing_period == "yearly":
        mapping = {
            "verified": os.getenv("STRIPE_VERIFIED_YEARLY_PRICE_ID", ""),
            "guardian": os.getenv("STRIPE_GUARDIAN_YEARLY_PRICE_ID", ""),
        }
    else:
        mapping = {
            "verified": os.getenv("STRIPE_VERIFIED_PRICE_ID", ""),
            "guardian": os.getenv("STRIPE_GUARDIAN_PRICE_ID", ""),
        }
    price_id = mapping.get(tier)
    if not price_id:
        raise ValueError(f"Unknown tier or missing price ID for: {tier} ({billing_period})")
    return price_id


class StripeService:
    """Handles Stripe customer and subscription lifecycle."""

    @staticmethod
    def create_customer(email: str, name: str, user_id: str) -> str:
        """Create a Stripe customer and return the customer ID."""
        _ensure_stripe_configured()
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"pawsledger_user_id": user_id},
        )
        logger.info("Stripe customer created: %s", customer.id)
        return customer.id

    @staticmethod
    def create_checkout_session(
        customer_id: str,
        tier: str,
        success_url: str,
        cancel_url: str,
        billing_period: str = "monthly",
    ) -> str:
        """Create a Stripe Checkout session and return the URL."""
        _ensure_stripe_configured()
        price_id = _get_price_id(tier, billing_period)

        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={"tier": tier},
        )
        return session.url

    @staticmethod
    def retrieve_checkout_session(session_id: str) -> Optional[Dict]:
        """Retrieve a Checkout session from Stripe to verify payment."""
        _ensure_stripe_configured()
        try:
            cs = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
            logger.info(
                "Checkout session %s: payment_status=%s, customer=%s, subscription=%s, metadata=%s",
                session_id, cs.payment_status, cs.customer, cs.subscription, cs.metadata,
            )
            sub_id = cs.subscription.id if hasattr(cs.subscription, 'id') else cs.subscription
            metadata = cs.metadata.to_dict() if hasattr(cs.metadata, 'to_dict') else (cs.metadata or {})
            return {
                "id": cs.id,
                "payment_status": cs.payment_status,
                "customer": cs.customer,
                "subscription": sub_id,
                "metadata": metadata,
            }
        except Exception as e:
            logger.error("Failed to retrieve checkout session %s: %s", session_id, e)
            return None

    @staticmethod
    def create_billing_portal_session(customer_id: str, return_url: str) -> str:
        """Create a Stripe Billing Portal session for subscription management."""
        _ensure_stripe_configured()
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=return_url,
        )
        return session.url

    @staticmethod
    def cancel_subscription(subscription_id: str) -> bool:
        """Cancel a subscription at period end."""
        _ensure_stripe_configured()
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True,
            )
            logger.info("Subscription %s set to cancel at period end", subscription_id)
            return True
        except stripe.error.StripeError as e:
            logger.error("Failed to cancel subscription: %s", e)
            return False

    @staticmethod
    def reactivate_subscription(subscription_id: str) -> bool:
        """Undo a pending cancellation — resume the subscription."""
        _ensure_stripe_configured()
        try:
            stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False,
            )
            logger.info("Subscription %s reactivated", subscription_id)
            return True
        except stripe.error.StripeError as e:
            logger.error("Failed to reactivate subscription: %s", e)
            return False

    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> Optional[stripe.Event]:
        """Verify and construct a Stripe webhook event."""
        _ensure_stripe_configured()
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            logger.error("STRIPE_WEBHOOK_SECRET not configured")
            return None
        try:
            return stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except (stripe.error.SignatureVerificationError, ValueError) as e:
            logger.error("Webhook signature verification failed: %s", e)
            return None

    @staticmethod
    def get_subscription(subscription_id: str) -> Optional[Dict]:
        """Retrieve subscription details from Stripe."""
        _ensure_stripe_configured()
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            # Period dates live on the first subscription item in newer Stripe API versions
            period_start = None
            period_end = None
            if hasattr(sub, 'current_period_start'):
                period_start = sub.current_period_start
                period_end = sub.current_period_end
            elif sub.items and sub.items.data:
                item = sub.items.data[0]
                period_start = item.current_period_start
                period_end = item.current_period_end
            return {
                "id": sub.id,
                "status": sub.status,
                "current_period_start": period_start,
                "current_period_end": period_end,
                "cancel_at_period_end": sub.cancel_at_period_end,
            }
        except stripe.error.StripeError as e:
            logger.error("Failed to retrieve subscription: %s", e)
            return None
