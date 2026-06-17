from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, Relationship


def _utc_now() -> datetime:
    """Return current UTC time as a naive datetime (for SQLite compatibility)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

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
    profile_updated_at: Optional[datetime] = None
    contact_reminded_at: Optional[datetime] = None

    pets: List["Pet"] = Relationship(back_populates="owner")
    sent_nudges: List["NudgeSession"] = Relationship(
        back_populates="finder",
        sa_relationship_kwargs={"foreign_keys": "[NudgeSession.finder_id]"},
    )
    subscription: Optional["Subscription"] = Relationship(back_populates="user")

class Pet(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    gender: str = "Unknown" # Male, Female, Unknown
    chip_id: str = Field(index=True, unique=True, max_length=15)  # 9-15 alphanumeric
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
    medication_notes: Optional[str] = None      # Name/dosage/schedule of medications
    emergency_vet_name: Optional[str] = None    # Emergency vet clinic name
    emergency_vet_phone: Optional[str] = None   # Emergency vet phone number
    care_priority: Optional[str] = None         # normal, important, critical — highlights urgency

    # Emergency contact (person)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None

    # Pet clinic
    clinic_name: Optional[str] = None
    clinic_address: Optional[str] = None
    clinic_phone: Optional[str] = None
    
    owner: Optional[User] = Relationship(back_populates="pets")
    ledger_events: List["LedgerEvent"] = Relationship(back_populates="pet")
    vaccinations: List["Vaccination"] = Relationship(back_populates="pet")
    shared_accesses: List["SharedAccess"] = Relationship(back_populates="pet")
    # Location — updated on each tag scan
    last_scan_latitude: Optional[float] = None
    last_scan_longitude: Optional[float] = None
    last_scan_location: Optional[str] = None  # Reverse-geocoded city, country
    last_scan_at: Optional[datetime] = None

    tags: List["PetTag"] = Relationship(back_populates="pet")
    nudge_sessions: List["NudgeSession"] = Relationship(back_populates="pet")
    vaccination_documents: List["VaccinationDocument"] = Relationship(back_populates="pet")
    tag_scans: List["TagScan"] = Relationship(back_populates="pet")

class LedgerEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id")
    event_type: str  # VACCINATION, WEIGHT_CHECK, OWNERSHIP_CHANGE, EMERGENCY_SCAN, HEARTBEAT_ACCESS
    description: str
    timestamp: datetime = Field(default_factory=_utc_now)

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
    created_at: datetime = Field(default_factory=_utc_now)
    last_accessed_at: Optional[datetime] = None
    access_count: int = Field(default=0)

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
    activated_at: datetime = Field(default_factory=_utc_now)
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


class NudgeSession(SQLModel, table=True):
    """Secure nudge record between a finder and a pet owner."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id", index=True)
    finder_id: UUID = Field(foreign_key="user.id", index=True)
    message: str = Field(max_length=500)
    response_token: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=_utc_now)
    expires_at: datetime
    is_resolved: bool = Field(default=False)
    resolved_at: Optional[datetime] = None
    # GPS location shared by finder (Verified tier)
    geo_latitude: Optional[float] = None
    geo_longitude: Optional[float] = None
    # Owner reply (Verified tier)
    owner_response: Optional[str] = None
    responded_at: Optional[datetime] = None
    # Soft-delete flags for per-side deletion
    deleted_by_finder: bool = Field(default=False)
    deleted_by_owner: bool = Field(default=False)

    pet: Pet = Relationship(back_populates="nudge_sessions")
    finder: User = Relationship(
        back_populates="sent_nudges",
        sa_relationship_kwargs={"foreign_keys": "[NudgeSession.finder_id]"},
    )


class Subscription(SQLModel, table=True):
    """Stripe subscription record for a user."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, unique=True)
    stripe_customer_id: str = Field(index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
    tier: str = Field(default="free")  # free, verified, guardian
    status: str = Field(default="inactive")  # active, inactive, past_due, canceled
    cancel_at_period_end: bool = Field(default=False)
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    user: User = Relationship(back_populates="subscription")


class OwnershipTransfer(SQLModel, table=True):
    """Tracks ownership transfers between users."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id", index=True)
    from_owner_id: UUID = Field(foreign_key="user.id")
    to_owner_email: str
    to_owner_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    transfer_token: str = Field(default_factory=lambda: str(uuid4()), index=True, unique=True)
    status: str = Field(default="pending")  # pending, accepted, rejected, expired
    initiated_at: datetime = Field(default_factory=_utc_now)
    completed_at: Optional[datetime] = None
    notes: Optional[str] = None


class VaccinationAlert(SQLModel, table=True):
    """Scheduled vaccination/appointment reminders."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    vaccination_id: Optional[UUID] = Field(default=None, foreign_key="vaccination.id")
    alert_type: str = Field(default="vaccination_expiry")  # vaccination_expiry, appointment
    alert_date: datetime
    title: str
    description: Optional[str] = None
    is_sent: bool = Field(default=False)
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utc_now)


class TagScan(SQLModel, table=True):
    """Records each NFC/QR tag scan with location data."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id", index=True)
    tag_id: Optional[UUID] = Field(default=None, foreign_key="pettag.id")
    scanned_at: datetime = Field(default_factory=_utc_now)
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    accuracy_meters: Optional[float] = None
    city: Optional[str] = None
    country: Optional[str] = None
    scanner_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    scan_method: str = "QR"  # QR, NFC, CHIP_LOOKUP

    pet: Pet = Relationship(back_populates="tag_scans")


class VaccinationDocument(SQLModel, table=True):
    """Uploaded pet document stored in R2."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id", index=True)
    filename: str
    original_filename: str
    content_type: str = "application/pdf"
    file_size: int = 0
    storage_key: str
    url: str
    uploaded_at: datetime = Field(default_factory=_utc_now)
    notes: Optional[str] = None
    document_name: Optional[str] = None
    description: Optional[str] = None

    pet: Pet = Relationship(back_populates="vaccination_documents")


