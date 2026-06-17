"""Verified tier feature routes — ownership transfer, care instructions, vaccination alerts."""

import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select

from ...database import get_session
from ...models import (
    Pet, User, LedgerEvent, Vaccination, OwnershipTransfer,
    VaccinationAlert, VaccinationDocument, Subscription, _utc_now,
)
from ...services.r2_storage import R2StorageService
from .common import get_current_user, email_service, sanitize_text
from .subscription import get_user_tier

logger = logging.getLogger("pawsledger.verified")
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


# ─── Auth Helpers ────────────────────────────────────────────

def _require_verified(request: Request, session: Session = Depends(get_session)) -> User:
    """Require at least Verified tier."""
    user = get_current_user(request, session)
    tier = get_user_tier(user, session)
    if tier not in ("verified", "guardian"):
        raise HTTPException(
            status_code=403,
            detail="This feature requires a Verified or Guardian subscription.",
        )
    return user


def _get_owned_pet(pet_id: UUID, user: User, session: Session) -> Pet:
    """Get a pet owned by the user or raise 403."""
    pet = session.get(Pet, pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    if not pet.owner_id or str(pet.owner_id) != str(user.id):
        raise HTTPException(status_code=403, detail="You do not own this pet")
    return pet


# ═══════════════════════════════════════════════════════════════
# OWNERSHIP TRANSFER
# ═══════════════════════════════════════════════════════════════

class TransferInitiate(BaseModel):
    new_owner_email: str
    notes: Optional[str] = None

    @field_validator("new_owner_email")
    @classmethod
    def validate_email(cls, v):
        if not v or "@" not in v:
            raise ValueError("Valid email required")
        return v.strip().lower()


class TransferAccept(BaseModel):
    transfer_token: str


@router.post("/pets/{pet_id}/transfer")
async def initiate_transfer(
    pet_id: UUID,
    payload: TransferInitiate,
    request: Request,
    session: Session = Depends(get_session),
):
    """Initiate an ownership transfer (Verified tier required)."""
    user = _require_verified(request, session)
    pet = _get_owned_pet(pet_id, user, session)

    # Check no pending transfer exists
    existing = session.exec(
        select(OwnershipTransfer).where(
            OwnershipTransfer.pet_id == pet_id,
            OwnershipTransfer.status == "pending",
        )
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="A pending transfer already exists for this pet.")

    # Cannot transfer to yourself
    if payload.new_owner_email == user.email:
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself.")

    transfer = OwnershipTransfer(
        pet_id=pet_id,
        from_owner_id=user.id,
        to_owner_email=payload.new_owner_email,
        notes=sanitize_text(payload.notes) if payload.notes else None,
    )
    session.add(transfer)

    # Log event
    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="OWNERSHIP_CHANGE",
        description=f"Transfer initiated to {payload.new_owner_email}",
    ))
    session.commit()
    session.refresh(transfer)

    # Notify the new owner via email
    import os
    base_url = os.getenv("BASE_URL", "https://www.pawsledger.com")
    accept_url = f"{base_url}/transfer/accept?token={transfer.transfer_token}"

    await email_service.send_email(
        to_email=payload.new_owner_email,
        subject=f"PawsLedger: Pet ownership transfer for {pet.name}",
        body=(
            f"Hello,\n\n"
            f"{user.name} wants to transfer ownership of their pet '{pet.name}' "
            f"(Chip ID: {pet.chip_id}) to you on PawsLedger.\n\n"
            f"To accept this transfer, visit:\n{accept_url}\n\n"
            f"This link expires in 7 days.\n\n"
            f"— PawsLedger"
        ),
    )

    return {
        "message": "Transfer initiated. The new owner has been notified via email.",
        "transfer_id": str(transfer.id),
        "transfer_token": transfer.transfer_token,
        "expires_in": "7 days",
    }


