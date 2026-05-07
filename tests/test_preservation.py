"""
Preservation Property Tests — Existing Behavior Baseline

These tests capture the CURRENT working behavior of the unfixed code.
They are written using observation-first methodology: run on unfixed code,
observe outputs, write tests asserting those outputs.

ALL tests in this file MUST PASS on the current unfixed code.
After fixes are applied, these tests should CONTINUE to pass (no regressions).

**Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8**
"""

import pytest
from unittest.mock import AsyncMock
from app.models import User, Pet, LedgerEvent
from app.api.v1.routes import serializer
from sqlmodel import select


# ---------------------------------------------------------------------------
# Test 1 — Session Restoration via Cookie (Req 3.1)
# ---------------------------------------------------------------------------
class TestSessionRestoration:
    """
    **Validates: Requirements 3.1**

    After auth callback, a signed cookie is set. When a NiceGUI page reads
    this cookie via try_restore_session(), it must populate
    app.storage.user with email, name, id, and greet_user keys.

    Since try_restore_session runs in a NiceGUI WebSocket context that
    cannot be tested via the FastAPI test client, we verify the prerequisite:
    the auth callback sets a valid signed cookie that resolves to the
    correct user.
    """

    @pytest.mark.asyncio
    async def test_auth_callback_sets_restorable_cookie(self, client, session, mocker):
        # Arrange — mock Google auth flow
        mock_token = {
            "access_token": "fake-token",
            "userinfo": {
                "sub": "preserve-storage-sub",
                "email": "preserve-storage@example.com",
                "name": "Preserve Storage User",
            },
        }
        mocker.patch(
            "app.api.v1.auth.google_auth.authorize_access_token",
            return_value=mock_token,
        )
        mocker.patch(
            "app.api.v1.auth.google_auth.get_user_info",
            return_value=mock_token["userinfo"],
        )

        # Act
        response = client.get("/api/v1/auth/callback?code=fake-code&state=fake-state", follow_redirects=False)

        # Assert — redirect to dashboard
        assert response.status_code == 307
        assert response.headers["location"] == "/dashboard"

        # Assert — cookie is set and resolves to the correct user
        assert "paws_user_id" in response.cookies
        user_id = serializer.loads(response.cookies["paws_user_id"])

        from uuid import UUID
        user = session.get(User, UUID(user_id))
        assert user is not None
        assert user.email == "preserve-storage@example.com"
        assert user.name == "Preserve Storage User"


# ---------------------------------------------------------------------------
# Test 2 — /me Endpoint Resolution (Req 3.2)
# ---------------------------------------------------------------------------
class TestMeEndpointResolution:
    """
    **Validates: Requirements 3.2**

    Setting paws_user_id cookie to a valid signed value and calling GET /me
    should return {"authenticated": true, "user": {...}}. The preservation
    concern is that /me continues to resolve valid cookies to users.
    """

    def test_me_resolves_signed_cookie(self, client, test_user):
        # Arrange — set cookie to the user's signed UUID (current format)
        client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))

        # Act
        response = client.get("/api/v1/me")

        # Assert — authenticated with correct user data
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["user"]["email"] == test_user.email
        assert data["user"]["name"] == test_user.name
        assert data["user"]["id"] == str(test_user.id)


# ---------------------------------------------------------------------------
# Test 3 — QR Scan Side Effects (Req 3.3)
# ---------------------------------------------------------------------------
class TestQRScanSideEffects:
    """
    **Validates: Requirements 3.3**

    Scanning a QR tag must log an EMERGENCY_SCAN ledger event and call
    notify_owner_of_scan. This works on unfixed code.
    """

    @pytest.mark.asyncio
    async def test_qr_scan_creates_ledger_event_and_notifies(
        self, client, session, test_pet, mocker
    ):
        # Arrange — mock email notification
        mock_notify = mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )

        # Act
        response = client.get(f"/api/v1/qr/{test_pet.id}")

        # Assert — successful response
        assert response.status_code == 200

        # Assert — EMERGENCY_SCAN ledger event was created
        statement = select(LedgerEvent).where(
            LedgerEvent.pet_id == test_pet.id,
            LedgerEvent.event_type == "EMERGENCY_SCAN",
        )
        event = session.exec(statement).first()
        assert event is not None, "EMERGENCY_SCAN ledger event was not created"
        assert "QR tag scanned" in event.description

        # Assert — owner notification was called
        mock_notify.assert_called_once_with(test_pet.owner.email, test_pet.breed)


