from datetime import datetime
from typing import List, Optional
from uuid import UUID, uuid4
from sqlmodel import Field, SQLModel, Relationship

class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True, unique=True)
    name: str
    role: str = "Guardian"  # Guardian, Caregiver, Vet

    pets: List["Pet"] = Relationship(back_populates="owner")

class Pet(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    chip_id: str = Field(index=True, unique=True, max_length=15)
    manufacturer: Optional[str] = None
    identity_status: str = "UNVERIFIED"  # VERIFIED, UNVERIFIED
    owner_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    pet_species: str = "DOG"
    breed: Optional[str] = None
    dob: Optional[datetime] = None
    
    owner: Optional[User] = Relationship(back_populates="pets")
    ledger_events: List["LedgerEvent"] = Relationship(back_populates="pet")

class LedgerEvent(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    pet_id: UUID = Field(foreign_key="pet.id")
    event_type: str  # VACCINATION, WEIGHT_CHECK, OWNERSHIP_CHANGE, EMERGENCY_SCAN
    description: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    pet: Pet = Relationship(back_populates="ledger_events")
