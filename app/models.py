from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, Relationship

class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    sub: str = Field(index=True, unique=True) # Subject ID from IdP
    email: str = Field(index=True, unique=True)
    address: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    name: str
    role: str = "Guardian"  # Guardian, Caregiver, Vet

    pets: List["Pet"] = Relationship(back_populates="owner")

class Pet(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    gender: str = "Unknown" # Male, Female, Unknown
    chip_id: str = Field(index=True, unique=True, max_length=15)
    manufacturer: Optional[str] = None
    identity_status: str = "UNVERIFIED"  # VERIFIED, UNVERIFIED
    owner_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    pet_species: str = "DOG"
    breed: Optional[str] = None
    dob: Optional[datetime] = None
    photo_url: Optional[str] = None  # Owner-provided profile photo URL

    # Care information
    energy_level: Optional[str] = None          # Low, Moderate, High, Very High
    max_alone_hours: Optional[int] = None       # Max hours the pet can be left alone
    feeds_per_day: Optional[int] = None         # Number of meals per day
    dietary_notes: Optional[str] = None         # Allergies, special diet, preferred food
    exercise_needs: Optional[str] = None        # e.g. "30 min walk twice daily"
    medical_conditions: Optional[str] = None    # Ongoing conditions (e.g. arthritis, diabetes)
    temperament: Optional[str] = None           # e.g. "Friendly with kids, anxious around dogs"
    care_notes: Optional[str] = None            # Free-form observations for caregivers
    
    owner: Optional[User] = Relationship(back_populates="pets")
    ledger_events: List["LedgerEvent"] = Relationship(back_populates="pet")
    vaccinations: List["Vaccination"] = Relationship(back_populates="pet")
    shared_accesses: List["SharedAccess"] = Relationship(back_populates="pet")
    tags: List["PetTag"] = Relationship(back_populates="pet")

class LedgerEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id")
    event_type: str  # VACCINATION, WEIGHT_CHECK, OWNERSHIP_CHANGE, EMERGENCY_SCAN, HEARTBEAT_ACCESS
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    pet: Pet = Relationship(back_populates="ledger_events")

class Vaccination(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id")
    
    vaccine_name: str
    manufacturer: str
    serial_number: str
    lot_number: Optional[str] = None
    date_given: datetime
    expiration_date: datetime
    
    administering_vet: str
    vet_license: Optional[str] = None
    clinic_name: str
    clinic_address: Optional[str] = None
    clinic_phone: Optional[str] = None
    
    # Cryptographic verification
    record_hash: Optional[str] = None # SHA-256 of the record
    
    pet: Pet = Relationship(back_populates="vaccinations")

class SharedAccess(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id")
    token: str = Field(default_factory=lambda: str(uuid4()), index=True, unique=True)
    expires_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    pet: Pet = Relationship(back_populates="shared_accesses")


class PetTag(SQLModel, table=True):
    """Physical NFC or QR tag linked to a pet for quick identification."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id", index=True)

    # Tag identification
    tag_type: str = "QR"                        # QR, NFC, DUAL (both QR + NFC)
    tag_code: str = Field(index=True, unique=True)  # Unique identifier encoded in the tag
    serial_number: Optional[str] = None         # Manufacturer serial number on the physical tag
    manufacturer: Optional[str] = None          # Tag hardware manufacturer

    # Status & lifecycle
    status: str = "ACTIVE"                      # ACTIVE, DEACTIVATED, LOST, REPLACED
    activated_at: datetime = Field(default_factory=datetime.utcnow)
    deactivated_at: Optional[datetime] = None

    # NFC-specific fields
    nfc_uid: Optional[str] = None               # NFC chip UID (hardware-level unique ID)
    nfc_technology: Optional[str] = None        # e.g. NTAG213, NTAG215, NTAG216, Mifare

    # QR-specific fields
    qr_url: Optional[str] = None                # Full URL encoded in the QR code

    # Metadata
    label: Optional[str] = None                 # User-friendly label, e.g. "Collar tag", "Harness tag"
    notes: Optional[str] = None                 # Free-form notes about this tag

    pet: Pet = Relationship(back_populates="tags")
