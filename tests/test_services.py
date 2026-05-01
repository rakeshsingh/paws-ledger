import pytest
import os
from app.services.integrations import HashService, PDFService, get_manufacturer_from_chip
from datetime import datetime

def test_hash_stability():
    data = {"name": "Buddy", "type": "Vaccination", "date": "2026-01-01"}
    hash1 = HashService.hash_record(data)
    hash2 = HashService.hash_record(data)
    assert hash1 == hash2
    
    # Different order, same data should have same hash
    data_reordered = {"date": "2026-01-01", "name": "Buddy", "type": "Vaccination"}
    hash3 = HashService.hash_record(data_reordered)
    assert hash1 == hash3

def test_pdf_generation():
    from app.models import Vaccination
    pet_name = "Buddy"
    vax = [
        Vaccination(
            vaccine_name="Rabies", 
            manufacturer="Zoetis", 
            serial_number="123", 
            date_given=datetime.utcnow(),
            expiration_date=datetime.utcnow(),
            administering_vet="Dr. X",
            clinic_name="Clinic Y"
        )
    ]
    path = PDFService.generate_vaccination_report(pet_name, vax, "test_hash")
    assert os.path.exists(path)
    assert path.endswith(".pdf")
    # Clean up
    if os.path.exists(path):
        os.remove(path)

def test_manufacturer_lookup():
    assert get_manufacturer_from_chip("985123456789012") == "Datamars / HomeAgain"
    assert get_manufacturer_from_chip("977000000000000") == "Trovan"
    assert get_manufacturer_from_chip("111000000000000") == "Generic (111)"
    assert get_manufacturer_from_chip("") == "Unknown"
