"""Pet routes — lookup, QR, nudge, transfer, vaccinations, shared access, tags."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlmodel import Session, select
from ...database import get_session
from ...models import Pet, LedgerEvent, Vaccination, SharedAccess, PetTag
from .common import aaha_client, email_service, hash_service, pdf_service
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta

router = APIRouter()


# ─── Tag Schemas ─────────────────────────────────────────────

class TagCreate(BaseModel):
    tag_type: str = "QR"            # QR, NFC, DUAL
    tag_code: Optional[str] = None  # Auto-generated if not provided
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    nfc_uid: Optional[str] = None
    nfc_technology: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None


class TagUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None    # ACTIVE, DEACTIVATED, LOST, REPLACED


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


# ─── Tag Management Endpoints ────────────────────────────────

@router.get("/pets/{pet_id}/tags")
async def list_tags(pet_id: UUID, session: Session = Depends(get_session)):
    """List all tags for a pet."""
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return [
        {
            "id": str(tag.id),
            "tag_type": tag.tag_type,
            "tag_code": tag.tag_code,
            "serial_number": tag.serial_number,
            "manufacturer": tag.manufacturer,
            "status": tag.status,
            "activated_at": tag.activated_at.isoformat() if tag.activated_at else None,
            "deactivated_at": tag.deactivated_at.isoformat() if tag.deactivated_at else None,
            "nfc_uid": tag.nfc_uid,
            "nfc_technology": tag.nfc_technology,
            "qr_url": tag.qr_url,
            "label": tag.label,
            "notes": tag.notes,
        }
        for tag in pet.tags
    ]


@router.post("/pets/{pet_id}/tags")
async def create_tag(pet_id: UUID, payload: TagCreate, session: Session = Depends(get_session)):
    """Create and link a new NFC/QR tag to a pet."""
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # Generate tag_code if not provided
    tag_code = payload.tag_code or str(uuid4()).replace("-", "")[:12].upper()

    # Check uniqueness
    existing = session.exec(
        select(PetTag).where(PetTag.tag_code == tag_code)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tag code already registered")

    # Build QR URL
    qr_url = f"/qr/tag/{tag_code}"

    new_tag = PetTag(
        pet_id=pet_id,
        tag_type=payload.tag_type,
        tag_code=tag_code,
        serial_number=payload.serial_number,
        manufacturer=payload.manufacturer,
        nfc_uid=payload.nfc_uid,
        nfc_technology=payload.nfc_technology,
        qr_url=qr_url,
        label=payload.label,
        notes=payload.notes,
    )
    session.add(new_tag)

    # Log event
    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="TAG_ACTIVATED",
        description=f"{payload.tag_type} tag activated: {tag_code}"
        + (f" ({payload.label})" if payload.label else ""),
    ))
    session.commit()
    session.refresh(new_tag)

    return {
        "id": str(new_tag.id),
        "tag_type": new_tag.tag_type,
        "tag_code": new_tag.tag_code,
        "qr_url": new_tag.qr_url,
        "status": new_tag.status,
        "label": new_tag.label,
    }


@router.put("/pets/{pet_id}/tags/{tag_id}")
async def update_tag(
    pet_id: UUID, tag_id: UUID, payload: TagUpdate,
    session: Session = Depends(get_session),
):
    """Update a tag's label, notes, or status."""
    tag = session.get(PetTag, tag_id)
    if not tag or tag.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="Tag not found")

    if payload.label is not None:
        tag.label = payload.label
    if payload.notes is not None:
        tag.notes = payload.notes
    if payload.status is not None:
        old_status = tag.status
        tag.status = payload.status
        if payload.status == "DEACTIVATED" and old_status != "DEACTIVATED":
            tag.deactivated_at = datetime.utcnow()
            session.add(LedgerEvent(
                pet_id=pet_id,
                event_type="TAG_DEACTIVATED",
                description=f"Tag deactivated: {tag.tag_code}"
                + (f" ({tag.label})" if tag.label else ""),
            ))
        elif payload.status == "ACTIVE" and old_status != "ACTIVE":
            tag.deactivated_at = None
            session.add(LedgerEvent(
                pet_id=pet_id,
                event_type="TAG_ACTIVATED",
                description=f"Tag reactivated: {tag.tag_code}"
                + (f" ({tag.label})" if tag.label else ""),
            ))

    session.add(tag)
    session.commit()
    session.refresh(tag)

    return {
        "id": str(tag.id),
        "tag_type": tag.tag_type,
        "tag_code": tag.tag_code,
        "status": tag.status,
        "label": tag.label,
        "notes": tag.notes,
    }


@router.delete("/pets/{pet_id}/tags/{tag_id}")
async def delete_tag(pet_id: UUID, tag_id: UUID, session: Session = Depends(get_session)):
    """Permanently remove a tag."""
    tag = session.get(PetTag, tag_id)
    if not tag or tag.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="Tag not found")

    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="TAG_REMOVED",
        description=f"Tag removed: {tag.tag_code}"
        + (f" ({tag.label})" if tag.label else ""),
    ))
    session.delete(tag)
    session.commit()
    return {"message": "Tag removed successfully"}


@router.get("/qr/tag/{tag_code}")
async def resolve_tag(tag_code: str, session: Session = Depends(get_session)):
    """Resolve a physical tag code to a pet profile (public endpoint for QR/NFC scans)."""
    tag = session.exec(
        select(PetTag).where(PetTag.tag_code == tag_code)
    ).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not registered")
    if tag.status != "ACTIVE":
        raise HTTPException(status_code=410, detail="Tag is no longer active")

    pet = tag.pet

    # Log scan event
    session.add(LedgerEvent(
        pet_id=pet.id,
        event_type="EMERGENCY_SCAN",
        description=f"Tag scanned: {tag.tag_code} ({tag.tag_type})",
    ))
    session.commit()

    # Notify owner
    if pet.owner and pet.owner.email:
        await email_service.notify_owner_of_scan(
            pet.owner.email, pet.breed or "Pet"
        )

    return {
        "pet_id": str(pet.id),
        "pet_species": pet.pet_species,
        "breed": pet.breed,
        "identity_status": pet.identity_status,
        "tag_type": tag.tag_type,
        "chip_id": pet.chip_id,
        "profile_url": f"/pet/{pet.id}",
    }
