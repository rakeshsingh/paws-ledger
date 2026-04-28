from sqlmodel import Session, create_engine
from app.models import Pet, User
from app.database import sqlite_url
import uuid

engine = create_engine(sqlite_url)

def seed():
    with Session(engine) as session:
        # Check if already seeded
        if session.query(Pet).first():
            print("Database already seeded.")
            return

        user = User(name="John Doe", email="john@example.com")
        session.add(user)
        session.commit()
        session.refresh(user)

        pet = Pet(
            chip_id="985123456789012",
            manufacturer="Datamars / HomeAgain",
            breed="Golden Retriever",
            pet_species="DOG",
            owner_id=user.id,
            identity_status="VERIFIED"
        )
        session.add(pet)
        session.commit()
        print(f"Seeded pet with chip_id: {pet.chip_id}")

if __name__ == "__main__":
    seed()
