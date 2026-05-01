from sqlmodel import Session, create_engine, select
from app.models import Pet, User, Vaccination, LedgerEvent, SharedAccess
from app.database import database_url, create_db_and_tables
from datetime import datetime, timedelta, timezone
import uuid

engine = create_engine(database_url)

def seed():
    create_db_and_tables()
    with Session(engine) as session:
        # Check if already seeded
        statement = select(User).where(User.email == "john@example.com")
        user = session.exec(statement).first()
        if user:
            print("Database already seeded.")
            return

        user = User(
            sub="manual|seed_user_john", 
            name="John Doe", 
            email="john@example.com",
            role="Guardian"
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        pet = Pet(
            name="Buddy",
            gender="Male",
            chip_id="985123456789012",
            manufacturer="Datamars / HomeAgain",
            breed="Golden Retriever",
            pet_species="DOG",
            owner_id=user.id,
            identity_status="VERIFIED"
        )
        session.add(pet)
        session.commit()
        session.refresh(pet)
        print(f"Seeded pet {pet.name} with chip_id: {pet.chip_id}")

        # Seed a vaccination
        vaccination = Vaccination(
            pet_id=pet.id,
            vaccine_name="Rabies 3-Year",
            manufacturer="Zoetis",
            serial_number="Z12345-ABC",
            date_given=datetime.now(timezone.utc) - timedelta(days=100),
            expiration_date=datetime.now(timezone.utc) + timedelta(days=900),
            administering_vet="Dr. Smith",
            clinic_name="Paws & Claws Clinic",
            record_hash="mock_hash_for_seed_data"
        )
        session.add(vaccination)
        
        # Log event
        session.add(LedgerEvent(
            pet_id=pet.id,
            event_type="VACCINATION",
            description="Rabies 3-Year vaccination added during seeding"
        ))
        
        # Seed a shared access token
        shared_access = SharedAccess(
            pet_id=pet.id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        session.add(shared_access)
        
        session.commit()
        print(f"Seeded vaccination record and shared access token: {shared_access.token}")

if __name__ == "__main__":
    seed()
