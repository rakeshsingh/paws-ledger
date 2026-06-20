"""Tests for app/api/v1/subscription.py — checkout, portal, status, webhooks."""

import pytest
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime, timezone, timedelta
from app.models import User, Subscription, Pet, _utc_now
from app.api.v1.routes import serializer


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_client(client, test_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
    return client


@pytest.fixture
def test_subscription(session, test_user):
    sub = Subscription(
        user_id=test_user.id,
        stripe_customer_id="cus_test123",
        stripe_subscription_id="sub_test123",
        tier="verified",
        status="active",
        current_period_start=_utc_now(),
        current_period_end=_utc_now() + timedelta(days=365),
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


@pytest.fixture
def inactive_subscription(session, test_user):
    sub = Subscription(
        user_id=test_user.id,
        stripe_customer_id="cus_inactive",
        tier="free",
        status="inactive",
    )
    session.add(sub)
    session.commit()
    session.refresh(sub)
    return sub


# ─────────────────────────────────────────────────────────────
# Subscription Status
# ─────────────────────────────────────────────────────────────

class TestSubscriptionStatus:

    def test_status_no_subscription(self, authenticated_client):
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["status"] == "inactive"
        assert data["is_verified"] is False

    def test_status_active_subscription(self, authenticated_client, test_subscription):
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "verified"
        assert data["status"] == "active"
        assert data["is_verified"] is True
        assert data["current_period_end"] is not None

    def test_status_inactive_subscription(self, authenticated_client, inactive_subscription):
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["status"] == "inactive"
        assert data["is_verified"] is False

    def test_status_requires_auth(self, client):
        resp = client.get("/api/v1/subscription/status")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────
# Checkout
# ─────────────────────────────────────────────────────────────

class TestCheckout:

    @patch("app.api.v1.subscription.StripeService")
    def test_checkout_creates_session(self, mock_stripe, authenticated_client):
        mock_stripe.create_customer.return_value = "cus_new123"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/test"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified"},
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/test"

    @patch("app.api.v1.subscription.StripeService")
    def test_checkout_reuses_existing_customer(self, mock_stripe, authenticated_client, inactive_subscription):
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/reuse"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified"},
        )
        assert resp.status_code == 200
        mock_stripe.create_customer.assert_not_called()

    def test_checkout_invalid_tier(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "platinum"},
        )
        assert resp.status_code == 400
        assert "Invalid tier" in resp.json()["detail"]

    def test_checkout_already_subscribed(self, authenticated_client, test_subscription):
        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified"},
        )
        assert resp.status_code == 409
        assert "already have" in resp.json()["detail"]

    def test_checkout_requires_auth(self, client):
        resp = client.post("/api/v1/subscription/checkout", json={"tier": "verified"})
        assert resp.status_code == 401

    @patch("app.api.v1.subscription.StripeService")
    def test_checkout_with_coupon(self, mock_stripe, authenticated_client):
        mock_stripe.create_customer.return_value = "cus_coupon123"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/coupon"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified", "coupon": "SUMMER50"},
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/coupon"
        mock_stripe.create_checkout_session.assert_called_once()
        kwargs = mock_stripe.create_checkout_session.call_args[1]
        assert kwargs["coupon"] == "SUMMER50"
        assert kwargs["allow_promotion_codes"] is None

    @patch("app.api.v1.subscription.StripeService")
    def test_checkout_disallow_promotion_codes(self, mock_stripe, authenticated_client):
        mock_stripe.create_customer.return_value = "cus_promo123"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/nopromo"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified", "allow_promotion_codes": False},
        )
        assert resp.status_code == 200
        assert resp.json()["checkout_url"] == "https://checkout.stripe.com/nopromo"
        mock_stripe.create_checkout_session.assert_called_once()
        kwargs = mock_stripe.create_checkout_session.call_args[1]
        assert kwargs["coupon"] is None
        assert kwargs["allow_promotion_codes"] is False


# ─────────────────────────────────────────────────────────────
# Portal
# ─────────────────────────────────────────────────────────────

