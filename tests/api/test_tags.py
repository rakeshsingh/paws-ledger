"""Tests for app/api/v1/pets.py — tag management and resolution endpoints."""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from datetime import datetime, UTC
from app.models import User, Pet, PetTag, LedgerEvent
from app.api.v1.routes import serializer
from sqlmodel import select


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_client(client, test_user):
    client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
    return client


@pytest.fixture
def test_tag(session, test_pet):
    tag = PetTag(
        pet_id=test_pet.id, tag_type="QR", tag_code="TESTQR001",
        label="Collar Tag", qr_url="/qr/TESTQR001", status="ACTIVE",
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


@pytest.fixture
def test_nfc_tag(session, test_pet):
    tag = PetTag(
        pet_id=test_pet.id, tag_type="NFC", tag_code="NFC123ABC",
        label="Harness NFC", nfc_uid="04:A2:3B:C1:D4:E5:F6",
        nfc_technology="NTAG215", qr_url="/qr/NFC123ABC", status="ACTIVE",
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


# ─────────────────────────────────────────────────────────────
# Tag CRUD
# ─────────────────────────────────────────────────────────────

class TestTagManagement:

    def test_list_tags_empty(self, client, test_pet):
        response = client.get(f"/api/v1/pets/{test_pet.id}/tags")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_tags_with_data(self, client, test_pet, test_tag):
        response = client.get(f"/api/v1/pets/{test_pet.id}/tags")
        assert response.status_code == 200
        tags = response.json()
        assert len(tags) == 1
        assert tags[0]["tag_code"] == "TESTQR001"
        assert tags[0]["tag_type"] == "QR"
        assert tags[0]["status"] == "ACTIVE"
        assert tags[0]["label"] == "Collar Tag"

    def test_create_qr_tag(self, authenticated_client, test_pet):
        payload = {
            "tag_type": "QR", "tag_code": "MYQR2024",
            "label": "Backpack Tag", "notes": "Attached to hiking backpack",
        }
        response = authenticated_client.post(f"/api/v1/pets/{test_pet.id}/tags", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tag_code"] == "MYQR2024"
        assert data["tag_type"] == "QR"
        assert data["status"] == "ACTIVE"
        assert data["label"] == "Backpack Tag"
        assert data["qr_url"] == "/qr/tag/MYQR2024"

    def test_create_nfc_tag(self, authenticated_client, test_pet):
        payload = {
            "tag_type": "NFC", "tag_code": "NFCTAG001",
            "nfc_uid": "04:B1:C2:D3:E4:F5:A6", "nfc_technology": "NTAG215",
            "manufacturer": "PawTag", "label": "Collar NFC",
        }
        response = authenticated_client.post(f"/api/v1/pets/{test_pet.id}/tags", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["tag_type"] == "NFC"
        assert data["tag_code"] == "NFCTAG001"

    def test_create_tag_auto_generates_code(self, authenticated_client, test_pet):
        payload = {"tag_type": "QR", "label": "Auto-code tag"}
        response = authenticated_client.post(f"/api/v1/pets/{test_pet.id}/tags", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert len(data["tag_code"]) == 12
        assert data["tag_code"].isupper()

    def test_create_tag_duplicate_code_rejected(self, authenticated_client, test_pet, test_tag):
        payload = {"tag_type": "QR", "tag_code": "TESTQR001"}
        response = authenticated_client.post(f"/api/v1/pets/{test_pet.id}/tags", json=payload)
        assert response.status_code == 409

    def test_create_tag_pet_not_found(self, authenticated_client):
        fake_id = str(uuid4())
        payload = {"tag_type": "QR", "label": "Ghost tag"}
        response = authenticated_client.post(f"/api/v1/pets/{fake_id}/tags", json=payload)
        assert response.status_code == 404

    def test_deactivate_tag(self, authenticated_client, test_pet, test_tag):
        payload = {"status": "DEACTIVATED"}
        response = authenticated_client.put(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}", json=payload
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DEACTIVATED"

    def test_reactivate_tag(self, authenticated_client, test_pet, test_tag, session):
        test_tag.status = "DEACTIVATED"
        test_tag.deactivated_at = datetime.now(UTC)
        session.add(test_tag)
        session.commit()

        payload = {"status": "ACTIVE"}
        response = authenticated_client.put(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}", json=payload
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ACTIVE"

    def test_update_tag_label_and_notes(self, authenticated_client, test_pet, test_tag):
        payload = {"label": "New Label", "notes": "Updated notes"}
        response = authenticated_client.put(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "New Label"
        assert data["notes"] == "Updated notes"

    def test_delete_tag(self, authenticated_client, test_pet, test_tag):
        response = authenticated_client.delete(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}"
        )
        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

        response = authenticated_client.get(f"/api/v1/pets/{test_pet.id}/tags")
        assert response.json() == []

    def test_delete_tag_not_found(self, authenticated_client, test_pet):
        fake_id = str(uuid4())
        response = authenticated_client.delete(f"/api/v1/pets/{test_pet.id}/tags/{fake_id}")
        assert response.status_code == 404

    def test_tag_lifecycle_creates_ledger_events(self, authenticated_client, test_pet, session):
        payload = {"tag_type": "QR", "tag_code": "AUDIT001", "label": "Audit Tag"}
        authenticated_client.post(f"/api/v1/pets/{test_pet.id}/tags", json=payload)

        events = session.exec(
            select(LedgerEvent).where(
                LedgerEvent.pet_id == test_pet.id,
                LedgerEvent.event_type == "TAG_ACTIVATED",
            )
        ).all()
        assert len(events) >= 1
        assert "AUDIT001" in events[-1].description


# ─────────────────────────────────────────────────────────────
# Tag Resolution (QR/NFC scan — public)
# ─────────────────────────────────────────────────────────────

class TestTagResolution:

    def test_resolve_active_tag(self, client, test_pet, test_tag, mocker):
        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )
        response = client.get(f"/api/v1/qr/tag/{test_tag.tag_code}")
        assert response.status_code == 200
        data = response.json()
        assert data["pet_id"] == str(test_pet.id)
        assert data["pet_species"] == test_pet.pet_species
        assert data["breed"] == test_pet.breed
        assert data["tag_type"] == "QR"
        assert data["profile_url"] == f"/pet/{test_pet.id}"

    def test_resolve_deactivated_tag_returns_410(self, client, test_pet, test_tag, session):
        test_tag.status = "DEACTIVATED"
        session.add(test_tag)
        session.commit()

        response = client.get(f"/api/v1/qr/tag/{test_tag.tag_code}")
        assert response.status_code == 410

    def test_resolve_unknown_tag_returns_404(self, client):
        response = client.get("/api/v1/qr/tag/NONEXISTENT")
        assert response.status_code == 404

    def test_tag_scan_logs_event(self, client, test_pet, test_tag, session, mocker):
        mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )
        client.get(f"/api/v1/qr/tag/{test_tag.tag_code}")

        events = session.exec(
            select(LedgerEvent).where(
                LedgerEvent.pet_id == test_pet.id,
                LedgerEvent.event_type == "EMERGENCY_SCAN",
            )
        ).all()
        assert len(events) >= 1
        assert test_tag.tag_code in events[-1].description

    def test_tag_scan_notifies_owner(self, client, test_pet, test_tag, mocker):
        mock_notify = mocker.patch(
            "app.api.v1.pets.email_service.notify_owner_of_scan",
            new_callable=AsyncMock,
        )
        client.get(f"/api/v1/qr/tag/{test_tag.tag_code}")
        mock_notify.assert_called_once()
