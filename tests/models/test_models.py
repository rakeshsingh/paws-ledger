"""Tests for app/models.py — data layer, relationships, constraints."""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app.models import User, Pet, PetTag, Vaccination


class TestPetRegistration:

    def test_register_pet_creates_record(self, session, test_user):
        pet = Pet(
            name="NewPet", chip_id="985000000000055", breed="Golden Retriever",
            pet_species="DOG", gender="Male", manufacturer="Datamars / HomeAgain",
            identity_status="VERIFIED", owner_id=test_user.id,
            energy_level="High", feeds_per_day=2, temperament="Friendly and playful",
        )
        session.add(pet)
        session.commit()
        session.refresh(pet)

        assert pet.id is not None
        assert pet.energy_level == "High"
        assert pet.feeds_per_day == 2
        assert pet.temperament == "Friendly and playful"

    def test_register_pet_with_tag(self, session, test_user):
        pet = Pet(
            name="TaggedPet", chip_id="985000000000066", breed="Beagle",
            pet_species="DOG", gender="Female", manufacturer="Datamars / HomeAgain",
            identity_status="VERIFIED", owner_id=test_user.id,
        )
        session.add(pet)
        session.flush()

        tag = PetTag(
            pet_id=pet.id, tag_type="QR", tag_code="REGQR001",
            label="Collar Tag", qr_url="/qr/REGQR001",
        )
        session.add(tag)
        session.commit()
        session.refresh(pet)

        assert len(pet.tags) == 1
        assert pet.tags[0].tag_code == "REGQR001"

    def test_max_five_pets_per_owner(self, session, test_user):
        for i in range(5):
            session.add(Pet(
                name=f"Pet{i}", chip_id=f"98500000000{i:04d}",
                breed="Mixed", pet_species="DOG",
                owner_id=test_user.id, identity_status="VERIFIED",
            ))
        session.commit()
        session.refresh(test_user)
        assert len(test_user.pets) == 5

    def test_chip_id_uniqueness(self, session, test_user):
        session.add(Pet(
            name="First", chip_id="985000000099999", breed="Lab",
            pet_species="DOG", owner_id=test_user.id,
        ))
        session.commit()

        session.add(Pet(
            name="Second", chip_id="985000000099999", breed="Poodle",
            pet_species="DOG", owner_id=test_user.id,
        ))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()


class TestRelationships:

    def test_pet_has_tags_relationship(self, session, test_pet):
        tag = PetTag(
            pet_id=test_pet.id, tag_type="QR", tag_code="RELQR001",
            label="Test Tag", qr_url="/qr/RELQR001", status="ACTIVE",
        )
        session.add(tag)
        session.commit()
        session.refresh(test_pet)
        assert len(test_pet.tags) == 1
        assert test_pet.tags[0].tag_code == "RELQR001"

    def test_pet_has_vaccinations_relationship(self, session, test_pet):
        vax = Vaccination(
            pet_id=test_pet.id, vaccine_name="Rabies", manufacturer="Zoetis",
            serial_number="RAB-001", date_given=datetime(2025, 1, 1),
            expiration_date=datetime(2026, 1, 1),
            administering_vet="Dr. Smith", clinic_name="Paws Clinic",
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


class TestVaccinationData:

    def test_canine_vaccine_names_loaded(self):
        from app.data import get_vaccine_names
        names = get_vaccine_names("DOG")
        assert len(names) > 0
        assert "Rabies" in names
        assert "Canine Distemper Virus (CDV)" in names

    def test_feline_vaccine_names_loaded(self):
        from app.data import get_vaccine_names
        names = get_vaccine_names("CAT")
        assert len(names) > 0
        assert "Rabies" in names
        assert "Feline Panleukopenia Virus (FPV)" in names

    def test_vaccine_details_have_schedule(self):
        from app.data import get_vaccine_details
        details = get_vaccine_details("DOG", "Rabies")
        assert details != {}
        assert "booster" in details
        assert "booster_interval_years" in details
        assert "initial_series" in details
        assert details["category"] == "core"

    def test_vaccine_dropdown_options_formatted(self):
        from app.data import get_vaccine_options_for_dropdown
        options = get_vaccine_options_for_dropdown("DOG")
        assert len(options) > 0
        keys = list(options.keys())
        assert any("[Core]" in k for k in keys)
        assert any("[Noncore]" in k for k in keys)

    def test_unknown_species_returns_empty(self):
        from app.data import get_vaccine_names
        assert get_vaccine_names("BIRD") == []

    def test_unknown_vaccine_returns_empty_dict(self):
        from app.data import get_vaccine_details
        assert get_vaccine_details("DOG", "Nonexistent Vaccine") == {}

    def test_core_only_filter(self):
        from app.data import get_vaccine_names
        core_only = get_vaccine_names("DOG", include_noncore=False)
        all_names = get_vaccine_names("DOG", include_noncore=True)
        assert len(core_only) < len(all_names)
        assert "Bordetella bronchiseptica + Parainfluenza (Kennel Cough)" not in core_only
