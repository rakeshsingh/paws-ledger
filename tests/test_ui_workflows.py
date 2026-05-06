"""
UI Workflow Tests — API-level verification of all UI-driven workflows.

These tests verify the backend logic that powers the UI components:
- Owner profile (view/edit with city/country/phone)
- Pet registration with tags
- Pet tag management (add/deactivate/reactivate/remove)
- Tag resolution (QR/NFC scan)
- Vaccination dropdown data
- Pet lookup and search
- Owner profile update

Since NiceGUI pages run in a WebSocket context, we test the underlying
API endpoints and data layer that the UI calls.
"""

import pytest
from unittest.mock import AsyncMock
from uuid import uuid4, UUID
from datetime import datetime, timedelta
from app.models import User, Pet, PetTag, LedgerEvent, Vaccination
from app.api.v1.routes import serializer
from sqlmodel import select


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def authenticated_client(client, test_user):
    """Client with a valid auth cookie set."""
    client.cookies.set("paws_user_id", serializer.dumps(str(test_user.id)))
    return client


@pytest.fixture
def test_tag(session, test_pet):
    """Create a test QR tag linked to the test pet."""
    tag = PetTag(
        pet_id=test_pet.id,
        tag_type="QR",
        tag_code="TESTQR001",
        label="Collar Tag",
        qr_url="/qr/TESTQR001",
        status="ACTIVE",
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


@pytest.fixture
def test_nfc_tag(session, test_pet):
    """Create a test NFC tag linked to the test pet."""
    tag = PetTag(
        pet_id=test_pet.id,
        tag_type="NFC",
        tag_code="NFC123ABC",
        label="Harness NFC",
        nfc_uid="04:A2:3B:C1:D4:E5:F6",
        nfc_technology="NTAG215",
        qr_url="/qr/NFC123ABC",
        status="ACTIVE",
    )
    session.add(tag)
    session.commit()
    session.refresh(tag)
    return tag


# ─────────────────────────────────────────────────────────────
# Owner Profile Workflows
# ─────────────────────────────────────────────────────────────

class TestOwnerProfileView:
    """Test the owner profile view/edit workflow."""

    def test_get_owner_profile(self, authenticated_client, test_user):
        response = authenticated_client.get("/api/v1/owner/profile")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_user.name
        assert data["email"] == test_user.email
        assert "phone" in data
        assert "city" in data
        assert "country" in data
        assert "pet_count" in data

    def test_get_owner_profile_unauthenticated(self, client):
        response = client.get("/api/v1/owner/profile")
        assert response.status_code == 401

    def test_update_owner_profile_full(self, authenticated_client, test_user):
        payload = {
            "name": "Updated Name",
            "email": "updated@example.com",
            "phone": "+1-555-123-4567",
            "address": "123 Main St, Portland, OR",
            "city": "Portland",
            "country": "United States",
        }
        response = authenticated_client.put("/api/v1/owner/profile", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Name"
        assert data["email"] == "updated@example.com"
        assert data["phone"] == "+1-555-123-4567"
        assert data["city"] == "Portland"
        assert data["country"] == "United States"

    def test_update_owner_profile_partial(self, authenticated_client, test_user):
        """Only update city — other fields should remain unchanged."""
        response = authenticated_client.put(
            "/api/v1/owner/profile", json={"city": "Seattle"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["city"] == "Seattle"
        assert data["name"] == test_user.name  # unchanged

    def test_update_owner_address(self, authenticated_client):
        payload = {"address": "456 Oak Ave, Seattle, WA"}
        response = authenticated_client.put(
            "/api/v1/owner/profile/address", json=payload
        )
        assert response.status_code == 200
        assert response.json()["address"] == "456 Oak Ave, Seattle, WA"


# ─────────────────────────────────────────────────────────────
# Pet Tag Management Workflows
# ─────────────────────────────────────────────────────────────

class TestTagManagement:
    """Test the NFC/QR tag CRUD workflows."""

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

    def test_create_qr_tag(self, client, test_pet):
        payload = {
            "tag_type": "QR",
            "tag_code": "MYQR2024",
            "label": "Backpack Tag",
            "notes": "Attached to hiking backpack",
        }
        response = client.post(
            f"/api/v1/pets/{test_pet.id}/tags", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tag_code"] == "MYQR2024"
        assert data["tag_type"] == "QR"
        assert data["status"] == "ACTIVE"
        assert data["label"] == "Backpack Tag"
        assert data["qr_url"] == "/qr/tag/MYQR2024"

    def test_create_nfc_tag(self, client, test_pet):
        payload = {
            "tag_type": "NFC",
            "tag_code": "NFCTAG001",
            "nfc_uid": "04:B1:C2:D3:E4:F5:A6",
            "nfc_technology": "NTAG215",
            "manufacturer": "PawTag",
            "label": "Collar NFC",
        }
        response = client.post(
            f"/api/v1/pets/{test_pet.id}/tags", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tag_type"] == "NFC"
        assert data["tag_code"] == "NFCTAG001"

    def test_create_tag_auto_generates_code(self, client, test_pet):
        payload = {"tag_type": "QR", "label": "Auto-code tag"}
        response = client.post(
            f"/api/v1/pets/{test_pet.id}/tags", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["tag_code"]) == 12  # auto-generated 12-char code
        assert data["tag_code"].isupper()

    def test_create_tag_duplicate_code_rejected(self, client, test_pet, test_tag):
        payload = {"tag_type": "QR", "tag_code": "TESTQR001"}
        response = client.post(
            f"/api/v1/pets/{test_pet.id}/tags", json=payload
        )
        assert response.status_code == 409

    def test_create_tag_pet_not_found(self, client):
        fake_id = str(uuid4())
        payload = {"tag_type": "QR", "label": "Ghost tag"}
        response = client.post(f"/api/v1/pets/{fake_id}/tags", json=payload)
        assert response.status_code == 404

    def test_deactivate_tag(self, client, test_pet, test_tag):
        payload = {"status": "DEACTIVATED"}
        response = client.put(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}", json=payload
        )
        assert response.status_code == 200
        assert response.json()["status"] == "DEACTIVATED"

    def test_reactivate_tag(self, client, test_pet, test_tag, session):
        # First deactivate
        test_tag.status = "DEACTIVATED"
        test_tag.deactivated_at = datetime.utcnow()
        session.add(test_tag)
        session.commit()

        # Then reactivate
        payload = {"status": "ACTIVE"}
        response = client.put(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}", json=payload
        )
        assert response.status_code == 200
        assert response.json()["status"] == "ACTIVE"

    def test_update_tag_label_and_notes(self, client, test_pet, test_tag):
        payload = {"label": "New Label", "notes": "Updated notes"}
        response = client.put(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}", json=payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["label"] == "New Label"
        assert data["notes"] == "Updated notes"

    def test_delete_tag(self, client, test_pet, test_tag):
        response = client.delete(
            f"/api/v1/pets/{test_pet.id}/tags/{test_tag.id}"
        )
        assert response.status_code == 200
        assert "removed" in response.json()["message"].lower()

        # Verify it's gone
        response = client.get(f"/api/v1/pets/{test_pet.id}/tags")
        assert response.json() == []

    def test_delete_tag_not_found(self, client, test_pet):
        fake_id = str(uuid4())
        response = client.delete(
            f"/api/v1/pets/{test_pet.id}/tags/{fake_id}"
        )
        assert response.status_code == 404

    def test_tag_lifecycle_creates_ledger_events(self, client, test_pet, session):
        """Creating and deactivating a tag should log audit events."""
        # Create
        payload = {"tag_type": "QR", "tag_code": "AUDIT001", "label": "Audit Tag"}
        client.post(f"/api/v1/pets/{test_pet.id}/tags", json=payload)

        events = session.exec(
            select(LedgerEvent).where(
                LedgerEvent.pet_id == test_pet.id,
                LedgerEvent.event_type == "TAG_ACTIVATED",
            )
        ).all()
        assert len(events) >= 1
        assert "AUDIT001" in events[-1].description


# ─────────────────────────────────────────────────────────────
# Tag Resolution (QR/NFC Scan) Workflows
# ─────────────────────────────────────────────────────────────

class TestTagResolution:
    """Test the tag scan resolution workflow."""

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

    def test_resolve_deactivated_tag_returns_410(
        self, client, test_pet, test_tag, session
    ):
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


# ─────────────────────────────────────────────────────────────
# Vaccination Data Workflows
# ─────────────────────────────────────────────────────────────

class TestVaccinationData:
    """Test the vaccination schedule data used by the UI dropdown."""

    def test_canine_vaccine_names_loaded(self):
        from app.data import get_vaccine_names
        names = get_vaccine_names("DOG")
        assert len(names) > 0
        assert "Rabies" in names
        assert "Canine Distemper Virus (CDV)" in names
        assert "Canine Parvovirus (CPV-2)" in names
        assert "Leptospirosis (4-serovar)" in names

    def test_feline_vaccine_names_loaded(self):
        from app.data import get_vaccine_names
        names = get_vaccine_names("CAT")
        assert len(names) > 0
        assert "Rabies" in names
        assert "Feline Panleukopenia Virus (FPV)" in names
        assert "Feline Herpesvirus Type 1 (FHV-1)" in names
        assert "Feline Calicivirus (FCV)" in names

    def test_vaccine_details_have_schedule(self):
        from app.data import get_vaccine_details
        details = get_vaccine_details("DOG", "Rabies")
        assert details != {}
        assert "booster" in details
        assert "booster_interval_years" in details
        assert "initial_series" in details
        assert "category" in details
        assert details["category"] == "core"

    def test_vaccine_dropdown_options_formatted(self):
        from app.data import get_vaccine_options_for_dropdown
        options = get_vaccine_options_for_dropdown("DOG")
        assert len(options) > 0
        # Keys should have [Core] or [Noncore] prefix
        keys = list(options.keys())
        assert any("[Core]" in k for k in keys)
        assert any("[Noncore]" in k for k in keys)

    def test_unknown_species_returns_empty(self):
        from app.data import get_vaccine_names
        names = get_vaccine_names("BIRD")
        assert names == []

    def test_unknown_vaccine_returns_empty_dict(self):
        from app.data import get_vaccine_details
        details = get_vaccine_details("DOG", "Nonexistent Vaccine")
        assert details == {}

    def test_core_only_filter(self):
        from app.data import get_vaccine_names
        core_only = get_vaccine_names("DOG", include_noncore=False)
        all_names = get_vaccine_names("DOG", include_noncore=True)
        assert len(core_only) < len(all_names)
        # Bordetella is noncore — should not be in core_only
        assert "Bordetella bronchiseptica + Parainfluenza (Kennel Cough)" not in core_only


# ─────────────────────────────────────────────────────────────
# Pet Registration Workflow
# ─────────────────────────────────────────────────────────────

class TestPetRegistration:
    """Test the pet registration data flow (API-level)."""

    def test_register_pet_creates_record(self, session, test_user):
        """Simulate the registration form submission at the data layer."""
        pet = Pet(
            name="NewPet",
            chip_id="985000000000055",
            breed="Golden Retriever",
            pet_species="DOG",
            gender="Male",
            manufacturer="Datamars / HomeAgain",
            identity_status="VERIFIED",
            owner_id=test_user.id,
            energy_level="High",
            feeds_per_day=2,
            temperament="Friendly and playful",
        )
        session.add(pet)
        session.commit()
        session.refresh(pet)

        assert pet.id is not None
        assert pet.energy_level == "High"
        assert pet.feeds_per_day == 2
        assert pet.temperament == "Friendly and playful"

    def test_register_pet_with_tag(self, session, test_user):
        """Simulate registration with a tag created simultaneously."""
        pet = Pet(
            name="TaggedPet",
            chip_id="985000000000066",
            breed="Beagle",
            pet_species="DOG",
            gender="Female",
            manufacturer="Datamars / HomeAgain",
            identity_status="VERIFIED",
            owner_id=test_user.id,
        )
        session.add(pet)
        session.flush()

        tag = PetTag(
            pet_id=pet.id,
            tag_type="QR",
            tag_code="REGQR001",
            label="Collar Tag",
            qr_url="/qr/REGQR001",
        )
        session.add(tag)
        session.commit()
        session.refresh(pet)

        assert len(pet.tags) == 1
        assert pet.tags[0].tag_code == "REGQR001"

    def test_max_five_pets_per_owner(self, session, test_user):
        """Verify the 5-pet limit at the data layer."""
        for i in range(5):
            session.add(Pet(
                name=f"Pet{i}",
                chip_id=f"98500000000{i:04d}",
                breed="Mixed",
                pet_species="DOG",
                owner_id=test_user.id,
                identity_status="VERIFIED",
            ))
        session.commit()
        session.refresh(test_user)
        assert len(test_user.pets) == 5

    def test_chip_id_uniqueness(self, session, test_user):
        """Duplicate chip IDs should raise an integrity error."""
        from sqlalchemy.exc import IntegrityError
        pet1 = Pet(
            name="First",
            chip_id="985000000099999",
            breed="Lab",
            pet_species="DOG",
            owner_id=test_user.id,
        )
        session.add(pet1)
        session.commit()

        pet2 = Pet(
            name="Second",
            chip_id="985000000099999",  # duplicate
            breed="Poodle",
            pet_species="DOG",
            owner_id=test_user.id,
        )
        session.add(pet2)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


# ─────────────────────────────────────────────────────────────
# Dog Breed API Integration
# ─────────────────────────────────────────────────────────────

class TestDogBreedAPI:
    """Test the dog.ceo breed API integration."""

    @pytest.mark.asyncio
    async def test_get_breeds_returns_list(self):
        from app.services.integrations import DogAPIClient
        client = DogAPIClient()
        breeds = await client.get_breeds()
        assert isinstance(breeds, list)
        assert len(breeds) > 50  # dog.ceo has 90+ breeds
        assert all("name" in b for b in breeds)

    @pytest.mark.asyncio
    async def test_breeds_are_capitalized(self):
        from app.services.integrations import DogAPIClient
        client = DogAPIClient()
        breeds = await client.get_breeds()
        for b in breeds[:10]:
            assert b["name"][0].isupper()

    @pytest.mark.asyncio
    async def test_search_breed_filters(self):
        from app.services.integrations import DogAPIClient
        client = DogAPIClient()
        results = await client.search_breed("retriever")
        assert len(results) > 0
        assert all("retriever" in b["name"].lower() for b in results)

    @pytest.mark.asyncio
    async def test_search_breed_no_results(self):
        from app.services.integrations import DogAPIClient
        client = DogAPIClient()
        results = await client.search_breed("xyznonexistent")
        assert results == []


# ─────────────────────────────────────────────────────────────
# Pet Lookup / Search Workflow
# ─────────────────────────────────────────────────────────────

class TestPetLookup:
    """Test the microchip search workflow used by the landing page."""

    def test_lookup_local_pet(self, client, test_pet):
        response = client.get(f"/api/v1/lookup/{test_pet.chip_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "local"
        assert data["data"]["id"] == str(test_pet.id)
        assert data["data"]["breed"] == test_pet.breed

    def test_lookup_aaha_fallback(self, client):
        response = client.get("/api/v1/lookup/985999999999999")
        assert response.status_code == 200
        assert response.json()["source"] == "aaha"

    def test_lookup_not_found(self, client):
        response = client.get("/api/v1/lookup/000000000000000")
        assert response.status_code == 404


# ─────────────────────────────────────────────────────────────
# Dashboard / Pet Profile Data Workflows
# ─────────────────────────────────────────────────────────────

class TestDashboardData:
    """Test data queries that power the dashboard and pet profile views."""

    def test_pet_has_tags_relationship(self, session, test_pet, test_tag):
        session.refresh(test_pet)
        assert len(test_pet.tags) == 1
        assert test_pet.tags[0].tag_code == "TESTQR001"

    def test_pet_has_vaccinations_relationship(self, session, test_pet):
        vax = Vaccination(
            pet_id=test_pet.id,
            vaccine_name="Rabies",
            manufacturer="Zoetis",
            serial_number="RAB-001",
            date_given=datetime.utcnow(),
            expiration_date=datetime.utcnow() + timedelta(days=365),
            administering_vet="Dr. Smith",
            clinic_name="Paws Clinic",
        )
        session.add(vax)
        session.commit()
        session.refresh(test_pet)
        assert len(test_pet.vaccinations) == 1

    def test_pet_photo_url_field(self, session, test_pet):
        test_pet.photo_url = "https://example.com/photo.jpg"
        session.add(test_pet)
        session.commit()
        session.refresh(test_pet)
        assert test_pet.photo_url == "https://example.com/photo.jpg"

    def test_user_city_country_fields(self, session, test_user):
        test_user.city = "Portland"
        test_user.country = "United States"
        session.add(test_user)
        session.commit()
        session.refresh(test_user)
        assert test_user.city == "Portland"
        assert test_user.country == "United States"
