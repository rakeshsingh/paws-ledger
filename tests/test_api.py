import pytest
from uuid import uuid4
from datetime import datetime, timedelta

def test_lookup_local(client, test_pet):
    response = client.get(f"/api/v1/lookup/{test_pet.chip_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "local"
    assert data["data"]["chip_id"] == test_pet.chip_id

def test_lookup_aaha_mock(client):
    # AAHAClient mock in integrations.py returns found if chip starts with 985
    # But if it's not in local DB, it returns source: aaha
    response = client.get("/api/v1/lookup/985999999999999")
    assert response.status_code == 200
    assert response.json()["source"] == "aaha"

def test_lookup_not_found(client):
    response = client.get("/api/v1/lookup/000000000000000")
    assert response.status_code == 404

def test_resolve_qr_notifies_owner(client, test_pet, mocker):
    mock_notify = mocker.patch("app.api.v1.pets.email_service.notify_owner_of_scan")
    response = client.get(f"/api/v1/qr/{test_pet.id}")
    assert response.status_code == 200
    assert "emergency_contact" in response.json()
    mock_notify.assert_called_once()

def test_add_vaccination(client, test_pet):
    vaccination_data = {
        "vaccine_name": "Rabies",
        "manufacturer": "Zoetis",
        "serial_number": "ABC-123",
        "date_given": datetime.utcnow().isoformat(),
        "expiration_date": (datetime.utcnow() + timedelta(days=365)).isoformat(),
        "administering_vet": "Dr. Smith",
        "clinic_name": "Paws Clinic"
    }
    response = client.post(f"/api/v1/pets/{test_pet.id}/vaccinations", json=vaccination_data)
    assert response.status_code == 200
    data = response.json()
    assert data["vaccine_name"] == "Rabies"
    assert data["record_hash"] is not None

def test_shared_access_heartbeat(client, test_pet, mocker):
    mock_notify = mocker.patch("app.api.v1.pets.email_service.notify_owner_of_access")
    
    # 1. Create access
    resp = client.post(f"/api/v1/pets/{test_pet.id}/shared-access?hours=1")
    token = resp.json()["access_url"].split("/")[-1]
    
    # 2. Use access
    resp = client.get(f"/api/v1/shared/{token}")
    assert resp.status_code == 200
    assert resp.json()["pet"]["breed"] == test_pet.breed
    mock_notify.assert_called_once()

def test_shared_access_expired(client, test_pet, session):
    from app.models import SharedAccess
    # Manually create expired access
    access = SharedAccess(
        pet_id=test_pet.id,
        expires_at=datetime.utcnow() - timedelta(hours=1)
    )
    session.add(access)
    session.commit()
    
    response = client.get(f"/api/v1/shared/{access.token}")
    assert response.status_code == 403
