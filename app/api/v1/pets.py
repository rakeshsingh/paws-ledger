"""Pet routes — lookup, QR, nudge, transfer, vaccinations, shared access, tags."""

import re
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select
from ...database import get_session
from ...models import Pet, LedgerEvent, Vaccination, SharedAccess, PetTag, User
from .common import aaha_client, email_service, hash_service, pdf_service, serializer, IS_PRODUCTION
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

# ISO 11784/11785 chip ID pattern: exactly 15 digits
CHIP_ID_PATTERN = re.compile(r'^\d{15}$')


# ─── Auth Dependency ─────────────────────────────────────────

def _get_current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Extract authenticated user from cookie. Raises 401 if not authenticated."""
    raw_cookie = request.cookies.get("paws_user_id")
    if not raw_cookie:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        user_id = serializer.loads(raw_cookie)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid session")
    user = session.get(User, UUID(user_id))
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def _verify_pet_ownership(pet: Pet, user: User):
    """Verify the user owns the pet. Raises 403 if not."""
    if not pet.owner_id or str(pet.owner_id) != str(user.id):
        raise HTTPException(status_code=403, detail="You do not own this pet")


def _validate_chip_id(chip_id: str) -> str:
    """Validate chip ID format. Returns cleaned chip_id or raises 400."""
    chip_id = chip_id.strip()
    if not CHIP_ID_PATTERN.match(chip_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid chip ID format. Must be exactly 15 digits (ISO 11784/11785)."
        )
    return chip_id


# ─── Tag Schemas ─────────────────────────────────────────────

class TagCreate(BaseModel):
    tag_type: str = "QR"
    tag_code: Optional[str] = None
    serial_number: Optional[str] = None
    manufacturer: Optional[str] = None
    nfc_uid: Optional[str] = None
    nfc_technology: Optional[str] = None
    label: Optional[str] = None
    notes: Optional[str] = None

    @field_validator('tag_type')
    @classmethod
    def validate_tag_type(cls, v):
        if v not in ('QR', 'NFC', 'DUAL'):
            raise ValueError('tag_type must be QR, NFC, or DUAL')
        return v

    @field_validator('label', 'notes', 'serial_number', 'manufacturer')
    @classmethod
    def validate_max_length(cls, v):
        if v and len(v) > 255:
            raise ValueError('Field must be 255 characters or less')
        return v


class TagUpdate(BaseModel):
    label: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = None

    @field_validator('status')
    @classmethod
    def validate_status(cls, v):
        if v and v not in ('ACTIVE', 'DEACTIVATED', 'LOST', 'REPLACED'):
            raise ValueError('status must be ACTIVE, DEACTIVATED, LOST, or REPLACED')
        return v


class VaccinationCreate(BaseModel):
    """Input schema for vaccination — only accepts user-provided fields."""
    vaccine_name: str
    manufacturer: Optional[str] = None
    serial_number: Optional[str] = None
    date_given: str  # YYYY-MM-DD
    expiration_date: str  # YYYY-MM-DD
    administering_vet: Optional[str] = None
    clinic_name: Optional[str] = None

    @field_validator('vaccine_name')
    @classmethod
    def validate_vaccine_name(cls, v):
        if not v or len(v.strip()) == 0:
            raise ValueError('vaccine_name is required')
        if len(v) > 200:
            raise ValueError('vaccine_name must be 200 characters or less')
        return v.strip()


@router.get("/lookup/{chip_id}")
@limiter.limit("30/minute")
async def lookup_pet(chip_id: str, request: Request, session: Session = Depends(get_session)):
    chip_id = _validate_chip_id(chip_id)
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
@limiter.limit("20/minute")
async def resolve_qr(tag_id: str, request: Request, session: Session = Depends(get_session)):
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
async def transfer_ownership(
    chip_id: str, new_owner_email: str,
    request: Request,
    session: Session = Depends(get_session),
):
    chip_id = _validate_chip_id(chip_id)
    user = _get_current_user(request, session)
    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    _verify_pet_ownership(pet, user)

    return {"message": f"Transfer of {chip_id} to {new_owner_email} initiated."}


@router.post("/pets/{pet_id}/vaccinations")
async def add_vaccination(
    pet_id: UUID, payload: VaccinationCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    user = _get_current_user(request, session)
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    _verify_pet_ownership(pet, user)

    try:
        date_given = datetime.strptime(payload.date_given, '%Y-%m-%d')
        expiration_date = datetime.strptime(payload.expiration_date, '%Y-%m-%d')
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD.")

    vaccination = Vaccination(
        pet_id=pet_id,
        vaccine_name=payload.vaccine_name,
        manufacturer=payload.manufacturer or "",
        serial_number=payload.serial_number or "",
        date_given=date_given,
        expiration_date=expiration_date,
        administering_vet=payload.administering_vet or "",
        clinic_name=payload.clinic_name or "",
    )
    record_data = vaccination.dict(exclude={"id", "pet_id", "record_hash", "pet"})
    vaccination.record_hash = hash_service.hash_record(record_data)

    session.add(vaccination)
    event = LedgerEvent(
        pet_id=pet_id,
        event_type="VACCINATION",
        description=f"Vaccination added: {vaccination.vaccine_name}",
        timestamp=date_given,
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
async def create_shared_access(
    pet_id: UUID, hours: int = 24,
    request: Request = None,
    session: Session = Depends(get_session),
):
    user = _get_current_user(request, session)
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    _verify_pet_ownership(pet, user)

    # Limit hours to reasonable range
    hours = max(1, min(hours, 168))  # 1 hour to 7 days

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
@limiter.limit("3/hour")
async def nudge_owner(chip_id: str, request: Request, session: Session = Depends(get_session)):
    """Nudge a pet owner. Requires authentication. Returns consistent response."""
    chip_id = _validate_chip_id(chip_id)
    # Require authentication to nudge
    _get_current_user(request, session)

    statement = select(Pet).where(Pet.chip_id == chip_id)
    pet = session.exec(statement).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    # Send notification if possible, but always return the same response
    # to prevent email existence oracle attacks
    if pet.owner and pet.owner.email:
        await email_service.send_email(
            pet.owner.email,
            f"Nudge: Someone found your pet!",
            f"Hello,\n\nA registered PawsLedger user has found a pet with microchip "
            f"{chip_id} and is nudging you to get in touch.\n\n"
            f"Please check your PawsLedger dashboard."
        )

    # Always return success — don't reveal whether owner has email
    return {"message": "If the owner has notifications enabled, they have been alerted."}


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
async def create_tag(
    pet_id: UUID, payload: TagCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    """Create and link a new NFC/QR tag to a pet. Requires ownership."""
    user = _get_current_user(request, session)
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    _verify_pet_ownership(pet, user)

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
    request: Request,
    session: Session = Depends(get_session),
):
    """Update a tag's label, notes, or status. Requires ownership."""
    user = _get_current_user(request, session)
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    _verify_pet_ownership(pet, user)

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
async def delete_tag(
    pet_id: UUID, tag_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
):
    """Permanently remove a tag. Requires ownership."""
    user = _get_current_user(request, session)
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    _verify_pet_ownership(pet, user)

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
@limiter.limit("20/minute")
async def resolve_tag(tag_code: str, request: Request, session: Session = Depends(get_session)):
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
