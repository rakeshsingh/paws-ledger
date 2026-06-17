"""Secure Nudge routes — free tier one-way + Verified tier bidirectional messaging."""

import html
import os
import re
import secrets
from datetime import timedelta
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlmodel import Session, select, func

from ...database import get_session
from ...models import Pet, NudgeSession, LedgerEvent, User, Subscription, _utc_now
from .common import email_service, get_current_user, validate_chip_id

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)

_HTML_TAG_RE = re.compile(r'<[^>]+>')


class NudgeRequest(BaseModel):
    message: str
    geo_latitude: Optional[float] = None
    geo_longitude: Optional[float] = None

    @field_validator('message')
    @classmethod
    def validate_message_length(cls, v):
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError('Message must be at least 10 characters')
        if len(stripped) > 500:
            raise ValueError('Message must be at most 500 characters')
        return stripped

    @field_validator('geo_latitude')
    @classmethod
    def validate_lat(cls, v):
        if v is not None and (v < -90 or v > 90):
            raise ValueError('Latitude must be between -90 and 90')
        return v

    @field_validator('geo_longitude')
    @classmethod
    def validate_lon(cls, v):
        if v is not None and (v < -180 or v > 180):
            raise ValueError('Longitude must be between -180 and 180')
        return v


class OwnerReplyRequest(BaseModel):
    response_token: str
    message: str

    @field_validator('message')
    @classmethod
    def validate_reply_length(cls, v):
        stripped = v.strip()
        if len(stripped) < 1:
            raise ValueError('Message cannot be empty')
        if len(stripped) > 1000:
            raise ValueError('Message must be at most 1000 characters')
        return stripped


def _sanitize(text: str) -> str:
    """Strip HTML tags and escape special characters."""
    text = _HTML_TAG_RE.sub('', text)
    return html.escape(text)


def _get_user_tier(user: User, session: Session) -> str:
    sub = session.exec(
        select(Subscription).where(Subscription.user_id == user.id)
    ).first()
    if not sub or sub.status != "active":
        return "free"
    return sub.tier


def _purge_expired_nudges(session: Session):
    """Remove NudgeSession records past their tier retention (30d free, 90d verified)."""
    cutoff_free = _utc_now() - timedelta(days=30)
    cutoff_verified = _utc_now() - timedelta(days=90)

    stale = session.exec(
        select(NudgeSession).where(NudgeSession.created_at < cutoff_verified)
    ).all()
    for record in stale:
        session.delete(record)

    # For free-tier users, purge records older than 30 days
    candidates = session.exec(
        select(NudgeSession).where(
            NudgeSession.created_at < cutoff_free,
            NudgeSession.created_at >= cutoff_verified,
        )
    ).all()
    for record in candidates:
        finder = session.get(User, record.finder_id)
        pet = session.get(Pet, record.pet_id)
        owner = session.get(User, pet.owner_id) if pet and pet.owner_id else None
        finder_tier = _get_user_tier(finder, session) if finder else "free"
        owner_tier = _get_user_tier(owner, session) if owner else "free"
        if finder_tier == "free" and owner_tier == "free":
            session.delete(record)