class TestPortal:

    @patch("app.api.v1.subscription.StripeService")
    def test_portal_creates_session(self, mock_stripe, authenticated_client, test_subscription):
        mock_stripe.create_billing_portal_session.return_value = "https://billing.stripe.com/portal"

        resp = authenticated_client.post("/api/v1/subscription/portal")
        assert resp.status_code == 200
        assert resp.json()["portal_url"] == "https://billing.stripe.com/portal"

    def test_portal_no_subscription(self, authenticated_client):
        resp = authenticated_client.post("/api/v1/subscription/portal")
        assert resp.status_code == 404

    def test_portal_requires_auth(self, client):
        resp = client.post("/api/v1/subscription/portal")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────
# Webhook
# ─────────────────────────────────────────────────────────────

class TestWebhook:

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_invalid_signature(self, mock_stripe, client):
        mock_stripe.construct_webhook_event.return_value = None
        resp = client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "invalid"},
        )
        assert resp.status_code == 400

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_checkout_completed(self, mock_stripe, client, session, test_user):
        # Setup: create subscription record
        sub = Subscription(
            user_id=test_user.id,
            stripe_customer_id="cus_webhook",
            tier="free",
            status="inactive",
        )
        session.add(sub)
        session.commit()

        mock_stripe.construct_webhook_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_webhook",
                    "subscription": "sub_new",
                    "metadata": {"tier": "verified"},
                }
            },
        }
        mock_stripe.get_subscription.return_value = {
            "current_period_start": int(datetime.now(timezone.utc).timestamp()),
            "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp()),
        }

        resp = client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )
        assert resp.status_code == 200

        session.refresh(sub)
        assert sub.status == "active"
        assert sub.tier == "verified"
        assert sub.stripe_subscription_id == "sub_new"

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_checkout_verifies_pets(self, mock_stripe, client, session, test_user, test_pet):
        sub = Subscription(
            user_id=test_user.id,
            stripe_customer_id="cus_verify",
            tier="free",
            status="inactive",
        )
        session.add(sub)
        test_pet.identity_status = "UNVERIFIED"
        session.add(test_pet)
        session.commit()

        mock_stripe.construct_webhook_event.return_value = {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "customer": "cus_verify",
                    "subscription": "sub_verify",
                    "metadata": {"tier": "verified"},
                }
            },
        }
        mock_stripe.get_subscription.return_value = {
            "current_period_start": int(datetime.now(timezone.utc).timestamp()),
            "current_period_end": int((datetime.now(timezone.utc) + timedelta(days=365)).timestamp()),
        }

        client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )

        session.refresh(test_pet)
        assert test_pet.identity_status == "VERIFIED"

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_subscription_deleted(self, mock_stripe, client, session, test_subscription):
        mock_stripe.construct_webhook_event.return_value = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": test_subscription.stripe_subscription_id,
                }
            },
        }

        resp = client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )
        assert resp.status_code == 200

        session.refresh(test_subscription)
        assert test_subscription.status == "canceled"
        assert test_subscription.tier == "free"

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_payment_failed(self, mock_stripe, client, session, test_subscription):
        mock_stripe.construct_webhook_event.return_value = {
            "type": "invoice.payment_failed",
            "data": {
                "object": {
                    "subscription": test_subscription.stripe_subscription_id,
                }
            },
        }

        resp = client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )
        assert resp.status_code == 200

        session.refresh(test_subscription)
        assert test_subscription.status == "past_due"

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_subscription_updated(self, mock_stripe, client, session, test_subscription):
        new_end = int((datetime.now(timezone.utc) + timedelta(days=730)).timestamp())
        mock_stripe.construct_webhook_event.return_value = {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": test_subscription.stripe_subscription_id,
                    "status": "active",
                    "current_period_start": int(datetime.now(timezone.utc).timestamp()),
                    "current_period_end": new_end,
                }
            },
        }

        resp = client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )
        assert resp.status_code == 200

        session.refresh(test_subscription)
        assert test_subscription.status == "active"


# ─────────────────────────────────────────────────────────────
# Tier Gating
# ─────────────────────────────────────────────────────────────

