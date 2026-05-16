"""Tests for app/services/integrations.py — hash, PDF, manufacturer, breed API."""

import os
import pytest
from datetime import datetime
from app.services.integrations import HashService, PDFService, get_manufacturer_from_chip, DogAPIClient


class TestHashService:

    def test_hash_stability(self):
        data = {"name": "Buddy", "type": "Vaccination", "date": "2026-01-01"}
        hash1 = HashService.hash_record(data)
        hash2 = HashService.hash_record(data)
        assert hash1 == hash2

    def test_hash_order_independent(self):
        data = {"name": "Buddy", "type": "Vaccination", "date": "2026-01-01"}
        data_reordered = {"date": "2026-01-01", "name": "Buddy", "type": "Vaccination"}
        assert HashService.hash_record(data) == HashService.hash_record(data_reordered)


class TestPDFService:

    def test_pdf_generation(self):
        from app.models import Vaccination
        vax = [
            Vaccination(
                vaccine_name="Rabies", manufacturer="Zoetis",
                serial_number="123", date_given=datetime(2025, 1, 1),
                expiration_date=datetime(2026, 1, 1),
                administering_vet="Dr. X", clinic_name="Clinic Y",
            )
        ]
        path = PDFService.generate_vaccination_report("Buddy", vax, "test_hash")
        try:
            assert os.path.exists(path)
            assert path.endswith(".pdf")
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestManufacturerLookup:

    def test_known_prefixes(self):
        assert get_manufacturer_from_chip("985123456789012") == "Datamars / HomeAgain"
        assert get_manufacturer_from_chip("977000000000000") == "Trovan"

    def test_unknown_prefix(self):
        assert get_manufacturer_from_chip("111000000000000") == "Generic (111)"

    def test_empty_chip(self):
        assert get_manufacturer_from_chip("") == "Unknown"


class TestDogBreedAPI:

    @pytest.mark.asyncio
    async def test_get_breeds_returns_list(self):
        client = DogAPIClient()
        breeds = await client.get_breeds()
        assert isinstance(breeds, list)
        assert len(breeds) > 50
        assert all("name" in b for b in breeds)

    @pytest.mark.asyncio
    async def test_breeds_are_capitalized(self):
        client = DogAPIClient()
        breeds = await client.get_breeds()
        for b in breeds[:10]:
            assert b["name"][0].isupper()

    @pytest.mark.asyncio
    async def test_search_breed_filters(self):
        client = DogAPIClient()
        results = await client.search_breed("retriever")
        assert len(results) > 0
        assert all("retriever" in b["name"].lower() for b in results)

    @pytest.mark.asyncio
    async def test_search_breed_no_results(self):
        client = DogAPIClient()
        results = await client.search_breed("xyznonexistent")
        assert results == []
