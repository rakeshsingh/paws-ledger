"""Tests for the Secure Nudge API endpoint."""

import pytest
from unittest.mock import AsyncMock
from sqlmodel import Session, select
from app.models import User, Pet, NudgeSession, LedgerEvent
from app.api.v1.common import serializer


@pytest.fixture
def finder_user(session: Session):
    user = User(sub="finder_sub", email="finder@example.com", name="Finder User")
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def authenticated_finder(client, finder_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(finder_user.id)))
    return client


@pytest.fixture
def orphan_pet(session: Session):
    pet = Pet(
        name="Stray", chip_id="985000000000099", breed="Mixed",
        owner_id=None, identity_status="UNVERIFIED",
    )
    session.add(pet)
    session.commit()
    session.refresh(pet)
    return pet


class TestSecureNudge:

    def test_nudge_requires_auth(self, client, test_pet):
        response = client.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "I found your dog in the park!"},
        )
        assert response.status_code == 401

    def test_nudge_valid_message(self, authenticated_finder, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.nudge.email_service.send_nudge_alert",
            new_callable=AsyncMock, return_value=True,
        )
        response = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "I found your dog in Central Park near the fountain."},
        )
        assert response.status_code == 200
        assert "nudge has been sent" in response.json()["message"]

        nudge = session.exec(select(NudgeSession)).first()
        assert nudge is not None
        assert nudge.pet_id == test_pet.id
        assert nudge.response_token is not None
        assert len(nudge.response_token) > 0

    def test_nudge_message_too_short(self, authenticated_finder, test_pet):
        response = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "Hi"},
        )
        assert response.status_code == 422

    def test_nudge_message_too_long(self, authenticated_finder, test_pet):
        response = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "x" * 501},
        )
        assert response.status_code == 422

    def test_nudge_self_rejected(self, client, test_user, test_pet):
        client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
        response = client.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "Trying to nudge my own pet."},
        )
        assert response.status_code == 409
        assert "cannot nudge yourself" in response.json()["detail"].lower()

    def test_nudge_orphan_pet(self, authenticated_finder, orphan_pet):
        response = authenticated_finder.post(
            f"/api/v1/nudge/{orphan_pet.chip_id}",
            json={"message": "Found this pet but no owner registered."},
        )
        assert response.status_code == 409
        assert "no registered owner" in response.json()["detail"]

    def test_nudge_pet_not_found(self, authenticated_finder):
        response = authenticated_finder.post(
            "/api/v1/nudge/999999999999999",
            json={"message": "Looking for a pet that doesn't exist."},
        )
        assert response.status_code == 404

    def test_nudge_rate_limit_enforced(self, authenticated_finder, test_pet, mocker):
        mocker.patch(
            "app.api.v1.nudge.email_service.send_nudge_alert",
            new_callable=AsyncMock, return_value=True,
        )
        for i in range(3):
            resp = authenticated_finder.post(
                f"/api/v1/nudge/{test_pet.chip_id}",
                json={"message": f"Nudge attempt number {i + 1} with enough chars."},
            )
            assert resp.status_code == 200

        resp = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "This fourth nudge should be rate limited."},
        )
        assert resp.status_code == 429
        assert "3 nudges" in resp.json()["detail"]

    def test_nudge_sanitizes_html(self, authenticated_finder, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.nudge.email_service.send_nudge_alert",
            new_callable=AsyncMock, return_value=True,
        )
        response = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "<script>alert('xss')</script>I found your dog"},
        )
        assert response.status_code == 200

        nudge = session.exec(select(NudgeSession)).first()
        assert "<script>" not in nudge.message
        assert "&lt;script&gt;" not in nudge.message or "alert" in nudge.message

    def test_nudge_email_failure_no_record(self, authenticated_finder, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.nudge.email_service.send_nudge_alert",
            new_callable=AsyncMock, return_value=False,
        )
        response = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "I found your dog but email will fail."},
        )
        assert response.status_code == 502
        assert "Unable to deliver" in response.json()["detail"]

        nudge = session.exec(select(NudgeSession)).first()
        assert nudge is None

    def test_nudge_creates_ledger_event(self, authenticated_finder, test_pet, session, mocker):
        mocker.patch(
            "app.api.v1.nudge.email_service.send_nudge_alert",
            new_callable=AsyncMock, return_value=True,
        )
        authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "Found your dog near the bus stop on Oak Street."},
        )
        event = session.exec(
            select(LedgerEvent).where(LedgerEvent.event_type == "NUDGE_SENT")
        ).first()
        assert event is not None
        assert event.pet_id == test_pet.id

    def test_nudge_hides_owner_pii_in_response(self, authenticated_finder, test_pet, mocker):
        mocker.patch(
            "app.api.v1.nudge.email_service.send_nudge_alert",
            new_callable=AsyncMock, return_value=True,
        )
        response = authenticated_finder.post(
            f"/api/v1/nudge/{test_pet.chip_id}",
            json={"message": "Found your pet in the neighborhood park."},
        )
        body = response.json()
        assert "test@example.com" not in str(body)
        assert "Test User" not in str(body)