class TestTierGating:

    def test_verified_endpoint_blocked_for_free_tier(self, authenticated_client, test_pet):
        resp = authenticated_client.get(f"/api/v1/pets/{test_pet.id}/care-instructions")
        assert resp.status_code == 403
        assert "Verified" in resp.json()["detail"]

    def test_verified_endpoint_allowed_for_verified_tier(self, authenticated_client, test_pet, test_subscription):
        resp = authenticated_client.get(f"/api/v1/pets/{test_pet.id}/care-instructions")
        assert resp.status_code == 200


# ─────────────────────────────────────────────────────────────
# Verify Checkout Session (direct activation without webhook)
# ─────────────────────────────────────────────────────────────

class TestVerifySession:

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_activates_subscription(self, mock_stripe, authenticated_client, session, test_user):
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_test_abc",
            "payment_status": "paid",
            "customer": "cus_new_verify",
            "subscription": "sub_new_verify",
            "metadata": {"tier": "verified"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test_abc"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "verified"
        assert data["status"] == "active"

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_updates_existing_inactive_subscription(
        self, mock_stripe, authenticated_client, session, test_user, inactive_subscription
    ):
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_test_upgrade",
            "payment_status": "paid",
            "customer": "cus_inactive",
            "subscription": "sub_upgraded",
            "metadata": {"tier": "guardian"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test_upgrade"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "guardian"
        assert data["status"] == "active"

        session.refresh(inactive_subscription)
        assert inactive_subscription.status == "active"
        assert inactive_subscription.tier == "guardian"

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_marks_pets_verified(self, mock_stripe, authenticated_client, session, test_user, test_pet):
        test_pet.identity_status = "UNVERIFIED"
        session.add(test_pet)
        session.commit()

        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_test_pets",
            "payment_status": "paid",
            "customer": "cus_pet_verify",
            "subscription": "sub_pet_verify",
            "metadata": {"tier": "verified"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test_pets"},
        )
        assert resp.status_code == 200

        session.refresh(test_pet)
        assert test_pet.identity_status == "VERIFIED"

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_skips_already_active(self, mock_stripe, authenticated_client, test_subscription):
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_test_dup",
            "payment_status": "paid",
            "customer": "cus_test123",
            "subscription": "sub_test123",
            "metadata": {"tier": "verified"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test_dup"},
        )
        assert resp.status_code == 200

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_accepts_no_payment_required(self, mock_stripe, authenticated_client):
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_test_trial",
            "payment_status": "no_payment_required",
            "customer": "cus_trial",
            "subscription": "sub_trial",
            "metadata": {"tier": "verified"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test_trial"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_rejects_unpaid(self, mock_stripe, authenticated_client):
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_test_unpaid",
            "payment_status": "unpaid",
            "customer": "cus_unpaid",
            "subscription": None,
            "metadata": {"tier": "verified"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test_unpaid"},
        )
        assert resp.status_code == 400

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_rejects_invalid_session(self, mock_stripe, authenticated_client):
        mock_stripe.retrieve_checkout_session.return_value = None

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_invalid"},
        )
        assert resp.status_code == 400

    def test_verify_session_missing_session_id(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={},
        )
        assert resp.status_code == 400

    def test_verify_session_requires_auth(self, client):
        resp = client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_test"},
        )
        assert resp.status_code == 400


# ─────────────────────────────────────────────────────────────
# Cancel Subscription
# ─────────────────────────────────────────────────────────────

class TestCancelSubscription:

    @patch("app.api.v1.subscription.StripeService")
    def test_cancel_sets_cancel_at_period_end(self, mock_stripe, authenticated_client, session, test_subscription):
        mock_stripe.cancel_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "canceling"
        assert data["cancel_at_period_end"] is True
        assert data["current_period_end"] is not None

        session.refresh(test_subscription)
        assert test_subscription.cancel_at_period_end is True

    @patch("app.api.v1.subscription.StripeService")
    def test_cancel_calls_stripe(self, mock_stripe, authenticated_client, test_subscription):
        mock_stripe.cancel_subscription.return_value = True

        authenticated_client.post("/api/v1/subscription/cancel")
        mock_stripe.cancel_subscription.assert_called_once_with("sub_test123")

    def test_cancel_requires_auth(self, client):
        resp = client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 401

    def test_cancel_no_subscription(self, authenticated_client):
        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 404
        assert "No active subscription" in resp.json()["detail"]

    def test_cancel_inactive_subscription(self, authenticated_client, inactive_subscription):
        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 404

    @patch("app.api.v1.subscription.StripeService")
    def test_cancel_already_canceling(self, mock_stripe, authenticated_client, session, test_subscription):
        test_subscription.cancel_at_period_end = True
        session.add(test_subscription)
        session.commit()

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 409
        assert "already scheduled" in resp.json()["detail"]

    @patch("app.api.v1.subscription.StripeService")
    def test_cancel_stripe_failure(self, mock_stripe, authenticated_client, test_subscription):
        mock_stripe.cancel_subscription.return_value = False

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 502
        assert "Failed to cancel" in resp.json()["detail"]

    def test_cancel_no_stripe_subscription_id(self, authenticated_client, session, test_user):
        sub = Subscription(
            user_id=test_user.id,
            stripe_customer_id="cus_no_sub",
            tier="verified",
            status="active",
            stripe_subscription_id=None,
        )
        session.add(sub)
        session.commit()

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 400
        assert "No Stripe subscription" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# Reactivate Subscription
# ─────────────────────────────────────────────────────────────

class TestReactivateSubscription:

    @patch("app.api.v1.subscription.StripeService")
    def test_reactivate_clears_cancel_flag(self, mock_stripe, authenticated_client, session, test_subscription):
        test_subscription.cancel_at_period_end = True
        session.add(test_subscription)
        session.commit()

        mock_stripe.reactivate_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "active"
        assert data["cancel_at_period_end"] is False

        session.refresh(test_subscription)
        assert test_subscription.cancel_at_period_end is False

    @patch("app.api.v1.subscription.StripeService")
    def test_reactivate_calls_stripe(self, mock_stripe, authenticated_client, session, test_subscription):
        test_subscription.cancel_at_period_end = True
        session.add(test_subscription)
        session.commit()

        mock_stripe.reactivate_subscription.return_value = True

        authenticated_client.post("/api/v1/subscription/reactivate")
        mock_stripe.reactivate_subscription.assert_called_once_with("sub_test123")

    def test_reactivate_requires_auth(self, client):
        resp = client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 401

    def test_reactivate_no_subscription(self, authenticated_client):
        resp = authenticated_client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 404

    def test_reactivate_not_canceling(self, authenticated_client, test_subscription):
        resp = authenticated_client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 409
        assert "not scheduled to cancel" in resp.json()["detail"]

    @patch("app.api.v1.subscription.StripeService")
    def test_reactivate_stripe_failure(self, mock_stripe, authenticated_client, session, test_subscription):
        test_subscription.cancel_at_period_end = True
        session.add(test_subscription)
        session.commit()

        mock_stripe.reactivate_subscription.return_value = False

        resp = authenticated_client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 502
        assert "Failed to reactivate" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# End-to-End Subscribe → Unsubscribe Workflow
# ─────────────────────────────────────────────────────────────

class TestSubscribeUnsubscribeWorkflow:
    """Validates the full user journey: subscribe → verify active → cancel → verify canceling → reactivate."""

    @patch("app.api.v1.subscription.StripeService")
    def test_full_subscribe_then_cancel_workflow(self, mock_stripe, authenticated_client, session, test_user):
        """User subscribes via checkout, then cancels, then status reflects pending cancellation."""
        # Step 1: Create checkout
        mock_stripe.create_customer.return_value = "cus_workflow"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/wf"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified", "billing_period": "monthly"},
        )
        assert resp.status_code == 200
        assert "checkout_url" in resp.json()

        # Step 2: Simulate successful payment via verify-session
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_wf_123",
            "payment_status": "paid",
            "customer": "cus_workflow",
            "subscription": "sub_workflow",
            "metadata": {"tier": "verified"},
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_wf_123"},
        )
        assert resp.status_code == 200
        assert resp.json()["tier"] == "verified"
        assert resp.json()["status"] == "active"

        # Step 3: Confirm status shows active
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "verified"
        assert data["status"] == "active"
        assert data["is_verified"] is True
        assert data["cancel_at_period_end"] is False

        # Step 4: Cancel subscription
        mock_stripe.cancel_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceling"
        assert resp.json()["cancel_at_period_end"] is True

        # Step 5: Status reflects pending cancellation (still active until period end)
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "verified"
        assert data["status"] == "active"
        assert data["is_verified"] is True
        assert data["cancel_at_period_end"] is True

    @patch("app.api.v1.subscription.StripeService")
    def test_cancel_then_reactivate_workflow(self, mock_stripe, authenticated_client, session, test_subscription):
        """User cancels, changes mind, reactivates — subscription restored to normal active state."""
        # Step 1: Cancel
        mock_stripe.cancel_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 200
        assert resp.json()["cancel_at_period_end"] is True

        # Step 2: Status shows canceling
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        assert resp.json()["cancel_at_period_end"] is True
        assert resp.json()["is_verified"] is True  # still active until period end

        # Step 3: Reactivate
        mock_stripe.reactivate_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
        assert resp.json()["cancel_at_period_end"] is False

        # Step 4: Status back to normal
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "verified"
        assert data["status"] == "active"
        assert data["is_verified"] is True
        assert data["cancel_at_period_end"] is False

    @patch("app.api.v1.subscription.StripeService")
    def test_cancel_prevents_double_cancel(self, mock_stripe, authenticated_client, session, test_subscription):
        """After canceling, a second cancel attempt is rejected."""
        mock_stripe.cancel_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 200

        # Second cancel fails
        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 409

    @patch("app.api.v1.subscription.StripeService")
    def test_reactivate_prevents_double_reactivate(self, mock_stripe, authenticated_client, session, test_subscription):
        """If subscription is not canceling, reactivate is rejected."""
        resp = authenticated_client.post("/api/v1/subscription/reactivate")
        assert resp.status_code == 409

    @patch("app.api.v1.subscription.StripeService")
    def test_webhook_deletion_after_cancel(self, mock_stripe, authenticated_client, client, session, test_subscription):
        """After cancel, when period ends Stripe sends subscription.deleted webhook → tier reverts to free."""
        # Cancel
        mock_stripe.cancel_subscription.return_value = True
        authenticated_client.post("/api/v1/subscription/cancel")

        # Simulate Stripe webhook when period actually ends
        mock_stripe.construct_webhook_event.return_value = {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": test_subscription.stripe_subscription_id,
                }
            },
        }

        resp = client.post(
            "/api/v1/subscription/webhook",
            content=b"{}",
            headers={"stripe-signature": "valid"},
        )
        assert resp.status_code == 200

        # Status now shows free/canceled
        resp = authenticated_client.get("/api/v1/subscription/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["status"] == "canceled"
        assert data["is_verified"] is False


# ─────────────────────────────────────────────────────────────
# Billing Period in Checkout
# ─────────────────────────────────────────────────────────────

class TestBillingPeriod:

    @patch("app.api.v1.subscription.StripeService")
    def test_checkout_monthly_default(self, mock_stripe, authenticated_client):
        mock_stripe.create_customer.return_value = "cus_monthly"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/monthly"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified"},
        )
        assert resp.status_code == 200
        mock_stripe.create_checkout_session.assert_called_once()
        call_kwargs = mock_stripe.create_checkout_session.call_args
        assert call_kwargs.kwargs.get("billing_period", "monthly") == "monthly" or \
            call_kwargs[1].get("billing_period", "monthly") == "monthly"

    @patch("app.api.v1.subscription.StripeService")
    def test_checkout_yearly(self, mock_stripe, authenticated_client):
        mock_stripe.create_customer.return_value = "cus_yearly"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/yearly"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified", "billing_period": "yearly"},
        )
        assert resp.status_code == 200
        mock_stripe.create_checkout_session.assert_called_once()
        call_kwargs = mock_stripe.create_checkout_session.call_args
        assert "yearly" in str(call_kwargs)

    def test_checkout_invalid_billing_period(self, authenticated_client):
        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified", "billing_period": "weekly"},
        )
        assert resp.status_code == 400
        assert "billing_period" in resp.json()["detail"]