@router.get("/transfer/details")
async def get_transfer_details(
    token: str,
    session: Session = Depends(get_session),
):
    """Get transfer details by token (public, no auth required).

    Returns limited info for the accept page to display context.
    """
    transfer = session.exec(
        select(OwnershipTransfer).where(
            OwnershipTransfer.transfer_token == token,
        )
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    pet = session.get(Pet, transfer.pet_id)
    from_user = session.get(User, transfer.from_owner_id)

    return {
        "status": transfer.status,
        "pet_name": pet.name if pet else "Unknown",
        "pet_species": pet.pet_species if pet else None,
        "chip_id": pet.chip_id if pet else None,
        "from_owner_name": from_user.name if from_user else "Unknown",
        "to_email": transfer.to_owner_email,
        "initiated_at": transfer.initiated_at.isoformat(),
        "notes": transfer.notes,
        "is_expired": _utc_now() > transfer.initiated_at + timedelta(days=7),
    }


@router.post("/transfer/accept")
async def accept_transfer(
    payload: TransferAccept,
    request: Request,
    session: Session = Depends(get_session),
):
    """Accept an ownership transfer (new owner must be logged in)."""
    user = get_current_user(request, session)

    transfer = session.exec(
        select(OwnershipTransfer).where(
            OwnershipTransfer.transfer_token == payload.transfer_token,
        )
    ).first()

    if not transfer:
        raise HTTPException(status_code=404, detail="Transfer not found.")

    if transfer.status != "pending":
        raise HTTPException(status_code=409, detail=f"Transfer is already {transfer.status}.")

    # Check expiry (7 days)
    if _utc_now() > transfer.initiated_at + timedelta(days=7):
        transfer.status = "expired"
        session.add(transfer)
        session.commit()
        raise HTTPException(status_code=410, detail="Transfer link has expired.")

    # Verify the accepting user matches the intended recipient
    if user.email != transfer.to_owner_email:
        raise HTTPException(
            status_code=403,
            detail="This transfer is intended for a different email address.",
        )

    # Execute transfer
    pet = session.get(Pet, transfer.pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet no longer exists.")

    old_owner_id = pet.owner_id
    pet.owner_id = user.id
    transfer.to_owner_id = user.id
    transfer.status = "accepted"
    transfer.completed_at = _utc_now()

    session.add(pet)
    session.add(transfer)
    session.add(LedgerEvent(
        pet_id=pet.id,
        event_type="OWNERSHIP_CHANGE",
        description=f"Ownership transferred from {old_owner_id} to {user.id}",
    ))
    session.commit()

    return {
        "message": f"You are now the registered owner of {pet.name}.",
        "pet_id": str(pet.id),
    }


@router.post("/pets/{pet_id}/transfer/cancel")
async def cancel_transfer(
    pet_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
):
    """Cancel a pending ownership transfer (Verified tier, original owner only)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    pending = session.exec(
        select(OwnershipTransfer).where(
            OwnershipTransfer.pet_id == pet_id,
            OwnershipTransfer.from_owner_id == user.id,
            OwnershipTransfer.status == "pending",
        )
    ).first()

    if not pending:
        raise HTTPException(status_code=404, detail="No pending transfer to cancel.")

    pending.status = "canceled"
    pending.completed_at = _utc_now()
    session.add(pending)
    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="OWNERSHIP_CHANGE",
        description=f"Transfer to {pending.to_owner_email} canceled by owner",
    ))
    session.commit()

    return {"message": "Transfer canceled successfully."}


@router.get("/pets/{pet_id}/transfer-history")
async def get_transfer_history(
    pet_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
):
    """Get ownership transfer history for a pet (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    transfers = session.exec(
        select(OwnershipTransfer)
        .where(OwnershipTransfer.pet_id == pet_id)
        .order_by(OwnershipTransfer.initiated_at.desc())
    ).all()

    return [
        {
            "id": str(t.id),
            "to_email": t.to_owner_email,
            "status": t.status,
            "initiated_at": t.initiated_at.isoformat(),
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
            "notes": t.notes,
        }
        for t in transfers
    ]


# ═══════════════════════════════════════════════════════════════
# CARE INSTRUCTIONS (stored on Pet model)
# ═══════════════════════════════════════════════════════════════

class CareInstructionsUpdate(BaseModel):
    energy_level: Optional[str] = None
    max_alone_hours: Optional[int] = None
    feeds_per_day: Optional[int] = None
    dietary_notes: Optional[str] = None
    exercise_needs: Optional[str] = None
    medical_conditions: Optional[str] = None
    temperament: Optional[str] = None
    care_notes: Optional[str] = None
    medication_notes: Optional[str] = None
    emergency_vet_name: Optional[str] = None
    emergency_vet_phone: Optional[str] = None
    care_priority: Optional[str] = None

    @field_validator("care_priority")
    @classmethod
    def validate_priority(cls, v):
        if v is not None and v not in ("normal", "important", "critical"):
            raise ValueError("care_priority must be normal, important, or critical")
        return v


@router.get("/pets/{pet_id}/care-instructions")
async def get_care_instructions(
    pet_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
):
    """Get care instructions for a pet (Verified tier)."""
    user = _require_verified(request, session)
    pet = _get_owned_pet(pet_id, user, session)

    return {
        "energy_level": pet.energy_level,
        "max_alone_hours": pet.max_alone_hours,
        "feeds_per_day": pet.feeds_per_day,
        "dietary_notes": pet.dietary_notes,
        "exercise_needs": pet.exercise_needs,
        "medical_conditions": pet.medical_conditions,
        "temperament": pet.temperament,
        "care_notes": pet.care_notes,
        "medication_notes": pet.medication_notes,
        "emergency_vet_name": pet.emergency_vet_name,
        "emergency_vet_phone": pet.emergency_vet_phone,
        "care_priority": pet.care_priority,
    }


@router.put("/pets/{pet_id}/care-instructions")
async def update_care_instructions(
    pet_id: UUID,
    payload: CareInstructionsUpdate,
    request: Request,
    session: Session = Depends(get_session),
):
    """Update care instructions for a pet (Verified tier)."""
    user = _require_verified(request, session)
    pet = _get_owned_pet(pet_id, user, session)

    if payload.energy_level is not None:
        pet.energy_level = payload.energy_level
    if payload.max_alone_hours is not None:
        pet.max_alone_hours = payload.max_alone_hours
    if payload.feeds_per_day is not None:
        pet.feeds_per_day = payload.feeds_per_day
    if payload.dietary_notes is not None:
        pet.dietary_notes = sanitize_text(payload.dietary_notes.strip()) if payload.dietary_notes else None
    if payload.exercise_needs is not None:
        pet.exercise_needs = sanitize_text(payload.exercise_needs.strip()) if payload.exercise_needs else None
    if payload.medical_conditions is not None:
        pet.medical_conditions = sanitize_text(payload.medical_conditions.strip()) if payload.medical_conditions else None
    if payload.temperament is not None:
        pet.temperament = sanitize_text(payload.temperament.strip()) if payload.temperament else None
    if payload.care_notes is not None:
        pet.care_notes = sanitize_text(payload.care_notes.strip()) if payload.care_notes else None
    if payload.medication_notes is not None:
        pet.medication_notes = sanitize_text(payload.medication_notes.strip()) if payload.medication_notes else None
    if payload.emergency_vet_name is not None:
        pet.emergency_vet_name = sanitize_text(payload.emergency_vet_name.strip()) if payload.emergency_vet_name else None
    if payload.emergency_vet_phone is not None:
        pet.emergency_vet_phone = sanitize_text(payload.emergency_vet_phone.strip()) if payload.emergency_vet_phone else None
    if payload.care_priority is not None:
        pet.care_priority = payload.care_priority

    session.add(pet)
    session.commit()
    session.refresh(pet)

    return {
        "message": "Care instructions updated.",
        "energy_level": pet.energy_level,
        "max_alone_hours": pet.max_alone_hours,
        "feeds_per_day": pet.feeds_per_day,
        "dietary_notes": pet.dietary_notes,
        "exercise_needs": pet.exercise_needs,
        "medical_conditions": pet.medical_conditions,
        "temperament": pet.temperament,
        "care_notes": pet.care_notes,
        "medication_notes": pet.medication_notes,
        "emergency_vet_name": pet.emergency_vet_name,
        "emergency_vet_phone": pet.emergency_vet_phone,
        "care_priority": pet.care_priority,
    }


# ═══════════════════════════════════════════════════════════════
# VACCINATION ALERTS
# ═══════════════════════════════════════════════════════════════

class AlertCreate(BaseModel):
    title: str
    alert_date: str  # YYYY-MM-DD
    description: Optional[str] = None
    alert_type: str = "vaccination_expiry"

    @field_validator("alert_date")
    @classmethod
    def validate_date(cls, v):
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError("Date must be YYYY-MM-DD format")
        return v


@router.get("/pets/{pet_id}/alerts")
async def list_alerts(
    pet_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
):
    """List vaccination/appointment alerts for a pet (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    alerts = session.exec(
        select(VaccinationAlert)
        .where(VaccinationAlert.pet_id == pet_id)
        .order_by(VaccinationAlert.alert_date)
    ).all()

    return [
        {
            "id": str(a.id),
            "title": a.title,
            "alert_type": a.alert_type,
            "alert_date": a.alert_date.strftime("%Y-%m-%d"),
            "description": a.description,
            "is_sent": a.is_sent,
        }
        for a in alerts
    ]


@router.post("/pets/{pet_id}/alerts")
async def create_alert(
    pet_id: UUID,
    payload: AlertCreate,
    request: Request,
    session: Session = Depends(get_session),
):
    """Create a vaccination/appointment alert (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    alert_date = datetime.strptime(payload.alert_date, "%Y-%m-%d")

    alert = VaccinationAlert(
        pet_id=pet_id,
        user_id=user.id,
        alert_type=payload.alert_type,
        alert_date=alert_date,
        title=payload.title,
        description=payload.description,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    return {
        "id": str(alert.id),
        "title": alert.title,
        "alert_date": alert.alert_date.strftime("%Y-%m-%d"),
        "alert_type": alert.alert_type,
    }


@router.delete("/pets/{pet_id}/alerts/{alert_id}")
async def delete_alert(
    pet_id: UUID,
    alert_id: UUID,
    request: Request,
    session: Session = Depends(get_session),
):
    """Delete an alert (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    alert = session.get(VaccinationAlert, alert_id)
    if not alert or alert.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="Alert not found")

    session.delete(alert)
    session.commit()
    return {"message": "Alert deleted."}


# ═══════════════════════════════════════════════════════════════
# VACCINATION DOCUMENT UPLOAD (R2)
# ═══════════════════════════════════════════════════════════════

@router.post("/pets/{pet_id}/vaccinations/upload")
@limiter.limit("5/hour")
async def upload_vaccination_document(
    pet_id: UUID,
    file: UploadFile = File(...),
    document_name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    request: Request = None,
    session: Session = Depends(get_session),
):
    """Upload a vaccination document (PDF/image) to R2 storage (Verified tier)."""
    user = _require_verified(request, session)
    pet = _get_owned_pet(pet_id, user, session)

    # Validate file type
    allowed_types = ("application/pdf", "image/jpeg", "image/png", "image/webp")
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {', '.join(allowed_types)}",
        )

    # Validate file size (max 10MB)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 10MB.")

    # Enforce document limit per tier
    existing_count = len(session.exec(
        select(VaccinationDocument).where(VaccinationDocument.pet_id == pet_id)
    ).all())
    tier = get_user_tier(user, session)
    max_docs = 1 if tier == "verified" else 100  # guardian gets up to 100
    if existing_count >= max_docs:
        raise HTTPException(
            status_code=400,
            detail=f"Document limit reached ({max_docs}). Delete old documents or upgrade your plan to upload more.",
        )

    # Upload to R2
    import uuid as _uuid
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "pdf"
    if ext not in ("pdf", "jpg", "jpeg", "png", "webp"):
        ext = "pdf"
    safe_filename = f"{_uuid.uuid4().hex[:12]}.{ext}"
    storage_key = f"vaccinations/{pet_id}/{safe_filename}"

    url = R2StorageService.upload_vaccination_doc(
        pet_id=str(pet_id),
        filename=safe_filename,
        file_content=content,
        content_type=file.content_type,
    )

    if not url:
        raise HTTPException(status_code=500, detail="File upload failed. Please try again.")

    # Persist document record
    doc = VaccinationDocument(
        pet_id=pet_id,
        filename=safe_filename,
        original_filename=file.filename or safe_filename,
        content_type=file.content_type,
        file_size=len(content),
        storage_key=storage_key,
        url=url,
        document_name=document_name.strip() if document_name else None,
        description=description.strip() if description else None,
    )
    session.add(doc)

    # Log event
    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="VACCINATION",
        description=f"Vaccination report uploaded: {file.filename}",
    ))
    session.commit()
    session.refresh(doc)

    return {
        "message": "Document uploaded successfully.",
        "id": str(doc.id),
        "url": url,
        "filename": doc.original_filename,
    }


@router.get("/pets/{pet_id}/vaccinations/documents")
async def list_vaccination_documents(
    pet_id: UUID,
    request: Request = None,
    session: Session = Depends(get_session),
):
    """List uploaded vaccination documents for a pet (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    docs = session.exec(
        select(VaccinationDocument)
        .where(VaccinationDocument.pet_id == pet_id)
        .order_by(VaccinationDocument.uploaded_at.desc())
    ).all()

    return [
        {
            "id": str(d.id),
            "filename": d.original_filename,
            "content_type": d.content_type,
            "file_size": d.file_size,
            "uploaded_at": d.uploaded_at.isoformat(),
            "notes": d.notes,
        }
        for d in docs
    ]


@router.get("/pets/{pet_id}/vaccinations/documents/{doc_id}/download")
async def download_vaccination_document(
    pet_id: UUID,
    doc_id: UUID,
    request: Request = None,
    session: Session = Depends(get_session),
):
    """Get a presigned download URL for a vaccination document (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    doc = session.get(VaccinationDocument, doc_id)
    if not doc or doc.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="Document not found")

    presigned = R2StorageService.generate_presigned_url(doc.storage_key, expires_in=3600)
    if presigned:
        return RedirectResponse(url=presigned)

    raise HTTPException(status_code=500, detail="Unable to generate download URL.")


@router.delete("/pets/{pet_id}/vaccinations/documents/{doc_id}")
async def delete_vaccination_document(
    pet_id: UUID,
    doc_id: UUID,
    request: Request = None,
    session: Session = Depends(get_session),
):
    """Delete a vaccination document (Verified tier)."""
    user = _require_verified(request, session)
    _get_owned_pet(pet_id, user, session)

    doc = session.get(VaccinationDocument, doc_id)
    if not doc or doc.pet_id != pet_id:
        raise HTTPException(status_code=404, detail="Document not found")

    R2StorageService.delete_file(doc.storage_key)
    session.delete(doc)
    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="VACCINATION",
        description=f"Vaccination report removed: {doc.original_filename}",
    ))
    session.commit()

    return {"message": "Document deleted."}


# ═══════════════════════════════════════════════════════════════
# PERIODIC CONTACT UPDATE REMINDER (check endpoint)
# ═══════════════════════════════════════════════════════════════

@router.post("/subscription/send-vaccination-alerts")
async def send_vaccination_alerts(
    request: Request,
    session: Session = Depends(get_session),
):
    """Send vaccination/appointment alert emails with advance notice.

    Designed to be called daily by a cron job.
    Sends alerts that haven't been sent yet and whose alert_date is within
    the next 7 days (advance_days) or already past (overdue).
    This gives users time to schedule before the actual due date.
    """
    import os
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret and request.headers.get("x-cron-secret") != cron_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")

    now = _utc_now()
    advance_window = now + timedelta(days=7)

    # Send alerts due within the next 7 days or already overdue
    pending_alerts = session.exec(
        select(VaccinationAlert).where(
            VaccinationAlert.is_sent == False,
            VaccinationAlert.alert_date <= advance_window,
        )
    ).all()

    sent_count = 0
    failed_count = 0

    for alert in pending_alerts:
        user = session.get(User, alert.user_id)
        if not user:
            continue

        pet = session.get(Pet, alert.pet_id)
        pet_name = pet.name if pet else "your pet"

        is_overdue = alert.alert_date <= now
        days_until = (alert.alert_date - now).days
        urgency = "OVERDUE" if is_overdue else f"due in {days_until} day{'s' if days_until != 1 else ''}"

        try:
            await email_service.send_email(
                to_email=user.email,
                subject=f"PawsLedger: {alert.title} ({urgency})",
                body=(
                    f"Hi {user.name},\n\n"
                    f"This is a reminder for {pet_name}:\n\n"
                    f"  {alert.title}\n"
                    f"  Due: {alert.alert_date.strftime('%B %d, %Y')} ({urgency})\n"
                    + (f"  Details: {alert.description}\n" if alert.description else "")
                    + f"\nPlease schedule or confirm the appointment soon.\n\n"
                    f"— PawsLedger"
                ),
            )
            alert.is_sent = True
            alert.sent_at = now
            session.add(alert)
            sent_count += 1
        except Exception as e:
            logger.error("Failed to send alert %s: %s", alert.id, e)
            failed_count += 1

    session.commit()
    return {"message": f"Sent {sent_count} alerts, {failed_count} failed."}


@router.post("/subscription/send-update-reminders")
async def send_contact_update_reminders(
    request: Request,
    session: Session = Depends(get_session),
):
    """Send periodic contact update reminders to Verified users.

    This endpoint is designed to be called by a cron job (e.g., monthly).
    It sends a reminder only if the user hasn't updated their profile
    in 90+ days AND hasn't already been reminded in the last 90 days.
    """
    import os
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret and request.headers.get("x-cron-secret") != cron_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")

    active_subs = session.exec(
        select(Subscription).where(Subscription.status == "active")
    ).all()

    now = _utc_now()
    reminder_threshold = now - timedelta(days=90)
    sent_count = 0
    skipped_count = 0

    for sub in active_subs:
        user = session.get(User, sub.user_id)
        if not user:
            continue

        # Skip if profile was updated within the last 90 days
        if user.profile_updated_at and user.profile_updated_at > reminder_threshold:
            skipped_count += 1
            continue

        # Skip if already reminded within the last 90 days
        if user.contact_reminded_at and user.contact_reminded_at > reminder_threshold:
            skipped_count += 1
            continue

        await email_service.send_email(
            to_email=user.email,
            subject="PawsLedger: Keep your contact info current",
            body=(
                f"Hi {user.name},\n\n"
                "This is a friendly reminder to verify that your contact information "
                "on PawsLedger is still accurate. Up-to-date details ensure you can "
                "be reached quickly if your pet is ever found.\n\n"
                "Please visit your profile to confirm:\n"
                f"{os.getenv('BASE_URL', 'https://www.pawsledger.com')}/owner/profile\n\n"
                "— PawsLedger"
            ),
        )
        user.contact_reminded_at = now
        session.add(user)
        sent_count += 1

    session.commit()
    return {"message": f"Reminders sent to {sent_count} users, {skipped_count} skipped."}


# ═══════════════════════════════════════════════════════════════
# PET PHOTO UPLOAD (R2)
# ═══════════════════════════════════════════════════════════════

@router.post("/pets/{pet_id}/photo")
@limiter.limit("10/hour")
async def upload_pet_photo(
    pet_id: UUID,
    file: UploadFile = File(...),
    request: Request = None,
    session: Session = Depends(get_session),
):
    """Upload a pet profile photo to R2 storage (Verified/Guardian tier required)."""
    user = _require_verified(request, session)
    pet = _get_owned_pet(pet_id, user, session)

    # Validate file type
    allowed_types = ("image/jpeg", "image/png", "image/webp")
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Accepted: {', '.join(allowed_types)}",
        )

    # Validate file size (max 5MB)
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 5MB.")

    # Upload to R2
    import uuid as _uuid
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else "jpg"
    if ext not in ("jpg", "jpeg", "png", "webp"):
        ext = "jpg"
    safe_filename = f"{_uuid.uuid4().hex[:12]}.{ext}"

    url = R2StorageService.upload_pet_photo(
        pet_id=str(pet_id),
        filename=safe_filename,
        file_content=content,
        content_type=file.content_type,
    )

    if not url:
        raise HTTPException(status_code=500, detail="Photo upload failed. Please try again.")

    # Update pet record with new photo URL
    pet.photo_url = url
    session.add(pet)
    session.add(LedgerEvent(
        pet_id=pet_id,
        event_type="PROFILE_UPDATE",
        description="Pet profile photo updated",
    ))
    session.commit()

    return {
        "message": "Photo uploaded successfully.",
        "photo_url": url,
    }


@router.delete("/pets/{pet_id}/photo")
async def delete_pet_photo(
    pet_id: UUID,
    request: Request = None,
    session: Session = Depends(get_session),
):
    """Remove a pet's profile photo (Verified/Guardian tier required)."""
    user = _require_verified(request, session)
    pet = _get_owned_pet(pet_id, user, session)

    if not pet.photo_url:
        raise HTTPException(status_code=404, detail="No photo to remove.")

    # Try to delete from R2 (best effort)
    old_url = pet.photo_url
    # Extract key from URL
    for prefix in (
        os.getenv("R2_PUBLIC_URL", ""),
        f"https://{os.getenv('R2_BUCKET_NAME', 'pawsledger-files')}.r2.dev",
    ):
        if prefix and old_url.startswith(prefix):
            key = old_url[len(prefix):].lstrip("/")
            R2StorageService.delete_file(key)
            break

    pet.photo_url = None
    session.add(pet)
    session.commit()

    return {"message": "Photo removed."}


@router.get("/pets/{pet_id}/photo")
async def get_pet_photo(
    pet_id: UUID,
    session: Session = Depends(get_session),
):
    """Serve a pet's profile photo via presigned R2 URL redirect."""
    pet = session.get(Pet, pet_id)
    if not pet or not pet.photo_url:
        raise HTTPException(status_code=404, detail="No photo available.")

    photo_url = pet.photo_url

    # Extract R2 object key from stored URL
    r2_public_url = os.getenv("R2_PUBLIC_URL", "")
    r2_bucket = os.getenv("R2_BUCKET_NAME", "pawsledger-files")
    key = None
    for prefix in (
        r2_public_url,
        f"https://{r2_bucket}.r2.dev",
        f"https://{os.getenv('R2_ACCOUNT_ID', '')}.r2.cloudflarestorage.com",
    ):
        if prefix and photo_url.startswith(prefix):
            key = photo_url[len(prefix):].lstrip("/")
            break

    if not key:
        raise HTTPException(status_code=500, detail="Unable to resolve photo storage key.")

    presigned = R2StorageService.generate_presigned_url(key, expires_in=3600)
    if presigned:
        return RedirectResponse(url=presigned)

    raise HTTPException(status_code=500, detail="Unable to generate photo URL.")


# ═══════════════════════════════════════════════════════════════
# DATABASE BACKUP (cron endpoint)
# ═══════════════════════════════════════════════════════════════

@router.post("/admin/backup")
async def trigger_database_backup(request: Request):
    """Backup the SQLite database to R2 storage.

    Designed to be called daily by a cron job.
    Authenticated via x-cron-secret header.
    Also prunes backups older than 30 days.
    """
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret and request.headers.get("x-cron-secret") != cron_secret:
        raise HTTPException(status_code=403, detail="Unauthorized")

    # Resolve database path from DATABASE_URL
    db_url = os.getenv("DATABASE_URL", "sqlite:///./pawsledger.db")
    if db_url.startswith("sqlite:///"):
        db_path = db_url.replace("sqlite:///", "", 1)
    else:
        db_path = "pawsledger.db"

    key = R2StorageService.backup_database(db_path)
    if not key:
        raise HTTPException(status_code=500, detail="Backup failed. Check R2 configuration.")

    pruned = R2StorageService.prune_old_backups(keep_days=30)

    return {
        "message": "Backup completed successfully.",
        "key": key,
        "pruned_count": pruned,
    }
