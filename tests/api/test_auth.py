"""Tests for app/api/v1/auth.py — login, callback, /me, cookie security."""

import pytest
from unittest.mock import AsyncMock
from uuid import UUID
from fastapi.responses import RedirectResponse
from app.models import User
from app.api.v1.routes import serializer
from sqlmodel import select


# ─────────────────────────────────────────────────────────────
# Auth Callback
# ─────────────────────────────────────────────────────────────

class TestAuthCallback:

    @pytest.mark.asyncio
    async def test_callback_redirects_to_dashboard(self, client, session, mocker):
        mock_token = {
            "access_token": "fake-token",
            "userinfo": {"sub": "12345", "email": "test@example.com", "name": "Test User"},
        }
        mocker.patch("app.api.v1.auth.google_auth.authorize_access_token", return_value=mock_token)
        mocker.patch("app.api.v1.auth.google_auth.get_user_info", return_value=mock_token["userinfo"])

        response = client.get(
            "/api/v1/auth/callback?code=fake-auth-code&state=fake-state",
            follow_redirects=False,
        )

        assert response.status_code == 307
        assert response.headers["location"] == "/dashboard"

        statement = select(User).where(User.email == "test@example.com")
        user = session.exec(statement).first()
        assert user is not None
        assert user.sub == "12345"
        assert user.name == "Test User"

        assert "paws_user_id" in response.cookies
        assert serializer.loads(response.cookies["paws_user_id"]) == str(user.id)

    @pytest.mark.asyncio
    async def test_callback_sets_restorable_cookie(self, client, session, mocker):
        mock_token = {
            "access_token": "fake-token",
            "userinfo": {
                "sub": "preserve-storage-sub",
                "email": "preserve-storage@example.com",
                "name": "Preserve Storage User",
            },
        }
        mocker.patch("app.api.v1.auth.google_auth.authorize_access_token", return_value=mock_token)
        mocker.patch("app.api.v1.auth.google_auth.get_user_info", return_value=mock_token["userinfo"])

        response = client.get(
            "/api/v1/auth/callback?code=fake-code&state=fake-state",
            follow_redirects=False,
        )

        assert response.status_code == 307
        assert "paws_user_id" in response.cookies
        user_id = serializer.loads(response.cookies["paws_user_id"])

        user = session.get(User, UUID(user_id))
        assert user is not None
        assert user.email == "preserve-storage@example.com"


# ─────────────────────────────────────────────────────────────
# Auth Login
# ─────────────────────────────────────────────────────────────

class TestAuthLogin:

    @pytest.mark.asyncio
    async def test_login_redirects_to_google(self, client, mocker):
        mock_redirect = RedirectResponse(url="https://accounts.google.com/o/oauth2/v2/auth?...")
        mocker.patch("app.api.v1.auth.google_auth.authorize_redirect", return_value=mock_redirect)

        response = client.get("/api/v1/auth/login", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"].startswith("https://accounts.google.com")

    @pytest.mark.asyncio
    async def test_login_no_500_error(self, client, mocker):
        mock_response = RedirectResponse(url="https://accounts.google.com/o/oauth2/v2/auth")
        mocker.patch("app.services.integrations.oauth.google.authorize_redirect", return_value=mock_response)
        mocker.patch("app.api.v1.auth.google_auth.client_id", "fake-client-id")

        response = client.get("/api/v1/auth/login", follow_redirects=False)
        assert response.status_code == 307


# ─────────────────────────────────────────────────────────────
# /me Endpoint
# ─────────────────────────────────────────────────────────────

class TestMeEndpoint:

    def test_me_resolves_signed_cookie(self, client, test_user):
        client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
        response = client.get("/api/v1/me")

        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["email"] == test_user.email
        assert data["user"]["name"] == test_user.name
        assert data["user"]["id"] == str(test_user.id)

    def test_tampered_cookie_returns_unauthenticated(self, client):
        client.cookies.set("paws_user_id", "tampered-not-a-uuid-value")
        response = client.get("/api/v1/me")

        assert response.status_code == 200
        data = response.json()
        assert data.get("authenticated") is False


# ─────────────────────────────────────────────────────────────
# Cookie Security
# ─────────────────────────────────────────────────────────────

class TestCookieSecurity:

    @pytest.mark.asyncio
    async def test_cookie_is_not_raw_uuid(self, client, session, mocker):
        mock_token = {
            "access_token": "fake-token",
            "userinfo": {"sub": "gap2a-sub", "email": "gap2a@example.com", "name": "Gap 2a User"},
        }
        mocker.patch("app.api.v1.auth.google_auth.authorize_access_token", return_value=mock_token)
        mocker.patch("app.api.v1.auth.google_auth.get_user_info", return_value=mock_token["userinfo"])

        response = client.get(
            "/api/v1/auth/callback?code=fake-code&state=fake-state",
            follow_redirects=False,
        )

        assert response.status_code == 307
        assert "paws_user_id" in response.cookies

        cookie_value = response.cookies["paws_user_id"]
        try:
            UUID(cookie_value)
            is_raw_uuid = True
        except ValueError:
            is_raw_uuid = False

        assert not is_raw_uuid, f"Cookie value '{cookie_value}' is a raw UUID — should be signed"

    @pytest.mark.asyncio
    async def test_cookie_has_httponly_and_samesite(self, client, session, mocker):
        mock_token = {
            "access_token": "fake-token",
            "userinfo": {"sub": "cookie-flag-sub", "email": "flags@example.com", "name": "Flags User"},
        }
        mocker.patch("app.api.v1.auth.google_auth.authorize_access_token", return_value=mock_token)
        mocker.patch("app.api.v1.auth.google_auth.get_user_info", return_value=mock_token["userinfo"])

        response = client.get(
            "/api/v1/auth/callback?code=fake-code&state=fake-state",
            follow_redirects=False,
        )

        set_cookie_headers = response.headers.get_list("set-cookie")
        paws_cookie_header = next(
            (h for h in set_cookie_headers if "paws_user_id" in h), None
        )

        assert paws_cookie_header is not None
        assert "HttpOnly" in paws_cookie_header
        assert "samesite=lax" in paws_cookie_header.lower()
