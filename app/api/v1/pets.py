"""Pet routes — lookup, QR, nudge, transfer, vaccinations, shared access."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from ...database import get_session
from ...models import Pet, LedgerEvent, Vaccination, SharedAccess
from .common import aaha_client, email_service, hash_service, pdf_service
from uuid import UUID
from datetime import datetime, timedelta

router = APIRouter()


@router.get("/lookup/{chip_id}")
async def lookup_pet(chip_id: str, session: Session = Depends(get_session)):
    # 1. Check local database
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()

    if pet:
        return {
            "source": "local",
            "data": {
                "id": str(pet.id),
                "chip_id": pet.chip_id,
                "pet_species": pet.pet_species,
                "breed": pet.breed,
                "manufacturer": pet.manufacturer,
                "identity_status": pet.identity_status,
            },
            "message": "Pet found in PawsLedger registry."
        }

    # 2. If not found locally, trigger AAHA meta-search
    aaha_data = await aaha_client.lookup(chip_id)
    if aaha_data:
        return {
            "source": "aaha",
            "data": aaha_data,
            "message": "Pet found in Nationwide AAHA Network."
        }

    raise HTTPException(status_code=404, detail="Chip ID not found in any registry.")


@router.get("/qr/{tag_id}")
async def resolve_qr(tag_id: str, session: Session = Depends(get_session)):
    try:
        pet_id = UUID(tag_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid Tag ID format")

    statement = select(Pet).where(Pet.id == pet_id)
    pet = session.exec(statement).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # Log the scan event
    event = LedgerEvent(
        pet_id=pet.id,
        event_type="EMERGENCY_SCAN",
        description="Public QR tag scanned"
    )
    session.add(event)
    session.commit()

    # Notify owner if email is available
    if pet.owner and pet.owner.email:
        await email_service.notify_owner_of_scan(pet.owner.email, pet.breed or "Pet")

    return {
        "pet_species": pet.pet_species,
        "breed": pet.breed,
        "identity_status": pet.identity_status,
        "emergency_contact": "Contact info obfuscated (PawsLedger notified owner)",
        "vaccinations": [
            {"vaccine_name": v.vaccine_name, "date_given": str(v.date_given.date())}
            for v in pet.vaccinations
        ]
    }


@router.post("/ledger/transfer")
async def transfer_ownership(chip_id: str, new_owner_email: str, session: Session = Depends(get_session)):
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    return {"message": f"Transfer of {chip_id} to {new_owner_email} initiated."}


@router.post("/pets/{pet_id}/vaccinations")
async def add_vaccination(pet_id: UUID, vaccination: Vaccination, session: Session = Depends(get_session)):
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # Ensure date fields are actual datetime objects for SQLite
    if isinstance(vaccination.date_given, str):
        vaccination.date_given = datetime.fromisoformat(vaccination.date_given)
    if isinstance(vaccination.expiration_date, str):
        vaccination.expiration_date = datetime.fromisoformat(vaccination.expiration_date)

    vaccination.pet_id = pet_id
    # Calculate hash for the record
    record_data = vaccination.dict(exclude={"id", "pet_id", "record_hash", "pet"})
    vaccination.record_hash = hash_service.hash_record(record_data)

    session.add(vaccination)

    # Log event
    event = LedgerEvent(
        pet_id=pet_id,
        event_type="VACCINATION",
        description=f"Vaccination added: {vaccination.vaccine_name}",
        timestamp=vaccination.date_given
    )
    session.add(event)
    session.commit()
    session.refresh(vaccination)
    return vaccination


@router.get("/pets/{pet_id}/vaccinations/export")
async def export_vaccinations(pet_id: UUID, session: Session = Depends(get_session)):
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    vaccinations = pet.vaccinations
    if not vaccinations:
        raise HTTPException(status_code=404, detail="No vaccinations found for this pet")

    # Generate aggregate hash for the export
    aggregate_data = [v.dict(exclude={"id", "pet_id", "record_hash", "pet"}) for v in vaccinations]
    export_hash = hash_service.hash_record({"pet_id": str(pet_id), "vaccinations": aggregate_data})

    pdf_path = pdf_service.generate_vaccination_report(pet.breed or "Pet", vaccinations, export_hash)
    return FileResponse(pdf_path, filename=f"{pet.breed or 'Pet'}_vaccinations.pdf")


@router.post("/pets/{pet_id}/shared-access")
async def create_shared_access(pet_id: UUID, hours: int = 24, session: Session = Depends(get_session)):
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    shared_access = SharedAccess(
        pet_id=pet_id,
        expires_at=datetime.utcnow() + timedelta(hours=hours)
    )
    session.add(shared_access)
    session.commit()
    session.refresh(shared_access)

    return {
        "access_url": f"/api/v1/shared/{shared_access.token}",
        "expires_at": shared_access.expires_at
    }


@router.get("/shared/{token}")
async def get_shared_access(token: str, session: Session = Depends(get_session)):
    statement = select(SharedAccess).where(SharedAccess.token == token)
    shared_access = session.exec(statement).first()

    if not shared_access or shared_access.expires_at < datetime.utcnow():
        raise HTTPException(status_code=403, detail="Access link expired or invalid")

    pet = shared_access.pet

    # Log Heartbeat Audit
    event = LedgerEvent(
        pet_id=pet.id,
        event_type="HEARTBEAT_ACCESS",
        description="Shared records accessed"
    )
    session.add(event)
    session.commit()

    # Notify owner
    if pet.owner and pet.owner.email:
        await email_service.notify_owner_of_access(pet.owner.email, pet.breed or "Pet", "Service Provider (Shared Link)")

    return {
        "pet": {
            "species": pet.pet_species,
            "breed": pet.breed,
            "dob": pet.dob,
        },
        "vaccinations": pet.vaccinations
    }


@router.post("/nudge/{chip_id}")
async def nudge_owner(chip_id: str, session: Session = Depends(get_session)):
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    if not pet.owner or not pet.owner.email:
        raise HTTPException(status_code=400, detail="Owner info not available for this pet")

    await email_service.send_email(
        pet.owner.email,
        f"Nudge: Someone found your pet {pet.name or ''}!",
        f"Hello,\n\nA registered PawsLedger user has found a pet with microchip {chip_id} and is nudging you to get in touch.\n\nPlease check your PawsLedger dashboard."
    )

    return {"message": "Nudge sent to owner successfully."}