@router.post("/nudge/{chip_id}")
@limiter.limit("10/hour")
async def send_nudge(chip_id: str, payload: NudgeRequest, request: Request, session: Session = Depends(get_session)):
    """Send a secure nudge to a pet owner. Requires authentication."""
    finder = get_current_user(request, session)
    chip_id = validate_chip_id(chip_id)

    pet = session.exec(select(Pet).where(Pet.chip_id == chip_id)).first()
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")

    if not pet.owner_id:
        raise HTTPException(status_code=409, detail="This pet has no registered owner — nudge unavailable")

    if str(finder.id) == str(pet.owner_id):
        raise HTTPException(status_code=409, detail="You cannot nudge yourself")

    # Application-level rate limit: 3 nudges per finder per pet per 24h
    cutoff = _utc_now() - timedelta(hours=24)
    count = session.exec(
        select(func.count(NudgeSession.id)).where(
            NudgeSession.pet_id == pet.id,
            NudgeSession.finder_id == finder.id,
            NudgeSession.created_at >= cutoff,
        )
    ).one()
    if count >= 3:
        raise HTTPException(status_code=429, detail="Rate limit: maximum 3 nudges per pet per 24 hours")

    sanitized_message = _sanitize(payload.message)
    response_token = secrets.token_urlsafe(32)

    base_url = os.getenv('BASE_URL', 'https://www.pawsledger.com')
    finder_tier = _get_user_tier(finder, session)

    # GPS coordinates only accepted from Verified+ tier finders
    geo_lat = None
    geo_lon = None
    if payload.geo_latitude is not None and payload.geo_longitude is not None:
        if finder_tier in ("verified", "guardian"):
            geo_lat = payload.geo_latitude
            geo_lon = payload.geo_longitude

    # Build email — Verified owners get a callback URL for reply
    owner = pet.owner
    owner_tier = _get_user_tier(owner, session) if owner else "free"

    if owner_tier in ("verified", "guardian"):
        callback_url = f"{base_url}/nudge/reply?token={response_token}"
        sent = await email_service.send_nudge_alert_verified(
            owner.email, pet.name or pet.breed or "your pet",
            sanitized_message, callback_url,
            geo_lat=geo_lat, geo_lon=geo_lon,
        )
    else:
        dashboard_url = f"{base_url}/dashboard"
        sent = await email_service.send_nudge_alert(
            owner.email, pet.name or pet.breed or "your pet",
            sanitized_message, dashboard_url,
        )

    if not sent:
        raise HTTPException(status_code=502, detail="Unable to deliver notification. Please try again later.")

    nudge = NudgeSession(
        pet_id=pet.id,
        finder_id=finder.id,
        message=sanitized_message,
        response_token=response_token,
        expires_at=_utc_now() + timedelta(hours=48),
        geo_latitude=geo_lat,
        geo_longitude=geo_lon,
    )
    session.add(nudge)

    event = LedgerEvent(
        pet_id=pet.id,
        event_type="NUDGE_SENT",
        description="Secure nudge sent by a verified user",
    )
    session.add(event)

    _purge_expired_nudges(session)
    session.commit()

    return {"message": "Your nudge has been sent. The owner has been notified."}


# ─── Owner Reply Relay (Verified Tier — US-V02) ─────────────

@router.get("/nudge/reply")
async def get_reply_form(token: str, session: Session = Depends(get_session)):
    """GET renders reply context without invalidating the token (safe for link prefetch)."""
    nudge = session.exec(
        select(NudgeSession).where(NudgeSession.response_token == token)
    ).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found.")
    if nudge.is_resolved:
        raise HTTPException(status_code=410, detail="This link has already been used.")
    if _utc_now() > nudge.expires_at:
        raise HTTPException(status_code=410, detail="This link has expired. Ask the finder to send another nudge.")

    return {
        "pet_id": str(nudge.pet_id),
        "finder_message": nudge.message,
        "created_at": nudge.created_at.isoformat(),
        "expires_at": nudge.expires_at.isoformat(),
        "geo_latitude": nudge.geo_latitude,
        "geo_longitude": nudge.geo_longitude,
    }


@router.post("/nudge/reply")
async def submit_owner_reply(
    payload: OwnerReplyRequest,
    request: Request,
    session: Session = Depends(get_session),
):
    """Owner submits a reply to the finder (Verified tier). Invalidates token on success."""
    owner = get_current_user(request, session)

    nudge = session.exec(
        select(NudgeSession).where(NudgeSession.response_token == payload.response_token)
    ).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found.")
    if nudge.is_resolved:
        raise HTTPException(status_code=410, detail="This link has already been used.")
    if _utc_now() > nudge.expires_at:
        raise HTTPException(status_code=410, detail="This link has expired. Ask the finder to send another nudge.")

    # Verify the authenticated user is the pet's owner
    pet = session.get(Pet, nudge.pet_id)
    if not pet or str(pet.owner_id) != str(owner.id):
        raise HTTPException(status_code=403, detail="You are not the owner of this pet.")

    # Require Verified tier
    owner_tier = _get_user_tier(owner, session)
    if owner_tier not in ("verified", "guardian"):
        raise HTTPException(status_code=403, detail="Secure reply requires a Verified or Guardian subscription.")

    sanitized_reply = _sanitize(payload.message)

    # Send reply email to finder (masked sender)
    finder = session.get(User, nudge.finder_id)
    if not finder:
        raise HTTPException(status_code=500, detail="Finder account no longer exists.")

    sent = await email_service.send_owner_reply(
        finder_email=finder.email,
        pet_name=pet.name or pet.breed or "a pet",
        owner_reply=sanitized_reply,
    )
    if not sent:
        raise HTTPException(status_code=502, detail="Unable to deliver reply. Please try again later.")

    # Mark resolved and store reply
    nudge.is_resolved = True
    nudge.resolved_at = _utc_now()
    nudge.owner_response = sanitized_reply
    nudge.responded_at = _utc_now()
    session.add(nudge)
    session.commit()

    return {"message": "Your reply has been sent securely to the finder."}