# ─────────────────────────────────────────────────────────────
# Subscription Data Integrity — verify all DB fields populated
# ─────────────────────────────────────────────────────────────

class TestSubscriptionDataIntegrity:
    """Verify that stripe_subscription_id, current_period_start, and
    current_period_end are populated after subscription activation."""

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_stores_stripe_subscription_id(
        self, mock_stripe, authenticated_client, session, test_user
    ):
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_integrity",
            "payment_status": "paid",
            "customer": "cus_integrity",
            "subscription": "sub_integrity_123",
            "metadata": {"tier": "verified"},
        }
        mock_stripe.get_subscription.return_value = {
            "id": "sub_integrity_123",
            "status": "active",
            "current_period_start": 1718000000,
            "current_period_end": 1720592000,
            "cancel_at_period_end": False,
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_integrity"},
        )
        assert resp.status_code == 200

        from sqlmodel import select
        sub = session.exec(
            select(Subscription).where(Subscription.user_id == test_user.id)
        ).first()
        assert sub is not None
        assert sub.stripe_subscription_id == "sub_integrity_123"
        assert sub.stripe_customer_id == "cus_integrity"
        assert sub.current_period_start is not None
        assert sub.current_period_end is not None
        assert sub.status == "active"
        assert sub.tier == "verified"

    @patch("app.api.v1.subscription.StripeService")
    def test_verify_session_updates_existing_sub_with_stripe_ids(
        self, mock_stripe, authenticated_client, session, test_user, inactive_subscription
    ):
        """When a sub record already exists (inactive), verify-session fills in all Stripe fields."""
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_upgrade",
            "payment_status": "paid",
            "customer": "cus_inactive",
            "subscription": "sub_upgraded_456",
            "metadata": {"tier": "verified"},
        }
        mock_stripe.get_subscription.return_value = {
            "id": "sub_upgraded_456",
            "status": "active",
            "current_period_start": 1718000000,
            "current_period_end": 1720592000,
            "cancel_at_period_end": False,
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_upgrade"},
        )
        assert resp.status_code == 200

        session.refresh(inactive_subscription)
        assert inactive_subscription.stripe_subscription_id == "sub_upgraded_456"
        assert inactive_subscription.current_period_start is not None
        assert inactive_subscription.current_period_end is not None
        assert inactive_subscription.status == "active"

    @patch("app.api.v1.subscription.StripeService")
    def test_full_flow_checkout_activate_cancel_data_integrity(
        self, mock_stripe, authenticated_client, session, test_user
    ):
        """End-to-end: checkout → activate → verify DB fields → cancel succeeds."""
        # Checkout
        mock_stripe.create_customer.return_value = "cus_e2e"
        mock_stripe.create_checkout_session.return_value = "https://checkout.stripe.com/e2e"

        resp = authenticated_client.post(
            "/api/v1/subscription/checkout",
            json={"tier": "verified", "billing_period": "monthly"},
        )
        assert resp.status_code == 200

        # Activate via verify-session
        mock_stripe.retrieve_checkout_session.return_value = {
            "id": "cs_e2e",
            "payment_status": "paid",
            "customer": "cus_e2e",
            "subscription": "sub_e2e_789",
            "metadata": {"tier": "verified"},
        }
        mock_stripe.get_subscription.return_value = {
            "id": "sub_e2e_789",
            "status": "active",
            "current_period_start": 1718000000,
            "current_period_end": 1720592000,
            "cancel_at_period_end": False,
        }

        resp = authenticated_client.post(
            "/api/v1/subscription/verify-session",
            json={"session_id": "cs_e2e"},
        )
        assert resp.status_code == 200

        # Verify DB state
        from sqlmodel import select
        sub = session.exec(
            select(Subscription).where(Subscription.user_id == test_user.id)
        ).first()
        assert sub.stripe_subscription_id == "sub_e2e_789"
        assert sub.stripe_customer_id == "cus_e2e"
        assert sub.current_period_start is not None
        assert sub.current_period_end is not None

        # Cancel should succeed (not 400 "No Stripe subscription to cancel")
        mock_stripe.cancel_subscription.return_value = True

        resp = authenticated_client.post("/api/v1/subscription/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "canceling"
        assert resp.json()["cancel_at_period_end"] is True
        assert resp.json()["current_period_end"] is not None
