import pytest
from unittest.mock import patch, MagicMock
from app.services.stripe_service import StripeService


class TestStripeServiceCheckoutSession:

    @patch("app.services.stripe_service.stripe.checkout.Session.create")
    def test_create_checkout_session_defaults(self, mock_session_create):
        mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/test")

        url = StripeService.create_checkout_session(
            customer_id="cus_test123",
            tier="verified",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            billing_period="monthly",
        )

        assert url == "https://checkout.stripe.com/test"
        mock_session_create.assert_called_once()
        kwargs = mock_session_create.call_args[1]
        assert kwargs["customer"] == "cus_test123"
        assert kwargs["allow_promotion_codes"] is True
        assert "discounts" not in kwargs

    @patch("app.services.stripe_service.stripe.checkout.Session.create")
    def test_create_checkout_session_with_coupon(self, mock_session_create):
        mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/coupon")

        url = StripeService.create_checkout_session(
            customer_id="cus_test123",
            tier="verified",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            billing_period="monthly",
            coupon="COUPON50",
        )

        assert url == "https://checkout.stripe.com/coupon"
        mock_session_create.assert_called_once()
        kwargs = mock_session_create.call_args[1]
        assert kwargs["customer"] == "cus_test123"
        assert kwargs["discounts"] == [{"coupon": "COUPON50"}]
        assert "allow_promotion_codes" not in kwargs

    @patch("app.services.stripe_service.stripe.checkout.Session.create")
    def test_create_checkout_session_disallow_promo_codes(self, mock_session_create):
        mock_session_create.return_value = MagicMock(url="https://checkout.stripe.com/nopromo")

        url = StripeService.create_checkout_session(
            customer_id="cus_test123",
            tier="verified",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            billing_period="monthly",
            allow_promotion_codes=False,
        )

        assert url == "https://checkout.stripe.com/nopromo"
        mock_session_create.assert_called_once()
        kwargs = mock_session_create.call_args[1]
        assert kwargs["customer"] == "cus_test123"
        assert "allow_promotion_codes" not in kwargs
        assert "discounts" not in kwargs