# ─── Nudge History & Management (Verified Tier — US-V03) ─────

@router.get("/nudges/sent")
async def list_sent_nudges(request: Request, session: Session = Depends(get_session)):
    """List all nudges sent by the current user (Verified tier: full history)."""
    user = get_current_user(request, session)
    nudges = session.exec(
        select(NudgeSession).where(
            NudgeSession.finder_id == user.id,
            NudgeSession.deleted_by_finder == False,
        ).order_by(NudgeSession.created_at.desc())
    ).all()

    return [
        {
            "id": str(n.id),
            "pet_id": str(n.pet_id),
            "message": n.message[:80],
            "created_at": n.created_at.isoformat(),
            "is_resolved": n.is_resolved,
            "status": "responded" if n.is_resolved else ("expired" if _utc_now() > n.expires_at else "pending"),
        }
        for n in nudges
    ]


@router.get("/nudges/received")
async def list_received_nudges(request: Request, session: Session = Depends(get_session)):
    """List all nudges received for the current user's pets (Verified tier: full history)."""
    user = get_current_user(request, session)
    pet_ids = [p.id for p in user.pets]
    if not pet_ids:
        return []

    nudges = session.exec(
        select(NudgeSession).where(
            NudgeSession.pet_id.in_(pet_ids),
            NudgeSession.deleted_by_owner == False,
        ).order_by(NudgeSession.created_at.desc())
    ).all()

    return [
        {
            "id": str(n.id),
            "pet_id": str(n.pet_id),
            "message": n.message,
            "created_at": n.created_at.isoformat(),
            "is_resolved": n.is_resolved,
            "geo_latitude": n.geo_latitude,
            "geo_longitude": n.geo_longitude,
            "status": "responded" if n.is_resolved else ("expired" if _utc_now() > n.expires_at else "pending"),
        }
        for n in nudges
    ]


@router.delete("/nudges/{nudge_id}")
async def delete_nudge(nudge_id: UUID, request: Request, session: Session = Depends(get_session)):
    """Soft-delete a nudge from the current user's view (does not affect other party)."""
    user = get_current_user(request, session)
    nudge = session.get(NudgeSession, nudge_id)
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found.")

    if str(nudge.finder_id) == str(user.id):
        nudge.deleted_by_finder = True
    elif nudge.pet_id:
        pet = session.get(Pet, nudge.pet_id)
        if pet and str(pet.owner_id) == str(user.id):
            nudge.deleted_by_owner = True
        else:
            raise HTTPException(status_code=403, detail="Not authorized to delete this nudge.")
    else:
        raise HTTPException(status_code=403, detail="Not authorized to delete this nudge.")

    session.add(nudge)
    session.commit()
    return {"message": "Nudge deleted from your history."}


@router.post("/nudges/purge")
async def purge_expired_nudges(request: Request, session: Session = Depends(get_session)):
    """Purge expired nudge records (30d free, 90d verified). Cron-authenticated."""
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret and request.headers.get("x-cron-secret") != cron_secret:
        raise HTTPException(status_code=403, detail="Unauthorized.")

    _purge_expired_nudges(session)
    session.commit()
    return {"message": "Expired nudges purged."}