# ---------------------------------------------------------------------------
# Test 4 — QR Page Existing Fields (Req 3.4)
# ---------------------------------------------------------------------------
class TestQRPageExistingFields:
    """
    **Validates: Requirements 3.4**

    The QR endpoint response must contain pet_species, breed, and
    emergency_contact fields. This works on unfixed code.
    """

    @pytest.mark.asyncio
    async def test_qr_response_contains_expected_fields(
        self, client, test_pet, mocker
    ):
        # Arrange — mock email notification
        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )

        # Act
        response = client.get(f"/api/v1/qr/{test_pet.id}")

        # Assert — response contains the expected fields
        assert response.status_code == 200
        data = response.json()
        assert "pet_species" in data, "Response missing 'pet_species' field"
        assert "breed" in data, "Response missing 'breed' field"
        assert "emergency_contact" in data, "Response missing 'emergency_contact' field"

        # Assert — values match the test pet
        assert data["pet_species"] == test_pet.pet_species
        assert data["breed"] == test_pet.breed


# ---------------------------------------------------------------------------
# Test 5 — Cookie Flags Preservation (Req 3.7)
# ---------------------------------------------------------------------------
class TestCookieFlagsPreservation:
    """
    **Validates: Requirements 3.7**

    The paws_user_id cookie must include HttpOnly and SameSite=lax flags.
    This works on unfixed code and must continue after fixes.
    """

    @pytest.mark.asyncio
    async def test_cookie_has_httponly_and_samesite(self, client, session, mocker):
        # Arrange — mock Google auth flow
        mock_token = {
            "access_token": "fake-token",
            "userinfo": {
                "sub": "preserve-cookie-sub",
                "email": "preserve-cookie@example.com",
                "name": "Preserve Cookie User",
            },
        }
        mocker.patch(
            "app.api.v1.auth.google_auth.authorize_access_token",
            return_value=mock_token,
        )
        mocker.patch(
            "app.api.v1.auth.google_auth.get_user_info",
            return_value=mock_token["userinfo"],
        )

        # Act
        response = client.get("/api/v1/auth/callback?code=fake-code&state=fake-state", follow_redirects=False)
        assert response.status_code == 307

        # Inspect raw Set-Cookie header
        set_cookie_headers = response.headers.get_list("set-cookie")
        paws_cookie_header = None
        for header in set_cookie_headers:
            if "paws_user_id" in header:
                paws_cookie_header = header
                break

        assert paws_cookie_header is not None, (
            "paws_user_id cookie not found in Set-Cookie headers"
        )

        # Assert — HttpOnly flag is present
        assert "HttpOnly" in paws_cookie_header, (
            f"Set-Cookie header '{paws_cookie_header}' missing HttpOnly flag"
        )

        # Assert — SameSite=lax is present
        assert "SameSite=lax" in paws_cookie_header, (
            f"Set-Cookie header '{paws_cookie_header}' missing SameSite=lax"
        )


# ---------------------------------------------------------------------------
# Test 6 — Unauthenticated Nudge Absent (Req 3.5)
# ---------------------------------------------------------------------------
class TestUnauthenticatedNudge:
    """
    **Validates: Requirements 3.5**

    The POST /api/v1/nudge/{chip_id} endpoint exists and returns 200 for
    valid pets with owners. The endpoint itself is not gated by auth — the
    UI button visibility is the preservation concern.

    NOTE: UI-layer preservation (no nudge button for unauthenticated users)
    requires NiceGUI integration testing and cannot be verified via the
    FastAPI test client alone.
    """

    @pytest.mark.asyncio
    async def test_nudge_endpoint_returns_200_for_valid_pet(
        self, client, session, mocker
    ):
        # Arrange — create pet with owner
        user = User(
            sub="preserve-nudge-sub",
            email="preserve-nudge@example.com",
            name="Preserve Nudge User",
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        pet = Pet(
            name="NudgePreserveDog",
            chip_id="985000000000088",
            breed="Corgi",
            owner_id=user.id,
            identity_status="VERIFIED",
        )
        session.add(pet)
        session.commit()
        session.refresh(pet)

        # Mock email sending
        mocker.patch(
            "app.api.v1.pets.email_service.send_email",
            new_callable=AsyncMock,
            return_value=True,
        )

        # Act — call nudge endpoint (requires auth now)
        client.cookies.set("paws_user_id", serializer.dumps(str(user.id)))
        response = client.post(f"/api/v1/nudge/{pet.chip_id}")

        # Assert — endpoint works and returns success
        assert response.status_code == 200
        data = response.json()
        assert "alerted" in data["message"].lower() or "notif" in data["message"].lower()


# ---------------------------------------------------------------------------
# Test 7 — AAHA Result Flow (Req 3.6)
# ---------------------------------------------------------------------------
class TestAAHAResultFlow:
    """
    **Validates: Requirements 3.6**

    Looking up a chip starting with '985' that is NOT in the local DB
    should return source="aaha". This works on unfixed code.
    """

    def test_aaha_lookup_returns_aaha_source(self, client):
        # Act — lookup a chip that starts with 985 but is not in local DB
        response = client.get("/api/v1/lookup/985999999999999")

        # Assert — response comes from AAHA
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "aaha", (
            f"Expected source='aaha' but got source='{data['source']}'"
        )
