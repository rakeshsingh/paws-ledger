"""Tests for app/api/v1/pets.py — lookup, QR, nudge, vaccinations, shared access."""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, timedelta
from app.models import User, Pet, Vaccination, SharedAccess
from app.api.v1.routes import serializer


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_client(client, test_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
    return client


# ─────────────────────────────────────────────────────────────
# Chip Lookup
# ─────────────────────────────────────────────────────────────

class TestChipLookup:

    def test_lookup_local(self, client, test_pet):
        response = client.get(f"/api/v1/lookup/{test_pet.chip_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "local"
        assert data["data"]["chip_id"] == test_pet.chip_id
        assert data["data"]["id"] == str(test_pet.id)
        assert data["data"]["breed"] == test_pet.breed

    def test_lookup_aaha_fallback(self, client):
        response = client.get("/api/v1/lookup/985999999999999")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "aaha"

    def test_lookup_not_found(self, client):
        response = client.get("/api/v1/lookup/000000000000000")
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────
# QR Scan
# ─────────────────────────────────────────────────────────────

class TestQRScan:

    def test_qr_notifies_owner(self, client, test_pet, mocker):
        mock_notify = mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )
        response = client.get(f"/api/v1/qr/{test_pet.id}")
        assert response.status_code == 200
        assert "emergency_contact" in response.json()
        mock_notify.assert_called_once()

    def test_qr_includes_vaccination_data(self, client, session, mocker):
        user = User(sub="qr-vax-sub", email="qrvax@example.com", name="QR Vax User")
        session.add(user)
        session.commit()
        session.refresh(user)

        pet = Pet(
            name="VaxBuddy", chip_id="985000000000099", breed="Beagle",
            owner_id=user.id, identity_status="VERIFIED",
        )
        session.add(pet)
        session.commit()
        session.refresh(pet)

        session.add(Vaccination(
            pet_id=pet.id, vaccine_name="Rabies", manufacturer="Zoetis",
            serial_number="RAB-001", date_given=datetime(2024, 6, 1),
            expiration_date=datetime(2025, 6, 1), administering_vet="Dr. Smith",
            clinic_name="Paws Clinic",
        ))
        session.commit()

        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )

        response = client.get(f"/api/v1/qr/{pet.id}")
        assert response.status_code == 200
        data = response.json()
        assert "vaccinations" in data
        assert len(data["vaccinations"]) > 0
        assert data["vaccinations"][0]["vaccine_name"] == "Rabies"

    def test_qr_response_contains_expected_fields(self, client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )
        response = client.get(f"/api/v1/qr/{test_pet.id}")
        assert response.status_code == 200
        data = response.json()
        assert "pet_species" in data
        assert "breed" in data
        assert "emergency_contact" in data
        assert data["pet_species"] == test_pet.pet_species
        assert data["breed"] == test_pet.breed

    def test_qr_scan_creates_ledger_event(self, client, session, test_pet, mocker):
        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )
        client.get(f"/api/v1/qr/{test_pet.id}")

        from sqlmodel import select
        from app.models import LedgerEvent
        event = session.exec(
            select(LedgerEvent).where(
                LedgerEvent.pet_id == test_pet.id,
                LedgerEvent.event_type == "EMERGENCY_SCAN",
            )
        ).first()
        assert event is not None
        assert "QR tag scanned" in event.description


# ─────────────────────────────────────────────────────────────
# Nudge
# ─────────────────────────────────────────────────────────────

class TestNudge:

    def test_nudge_endpoint_callable(self, client, session, mocker):
        user = User(sub="nudge-sub", email="nudge@example.com", name="Nudge User")
        session.add(user)
        session.commit()
        session.refresh(user)

        pet = Pet(
            name="NudgeDog", chip_id="985000000000077", breed="Poodle",
            owner_id=user.id, identity_status="VERIFIED",
        )
        session.add(pet)
        session.commit()
        session.refresh(pet)

        mocker.patch(
            "app.api.v1.pets.email_service.send_email",
            new_callable=AsyncMock, return_value=True,
        )

        client.cookies.set("paws_user_id", serializer.dumps(str(user.id)))
        response = client.post(f"/api/v1/nudge/{pet.chip_id}")

        assert response.status_code == 200
        assert "message" in response.json()


# ─────────────────────────────────────────────────────────────
# Vaccinations
# ─────────────────────────────────────────────────────────────

class TestVaccinations:

    def test_add_vaccination(self, authenticated_client, test_pet):
        vaccination_data = {
            "vaccine_name": "Rabies",
            "manufacturer": "Zoetis",
            "serial_number": "ABC-123",
            "date_given": datetime.utcnow().strftime('%Y-%m-%d'),
            "expiration_date": (datetime.utcnow() + timedelta(days=365)).strftime('%Y-%m-%d'),
            "administering_vet": "Dr. Smith",
            "clinic_name": "Paws Clinic",
        }
        response = authenticated_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations", json=vaccination_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["vaccine_name"] == "Rabies"
        assert data["record_hash"] is not None

    def test_add_vaccination_expiry_before_given_rejected(self, authenticated_client, test_pet):
        vaccination_data = {
            "vaccine_name": "Rabies",
            "date_given": "2025-06-01",
            "expiration_date": "2025-01-01",
        }
        response = authenticated_client.post(
            f"/api/v1/pets/{test_pet.id}/vaccinations", json=vaccination_data
        )
        assert response.status_code == 400
        assert "after" in response.json()["detail"].lower()

    def test_export_requires_auth(self, client, test_pet):
        response = client.get(f"/api/v1/pets/{test_pet.id}/vaccinations/export")
        assert response.status_code == 401

    def test_export_requires_ownership(self, client, session, test_pet):
        other_user = User(sub="other-sub", email="other@example.com", name="Other")
        session.add(other_user)
        session.commit()
        session.refresh(other_user)

        client.cookies.set("paws_user_id", serializer.dumps(str(other_user.id)))
        response = client.get(f"/api/v1/pets/{test_pet.id}/vaccinations/export")
        assert response.status_code == 403


# ─────────────────────────────────────────────────────────────
# Shared Access
# ─────────────────────────────────────────────────────────────

class TestSharedAccess:

    def test_shared_access_heartbeat(self, authenticated_client, test_pet, mocker):
        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_access",
            new_callable=AsyncMock,
        )

        resp = authenticated_client.post(f"/api/v1/pets/{test_pet.id}/shared-access?hours=1")
        assert resp.status_code == 200
        token = resp.json()["access_url"].split("/")[-1]

        resp = authenticated_client.get(f"/api/v1/shared/{token}")
        assert resp.status_code == 200
        assert resp.json()["pet"]["breed"] == test_pet.breed

    def test_shared_access_expired(self, client, test_pet, session):
        access = SharedAccess(
            pet_id=test_pet.id,
            expires_at=datetime.utcnow() - timedelta(hours=1),
        )
        session.add(access)
        session.commit()

        response = client.get(f"/api/v1/shared/{access.token}")
        assert response.status_code == 403
